#!/usr/bin/env python3
"""Проверка качества живого слоя HyperCRM.

Проверка намеренно не создаёт отчётов внутри vault: результат живёт в stdout,
чтобы сама гигиена не превращалась в новый склад событий.

Проверяется:
- целостность внутренних Markdown-ссылок;
- просроченные активные гипотезы и закрытые гипотезы без результата;
- доказательства у движков и playbook'ов Marketing OS со статусом working/playbook;
- полнота канонического словаря и отсутствие плавающих терминов в рабочих модулях;
- владелец и статус у управляемых документов;
- детерминированные противоречия канону (замороженные источники в живых индексах,
  устаревшая неделя в текущем фокусе, экспорт замороженных сущностей);
- ссылки на приватные разделы из экспортируемого шаблона;
- срок годности (WARN): для файлов, на которые ссылаются активные индексы,
  порог по типу — решения 90 дн., клиентские материалы 45, планы 30. Явное поле
  `годен-до:` сильнее типа. Неклассифицированное по календарю не проверяется.
  Файл нужного типа вовсе без отметки — только в --strict;
- незаполненные таблицы в активных индексах (WARN).

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/vault/quality-check.py
    .tools/venv/Scripts/python.exe .tools/universal/vault/quality-check.py --strict
    .tools/venv/Scripts/python.exe .tools/universal/vault/quality-check.py --json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKIP_DIRS = {
    ".git",
    ".obsidian",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "outputs",
    "tmp",
}
FROZEN_PREFIXES = ("daily/", "reviews/", "recurring/")
FROZEN_MARKERS = ("/_archive/", "/backlog.md")
PRIVATE_ROOTS = {"life", "team", "daily", "reviews", "recurring"}
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
HYP_HEADING_RE = re.compile(r"(?m)^###\s+(HYP-[^|\n]+)\s*\|\s*(20\d{2}-\d{2}-\d{2})\s*\|\s*Статус:\s*([^\n]+)")
FIELD_RE_TEMPLATE = r"(?mi)^\*\*{name}:\*\*\s*(.*)$"
EMPTY_MARKERS = ("заполнить", "позже", "—", "-", "нет данных", "ожидается")
ACTIVE_STATUS_MARKERS = ("🧪", "тест", "провер", "pilot", "active")
CLOSED_STATUS_MARKERS = ("✅", "❌", "сработ", "не сработ", "закрыт", "заверш")
INACTIVE_STATUS_MARKERS = ("⏸", "📦", "💡", "archiv", "отлож", "пауза", "сырая идея")
GLOSSARY_PATH = ROOT / "marketing-os" / "core" / "glossary.md"
GLOSSARY_CARD_RE = re.compile(
    r'(?ms)^<a id="(term-[a-z0-9-]+)"></a>\s*\n###\s+([^\n]+)\n(.*?)(?=^<a id="term-|\Z)'
)
GLOSSARY_REQUIRED_FIELDS = ("Aliases", "Определение", "Зачем", "Не путать")
GLOSSARY_REQUIRED_ALIASES = {
    "marketing os", "opf", "full business diagnostic", "local high-ticket service",
    "capacity", "unit economics", "ца", "icp", "лпр", "кфв", "утп",
    "rdb", "aarrr", "value equation", "crm", "sla", "utm", "kpi",
    "proof", "evidence", "push", "pull", "anxiety", "habit",
    "jtbd", "voc", "cjm", "cta", "follow-up", "playbook",
    "scorecard", "cpl", "cac", "ltv", "ctr", "cpm", "cpv", "er",
    "cpo", "nps", "дрр", "contribution margin",
}
TERM_DRIFT_RE = re.compile(
    r"(?i)(?<![\w-])(proof|evidence|push|pull|anxiety|habit|follow-up)(?![\w-])"
)
TERM_RUSSIAN_NAMES = {
    "proof": "доказательство для клиента",
    "evidence": "доказательство метода",
    "push": "давление текущей ситуации",
    "pull": "притяжение результата",
    "anxiety": "тревога перехода",
    "habit": "инерция текущего способа",
    "follow-up": "дожим по контексту",
}


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    file: str
    line: int
    message: str


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_frozen(path: Path) -> bool:
    value = rel(path)
    return (
        value.startswith(FROZEN_PREFIXES)
        or any(marker in f"/{value}" for marker in FROZEN_MARKERS)
        or value == "tasks.md"
    )


def iter_markdown():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            path = Path(dirpath) / name
            if not is_frozen(path):
                yield path


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def mask_noncontent(text: str) -> str:
    """Скрывает комментарии и fenced-code, сохраняя длину и номера строк."""

    def mask(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    text = re.sub(r"<!--.*?-->", mask, text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", mask, text, flags=re.DOTALL)
    return re.sub(r"`[^`\n]+`", mask, text)


def visible_markdown(text: str) -> str:
    """Убирает цели ссылок, оставляя только видимый пользователю текст."""

    text = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", text)

    def wiki_label(match: re.Match[str]) -> str:
        target, label = match.groups()
        return label or Path(target).stem

    return re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]", wiki_label, text)


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def clean_link(raw: str) -> str:
    value = urllib.parse.unquote(raw.strip().strip("<>"))
    if " " in value and not value.startswith(("http://", "https://")):
        # Markdown допускает title после пути: (file.md "title").
        value = value.split(" ", 1)[0]
    return value.split("#", 1)[0].split("?", 1)[0]


def resolve_link(source: Path, raw: str, wiki: bool = False) -> Path | None:
    value = clean_link(raw)
    if not value or value.startswith(("http://", "https://", "mailto:", "data:")):
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    target = (source.parent / candidate).resolve()
    if wiki and not target.suffix:
        target = target.with_suffix(".md")
    return target


def check_links() -> list[Issue]:
    issues: list[Issue] = []
    for path in iter_markdown():
        text = mask_noncontent(read(path))
        for regex, wiki in ((MARKDOWN_LINK_RE, False), (WIKI_LINK_RE, True)):
            for match in regex.finditer(text):
                raw = match.group(1)
                target = resolve_link(path, raw, wiki)
                if target is None:
                    continue
                # Ссылки без расширения в обычном Markdown часто являются URL-схемой
                # или якорем; проверяем только явно файловые цели.
                if not wiki and not Path(clean_link(raw)).suffix:
                    continue
                if not target.exists():
                    issues.append(Issue(
                        "ERROR",
                        "BROKEN_LINK",
                        rel(path),
                        line_of(text, match.start()),
                        f"нет цели: {raw}",
                    ))
    return issues


def field_value(block: str, *names: str) -> str | None:
    for name in names:
        match = re.search(FIELD_RE_TEMPLATE.format(name=re.escape(name)), block)
        if match:
            return match.group(1).strip()
    return None


def meaningful(value: str | None) -> bool:
    if value is None:
        return False
    clean = value.strip().lower().strip(".()")
    return bool(clean) and not any(clean == marker or clean.startswith(marker) for marker in EMPTY_MARKERS)


def check_hypotheses(today: dt.date) -> list[Issue]:
    issues: list[Issue] = []
    for path in iter_markdown():
        if path.name != "hypotheses.md":
            continue
        text = mask_noncontent(read(path))
        matches = list(HYP_HEADING_RE.finditer(text))
        for index, match in enumerate(matches):
            block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[match.start():block_end]
            hyp_id, created_raw, status = match.groups()
            created = dt.date.fromisoformat(created_raw)
            status_lower = status.lower()
            result = field_value(block, "Результат", "Ретроспектива")
            conclusion = field_value(block, "Вывод")
            checkpoint = field_value(block, "Срок проверки", "Чекпоинт")
            checkpoint_dates = [dt.date.fromisoformat(raw) for raw in DATE_RE.findall(checkpoint or "")]
            inactive = any(marker in status_lower for marker in INACTIVE_STATUS_MARKERS)
            active = not inactive and any(marker in status_lower for marker in ACTIVE_STATUS_MARKERS)
            closed = any(marker in status_lower for marker in CLOSED_STATUS_MARKERS)
            line = line_of(text, match.start())

            if closed and not meaningful(result):
                issues.append(Issue(
                    "ERROR", "HYP_CLOSED_NO_RESULT", rel(path), line,
                    f"{hyp_id.strip()}: закрыта, но поле «Результат» пустое",
                ))
            if closed and not meaningful(conclusion):
                issues.append(Issue(
                    "ERROR", "HYP_CLOSED_NO_CONCLUSION", rel(path), line,
                    f"{hyp_id.strip()}: закрыта, но поле «Вывод» пустое",
                ))
            if active and checkpoint_dates and max(checkpoint_dates) < today and not meaningful(result):
                issues.append(Issue(
                    "ERROR", "HYP_OVERDUE", rel(path), line,
                    f"{hyp_id.strip()}: последний checkpoint {max(checkpoint_dates)}, результата нет",
                ))
            if active and not checkpoint_dates:
                issues.append(Issue(
                    "ERROR", "HYP_NO_EXACT_CHECKPOINT", rel(path), line,
                    f"{hyp_id.strip()}: активна без checkpoint в YYYY-MM-DD",
                ))
    return issues


def metadata_value(text: str, name: str) -> str | None:
    match = re.search(FIELD_RE_TEMPLATE.format(name=re.escape(name)), text)
    if match:
        return match.group(1).strip()
    inline_heading = re.search(rf"(?mi)^##\s+{re.escape(name)}:\s*(.+)$", text)
    if inline_heading:
        return inline_heading.group(1).strip()
    heading = re.search(rf"(?mi)^##\s+{re.escape(name)}\s*$\n+([^\n]+)", text)
    return heading.group(1).strip() if heading else None


def governed_documents() -> list[Path]:
    marketing_os = ROOT / "marketing-os"
    paths = []
    for folder in ("engines", "playbooks"):
        paths.extend((marketing_os / folder).glob("*.md"))
    for path in (ROOT / "projects").rglob("_index.md"):
        if "_archive" not in path.parts:
            paths.append(path)
    if GLOSSARY_PATH.exists():
        paths.append(GLOSSARY_PATH)
    return sorted(set(paths))


def check_project_indexes() -> list[Issue]:
    issues: list[Issue] = []
    projects = ROOT / "projects"
    for directory in projects.iterdir():
        if not directory.is_dir() or directory.name.startswith("_"):
            continue
        index = directory / "_index.md"
        if not index.exists():
            issues.append(Issue(
                "ERROR", "PROJECT_NO_INDEX", rel(directory), 1,
                "активный каталог верхнего уровня без _index.md",
            ))
    return issues


def check_governed_documents() -> list[Issue]:
    issues: list[Issue] = []
    for path in governed_documents():
        text = read(path)
        for field in ("Статус", "Владелец"):
            if not meaningful(metadata_value(text, field)):
                issues.append(Issue(
                    "ERROR", f"DOC_NO_{'STATUS' if field == 'Статус' else 'OWNER'}",
                    rel(path), 1, f"управляемый документ без поля «{field}»",
                ))
    return issues


def check_module_evidence() -> list[Issue]:
    issues: list[Issue] = []
    marketing_os = ROOT / "marketing-os"
    documents = []
    for folder in ("engines", "playbooks"):
        documents.extend((marketing_os / folder).glob("*.md"))
    for path in documents:
        text = read(path)
        status = (metadata_value(text, "Статус") or "").lower()
        if not (status.startswith("working") or status.startswith("playbook")):
            continue
        evidence_match = re.search(r"(?mi)^##\s+(Доказательства|Результаты применения)\s*$", text)
        if not evidence_match:
            issues.append(Issue(
                "ERROR", "MODULE_NO_EVIDENCE", rel(path), 1,
                f"статус {status!r}, но нет раздела «Доказательства»",
            ))
            continue
        evidence = text[evidence_match.end():]
        next_heading = re.search(r"(?m)^##\s+", evidence)
        if next_heading:
            evidence = evidence[:next_heading.start()]
        links = MARKDOWN_LINK_RE.findall(evidence)
        if not links:
            issues.append(Issue(
                "ERROR", "MODULE_EVIDENCE_NO_LINK", rel(path),
                line_of(text, evidence_match.start()), "в доказательствах нет ссылки на кейс/результат",
            ))
        if status.startswith("playbook") and len(links) < 2:
            issues.append(Issue(
                "ERROR", "PLAYBOOK_NOT_REPEATED", rel(path),
                line_of(text, evidence_match.start()), "playbook требует минимум 2 связанных применений",
            ))
    return issues


def glossary_field(block: str, name: str) -> str | None:
    match = re.search(rf"(?mi)^-\s+\*\*{re.escape(name)}:\*\*\s*(.+)$", block)
    return match.group(1).strip() if match else None


def terminology_documents() -> list[Path]:
    marketing_os = ROOT / "marketing-os"
    paths = [marketing_os / "_index.md"]
    for folder in ("engines", "routes", "playbooks", "templates", "maps", "product", "systems"):
        base = marketing_os / folder
        if base.exists():
            paths.extend(base.rglob("*.md"))
    evidence_bank = marketing_os / "evidence" / "one-product-flow-proof-bank.md"
    if evidence_bank.exists():
        paths.append(evidence_bank)
    skills = ROOT / ".claude" / "skills"
    if skills.exists():
        paths.extend(skills.rglob("SKILL.md"))
    return sorted({path for path in paths if path.exists() and "_archive" not in path.parts})


def check_terminology() -> list[Issue]:
    issues: list[Issue] = []
    if not GLOSSARY_PATH.exists():
        return [Issue(
            "ERROR", "GLOSSARY_MISSING", rel(GLOSSARY_PATH), 1,
            "нет канонического словаря Marketing OS",
        )]

    text = read(GLOSSARY_PATH)
    cards = list(GLOSSARY_CARD_RE.finditer(text))
    if len(cards) < 80:
        issues.append(Issue(
            "ERROR", "GLOSSARY_TOO_SMALL", rel(GLOSSARY_PATH), 1,
            f"найдено {len(cards)} карточек; ожидается не меньше 80",
        ))

    anchors: set[str] = set()
    titles: set[str] = set()
    aliases: dict[str, str] = {}
    for card in cards:
        anchor, title, block = card.groups()
        line = line_of(text, card.start())
        title_key = title.strip().casefold()
        if anchor in anchors:
            issues.append(Issue(
                "ERROR", "GLOSSARY_DUPLICATE_ANCHOR", rel(GLOSSARY_PATH), line,
                f"повторяется якорь {anchor}",
            ))
        anchors.add(anchor)
        if title_key in titles:
            issues.append(Issue(
                "ERROR", "GLOSSARY_DUPLICATE_TERM", rel(GLOSSARY_PATH), line,
                f"повторяется каноническое имя «{title.strip()}»",
            ))
        titles.add(title_key)

        for field in GLOSSARY_REQUIRED_FIELDS:
            value = glossary_field(block, field)
            if not meaningful(value):
                issues.append(Issue(
                    "ERROR", "GLOSSARY_INCOMPLETE_CARD", rel(GLOSSARY_PATH), line,
                    f"у термина «{title.strip()}» нет содержательного поля «{field}»",
                ))

        alias_value = glossary_field(block, "Aliases") or ""
        for raw_alias in alias_value.split(","):
            alias = raw_alias.strip().strip("`.* ").casefold()
            if not alias:
                continue
            previous = aliases.get(alias)
            if previous and previous != anchor:
                issues.append(Issue(
                    "ERROR", "GLOSSARY_ALIAS_COLLISION", rel(GLOSSARY_PATH), line,
                    f"alias «{alias}» назначен и {previous}, и {anchor}",
                ))
            else:
                aliases[alias] = anchor

    for alias in sorted(GLOSSARY_REQUIRED_ALIASES - aliases.keys()):
        issues.append(Issue(
            "ERROR", "GLOSSARY_REQUIRED_ALIAS_MISSING", rel(GLOSSARY_PATH), 1,
            f"нет обязательного alias «{alias}»",
        ))

    navigation_end = text.find("\n## Границы системы")
    navigation = text[:navigation_end] if navigation_end != -1 else ""
    navigation_anchors = set(re.findall(r"\(#(term-[a-z0-9-]+)\)", navigation))
    for anchor in sorted(anchors - navigation_anchors):
        issues.append(Issue(
            "ERROR", "GLOSSARY_TERM_NOT_IN_NAV", rel(GLOSSARY_PATH), 1,
            f"карточка {anchor} отсутствует в навигации словаря",
        ))
    for anchor in sorted(navigation_anchors - anchors):
        issues.append(Issue(
            "ERROR", "GLOSSARY_NAV_TARGET_MISSING", rel(GLOSSARY_PATH), 1,
            f"навигация ссылается на отсутствующую карточку {anchor}",
        ))

    references = (ROOT / "CLAUDE.md", ROOT / "marketing-os" / "_index.md")
    for path in references:
        if path.exists() and "core/glossary.md" not in read(path):
            issues.append(Issue(
                "ERROR", "GLOSSARY_NOT_CANONICAL", rel(path), 1,
                "документ не назначает core/glossary.md каноническим словарём",
            ))

    for path in terminology_documents():
        content = mask_noncontent(visible_markdown(read(path)))
        for match in TERM_DRIFT_RE.finditer(content):
            alias = match.group(1).casefold()
            issues.append(Issue(
                "ERROR", "NONCANONICAL_TERM", rel(path), line_of(content, match.start()),
                f"«{match.group(1)}» вне словаря; используй «{TERM_RUSSIAN_NAMES[alias]}»",
            ))
    return issues


CHECKED_RE = re.compile(r"(?mi)^\*\*Проверено:\*\*\s*(20\d{2}-\d{2}-\d{2})")
WRITTEN_RE = re.compile(r"(?m)^дата:\s*(20\d{2}-\d{2}-\d{2})")
EXPIRES_RE = re.compile(r"(?mi)^годен-до:\s*(20\d{2}-\d{2}-\d{2})")
TABLE_ROW_RE = re.compile(r"(?m)^\|(.+)\|\s*$")
STALE_AFTER_DAYS = 45

# Срок годности вместо даты написания.
#
# Поле «Проверено» стояло у 9 файлов из 400 — проверка следила за 2% волта, и
# всё остальное протухало невидимо (инфобиз-дашборд врал два с половиной месяца).
# Расширяем не на всё разом: 400 предупреждений — это шум, который начинают
# игнорировать, и проверка умирает как инструмент.
#
# Область — файлы, на которые ссылаются активные индексы: то, что реально читают.
# Порог — по типу файла; неклассифицированное не проверяется вовсе, потому что
# у скрипта звонка или брифа нет срока годности по календарю: он устаревает
# вместе с процессом, а не от возраста.
FRESHNESS_SEEDS = ("projects/*/_index.md", "life/decisions.md", "life/finance/_index.md")
DECISION_FILES = {
    "decisions.md", "model.md", "market.md", "positioning.md",
    "personal-brand-strategy.md", "glossary.md", "club.md", "offer-soprovozhdenie.md",
}
PLAN_NAME_RE = re.compile(r"(?i)(^|[-_])(plan|roadmap|finmodel)([-_.]|$)")
PLAN_FILES = {"_index.md", "_dashboard.md"}
FRESHNESS_RULES = {"решение": 90, "клиентский материал": 45, "план": 30}


def freshness_kind(path: Path) -> str | None:
    """Тип файла для срока годности. None — по календарю не проверяем."""
    posix = path.as_posix()
    name = path.name.lower()
    if name in DECISION_FILES:
        return "решение"
    if "/marketing-os/" in posix:
        # Метод не протухает по календарю: маршрут устаревает, когда меняется
        # способ работы, а не когда прошло тридцать дней. Свежесть модулей
        # Marketing OS проверяется своими правилами — доказательствами и словарём.
        return None
    if "/clients/" in posix:
        return "клиентский материал"
    if name in PLAN_FILES or PLAN_NAME_RE.search(path.stem):
        return "план"
    return None


def freshness_scope() -> set[Path]:
    """Активные индексы и всё, на что они ссылаются напрямую.

    Один хоп, а не обход всего графа: то, до чего от индекса три перехода,
    в работе не открывают, и напоминать про его свежесть — производить шум.
    """
    seeds = []
    for pattern in FRESHNESS_SEEDS:
        seeds.extend(p for p in ROOT.glob(pattern) if p.exists())
    scope = set(seeds)
    for seed in seeds:
        text = mask_noncontent(read(seed))
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group(1).split("#")[0].strip()
            if not target or target.startswith(("http", "mailto:")):
                continue
            resolved = (seed.parent / urllib.parse.unquote(target)).resolve()
            if resolved.suffix == ".md" and resolved.exists() and "_archive" not in resolved.parts:
                scope.add(resolved)
    return scope


def check_expiry(today: dt.date, strict: bool) -> list[Issue]:
    issues: list[Issue] = []
    for path in sorted(freshness_scope()):
        if is_frozen(path):
            continue
        text = mask_noncontent(read(path))
        status = (metadata_value(text, "Статус") or "").lower()
        if status.startswith(("retired", "frozen", "архив")):
            continue

        # Явный срок годности сильнее типа: файл сам сказал, когда протухнет.
        explicit = EXPIRES_RE.search(text)
        if explicit:
            due = dt.date.fromisoformat(explicit.group(1))
            if today > due:
                issues.append(Issue(
                    "WARN", "EXPIRED", rel(path), line_of(text, explicit.start()),
                    f"срок годности вышел {(today - due).days} дн. назад",
                ))
            continue

        kind = freshness_kind(path)
        if kind is None:
            continue
        limit = FRESHNESS_RULES[kind]

        checked = CHECKED_RE.search(text)
        if checked:
            age = (today - dt.date.fromisoformat(checked.group(1))).days
            if age > limit:
                issues.append(Issue(
                    "WARN", "STALE_CHECKED", rel(path), line_of(text, checked.start()),
                    f"{kind}: проверено {age} дн. назад при пороге {limit}",
                ))
            continue

        written = WRITTEN_RE.search(text)
        if written:
            age = (today - dt.date.fromisoformat(written.group(1))).days
            if age > limit:
                issues.append(Issue(
                    "WARN", "STALE_WRITTEN", rel(path), line_of(text, written.start()),
                    f"{kind}: написан {age} дн. назад, отметки проверки нет",
                ))
            continue

        # Нет ни отметки проверки, ни даты — судить не по чему. Это долг разметки,
        # а не протухание, поэтому только в --strict: иначе обычный прогон
        # захлебнётся файлами, про которые нечего сказать.
        if strict:
            issues.append(Issue(
                "WARN", "NO_CHECK_MARK", rel(path), 1,
                f"{kind} без отметки «**Проверено:**» — срок годности не с чем сверить",
            ))
    return issues


def check_freshness(today: dt.date) -> list[Issue]:
    """Незаполненные таблицы в активных индексах — форма, которую завели и бросили.

    Свежесть сама по себе живёт в check_expiry: у неё своя область и пороги по типу.
    """
    issues: list[Issue] = []
    for path in (ROOT / "projects").rglob("_index.md"):
        if "_archive" in path.parts or is_frozen(path):
            continue
        text = mask_noncontent(read(path))
        status = (metadata_value(text, "Статус") or "").lower()
        if status.startswith(("retired", "frozen", "архив")):
            continue

        # Таблица, у которой все строки данных пустые, — незаполненная форма.
        rows = list(TABLE_ROW_RE.finditer(text))
        block: list[re.Match[str]] = []
        for index, row in enumerate(rows + [None]):
            contiguous = row is not None and (not block or text.count("\n", block[-1].end(), row.start()) <= 1)
            if contiguous:
                block.append(row)
                continue
            if len(block) >= 3:
                data = [m for m in block[2:]]
                if data and all(not cell.strip() for m in data for cell in m.group(1).split("|")):
                    issues.append(Issue(
                        "WARN", "EMPTY_TABLE", rel(path), line_of(text, block[0].start()),
                        f"таблица из {len(data)} строк не заполнена",
                    ))
            block = [row] if row is not None else []
    return issues


def check_canonical_consistency(today: dt.date) -> list[Issue]:
    issues: list[Issue] = []

    # В живых индексах нельзя использовать замороженные журналы как актуальный источник.
    frozen_source_re = re.compile(r"(?i)(?:`|\]\()([^\n`)]*(?:tasks\.md|daily/|reviews/|recurring/tasks\.md)[^\n`)]*)")
    for path in (ROOT / "projects").glob("*/_index.md"):
        if "_archive" in path.parts:
            continue
        text = read(path)
        for match in frozen_source_re.finditer(text):
            issues.append(Issue(
                "ERROR", "INDEX_USES_FROZEN_SOURCE", rel(path), line_of(text, match.start()),
                f"живой индекс использует замороженный источник: {match.group(1).strip()}",
            ))

        focus = re.search(r"(?mis)^##\s+Текущий фокус\s*$\n(.*?)(?=^##\s+|\Z)", text)
        if focus:
            current_week = today.isocalendar().week
            for week_match in re.finditer(r"\bW(\d{1,2})\b", focus.group(1)):
                week = int(week_match.group(1))
                if current_week - week > 2:
                    issues.append(Issue(
                        "ERROR", "INDEX_STALE_FOCUS", rel(path),
                        line_of(text, focus.start(1) + week_match.start()),
                        f"текущий фокус всё ещё ссылается на W{week}; сейчас W{current_week}",
                    ))

    export_rules = ROOT / "system" / "export-rules" / "access-levels.md"
    text = read(export_rules)
    level3 = text.split("## Уровень 3", 1)[1] if "## Уровень 3" in text else ""
    match = re.search(r"recurring/tasks\.md", level3)
    if match:
        offset = text.find("## Уровень 3") + match.start()
        issues.append(Issue(
            "ERROR", "EXPORT_CONTRADICTS_CANON", rel(export_rules), line_of(text, offset),
            "экспорт предлагает замороженный recurring/tasks.md",
        ))
    return issues


def exportable_files() -> list[Path]:
    paths = [ROOT / "CLAUDE.md", ROOT / "README.md"]
    for base in (ROOT / "system" / "templates", ROOT / "knowledge"):
        if base.exists():
            paths.extend(base.rglob("*.md"))
    marketing_os = ROOT / "marketing-os"
    for folder in ("core", "engines", "routes", "playbooks", "templates", "maps", "product", "systems"):
        base = marketing_os / folder
        if base.exists():
            paths.extend(base.rglob("*.md"))
    return [path for path in paths if path.exists()]


def check_private_export_links() -> list[Issue]:
    issues: list[Issue] = []
    for path in exportable_files():
        text = read(path)
        for regex, wiki in ((MARKDOWN_LINK_RE, False), (WIKI_LINK_RE, True)):
            for match in regex.finditer(text):
                target = resolve_link(path, match.group(1), wiki)
                if target is None:
                    continue
                try:
                    target_rel = target.relative_to(ROOT)
                except ValueError:
                    continue
                if target_rel.parts and target_rel.parts[0] in PRIVATE_ROOTS:
                    issues.append(Issue(
                        "ERROR", "PRIVATE_LINK_IN_EXPORT", rel(path), line_of(text, match.start()),
                        f"экспортируемый файл ссылается на приватное: {match.group(1)}",
                    ))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="warnings также дают ненулевой exit code")
    parser.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    parser.add_argument("--today", help="дата проверки YYYY-MM-DD (для тестов)")
    args = parser.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    issues = []
    issues.extend(check_links())
    issues.extend(check_hypotheses(today))
    issues.extend(check_module_evidence())
    issues.extend(check_terminology())
    issues.extend(check_project_indexes())
    issues.extend(check_governed_documents())
    issues.extend(check_freshness(today))
    issues.extend(check_expiry(today, args.strict))
    issues.extend(check_canonical_consistency(today))
    issues.extend(check_private_export_links())
    issues.sort(key=lambda item: (item.severity != "ERROR", item.code, item.file, item.line))

    if args.json:
        print(json.dumps({
            "date": today.isoformat(),
            "issues": [asdict(issue) for issue in issues],
            "summary": {
                "errors": sum(issue.severity == "ERROR" for issue in issues),
                "warnings": sum(issue.severity == "WARN" for issue in issues),
            },
        }, ensure_ascii=False, indent=2))
    else:
        for issue in issues:
            print(f"[{issue.severity}] {issue.code} {issue.file}:{issue.line} — {issue.message}")
        errors = sum(issue.severity == "ERROR" for issue in issues)
        warnings = sum(issue.severity == "WARN" for issue in issues)
        print(f"\nПроверка {today}: ошибок {errors}, предупреждений {warnings}")

    has_errors = any(issue.severity == "ERROR" for issue in issues)
    has_warnings = any(issue.severity == "WARN" for issue in issues)
    return 1 if has_errors or (args.strict and has_warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
