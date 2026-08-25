#!/usr/bin/env python3
"""Рабочая доска волта — локальный сервер, а не снимок.

Отличие от `board.py`: страница не сохраняется в файл, а собирается заново на
каждый запрос. Открыл или обновил — увидел текущее состояние волта. Клик по
задаче переключает чекбокс **прямо в markdown**, поэтому доска и файлы всегда
показывают одно и то же: правишь в Obsidian — видно на доске, отмечаешь на
доске — видно в Obsidian.

Слушает только localhost: в задачах имена клиентов, чеки и выручка, наружу это
не отдаётся.

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/vault/board_server.py
    ... --port 8800      # другой порт
    ... --no-open        # не открывать браузер
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import datetime as dt  # noqa: E402

from board import ROOT, RECUR_MARK, TRACE_MARK, collect, render  # noqa: E402

CHECKBOX_RE = re.compile(r"^(\s*- \[)( |x|X)(\]\s+.+)$")
MAX_BODY = 4096


class ToggleError(Exception):
    """Отказ записи: файл или строка не соответствуют ожиданиям."""


def toggle_task(rel_path: str, line_no: int, trace: str = "") -> bool:
    """Переключает чекбокс на строке и ведёт след закрытия. Возвращает состояние.

    Задача закрывается не отметкой, а следом: при закрытии в строку дописывается
    `↳ что появилось`, при снятии отметки след убирается. Это та же логика, что
    у гипотез волта — закрытую нельзя оставить без результата.

    Проверок намеренно больше, чем кажется нужным: страница пишет в рабочие
    файлы волта, и ошибка здесь стоит дороже, чем неудобство отказа.
    """
    candidate = (ROOT / rel_path).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        raise ToggleError("путь вне волта")
    if candidate.suffix != ".md" or not candidate.is_file():
        raise ToggleError("не markdown-файл волта")

    lines = candidate.read_text(encoding="utf-8").splitlines(keepends=True)
    if not 1 <= line_no <= len(lines):
        raise ToggleError("строки нет — обновите страницу")

    raw = lines[line_no - 1]
    match = CHECKBOX_RE.match(raw.rstrip("\n"))
    if not match:
        raise ToggleError("на этой строке нет чекбокса — файл изменился, обновите страницу")

    done = match.group(2).lower() == "x"
    ending = raw[len(raw.rstrip("\n")):]
    body = match.group(3)

    head, mark, _ = body.partition(TRACE_MARK)
    body = head.rstrip() if mark else body
    if not done:
        clean = " ".join(trace.split()).replace(TRACE_MARK, "")
        if not clean:
            raise ToggleError("нужен след: что появилось в системе")
        body = f"{body} {TRACE_MARK} {clean}"

    lines[line_no - 1] = match.group(1) + (" " if done else "x") + body + ending
    candidate.write_text("".join(lines), encoding="utf-8")
    return not done


def touch_routine(rel_path: str, line_no: int) -> str:
    """Ставит сегодняшнюю дату регулярному ритму. Возвращает новую дату.

    Регулярное не закрывается галочкой — у него меняется дата последнего раза,
    и со следующего периода оно снова становится актуальным.
    """
    candidate = (ROOT / rel_path).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        raise ToggleError("путь вне волта")
    if candidate.suffix != ".md" or not candidate.is_file():
        raise ToggleError("не markdown-файл волта")

    lines = candidate.read_text(encoding="utf-8").splitlines(keepends=True)
    if not 1 <= line_no <= len(lines):
        raise ToggleError("строки нет — обновите страницу")

    raw = lines[line_no - 1]
    if RECUR_MARK not in raw:
        raise ToggleError("на этой строке нет регулярного ритма — обновите страницу")

    today = dt.date.today().isoformat()
    head, mark, tail = raw.rstrip("\n").rpartition(RECUR_MARK)
    if not re.fullmatch(r"\s*20\d{2}-\d{2}-\d{2}\s*", tail):
        raise ToggleError("после знака ритма нет даты")
    ending = raw[len(raw.rstrip("\n")):]
    lines[line_no - 1] = f"{head}{mark} {today}{ending}"
    candidate.write_text("".join(lines), encoding="utf-8")
    return today


class Handler(BaseHTTPRequestHandler):
    server_version = "VaultBoard/1.0"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/", "/index.html"):
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        projects, upcoming = collect()
        page = render(projects, upcoming, interactive=True)
        self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/toggle", "/touch"):
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._reply({"ok": False, "error": "плохой запрос"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            path, line = str(payload["file"]), int(payload["line"])
            if self.path == "/touch":
                result = {"ok": True, "last": touch_routine(path, line)}
            else:
                trace = str(payload.get("trace") or "")
                done = toggle_task(path, line, trace)
                result = {"ok": True, "done": done,
                          "trace": " ".join(trace.split()) if done else ""}
        except ToggleError as error:
            self._reply({"ok": False, "error": str(error)})
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            self._reply({"ok": False, "error": "плохой запрос"})
        except OSError as error:
            self._reply({"ok": False, "error": f"не записалось: {error}"})
        else:
            self._reply(result)

    def _reply(self, data: dict) -> None:
        self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:
        if self.command == "POST":
            print("отметка:", fmt % args)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Доска волта: {url}\nОстановить — Ctrl+C")
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
