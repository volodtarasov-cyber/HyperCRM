"""
Распределение ВСЕХ заказ-нарядов с плёнкой по чеку (работа + материал).
Источник: ~/Downloads/24_26_клиенты_услуги по месяцам.xlsx — построчная выгрузка 1С.

Структура файла:
- Строка клиента: имя в col[0], нет ", " префикса, нет "Заказ-наряд" префикса
- Строка наряда: col[0] начинается с "Заказ-наряд"
- Строка услуги/материала: col[0] начинается с ", "
- В col(итого выручка) — суммарная стоимость строки за весь период
"""
import re
import os
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[4]
SRC = Path.home() / "Downloads/24_26_клиенты_услуги по месяцам.xlsx"
OUT_CSV = ROOT / ".tools/snapshots/film-orders-distribution.csv"
FROM_DATE = os.environ.get("FROM_DATE")  # формат "DD.MM.YYYY" минимальная дата

# Колонка "Итого/Выручка" — судя по структуре, 9-я (индекс с 0 = 9).
# Проверим в первых строках.
COL_ITOGO_REVENUE = 9

FILM_WORK_PATTERNS = [
    r"Антигравийная пленка",  # "на кузов" + "(Полная оклейка ТС)" — обе формулировки
]
FILM_MATERIAL_PATTERNS = [
    r"Материал Пленка",
]


def is_film_work(name: str) -> bool:
    return any(re.search(p, name, re.IGNORECASE) for p in FILM_WORK_PATTERNS)


def is_film_material(name: str) -> bool:
    return any(re.search(p, name, re.IGNORECASE) for p in FILM_MATERIAL_PATTERNS)


def parse_revenue(cell) -> float:
    if cell is None:
        return 0.0
    if isinstance(cell, (int, float)):
        return float(cell)
    s = str(cell).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def main():
    print(f"Открываю {SRC}...")
    wb = load_workbook(SRC, read_only=True, data_only=True)
    ws = wb.active

    # Подтвердить индекс колонки выручки
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    print("Заголовки колонок:")
    for i, h in enumerate(header_row[:15]):
        print(f"  [{i}] {h}")
    print()

    orders = []  # список нарядов: {client, order_id, date, film_work, film_material, all_services}
    current_client = None
    current_order = None

    rows_processed = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        rows_processed += 1
        first = row[0]
        if first is None:
            continue
        first = str(first).strip()
        if not first:
            continue

        if first.startswith("Заказ-наряд"):
            # сохранить предыдущий
            if current_order is not None:
                orders.append(current_order)
            # парсим номер и дату
            m = re.search(r"Заказ-наряд\s+(\S+)\s+от\s+(\d{2}\.\d{2}\.\d{4})", first)
            order_id = m.group(1) if m else first
            date = m.group(2) if m else ""
            current_order = {
                "client": current_client,
                "order_id": order_id,
                "date": date,
                "total_revenue": parse_revenue(row[COL_ITOGO_REVENUE]),
                "film_work": 0.0,
                "film_material": 0.0,
                "has_film_work": False,
                "has_film_material": False,
            }
        elif first.startswith(", "):
            # строка услуги/материала внутри текущего наряда
            service_name = first[2:]  # убрать ", "
            rev = parse_revenue(row[COL_ITOGO_REVENUE])
            if current_order is None:
                continue
            if is_film_work(service_name):
                current_order["film_work"] += rev
                current_order["has_film_work"] = True
            elif is_film_material(service_name):
                current_order["film_material"] += rev
                current_order["has_film_material"] = True
        else:
            # строка клиента
            if current_order is not None:
                orders.append(current_order)
                current_order = None
            current_client = first

    # хвост
    if current_order is not None:
        orders.append(current_order)

    print(f"Всего строк обработано: {rows_processed}")
    print(f"Всего заказ-нарядов найдено: {len(orders)}")
    print()

    # Фильтр по дате (если задан)
    if FROM_DATE:
        from datetime import datetime
        cutoff = datetime.strptime(FROM_DATE, "%d.%m.%Y")
        before = len(orders)
        orders = [
            o for o in orders
            if o["date"] and datetime.strptime(o["date"], "%d.%m.%Y") >= cutoff
        ]
        print(f"Фильтр по дате ≥ {FROM_DATE}: {before} → {len(orders)} нарядов")
        print()

    # Фильтр: только наряды с плёнкой (работа ИЛИ материал)
    film_orders = [
        o for o in orders
        if o["has_film_work"] or o["has_film_material"]
    ]
    print(f"Заказ-нарядов с плёнкой (работа + материал): {len(film_orders)}")
    print()

    # Чек плёнки в наряде = работа + материал
    checks = []
    for o in film_orders:
        check = o["film_work"] + o["film_material"]
        if check <= 0:
            continue
        checks.append(check)
        o["film_check"] = check

    total = len(checks)
    total_rev = sum(checks)
    print(f"Нарядов с положительным плёночным чеком: {total}")
    print(f"Суммарная выручка от плёнки (работа+материал): {total_rev:,.0f} ₽".replace(",", " "))
    print()

    # Разрезы Володи
    bucket_300_plus = [c for c in checks if c >= 300_000]
    bucket_100_300 = [c for c in checks if 100_000 <= c < 300_000]
    bucket_lt_100 = [c for c in checks if c < 100_000]

    print("=" * 70)
    print(f"{'Чек':<28}{'Нарядов':>10}{'%':>8}{'Сумма ₽':>22}{'%выр':>8}")
    print("=" * 70)
    for label, lst in [
        ("300 000+ ₽", bucket_300_plus),
        ("100 000–299 999 ₽", bucket_100_300),
        ("Менее 100 000 ₽", bucket_lt_100),
    ]:
        cnt = len(lst)
        s = sum(lst)
        pct_cnt = cnt / total * 100
        pct_rev = s / total_rev * 100
        print(
            f"{label:<28}{cnt:>10}{pct_cnt:>7.1f}%{s:>20,.0f} ₽{pct_rev:>7.1f}%".replace(",", " ")
        )
    print("=" * 70)
    print()

    # Гистограмма
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
    print("=== Гистограмма по интервалам ===")
    for lo, hi, label in intervals:
        cnt = sum(1 for c in checks if lo <= c < hi)
        pct = cnt / total * 100
        bar = "█" * int(pct * 2)
        print(f"  {label:<10} {cnt:>5} ({pct:>5.1f}%) {bar}")
    print()

    # Сохранить детальную выгрузку для аудита
    OUT_CSV.parent.mkdir(exist_ok=True)
    import csv
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["client", "order_id", "date", "total_revenue", "film_work", "film_material", "film_check"])
        for o in film_orders:
            if "film_check" in o:
                w.writerow([
                    o["client"] or "",
                    o["order_id"],
                    o["date"],
                    o["total_revenue"],
                    o["film_work"],
                    o["film_material"],
                    o["film_check"],
                ])
    print(f"Детальный CSV: {OUT_CSV}")


if __name__ == "__main__":
    main()
