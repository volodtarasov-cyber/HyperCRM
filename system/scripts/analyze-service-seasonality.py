#!/usr/bin/env python3
"""
Service seasonality analysis for Levsha.

Seasonality is calculated on full years 2024-2025. 2026 is kept as YTD
context only, because the source data currently ends in April 2026.
"""

from __future__ import annotations

import os
import sys
import warnings
from importlib import import_module

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
ticket = import_module("analyze-ticket-depth-monthly")

OUT_DIR = os.path.join(ROOT, "projects", "detailing-samara", "analytics")
REPORT_PATH = os.path.join(OUT_DIR, "service-seasonality-2026-05-19.md")
SUMMARY_CSV_PATH = os.path.join(OUT_DIR, "service-seasonality-summary-2026-05-19.csv")
MONTHLY_CSV_PATH = os.path.join(OUT_DIR, "service-seasonality-monthly-2026-05-19.csv")
CALENDAR_CSV_PATH = os.path.join(OUT_DIR, "service-seasonality-calendar-2026-05-19.csv")
CHART_DIR_NAME = "service-seasonality-2026-05-19"
CHART_DIR = os.path.join(OUT_DIR, "assets", CHART_DIR_NAME)
CHART_REL_DIR = f"assets/{CHART_DIR_NAME}"

FULL_YEARS = [2024, 2025]
TOP_SERVICE_COUNT = 10
MARKETING_EXCLUDED_SERVICES = {
    "Прочее",
    "Товары / материалы",
    "Арматурные работы / с-у",
    "Дооснащение / установка оборудования",
}

MONTH_NAMES = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "май",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def integer(value: float) -> str:
    return f"{int(value):,}".replace(",", " ")


def num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value: float, digits: int = 1) -> str:
    return f"{num(value, digits)}%"


def service_short(name: str) -> str:
    replacements = {
        "Антигравийная пленка": "Пленка",
        "Полировка + защитные составы": "Полировка/защита",
        "Шумовиброизоляция": "Шумка",
        "Дооснащение / установка оборудования": "Дооснащение",
        "Арматурные работы / с-у": "Арматурка",
    }
    return replacements.get(name, name)


def visit_key(df: pd.DataFrame) -> pd.Series:
    return (
        df["client"].astype(str)
        + "||"
        + df["order_id"].astype(str)
        + "||"
        + pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    )


def save_chart(fig, filename: str) -> str:
    os.makedirs(CHART_DIR, exist_ok=True)
    output_path = os.path.join(CHART_DIR, filename)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    return f"{CHART_REL_DIR}/{filename}"


def mln_axis(value: float, _pos=None) -> str:
    return f"{value / 1_000_000:,.1f}".replace(".", ",")


