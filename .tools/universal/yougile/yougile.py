#!/usr/bin/env python3
"""
YouGile API v2 клиент (stdlib-only, без pip).

Запускать ЛОКАЛЬНО в Терминале (из песочницы Claude Code сеть до YouGile закрыта).
Python 3.9+ (системный python3 подойдёт).

Ключ берётся из переменной окружения YOUGILE_API_KEY.

Быстрый старт:
  1) python3 yougile.py companies --login MAIL --password PASS
       → покажет companyId
  2) python3 yougile.py make-key --login MAIL --password PASS --company-id ID
       → создаст и покажет API-ключ
  3) export YOUGILE_API_KEY=<ключ>
  4) python3 yougile.py boards                 # список досок с id
  5) python3 yougile.py columns --board-id B   # колонки доски
  6) python3 yougile.py push --file infobiz-tasks.json --board-id B --create-columns

Подробности и формат файла задач → README.md в этой же папке.
"""
import argparse, json, os, sys, urllib.request, urllib.error

BASE = "https://ru.yougile.com/api-v2"


def _req(method, path, body=None, key=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} на {method} {path}\n{e.read().decode()}")
    except urllib.error.URLError as e:
        sys.exit(f"Сеть недоступна до {url}: {e.reason}\n"
                 f"Запускай локально в Терминале, не через Claude Code.")


def _key():
    k = os.environ.get("YOUGILE_API_KEY")
    if not k:
        sys.exit("Нет YOUGILE_API_KEY. Сделай: export YOUGILE_API_KEY=<ключ>")
    return k


def cmd_companies(a):
    res = _req("POST", "/auth/companies", {"login": a.login, "password": a.password})
    items = res.get("content", res) if isinstance(res, dict) else res
    for c in items:
        print(f"{c.get('id')}  {c.get('name')}")


def cmd_make_key(a):
    res = _req("POST", "/auth/keys",
               {"login": a.login, "password": a.password, "companyId": a.company_id})
    print(res.get("key") or json.dumps(res, ensure_ascii=False))


def cmd_boards(a):
    res = _req("GET", "/boards", key=_key())
    for b in res.get("content", []):
        print(f"{b.get('id')}  {b.get('title')}")


def cmd_columns(a):
    res = _req("GET", f"/columns?boardId={a.board_id}", key=_key())
    for c in res.get("content", []):
        print(f"{c.get('id')}  {c.get('title')}")


def _existing_columns(board_id, key):
    res = _req("GET", f"/columns?boardId={board_id}", key=key)
    return {c["title"]: c["id"] for c in res.get("content", [])}


def cmd_push(a):
    key = _key()
    spec = json.load(open(a.file, encoding="utf-8"))
    cols = _existing_columns(a.board_id, key)
    created = 0
    for col in spec["columns"]:
        title = col["title"]
        col_id = cols.get(title)
        if not col_id:
            if not a.create_columns:
                print(f"⚠ колонки нет: «{title}» (запусти с --create-columns) — пропуск")
                continue
            col_id = _req("POST", "/columns",
                          {"title": title, "boardId": a.board_id}, key=key)["id"]
            cols[title] = col_id
            print(f"＋ колонка: {title}")
        for t in col["tasks"]:
            payload = {"title": t["title"], "columnId": col_id}
            if t.get("description"):
                payload["description"] = t["description"]
            if t.get("checklist"):
                payload["checklists"] = [{
                    "title": "Шаги",
                    "items": [{"title": x, "isCompleted": False} for x in t["checklist"]],
                }]
            _req("POST", "/tasks", payload, key=key)
            created += 1
            print(f"  ✓ {t['title']}")
    print(f"\nГотово: {created} задач.")


def main():
    p = argparse.ArgumentParser(description="YouGile API v2 клиент")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("companies"); s.add_argument("--login", required=True); s.add_argument("--password", required=True); s.set_defaults(fn=cmd_companies)
    s = sub.add_parser("make-key"); s.add_argument("--login", required=True); s.add_argument("--password", required=True); s.add_argument("--company-id", required=True); s.set_defaults(fn=cmd_make_key)
    s = sub.add_parser("boards"); s.set_defaults(fn=cmd_boards)
    s = sub.add_parser("columns"); s.add_argument("--board-id", required=True); s.set_defaults(fn=cmd_columns)
    s = sub.add_parser("push"); s.add_argument("--file", required=True); s.add_argument("--board-id", required=True); s.add_argument("--create-columns", action="store_true"); s.set_defaults(fn=cmd_push)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
