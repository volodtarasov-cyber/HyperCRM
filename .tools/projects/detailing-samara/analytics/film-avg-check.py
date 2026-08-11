"""
Считает средний чек ПЕРВОЙ плёнки клиента + LTV-вклад за 12 мес после.
Источник: film-return-patterns-cohort-2026-05-20.csv (когорта первых плёнок).
"""
import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "projects/detailing-samara/analytics/film-return-patterns-cohort-2026-05-20.csv"


def percentile(data, p):
    """Линейный перцентиль на отсортированных данных."""
    if not data:
        return 0
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f = int(k); c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    rows = []
    with open(SRC, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                rev = float(r["first_film_revenue"])
                date = r["first_film_date"]
                returned_12m = r["returned_12m"] == "True"
                post_12m_rev = float(r["post_12m_revenue"] or 0)
                post_12m_visits = int(r["post_12m_visits"] or 0)
            except (ValueError, KeyError):
                continue
            if rev <= 0:
                continue
            rows.append({
                "client": r["client"],
                "date": date,
                "year": date[:4],
                "ym": date[:7],
                "rev": rev,
                "returned_12m": returned_12m,
                "post_12m_rev": post_12m_rev,
                "post_12m_visits": post_12m_visits,
            })

    print(f"Всего клиентов в когорте: {len(rows)}")
    print(f"Период: {min(r['date'] for r in rows)} → {max(r['date'] for r in rows)}")
    print()

    # ---------- Общий средний чек первой плёнки ----------
    revs = [r["rev"] for r in rows]
    print("=== Средний чек ПЕРВОЙ плёнки ===")
    print(f"  Среднее:    {statistics.mean(revs):>12,.0f} ₽")
    print(f"  Медиана:    {statistics.median(revs):>12,.0f} ₽")
    print(f"  P25:        {percentile(revs, 25):>12,.0f} ₽")
    print(f"  P75:        {percentile(revs, 75):>12,.0f} ₽")
    print(f"  P90:        {percentile(revs, 90):>12,.0f} ₽")
    print(f"  P95:        {percentile(revs, 95):>12,.0f} ₽")
    print(f"  Минимум:    {min(revs):>12,.0f} ₽")
    print(f"  Максимум:   {max(revs):>12,.0f} ₽")
    print(f"  Сумма:      {sum(revs):>12,.0f} ₽")
    print()

    # ---------- По годам ----------
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r["rev"])
    print("=== По годам ===")
    print(f"{'Год':<8}{'Клиентов':>12}{'Средний':>14}{'Медиана':>14}{'Сумма':>16}")
    for yr in sorted(by_year):
        lst = by_year[yr]
        print(f"{yr:<8}{len(lst):>12,}{statistics.mean(lst):>14,.0f}{statistics.median(lst):>14,.0f}{sum(lst):>16,.0f}")
    print()

    # ---------- По месяцам ----------
    by_ym = defaultdict(list)
    for r in rows:
        by_ym[r["ym"]].append(r["rev"])
    print("=== По месяцам (последние 24) ===")
    print(f"{'Месяц':<10}{'Клиентов':>10}{'Средний':>14}{'Медиана':>14}{'Сумма':>14}")
    for ym in sorted(by_ym)[-24:]:
        lst = by_ym[ym]
        print(f"{ym:<10}{len(lst):>10,}{statistics.mean(lst):>14,.0f}{statistics.median(lst):>14,.0f}{sum(lst):>14,.0f}")
    print()

    # ---------- За последние 24 мес ----------
    cutoff = "2024-05"  # 24 мес от 2026-05
    last24 = [r["rev"] for r in rows if r["date"] >= cutoff]
    if last24:
        print(f"=== За последние 24 месяца (с {cutoff}) ===")
        print(f"  Клиентов: {len(last24)}")
        print(f"  Средний:  {statistics.mean(last24):,.0f} ₽")
        print(f"  Медиана:  {statistics.median(last24):,.0f} ₽")
        print(f"  Сумма:    {sum(last24):,.0f} ₽")
        print()

    # ---------- LTV: средний чек + что приносят за следующие 12 мес ----------
    print("=== Что клиент приносит за 12 мес ПОСЛЕ первой плёнки ===")
    avg_post = statistics.mean(r["post_12m_rev"] for r in rows)
    returned = [r for r in rows if r["returned_12m"]]
    print(f"  Возвратились за 12 мес: {len(returned)}/{len(rows)} = {len(returned)/len(rows)*100:.1f}%")
    print(f"  Средняя доп. выручка за 12 мес (на всех): {avg_post:,.0f} ₽")
    if returned:
        avg_returned = statistics.mean(r["post_12m_rev"] for r in returned)
        print(f"  Средняя доп. выручка за 12 мес (только вернувшиеся): {avg_returned:,.0f} ₽")
    print()
    print(f"  Полный средний LTV первого года = {statistics.mean(revs) + avg_post:,.0f} ₽")


if __name__ == "__main__":
    main()
