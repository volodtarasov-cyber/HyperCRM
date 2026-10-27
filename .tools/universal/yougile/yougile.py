"""YouGile REST API v2 — задачи из волта по проектам.

Правило (CLAUDE.md → «Tasks in YouGile»): ассистент ничего не создаёт и не меняет
без явного «да» Володи на конкретный список. Скрипт сам ничего не решает —
он только выполняет команду.

    .tools/venv/Scripts/python.exe .tools/universal/yougile/yougile.py setup
        один раз: логин и пароль вводятся в окне (в чат не попадают), выбирается
        компания, ключ сохраняется в .tools/local/yougile/key.env (вне git)
    ... yougile.py tree                      проекты → доски → колонки
    ... yougile.py users                     сотрудники компании
    ... yougile.py tasks --where "Arcars/Задачи/В работе" [--limit 20]
    ... yougile.py create --where "Arcars/Задачи/Новые" --title "..." \
            [--description "..."] [--deadline 2026-11-05] [--assign "Имя или email"]
    ... yougile.py push --file batch.json [--dry-run]
        несколько задач разом — тот список, на который Володя сказал «да»:
        [{"where": "проект/доска/колонка", "title": "...", "description": "...",
          "deadline": "ГГГГ-ММ-ДД", "assign": "Имя",
          "claude": "что сделает ассистент", "when": "когда закинуть", "chat": "id сессии"}]
        Сначала проверяет все адреса, потом создаёт: опечатка в одном пункте
        не оставит половину списка созданной.
    ... yougile.py show --code VED-27         задача по коду: где лежит, срок, описание
    ... yougile.py mark --code VED-27 --claude "..." [--when "..."] [--chat ID]
        дописывает в описание пометку «🤖 Claude»: что делает ассистент, когда
        закинуть задачу ему и в каком чате она живёт. Больше ничего не меняет.
    ... yougile.py done --code FIN-157        отметить выполненной (после «да» Володи)
    ... yougile.py files --code VED-28 --path clients/arcars/reports/drafts-2026-10-27
        дописывает кликабельную ссылку на папку в GitHub.
        В push — поле "files": "путь в волте".

--where — «проект/доска/колонка» по названиям, без учёта регистра; хватает
начала названия, если оно однозначно. Колонки по умолчанию нет: задача всегда
идёт в колонку своего проекта.

Ограничение API — не больше 50 запросов в минуту на компанию.
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://yougile.com/api-v2"
VAULT = Path(__file__).resolve().parents[3]
KEY_FILE = VAULT / ".tools" / "local" / "yougile" / "key.env"

sys.stdout.reconfigure(encoding="utf-8")


def call(method: str, path: str, body: dict | None = None, key: str | None = None, query: str = "") -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{API}{path}{query}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:          # 50 запросов в минуту на компанию
                time.sleep(15)
                continue
            raise SystemExit(f"✗ YouGile {e.code} на {method} {path}: {e.read().decode('utf-8', 'replace')[:300]}")
    raise SystemExit("✗ YouGile: слишком много запросов, повтори через минуту")


def load_key() -> str:
    if not KEY_FILE.exists():
        raise SystemExit("✗ Ключа нет. Один раз запусти: yougile.py setup")
    for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("YOUGILE_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"✗ В {KEY_FILE} нет строки YOUGILE_KEY=")


def content(key: str, path: str, query: str = "") -> list[dict]:
    out, offset = [], 0
    while True:
        sep = "&" if query else ""
        page = call("GET", path, key=key, query=f"?limit=1000&offset={offset}{sep}{query}")
        items = page.get("content", [])
        out += [i for i in items if not i.get("deleted")]
        if not page.get("paging", {}).get("next"):
            return out
        offset += len(items)


# ── команды ──────────────────────────────────────────────────────────

def cmd_setup(_: argparse.Namespace) -> None:
    login = input("Логин YouGile (email): ").strip()
    password = getpass.getpass("Пароль (не отображается): ")
    companies = call("POST", "/auth/companies", {"login": login, "password": password}).get("content", [])
    if not companies:
        raise SystemExit("✗ Компаний не найдено — проверь логин и пароль")
    for i, c in enumerate(companies, 1):
        print(f"  {i}. {c.get('name')}")
    pick = companies[int(input("Номер компании: ").strip() or "1") - 1]
    key = call("POST", "/auth/keys", {"login": login, "password": password, "companyId": pick["id"]})["key"]
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(f"# YouGile API, компания «{pick.get('name')}», создан {dt.date.today()}\nYOUGILE_KEY={key}\n",
                        encoding="utf-8")
    print(f"✓ Ключ для «{pick.get('name')}» сохранён в {KEY_FILE.relative_to(VAULT)} (вне git). Пароль нигде не сохранён.")


def tree(key: str) -> list[dict]:
    projects = content(key, "/projects")
    boards = content(key, "/boards")
    columns = content(key, "/columns")
    for p in projects:
        p["boards"] = [b for b in boards if b.get("projectId") == p["id"]]
        for b in p["boards"]:
            b["columns"] = [c for c in columns if c.get("boardId") == b["id"]]
    return projects


def cmd_tree(_: argparse.Namespace) -> None:
    for p in tree(load_key()):
        print(p["title"])
        for b in p["boards"]:
            print(f"  {b['title']}")
            for c in b["columns"]:
                print(f"    · {c['title']}")


def pick(items: list[dict], name: str, what: str) -> dict:
    n = name.strip().lower()
    exact = [i for i in items if i["title"].strip().lower() == n]
    starts = exact or [i for i in items if i["title"].strip().lower().startswith(n)]
    if len(starts) == 1:
        return starts[0]
    variants = ", ".join(f"«{i['title']}»" for i in (starts or items)[:12])
    raise SystemExit(f"✗ {what} «{name}»: {'неоднозначно' if starts else 'не найден(а)'}. Есть: {variants}")


def resolve(key: str, where: str) -> tuple[dict, dict, dict]:
    parts = [x for x in where.split("/") if x.strip()]
    if len(parts) != 3:
        raise SystemExit("✗ --where нужен в виде «проект/доска/колонка»")
    p = pick(tree(key), parts[0], "Проект")
    b = pick(p["boards"], parts[1], "Доска")
    c = pick(b["columns"], parts[2], "Колонка")
    return p, b, c


def cmd_users(_: argparse.Namespace) -> None:
    for u in content(load_key(), "/users"):
        print(f"{u.get('realName') or '—'} · {u.get('email')}")


def cmd_tasks(a: argparse.Namespace) -> None:
    key = load_key()
    p, b, c = resolve(key, a.where)
    items = content(key, "/tasks", f"columnId={c['id']}")[: a.limit]
    print(f"{p['title']} / {b['title']} / {c['title']} — задач: {len(items)}")
    for t in items:
        print(f"  {t.get('idTaskProject') or t.get('idTaskCommon') or ''} {t['title']}{' ✓' if t.get('completed') else ''}")


def claude_block(what: str, when: str | None = None, chat: str | None = None) -> str:
    """Пометка для задач, которые надо закинуть ассистенту. Код задачи достаточно
    назвать в любом чате волта — `show` прочитает её отсюда; сессия — для возврата в тот же разговор."""
    lines = [f"🤖 Claude: {what}"]
    if when:
        lines.append(f"Закинуть: {when}")
    if chat:
        lines.append(f"Чат: Claude Code, папка HyperCRM, сессия {chat} (claude --resume {chat})")
    else:
        lines.append("Чат: любой новый в HyperCRM — назови код задачи")
    return "<br>".join(lines)


GITHUB = "https://github.com/volodtarasov-cyber/HyperCRM/tree/master"


def files_block(rel: str) -> str:
    """Кликабельная ссылка на файлы волта в GitHub (открывается и с телефона).
    Ссылки file:// и vscode:// YouGile вырезает из описания — проверено 2026-10-27."""
    rel = rel.strip().strip("/").replace("\\", "/")
    return f'📁 Файлы: <a href="{GITHUB}/{urllib.parse.quote(rel)}">{rel}</a>'


