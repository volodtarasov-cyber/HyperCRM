#!/usr/bin/env python3
"""Вход для периодического разбора: что изменилось с прошлого прогона.

Скрипт не делает выводов — он готовит факты, на которых выводы делаются:
какие задачи закрыты и с каким следом, что появилось, что не двигается,
что протухло и какие чекпоинты на горизонте.

Сравнение идёт со снимком прошлого прогона в `.tools/review-state.json`, а не
с git: коммиты делаются нерегулярно, а разбор должен работать в любом случае.
Снимок и отчёт живут вне волта — по правилу «гигиена не создаёт склад событий».

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/vault/review.py
    ... --dry     # показать, но не сохранять новый снимок
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board import EXTERNAL_STALE_DAYS, ROOT, collect, collect_external  # noqa: E402

STATE = ROOT / ".tools" / "review-state.json"
STALE_TASK_DAYS = 21


def key(project_slug: str, task) -> str:
    return f"{project_slug}|{task.source}|{task.text}"


def snapshot(projects) -> dict:
    tasks = {}
    for slug, project in projects.items():
        for task in project.tasks:
            tasks[key(slug, task)] = {
                "project": project.title,
                "text": task.text,
                "done": task.done,
                "trace": task.trace,
                "source": task.source,
            }
    return {"date": dt.date.today().isoformat(), "tasks": tasks}


def load_previous() -> dict | None:
    if not STATE.exists():
        return None
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def section(title: str, lines: list[str]) -> None:
    if not lines:
        return
    print(f"\n## {title}\n")
    for line in lines:
        print(line)


def external_block() -> None:
    """Обратный ход: что случилось снаружи и не вернулось в волт.

    Задачи и свежесть файлов смотрят внутрь. Ролик, вышедший на YouTube,
    оплата, отвалившийся сертификат — внутрь не возвращаются никогда, и волт
    продолжает описывать позавчерашний мир, не подавая ни одного признака.
    Спросить дешевле, чем обнаружить через полтора месяца.
    """
    items = collect_external()
    print("\n## Что снаружи — спросить и свести\n")
    if not items:
        print("- меток нет. Отмечай так: `- [вне] что сверяем ⟳ 2026-08-25`")
        print("  (`⟳ —` — если не сверялось ни разу). Метка живёт рядом с фактом,")
        print("  не в отдельном реестре: отдельный реестр протухнет первым.")
        return
    for item in items:
        if item.age is None:
            mark, note = "‼", "не сверялось ни разу"
        elif item.age >= EXTERNAL_STALE_DAYS:
            mark, note = "!", f"{item.age} дн. назад"
        else:
            mark, note = " ", f"{item.age} дн. назад"
        print(f"{mark} {item.text}")
        print(f"      сверяли: {note} · {item.source}:{item.line}")
    print("\n  Свёл — поставь сегодняшнюю дату после ⟳ в том же файле.")


def main() -> int:
    projects, upcoming = collect()
    current = snapshot(projects)
    previous = load_previous()
    today = dt.date.today()

    print("=" * 62)
    if previous:
        gap = (today - dt.date.fromisoformat(previous["date"])).days
        print(f"Разбор {today} · прошлый прогон {previous['date']} ({gap} дн. назад)")
    else:
        print(f"Разбор {today} · первый прогон, сравнивать не с чем")
    print("=" * 62)

    old = previous["tasks"] if previous else {}
    closed, opened, appeared, vanished = [], [], [], []

    for task_key, now in current["tasks"].items():
        was = old.get(task_key)
        if was is None:
            # Задача, заведённая и закрытая между прогонами, тоже результат периода —
            # иначе работа, сделанная по ходу, исчезает из разбора бесследно.
            if now["done"]:
                trace = now["trace"] or "без следа"
                closed.append(f"- {now['project']}: {now['text']}\n      след: {trace}")
            else:
                appeared.append(f"- {now['project']}: {now['text']}")
            continue
        if now["done"] and not was["done"]:
            trace = now["trace"] or "без следа"
            closed.append(f"- {now['project']}: {now['text']}\n      след: {trace}")
        elif was["done"] and not now["done"]:
            opened.append(f"- {now['project']}: {now['text']}")

    for task_key, was in old.items():
        if task_key not in current["tasks"]:
            vanished.append(f"- {was['project']}: {was['text']}")

    section("Закрыто с прошлого раза", closed)
    section("Снова открыто", opened)
    section("Новые задачи", appeared)
    section("Исчезло из индексов", vanished)

    if previous:
        stuck = []
        for task_key, now in current["tasks"].items():
            if now["done"] or task_key not in old:
                continue
            stuck.append(f"- {now['project']}: {now['text']}")
        if stuck:
            gap = (today - dt.date.fromisoformat(previous["date"])).days
            if gap >= STALE_TASK_DAYS:
                section(f"Не двигается {gap} дн.", stuck)
            else:
                print(f"\n## Висит с прошлого раза: {len(stuck)}\n")
                for line in stuck[:8]:
                    print(line)
                if len(stuck) > 8:
                    print(f"  … ещё {len(stuck) - 8}")

    external_block()

    attention = []
    for project in projects.values():
        attention.extend(f"- {project.title}: {item}" for item in project.attention)
    section("Требует внимания", attention)
    section("Чекпоинты на горизонте", [f"- {item}" for item in upcoming])

    total_open = sum(len(p.open_tasks) for p in projects.values())
    no_trace = sum(1 for t in current["tasks"].values() if t["done"] and not t["trace"])
    print(f"\n{'-' * 62}")
    print(f"Открыто: {total_open} · закрыто всего: "
          f"{sum(1 for t in current['tasks'].values() if t['done'])}"
          + (f" · из них без следа: {no_trace}" if no_trace else ""))
    print("Дальше — разбор в диалоге: что это значит и что делаем следующим.")

    if "--dry" not in sys.argv:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
