#!/usr/bin/env python3
"""
Composition analysis of monthly top-10% checks for Levsha.

Top-10% means the highest-revenue visits inside each month, using the same
monthly period and exclusions as analyze-ticket-depth-monthly.py.
"""

from __future__ import annotations

import math
import os
import sys
from importlib import import_module

import pandas as pd


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

ticket = import_module("analyze-ticket-depth-monthly")
base = import_module("analyze-detailing-base")

OUT_DIR = os.path.join(ROOT, "projects", "detailing-samara", "analytics")
DATE_TAG = "2026-05-20"
REPORT_PATH = os.path.join(OUT_DIR, f"top10-check-composition-{DATE_TAG}.md")
MONTHLY_CSV_PATH = os.path.join(OUT_DIR, f"top10-check-composition-monthly-{DATE_TAG}.csv")
CATEGORY_CSV_PATH = os.path.join(OUT_DIR, f"top10-check-composition-categories-{DATE_TAG}.csv")
COMBO_CSV_PATH = os.path.join(OUT_DIR, f"top10-check-composition-combos-{DATE_TAG}.csv")
RAW_SERVICE_CSV_PATH = os.path.join(OUT_DIR, f"top10-check-composition-services-{DATE_TAG}.csv")


def visit_key(df: pd.DataFrame) -> pd.Series:
    return (
        df["client"].astype(str)
        + "||"
        + df["order_id"].astype(str)
        + "||"
        + pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    )


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def integer(value: float) -> str:
    return f"{int(value):,}".replace(",", " ")


def num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value: float, digits: int = 1) -> str:
    return f"{num(value, digits)}%"


def month_label(month: str) -> str:
    return ticket.month_label(month)


