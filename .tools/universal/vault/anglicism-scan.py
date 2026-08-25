"""
Скан англицизмов в живом слое волта.

Ищет латинские слова в рабочем тексте .md, отбрасывая то, где английский
законен: код, ссылки, пути, frontmatter-ключи. Остальное группирует по
частоте, чтобы отделить канон (CPL, JTBD) и имена собственные (Telegram)
от протёкших англицизмов вроде guard-rail.

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/vault/anglicism-scan.py [--all]

Без флага показывает только НЕизвестные слова (кандидаты в англицизмы).
С --all — полный частотный список, включая разрешённые.
"""

import io
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

SKIP_DIRS = {".git", ".obsidian", "venv", "node_modules", "snapshots",
             "carousel-out", "cards-out", "skill-build", "_archive"}

# Английский здесь законен: канонические аббревиатуры метрик и методов
CANON = {
    "cpl", "cac", "ltv", "ctr", "cpm", "cpv", "cpo", "cpa", "er", "nps", "roi",
    "romi", "drr", "aarrr", "jtbd", "rdb", "seo", "smm", "crm", "utm", "sla",
    "kpi", "b2b", "b2c", "lal", "mvp", "tov", "usp", "abc", "pnl", "gmv", "arpu",
    "hyp", "opf", "os", "id", "ok", "ux", "ui", "faq", "cta", "ab", "ai",
}

# Имена собственные, продукты, технологии
PROPER = {
    "marketing", "one", "product", "flow", "music", "bingo", "wowloto",
    "google", "sheets", "drive", "calendar", "docs", "telegram", "instagram",
    "facebook", "youtube", "tiktok", "vk", "yandex", "playwright", "python",
    "claude", "anthropic", "github", "markdown", "html", "css", "json", "yaml",
    "csv", "pdf", "png", "jpg", "jpeg", "svg", "md", "py", "url", "api", "sdk",
    "mcp", "excel", "notion", "obsidian", "yougile", "hormozi", "schwartz",
    "kassir", "kudago", "timepad", "everygo", "afishagoroda", "gis", "smr",
    "samara", "lazyhim", "ppf", "kp", "dj", "vip", "the", "and", "of", "in",
    "for", "to", "is", "it", "no", "on", "at", "by", "as", "we", "you",
}

# Товарные линейки, марки, отраслевой жаргон — не термины метода
TRADE = {
    "quantum", "rocket", "optimal", "light", "premium", "llumar", "body",
    "bmw", "mercedes", "audi", "toyota", "lexus", "kia", "hyundai", "haval",
    "chery", "geely", "exeed", "omoda", "tank", "gac", "changan", "jetour",
    "porsche", "volkswagen", "skoda", "nissan", "mazda", "honda", "ford",
    "goodzone", "youco", "levsha", "unisec", "ananas", "tilda", "avito",
    "wordstat", "vpn", "meta", "vc", "whatsapp", "max", "tg", "pdr", "pnl",
    "detailing", "traffic", "infobiz", "agency", "life", "system", "team",
    "core", "index", "readme", "template", "draft", "pilot", "working",
    "retired", "playbook", "evidence", "sources", "applications", "engines",
    "routes", "maps", "systems", "templates", "product", "content", "web",
    "analytics", "exports", "documents", "aliases", "owner", "status",
}

ALLOWED = CANON | PROPER | TRADE

# Файлы, англоязычные по замыслу
SKIP_FILES = {"CLAUDE.md"}

# ID-коды вида TASK-DET-026, CRE-02, HYP-BNG-06
ID_CODE = re.compile(r"\b[A-Z]{2,5}(?:-[A-Z0-9]{1,6}){1,3}\b")

WORD = re.compile(r"[A-Za-z][A-Za-z\-']{1,}")


def strip_noise(text):
    """Убираем всё, где латиница законна по природе."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)      # frontmatter
    text = re.sub(r"```.*?```", " ", text, flags=re.S)            # блоки кода
    text = re.sub(r"`[^`]*`", " ", text)                          # инлайн-код
    text = re.sub(r"\]\([^)]*\)", "]( )", text)                   # цели ссылок
    text = re.sub(r"https?://\S+", " ", text)                     # голые URL
    text = re.sub(r"\b[\w./-]+\.(md|py|csv|png|html|json|js)\b", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)                          # html-теги
    return text


def main():
    show_all = "--all" in sys.argv
    counts = Counter()
    where = defaultdict(set)
    examples = {}

    for path in ROOT.rglob("*.md"):
        if any(p in SKIP_DIRS for p in path.parts):
            continue
        try:
            raw = io.open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        clean = strip_noise(raw)
        rel = path.relative_to(ROOT).as_posix()
        for m in WORD.finditer(clean):
            w = m.group(0)
            key = w.lower().strip("-'")
            if len(key) < 2:
                continue
            if not show_all and key in ALLOWED:
                continue
            counts[key] += 1
            where[key].add(rel)
            if key not in examples:
                s = max(0, m.start() - 45)
                examples[key] = " ".join(clean[s:m.end() + 45].split())

    print(f"Просканировано файлов живого слоя: "
          f"{len({f for s in where.values() for f in s})}")
    print(f"Уникальных латинских слов вне белого списка: {len(counts)}\n")
    print(f"{'слово':<22} {'раз':>4} {'файлов':>7}  где / пример")
    print("-" * 110)
    for w, c in counts.most_common(60):
        files = sorted(where[w])
        loc = files[0] if len(files) == 1 else f"{len(files)} файлов"
        print(f"{w:<22} {c:>4} {len(files):>7}  {loc}")
        if c >= 3 or len(files) > 1:
            print(f"{'':<36}  …{examples[w]}…")


if __name__ == "__main__":
    main()