def prepare(key: str, task: dict, projects: list[dict], users: list[dict] | None) -> tuple[dict, str]:
    """Тело запроса и подпись «проект / доска / колонка». Падает до любой записи."""
    parts = [x for x in str(task.get("where", "")).split("/") if x.strip()]
    if len(parts) != 3:
        raise SystemExit(f"✗ «{task.get('title')}»: where нужен в виде «проект/доска/колонка»")
    p = pick(projects, parts[0], "Проект")
    b = pick(p["boards"], parts[1], "Доска")
    c = pick(b["columns"], parts[2], "Колонка")
    if not str(task.get("title", "")).strip():
        raise SystemExit("✗ У задачи нет заголовка")
    body: dict = {"title": task["title"].strip(), "columnId": c["id"]}
    if task.get("description"):
        body["description"] = task["description"].replace("\n", "<br>")
    if task.get("files"):
        block = files_block(task["files"])
        body["description"] = f"{body['description']}<br><br>{block}" if body.get("description") else block
    if task.get("claude"):
        block = claude_block(task["claude"], task.get("when"), task.get("chat"))
        body["description"] = f"{body['description']}<br><br>{block}" if body.get("description") else block
    if task.get("deadline"):
        d = dt.datetime.strptime(task["deadline"], "%Y-%m-%d").replace(hour=12)
        body["deadline"] = {"deadline": int(d.timestamp() * 1000), "withTime": False}
    if task.get("assign"):
        q = task["assign"].strip().lower()
        hit = [u for u in users or [] if q in (u.get("realName") or "").lower() or q == (u.get("email") or "").lower()]
        if len(hit) != 1:
            raise SystemExit(f"✗ Исполнитель «{task['assign']}»: {'неоднозначно' if hit else 'не найден'}")
        body["assigned"] = [hit[0]["id"]]
    return body, f"{p['title']} / {b['title']} / {c['title']}"


