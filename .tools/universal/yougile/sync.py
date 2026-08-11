#!/usr/bin/env python3
"""
Демон-синхронизатор очереди → YouGile.

Идея: ассистент дописывает задачи в queue.jsonl (по одной задаче на строку).
Этот скрипт читает очередь, создаёт в YouGile только НОВЫЕ задачи (по id),
помечает сделанные в state.json. Идемпотентно — повторный запуск не дублирует.

Запускается автоматически launchd-агентом (com.hypercrm.yougile-sync.plist):
по изменению queue.jsonl + раз в 5 минут на всякий.

Env:
  YOUGILE_API_KEY   — обязателен
  YOUGILE_BOARD_ID  — доска по умолчанию (если в строке очереди нет board_id)

Формат строки queue.jsonl:
  {"id":"uuid","column":"🔥 Сейчас","title":"...","description":"...","checklist":["шаг1"]}
  (board_id опционально; description/checklist опциональны)
"""
import json, os, sys
from pathlib import Path
from yougile import _req  # тот же каталог

HERE = Path(__file__).parent
QUEUE = HERE / "queue.jsonl"
STATE = HERE / "state.json"
LOG = HERE / "pushed.log"
BOARDS = HERE / "boards.json"


def load_boards():
    """Карта 'проект' → id доски. Плейсхолдеры ВСТАВЬ_* игнорируем."""
    if not BOARDS.exists():
        return {}
    raw = json.loads(BOARDS.read_text(encoding="utf-8"))
    return {k.lower(): v for k, v in raw.items()
            if not k.startswith("_") and not str(v).startswith("ВСТАВЬ")}


def resolve_board(task, boards_map, default_board):
    """Порядок: явный board_id → по имени проекта → default из карты → env."""
    if task.get("board_id"):
        return task["board_id"]
    proj = str(task.get("project", "")).lower()
    if proj and proj in boards_map:
        return boards_map[proj]
    return boards_map.get("default") or default_board


def log(msg):
    ts = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    line = f"{ts}  {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"done": [], "columns": {}}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2))


def column_id(board_id, title, key, st):
    cache = st["columns"].setdefault(board_id, {})
    if title in cache:
        return cache[title]
    res = _req("GET", f"/columns?boardId={board_id}", key=key)
    for c in res.get("content", []):
        cache[c["title"]] = c["id"]
    if title not in cache:
        cid = _req("POST", "/columns", {"title": title, "boardId": board_id}, key=key)["id"]
        cache[title] = cid
        log(f"＋ колонка: {title}")
    return cache[title]


def main():
    key = os.environ.get("YOUGILE_API_KEY")
    if not key:
        sys.exit("Нет YOUGILE_API_KEY")
    default_board = os.environ.get("YOUGILE_BOARD_ID", "")
    boards_map = load_boards()
    if not QUEUE.exists():
        return
    st = load_state()
    done = set(st["done"])
    created = 0
    for raw in QUEUE.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            t = json.loads(raw)
        except json.JSONDecodeError:
            log(f"⚠ битая строка пропущена: {raw[:80]}")
            continue
        tid = t.get("id")
        if not tid or tid in done:
            continue
        board = resolve_board(t, boards_map, default_board)
        if not board:
            log(f"⚠ доска не определена (project={t.get('project')!r}) — пропуск: {t.get('title')}")
            continue
        try:
            cid = column_id(board, t.get("column", "Входящие"), key, st)
            payload = {"title": t["title"], "columnId": cid}
            if t.get("description"):
                payload["description"] = t["description"]
            if t.get("checklist"):
                payload["checklists"] = [{
                    "title": "Шаги",
                    "items": [{"title": x, "isCompleted": False} for x in t["checklist"]],
                }]
            _req("POST", "/tasks", payload, key=key)
            done.add(tid)
            st["done"] = list(done)
            save_state(st)  # сохраняем после каждой — при сбое не задвоит
            created += 1
            log(f"✓ {t['title']}")
        except SystemExit as e:
            log(f"✗ ошибка на «{t.get('title')}»: {e}")
            break  # сеть/ключ — нет смысла продолжать
    if created:
        log(f"— залито: {created}")


if __name__ == "__main__":
    main()
