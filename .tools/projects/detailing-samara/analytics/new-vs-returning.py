#!/usr/bin/env python3
# Новые vs повторные обращения по годам для Левши.
# Источники:
#   b2b-vs-private-clients-2026-05-20.csv  — мастер клиентов (first_visit, visits)
#   visit-intervals-atbv-raw-2026-05-20.csv — пары последовательных визитов (даёт все даты визитов у клиентов с >=2 визитами)
import csv, collections
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "projects/detailing-samara/analytics"

def y(d):
    return datetime.strptime(d, "%Y-%m-%d").year

# --- мастер клиентов: first_visit у каждого ---
first_visit = {}
master_visits = {}
with open(BASE / "b2b-vs-private-clients-2026-05-20.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        first_visit[r["client"]] = r["first_visit"]
        master_visits[r["client"]] = int(float(r["visits"]))

# --- восстанавливаем все даты визитов из интервалов ---
visit_dates = collections.defaultdict(set)
with open(BASE / "visit-intervals-atbv-raw-2026-05-20.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        visit_dates[r["client"]].add(r["prev_date"])
        visit_dates[r["client"]].add(r["next_date"])

# клиенты с 1 визитом не попали в интервалы — добавим их единственный визит
for c, fv in first_visit.items():
    if c not in visit_dates:
        visit_dates[c].add(fv)

# --- собираем все визиты: (дата, клиент, это ли первый визит) ---
new_by_year = collections.Counter()      # первый визит клиента пришёлся на год
repeat_by_year = collections.Counter()   # повторное обращение существующего клиента
for c, dates in visit_dates.items():
    fv = min(dates)  # самый ранний визит = факт. первый по нашим данным
    for d in sorted(dates):
        if d == fv:
            new_by_year[y(d)] += 1
        else:
            repeat_by_year[y(d)] += 1

# --- по календарным годам ---
years = sorted(set(list(new_by_year) + list(repeat_by_year)))
print("ГОД  | новых клиентов | повторных обращ. | всего обращ. | доля повторных")
for yr in years:
    n = new_by_year[yr]; rep = repeat_by_year[yr]; tot = n + rep
    share = rep / tot * 100 if tot else 0
    print(f"{yr} |   {n:6d}       |    {rep:6d}        |   {tot:6d}    |   {share:5.1f}%")

# --- последние 12 мес (примерно май2025–апр2026), но проще: годовые срезы уже выше ---
total_clients = len(first_visit)
multi = sum(1 for c in master_visits if master_visits[c] >= 2)
one = total_clients - multi
print()
print(f"Всего уникальных клиентов в базе: {total_clients}")
print(f"  с 1 визитом (one-and-done):    {one}  ({one/total_clients*100:.1f}%)")
print(f"  с 2+ визитами (вернулись):      {multi}  ({multi/total_clients*100:.1f}%)")
all_visits = sum(master_visits.values())
print(f"Всего визитов (по мастеру):       {all_visits}")
print(f"  первичных (=кол-во клиентов):   {total_clients}  ({total_clients/all_visits*100:.1f}%)")
print(f"  повторных:                      {all_visits-total_clients}  ({(all_visits-total_clients)/all_visits*100:.1f}%)")
