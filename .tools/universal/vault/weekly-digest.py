#!/usr/bin/env python3
"""Понедельничный дайджест волта в Telegram.

Не отчёт вместо прогона, а повод сесть за прогон: короткий срез, по которому
видно, стоит ли открывать волт прямо сейчас. Сам разбор остаётся диалогом.

Почему не облачная рутина: облачный агент не видит локальные файлы, а у волта
нет git-remote. Почему не старый telegram-vault: он macOS-овый — Keychain,
launchd, пути `~/Library`. Здесь нужен один маленький кусок — отправка.

**Снимок прогона не трогается.** `review.py` сравнивает состояние со снимком и
переписывает его; если бы дайджест делал то же, он съедал бы разницу, и к
живому прогону «изменилось с прошлого раза» оказывалось бы пустым. Поэтому
данные читаются напрямую из board.py, а `review-state.json` остаётся нетронутым.

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/vault/weekly-digest.py
    ... --print   # показать текст, ничего не отправляя
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board import ROOT, collect, collect_external  # noqa: E402

QUALITY_CHECK = ROOT / ".tools" / "universal" / "vault" / "quality-check.py"
TELEGRAM_LIMIT = 4096
WEEKDAYS = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")


def config_path() -> Path:
    """Секрет живёт вне волта: волт синхронизируется и лежит в git."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".config")
    return Path(base) / "HyperCRM" / "telegram.json"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        raise SystemExit(
            f"Нет конфига: {path}\n"
            "Заведи его установщиком:\n"
            "    .tools/venv/Scripts/python.exe .tools/universal/vault/telegram-setup.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def quality_summary() -> tuple[int, int, dict[str, int]]:
    """Ошибки, предупреждения и разбивка по кодам. --strict, чтобы видеть долг разметки.

    Читаем байтами и декодируем сами. Под Планировщиком консоли нет, кодовая
    страница OEM, и `text=True, encoding="utf-8"` роняет поток чтения на первом
    же кириллическом байте в stderr — stdout при этом приходит пустым, а ошибка
    выглядит так, будто сломался JSON. PYTHONIOENCODING делает вывод ребёнка
    предсказуемым независимо от того, кто его запустил.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, str(QUALITY_CHECK), "--strict", "--json"],
        capture_output=True, env=env,
    )
    try:
        data = json.loads((result.stdout or b"").decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return -1, -1, {}
    by_code: dict[str, int] = {}
    for issue in data.get("issues", []):
        by_code[issue["code"]] = by_code.get(issue["code"], 0) + 1
    summary = data.get("summary", {})
    return summary.get("errors", 0), summary.get("warnings", 0), by_code


def build_message(today: dt.date) -> str:
    projects, upcoming = collect()
    external = collect_external()
    errors, warnings, by_code = quality_summary()

    lines = [f"🗓 <b>Прогон волта</b> — {WEEKDAYS[today.weekday()]}, {today.strftime('%d.%m')}", ""]

    open_tasks = sum(len(p.open_tasks) for p in projects.values())
    lines.append(f"Открытых задач: <b>{open_tasks}</b>")

    if errors < 0:
        lines.append("⚠️ Проверка не отработала — запусти quality-check руками")
    elif errors:
        lines.append(f"❌ Ошибок в волте: <b>{errors}</b> — чинить до разбора")
    else:
        stale = sum(by_code.get(code, 0) for code in ("STALE_CHECKED", "STALE_WRITTEN", "EXPIRED"))
        debt = by_code.get("NO_CHECK_MARK", 0)
        tail = f", долг разметки {debt}" if debt else ""
        lines.append(f"Ошибок нет · протухло по сроку годности: <b>{stale}</b>{tail}")

    never = [item for item in external if item.age is None]
    old = [item for item in external if item.age is not None and item.age >= 14]
    if never or old:
        lines += ["", "🌍 <b>Снаружи — спросить и свести</b>"]
        for item in (never + old)[:6]:
            mark = "ни разу" if item.age is None else f"{item.age} дн."
            lines.append(f"• {item.text.split(':')[0]} — <i>{mark}</i>")
        if len(never + old) > 6:
            lines.append(f"  … ещё {len(never + old) - 6}")

    attention = [f"{p.title}: {item}" for p in projects.values() for item in p.attention]
    if attention:
        lines += ["", "⚠️ <b>Требует внимания</b>"]
        lines += [f"• {item}" for item in attention[:5]]
        if len(attention) > 5:
            lines.append(f"  … ещё {len(attention) - 5}")

    if upcoming:
        lines += ["", "📌 <b>Чекпоинты рядом</b>"]
        lines += [f"• {item}" for item in upcoming[:5]]

    lines += ["", "<i>Дальше — прогон в диалоге: review.py + quality-check.py --strict</i>"]

    text = "\n".join(lines)
    if len(text) > TELEGRAM_LIMIT:
        text = text[: TELEGRAM_LIMIT - 20].rsplit("\n", 1)[0] + "\n…"
    return text


def send(config: dict, text: str) -> None:
    payload = urllib.parse.urlencode({
        "chat_id": config["chat_id"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=payload), timeout=30) as response:
            answer = json.loads(response.read())
    except urllib.error.URLError as error:
        raise SystemExit(f"Не отправилось: {error}") from error
    if not answer.get("ok"):
        # Токен в текст ошибки не попадает: печатаем только описание от Telegram.
        raise SystemExit(f"Telegram отказал: {answer.get('description')}")


def main() -> int:
    # --log: запуск из Планировщика. Отметка времени и исход пишутся сюда же,
    # чтобы в понедельник было видно, отработало или упало, и на чём именно.
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M") if "--log" in sys.argv else None
    try:
        text = build_message(dt.date.today())
        if "--print" in sys.argv:
            print(text)
            return 0
        send(load_config(), text)
    except SystemExit as error:
        if stamp:
            print(f"[{stamp}] не отправлено: {error}")
            return 1
        raise
    print(f"[{stamp}] отправлено" if stamp else "Отправлено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
