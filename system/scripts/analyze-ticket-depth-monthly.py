#!/usr/bin/env python3
"""
Monthly analysis of average ticket size and ticket depth for Levsha.

The script uses the same Google Sheets source and parser as
analyze-detailing-base.py, then builds a visit-level dataset.
"""

from __future__ import annotations

import math
import os
import sys
import warnings
from importlib import import_module
from typing import Iterable

import pandas as pd


warnings.filterwarnings(
    "ignore",
    message=r"You are using a Python version .*",
    category=FutureWarning,
    module=r"google\.api_core\._python_version_support",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

base = import_module("analyze-detailing-base")

OUT_DIR = os.path.join(ROOT, "projects", "detailing-samara", "analytics")
DATE_TAG = "2026-05-20"
REPORT_PATH = os.path.join(OUT_DIR, f"monthly-ticket-depth-{DATE_TAG}.md")
CSV_PATH = os.path.join(OUT_DIR, f"monthly-ticket-depth-{DATE_TAG}.csv")
CHART_DIR_NAME = f"monthly-ticket-depth-{DATE_TAG}"
CHART_DIR = os.path.join(OUT_DIR, "assets", CHART_DIR_NAME)
CHART_REL_DIR = f"assets/{CHART_DIR_NAME}"

ADMIN_LABEL = "Админ / внутреннее / служебное"
ANALYSIS_START_MONTH = "2024-01"
FILM_LABEL = "Антигравийная пленка"
FILM_MATERIAL_SERVICE = "материал пленка"
WASH_LABEL = "Мойка"


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def integer(value: float) -> str:
    return f"{int(value):,}".replace(",", " ")


def num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value: float, digits: int = 1) -> str:
    return f"{num(value, digits)}%"


def month_label(month: str) -> str:
    names = {
        "01": "янв",
        "02": "фев",
        "03": "мар",
        "04": "апр",
        "05": "май",
        "06": "июн",
        "07": "июл",
        "08": "авг",
        "09": "сен",
        "10": "окт",
        "11": "ноя",
        "12": "дек",
    }
    year, month_num = month.split("-")
    return f"{names[month_num]}.{year[-2:]}"


def chart_labels(monthly: pd.DataFrame) -> tuple[list[int], list[str]]:
    x = list(range(len(monthly)))
    labels = [month_label(month) for month in monthly.index]
    return x, labels


def save_chart(fig, filename: str) -> str:
    os.makedirs(CHART_DIR, exist_ok=True)
    output_path = os.path.join(CHART_DIR, filename)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    return f"{CHART_REL_DIR}/{filename}"


def rub_axis(value: float, _pos=None) -> str:
    return f"{value / 1000:,.0f}k".replace(",", " ")


def mln_axis(value: float, _pos=None) -> str:
    return f"{value / 1_000_000:,.0f}".replace(",", " ")


def pct_axis(value: float, _pos=None) -> str:
    return f"{value:.0f}%"


def is_placeholder_client(name: str) -> bool:
    value = str(name or "").strip().lower()
    if not value:
        return True
    if value.startswith("<") and value.endswith(">"):
        return True
    if "продажи без заказа" in value:
        return True
    return False


