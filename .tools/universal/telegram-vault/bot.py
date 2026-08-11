#!/usr/bin/env python3
"""Private Telegram gateway to the HyperCRM vault and local Codex CLI."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SAMARA = ZoneInfo("Europe/Samara")
LABEL = "com.hypercrm.telegram-vault"
TELEGRAM_LIMIT = 3900
POLL_TIMEOUT = 40
CODEX_TIMEOUT = 900
VOICE_TRANSCRIBE_TIMEOUT = 1800
DEFAULT_VOICE_MODEL = "/Users/vladimirtarasov/Library/Application Support/com.pais.handy/models/ggml-large-v3-q5_0.bin"
DEFAULT_KEYCHAIN_SERVICE = "com.hypercrm.telegram-vault.bot-token"
DEFAULT_KEYCHAIN_ACCOUNT = "owner"

GATEWAY_PROMPT = """
Ты работаешь через личный Telegram-шлюз владельца HyperCRM.

Обязательные правила:
1. Работай строго в корне HyperCRM и следуй AGENTS.md. Задачи живут в YouGile, vault — база знаний и стратегия.
2. Обычные безопасные чтение, поиск, создание и изменение файлов внутри vault разрешены. Ничего не удаляй и не делай разрушительных действий без явного подтверждения в текущем сообщении.
3. Не отправляй сообщения третьим лицам, не публикуй материалы и не меняй внешние системы без явной команды владельца.
4. Никогда не выводи в Telegram пароли, токены, cookie, ключи, полные реквизиты доступа или содержимое access.md. Можно только сказать, есть ли нужный доступ и где он хранится.
5. Отвечай коротко, по-русски, без markdown-таблиц, до 3500 символов. Если изменил файл — назови путь. Если запрос только на анализ, ничего не меняй.
6. Не создавай daily-логи, todo и backlog в vault. Проектные задачи пользователь сам ведёт в YouGile, если AGENTS.md не задаёт разрешённый автоматический контур.