def build_monthly(clean_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = clean_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month_num"] = df["date"].dt.month
    df["month_name"] = df["month_num"].map(MONTH_NAMES)
    df["visit_key"] = visit_key(df)

    monthly_raw = (
        df.groupby(["year", "month_num", "month_name", "service_norm"], as_index=False)
        .agg(
            revenue=("revenue", "sum"),
            service_lines=("service_norm", "size"),
            visits=("visit_key", "nunique"),
            clients=("client", "nunique"),
        )
    )

    full_services = sorted(monthly_raw.loc[monthly_raw["year"].isin(FULL_YEARS), "service_norm"].unique())
    grid = pd.MultiIndex.from_product(
        [FULL_YEARS, range(1, 13), full_services],
        names=["year", "month_num", "service_norm"],
    ).to_frame(index=False)
    grid["month_name"] = grid["month_num"].map(MONTH_NAMES)

    full_monthly = grid.merge(
        monthly_raw.loc[monthly_raw["year"].isin(FULL_YEARS)],
        on=["year", "month_num", "month_name", "service_norm"],
        how="left",
    )
    for col in ["revenue", "service_lines", "visits", "clients"]:
        full_monthly[col] = full_monthly[col].fillna(0)

    ytd_2026 = monthly_raw.loc[monthly_raw["year"].eq(2026)].copy()
    monthly = pd.concat([full_monthly, ytd_2026], ignore_index=True, sort=False)

    annual = (
        full_monthly.groupby(["year", "service_norm"], as_index=False)["revenue"]
        .sum()
        .rename(columns={"revenue": "annual_revenue"})
    )
    monthly = monthly.merge(annual, on=["year", "service_norm"], how="left")
    monthly["year_share"] = monthly["revenue"] / monthly["annual_revenue"].where(
        monthly["annual_revenue"].gt(0), pd.NA
    ) * 100
    monthly["seasonality_index"] = monthly["year_share"] / (100 / 12)
    monthly["month_label"] = monthly["month_num"].map(MONTH_NAMES)
    return monthly, full_services


def build_summary(monthly: pd.DataFrame, clean_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    full = monthly.loc[monthly["year"].isin(FULL_YEARS)].copy()
    service_totals = (
        full.groupby("service_norm", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
        .rename(columns={"revenue": "revenue_2024_2025"})
    )
    top_services = [
        service
        for service in service_totals["service_norm"].tolist()
        if service not in MARKETING_EXCLUDED_SERVICES
    ][:TOP_SERVICE_COUNT]

    seasonal = (
        full.groupby(["service_norm", "month_num", "month_name"], as_index=False)
        .agg(
            avg_revenue=("revenue", "mean"),
            avg_year_share=("year_share", "mean"),
            avg_seasonality_index=("seasonality_index", "mean"),
            min_year_share=("year_share", "min"),
            max_year_share=("year_share", "max"),
        )
    )

    annual_pivot = (
        full.groupby(["service_norm", "year"])["revenue"]
        .sum()
        .unstack(fill_value=0)
        .rename(columns={2024: "revenue_2024", 2025: "revenue_2025"})
    )
    ytd_2026 = (
        clean_df.loc[pd.to_datetime(clean_df["date"]).dt.year.eq(2026)]
        .groupby("service_norm")["revenue"]
        .sum()
        .rename("revenue_2026_ytd")
    )

    rows = []
    for service in service_totals["service_norm"]:
        service_months = seasonal.loc[seasonal["service_norm"].eq(service)].sort_values(
            "avg_seasonality_index", ascending=False
        )
        peak = service_months.iloc[0]
        weak = service_months.iloc[-1]
        top3 = ", ".join(service_months.head(3)["month_name"].tolist())
        low3 = ", ".join(service_months.tail(3).sort_values("month_num")["month_name"].tolist())
        revenue_2024 = float(annual_pivot.loc[service, "revenue_2024"]) if service in annual_pivot.index else 0
        revenue_2025 = float(annual_pivot.loc[service, "revenue_2025"]) if service in annual_pivot.index else 0
        revenue_2026 = float(ytd_2026.get(service, 0))
        rows.append(
            {
                "service_norm": service,
                "revenue_2024_2025": float(service_totals.loc[service_totals["service_norm"].eq(service), "revenue_2024_2025"].iloc[0]),
                "revenue_2024": revenue_2024,
                "revenue_2025": revenue_2025,
                "revenue_2026_ytd": revenue_2026,
                "peak_month": peak["month_name"],
                "peak_index": float(peak["avg_seasonality_index"]),
                "peak_year_share": float(peak["avg_year_share"]),
                "weak_month": weak["month_name"],
                "weak_index": float(weak["avg_seasonality_index"]),
                "weak_year_share": float(weak["avg_year_share"]),
                "top3_months": top3,
                "low3_months": low3,
                "revenue_change_2025_vs_2024": (revenue_2025 / revenue_2024 - 1) * 100 if revenue_2024 else pd.NA,
            }
        )

    summary = pd.DataFrame(rows)
    summary = summary.sort_values("revenue_2024_2025", ascending=False)
    return summary, top_services, seasonal


def build_calendar(seasonal: pd.DataFrame, top_services: list[str]) -> pd.DataFrame:
    scoped = seasonal.loc[seasonal["service_norm"].isin(top_services)].copy()
    rows = []
    for month_num in range(1, 13):
        month_data = scoped.loc[scoped["month_num"].eq(month_num)].copy()
        hot = month_data.sort_values(["avg_seasonality_index", "avg_revenue"], ascending=False).head(4)
        money_leaders = month_data.sort_values("avg_revenue", ascending=False).head(4)
        cold = month_data.sort_values(["avg_seasonality_index", "avg_revenue"], ascending=[True, False]).head(4)
        rows.append(
            {
                "month_num": month_num,
                "month_name": MONTH_NAMES[month_num],
                "seasonal_focus": "; ".join(
                    f"{service_short(row.service_norm)} ({num(row.avg_seasonality_index, 1)}x)"
                    for row in hot.itertuples()
                ),
                "revenue_leaders": "; ".join(
                    f"{service_short(row.service_norm)} ({money(row.avg_revenue)} ₽)"
                    for row in money_leaders.itertuples()
                ),
                "weak_services": "; ".join(
                    f"{service_short(row.service_norm)} ({num(row.avg_seasonality_index, 1)}x)"
                    for row in cold.itertuples()
                ),
            }
        )
    return pd.DataFrame(rows)


def render_charts(summary: pd.DataFrame, seasonal: pd.DataFrame, top_services: list[str]) -> list[tuple[str, str]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick
    import numpy as np

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

    charts: list[tuple[str, str]] = []
    scoped = seasonal.loc[seasonal["service_norm"].isin(top_services)].copy()
    heat = scoped.pivot(index="service_norm", columns="month_num", values="avg_seasonality_index").loc[top_services]
    heat.columns = [MONTH_NAMES[int(col)] for col in heat.columns]
    heat.index = [service_short(value) for value in heat.index]

    fig, ax = plt.subplots(figsize=(14, 8))
    image = ax.imshow(heat.values, cmap="YlOrRd", vmin=0, vmax=max(2.2, float(np.nanmax(heat.values))))
    ax.set_title("Сезонный индекс по услугам: 1,0x = обычный месяц")
    ax.set_xticks(range(len(heat.columns)))
    ax.set_xticklabels(heat.columns)
    ax.set_yticks(range(len(heat.index)))
    ax.set_yticklabels(heat.index)
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            value = heat.iloc[i, j]
            ax.text(j, i, num(value, 1), ha="center", va="center", color="#20242a", fontsize=8)
    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("индекс")
    charts.append(("Тепловая карта сезонности", save_chart(fig, "01-seasonality-heatmap.png")))
    plt.close(fig)

    top6 = top_services[:6]
    fig, ax = plt.subplots(figsize=(13.5, 6.5))
    for service in top6:
        line = scoped.loc[scoped["service_norm"].eq(service)].sort_values("month_num")
        ax.plot(
            line["month_num"],
            line["avg_revenue"],
            marker="o",
            linewidth=2.3,
            markersize=4,
            label=service_short(service),
        )
    ax.set_title("Средняя выручка по месяцам, 2024-2025")
    ax.set_ylabel("млн ₽")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(mln_axis))
    ax.grid(axis="y", color="#e8edf3", linewidth=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([MONTH_NAMES[i] for i in range(1, 13)])
    ax.legend(ncol=3, frameon=False, loc="upper left")
    charts.append(("Средняя выручка топ-услуг", save_chart(fig, "02-top-services-monthly-revenue.png")))
    plt.close(fig)

    top10 = summary.head(10).iloc[::-1].copy()
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh([service_short(s) for s in top10["service_norm"]], top10["revenue_2024_2025"], color="#2b7bbb", alpha=0.86)
    ax.set_title("Топ услуг по выручке за 2024-2025")
    ax.set_xlabel("млн ₽")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(mln_axis))
    ax.grid(axis="x", color="#e8edf3", linewidth=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    charts.append(("Топ услуг по выручке", save_chart(fig, "03-service-revenue-ranking.png")))
    plt.close(fig)

    return charts


def markdown_table(df: pd.DataFrame, columns: list[tuple[str, str, str]], max_rows: int = 30) -> str:
    lines = ["| " + " | ".join(title for _col, title, _kind in columns) + " |"]
    lines.append("|" + "|".join(["---"] * len(columns)) + "|")
    for _, row in df.head(max_rows).iterrows():
        values = []
        for col, _title, kind in columns:
            value = row[col]
            if kind == "money":
                values.append(f"{money(float(value))} ₽")
            elif kind == "pct":
                values.append(pct(float(value), 1) if pd.notna(value) else "")
            elif kind == "num":
                values.append(num(float(value), 2) if pd.notna(value) else "")
            elif kind == "index":
                values.append(f"{num(float(value), 1)}x" if pd.notna(value) else "")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def validate(clean_df: pd.DataFrame, monthly: pd.DataFrame) -> list[str]:
    full = monthly.loc[monthly["year"].isin(FULL_YEARS)]
    source_full_revenue = float(
        clean_df.loc[pd.to_datetime(clean_df["date"]).dt.year.isin(FULL_YEARS), "revenue"].sum()
    )
    monthly_full_revenue = float(full["revenue"].sum())
    if abs(source_full_revenue - monthly_full_revenue) > 0.01:
        raise AssertionError(f"Revenue mismatch: {source_full_revenue} vs {monthly_full_revenue}")

    checks = [
        f"Период сезонности: {FULL_YEARS[0]}-{FULL_YEARS[-1]}, полные годы.",
        f"Выручка строк услуг за 2024-2025 = помесячная выручка: {money(source_full_revenue)} ₽.",
        f"2026 используется только как YTD-контекст: данные до {pd.to_datetime(clean_df['date']).max():%d.%m.%Y}.",
    ]
    return checks


def write_report(
    clean_df: pd.DataFrame,
    monthly: pd.DataFrame,
    summary: pd.DataFrame,
    seasonal: pd.DataFrame,
    calendar: pd.DataFrame,
    charts: list[tuple[str, str]],
    checks: list[str],
) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_CSV_PATH, index=False, encoding="utf-8-sig")
    calendar.to_csv(CALENDAR_CSV_PATH, index=False, encoding="utf-8-sig")

    chart_md = "\n\n".join(f"![{title}]({path})" for title, path in charts)
    checks_md = "\n".join(f"- {line}" for line in checks)

    top = summary.head(8)
    film = summary.loc[summary["service_norm"].eq("Антигравийная пленка")].iloc[0]
    wash = summary.loc[summary["service_norm"].eq("Мойка")].iloc[0]
    tire = summary.loc[summary["service_norm"].eq("Шиномонтаж")].iloc[0]
    polish = summary.loc[summary["service_norm"].eq("Полировка + защитные составы")].iloc[0]

    report = f"""# Сезонность услуг Левши

Дата расчета: 2026-05-19.

Источник: та же 1С-выгрузка `Продажи по заказам`, что используется в базовом анализе. Анализ начинается с января 2024, потому что до этого был переход на 1С и исторические данные могли быть неполными.

Методика:
- сезонный профиль считается по полным годам 2024-2025;
- 2026 не входит в сезонный индекс, потому что данные есть только до 27.04.2026;
- единица денег — строки услуг в заказ-нарядах после исключения автосервиса/запчастей, служебных строк и технических клиентов;
- `Материал Пленка` учитывается внутри категории `Антигравийная пленка`, потому что это строка материала/себестоимости для расчета ЗП, а не отдельный розничный продукт.

## Контроль данных

{checks_md}

## Короткий вывод

Главный календарный вывод: плёнка — не только самая крупная категория, но и категория с выраженными пиками летом и отдельным весенним всплеском. Для маркетинга её нельзя вести ровным фоном: нужны заранее подготовленные усиления под месяцы спроса.

- **Антигравийная пленка:** пик — {film["peak_month"]} ({num(film["peak_index"], 1)}x среднего месяца), сильные месяцы: {film["top3_months"]}.
- **Мойка:** пик — {wash["peak_month"]} ({num(wash["peak_index"], 1)}x), сильные месяцы: {wash["top3_months"]}.
- **Шиномонтаж:** пик — {tire["peak_month"]} ({num(tire["peak_index"], 1)}x), сильные месяцы: {tire["top3_months"]}.
- **Полировка/защита:** пик — {polish["peak_month"]} ({num(polish["peak_index"], 1)}x), сильные месяцы: {polish["top3_months"]}.

## Топ услуг по сезонности и выручке

{markdown_table(top, [
    ("service_norm", "Услуга", "text"),
    ("revenue_2024_2025", "Выручка 2024-2025", "money"),
    ("revenue_2024", "2024", "money"),
    ("revenue_2025", "2025", "money"),
    ("revenue_change_2025_vs_2024", "2025/2024", "pct"),
    ("peak_month", "Пик", "text"),
    ("peak_index", "Индекс пика", "index"),
    ("top3_months", "Сильные месяцы", "text"),
    ("weak_month", "Провал", "text"),
    ("weak_index", "Индекс провала", "index"),
], 12)}

## Маркетинговый календарь

`Сезонный фокус` показывает услуги, у которых месяц выше обычного для этой услуги. `Лидеры оборота` показывает, где в среднем больше денег в абсолюте.

{markdown_table(calendar, [
    ("month_name", "Месяц", "text"),
    ("seasonal_focus", "Сезонный фокус", "text"),
    ("revenue_leaders", "Лидеры оборота", "text"),
    ("weak_services", "Слабые сезонные услуги", "text"),
], 12)}

## Графики

{chart_md}

## Как использовать

1. Для плёнки: готовить офферы и креативы заранее, до сезонного окна, а не в месяц пика. Пик в данных приходит уже как факт спроса.
2. Для шиномонтажа: использовать сезонные пики как якорь для записи на мойку/уход/плёнку, а не как отдельную низкомаржинальную услугу.
3. Для мойки: смотреть не только выручку, но и загрузку выходных. Мойка может быть входом в базу, но сама по себе не объясняет крупный чек.
4. Для полировки/защитных составов: использовать как докрутку к плёнке и как сезонный повод для возврата, а не как главный вход в постоянную базу.

## Файлы

- `{os.path.basename(SUMMARY_CSV_PATH)}` — свод по услугам, пикам и провалам.
- `{os.path.basename(MONTHLY_CSV_PATH)}` — помесячная таблица по годам, услугам и сезонному индексу.
- `{os.path.basename(CALENDAR_CSV_PATH)}` — маркетинговый календарь по месяцам.
"""
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)


def main() -> None:
    rows = base.fetch_sheet()
    long_df = base.parse_to_long(rows)
    clean_df, _summary = ticket.clean_source(long_df)
    monthly, _services = build_monthly(clean_df)
    summary, top_services, seasonal = build_summary(monthly, clean_df)
    calendar = build_calendar(seasonal, top_services)
    checks = validate(clean_df, monthly)
    charts = render_charts(summary, seasonal, top_services)
    write_report(clean_df, monthly, summary, seasonal, calendar, charts, checks)

    print(f"Report: {REPORT_PATH}")
    print(f"Summary CSV: {SUMMARY_CSV_PATH}")
    print(f"Monthly CSV: {MONTHLY_CSV_PATH}")
    print(f"Calendar CSV: {CALENDAR_CSV_PATH}")
    for line in checks:
        print(f"OK: {line}")


if __name__ == "__main__":
    main()