def create_all(tasks: list[dict], dry_run: bool = False) -> None:
    key = load_key()
    projects = tree(key)
    users = content(key, "/users") if any(t.get("assign") for t in tasks) else None
    ready = [prepare(key, t, projects, users) for t in tasks]     # всё проверено до первой записи
    for body, place in ready:
        if dry_run:
            print(f"· {body['title']} → {place}")
            continue
        tid = call("POST", "/tasks", body, key=key)["id"]
        t = call("GET", f"/tasks/{tid}", key=key)
        code = t.get("idTaskProject") or t.get("idTaskCommon") or tid
        print(f"✓ {code} «{body['title']}» → {place}")


def cmd_create(a: argparse.Namespace) -> None:
    create_all([{"where": a.where, "title": a.title, "description": a.description,
                 "deadline": a.deadline, "assign": a.assign}])


def cmd_push(a: argparse.Namespace) -> None:
    tasks = json.loads(Path(a.file).read_text(encoding="utf-8"))
    create_all(tasks if isinstance(tasks, list) else [tasks], dry_run=a.dry_run)


def find_task(key: str, code: str) -> dict:
    """Задача по коду вида VED-27 — так её видно на доске и так её называют в чате."""
    c = code.strip().upper()
    hit = [t for t in content(key, "/tasks")
           if c in ((t.get("idTaskProject") or "").upper(), (t.get("idTaskCommon") or "").upper())]
    if len(hit) != 1:
        raise SystemExit(f"✗ Задача {code}: {'неоднозначно' if hit else 'не найдена'}")
    return hit[0]


def place_of(key: str, column_id: str | None) -> str:
    for p in tree(key):
        for b in p["boards"]:
            for c in b["columns"]:
                if c["id"] == column_id:
                    return f"{p['title']} / {b['title']} / {c['title']}"
    return "—"


