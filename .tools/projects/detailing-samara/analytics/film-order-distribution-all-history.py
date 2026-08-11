#!/usr/bin/env python3
"""Distribution of Levsha film order tickets by film-only revenue."""

from __future__ import annotations

import os
import sys
import warnings
import argparse
from importlib import import_module
from pathlib import Path

import pandas as pd


warnings.filterwarnings(
    "ignore",
    message=r"You are using a Python version .*",
    category=FutureWarning,
    module=r"google\.api_core\._python_version_support",
)

ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = str(ROOT / "system/scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

base = import_module("analyze-detailing-base")

FILM_LABEL = "Антигравийная пленка"
ADMIN_LABEL = "Админ / внутреннее / служебное"


def is_placeholder_client(name: str) -> bool:
    value = str(name or "").strip().lower()
    return not value or (value.startswith("<") and value.endswith(">")) or "продажи без заказа" in value


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def pct(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def main() -> None:
    parser = argparse.ArgumentParser(description="Levsha film order ticket distribution.")
    parser.add_argument("--start-date", help="Include film orders from this date, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Include film orders up to this date, YYYY-MM-DD.")
    args = parser.parse_args()

    rows = base.fetch_sheet()
    df = base.parse_to_long(rows)
    if df.empty:
        raise SystemExit("No source rows parsed.")

    df["client"] = df["client"].astype(str).str.strip()
    df["service_norm"] = df["service"].apply(base.normalize_service)

    clean = df.loc[
        ~df["service_norm"].eq(base.EXCLUDED_SERVICE_LABEL)
        & ~df["service_norm"].eq(ADMIN_LABEL)
        & ~df["client"].apply(is_placeholder_client)
    ].copy()

    visit_keys = ["client", "order_id", "date"]
    film_rows = clean.loc[clean["service_norm"].eq(FILM_LABEL)].copy()
    film_orders = (
        film_rows.groupby(visit_keys, as_index=False)
        .agg(
            film_revenue=("revenue", "sum"),
            film_lines=("service", "size"),
            film_quantity=("quantity", "sum"),
        )
        .sort_values("film_revenue", ascending=False)
    )
    film_orders = film_orders.loc[film_orders["film_revenue"].gt(0)].copy()
    if args.start_date:
        film_orders = film_orders.loc[film_orders["date"].ge(pd.Timestamp(args.start_date))].copy()
    if args.end_date:
        film_orders = film_orders.loc[film_orders["date"].le(pd.Timestamp(args.end_date))].copy()

    total_orders = len(film_orders)
    total_revenue = float(film_orders["film_revenue"].sum())
    if total_orders == 0:
        raise SystemExit("No positive film orders found.")

    buckets = [
        ("300 000+ ₽", film_orders["film_revenue"].ge(300_000)),
        ("100 000-299 999 ₽", film_orders["film_revenue"].ge(100_000) & film_orders["film_revenue"].lt(300_000)),
        ("< 100 000 ₽", film_orders["film_revenue"].lt(100_000)),
    ]

    print("Источник: 1С «Продажи по заказам» / Google Sheet")
    print(f"Период: {film_orders['date'].min():%Y-%m-%d} — {film_orders['date'].max():%Y-%m-%d}")
    print(f"Плёночных заказ-нарядов: {total_orders:,}".replace(",", " "))
    print(f"Выручка по плёнке в этих заказах: {money(total_revenue)} ₽")
    print(f"Средний плёночный чек: {money(float(film_orders['film_revenue'].mean()))} ₽")
    print(f"Медианный плёночный чек: {money(float(film_orders['film_revenue'].median()))} ₽")
    print()
    print(f"{'Диапазон':<20} {'Заказов':>8} {'Доля заказов':>12} {'Выручка':>14} {'Доля выручки':>13}")
    for label, mask in buckets:
        subset = film_orders.loc[mask]
        count = len(subset)
        revenue = float(subset["film_revenue"].sum())
        print(
            f"{label:<20} "
            f"{count:>8} "
            f"{pct(count / total_orders * 100):>11}% "
            f"{money(revenue):>13} ₽ "
            f"{pct(revenue / total_revenue * 100):>12}%"
        )

    print()
    print("Доп. гистограмма:")
    intervals = [
        ("0-25к", 0, 25_000),
        ("25-50к", 25_000, 50_000),
        ("50-100к", 50_000, 100_000),
        ("100-150к", 100_000, 150_000),
        ("150-200к", 150_000, 200_000),
        ("200-300к", 200_000, 300_000),
        ("300-500к", 300_000, 500_000),
        ("500к+", 500_000, float("inf")),
    ]
    for label, lower, upper in intervals:
        mask = film_orders["film_revenue"].ge(lower) & film_orders["film_revenue"].lt(upper)
        count = int(mask.sum())
        print(f"{label:<10} {count:>5} {pct(count / total_orders * 100):>6}%")

    visits = (
        clean.groupby(visit_keys, as_index=False)
        .agg(visit_revenue=("revenue", "sum"))
        .sort_values(["client", "date", "order_id"])
    )
    visits["visit_seq"] = visits.groupby("client").cumcount() + 1
    visits["client_visits"] = visits.groupby("client")["order_id"].transform("size")

    enriched = film_orders.merge(
        visits[visit_keys + ["visit_seq", "client_visits"]],
        on=visit_keys,
        how="left",
    ).sort_values(["client", "date", "order_id"])
    enriched["film_seq"] = enriched.groupby("client").cumcount() + 1
    enriched["client_film_orders"] = enriched.groupby("client")["order_id"].transform("size")
    enriched["has_prior_visit"] = enriched["visit_seq"].gt(1)
    enriched["has_later_visit"] = enriched["visit_seq"].lt(enriched["client_visits"])
    enriched["has_prior_film"] = enriched["film_seq"].gt(1)
    enriched["has_later_film"] = enriched["film_seq"].lt(enriched["client_film_orders"])
    enriched["one_visit_client"] = enriched["client_visits"].eq(1)

    low = enriched.loc[enriched["film_revenue"].lt(50_000)].copy()
    low_total = len(low)
    low_revenue = float(low["film_revenue"].sum())

    print()
    print("=== Плёночные заказ-наряды до 50к: возвратность клиента ===")
    print(f"До 50к: {low_total} заказов, {pct(low_total / total_orders * 100)}% всех платных плёночных заказов")
    print(f"Выручка до 50к: {money(low_revenue)} ₽, {pct(low_revenue / total_revenue * 100)}% плёночной выручки")

    segments = [
        ("Единственный визит клиента в базе", low["one_visit_client"]),
        ("Первый визит, но клиент потом вернулся", low["visit_seq"].eq(1) & low["has_later_visit"]),
        ("Не первый визит клиента", low["has_prior_visit"]),
        ("Повторная плёнка у клиента", low["has_prior_film"]),
        ("После этого заказа был любой возврат", low["has_later_visit"]),
        ("После этого заказа была ещё плёнка", low["has_later_film"]),
    ]
    for label, mask in segments:
        count = int(mask.sum())
        revenue = float(low.loc[mask, "film_revenue"].sum())
        print(
            f"{label:<36} "
            f"{count:>5} "
            f"{pct(count / low_total * 100):>6}% "
            f"{money(revenue):>12} ₽"
        )

    first_small = low.loc[low["visit_seq"].eq(1)]
    if not first_small.empty:
        returned = int(first_small["has_later_visit"].sum())
        print()
        print(
            "Если заказ до 50к был первым визитом: "
            f"{returned}/{len(first_small)} вернулись = {pct(returned / len(first_small) * 100)}%"
        )


if __name__ == "__main__":
    main()
