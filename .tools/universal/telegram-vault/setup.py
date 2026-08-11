#!/usr/bin/env python3
"""One-time secure setup for the HyperCRM Telegram vault bot."""

from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import os
import plistlib
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SAMARA = ZoneInfo("Europe/Samara")
LABEL = "com.hypercrm.telegram-vault"
KEYCHAIN_SERVICE = "com.hypercrm.telegram-vault.bot-token"
KEYCHAIN_ACCOUNT = "owner"
APP_DIR = Path.home() / "Library/Application Support/HyperCRM Telegram Bot"
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"
PLIST_PATH = Path.home() / f"Library/LaunchAgents/{LABEL}.plist"


def load_bot_helpers(bot_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("hypercrm_telegram_vault_bot", bot_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить {bot_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def store_keychain_secret(token: str) -> None:
    result = subprocess.run(
        [
            "/usr/bin/security",
            "add-generic-password",
            "-U",
            "-a",
            KEYCHAIN_ACCOUNT,
            "-s",
            KEYCHAIN_SERVICE,
            "-w",
            token,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "не удалось сохранить ключ в macOS Keychain")


def choose_owner(helpers: Any, token: str) -> tuple[int, int, int, str]:
    existing = helpers.telegram_api(token, "getUpdates", {"timeout": 0, "allowed_updates": ["message"]}, timeout=15) or []
    candidates = []
    for update in existing:
        message = update.get("message") or {}
        sender = message.get("from") or {}
        chat = message.get("chat") or {}
        if sender.get("id") and chat.get("id") and chat.get("type") == "private":
            candidates.append((int(update["update_id"]), int(sender["id"]), int(chat["id"]), str(sender.get("first_name") or "")))
    if candidates:
        return candidates[-1]

    print("Отправь созданному боту в Telegram сообщение /start. Жду до 3 минут…", flush=True)
    offset = 0
    deadline = time.time() + 180
    while time.time() < deadline:
        updates = helpers.telegram_api(
            token,
            "getUpdates",
            {"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
            timeout=40,
        ) or []
        for update in updates:
            offset = int(update["update_id"]) + 1
            message = update.get("message") or {}
            sender = message.get("from") or {}
            chat = message.get("chat") or {}
            if sender.get("id") and chat.get("id") and chat.get("type") == "private":
                return int(update["update_id"]), int(sender["id"]), int(chat["id"]), str(sender.get("first_name") or "")
    raise RuntimeError("Не дождался сообщения боту")


def launchd_payload(python: Path, bot_path: Path) -> dict[str, Any]:
    return {
        "Label": LABEL,
        "ProgramArguments": [str(python), str(bot_path), "--config", str(CONFIG_PATH)],
        "WorkingDirectory": str(bot_path.parents[3]),
        "EnvironmentVariables": {
            "HYPERCRM_TELEGRAM_CONFIG": str(CONFIG_PATH),
            "PYTHONUNBUFFERED": "1",
            "PATH": "/Applications/ChatGPT.app/Contents/Resources:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(APP_DIR / "bot.out.log"),
        "StandardErrorPath": str(APP_DIR / "bot.err.log"),
        "ProcessType": "Background",
    }


def install_launchd(plist_path: Path) -> None:
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(plist_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "launchctl bootstrap завершился с ошибкой")
    subprocess.run(["launchctl", "kickstart", "-k", f"{domain}/{LABEL}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--hour", type=int, default=8)
    parser.add_argument("--minute", type=int, default=30)
    parser.add_argument("--no-start", action="store_true", help="создать конфиг и plist, но не запускать launchd")
    parser.add_argument("--token-stdin", action="store_true", help="прочитать токен из stdin, не показывая его")
    parser.add_argument("--yes", action="store_true", help="подтвердить найденного владельца без prompt")
    parser.add_argument("--use-keychain", action="store_true", help="взять ранее сохранённый токен из macOS Keychain")
    parser.add_argument("--store-token-only", action="store_true", help="проверить и сохранить токен в Keychain без привязки Telegram ID")
    args = parser.parse_args()

    root = args.vault_root.resolve()
    bot_path = Path(__file__).with_name("bot.py").resolve()
    helpers = load_bot_helpers(bot_path)
    if args.use_keychain:
        token = helpers.read_keychain_secret(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    else:
        token = (sys.stdin.readline() if args.token_stdin else getpass.getpass("Токен от @BotFather (не отображается): ")).strip()
    if not token:
        print("Токен не указан", file=sys.stderr)
        return 1

    try:
        helpers.telegram_api(token, "deleteWebhook", {"drop_pending_updates": False}, timeout=15)
        me = helpers.telegram_api(token, "getMe", timeout=15)
        print(f"Бот найден: @{me.get('username')} ({me.get('first_name')})")
        store_keychain_secret(token)
        print("Ключ сохранён в macOS Keychain.")
        if args.store_token_only:
            return 0
        update_id, owner_id, chat_id, owner_name = choose_owner(helpers, token)
        answer = "y" if args.yes else input(
            f"Разрешить доступ пользователю {owner_name or owner_id} (user_id={owner_id})? [Y/n] "
        ).strip().lower()
        if answer not in {"", "y", "yes", "д", "да"}:
            print("Отменено")
            return 1

        APP_DIR.mkdir(parents=True, exist_ok=True)
        config = {
            "token_keychain_service": KEYCHAIN_SERVICE,
            "token_keychain_account": KEYCHAIN_ACCOUNT,
            "owner_user_id": owner_id,
            "report_chat_id": chat_id,
            "vault_root": str(root),
            "state_path": str(STATE_PATH),
            "codex_path": "/Applications/ChatGPT.app/Contents/Resources/codex",
            "reasoning_effort": "medium",
            "voice_python": str(root / ".tools/venv/bin/python"),
            "voice_model": "/Users/vladimirtarasov/Library/Application Support/com.pais.handy/models/ggml-large-v3-q5_0.bin",
            "voice_language": "ru",
            "voice_max_seconds": 1200,
            "voice_max_bytes": 26214400,
            "report_hour": args.hour,
            "report_minute": args.minute,
            "report_weekdays": [0, 1, 2, 3, 4],
        }
        helpers.atomic_json_write(CONFIG_PATH, config)
        now = datetime.now(SAMARA)
        already_past = (now.hour, now.minute) >= (args.hour, args.minute) and now.weekday() < 5
        state = {
            "offset": update_id + 1,
            "sessions": {},
            "last_report_date": now.date().isoformat() if already_past else "",
            "last_report_attempt": 0,
        }
        helpers.atomic_json_write(STATE_PATH, state)

        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PLIST_PATH.open("wb") as stream:
            plistlib.dump(launchd_payload(Path(sys.executable).resolve(), bot_path), stream)
        os.chmod(PLIST_PATH, 0o600)

        if not args.no_start:
            install_launchd(PLIST_PATH)
            helpers.telegram_api(
                token,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": (
                        "Связка с HyperCRM готова. Пиши обычным языком или используй /help. "
                        f"Утренний отчёт: будни {args.hour:02d}:{args.minute:02d} по Самаре."
                    ),
                },
            )
            print("Готово: бот запущен и добавлен в автозапуск.")
        else:
            print("Готово: конфигурация создана, launchd не запускался.")
        print(f"Конфигурация: {CONFIG_PATH}")
        print(f"Логи: {APP_DIR / 'bot.err.log'}")
        return 0
    except Exception as error:
        print(f"Ошибка настройки: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