def clean_source(long_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    df = long_df.copy()
    df["client"] = df["client"].astype(str).str.strip()
    df["service_norm"] = df["service"].apply(base.normalize_service)

    excluded_autoservice = df["service_norm"].eq(base.EXCLUDED_SERVICE_LABEL)
    excluded_admin = df["service_norm"].eq(ADMIN_LABEL)
    excluded_placeholder = df["client"].apply(is_placeholder_client)

    clean_all = df.loc[~excluded_autoservice & ~excluded_admin & ~excluded_placeholder].copy()
    clean_all["month"] = pd.to_datetime(clean_all["date"]).dt.to_period("M").astype(str)
    before_period = clean_all["month"].lt(ANALYSIS_START_MONTH)
    clean = clean_all.loc[~before_period].copy()

    summary = {
        "raw_rows": float(len(df)),
        "raw_revenue": float(df["revenue"].sum()),
        "excluded_total_rows": float(len(df) - len(clean_all)),
        "excluded_autoservice_rows": float(excluded_autoservice.sum()),
        "excluded_admin_rows": float(excluded_admin.sum()),
        "excluded_placeholder_rows": float(excluded_placeholder.sum()),
        "clean_all_rows": float(len(clean_all)),
        "clean_all_revenue": float(clean_all["revenue"].sum()),
        "before_period_rows": float(before_period.sum()),
        "before_period_revenue": float(clean_all.loc[before_period, "revenue"].sum()),
        "clean_rows": float(len(clean)),
        "clean_revenue": float(clean["revenue"].sum()),
    }
    return clean, summary


def build_visit_table(clean_df: pd.DataFrame) -> pd.DataFrame:
    if clean_df.empty:
        raise ValueError("Clean dataset is empty after exclusions.")

    df = clean_df.copy()
    visit_keys = ["client", "order_id", "date"]
    is_film_material = df["service"].astype(str).str.strip().str.lower().eq(FILM_MATERIAL_SERVICE)
    is_film_work = df["service_norm"].eq(FILM_LABEL) & ~is_film_material
    is_film = df["service_norm"].eq(FILM_LABEL)
    is_zero_wash = df["service_norm"].eq(WASH_LABEL) & df["revenue"].eq(0)
    has_film_work_in_visit = is_film_work.groupby([df[key] for key in visit_keys]).transform("any")
    has_film_in_visit = is_film.groupby([df[key] for key in visit_keys]).transform("any")
    df["collapsed_film_material_line"] = is_film_material & has_film_work_in_visit
    df["excluded_zero_film_wash_line"] = is_zero_wash & has_film_in_visit
    df["service_unit_count"] = 1
    df.loc[df["collapsed_film_material_line"], "service_unit_count"] = 0
    df.loc[df["excluded_zero_film_wash_line"], "service_unit_count"] = 0
    commercial_df = df.loc[~df["excluded_zero_film_wash_line"]].copy()

    service_sets = (
        commercial_df.groupby(visit_keys)["service_norm"]
        .agg(lambda values: sorted(set(values)))
        .reset_index(name="services")
    )
    service_revenue = (
        commercial_df.groupby([*visit_keys, "service_norm"], as_index=False)["revenue"]
        .sum()
        .sort_values(["client", "order_id", "date", "revenue"], ascending=[True, True, True, False])
    )
    dominant = service_revenue.drop_duplicates(visit_keys)[
        ["client", "order_id", "date", "service_norm"]
    ].rename(columns={"service_norm": "dominant_service"})

    visits = (
        df.groupby(visit_keys, as_index=False)
        .agg(
            revenue=("revenue", "sum"),
            quantity=("quantity", "sum"),
            service_lines=("service_norm", "size"),
            service_units=("service_unit_count", "sum"),
            collapsed_film_material_lines=("collapsed_film_material_line", "sum"),
            excluded_zero_film_wash_lines=("excluded_zero_film_wash_line", "sum"),
        )
        .merge(service_sets, on=["client", "order_id", "date"], how="left")
        .merge(dominant, on=["client", "order_id", "date"], how="left")
    )
    visits["service_categories"] = visits["services"].apply(len)
    visits["date"] = pd.to_datetime(visits["date"])
    visits["month"] = visits["date"].dt.to_period("M").astype(str)
    visits["combo_visit"] = visits["service_categories"].ge(2)
    visits["deep_line_visit"] = visits["service_lines"].ge(3)
    visits["deep_service_visit"] = visits["service_units"].ge(3)
    visits["avg_line_revenue"] = visits["revenue"] / visits["service_lines"].where(
        visits["service_lines"].gt(0), pd.NA
    )
    visits["avg_service_revenue"] = visits["revenue"] / visits["service_units"].where(
        visits["service_units"].gt(0), pd.NA
    )
    return visits


def top_share(values: pd.Series, share: float = 0.1) -> float:
    if values.empty or values.sum() == 0:
        return 0.0
    count = max(1, math.ceil(len(values) * share))
    return float(values.nlargest(count).sum() / values.sum() * 100)


def safe_share(part: float, total: float) -> float:
    if total == 0:
        return 0.0
    return float(part / total * 100)


def monthly_summary(clean_df: pd.DataFrame, visits: pd.DataFrame) -> pd.DataFrame:
    grouped = visits.groupby("month")
    monthly = grouped.agg(
        visits=("order_id", "size"),
        clients=("client", "nunique"),
        revenue=("revenue", "sum"),
        avg_ticket=("revenue", "mean"),
        median_ticket=("revenue", "median"),
        p75_ticket=("revenue", lambda s: s.quantile(0.75)),
        p90_ticket=("revenue", lambda s: s.quantile(0.90)),
        service_lines=("service_lines", "sum"),
        service_units=("service_units", "sum"),
        collapsed_film_material_lines=("collapsed_film_material_lines", "sum"),
        excluded_zero_film_wash_lines=("excluded_zero_film_wash_lines", "sum"),
        avg_service_lines=("service_lines", "mean"),
        avg_service_units=("service_units", "mean"),
        avg_categories=("service_categories", "mean"),
        combo_visits=("combo_visit", "sum"),
        deep_line_visits=("deep_line_visit", "sum"),
        deep_service_visits=("deep_service_visit", "sum"),
        avg_line_revenue=("avg_line_revenue", "mean"),
        avg_service_revenue=("avg_service_revenue", "mean"),
    )
    monthly["combo_share"] = monthly["combo_visits"] / monthly["visits"] * 100
    monthly["deep_line_share"] = monthly["deep_line_visits"] / monthly["visits"] * 100
    monthly["deep_service_share"] = monthly["deep_service_visits"] / monthly["visits"] * 100
    monthly["top10_revenue_share"] = grouped["revenue"].apply(top_share)

    category_revenue = clean_df.groupby(["month", "service_norm"])["revenue"].sum().unstack(fill_value=0)
    for label, column in [
        (FILM_LABEL, "ppf_revenue_share"),
        ("Мойка", "wash_revenue_share"),
        ("Полировка", "polish_revenue_share"),
        ("Шиномонтаж", "tire_revenue_share"),
        ("Керамика / защитные составы", "coating_revenue_share"),
    ]:
        values = category_revenue[label] if label in category_revenue.columns else pd.Series(0, index=monthly.index)
        monthly[column] = [
            safe_share(float(values.get(month, 0)), float(monthly.loc[month, "revenue"]))
            for month in monthly.index
        ]

    monthly = monthly.sort_index()
    monthly["avg_ticket_yoy"] = pd.NA
    monthly["revenue_yoy"] = pd.NA
    for month in monthly.index:
        year, month_num = month.split("-")
        previous = f"{int(year) - 1}-{month_num}"
        if previous in monthly.index:
            prev_avg = monthly.loc[previous, "avg_ticket"]
            prev_rev = monthly.loc[previous, "revenue"]
            if prev_avg:
                monthly.loc[month, "avg_ticket_yoy"] = (monthly.loc[month, "avg_ticket"] / prev_avg - 1) * 100
            if prev_rev:
                monthly.loc[month, "revenue_yoy"] = (monthly.loc[month, "revenue"] / prev_rev - 1) * 100
    return monthly


def validate(clean_df: pd.DataFrame, visits: pd.DataFrame, monthly: pd.DataFrame) -> list[str]:
    checks: list[str] = []

    if clean_df.empty:
        raise AssertionError("No clean service rows.")
    if visits.empty:
        raise AssertionError("No visit rows.")
    if monthly.empty:
        raise AssertionError("No monthly rows.")

    clean_revenue = float(clean_df["revenue"].sum())
    visit_revenue = float(visits["revenue"].sum())
    monthly_revenue = float(monthly["revenue"].sum())
    if abs(clean_revenue - visit_revenue) > 0.01:
        raise AssertionError(f"Clean/visit revenue mismatch: {clean_revenue} vs {visit_revenue}")
    if abs(visit_revenue - monthly_revenue) > 0.01:
        raise AssertionError(f"Visit/monthly revenue mismatch: {visit_revenue} vs {monthly_revenue}")

    if int(visits["service_lines"].sum()) != int(len(clean_df)):
        raise AssertionError("Service line count mismatch between clean rows and visits.")
    collapsed_lines = int(visits["collapsed_film_material_lines"].sum())
    zero_film_wash_lines = int(visits["excluded_zero_film_wash_lines"].sum())
    if int(visits["service_units"].sum() + collapsed_lines + zero_film_wash_lines) != int(len(clean_df)):
        raise AssertionError("Adjusted service count mismatch after film-material collapse.")
    if int(monthly["visits"].sum()) != int(len(visits)):
        raise AssertionError("Visit count mismatch between visits and monthly summary.")
    if clean_df["date"].isna().any() or visits["date"].isna().any():
        raise AssertionError("Found empty dates.")
    if (visits["revenue"] < 0).any():
        raise AssertionError("Found negative visit revenue.")

    checks.append(f"Выручка строк услуг = выручка визитов = выручка месяцев: {money(clean_revenue)} ₽")
    checks.append(f"Строки услуг в чистой базе = сумма строк услуг в визитах: {len(clean_df):,}".replace(",", " "))
    checks.append(
        f"Схлопнуто строк `Материал Пленка` внутри плёночных визитов: {collapsed_lines:,}".replace(",", " ")
    )
    checks.append(
        f"Исключено нулевых строк мойки внутри плёночных визитов из услуг/комбо: {zero_film_wash_lines:,}".replace(",", " ")
    )
    checks.append(
        f"Скорректированных услуг после схлопывания/исключения: {int(visits['service_units'].sum()):,}".replace(",", " ")
    )
    checks.append(f"Визиты в таблице = сумма визитов по месяцам: {len(visits):,}".replace(",", " "))
    checks.append(
        f"Период: {month_label(monthly.index.min())} - {month_label(monthly.index.max())}, месяцев: {len(monthly)}"
    )
    return checks


def markdown_table(monthly: pd.DataFrame) -> str:
    headers = [
        "Месяц",
        "Визиты",
        "Выручка",
        "Средний чек",
        "Медиана",
        "P90",
        "Услуг/визит",
        "Строк/визит",
        "Категорий/визит",
        "Комбо %",
        "Top10% выручки",
        "Пленка %",
    ]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for month, row in monthly.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    month_label(month),
                    str(int(row["visits"])),
                    f"{money(row['revenue'])} ₽",
                    f"{money(row['avg_ticket'])} ₽",
                    f"{money(row['median_ticket'])} ₽",
                    f"{money(row['p90_ticket'])} ₽",
                    num(row["avg_service_units"], 2),
                    num(row["avg_service_lines"], 2),
                    num(row["avg_categories"], 2),
                    pct(row["combo_share"], 1),
                    pct(row["top10_revenue_share"], 1),
                    pct(row["ppf_revenue_share"], 1),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def format_period_summary(label: str, frame: pd.DataFrame) -> str:
    visits = int(frame["visits"].sum())
    revenue = float(frame["revenue"].sum())
    avg_ticket = revenue / visits if visits else 0
    weighted_units = float((frame["avg_service_units"] * frame["visits"]).sum() / visits) if visits else 0
    weighted_lines = float((frame["avg_service_lines"] * frame["visits"]).sum() / visits) if visits else 0
    weighted_categories = float((frame["avg_categories"] * frame["visits"]).sum() / visits) if visits else 0
    combo_share = float(frame["combo_visits"].sum() / visits * 100) if visits else 0
    return (
        f"- {label}: {integer(visits)} визитов, {money(revenue)} ₽ выручки, "
        f"средний чек {money(avg_ticket)} ₽, услуг/визит {num(weighted_units, 2)} "
        f"(строк/визит до схлопывания {num(weighted_lines, 2)}), "
        f"категорий/визит {num(weighted_categories, 2)}, комбо {pct(combo_share, 1)}."
    )


def top_months(frame: pd.DataFrame, metric: str, count: int = 5, ascending: bool = False) -> str:
    rows = []
    for month, row in frame.sort_values(metric, ascending=ascending).head(count).iterrows():
        value = row[metric]
        if metric.endswith("share") or metric.endswith("yoy"):
            rendered = pct(float(value), 1)
        elif "ticket" in metric or metric == "revenue":
            rendered = f"{money(float(value))} ₽"
        else:
            rendered = num(float(value), 2)
        rows.append(f"{month_label(month)}: {rendered}")
    return "; ".join(rows)


def render_charts(monthly: pd.DataFrame) -> list[tuple[str, str]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 16,
            "axes.labelsize": 10,
            "axes.edgecolor": "#ccd3dc",
            "axes.linewidth": 0.8,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "xtick.color": "#56616f",
            "ytick.color": "#56616f",
        }
    )

    x, labels = chart_labels(monthly)
    tick_step = 2 if len(labels) > 18 else 1
    ticks = x[::tick_step]
    tick_labels = labels[::tick_step]

    def polish_axis(ax):
        ax.grid(axis="y", color="#e8edf3", linewidth=0.9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xticks(ticks)
        ax.set_xticklabels(tick_labels, rotation=45, ha="right")

    charts: list[tuple[str, str]] = []

    fig, ax = plt.subplots(figsize=(13.5, 6))
    ax.plot(x, monthly["avg_ticket"], color="#1f77b4", linewidth=2.6, marker="o", markersize=4, label="Средний чек")
    ax.plot(x, monthly["median_ticket"], color="#2ca02c", linewidth=2.2, marker="o", markersize=3.5, label="Медиана")
    ax.plot(x, monthly["p90_ticket"], color="#ff7f0e", linewidth=2.2, marker="o", markersize=3.5, label="P90")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(rub_axis))
    ax.set_ylabel("руб., тыс.")
    ax.set_title("Величина чека: средний, медиана и P90")
    polish_axis(ax)
    ax.legend(ncol=3, frameon=False, loc="upper left")
    charts.append(("Величина чека", save_chart(fig, "01-ticket-size-trend.png")))
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(13.5, 8), sharex=True, gridspec_kw={"height_ratios": [1.1, 1]})
    axes[0].plot(
        x,
        monthly["avg_service_units"],
        color="#1f77b4",
        linewidth=2.5,
        marker="o",
        markersize=4,
        label="Услуг / визит",
    )
    axes[0].plot(
        x,
        monthly["avg_service_lines"],
        color="#6b7280",
        linewidth=1.8,
        linestyle="--",
        marker="o",
        markersize=3,
        alpha=0.75,
        label="Строк 1С / визит",
    )
    axes[0].plot(
        x,
        monthly["avg_categories"],
        color="#9467bd",
        linewidth=2.5,
        marker="o",
        markersize=4,
        label="Категорий / визит",
    )
    axes[0].set_ylabel("среднее на визит")
    axes[0].set_title("Глубина чека: услуги после схлопывания материала пленки")
    polish_axis(axes[0])
    axes[0].legend(ncol=3, frameon=False, loc="upper right")

    axes[1].plot(
        x,
        monthly["combo_share"],
        color="#2ca02c",
        linewidth=2.5,
        marker="o",
        markersize=4,
        label="Комбо-визиты, 2+ категории",
    )
    axes[1].plot(
        x,
        monthly["deep_service_share"],
        color="#ff7f0e",
        linewidth=2.5,
        marker="o",
        markersize=4,
        label="Визиты с 3+ услугами",
    )
    axes[1].yaxis.set_major_formatter(mtick.FuncFormatter(pct_axis))
    axes[1].set_ylabel("доля визитов")
    polish_axis(axes[1])
    axes[1].legend(ncol=2, frameon=False, loc="upper right")
    charts.append(("Глубина чека", save_chart(fig, "02-ticket-depth-trend.png")))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13.5, 6))
    ax.bar(x, monthly["revenue"], color="#7aa6c2", alpha=0.78, label="Выручка")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(mln_axis))
    ax.set_ylabel("выручка, млн ₽")
    ax2 = ax.twinx()
    ax2.plot(x, monthly["visits"], color="#d62728", linewidth=2.5, marker="o", markersize=4, label="Визиты")
    ax2.set_ylabel("визиты")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color("#ccd3dc")
    ax.set_title("Объем: выручка и количество визитов")
    polish_axis(ax)
    lines, labels_1 = ax.get_legend_handles_labels()
    lines2, labels_2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels_1 + labels_2, ncol=2, frameon=False, loc="upper left")
    charts.append(("Выручка и визиты", save_chart(fig, "03-revenue-visits-trend.png")))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13.5, 6))
    ax.plot(
        x,
        monthly["top10_revenue_share"],
        color="#d62728",
        linewidth=2.6,
        marker="o",
        markersize=4,
        label="Доля выручки top-10% чеков",
    )
    ax.plot(
        x,
        monthly["ppf_revenue_share"],
        color="#1f77b4",
        linewidth=2.4,
        marker="o",
        markersize=4,
        label="Доля пленки в выручке",
    )
    ax.plot(
        x,
        monthly["wash_revenue_share"],
        color="#2ca02c",
        linewidth=2.1,
        marker="o",
        markersize=3.5,
        label="Доля мойки в выручке",
    )
    ax.plot(
        x,
        monthly["tire_revenue_share"],
        color="#ff7f0e",
        linewidth=2.1,
        marker="o",
        markersize=3.5,
        label="Доля шиномонтажа в выручке",
    )
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(pct_axis))
    ax.set_ylabel("доля месячной выручки")
    ax.set_title("Микс и концентрация: что двигает средний чек")
    polish_axis(ax)
    ax.legend(ncol=2, frameon=False, loc="upper left")
    charts.append(("Микс и концентрация", save_chart(fig, "04-mix-concentration-trend.png")))
    plt.close(fig)

    yoy = monthly.loc[monthly["avg_ticket_yoy"].notna()].copy()
    if not yoy.empty:
        x_yoy, labels_yoy = chart_labels(yoy)
        width = 0.38
        fig, ax = plt.subplots(figsize=(13.5, 6))
        ax.bar(
            [i - width / 2 for i in x_yoy],
            yoy["avg_ticket_yoy"].astype(float),
            width=width,
            color="#1f77b4",
            alpha=0.82,
            label="Средний чек YoY",
        )
        ax.bar(
            [i + width / 2 for i in x_yoy],
            yoy["revenue_yoy"].astype(float),
            width=width,
            color="#ff7f0e",
            alpha=0.82,
            label="Выручка YoY",
        )
        ax.axhline(0, color="#6b7280", linewidth=1.0)
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(pct_axis))
        ax.set_ylabel("изменение к тому же месяцу прошлого года")
        ax.set_title("YoY-динамика: средний чек и выручка")
        ax.grid(axis="y", color="#e8edf3", linewidth=0.9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xticks(x_yoy)
        ax.set_xticklabels(labels_yoy, rotation=45, ha="right")
        ax.legend(ncol=2, frameon=False, loc="upper left")
        charts.append(("YoY-динамика", save_chart(fig, "05-yoy-trend.png")))
        plt.close(fig)

    return charts


def write_outputs(
    monthly: pd.DataFrame,
    clean_df: pd.DataFrame,
    visits: pd.DataFrame,
    source_summary: dict[str, float],
    checks: Iterable[str],
) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    monthly_export = monthly.reset_index().rename(columns={"index": "month"})
    monthly_export.insert(1, "month_label", monthly_export["month"].apply(month_label))
    monthly_export.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    chart_paths = render_charts(monthly)
    charts_md = "\n\n".join(f"![{title}]({path})" for title, path in chart_paths)

    last_12 = monthly.tail(12)
    previous_12 = monthly.iloc[-24:-12] if len(monthly) >= 24 else pd.DataFrame()
    latest_month = monthly.index.max()
    latest = monthly.loc[latest_month]
    date_min = pd.to_datetime(clean_df["date"]).min()
    date_max = pd.to_datetime(clean_df["date"]).max()
    month_end = date_max + pd.offsets.MonthEnd(0)
    latest_month_note = ""
    if date_max.date() != month_end.date():
        latest_month_note = (
            f"\n\nВажно: {month_label(latest_month)} в выгрузке неполный, "
            f"последняя дата данных {date_max.strftime('%d.%m.%Y')}."
        )

    checks_md = "\n".join(f"- {line}" for line in checks)
    summary_lines = [
        format_period_summary("Весь анализируемый период", monthly),
        format_period_summary("Последние 12 месяцев", last_12),
    ]
    if not previous_12.empty:
        summary_lines.append(format_period_summary("Предыдущие 12 месяцев", previous_12))

    avg_ticket_last12 = float(last_12["revenue"].sum() / last_12["visits"].sum())
    avg_ticket_all = float(monthly["revenue"].sum() / monthly["visits"].sum())
    median_last12 = float(
        visits.loc[visits["month"].isin(last_12.index), "revenue"].median()
    )
    combo_last12 = float(last_12["combo_visits"].sum() / last_12["visits"].sum() * 100)
    ppf_last12 = float(
        clean_df.loc[
            clean_df["month"].isin(last_12.index)
            & clean_df["service_norm"].eq(FILM_LABEL),
            "revenue",
        ].sum()
        / last_12["revenue"].sum()
        * 100
    )

    collapsed_total = int(monthly["collapsed_film_material_lines"].sum())
    collapsed_last12 = int(last_12["collapsed_film_material_lines"].sum())
    zero_wash_total = int(monthly["excluded_zero_film_wash_lines"].sum())
    zero_wash_last12 = int(last_12["excluded_zero_film_wash_lines"].sum())

    report = f"""# Помесячный анализ среднего чека и глубины чека Левши

Дата расчета: {DATE_TAG}.

Источник: выгрузка 1С `Продажи по заказам`, та же таблица Google Sheets, что используется в базовом анализе клиентской базы.

Период данных в анализе: {date_min.strftime('%d.%m.%Y')} - {date_max.strftime('%d.%m.%Y')}.

Анализ считаем с {month_label(ANALYSIS_START_MONTH)}, потому что до этого был переход на 1С и исторические данные могли быть неполными.

## Методика

Единица анализа: один визит = один `Заказ-наряд` клиента в конкретную дату.

Из анализа исключены:
- автосервис и запчасти;
- административные, внутренние и служебные строки;
- технические клиенты и строки вида `<Продажи без заказа>`.

Что считаем:
- величина среднего чека: выручка визита, среднее по месяцу;
- медиана и P90: чтобы видеть, держится ли рост на массе клиентов или на крупных чеках;
- глубина чека: среднее количество услуг и уникальных категорий услуг в одном визите;
- `услуг/визит`: скорректированная метрика, где строка `Материал Пленка` не считается отдельной услугой, если в том же заказ-наряде есть работа по плёнке;
- нулевая мойка внутри плёночного заказ-наряда не считается отдельной услугой, категорией или комбо; она остаётся только в сырых строках 1С;
- `строк/визит`: сырое количество строк 1С до схлопывания материала плёнки;
- комбо-визит: визит, где было 2+ уникальные категории услуг;
- Top10% выручки: доля месячной выручки, которую дали 10% самых дорогих визитов.

## Контроль качества данных

{checks_md}

Сырые строки услуг: {integer(source_summary["raw_rows"])}.
Всего исключено строк по объединению признаков: {integer(source_summary["excluded_total_rows"])}.
Строк с признаком автосервиса/запчастей: {integer(source_summary["excluded_autoservice_rows"])}.
Строк с признаком админ/служебных операций: {integer(source_summary["excluded_admin_rows"])}.
Строк с признаком технического клиента: {integer(source_summary["excluded_placeholder_rows"])}.
Признаки могут пересекаться, поэтому отдельные счетчики не складываются в общий счетчик исключений.
Чистых строк после исключений во всей выгрузке: {integer(source_summary["clean_all_rows"])}.
Исключено из анализа до {month_label(ANALYSIS_START_MONTH)}: {integer(source_summary["before_period_rows"])} строк на {money(source_summary["before_period_revenue"])} ₽.
Осталось чистых строк услуг в анализе: {integer(source_summary["clean_rows"])}.
Всего схлопнуто строк `Материал Пленка`: {integer(collapsed_total)}, из них за последние 12 месяцев: {integer(collapsed_last12)}.
Всего исключено нулевых строк мойки внутри плёночных визитов из услуг/комбо: {integer(zero_wash_total)}, из них за последние 12 месяцев: {integer(zero_wash_last12)}.

## Короткий вывод

{chr(10).join(summary_lines)}

Последние 12 месяцев: средний чек {money(avg_ticket_last12)} ₽ против {money(avg_ticket_all)} ₽ по всей чистой базе. Медианный визит за последние 12 месяцев: {money(median_last12)} ₽. Комбо-визитов за последние 12 месяцев: {pct(combo_last12, 1)}. Доля пленки в выручке последних 12 месяцев: {pct(ppf_last12, 1)}.

Последний месяц в выгрузке: {month_label(latest_month)}. В нем {integer(latest["visits"])} визитов, выручка {money(latest["revenue"])} ₽, средний чек {money(latest["avg_ticket"])} ₽, медиана {money(latest["median_ticket"])} ₽, комбо-визиты {pct(latest["combo_share"], 1)}.{latest_month_note}

## Где чек был самым высоким

За анализируемый период: {top_months(monthly, "avg_ticket")}.

## Где чек был самым глубоким

По скорректированным услугам в визите: {top_months(monthly, "avg_service_units")}.

По количеству категорий в визите: {top_months(monthly, "avg_categories")}.

По доле комбо-визитов: {top_months(monthly, "combo_share")}.

## Как читать динамику

Если средний чек растет, а медиана и глубина не растут, рост идет за счет дорогих визитов: пленка, крупные комплексы, единичные большие заказы. Это хорошо для выручки, но не доказывает, что менеджеры стали лучше докручивать массовые визиты.

Если растут `услуг/визит`, `категорий/визит` и `комбо %`, это уже признак настоящего роста глубины чека: к базовой услуге добавляют вторую и третью потребность. `Строк/визит` используем только как контроль 1С-детализации, потому что материал плёнки может создавать техническую строку без новой услуги.

Если растет `Top10% выручки`, значит месяц сильнее зависит от крупных чеков. Для управляемости лучше отдельно смотреть массовый чек через медиану и отдельно дорогие продажи через P90.

## Графики трендов

{charts_md}

## Помесячная таблица

{markdown_table(monthly)}
"""
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)


def main() -> None:
    rows = base.fetch_sheet()
    long_df = base.parse_to_long(rows)
    clean_df, source_summary = clean_source(long_df)
    visits = build_visit_table(clean_df)
    monthly = monthly_summary(clean_df, visits)
    checks = validate(clean_df, visits, monthly)
    write_outputs(monthly, clean_df, visits, source_summary, checks)

    print(f"Report: {REPORT_PATH}")
    print(f"CSV: {CSV_PATH}")
    for line in checks:
        print(f"OK: {line}")


if __name__ == "__main__":
    main()
