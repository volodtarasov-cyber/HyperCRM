#!/usr/bin/env python3
"""Установка понедельничного дайджеста в Telegram.

Три шага: токен → chat_id → задача в Планировщике Windows.

Токен вводится скрытым полем и никогда не печатается: ни в консоль, ни в
сообщения об ошибках. Лежит он вне волта — волт в git и синхронизируется.

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/vault/telegram-setup.py
    ... --task-only     # переставить только задачу, токен не трогать
    ... --send-test     # отправить пробный дайджест после установки
"""

from __future__ import annotations

import getpass
import json
import locale
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board import ROOT  # noqa: E402

DIGEST = ROOT / ".tools" / "universal" / "vault" / "weekly-digest.py"
PYTHON = ROOT / ".tools" / "venv" / "Scripts" / "python.exe"
TASK_NAME = "HyperCRM - понедельничный прогон"  # двоеточие Планировщик не принимает


def config_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".config")
    return Path(base) / "HyperCRM" / "telegram.json"


def api(token: str, method: str, **params) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        # В URL зашит токен — печатаем только код, не сам запрос.
        raise SystemExit(f"Telegram ответил {error.code}. Проверь токен.") from None
    except urllib.error.URLError as error:
        raise SystemExit(f"Нет связи с Telegram: {error.reason}") from None


def ask_token() -> str:
    print("Токен бота от @BotFather. Ввод скрытый, в консоли не появится.")
    token = getpass.getpass("Токен: ").strip()
    if not token:
        raise SystemExit("Пусто — прервал.")
    answer = api(token, "getMe")
    if not answer.get("ok"):
        raise SystemExit("Токен не принят Telegram.")
    print(f"Бот найден: @{answer['result'].get('username')}")
    return token


def ask_chat_id(token: str) -> int:
    print(f"\nОткрой бота в Telegram и отправь ему любое сообщение — например /start.")
    input("Отправил? Нажми Enter... ")
    answer = api(token, "getUpdates", timeout=0)
    updates = answer.get("result", [])
    chats = {}
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        if chat.get("id"):
            title = chat.get("username") or chat.get("title") or chat.get("first_name") or "—"
            chats[chat["id"]] = title
    if not chats:
        raise SystemExit(
            "Сообщений не видно. Так бывает, если бот уже опрашивается другим процессом\n"
            "или сообщение отправлено больше суток назад. Напиши боту ещё раз и повтори."
        )
    if len(chats) == 1:
        chat_id, title = next(iter(chats.items()))
        print(f"Чат найден: {title} ({chat_id})")
        return chat_id
    print("Найдено несколько чатов:")
    for index, (chat_id, title) in enumerate(chats.items(), 1):
        print(f"  {index}. {title} ({chat_id})")
    choice = input("Какой использовать? Номер: ").strip()
    return list(chats)[int(choice) - 1]


def save(token: str, chat_id: int) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"bot_token": token, "chat_id": chat_id}, indent=1), encoding="utf-8")
    return path


def install_task() -> None:
    """Понедельник 09:00. Пропуск не теряется — задача догоняет при включении.

    Планировщик не умеет ставить «догонять» через schtasks /Create, поэтому
    флаг StartWhenAvailable дописывается правкой XML уже созданной задачи.
    """
    # Задача запускает не python напрямую, а обёртку. Две причины:
    # у задачи Планировщика нет рабочей папки (cwd оказывается System32), и у неё
    # некуда писать ошибку — при сбое остаётся только код возврата без текста.
    # Обёртка задаёт папку и кладёт весь вывод в лог рядом с конфигом.
    wrapper = config_path().parent / "run-digest.cmd"
    log = config_path().parent / "digest.log"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    # Отметки времени пишет сам питон, а не `echo`: иначе в логе смешиваются две
    # кодировки — OEM от cmd и питоновская, — и читать его нечем.
    wrapper.write_text(
        "@echo off\r\n"
        "set PYTHONIOENCODING=utf-8\r\n"
        f'cd /d "{ROOT}"\r\n'
        f'"{PYTHON}" "{DIGEST}" --log >> "{log}" 2>&1\r\n',
        encoding="cp866",
    )
    subprocess.run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/TR", f'"{wrapper}"',
         "/SC", "WEEKLY", "/D", "MON", "/ST", "09:00", "/F"],
        check=True,
    )
    # StartWhenAvailable: если в понедельник машина была выключена, задача
    # отработает при первом включении, а не потеряется до следующей недели.
    # Через /Create такой флаг не выставить — только правкой XML готовой задачи.
    #
    # Кодировку не угадываем: schtasks отдаёт XML в кодировке консоли, а она
    # на русской Windows не UTF-8 — из-за кириллицы в имени задачи utf-8 падает.
    # Читаем байтами и перебираем кандидатов, включая кодовую страницу OEM.
    raw = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/XML"],
                         capture_output=True, check=True).stdout
    xml = ""
    candidates = ["utf-8-sig", "utf-8", "utf-16", "cp866", "cp1251",
                  locale.getpreferredencoding(False)]
    for encoding in candidates:
        try:
            candidate = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "<Task" in candidate:
            xml = candidate
            break
    if not xml:
        print("Задача создана, но XML прочитать не вышло — флаг «догонять пропуск» "
              "поставь руками: Планировщик → задача → Условия.")
    elif "<StartWhenAvailable>true</StartWhenAvailable>" not in xml:
        xml = xml.replace("<Settings>", "<Settings>\n    <StartWhenAvailable>true</StartWhenAvailable>", 1)
        tmp = Path(os.environ.get("TEMP", ".")) / "hypercrm-task.xml"
        tmp.write_text(xml, encoding="utf-16")
        subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(tmp), "/F"], check=True)
        tmp.unlink(missing_ok=True)
    print(f"Задача поставлена: «{TASK_NAME}» — понедельник 09:00, догоняет пропуск.")


def main() -> int:
    if "--task-only" not in sys.argv:
        token = ask_token()
        chat_id = ask_chat_id(token)
        path = save(token, chat_id)
        print(f"Конфиг сохранён: {path}")
    install_task()
    if "--send-test" in sys.argv:
        subprocess.run([str(PYTHON), str(DIGEST)], check=False)
    print("\nПроверить руками:")
    print(f'    "{PYTHON}" "{DIGEST}" --print   # текст без отправки')
    print(f'    "{PYTHON}" "{DIGEST}"           # отправить сейчас')
    print(f'    schtasks /Run /TN "{TASK_NAME}"  # прогнать задачу целиком')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
