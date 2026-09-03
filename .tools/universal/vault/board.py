#!/usr/bin/env python3
"""Визуальная доска волта: задачи по проектам и то, что требует внимания.

Задачей считается незакрытый чекбокс в индексном файле проекта, клиента или
в материалах направления `practice`. Правило намеренное: чтобы задача попала
на доску, её кладут в индекс, а не вглубь рабочего документа — иначе доска
соберёт семь сотен чек-листов из аналитики и перестанет быть доской.

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/vault/board.py
    .tools/venv/Scripts/python.exe .tools/universal/vault/board.py --open
"""

from __future__ import annotations

import datetime as dt
import html
import re
import sys
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / ".tools" / "board.html"

TASK_RE = re.compile(r"(?m)^- \[( |x|X)\]\s+(.+)$")
HEADING_RE = re.compile(r"(?m)^(#{2,4})\s+(.+)$")
CHECKED_RE = re.compile(r"(?mi)^\*\*Проверено:\*\*\s*(20\d{2}-\d{2}-\d{2})")
HYP_RE = re.compile(r"(?m)^###\s+(HYP-[^|\n]+)\s*\|\s*(20\d{2}-\d{2}-\d{2})\s*\|\s*Статус:\s*([^\n]+)")
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TRACE_MARK = "↳"  # ↳ — след закрытия: дописывается доской и ею же снимается

