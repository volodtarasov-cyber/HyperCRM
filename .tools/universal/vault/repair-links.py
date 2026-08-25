#!/usr/bin/env python3
"""Консервативный ремонт внутренних ссылок vault.

По умолчанию показывает план. С ``--apply``:
- перевязывает ссылку, если найден ровно один живой файл с тем же именем;
  архивный дубль не перебивает текущий канон;
- снимает ссылочную разметку, если цели больше нет, сохраняя видимый текст;
- для утраченной картинки оставляет явную текстовую пометку.

Содержимое отсутствующих файлов не восстанавливает и новые заглушки не создаёт.
Замороженные документы не изменяет.
"""

from __future__ import annotations

import argparse
import os
import re
import urllib.parse
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKIP_DIRS = {".git", ".obsidian", "node_modules", "venv", ".venv", "__pycache__", "outputs", "tmp"}
FROZEN_PREFIXES = ("daily/", "reviews/", "recurring/")
MARKDOWN_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
WIKI_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_frozen(path: Path) -> bool:
    value = relative(path)
    return (
        value.startswith(FROZEN_PREFIXES)
        or "/_archive/" in f"/{value}"
        or value.endswith("/backlog.md")
        or value == "tasks.md"
    )


def walk_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def clean_target(raw: str) -> str:
    value = urllib.parse.unquote(raw.strip().strip("<>"))
    if " " in value and not value.startswith(("http://", "https://")):
        value = value.split(" ", 1)[0]
    return value.split("#", 1)[0].split("?", 1)[0]


def resolve(source: Path, raw: str, wiki: bool = False) -> Path | None:
    value = clean_target(raw)
    if not value or value.startswith(("http://", "https://", "mailto:", "data:")):
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    target = (source.parent / candidate).resolve()
    if wiki and not target.suffix:
        target = target.with_suffix(".md")
    return target


def replacement_path(source: Path, target: Path) -> str:
    return os.path.relpath(target, source.parent).replace(os.sep, "/")


def unique_live_candidate(candidates: list[Path]) -> Path | None:
    """Предпочитает единственную цель в живом слое архивным дублям."""
    live = [path for path in candidates if not is_frozen(path)]
    if len(live) == 1:
        return live[0]
    if not live and len(candidates) == 1:
        return candidates[0]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="записать исправления")
    args = parser.parse_args()

    files = list(walk_files())
    by_name: dict[str, list[Path]] = defaultdict(list)
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        by_name[path.name.lower()].append(path)
        if path.suffix.lower() == ".md":
            by_stem[path.stem.lower()].append(path)

    changed_files = 0
    retargeted = 0
    unlinked = 0

    for source in files:
        if source.suffix.lower() != ".md" or is_frozen(source):
            continue
        try:
            original = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        def replace_markdown(match: re.Match[str]) -> str:
            nonlocal retargeted, unlinked
            image, label, raw = match.groups()
            target = resolve(source, raw)
            if target is None or target.exists():
                return match.group(0)
            clean = clean_target(raw)
            candidates = by_name.get(Path(clean).name.lower(), [])
            candidate = unique_live_candidate(candidates)
            if candidate is not None:
                retargeted += 1
                return f"{image}[{label}]({replacement_path(source, candidate)})"
            unlinked += 1
            return f"[Утраченная иллюстрация: {label or Path(clean).name}]" if image else label

        def replace_wiki(match: re.Match[str]) -> str:
            nonlocal retargeted, unlinked
            raw, alias = match.groups()
            target = resolve(source, raw, wiki=True)
            if target is None or target.exists():
                return match.group(0)
            clean = clean_target(raw)
            key = Path(clean).stem.lower()
            candidates = by_stem.get(key, [])
            candidate = unique_live_candidate(candidates)
            if candidate is not None:
                retargeted += 1
                link = replacement_path(source, candidate)
                if link.endswith(".md"):
                    link = link[:-3]
                return f"[[{link}|{alias}]]" if alias else f"[[{link}]]"
            unlinked += 1
            return alias or Path(clean).name

        updated = MARKDOWN_RE.sub(replace_markdown, original)
        updated = WIKI_RE.sub(replace_wiki, updated)
        if updated == original:
            continue
        changed_files += 1
        print(relative(source))
        if args.apply:
            source.write_text(updated, encoding="utf-8")

    mode = "изменено" if args.apply else "будет изменено"
    print(f"\nФайлов {mode}: {changed_files}; перевязок: {retargeted}; снято мёртвых ссылок: {unlinked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