Сообщение владельца из Telegram:
""".strip()


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default)
    return value if isinstance(value, dict) else dict(default)


def read_keychain_secret(service: str, account: str) -> str:
    process = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-w", "-s", service, "-a", account],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if process.returncode != 0 or not process.stdout.strip():
        raise RuntimeError("Ключ Telegram-бота не найден в macOS Keychain")
    return process.stdout.strip()


def telegram_api(token: str, method: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    url = f"https://api.telegram.org/bot{token}/{method}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Telegram недоступен: {error.reason}") from error
    if not result.get("ok"):
        raise RuntimeError(f"Telegram отклонил {method}: {result}")
    return result.get("result")


def download_telegram_file(token: str, file_id: str, destination: Path) -> None:
    file_info = telegram_api(token, "getFile", {"file_id": file_id}, timeout=30)
    file_path = str((file_info or {}).get("file_path") or "")
    if not file_path:
        raise RuntimeError("Telegram не вернул путь голосового файла")
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    try:
        with urllib.request.urlopen(url, timeout=60) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
        os.chmod(destination, 0o600)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as error:
        raise RuntimeError("Не удалось скачать голосовое из Telegram") from error


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    text = text.strip()
    if not text:
        return ["Готово, но текстового ответа нет."]
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(block) <= limit:
            current = block
        else:
            chunks.extend(block[start : start + limit] for start in range(0, len(block), limit))
            current = ""
    if current:
        chunks.append(current)
    return chunks


def parse_codex_json(output: str) -> tuple[str | None, str | None]:
    thread_id: str | None = None
    messages: list[str] = []
    for raw in output.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            thread_id = str(event.get("thread_id") or "") or None
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        if item.get("type") == "agent_message" and item.get("text"):
            messages.append(str(item["text"]).strip())
    response = messages[-1] if messages else None
    return thread_id, response


class CodexBridge:
    def __init__(self, config: dict[str, Any]) -> None:
        self.root = Path(config["vault_root"]).resolve()
        self.codex = str(config.get("codex_path") or "/Applications/ChatGPT.app/Contents/Resources/codex")
        self.reasoning = str(config.get("reasoning_effort") or "medium")

    def _run(self, user_text: str, session_id: str | None) -> tuple[str, str | None]:
        prompt = f"{GATEWAY_PROMPT}\n\n{user_text.strip()}" if not session_id else (
            "Новое сообщение владельца из Telegram. Следуй исходным правилам шлюза и AGENTS.md.\n\n"
            + user_text.strip()
        )
        common = [
            "--skip-git-repo-check",
            "--json",
            "-c",
            f'model_reasoning_effort="{self.reasoning}"',
        ]
        if session_id:
            command = [self.codex, "exec", "resume", *common, session_id, prompt]
        else:
            command = [
                self.codex,
                "exec",
                *common,
                "-s",
                "workspace-write",
                "-C",
                str(self.root),
                prompt,
            ]
        process = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CODEX_TIMEOUT,
            cwd=self.root,
            env={**os.environ, "NO_COLOR": "1"},
        )
        thread_id, response = parse_codex_json(process.stdout)
        if process.returncode != 0 or not response:
            detail = process.stderr.strip().splitlines()[-1:] or ["нет деталей"]
            raise RuntimeError(f"Codex завершился с кодом {process.returncode}: {detail[0]}")
        return response, thread_id or session_id

    def ask(self, user_text: str, session_id: str | None) -> tuple[str, str | None]:
        try:
            return self._run(user_text, session_id)
        except (RuntimeError, subprocess.TimeoutExpired):
            if not session_id:
                raise
            return self._run(user_text, None)


def load_report_module(vault_root: Path) -> Any:
    path = vault_root / ".tools/universal/reporting/dashboard-telegram.py"
    spec = importlib.util.spec_from_file_location("hypercrm_dashboard_report", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TelegramVaultBot:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config = load_json(config_path, {})
        required = ("owner_user_id", "report_chat_id", "vault_root", "state_path")
        missing = [name for name in required if not self.config.get(name)]
        if missing:
            raise RuntimeError("В конфигурации отсутствуют: " + ", ".join(missing))
        self.token = str(self.config.get("bot_token") or "").strip() or read_keychain_secret(
            str(self.config.get("token_keychain_service") or DEFAULT_KEYCHAIN_SERVICE),
            str(self.config.get("token_keychain_account") or DEFAULT_KEYCHAIN_ACCOUNT),
        )
        self.owner_user_id = int(self.config["owner_user_id"])
        self.state_path = Path(self.config["state_path"])
        self.state = load_json(
            self.state_path,
            {"offset": 0, "sessions": {}, "last_report_date": "", "last_report_attempt": 0},
        )
        self.bridge = CodexBridge(self.config)
        self.report_module = load_report_module(Path(self.config["vault_root"]))
        me = telegram_api(self.token, "getMe")
        self.bot_id = int(me["id"])
        self.bot_username = str(me.get("username") or "")

    def transcribe_voice(self, voice: dict[str, Any]) -> str:
        duration = int(voice.get("duration") or 0)
        file_size = int(voice.get("file_size") or 0)
        max_seconds = int(self.config.get("voice_max_seconds", 1200))
        max_bytes = int(self.config.get("voice_max_bytes", 25 * 1024 * 1024))
        if duration > max_seconds:
            raise RuntimeError(f"Голосовое длиннее допустимых {max_seconds // 60} минут")
        if file_size > max_bytes:
            raise RuntimeError(f"Голосовое больше допустимых {max_bytes // (1024 * 1024)} МБ")

        root = Path(self.config["vault_root"])
        python = str(self.config.get("voice_python") or root / ".tools/venv/bin/python")
        helper = root / ".tools/universal/telegram-vault/transcribe_voice.py"
        model = Path(str(self.config.get("voice_model") or DEFAULT_VOICE_MODEL)).expanduser()
        language = str(self.config.get("voice_language") or "ru")
        if not model.exists():
            raise RuntimeError("Локальная модель Whisper не найдена")

        with tempfile.TemporaryDirectory(prefix="hypercrm-telegram-voice-") as temporary:
            temporary_path = Path(temporary)
            os.chmod(temporary_path, 0o700)
            audio_path = temporary_path / "voice.ogg"
            download_telegram_file(self.token, str(voice["file_id"]), audio_path)
            process = subprocess.run(
                [python, str(helper), str(audio_path), "--model", str(model), "--language", language],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=VOICE_TRANSCRIBE_TIMEOUT,
                cwd=root,
            )
            if process.returncode != 0 or not process.stdout.strip():
                detail = process.stderr.strip().splitlines()[-1:] or ["нет текста"]
                raise RuntimeError(f"Не удалось расшифровать голосовое: {detail[0]}")
            transcript = process.stdout.strip()
        # TemporaryDirectory has already removed the downloaded voice before Codex sees the text.
        return transcript

    def save_state(self) -> None:
        atomic_json_write(self.state_path, self.state)

    def save_config(self) -> None:
        atomic_json_write(self.config_path, self.config)

    def send(self, chat_id: int | str, text: str) -> None:
        for chunk in split_message(text):
            telegram_api(
                self.token,
                "sendMessage",
                {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
            )

    def typing(self, chat_id: int | str) -> None:
        try:
            telegram_api(self.token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except RuntimeError:
            pass

    def should_handle_group_message(self, message: dict[str, Any], text: str) -> bool:
        chat_type = str((message.get("chat") or {}).get("type") or "")
        if chat_type == "private":
            return True
        if text.startswith("/"):
            return True
        mention = f"@{self.bot_username.lower()}" if self.bot_username else ""
        reply_to = message.get("reply_to_message") or {}
        reply_from = reply_to.get("from") or {}
        return (mention and mention in text.lower()) or int(reply_from.get("id") or 0) == self.bot_id

    def strip_mention(self, text: str) -> str:
        if not self.bot_username:
            return text.strip()
        return re.sub(rf"@{re.escape(self.bot_username)}\b", "", text, flags=re.IGNORECASE).strip()

    def help_text(self) -> str:
        return (
            "Я подключён к HyperCRM. Можно писать обычным языком: найти материал, показать статус, "
            "зафиксировать решение или гипотезу, создать/обновить проектный документ.\n\n"
            "/report — сводка из всех живых дашбордов\n"
            "/new — начать новый контекст разговора\n"
            "/status — состояние связки\n"
            "/reporthere — присылать автоотчёт в текущий чат\n"
            "/time 08:30 — время автоотчёта по будням\n"
            "/help — эта справка\n\n"
            "В группе обращайся командой, ответом на моё сообщение или через @упоминание."
        )

    def command(self, message: dict[str, Any], text: str) -> bool:
        chat_id = int((message.get("chat") or {})["id"])
        command, _, argument = text.partition(" ")
        command = command.split("@", 1)[0].lower()
        argument = argument.strip()

        if command in {"/start", "/help"}:
            self.send(chat_id, self.help_text())
            return True
        if command == "/report":
            report = self.report_module.build_report(Path(self.config["vault_root"]))
            self.send(chat_id, report)
            return True
        if command == "/new":
            self.state.setdefault("sessions", {}).pop(str(chat_id), None)
            self.save_state()
            self.send(chat_id, "Контекст сброшен. Следующее сообщение начнёт новый диалог с vault.")
            return True
        if command == "/status":
            count = len(self.report_module.discover_dashboards(Path(self.config["vault_root"])))
            session = "есть" if self.state.get("sessions", {}).get(str(chat_id)) else "нет"
            hour = int(self.config.get("report_hour", 8))
            minute = int(self.config.get("report_minute", 30))
            self.send(
                chat_id,
                f"Связка работает. Дашбордов: {count}. Контекст чата: {session}. "
                f"Автоотчёт: будни {hour:02d}:{minute:02d}, chat_id {self.config['report_chat_id']}.",
            )
            return True
        if command == "/reporthere":
            self.config["report_chat_id"] = chat_id
            self.save_config()
            self.send(chat_id, "Готово. Утренний отчёт будет приходить в этот чат.")
            return True
        if command == "/time":
            match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", argument)
            if not match:
                self.send(chat_id, "Формат: /time 08:30")
                return True
            self.config["report_hour"] = int(match.group(1))
            self.config["report_minute"] = int(match.group(2))
            self.save_config()
            self.send(chat_id, f"Время автоотчёта: будни {int(match.group(1)):02d}:{int(match.group(2)):02d} по Самаре.")
            return True
        return False

    def handle_message(self, message: dict[str, Any]) -> None:
        sender = message.get("from") or {}
        if int(sender.get("id") or 0) != self.owner_user_id:
            return
        text = str(message.get("text") or message.get("caption") or "").strip()
        voice = message.get("voice") or {}
        if voice and not text:
            text = "__VOICE__"
        if not text or not self.should_handle_group_message(message, text):
            return
        text = self.strip_mention(text)
        chat_id = int((message.get("chat") or {})["id"])
        try:
            if voice:
                self.typing(chat_id)
                self.send(chat_id, "🎙 Расшифровываю локально…")
                text = self.transcribe_voice(voice)
                self.send(chat_id, f"🎙 Расшифровка:\n{text}")
            if text.startswith("/") and self.command(message, text):
                return
            self.typing(chat_id)
            session_id = self.state.setdefault("sessions", {}).get(str(chat_id))
            response, new_session_id = self.bridge.ask(text, session_id)
            if new_session_id:
                self.state["sessions"][str(chat_id)] = new_session_id
                self.save_state()
            self.send(chat_id, response)
        except subprocess.TimeoutExpired:
            self.send(chat_id, "Codex не успел ответить за 15 минут. Попробуй повторить запрос короче.")
        except Exception as error:  # daemon boundary: report concise error and continue polling
            print(f"handle_message error: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
            self.send(chat_id, f"Не получилось выполнить запрос: {error}")

    def maybe_send_scheduled_report(self) -> None:
        now = datetime.now(SAMARA)
        weekdays = {int(day) for day in self.config.get("report_weekdays", [0, 1, 2, 3, 4])}
        scheduled = (int(self.config.get("report_hour", 8)), int(self.config.get("report_minute", 30)))
        if now.weekday() not in weekdays or (now.hour, now.minute) < scheduled:
            return
        if self.state.get("last_report_date") == now.date().isoformat():
            return
        last_attempt = float(self.state.get("last_report_attempt") or 0)
        if time.time() - last_attempt < 1800:
            return
        self.state["last_report_attempt"] = time.time()
        self.save_state()
        try:
            report = self.report_module.build_report(Path(self.config["vault_root"]), now=now)
            self.send(self.config["report_chat_id"], report)
            self.state["last_report_date"] = now.date().isoformat()
            self.save_state()
        except Exception as error:
            print(f"scheduled report error: {type(error).__name__}: {error}", file=sys.stderr, flush=True)

    def run(self, once: bool = False) -> None:
        print(f"{LABEL} started as @{self.bot_username}", flush=True)
        while True:
            self.maybe_send_scheduled_report()
            try:
                updates = telegram_api(
                    self.token,
                    "getUpdates",
                    {
                        "offset": int(self.state.get("offset") or 0),
                        "timeout": 0 if once else POLL_TIMEOUT,
                        "allowed_updates": ["message", "edited_message"],
                    },
                    timeout=10 if once else POLL_TIMEOUT + 10,
                )
                for update in updates or []:
                    self.state["offset"] = int(update["update_id"]) + 1
                    self.save_state()
                    message = update.get("message") or update.get("edited_message")
                    if message:
                        self.handle_message(message)
            except Exception as error:
                print(f"poll error: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
                if once:
                    raise
                time.sleep(5)
            if once:
                return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("HYPERCRM_TELEGRAM_CONFIG", "~/Library/Application Support/HyperCRM Telegram Bot/config.json")).expanduser(),
    )
    parser.add_argument("--once", action="store_true", help="один короткий poll для диагностики")
    parser.add_argument("--self-test", action="store_true", help="проверить локальные компоненты без Telegram")
    args = parser.parse_args()

    if args.self_test:
        sample = '\n'.join([
            '{"type":"thread.started","thread_id":"abc"}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"готов"}}',
        ])
        assert parse_codex_json(sample) == ("abc", "готов")
        assert split_message("a" * 5000) == ["a" * 3900, "a" * 1100]
        print("OK: self-test")
        return 0

    try:
        TelegramVaultBot(args.config.expanduser()).run(once=args.once)
        return 0
    except Exception as error:
        print(f"Ошибка запуска: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