# Регулярные ритмы: «- [Пн] текст ⟳ 2026-08-17». Не чекбоксы: такие дела не
# закрываются навсегда, а наступают снова, поэтому хранится дата последнего раза.
RECUR_MARK = "⟳"
RECUR_RE = re.compile(r"(?m)^- \[([^\]]{1,4})\]\s+(.+?)\s*" + RECUR_MARK + r"\s*(20\d{2}-\d{2}-\d{2})\s*$")
WEEKDAYS = {"пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6}
PERIODS = {"мес": 30, "кв": 90}

# Внешние факты: «- [вне] YouTube-канал: ссылка и метрики ⟳ 2026-08-25».
# Состояние такой вещи живёт вне волта и внутрь само не возвращается: ролик
# вышел, клиент заплатил, сертификат протух — в файлах не изменилось ничего.
# Поэтому прогон обязан спросить вслух. `⟳ —` значит «не сверялось ни разу».
EXTERNAL_LABEL = "вне"
EXTERNAL_RE = re.compile(
    r"(?m)^- \[вне\]\s+(.+?)\s*" + RECUR_MARK + r"\s*(20\d{2}-\d{2}-\d{2}|—)\s*$"
)
EXTERNAL_STALE_DAYS = 14

STALE_DAYS = 45
PROJECT_TITLES = {
    "practice": "Личная практика",
    "detailing-samara": "Детейлинг (Левша)",
    "traffic-freelance": "Трафик-портфель",
    "ai-infobiz": "AI-инфобиз",
    "marketing-os": "Marketing OS",
    "seo-sites": "SEO-сайты",
}
ORDER = ["practice", "detailing-samara", "traffic-freelance", "ai-infobiz", "seo-sites", "marketing-os"]
ACTIVE_HYP_MARKERS = ("\U0001f9ea", "провер", "тест")
INACTIVE_HYP_MARKERS = ("⏸", "\U0001f4e6", "\U0001f4a1", "отлож", "пауза", "архив", "сыр")

HINT = ('<div class="hint">Клик по задаче закрывает её — но только вместе со следом: '
        'что появилось в системе. Зелёная точка значит, что артефакт по ссылке уже на месте. '
        'Обновить страницу — перечитать волт.</div>')

SCRIPT = """<script>
document.addEventListener('click', function (event) {
  const row = event.target.closest('.task[data-file]');
  if (!row || row.dataset.busy) return;
  var trace = null;
  if (!row.classList.contains('done')) {
    trace = window.prompt(
      'Что появилось в системе? Файл, цифра, ссылка, договорённость.\\n' +
      'Пусто — задача останется открытой.',
      row.querySelector('.art.ok') ? 'артефакт по ссылке на месте' : ''
    );
    if (trace === null || !trace.trim()) return;
  }
  row.dataset.busy = '1';
  fetch('/toggle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file: row.dataset.file, line: Number(row.dataset.line), trace: trace })
  }).then(function (response) {
    return response.json();
  }).then(function (data) {
    if (!data.ok) { alert('Не записалось: ' + data.error); return; }
    row.classList.toggle('done', data.done);
    row.querySelector('.mark').innerHTML = data.done ? '&#10003;' : '&#9675;';
    var box = row.querySelector('.txt');
    var old = box.querySelector('.trace');
    if (old) old.remove();
    if (data.done && data.trace) {
      var el = document.createElement('span');
      el.className = 'trace';
      el.textContent = data.trace;
      box.appendChild(el);
    }
    const counter = document.querySelector('.stat b');
    if (counter) counter.textContent = String(Number(counter.textContent) + (data.done ? -1 : 1));
  }).catch(function (error) {
    alert('Сервер не ответил: ' + error);
  }).finally(function () {
    delete row.dataset.busy;
  });
});
document.addEventListener('click', function (event) {
  const row = event.target.closest('.rt[data-rfile]');
  if (!row || row.dataset.busy) return;
  row.dataset.busy = '1';
  fetch('/touch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file: row.dataset.rfile, line: Number(row.dataset.rline) })
  }).then(function (r) { return r.json(); }).then(function (data) {
    if (!data.ok) { alert('Не записалось: ' + data.error); return; }
    row.classList.remove('due');
    row.querySelector('.note').textContent = 'был сегодня';
  }).catch(function (e) {
    alert('Сервер не ответил: ' + e);
  }).finally(function () { delete row.dataset.busy; });
});
document.addEventListener('keydown', function (event) {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const row = document.activeElement;
  if (row && row.classList && (row.classList.contains('task') || row.classList.contains('rt'))) {
    event.preventDefault(); row.click();
  }
});
</script>"""


@dataclass
class Task:
    text: str
    done: bool
    section: str
    source: str
    line: int = 0
    trace: str = ""      # след закрытия: что появилось в системе
    linked: str = ""     # "ok" / "missing" — ссылка на артефакт из текста задачи


@dataclass
class Project:
    slug: str
    title: str
    tasks: list = field(default_factory=list)
    attention: list = field(default_factory=list)

    @property
    def open_tasks(self):
        return [t for t in self.tasks if not t.done]


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def mask_noncontent(text: str) -> str:
    """Прячет HTML-комментарии и fenced-блоки, сохраняя длину и номера строк.

    Без этого доска считает задачами примеры из шаблонов и закомментированные
    блоки — проверено на HYP-001 детейлинга, который лежит внутри комментария.
    """

    def mask(match):
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    text = re.sub(r"<!--.*?-->", mask, text, flags=re.DOTALL)
    return re.sub(r"```.*?```", mask, text, flags=re.DOTALL)


def section_at(text: str, offset: int) -> str:
    last = ""
    for match in HEADING_RE.finditer(text):
        if match.start() > offset:
            break
        last = match.group(2).strip()
    return last


def strip_md(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"[*`~]", "", value)
    return value.strip()


def task_sources():
    paths = []
    for path in (ROOT / "projects").rglob("_index.md"):
        if "_archive" not in path.parts:
            paths.append(path)
    practice = ROOT / "projects" / "practice"
    if practice.exists():
        # Шаблоны пропускаем: их пустые чекбоксы («- [ ] ________») доска
        # считала задачами и показывала в прогоне как настоящую работу.
        paths.extend(p for p in practice.rglob("*.md")
                     if not p.stem.endswith("-template") and "templates" not in p.parts)
    return sorted(set(paths))


def project_of(path: Path) -> str:
    rel = path.relative_to(ROOT).parts
    return rel[1] if len(rel) > 2 and rel[0] == "projects" else rel[-2]


def collect():
    projects = {}
    today = dt.date.today()
    upcoming = []

    for path in task_sources():
        text = mask_noncontent(read(path))
        slug = project_of(path)
        rel = path.relative_to(ROOT).as_posix()
        project = projects.setdefault(slug, Project(slug, PROJECT_TITLES.get(slug, slug)))

        for match in TASK_RE.finditer(text):
            raw = match.group(2).strip()
            if raw.startswith("~~"):
                continue
            trace = ""
            if TRACE_MARK in raw:
                raw, _, trace = raw.partition(TRACE_MARK)
                raw, trace = raw.strip(), trace.strip()
            linked = ""
            for target in LINK_RE.findall(raw):
                if target.startswith(("http://", "https://", "#")):
                    continue
                linked = "ok" if (path.parent / target.split("#")[0]).exists() else "missing"
                break
            project.tasks.append(Task(
                text=strip_md(raw),
                done=match.group(1).lower() == "x",
                section=section_at(text, match.start()),
                source=rel,
                line=text.count("\n", 0, match.start()) + 1,
                trace=trace,
                linked=linked,
            ))

        checked = CHECKED_RE.search(text)
        if checked and path.name == "_index.md":
            age = (today - dt.date.fromisoformat(checked.group(1))).days
            if age > STALE_DAYS:
                project.attention.append(f"{rel}: проверено {age} дн. назад")

    for path in (ROOT / "projects").rglob("hypotheses.md"):
        if "_archive" in path.parts:
            continue
        text = mask_noncontent(read(path))
        slug = project_of(path)
        project = projects.setdefault(slug, Project(slug, PROJECT_TITLES.get(slug, slug)))
        matches = list(HYP_RE.finditer(text))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[match.start():end]
            status = match.group(3).lower()
            if any(marker in status for marker in INACTIVE_HYP_MARKERS):
                continue
            if not any(marker in status for marker in ACTIVE_HYP_MARKERS):
                continue
            dates = sorted({dt.date.fromisoformat(d) for d in DATE_RE.findall(block)})
            future = [d for d in dates if d >= today]
            name = match.group(1).strip()
            if dates and not future:
                project.attention.append(f"{name}: чекпоинт прошёл ({max(dates)}), результата нет")
            elif future and (future[0] - today).days <= 14:
                upcoming.append(f"{name} — чекпоинт {future[0]} (через {(future[0] - today).days} дн.)")

    return projects, upcoming


@dataclass
class External:
    text: str
    last: dt.date | None   # None — не сверялось ни разу
    source: str
    line: int
    age: int | None        # дней с последней сверки; None если не сверялось


def external_sources():
    """Внешние факты живут рядом со своим фактом, а не в одном реестре.

    Реестр пришлось бы поддерживать отдельно, и он бы протух первым — ровно
    та болезнь, от которой этот механизм лечит.
    """
    paths = []
    for root in ("projects", "life"):
        for path in (ROOT / root).rglob("*.md"):
            if "_archive" not in path.parts:
                paths.append(path)
    return sorted(set(paths))


def collect_external():
    today = dt.date.today()
    found = []
    for path in external_sources():
        text = mask_noncontent(read(path))
        for match in EXTERNAL_RE.finditer(text):
            raw = match.group(2)
            last = None if raw == "—" else dt.date.fromisoformat(raw)
            found.append(External(
                text=strip_md(match.group(1).strip()),
                last=last,
                source=path.relative_to(ROOT).as_posix(),
                line=text.count("\n", 0, match.start()) + 1,
                age=None if last is None else (today - last).days,
            ))
    # Ни разу не сверенное — вперёд: это самая дорогая слепая зона.
    return sorted(found, key=lambda e: (e.age is not None, -(e.age or 0)))


@dataclass
class Routine:
    label: str      # «Пн» / «мес» — когда положено
    text: str
    last: dt.date
    source: str
    line: int
    due: bool       # пора делать
    overdue: int    # на сколько дней просрочено, 0 если нет


def collect_routines():
    """Регулярные ритмы из секций «Регулярно» индексов проектов."""
    today = dt.date.today()
    found = []
    for path in task_sources():
        text = mask_noncontent(read(path))
        for match in RECUR_RE.finditer(text):
            label, body, date_raw = match.group(1).strip(), match.group(2).strip(), match.group(3)
            if label.lower() == EXTERNAL_LABEL:
                continue  # это внешний факт, у него свой сбор — collect_external()
            last = dt.date.fromisoformat(date_raw)
            age = (today - last).days
            key = label.lower()

            if key in WEEKDAYS:
                period = 7
                # Пора, если наступил нужный день недели и на этой неделе ещё не делали.
                due = age >= 7 or (today.weekday() == WEEKDAYS[key] and age >= 1)
            else:
                period = PERIODS.get(key, 7)
                due = age >= period

            found.append(Routine(
                label=label,
                text=strip_md(body),
                last=last,
                source=path.relative_to(ROOT).as_posix(),
                line=text.count("\n", 0, match.start()) + 1,
                due=due,
                overdue=max(0, age - period),
            ))
    return sorted(found, key=lambda r: (not r.due, -r.overdue))


def routines_block(routines, interactive: bool) -> str:
    if not routines:
        return ""
    today = dt.date.today()
    rows = []
    for item in routines:
        cls = "rt due" if item.due else "rt"
        attrs = ""
        if interactive:
            attrs = (' data-rfile="' + html.escape(item.source) + '"'
                     ' data-rline="' + str(item.line) + '" tabindex="0" role="button"')
        age = (today - item.last).days
        if item.overdue:
            note = f"просрочено на {item.overdue} дн."
        elif item.due:
            note = "пора"
        else:
            note = f"был {age} дн. назад"
        rows.append(
            '<div class="' + cls + '"' + attrs + '>'
            + '<span class="when">' + html.escape(item.label) + "</span>"
            + '<span class="txt">' + html.escape(item.text) + "</span>"
            + '<span class="note">' + note + "</span></div>"
        )
    due_count = sum(1 for item in routines if item.due)
    return ('<section class="routines"><h2>Регулярно<span class="cnt">' + str(due_count) + "</span></h2>"
            + '<p class="colsub">Не закрывается навсегда — отметил, наступит снова. '
              'Клик ставит сегодняшнюю дату.</p>' + "".join(rows) + "</section>")


def external_block() -> str:
    """Отдельная секция, а не строки среди ритмов.

    Ритм — то, что делаешь сам и отмечаешь. Внешний факт — то, что происходит
    без тебя и требует не выполнения, а сверки. Смешивать их в одном списке
    нельзя: получается список дел, половина которого делами не является.
    """
    items = collect_external()
    if not items:
        return ""
    rows = []
    for item in items:
        if item.age is None:
            cls, note = "rt due", "не сверялось"
        elif item.age >= EXTERNAL_STALE_DAYS:
            cls, note = "rt due", f"сверяли {item.age} дн. назад"
        else:
            cls, note = "rt", f"сверяли {item.age} дн. назад"
        rows.append(
            '<div class="' + cls + '">'
            + '<span class="when">СНАРУЖИ</span>'
            + '<span class="txt">' + html.escape(item.text) + "</span>"
            + '<span class="note">' + note + "</span></div>"
        )
    stale = sum(1 for item in items if item.age is None or item.age >= EXTERNAL_STALE_DAYS)
    return ('<section class="routines"><h2>Живёт снаружи<span class="cnt">' + str(stale) + "</span></h2>"
            + '<p class="colsub">Состояние меняется вне волта и внутрь само не возвращается. '
              'Не задачи — вопросы, которые задаёт прогон.</p>' + "".join(rows) + "</section>")


MAIN_LIMIT = 3


def split_focus(projects):
    """Делит открытые задачи на главные дня, мелкие и остальное.

    Главные — из первого «Дня N», где ещё есть незакрытое, не больше трёх:
    правило трёх это ограничение, а не описание, поэтому лишнее из того же дня
    уходит вниз. Мелкие — то, что помечено как мелочи, и задачи клиентских
    карточек: их берут между делом, а не вместо главного.
    """
    days: dict[str, list] = {}
    small: list = []
    for project in projects.values():
        for task in project.tasks:
            if task.done:
                continue
            section = task.section or ""
            if section.startswith("День ") and task.source.endswith("practice/_index.md"):
                days.setdefault(section, []).append(task)
            elif "мелоч" in section.lower() or "/clients/" in task.source:
                small.append(task)

    def day_number(name: str) -> int:
        match = re.match(r"День\s+(\d+)", name)
        return int(match.group(1)) if match else 999

    day_name, main = "", []
    for name in sorted(days, key=day_number):
        if days[name]:
            day_name, main = name, days[name]
            break
    return day_name, main[:MAIN_LIMIT], len(main) - len(main[:MAIN_LIMIT]), small


def focus_block(day_name: str, main, spill: int, small, interactive: bool) -> str:
    if not main and not small:
        return ""

    def row(task) -> str:
        attrs = ""
        if interactive:
            attrs = (' data-file="' + html.escape(task.source) + '"'
                     ' data-line="' + str(task.line) + '" tabindex="0" role="button"')
        art = ""
        if task.linked == "ok":
            art = '<span class="art ok" title="артефакт на месте">&#9679;</span>'
        elif task.linked == "missing":
            art = '<span class="art no" title="артефакта ещё нет">&#9679;</span>'
        return ('<div class="task"' + attrs + '><span class="mark">&#9675;</span>'
                + '<span class="txt">' + html.escape(task.text) + "</span>" + art + "</div>")

    left = "".join(row(t) for t in main) or '<div class="empty">На сегодня главного нет — бери из мелкого</div>'
    spill_note = (f'<div class="spill">Ещё {spill} в этом дне — после трёх главных</div>' if spill else "")
    right = "".join(row(t) for t in small) or '<div class="empty">Мелкого нет</div>'

    return (
        '<div class="focus">'
        '<section class="col main"><h2>Главное' + (' · ' + html.escape(day_name) if day_name else "")
        + '<span class="cnt">' + str(len(main)) + "</span></h2>"
        + '<p class="colsub">Три задачи. Пока они не закрыты, остальное не начинаем.</p>'
        + left + spill_note + "</section>"
        '<section class="col small"><h2>Мелкое<span class="cnt">' + str(len(small)) + "</span></h2>"
        + '<p class="colsub">Берётся после главных или в паузах — по десять-двадцать минут.</p>'
        + right + "</section></div>"
    )


# --- Сводка направления: деньги, блокеры, чекпоинты, реестр -----------------
# Всё читается из markdown волта: доска рендерит, но не хранит. Единственный
# источник правды остаётся в файлах, иначе цифры на доске начнут расходиться
# с теми, по которым принимаются решения.

PRACTICE_INDEX = ROOT / "projects" / "practice" / "_index.md"
PRACTICE_PLAN = ROOT / "projects" / "practice" / "plan.md"
SEP_RE = re.compile(r"^:?-{2,}:?$")
DDMM_RE = re.compile(r"(\d{1,2})\.(\d{1,2})")


def md_section(text: str, needle: str) -> str:
    """Тело секции, чей заголовок содержит подстроку. До следующего заголовка
    того же или более высокого уровня."""
    for match in HEADING_RE.finditer(text):
        if needle.lower() not in match.group(2).lower():
            continue
        level = len(match.group(1))
        rest = text[match.end():]
        nxt = re.search(r"(?m)^#{1," + str(level) + r"}\s+\S", rest)
        return rest[:nxt.start()] if nxt else rest
    return ""


def md_tables(body: str):
    """Все markdown-таблицы секции как списки строк-ячеек, без разделителей."""
    chunks, current = [], []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            current.append(stripped)
        elif current:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)

    tables = []
    for chunk in chunks:
        rows = []
        for line in chunk:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and all(SEP_RE.match(c) for c in cells if c):
                continue
            rows.append([strip_md(c) for c in cells])
        if rows:
            tables.append(rows)
    return tables


