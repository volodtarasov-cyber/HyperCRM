"""Разведка спроса владельцев бизнеса под нишевые страницы агентства.

По списку запросов снимает через XMLRiver (ключ берётся из копии SEO-завода):
  - частотность Wordstat: широкую и фразовую («в кавычках»);
  - топ-10 Яндекса — из него считаются домены, которые повторяются по многим
    запросам: это и есть конкуренты по выдаче.

Цена — 0,025 ₽ за обращение: 3 обращения на запрос.

Использование:
    .tools/venv/Scripts/python.exe niche-demand-probe.py <seeds.txt> <out_dir> \
        [--factory D:/SecondBrain/seo-factory-volodtarasov] [--region 51]

seeds.txt — по запросу в строке; строка «# кластер» начинает группу.
В out_dir пишутся сырые данные (не версионируются): demand.csv, serp.json, domains.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

# Площадки и справочники, которые попадают в топ по любому запросу и конкурентами не являются.
NOT_COMPETITORS = {
    "avito.ru", "youtube.com", "vk.com", "dzen.ru", "ya.ru", "yandex.ru", "market.yandex.ru",
    "pikabu.ru", "vc.ru", "habr.com", "rutube.ru", "t.me", "ok.ru", "2gis.ru", "otzovik.com",
    "irecommend.ru", "wikipedia.org", "ru.wikipedia.org", "profi.ru", "kwork.ru", "fl.ru",
    "hh.ru", "spark-interfax.ru", "rusprofile.ru", "pinterest.com", "instagram.com",
}


def load_seeds(path: Path) -> list[tuple[str, str]]:
    cluster, out = "без кластера", []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            cluster = line.lstrip("# ").strip()
            continue
        out.append((cluster, line))
    return out


def domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--factory", type=Path, default=Path("D:/SecondBrain/seo-factory-volodtarasov"))
    ap.add_argument("--region", type=int, default=225,
                    help="регион Wordstat и выдачи Яндекса: 225 — Россия, 51 — Самара, 213 — Москва")
    args = ap.parse_args()

    sys.path.insert(0, str(args.factory / "engine" / "seo-agent"))
    from modules import xmlriver_api as xr  # noqa: E402

    if not xr.available():
        print("XMLRiver не подключён в копии завода — нечем мерить.")
        return 1

    seeds = load_seeds(args.seeds)
    phrases = [p for _, p in seeds]
    before = xr.balance()
    print(f"Регион {args.region} · запросов: {len(phrases)} · прогноз ≈ {len(phrases) * 3 * xr.RUB_PER_CALL:.2f} ₽ · баланс {before} ₽")

    def measure(ph: str):
        wide = xr.frequency([ph], ws="base", region=args.region).get(ph)
        phrase = xr.frequency([ph], ws="quoted", region=args.region).get(ph)
        top = xr.serp_top(ph, engine="yandex", depth=10, region=args.region)
        return ph, wide, phrase, top

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = {ph: (w, q, top) for ph, w, q, top in pool.map(measure, phrases)}

    args.out.mkdir(parents=True, exist_ok=True)

    with (args.out / "demand.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["кластер", "запрос", "широкая", "фразовая", "в топе статей/агентств"])
        for cluster, ph in seeds:
            wide, quoted, top = results[ph]
            w.writerow([cluster, ph, "" if wide is None else wide, "" if quoted is None else quoted, len(top)])

    (args.out / "serp.json").write_text(
        json.dumps({ph: r[2] for ph, r in results.items()}, ensure_ascii=False, indent=1), encoding="utf-8")

    # Конкурент = домен, который встречается в топе по нескольким запросам.
    hits: Counter[str] = Counter()
    where: dict[str, list[str]] = defaultdict(list)
    for ph, (_, _, top) in results.items():
        for d in {domain(u) for u in top}:
            if d and d not in NOT_COMPETITORS and not d.endswith(".yandex.ru"):
                hits[d] += 1
                where[d].append(ph)
    with (args.out / "domains.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["домен", "в скольких топах", "по каким запросам"])
        for d, n in hits.most_common():
            w.writerow([d, n, " | ".join(where[d])])

    after = xr.balance()
    unmeasured = [ph for ph, r in results.items() if r[0] is None and r[1] is None]
    no_serp = [ph for ph, r in results.items() if not r[2]]

    # Итог в консоль: по кластерам и топ доменов.
    by_cluster: dict[str, list[tuple[str, int | None, int | None]]] = defaultdict(list)
    for cluster, ph in seeds:
        by_cluster[cluster].append((ph, results[ph][0], results[ph][1]))
    for cluster, rows in by_cluster.items():
        total = sum(q or 0 for _, _, q in rows)
        print(f"\n## {cluster} — фразовая сумма {total}")
        for ph, wide, quoted in sorted(rows, key=lambda r: -(r[2] or 0)):
            print(f"  {quoted if quoted is not None else '—':>6} / {wide if wide is not None else '—':>7}  {ph}")
    print("\n## Домены, повторяющиеся в топах (≥3)")
    for d, n in hits.most_common():
        if n >= 3:
            print(f"  {n:>3}  {d}")
    print(f"\nНе замерено частотностей: {len(unmeasured)} · без выдачи: {len(no_serp)}")
    print(f"Баланс: {before} → {after} ₽")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