def pick_monthly_top10(visits: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for _month, group in visits.groupby("month", sort=True):
        top_count = max(1, math.ceil(len(group) * 0.10))
        frames.append(group.sort_values("revenue", ascending=False).head(top_count))
    top = pd.concat(frames, ignore_index=True)
    top["visit_key"] = visit_key(top)
    return top


def summarize_visit_group(label: str, frame: pd.DataFrame) -> dict[str, float | str]:
    visits = len(frame)
    revenue = float(frame["revenue"].sum())
    return {
        "segment": label,
        "visits": visits,
        "revenue": revenue,
        "avg_ticket": revenue / visits if visits else 0,
        "median_ticket": float(frame["revenue"].median()) if visits else 0,
        "avg_service_units": float(frame["service_units"].mean()) if visits else 0,
        "avg_categories": float(frame["service_categories"].mean()) if visits else 0,
        "combo_share": float(frame["combo_visit"].mean() * 100) if visits else 0,
        "deep_service_share": float(frame["deep_service_visit"].mean() * 100) if visits else 0,
    }


def commercial_clean_top(clean_top: pd.DataFrame, top10: pd.DataFrame) -> pd.DataFrame:
    film_keys = set(
        top10.loc[
            top10["services"].apply(lambda services: ticket.FILM_LABEL in set(services or [])),
            "visit_key",
        ]
    )
    excluded_zero_wash = (
        clean_top["visit_key"].isin(film_keys)
        & clean_top["service_norm"].eq(ticket.WASH_LABEL)
        & clean_top["revenue"].eq(0)
    )
    return clean_top.loc[~excluded_zero_wash].copy()


def category_summary(clean_top: pd.DataFrame, top10_revenue: float) -> pd.DataFrame:
    grouped = (
        clean_top.groupby("service_norm", as_index=False)
        .agg(
            revenue=("revenue", "sum"),
            service_rows=("service_norm", "size"),
            visits=("visit_key", "nunique"),
        )
        .sort_values("revenue", ascending=False)
    )
    grouped["revenue_share"] = grouped["revenue"] / top10_revenue * 100
    return grouped


def dominant_summary(top10: pd.DataFrame, top10_revenue: float) -> pd.DataFrame:
    grouped = (
        top10.groupby("dominant_service", as_index=False)
        .agg(visits=("visit_key", "nunique"), revenue=("revenue", "sum"))
        .sort_values("revenue", ascending=False)
    )
    grouped["revenue_share"] = grouped["revenue"] / top10_revenue * 100
    grouped["visit_share"] = grouped["visits"] / len(top10) * 100
    return grouped


def combo_summary(top10: pd.DataFrame, top10_revenue: float) -> pd.DataFrame:
    combo = top10.copy()
    combo["service_combo"] = combo["services"].apply(lambda values: " + ".join(values))
    grouped = (
        combo.groupby("service_combo", as_index=False)
        .agg(
            visits=("visit_key", "nunique"),
            revenue=("revenue", "sum"),
            avg_ticket=("revenue", "mean"),
            avg_categories=("service_categories", "mean"),
            avg_service_units=("service_units", "mean"),
        )
        .sort_values("revenue", ascending=False)
    )
    grouped["revenue_share"] = grouped["revenue"] / top10_revenue * 100
    grouped["visit_share"] = grouped["visits"] / len(top10) * 100
    return grouped


def raw_service_summary(clean_top: pd.DataFrame, top10_revenue: float) -> pd.DataFrame:
    grouped = (
        clean_top.groupby(["service_norm", "service"], as_index=False)
        .agg(revenue=("revenue", "sum"), lines=("service", "size"), visits=("visit_key", "nunique"))
        .sort_values("revenue", ascending=False)
    )
    grouped["revenue_share"] = grouped["revenue"] / top10_revenue * 100
    return grouped


def monthly_top10_summary(clean_top: pd.DataFrame, top10: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month, group in top10.groupby("month", sort=True):
        service_rows = clean_top.loc[clean_top["month"].eq(month)]
        top_revenue = float(group["revenue"].sum())
        service_revenue = service_rows.groupby("service_norm")["revenue"].sum()
        rows.append(
            {
                "month": month,
                "month_label": month_label(month),
                "top10_visits": len(group),
                "all_visits": int(monthly.loc[month, "visits"]),
                "top10_revenue": top_revenue,
                "all_revenue": float(monthly.loc[month, "revenue"]),
                "top10_revenue_share": top_revenue / float(monthly.loc[month, "revenue"]) * 100,
                "avg_top10_ticket": float(group["revenue"].mean()),
                "median_top10_ticket": float(group["revenue"].median()),
                "avg_categories": float(group["service_categories"].mean()),
                "avg_service_units": float(group["service_units"].mean()),
                "combo_share": float(group["combo_visit"].mean() * 100),
                "ppf_share": float(service_revenue.get("Антигравийная пленка", 0) / top_revenue * 100),
                "wash_share": float(service_revenue.get("Мойка", 0) / top_revenue * 100),
                "tire_share": float(service_revenue.get("Шиномонтаж", 0) / top_revenue * 100),
                "polish_share": float(service_revenue.get("Полировка", 0) / top_revenue * 100),
                "coating_share": float(service_revenue.get("Керамика / защитные составы", 0) / top_revenue * 100),
            }
        )
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame, columns: list[tuple[str, str, str]], max_rows: int = 20) -> str:
    lines = ["| " + " | ".join(title for _col, title, _kind in columns) + " |"]
    lines.append("|" + "|".join(["---"] * len(columns)) + "|")
    for _, row in df.head(max_rows).iterrows():
        values = []
        for col, _title, kind in columns:
            value = row[col]
            if kind == "money":
                values.append(f"{money(float(value))} ₽")
            elif kind == "int":
                values.append(integer(float(value)))
            elif kind == "pct":
                values.append(pct(float(value), 1))
            elif kind == "num":
                values.append(num(float(value), 2))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(
    visits: pd.DataFrame,
    top10: pd.DataFrame,
    monthly: pd.DataFrame,
    monthly_top: pd.DataFrame,
    categories: pd.DataFrame,
    dominant: pd.DataFrame,
    combos: pd.DataFrame,
    raw_services: pd.DataFrame,
) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    monthly_top.to_csv(MONTHLY_CSV_PATH, index=False, encoding="utf-8-sig")
    categories.to_csv(CATEGORY_CSV_PATH, index=False, encoding="utf-8-sig")
    combos.to_csv(COMBO_CSV_PATH, index=False, encoding="utf-8-sig")
    raw_services.to_csv(RAW_SERVICE_CSV_PATH, index=False, encoding="utf-8-sig")

    top_keys = set(top10["visit_key"])
    regular = visits.loc[~visit_key(visits).isin(top_keys)].copy()
    top_summary = summarize_visit_group("Top-10% визитов каждого месяца", top10)
    regular_summary = summarize_visit_group("Остальные 90% визитов", regular)

    total_revenue = float(visits["revenue"].sum())
    top_revenue = float(top10["revenue"].sum())
    top_visit_share = len(top10) / len(visits) * 100
    top_revenue_share = top_revenue / total_revenue * 100

    ppf = float(categories.loc[categories["service_norm"].eq("Антигравийная пленка"), "revenue_share"].sum())
    wash = float(categories.loc[categories["service_norm"].eq("Мойка"), "revenue_share"].sum())
    tire = float(categories.loc[categories["service_norm"].eq("Шиномонтаж"), "revenue_share"].sum())
    top_one_category_share = float(top10.loc[top10["service_categories"].eq(1), "revenue"].sum() / top_revenue * 100)
    top_combo_revenue_share = float(top10.loc[top10["service_categories"].ge(2), "revenue"].sum() / top_revenue * 100)

    segment_df = pd.DataFrame([top_summary, regular_summary])

    report = f"""# Состав чеков, которые формируют top-10% выручки

Дата расчета: {DATE_TAG}.

Период: {month_label(monthly.index.min())} - {month_label(monthly.index.max())}. Методика та же, что в отчете по среднему чеку: анализ идет с января 2024, исключены автосервис/запчасти, админ/служебные строки и технические клиенты.

Важно: `top-10%` здесь означает верхние 10% самых дорогих визитов внутри каждого месяца, а не top-10% клиентов всей базы.

## Короткий вывод

Top-10% визитов по месяцам = {integer(len(top10))} визитов из {integer(len(visits))}, то есть {pct(top_visit_share, 1)} визитов. Они дали {money(top_revenue)} ₽ из {money(total_revenue)} ₽, то есть {pct(top_revenue_share, 1)} всей выручки анализируемого периода.

Внутри этих чеков крупнейшая категория - антигравийная пленка: {pct(ppf, 1)} выручки top-10%. Мойка дает {pct(wash, 1)} выручки top-10%, шиномонтаж - {pct(tire, 1)}.

По структуре это чаще комплексные визиты: {pct(top_one_category_share, 1)} выручки top-10% дали визиты с одной категорией услуг, {pct(top_combo_revenue_share, 1)} - визиты с 2+ категориями. Но определяет размер чека не само количество позиций, а дорогая главная услуга внутри визита, прежде всего пленка.

## Top-10% против остальных 90%

{markdown_table(segment_df, [
    ("segment", "Сегмент", "text"),
    ("visits", "Визиты", "int"),
    ("revenue", "Выручка", "money"),
    ("avg_ticket", "Средний чек", "money"),
    ("median_ticket", "Медиана", "money"),
    ("avg_service_units", "Услуг/визит", "num"),
    ("avg_categories", "Категорий/визит", "num"),
    ("combo_share", "Комбо %", "pct"),
])}

## Категории услуг внутри top-10%

{markdown_table(categories, [
    ("service_norm", "Категория", "text"),
    ("revenue", "Выручка", "money"),
    ("revenue_share", "Доля выручки", "pct"),
    ("visits", "Визитов", "int"),
    ("service_rows", "Строк услуг", "int"),
], 20)}

## Что является главной категорией чека

`Главная категория` = категория, которая дала максимальную выручку внутри визита.

{markdown_table(dominant, [
    ("dominant_service", "Главная категория", "text"),
    ("visits", "Визитов", "int"),
    ("visit_share", "Доля визитов", "pct"),
    ("revenue", "Выручка", "money"),
    ("revenue_share", "Доля выручки", "pct"),
], 20)}

## Самые частые/денежные комбинации категорий

{markdown_table(combos, [
    ("service_combo", "Комбинация категорий", "text"),
    ("visits", "Визитов", "int"),
    ("visit_share", "Доля визитов", "pct"),
    ("revenue", "Выручка", "money"),
    ("revenue_share", "Доля выручки", "pct"),
    ("avg_ticket", "Средний чек", "money"),
], 20)}

## Самые денежные исходные услуги в 1С

{markdown_table(raw_services, [
    ("service_norm", "Категория", "text"),
    ("service", "Услуга в 1С", "text"),
    ("revenue", "Выручка", "money"),
    ("revenue_share", "Доля top-10%", "pct"),
    ("visits", "Визитов", "int"),
], 25)}

## Помесячно: что внутри top-10%

{markdown_table(monthly_top, [
    ("month_label", "Месяц", "text"),
    ("top10_visits", "Top-визиты", "int"),
    ("top10_revenue", "Top-выручка", "money"),
    ("top10_revenue_share", "Доля месяца", "pct"),
    ("avg_top10_ticket", "Средний top-чек", "money"),
    ("avg_categories", "Категорий/визит", "num"),
    ("combo_share", "Комбо %", "pct"),
    ("ppf_share", "Пленка %", "pct"),
    ("wash_share", "Мойка %", "pct"),
    ("tire_share", "Шины %", "pct"),
], 40)}

## Практический смысл

1. Крупная выручка держится на дорогих заказ-нарядах, а не на массовой глубине чека.
2. Главный драйвер top-10% - пленка. Если поток пленки проседает, средний чек и месячная выручка быстро становятся уязвимыми.
3. В top-10% есть комбо, но комбо не объясняет все. Поэтому KPI менеджеров лучше делить на два слоя: отдельно продажа дорогой базовой услуги, отдельно докрутка второй категории к уже пришедшему клиенту.
4. Для роста устойчивости нужно повышать долю комбо в дорогих чеках: пленка + мойка/уход, пленка + керамика, пленка + салон, пленка + сезонные услуги.

## Файлы с детализацией

- `{os.path.basename(MONTHLY_CSV_PATH)}` - помесячный состав top-10%.
- `{os.path.basename(CATEGORY_CSV_PATH)}` - категории услуг внутри top-10%.
- `{os.path.basename(COMBO_CSV_PATH)}` - комбинации категорий.
- `{os.path.basename(RAW_SERVICE_CSV_PATH)}` - исходные строки услуг внутри top-10%.
"""
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)


