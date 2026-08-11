"""
Для мелких плёночных нарядов (<50к) определяем — это разовые истории или повторные.
Источник: .tools/snapshots/film-orders-distribution.csv
(сгенерирован film-orders-distribution.py).
"""
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / ".tools/snapshots/film-orders-distribution.csv"

# Загрузка нарядов
orders = []
with open(SRC, newline="", encoding="utf-8") as f:
    rdr = csv.DictReader(f)
    for r in rdr:
        try:
            check = float(r["film_check"])
            date = datetime.strptime(r["date"], "%d.%m.%Y") if r["date"] else None
        except (ValueError, KeyError):
            continue
        if check <= 0:
            continue
        orders.append({
            "client": r["client"] or "(БЕЗ ИМЕНИ)",
            "order_id": r["order_id"],
            "date": date,
            "check": check,
        })

# Группировка по клиентам
by_client = defaultdict(list)
for o in orders:
    by_client[o["client"]].append(o)

# Сортируем наряды каждого клиента по дате (None дата в конец)
for client, lst in by_client.items():
    lst.sort(key=lambda x: (x["date"] is None, x["date"]))

print(f"Всего плёночных нарядов: {len(orders)}")
print(f"Уникальных клиентов с плёнкой: {len(by_client)}")
print(f"Среднее число плёночных нарядов на клиента: {len(orders) / len(by_client):.2f}")
print()

# === Анализ клиентов по числу плёночных нарядов ===
counts = defaultdict(int)
for client, lst in by_client.items():
    counts[len(lst)] += 1

print("=== Распределение клиентов по числу плёночных нарядов ===")
print(f"{'Нарядов у клиента':<22}{'Клиентов':>10}{'%':>8}")
print("-" * 42)
for n in sorted(counts):
    cnt = counts[n]
    pct = cnt / len(by_client) * 100
    label = f"{n} наряд" if n == 1 else f"{n} нарядов"
    bar = "█" * int(pct / 2)
    print(f"{label:<22}{cnt:>10}{pct:>7.1f}% {bar}")
print()

# === Главный вопрос: мелкие наряды (<50к) — разовые или повторные? ===
THRESHOLD_SMALL = 50_000
THRESHOLD_BIG = 100_000

small_orders = [o for o in orders if o["check"] < THRESHOLD_SMALL]
print(f"Мелких нарядов (< {THRESHOLD_SMALL/1000:.0f}к): {len(small_orders)} = {len(small_orders)/len(orders)*100:.1f}% всех плёночных")
print()

# Для каждого мелкого наряда определяем его позицию у клиента
buckets = {
    "Первый плёночный наряд клиента (история разовая на этом моменте)": 0,
    "Повторный — у клиента было ≥1 наряд 100к+ раньше": 0,
    "Повторный — у клиента раньше тоже была мелочь (<100к)": 0,
    "Первый, но потом клиент пришёл ещё (доклейки в будущем)": 0,
}

# Точнее: для каждого small order смотрим всю историю клиента и определяем позицию
small_categories = []
for o in small_orders:
    client_orders = by_client[o["client"]]
    # все наряды клиента в хронологии
    idx = client_orders.index(o)
    earlier = client_orders[:idx]  # наряды РАНЬШЕ этого
    later = client_orders[idx+1:]  # наряды ПОЗЖЕ этого

    has_big_earlier = any(eo["check"] >= THRESHOLD_BIG for eo in earlier)
    has_small_earlier = any(eo["check"] < THRESHOLD_BIG for eo in earlier)
    has_later = len(later) > 0

    if len(earlier) == 0:
        # Первый плёночный наряд клиента
        if has_later:
            cat = "Первый, но потом клиент пришёл ещё (доклейки в будущем)"
        else:
            cat = "Первый плёночный наряд клиента (история разовая на этом моменте)"
    else:
        if has_big_earlier:
            cat = "Повторный — у клиента было ≥1 наряд 100к+ раньше"
        else:
            cat = "Повторный — у клиента раньше тоже была мелочь (<100к)"

    buckets[cat] += 1
    small_categories.append((o, cat))

