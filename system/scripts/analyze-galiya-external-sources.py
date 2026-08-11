#!/usr/bin/env python3
"""
Analyze external Google Sheets from Galiya handover: G2/G3.
"""

from __future__ import annotations

import os
import re
import sys
import warnings
from importlib import import_module

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build


warnings.filterwarnings(
    "ignore",
    message=r"You are using a Python version .*",
    category=FutureWarning,
    module=r"google\.api_core\._python_version_support",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

base = import_module("analyze-detailing-base")

OUT_DIR = os.path.join(ROOT, "projects", "detailing-samara", "analytics")
DATE_TAG = "2026-05-19"

G2_SHEET_ID = "1B_z3HYPFRcJ9XVoiAjSTnMKAMbIW8bh1EEyxZxgugIc"
G3_SHEET_ID = "1y903xdhFmH8LkkgYPBETVTOv3iYLEyWGZwWyGMqcR0U"

G2_REPORT = os.path.join(OUT_DIR, f"awareness-source-galiya-check-{DATE_TAG}.md")
G3_REPORT = os.path.join(OUT_DIR, f"competitor-galiya-shumka-film-2025-08.md")
G3_CSV = os.path.join(OUT_DIR, f"competitor-galiya-shumka-film-2025-08.csv")


def money(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:,.0f}".replace(",", " ")


def num(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.{digits}f}".replace(".", ",")


def get_service():
    creds = service_account.Credentials.from_service_account_file(
        base.SERVICE_ACCOUNT_KEY,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def read_values(svc, spreadsheet_id: str, sheet_name: str, range_a1: str = "A1:Z1000"):
    return (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!{range_a1}")
        .execute()
        .get("values", [])
    )


def extract_prices(text: str) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    value = str(text).lower().replace("\xa0", " ")
    numbers = []
    for match in re.finditer(r"(\d[\d\s]{1,8})(?:\s*[-–]\s*(\d[\d\s]{1,8}))?\s*(?:р|₽|руб)", value):
        first = int(re.sub(r"\D", "", match.group(1)))
        numbers.append(first)
        if match.group(2):
            second = int(re.sub(r"\D", "", match.group(2)))
            if second < 1000 and first >= 1000:
                # "330-340 000" style is rare after regex split; keep conservative.
                second = second * 1000
            numbers.append(second)
    return (min(numbers), max(numbers)) if numbers else (None, None)


def extract_response_minutes(text: str) -> float | None:
    value = str(text or "").lower()
    if not value:
        return None
    if "0" in value and "мин" in value:
        return 0
    minute = re.search(r"(\d+)\s*мин", value)
    if minute:
        return float(minute.group(1))
    days = re.search(r"(\d+)(?:\s*[-–]\s*(\d+))?\s*д", value)
    if days:
        first = float(days.group(1))
        second = float(days.group(2)) if days.group(2) else first
        return ((first + second) / 2) * 24 * 60
    return None


def markdown_table(df: pd.DataFrame, columns, max_rows=30) -> str:
    lines = ["| " + " | ".join(title for _col, title, _kind in columns) + " |"]
    lines.append("|" + "|".join(["---"] * len(columns)) + "|")
    for _, row in df.head(max_rows).iterrows():
        values = []
        for col, _title, kind in columns:
            value = row[col]
            if kind == "money":
                values.append(f"{money(float(value))} ₽" if pd.notna(value) else "")
            elif kind == "num":
                values.append(num(float(value), 1) if pd.notna(value) else "")
            else:
                values.append(str(value).replace("\n", "<br>") if pd.notna(value) else "")
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def analyze_g2(svc) -> None:
    rows = read_values(svc, G2_SHEET_ID, "Опросник", "A1:Z80")
    flattened = "\n".join("\t".join(row) for row in rows).lower()
    source_markers = ["откуда", "узнал", "источник", "реклама", "яндекс", "авито", "vk", "вк", "инст"]
    found = [marker for marker in source_markers if marker in flattened]
    with open(G2_REPORT, "w", encoding="utf-8") as f:
        f.write(
            f"""# Проверка источника G2: «откуда о нас узнали»

Дата проверки: 2026-05-19.

Источник: Google Sheet `{G2_SHEET_ID}`, лист `Опросник`.

## Вывод

В доступной таблице нет отдельного распределения по источникам узнавания о Левше. Таблица является опросником ушедших постоянных клиентов: скрипт звонка, причины ухода, комментарии.

Поиск маркеров источника (`откуда`, `узнал`, `источник`, `реклама`, `Яндекс`, `Авито`, `ВК`, `Инст`) дал: {", ".join(found) if found else "ничего содержательного"}.

## Решение

G2 закрываем как проверенный источник без данных по атрибуции. Для атрибуции первичного контакта нужны другой лист/ссылка или выгрузка из CRM/коллтрекинга.
"""
        )


def analyze_g3(svc) -> None:
    rows = read_values(svc, G3_SHEET_ID, "Лист1", "A1:I1000")
    header = rows[0]
    data = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        padded = row + [""] * (len(header) - len(row))
        item = dict(zip(header, padded))
        full_min, full_max = extract_prices(item.get("Цена оклейка Toyota Camry 80 полная", ""))
        risk_min, risk_max = extract_prices(item.get("Цена оклейка Toyota Camry 80 зоны риска", ""))
        noise_min, noise_max = extract_prices(item.get("Шумоизоляция Toyota Camry 80", ""))
        data.append(
            {
                "competitor": item.get("Детейлинг", "").strip(),
                "response_time": item.get("Время ответа", ""),
                "response_minutes": extract_response_minutes(item.get("Время ответа", "")),
                "politeness": item.get("Вежливость (шкала от 1 до 5)", ""),
                "noise_text": item.get("Шумоизоляция Toyota Camry 80", ""),
                "noise_min": noise_min,
                "noise_max": noise_max,
                "noise_term": item.get("Срок", ""),
                "full_wrap_text": item.get("Цена оклейка Toyota Camry 80 полная", ""),
                "full_wrap_min": full_min,
                "full_wrap_max": full_max,
                "full_wrap_term": item.get("Срок оклейки", ""),
                "risk_zones_text": item.get("Цена оклейка Toyota Camry 80 зоны риска", ""),
                "risk_zones_min": risk_min,
                "risk_zones_max": risk_max,
                "risk_zones_term": item.get("Срок оклейки", ""),
            }
        )
    df = pd.DataFrame(data)
    df.to_csv(G3_CSV, index=False, encoding="utf-8-sig")

    full = df.loc[df["full_wrap_min"].notna()].copy().sort_values("full_wrap_min")
    risk = df.loc[df["risk_zones_min"].notna()].copy().sort_values("risk_zones_min")
    noise = df.loc[df["noise_min"].notna()].copy().sort_values("noise_min")

    levsha = df.loc[df["competitor"].str.lower().eq("левша")]
    levsha_note = ""
    if not levsha.empty:
        row = levsha.iloc[0]
        levsha_note = (
            f"- Левша в таблице: полная оклейка от {money(row['full_wrap_min'])} до {money(row['full_wrap_max'])} ₽, "
            f"зоны риска от {money(row['risk_zones_min'])} до {money(row['risk_zones_max'])} ₽, "
            f"шумоизоляция от {money(row['noise_min'])} до {money(row['noise_max'])} ₽."
        )

    with open(G3_REPORT, "w", encoding="utf-8") as f:
        f.write(
            f"""# Конкурентный анализ Галии: шумка и оклейка зон риска

Дата обработки: 2026-05-19. Источник: Google Sheet `{G3_SHEET_ID}`, лист `Лист1`. Судя по очереди, источник относится к августу 2025.

## Короткий вывод

- В таблице обработано конкурентов: {len(df)}.
- По полной оклейке Toyota Camry 80 есть {len(full)} ценовых наблюдений.
- По зонам риска есть {len(risk)} ценовых наблюдений.
- По шумоизоляции есть {len(noise)} ценовых наблюдений.
{levsha_note}

## Полная оклейка Toyota Camry 80

{markdown_table(full, [
    ("competitor", "Конкурент", "text"),
    ("full_wrap_min", "Мин.", "money"),
    ("full_wrap_max", "Макс.", "money"),
    ("full_wrap_term", "Срок", "text"),
    ("full_wrap_text", "Комментарий", "text"),
], 30)}

## Оклейка зон риска Toyota Camry 80

{markdown_table(risk, [
    ("competitor", "Конкурент", "text"),
    ("risk_zones_min", "Мин.", "money"),
    ("risk_zones_max", "Макс.", "money"),
    ("risk_zones_term", "Срок", "text"),
    ("risk_zones_text", "Комментарий", "text"),
], 30)}

## Шумоизоляция Toyota Camry 80

{markdown_table(noise, [
    ("competitor", "Конкурент", "text"),
    ("noise_min", "Мин.", "money"),
    ("noise_max", "Макс.", "money"),
    ("noise_term", "Срок", "text"),
    ("noise_text", "Комментарий", "text"),
], 30)}

## Практический смысл

Этот источник полезен как исторический срез упаковки и цен по двум услугам. Для текущей таблицы конкурентов его нужно использовать как источник второго уровня: цены могли измениться, но структура офферов, сроки и материалы помогают сравнить, где Левша была дороже/дешевле и чем обосновывать премиум.

CSV с нормализованными полями: `{os.path.basename(G3_CSV)}`.
"""
        )


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    svc = get_service()
    analyze_g2(svc)
    analyze_g3(svc)
    print(f"Report: {G2_REPORT}")
    print(f"Report: {G3_REPORT}")
    print(f"CSV: {G3_CSV}")


if __name__ == "__main__":
    main()