def money_block() -> str:
    body = md_section(read(PRACTICE_INDEX), "Деньги сейчас")
    tables = md_tables(body)
    if not tables:
        return ""
    rows = tables[0]
    note = ""
    for line in body.splitlines():
        if line.strip().startswith(">"):
            note = strip_md(line.strip("> ").strip())
            break

    cells = []
    for row in rows[1:] if len(rows) > 1 else []:
        if len(row) < 2:
            continue
        label, value = row[0], row[1]
        state = row[2] if len(row) > 2 else ""
        if not label and not value:
            continue
        total = "итого" in label.lower()
        cls = "mcell total" if total else "mcell"
        cells.append(
            '<div class="' + cls + '"><b>' + html.escape(value) + "</b>"
            '<span class="ml">' + html.escape(label or "Итого") + "</span>"
            + ('<span class="mst">' + html.escape(state) + "</span>" if state else "")
            + "</div>"
        )
    if not cells:
        return ""
    sub = '<div class="colsub">' + html.escape(note) + "</div>" if note else ""
    return ('<section class="money"><h2>Деньги сейчас</h2>' + sub
            + '<div class="mgrid">' + "".join(cells) + "</div></section>")


def blockers_block() -> str:
    body = md_section(read(PRACTICE_INDEX), "Что стоит и чего ждёт")
    tables = md_tables(body)
    if not tables:
        return ""
    rows = [r for r in tables[0][1:] if len(r) >= 2 and r[0]]
    if not rows:
        return ""
    items = []
    for row in rows:
        who = row[2] if len(row) > 2 else ""
        items.append(
            '<div class="blk"><span class="bk">' + html.escape(row[0]) + "</span>"
            '<span class="bh">' + html.escape(row[1]) + "</span>"
            + ('<span class="bw">' + html.escape(who) + "</span>" if who else "")
            + "</div>"
        )
    return ('<section class="blockers"><h2>Что стоит<span class="cnt">'
            + str(len(rows)) + "</span></h2>" + "".join(items) + "</section>")