def cmd_show(a: argparse.Namespace) -> None:
    key = load_key()
    t = find_task(key, a.code)
    print(f"{a.code.upper()} «{t['title']}»{' ✓' if t.get('completed') else ''}")
    print(f"  {place_of(key, t.get('columnId'))}")
    if (t.get("deadline") or {}).get("deadline"):
        print(f"  срок: {dt.date.fromtimestamp(t['deadline']['deadline'] / 1000)}")
    for line in re.sub(r"<br\s*/?>", "\n", t.get("description") or "").splitlines():
        print(f"  {line}")


def cmd_mark(a: argparse.Namespace) -> None:
    key = load_key()
    t = find_task(key, a.code)
    old = t.get("description") or ""
    if "🤖 Claude:" in old:
        raise SystemExit(f"✗ {a.code}: пометка уже есть — `show`, чтобы посмотреть")
    block = claude_block(a.claude, a.when, a.chat)
    call("PUT", f"/tasks/{t['id']}", {"description": f"{old}<br><br>{block}" if old else block}, key=key)
    print(f"✓ {a.code.upper()} «{t['title']}» — пометка добавлена")


def cmd_files(a: argparse.Namespace) -> None:
    key = load_key()
    t = find_task(key, a.code)
    old = t.get("description") or ""
    if "📁 Файлы:" in old:
        raise SystemExit(f"✗ {a.code}: ссылки на файлы уже есть — `show`, чтобы посмотреть")
    block = files_block(a.path)
    call("PUT", f"/tasks/{t['id']}", {"description": f"{old}<br><br>{block}" if old else block}, key=key)
    print(f"✓ {a.code.upper()} «{t['title']}» — ссылки на {a.path} добавлены")


def cmd_done(a: argparse.Namespace) -> None:
    key = load_key()
    t = find_task(key, a.code)
    if t.get("completed"):
        raise SystemExit(f"✗ {a.code}: уже выполнена")
    call("PUT", f"/tasks/{t['id']}", {"completed": True}, key=key)
    print(f"✓ {a.code.upper()} «{t['title']}» — выполнена")


def main() -> int:
    ap = argparse.ArgumentParser(description="YouGile: задачи по проектам")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup").set_defaults(fn=cmd_setup)
    sub.add_parser("tree").set_defaults(fn=cmd_tree)
    sub.add_parser("users").set_defaults(fn=cmd_users)
    t = sub.add_parser("tasks")
    t.add_argument("--where", required=True)
    t.add_argument("--limit", type=int, default=30)
    t.set_defaults(fn=cmd_tasks)
    c = sub.add_parser("create")
    c.add_argument("--where", required=True, help="проект/доска/колонка")
    c.add_argument("--title", required=True)
    c.add_argument("--description")
    c.add_argument("--deadline", help="ГГГГ-ММ-ДД")
    c.add_argument("--assign", help="имя или email исполнителя")
    c.set_defaults(fn=cmd_create)
    pu = sub.add_parser("push")
    pu.add_argument("--file", required=True, help="JSON-список задач")
    pu.add_argument("--dry-run", action="store_true", help="только проверить адреса и показать, куда ляжет")
    pu.set_defaults(fn=cmd_push)
    sh = sub.add_parser("show")
    sh.add_argument("--code", required=True, help="код задачи, например VED-27")
    sh.set_defaults(fn=cmd_show)
    mk = sub.add_parser("mark")
    mk.add_argument("--code", required=True)
    mk.add_argument("--claude", required=True, help="что делает ассистент")
    mk.add_argument("--when", help="когда закинуть задачу ассистенту")
    mk.add_argument("--chat", help="id сессии Claude Code")
    mk.set_defaults(fn=cmd_mark)
    fl = sub.add_parser("files")
    fl.add_argument("--code", required=True)
    fl.add_argument("--path", required=True, help="папка или файл волта, например clients/arcars/reports/drafts-2026-10-27")
    fl.set_defaults(fn=cmd_files)
    dn = sub.add_parser("done")
    dn.add_argument("--code", required=True)
    dn.set_defaults(fn=cmd_done)
    a = ap.parse_args()
    a.fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