total_small = len(small_orders)
print(f"=== Мелкие наряды (<50к): разовые vs повторные ===")
print(f"{'Категория':<70}{'Шт':>8}{'%':>8}")
print("-" * 86)
for cat, cnt in buckets.items():
    pct = cnt / total_small * 100
    print(f"{cat:<70}{cnt:>8}{pct:>7.1f}%")
print()

# Свёртка: разовые vs возвращавшиеся
one_time_small = buckets["Первый плёночный наряд клиента (история разовая на этом моменте)"]
returned_small = (
    buckets["Повторный — у клиента было ≥1 наряд 100к+ раньше"]
    + buckets["Повторный — у клиента раньше тоже была мелочь (<100к)"]
    + buckets["Первый, но потом клиент пришёл ещё (доклейки в будущем)"]
)
print(f"=== ИТОГ по мелким нарядам ===")
print(f"  Разовые (клиент пришёл один раз и не вернулся): {one_time_small} = {one_time_small/total_small*100:.1f}%")
print(f"  Часть истории постоянного клиента:             {returned_small} = {returned_small/total_small*100:.1f}%")
print()

# === Аналогично для всех плёночных нарядов (для сравнения) ===
print("=== То же для ВСЕХ плёночных нарядов (а не только <50к) ===")
all_buckets = defaultdict(int)
for o in orders:
    client_orders = by_client[o["client"]]
    idx = client_orders.index(o)
    earlier = client_orders[:idx]
    later = client_orders[idx+1:]
    has_big_earlier = any(eo["check"] >= THRESHOLD_BIG for eo in earlier)
    has_later = len(later) > 0

    if len(earlier) == 0:
        if has_later:
            cat = "Первый, потом ещё"
        else:
            cat = "Единственный (разовый)"
    else:
        if has_big_earlier:
            cat = "Повторный после крупного"
        else:
            cat = "Повторный после мелкого"
    all_buckets[cat] += 1

for cat, cnt in all_buckets.items():
    pct = cnt / len(orders) * 100
    print(f"  {cat:<40} {cnt:>5} ({pct:>5.1f}%)")
print()

# === Клиенты с большим чеком + сколько мелких потом ===
print("=== Клиенты, у которых был хотя бы один наряд 100к+ ===")
clients_with_big = [c for c, lst in by_client.items() if any(o["check"] >= THRESHOLD_BIG for o in lst)]
clients_with_big_then_small = []
for c in clients_with_big:
    lst = by_client[c]
    # Найти первый крупный наряд
    first_big_idx = next(i for i, o in enumerate(lst) if o["check"] >= THRESHOLD_BIG)
    after_big = lst[first_big_idx+1:]
    small_after = [o for o in after_big if o["check"] < THRESHOLD_SMALL]
    if small_after:
        clients_with_big_then_small.append((c, len(small_after), sum(o["check"] for o in small_after)))

print(f"  Всего клиентов с крупным нарядом (≥100к): {len(clients_with_big)}")
print(f"  Из них пришли ещё с мелочью (<50к) после крупного: {len(clients_with_big_then_small)} ({len(clients_with_big_then_small)/len(clients_with_big)*100:.1f}%)")
if clients_with_big_then_small:
    total_followup_revenue = sum(rev for _, _, rev in clients_with_big_then_small)
    print(f"  Суммарная выручка от этих мелких 'follow-up' нарядов: {total_followup_revenue:,.0f} ₽".replace(",", " "))
    avg_followup = total_followup_revenue / len(clients_with_big_then_small)
    print(f"  Средняя доп.выручка от мелких после крупного на клиента: {avg_followup:,.0f} ₽".replace(",", " "))
