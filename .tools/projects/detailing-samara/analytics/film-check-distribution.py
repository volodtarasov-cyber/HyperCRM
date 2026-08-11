"""
Распределение плёночных нарядов по чекам.
Источник: film-return-patterns-cohort-2026-05-20.csv (первая плёнка каждого клиента).
В first_film_revenue материал плёнки уже схлопнут с работой по методике 2026-05-20.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "projects/detailing-samara/analytics/film-return-patterns-cohort-2026-05-20.csv"

revs = []
with open(SRC, newline="", encoding="utf-8-sig") as f:
    rdr = csv.DictReader(f)
    for r in rdr:
        try:
            v = float(r["first_film_revenue"])
        except (ValueError, KeyError):
            continue
        if v > 0:
            revs.append(v)

total = len(revs)
print(f"Всего плёночных нарядов (первые плёнки клиентов): {total}")
print(f"Период когорты: янв.2024 — апр.2025 (16 месяцев)")
print(f"Сумма выручки: {sum(revs):,.0f} ₽".replace(",", " "))
print()

# Разрезы Володи
buckets = {
    "300 000+ ₽":   sum(1 for v in revs if v >= 300_000),
    "100 000-299 999 ₽": sum(1 for v in revs if 100_000 <= v < 300_000),
    "Менее 100 000 ₽":   sum(1 for v in revs if v < 100_000),
}

print("=" * 60)
print(f"{'Чек':<24}{'Кол-во':>10}{'%':>8}{'Сумма ₽':>18}")
print("=" * 60)
for label, count in buckets.items():
    rev_sum = sum(v for v in revs if {
        "300 000+ ₽": v >= 300_000,
        "100 000-299 999 ₽": 100_000 <= v < 300_000,
        "Менее 100 000 ₽": v < 100_000,
    }[label])
    pct = count / total * 100
    print(f"{label:<24}{count:>10}{pct:>7.1f}%{rev_sum:>18,.0f}".replace(",", " "))
print("=" * 60)
print()

# Доля выручки от каждой группы
total_rev = sum(revs)
print("=== Доля выручки от каждой группы ===")
for label, _ in buckets.items():
    rev_sum = sum(v for v in revs if {
        "300 000+ ₽": v >= 300_000,
        "100 000-299 999 ₽": 100_000 <= v < 300_000,
        "Менее 100 000 ₽": v < 100_000,
    }[label])
    print(f"  {label:<22} даёт {rev_sum/total_rev*100:>5.1f}% общей выручки от плёнки")

print()
# Дополнительная детализация — гистограмма
print("=== Гистограмма по интервалам ===")
intervals = [
    (0, 25_000, "< 25к"),
    (25_000, 50_000, "25-50к"),
    (50_000, 100_000, "50-100к"),
    (100_000, 150_000, "100-150к"),
    (150_000, 200_000, "150-200к"),
    (200_000, 300_000, "200-300к"),
    (300_000, 500_000, "300-500к"),
    (500_000, 10**9, "500к+"),
]
for lo, hi, label in intervals:
    cnt = sum(1 for v in revs if lo <= v < hi)
    pct = cnt / total * 100
    bar = "█" * int(pct * 2)
    print(f"  {label:<10} {cnt:>4} ({pct:>5.1f}%) {bar}")