def checkpoints_block() -> str:
    """Чекпоинты плана с расчётом, сколько дней осталось."""
    body = md_section(read(PRACTICE_PLAN), "Чекпоинты")
    tables = md_tables(body)
    if not tables:
        return ""
    today = dt.date.today()
    items = []
    for row in tables[0][1:]:
        if len(row) < 2 or not row[0]:
            continue
        match = DDMM_RE.search(row[0])
        left, cls = "", "cp"
        if match:
            day, month = int(match.group(1)), int(match.group(2))
            try:
                when = dt.date(today.year, month, day)
            except ValueError:
                when = None
            if when:
                days = (when - today).days
                if days < 0:
                    left, cls = "просрочен", "cp over"
                elif days == 0:
                    left, cls = "сегодня", "cp soon"
                else:
                    left = "через " + str(days) + " дн."
                    cls = "cp soon" if days <= 14 else "cp"
        threshold = row[2] if len(row) > 2 else ""
        items.append(
            '<div class="' + cls + '"><span class="cpd">' + html.escape(row[0]) + "</span>"
            '<span class="cpt">' + html.escape(row[1])
            + ('<span class="cpn">' + html.escape(threshold) + "</span>" if threshold else "")
            + "</span>"
            + ('<span class="cpl">' + html.escape(left) + "</span>" if left else "")
            + "</div>"
        )
    if not items:
        return ""
    return ('<section class="cps"><h2>Чекпоинты</h2>' + "".join(items) + "</section>")


