#!/usr/bin/env python3
"""Мини-CRM клиента сопровождения: создаёт рабочий документ в Google Sheets.

Форма повторяет «Левша Рабочий документ», доказавший себя на практике:
сырьё обращений отдельно, показатели считаются формулами, очередь проверок
рядом. Отличие — показатели считаются автоматически из листа учёта, поэтому
сотрудник клиента заполняет одну строку на обращение, а не отчёт.

Листы:
    Шапка            — кто, чек, каналы, исполнители, ссылки
    Учёт обращений   — сырьё: одна строка = одно обращение (ведёт клиент)
    Показатели       — недели, формулы из учёта; расход проставляется руками
    Тесты            — что проверяем, гипотеза, даты, результат
    Сделано          — журнал: что появилось в системе

Порядок: владелец создаёт пустую таблицу и даёт доступ сервисному аккаунту
(hypercrm-sheets@neon-lock-151817.iam.gserviceaccount.com, роль «Редактор»),
дальше скрипт раскладывает в ней листы, формулы и проверки. Сам аккаунт файлы
создавать не может: у сервисных аккаунтов вне Workspace нет места на Диске.

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/sheets/create-client-crm.py "Стиралкин" --sheet <ID>
    ... --weeks 26                          # сколько недель разметить вперёд
    ... --share someone@example.com         # добавить ещё редакторов
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[3]
KEY = ROOT / "system" / "secrets" / "gsheets-key.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

SOURCES = ["Яндекс Директ", "Авито", "ВК", "Карты", "Сайт (органика)", "Рекомендация", "Повторный"]
STATUSES = ["новое", "в работе", "продажа", "отказ"]


def services():
    creds = service_account.Credentials.from_service_account_file(str(KEY), scopes=SCOPES)
    return build("sheets", "v4", credentials=creds), build("drive", "v3", credentials=creds)


def header_rows(client: str) -> list[list]:
    today = dt.date.today().isoformat()
    return [
        [f"{client} — рабочий документ"],
        ["Внутренний документ сопровождения. Клиенту показываем лист «Учёт обращений» — его ведут его сотрудники."],
        [],
        ["Клиент", client],
        ["Чек и состав", "50 000 ₽ управление + ___ исполнение"],
        ["Каналы", ""],
        ["Исполнители", ""],
        ["Кто ведёт учёт", "имя сотрудника клиента"],
        ["Ведём с", today],
        [],
        ["Как это работает"],
        ["1. Сотрудник клиента пишет каждое обращение строкой в «Учёт обращений» — минута в день."],
        ["2. «Показатели» считаются сами; руками проставляется только расход на рекламу."],
        ["3. Раз в неделю — разбор: что сдвинулось, что тестируем дальше."],
        ["4. Раз в месяц из этих данных собирается документ для клиента."],
        ["5. Задачи команде живут в YouGile, здесь — только факты и результаты."],
    ]


def intake_rows() -> list[list]:
    return [
        ["Дата", "Источник", "Кто обратился", "Целевое", "Услуга", "Статус", "Сумма", "Заметка"],
        [dt.date.today().isoformat(), SOURCES[0], "пример: Ирина, +7...", "да", "химчистка ковра", "продажа", 4500,
         "строка-пример, удалить"],
    ]


def metrics_rows(weeks: int) -> list[list]:
    """Недельная сетка с формулами по листу учёта."""
    header = ["Неделя с", "по", "Расход", "Обращений", "Целевых", "Продаж", "Выручка",
              "CR в целевые", "CR целевое→продажа", "Стоимость продажи", "ДРР"]
    today = dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    rows = [header]
    for i in range(weeks):
        start = monday + dt.timedelta(weeks=i)
        end = start + dt.timedelta(days=6)
        r = i + 2  # номер строки в таблице
        intake = "'Учёт обращений'"
        window = f"{intake}!$A:$A,\">=\"&$A{r},{intake}!$A:$A,\"<=\"&$B{r}"
        rows.append([
            start.isoformat(),
            end.isoformat(),
            "",  # расход — руками из кабинетов
            f"=COUNTIFS({window})",
            f"=COUNTIFS({window},{intake}!$D:$D,\"да\")",
            f"=COUNTIFS({window},{intake}!$F:$F,\"продажа\")",
            f"=SUMIFS({intake}!$G:$G,{window})",
            f"=IFERROR(E{r}/D{r},\"\")",
            f"=IFERROR(F{r}/E{r},\"\")",
            f"=IFERROR(C{r}/F{r},\"\")",
            f"=IFERROR(C{r}/G{r},\"\")",
        ])
    return rows


def tests_rows() -> list[list]:
    return [
        ["Статус", "Что тестируем", "Гипотеза", "Запущено", "Смотрим", "Результат", "Вывод"],
        ["идёт", "оффер на посадочной", "если назвать срок, заявок станет больше", "", "", "", ""],
        ["", "", "Правило: тест без даты «смотрим» — не тест, а идея.", "", "", "", ""],
    ]


def done_rows() -> list[list]:
    return [
        ["Дата", "Что появилось", "Ссылка"],
        ["", "Строка появляется, только если после неё что-то существует: страница, скрипт, регламент, отключённый источник.", ""],
    ]


def build_document(client: str, weeks: int, share_with: list[str], sid: str) -> tuple[str, str]:
    """Наполняет существующую таблицу структурой мини-CRM.

    Таблицу создаёт владелец волта и расшаривает сервисному аккаунту: у самого
    аккаунта нет места на Диске (квота 0), создавать файлы он не может — это
    свойство сервисных аккаунтов вне Workspace, а не настройка.
    """
    sheets, drive = services()
    tabs = ["Шапка", "Учёт обращений", "Показатели", "Тесты", "Сделано"]

    meta = sheets.spreadsheets().get(spreadsheetId=sid).execute()
    existing = {s["properties"]["title"] for s in meta["sheets"]}
    add = [{"addSheet": {"properties": {"title": name}}} for name in tabs if name not in existing]
    if add:
        sheets.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": add}).execute()
        meta = sheets.spreadsheets().get(spreadsheetId=sid).execute()
    created = meta

    payload = [
        ("Шапка!A1", header_rows(client)),
        ("'Учёт обращений'!A1", intake_rows()),
        ("Показатели!A1", metrics_rows(weeks)),
        ("Тесты!A1", tests_rows()),
        ("Сделано!A1", done_rows()),
    ]
    sheets.spreadsheets().values().batchUpdate(spreadsheetId=sid, body={
        "valueInputOption": "USER_ENTERED",
        "data": [{"range": rng, "values": values} for rng, values in payload],
    }).execute()

    ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in created["sheets"]}
    requests = []
    for name in tabs:
        requests.append({"repeatCell": {
            "range": {"sheetId": ids[name], "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }})
    for name in ("Учёт обращений", "Показатели", "Тесты", "Сделано"):
        requests.append({"updateSheetProperties": {
            "properties": {"sheetId": ids[name], "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }})
    # Выпадающие списки там, где ошибка в написании ломает формулы
    validations = [
        ("Учёт обращений", 1, 3, ["да", "нет"]),      # столбец D — целевое
        ("Учёт обращений", 5, 5, STATUSES),            # столбец F — статус
        ("Учёт обращений", 1, 1, SOURCES),             # столбец B — источник
    ]
    for name, col_from, col_to, values in validations:
        requests.append({"setDataValidation": {
            "range": {"sheetId": ids[name], "startRowIndex": 1, "startColumnIndex": col_to,
                      "endColumnIndex": col_to + 1},
            "rule": {"condition": {"type": "ONE_OF_LIST",
                                   "values": [{"userEnteredValue": v} for v in values]},
                     "showCustomUi": True, "strict": False},
        }})
    sheets.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": requests}).execute()

    for email in share_with:
        drive.permissions().create(fileId=sid, sendNotificationEmail=False,
                                   body={"type": "user", "role": "writer", "emailAddress": email}).execute()

    return sid, f"https://docs.google.com/spreadsheets/d/{sid}/edit"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("client", help="имя клиента, как в волте")
    parser.add_argument("--sheet", required=True, help="ID существующей таблицы (из её URL)")
    parser.add_argument("--weeks", type=int, default=26)
    parser.add_argument("--share", action="append", default=[])
    args = parser.parse_args()

    if not KEY.exists():
        print("Нет ключа сервисного аккаунта:", KEY, file=sys.stderr)
        return 1

    sid, url = build_document(args.client, args.weeks, args.share, args.sheet)
    print("Готово:", url)
    if args.share:
        print("Доступ выдан:", ", ".join(args.share))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
