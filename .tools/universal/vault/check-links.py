#!/usr/bin/env python3
"""
Проверка целостности внутренних ссылок волта.

Ходит по всем .md, берёт относительные ссылки на файлы (.md, .csv, .html,
.png, .txt, .srt) и проверяет, что цель существует. URL-кодирование в путях
(%20, %23) разворачивается — иначе кириллические имена дают ложные поломки.

Замороженные разделы (daily/, reviews/, _archive/, tasks.md, backlog) по
умолчанию пропускаются: они не поддерживаются по правилу CLAUDE.md, и их
поломки смешиваются с реальными.

Запуск:
    .tools/venv/Scripts/python.exe .tools/universal/vault/check-links.py
    .tools/venv/Scripts/python.exe .tools/universal/vault/check-links.py --all
    .tools/venv/Scripts/python.exe .tools/universal/vault/check-links.py --by-file
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sys
import urllib.parse

EXTENSIONS = ("md", "csv", "html", "htm", "png", "jpg", "pdf", "txt", "srt", "xlsx", "ps1", "py")
LINK_RE = re.compile(r"\]\(([^)]+\.(?:" + "|".join(EXTENSIONS) + r"))\)")

SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", ".obsidian"}
FROZEN_PREFIXES = ("daily/", "reviews/", "recurring/")
FROZEN_MARKERS = ("_archive/", "/backlog.md")


def is_frozen(rel: str) -> bool:
    p = rel.replace(os.sep, "/")
    return (
        p.startswith(FROZEN_PREFIXES)
        or any(m in p for m in FROZEN_MARKERS)
        or p == "tasks.md"
    )


def walk_markdown(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".md"):
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(full, root)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="включая замороженные разделы")
    ap.add_argument("--by-file", action="store_true", help="сводка по файлам, не по ссылкам")
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    broken = []
    skipped = 0

    for full, rel in walk_markdown(root):
        if not args.all and is_frozen(rel):
            skipped += 1
            continue
        try:
            text = open(full, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        base = os.path.dirname(full)
        for link in LINK_RE.findall(text):
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = os.path.join(base, urllib.parse.unquote(link))
            if not os.path.exists(target):
                broken.append((rel, link))

    if args.by_file:
        counts = collections.Counter(f for f, _ in broken)
        for f, n in counts.most_common():
            print(f"{n:4}  {f}")
    else:
        for f, link in broken:
            print(f"{f} -> {link}")

    tail = f", пропущено замороженных файлов: {skipped}" if skipped else ""
    print(f"\nБитых ссылок: {len(broken)}{tail}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