def registry_block() -> str:
    """Реестр проектов: подсекции с таблицами как есть."""
    body = md_section(read(PRACTICE_INDEX), "Реестр проектов")
    if not body:
        return ""
    parts, current_title, buffer = [], "", []
    for line in body.splitlines():
        heading = re.match(r"^#{3,4}\s+(.+)$", line.strip())
        if heading:
            if current_title:
                parts.append((current_title, "\n".join(buffer)))
            current_title, buffer = strip_md(heading.group(1)), []
        else:
            buffer.append(line)
    if current_title:
        parts.append((current_title, "\n".join(buffer)))

    groups = []
    for title, chunk in parts:
        tables = md_tables(chunk)
        if not tables:
            continue
        rows = tables[0][1:]
        lines = []
        for row in rows:
            if not row or not row[0]:
                continue
            tail = " · ".join(c for c in row[1:] if c)
            lines.append('<div class="rrow"><span class="rn">' + html.escape(row[0])
                         + '</span><span class="rv">' + html.escape(tail) + "</span></div>")
        if lines:
            groups.append('<div class="rgrp"><div class="sec">' + html.escape(title)
                          + "</div>" + "".join(lines) + "</div>")
    if not groups:
        return ""
    return '<section class="reg"><h2>Проекты и клиенты</h2>' + "".join(groups) + "</section>"