def main() -> None:
    rows = base.fetch_sheet()
    long_df = base.parse_to_long(rows)
    clean_df, _source_summary = ticket.clean_source(long_df)
    visits = ticket.build_visit_table(clean_df)
    monthly = ticket.monthly_summary(clean_df, visits)
    ticket.validate(clean_df, visits, monthly)

    visits = visits.copy()
    visits["visit_key"] = visit_key(visits)
    clean_df = clean_df.copy()
    clean_df["visit_key"] = visit_key(clean_df)

    top10 = pick_monthly_top10(visits)
    clean_top = clean_df.loc[clean_df["visit_key"].isin(set(top10["visit_key"]))].copy()
    commercial_top = commercial_clean_top(clean_top, top10)

    top_revenue = float(top10["revenue"].sum())
    categories = category_summary(commercial_top, top_revenue)
    dominant = dominant_summary(top10, top_revenue)
    combos = combo_summary(top10, top_revenue)
    raw_services = raw_service_summary(commercial_top, top_revenue)
    monthly_top = monthly_top10_summary(commercial_top, top10, monthly)

    write_report(visits, top10, monthly, monthly_top, categories, dominant, combos, raw_services)

    print(f"Report: {REPORT_PATH}")
    print(f"Monthly CSV: {MONTHLY_CSV_PATH}")
    print(f"Categories CSV: {CATEGORY_CSV_PATH}")
    print(f"Combos CSV: {COMBO_CSV_PATH}")
    print(f"Raw services CSV: {RAW_SERVICE_CSV_PATH}")
    print(f"Top visits: {len(top10):,}".replace(",", " "))
    print(f"Top revenue: {money(top_revenue)} ₽")


if __name__ == "__main__":
    main()