def render(projects, upcoming, interactive: bool = False) -> str:
    today = dt.date.today().isoformat()
    ordered = [projects[s] for s in ORDER if s in projects]
    ordered += [p for s, p in sorted(projects.items()) if s not in ORDER]
    ordered = [p for p in ordered if p.tasks or p.attention]

    total_open = sum(len(p.open_tasks) for p in ordered)
    total_done = sum(len(p.tasks) - len(p.open_tasks) for p in ordered)
    attention = sum(len(p.attention) for p in ordered) + len(upcoming)

    blocks = []
    for project in ordered:
        by_section = {}
        for task in project.tasks:
            by_section.setdefault(task.section or "—", []).append(task)

        rows = []
        for section, tasks in by_section.items():
            rows.append('<div class="sec">' + html.escape(section) + "</div>")
            for task in tasks:
                cls = "task done" if task.done else "task"
                mark = "&#10003;" if task.done else "&#9675;"
                attrs = ""
                if interactive:
                    attrs = (' data-file="' + html.escape(task.source) + '"'
                             ' data-line="' + str(task.line) + '" tabindex="0" role="button"')
                # Артефакт: ✓ ссылка ведёт на существующий файл, ! ссылка битая
                art = ""
                if task.linked == "ok":
                    art = '<span class="art ok" title="артефакт на месте">&#9679;</span>'
                elif task.linked == "missing":
                    art = '<span class="art no" title="артефакта ещё нет">&#9679;</span>'
                trace = ""
                if task.trace:
                    trace = '<span class="trace">' + html.escape(task.trace) + "</span>"
                rows.append(
                    '<div class="' + cls + '"' + attrs + '><span class="mark">' + mark + "</span>"
                    + '<span class="txt">' + html.escape(task.text) + trace + "</span>"
                    + art + '<span class="src">' + html.escape(task.source) + "</span></div>"
                )

        att = ""
        if project.attention:
            items = "".join("<li>" + html.escape(a) + "</li>" for a in project.attention)
            att = '<div class="att"><b>Требует внимания</b><ul>' + items + "</ul></div>"

        blocks.append(
            "<section><h2>" + html.escape(project.title)
            + '<span class="cnt">' + str(len(project.open_tasks)) + "</span></h2>"
            + att + "".join(rows) + "</section>"
        )

    warn = ""
    if upcoming:
        items = "".join("<li>" + html.escape(a) + "</li>" for a in upcoming)
        warn = '<div class="soon"><b>Ближайшие чекпоинты</b><ul>' + items + "</ul></div>"

    day_name, main, spill, small = split_focus(projects)
    focus = focus_block(day_name, main, spill, small, interactive)
    routines = routines_block(collect_routines(), interactive)
    external = external_block()
    money = money_block()
    blockers = blockers_block()
    checkpoints = checkpoints_block()
    registry = registry_block()

    style = """
:root { --bg:#2B223A; --card:#352b47; --acc:#FFBA24; --txt:#efeaf5; --dim:#9a90ad; }
* { box-sizing:border-box; }
body { margin:0; padding:32px 20px 60px; background:var(--bg); color:var(--txt);
  font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif; }
.wrap { max-width:1080px; margin:0 auto; }
h1 { font-size:26px; margin:0 0 4px; }
.meta { color:var(--dim); font-size:13px; margin-bottom:24px; }
.stats { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:28px; }
.stat { background:var(--card); border-radius:10px; padding:14px 18px; min-width:132px; }
.stat b { display:block; font-size:26px; color:var(--acc); }
.stat span { color:var(--dim); font-size:12px; }
section { background:var(--card); border-radius:12px; padding:18px 20px; margin-bottom:16px; }
h2 { font-size:17px; margin:0 0 12px; display:flex; align-items:center; gap:10px; }
.cnt { background:var(--acc); color:#2B223A; border-radius:20px; padding:1px 9px; font-size:13px; }
.sec { color:var(--dim); font-size:12px; text-transform:uppercase; letter-spacing:.04em; margin:14px 0 6px; }
.task { display:flex; gap:10px; align-items:baseline; padding:5px 0; border-bottom:1px solid rgba(255,255,255,.05); }
.task.done { opacity:.42; text-decoration:line-through; }
.task[data-file] { cursor:pointer; padding-left:6px; margin-left:-6px; border-radius:5px; }
.task[data-file]:hover { background:rgba(255,186,36,.09); }
.task[data-file]:focus-visible { outline:2px solid var(--acc); outline-offset:1px; }
.hint { background:rgba(255,186,36,.1); border-left:3px solid var(--acc); padding:9px 14px;
  border-radius:6px; margin-bottom:16px; font-size:13px; color:var(--dim); }
.routines { background:var(--card); border-radius:12px; padding:18px 20px; margin-bottom:16px;
  border-left:3px solid #6FD3A5; }
.rt { display:flex; gap:12px; align-items:baseline; padding:7px 0;
  border-bottom:1px solid rgba(255,255,255,.05); }
.rt:last-child { border-bottom:none; }
.rt[data-rfile] { cursor:pointer; padding-left:6px; margin-left:-6px; border-radius:5px; }
.rt[data-rfile]:hover { background:rgba(111,211,165,.1); }
.rt[data-rfile]:focus-visible { outline:2px solid #6FD3A5; outline-offset:1px; }
.rt .when { font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--dim);
  min-width:34px; }
.rt .note { color:var(--dim); font-size:12px; white-space:nowrap; }
.rt.due .when { color:#6FD3A5; font-weight:600; }
.rt.due .note { color:#6FD3A5; }
.routines .cnt { background:#6FD3A5; }
.focus { display:grid; grid-template-columns:1.35fr 1fr; gap:16px; margin-bottom:22px; }
.col { background:var(--card); border-radius:12px; padding:18px 20px; }
.col.main { border-top:3px solid var(--acc); }
.col.small { background:transparent; border:1px solid rgba(255,255,255,.09); }
.col h2 { font-size:16px; }
.colsub { color:var(--dim); font-size:12.5px; margin:-6px 0 12px; }
.col .task { padding:8px 0; }
.col.main .task .txt { font-size:15px; }
.empty { color:var(--dim); font-size:13px; padding:6px 0; }
.spill { color:var(--dim); font-size:12.5px; padding-top:10px; }
.allh { font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:var(--dim);
  font-weight:500; margin:26px 0 12px; }
@media (max-width:760px) { .focus { grid-template-columns:1fr; } }
.art { font-size:9px; line-height:1; }
.art.ok { color:#6FD3A5; }
.art.no { color:#7D7290; }
.trace { display:block; font-size:12.5px; color:var(--dim); text-decoration:none;
  padding-left:2px; margin-top:1px; }
.task.done .trace { text-decoration:none; opacity:.85; }
.mark { color:var(--acc); }
.txt { flex:1; }
.src { color:var(--dim); font-size:11px; white-space:nowrap; }
.att, .soon { background:rgba(255,186,36,.1); border-left:3px solid var(--acc);
  padding:10px 14px; border-radius:6px; margin-bottom:12px; font-size:14px; }
.att ul, .soon ul { margin:6px 0 0; padding-left:18px; }
@media (max-width:640px) { .src { display:none; } }

/* деньги */
.money { border-top:3px solid #6FD3A5; }
.mgrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; }
.mcell { background:rgba(255,255,255,.04); border-radius:9px; padding:12px 14px; }
.mcell b { display:block; font-size:20px; color:#6FD3A5; }
.mcell.total { background:rgba(111,211,165,.13); }
.mcell.total b { font-size:24px; }
.ml { display:block; font-size:12.5px; margin-top:2px; }
.mst { display:block; color:var(--dim); font-size:11.5px; margin-top:4px; }

/* блокеры */
.blockers { border-top:3px solid #E86A5C; }
.blockers .cnt { background:#E86A5C; color:#fff; }
.blk { display:flex; gap:12px; align-items:baseline; padding:7px 0;
  border-bottom:1px solid rgba(255,255,255,.05); flex-wrap:wrap; }
.blk:last-child { border-bottom:none; }
.bk { font-weight:600; min-width:210px; }
.bh { flex:1; color:var(--dim); font-size:13.5px; }
.bw { font-size:11.5px; color:#E8A05C; white-space:nowrap; }

/* чекпоинты */
.cps { border-top:3px solid var(--acc); }
.cp { display:flex; gap:12px; align-items:baseline; padding:7px 0;
  border-bottom:1px solid rgba(255,255,255,.05); }
.cp:last-child { border-bottom:none; }
.cpd { min-width:64px; font-weight:600; color:var(--dim); }
.cpt { flex:1; }
.cpn { display:block; color:var(--dim); font-size:12.5px; }
.cpl { font-size:11.5px; color:var(--dim); white-space:nowrap; }
.cp.soon .cpd, .cp.soon .cpl { color:var(--acc); }
.cp.over .cpd, .cp.over .cpl { color:#E86A5C; }

/* реестр */
.reg .rgrp { margin-bottom:10px; }
.rrow { display:flex; gap:12px; align-items:baseline; padding:5px 0;
  border-bottom:1px solid rgba(255,255,255,.05); }
.rrow:last-child { border-bottom:none; }
.rn { min-width:230px; font-size:14px; }
.rv { flex:1; color:var(--dim); font-size:13px; }
@media (max-width:700px) { .bk, .rn { min-width:100%; } }
"""

    script = SCRIPT if interactive else ""
    hint = HINT if interactive else ""
    return (
        '<!doctype html>\n<html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Доска волта — " + today + "</title><style>" + style + "</style></head><body><div class=\"wrap\">"
        "<h1>Доска волта</h1>"
        '<div class="meta">Сгенерировано ' + today
        + " · задача = незакрытый чекбокс в индексе проекта или в материалах practice</div>"
        '<div class="stats">'
        '<div class="stat"><b>' + str(total_open) + "</b><span>открытых задач</span></div>"
        '<div class="stat"><b>' + str(total_done) + "</b><span>закрыто</span></div>"
        '<div class="stat"><b>' + str(attention) + "</b><span>требует внимания</span></div>"
        "</div>" + hint + money + blockers + checkpoints + routines + external + focus + warn
        + '<h2 class="allh">Всё по проектам</h2>' + "".join(blocks)
        + registry + "</div>" + script + "</body></html>"
    )


def main() -> int:
    projects, upcoming = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(projects, upcoming), encoding="utf-8")
    total = sum(len(p.open_tasks) for p in projects.values())
    print("Доска собрана: " + OUT.relative_to(ROOT).as_posix() + " · открытых задач: " + str(total))
    if "--open" in sys.argv:
        webbrowser.open(OUT.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
