#!/usr/bin/env python3
"""
Анализ: сколько визитов/месяцев нужно клиенту Левши, чтобы стать постоянным.

Определение "постоянный" синхронизировано с базовыми отчетами:
4+ уникальных визита / заказ-наряда.

Запуск:
    cd D:/SecondBrain/HyperCRM
    .tools/venv/Scripts/python.exe system/scripts/analyze-client-habit-threshold.py
"""

import os
import sys
from importlib import import_module

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
base = import_module("analyze-detailing-base")
ticket = import_module("analyze-ticket-depth-monthly")

OUT_DIR = f"{base.ROOT}/projects/detailing-samara/analytics"
DATE_TAG = "2026-05-20"
MIN_FIRST_VISIT = pd.Timestamp("2024-04-01")
REGULAR_VISITS = 4
OBSERVATION_MONTHS = 12


def fmt_int(n):
    return f"{int(n):,}".replace(",", " ")


def fmt_pct(x):
    if pd.isna(x):
        return "-"
    return f"{x:.1f}%"


def fmt_money(n):
    return f"{int(round(n)):,}".replace(",", " ") + " ₽"


def month_delta(start, end):
    return ((end.year - start.year) * 12) + (end.month - start.month)


def is_placeholder_client(name):
    s = str(name).strip().lower()
    return not s or s.startswith("<") or "продажи без заказа" in s


def is_b2b_like(name):
    s = str(name).upper()
    markers = [
        " ООО", "ООО ", " АО", "АО ", " ЗАО", "ЗАО ", " ОАО", "ОАО ",
        " ИП", "ИП ", " ПАО", "ПАО ", "НКО", "ФГБУ", "ФГУП", "МБУ",
        " ГК ", " ТД ", " ТК ", " СК ", "ПП ", "ПО ", "НПП",
    ]
    return any(m in s for m in markers)


def build_visits(df):
    clean_df, _source_summary = ticket.clean_source(df)
    visits = ticket.build_visit_table(clean_df)
    visits["b2b_like"] = visits["client"].apply(is_b2b_like)
    return visits.sort_values(["client", "date", "order_id"]).reset_index(drop=True)


def client_rows(visits, cohort_clients, observation_cutoff):
    records = []
    for client in cohort_clients:
        cv_all = visits[visits["client"] == client].sort_values(["date", "order_id"])
        if cv_all.empty:
            continue
        first_date = cv_all.iloc[0]["date"]
        within_12 = cv_all[cv_all["date"] <= first_date + pd.DateOffset(months=OBSERVATION_MONTHS)]
        first_visit = cv_all.iloc[0]
        first_services = first_visit["services"]

        reached_4_any = len(cv_all) >= REGULAR_VISITS
        reached_4_12m = len(within_12) >= REGULAR_VISITS

        row = {
            "client": client,
            "b2b_like": bool(first_visit["b2b_like"]),
            "first_date": first_date,
            "first_service": first_visit["dominant_service"],
            "visits_12m": len(within_12),
            "visits_all": len(cv_all),
            "revenue_12m": within_12["revenue"].sum(),
            "reached_4_any": reached_4_any,
            "reached_4_12m": reached_4_12m,
        }

        for m in [1, 2, 3, 4, 6, 12]:
            by_m = cv_all[cv_all["date"] <= first_date + pd.DateOffset(months=m)]
            row[f"visits_by_m{m}"] = len(by_m)

        if reached_4_any:
            first4 = cv_all.head(REGULAR_VISITS)
            fourth_date = first4.iloc[-1]["date"]
            days_to_4th = (fourth_date - first_date).days
            row.update({
                "fourth_date": fourth_date,
                "days_to_4th": days_to_4th,
                "months_to_4th": days_to_4th / 30.4375,
                "month_offset_to_4th": month_delta(first_date, fourth_date),
                "service_lines_to_4th": int(first4["service_lines"].sum()),
                "service_units_to_4th": int(first4["service_units"].sum()),
                "revenue_to_4th": first4["revenue"].sum(),
                "distinct_services_to_4th": len(set().union(*first4["services"].tolist())),
                "sequence_4": " -> ".join(first4["dominant_service"].tolist()),
                "gap_1_2_days": (first4.iloc[1]["date"] - first4.iloc[0]["date"]).days,
                "gap_2_3_days": (first4.iloc[2]["date"] - first4.iloc[1]["date"]).days,
                "gap_3_4_days": (first4.iloc[3]["date"] - first4.iloc[2]["date"]).days,
            })
        records.append(row)
    return pd.DataFrame(records)


def summarize_segment(df, label, regular_col="reached_4_12m"):
    n = len(df)
    if n == 0:
        return {"label": label, "n": 0}
    regular = df[df[regular_col]].copy()
    res = {
        "label": label,
        "n": n,
        "regular_n": len(regular),
        "regular_pct": len(regular) / n * 100,
    }
    if len(regular):
        res.update({
            "median_months_to_4th": regular["months_to_4th"].median(),
            "avg_months_to_4th": regular["months_to_4th"].mean(),
            "p25_months_to_4th": regular["months_to_4th"].quantile(0.25),
            "p75_months_to_4th": regular["months_to_4th"].quantile(0.75),
            "median_service_lines_to_4th": regular["service_lines_to_4th"].median(),
            "median_service_units_to_4th": regular["service_units_to_4th"].median(),
            "avg_service_lines_to_4th": regular["service_lines_to_4th"].mean(),
            "median_distinct_services_to_4th": regular["distinct_services_to_4th"].median(),
            "median_revenue_to_4th": regular["revenue_to_4th"].median(),
        })
    return res


def conversion_condition_table(df):
    rows = []
    baseline = df["reached_4_12m"].mean() * 100 if len(df) else 0
    conditions = [
        ("2+ визита за 1 месяц", "visits_by_m1", 2),
        ("2+ визита за 2 месяца", "visits_by_m2", 2),
        ("2+ визита за 3 месяца", "visits_by_m3", 2),
        ("2+ визита за 4 месяца", "visits_by_m4", 2),
        ("3+ визита за 3 месяца", "visits_by_m3", 3),
        ("3+ визита за 4 месяца", "visits_by_m4", 3),
        ("4+ визита за 4 месяца", "visits_by_m4", 4),
    ]
    for label, col, threshold in conditions:
        subset = df[df[col] >= threshold]
        if subset.empty:
            continue
        conv = subset["reached_4_12m"].mean() * 100
        rows.append({
            "condition": label,
            "clients": len(subset),
            "regular": int(subset["reached_4_12m"].sum()),
            "conversion": conv,
            "lift": conv / baseline if baseline else None,
        })
    return pd.DataFrame(rows)


def make_report(visits, res, out_path):
    max_date = visits["date"].max()
    cutoff = max_date - pd.DateOffset(months=OBSERVATION_MONTHS)
    regular = res[res["reached_4_12m"]].copy()
    segments_12m = [
        summarize_segment(res, "Все клиенты когорты"),
        summarize_segment(res[~res["b2b_like"]], "Без явных юрлиц/B2B"),
        summarize_segment(res[res["b2b_like"]], "B2B-like"),
    ]
    segments_any = [
        summarize_segment(res, "Все клиенты когорты", "reached_4_any"),
        summarize_segment(res[~res["b2b_like"]], "Без явных юрлиц/B2B", "reached_4_any"),
        summarize_segment(res[res["b2b_like"]], "B2B-like", "reached_4_any"),
    ]

    out = []
    out.append("# Сколько визитов/месяцев нужно, чтобы клиент стал постоянным\n")
    out.append(f"**Дата:** {DATE_TAG}  ")
    out.append(f"**Источник:** 1С-выгрузка `10tH-ihEClPbHqUjXWXeSgSV-uxb-UPWiQDql0lluc6Y` через `analyze-client-habit-threshold.py`  ")
    out.append(f"**Данные:** до {max_date:%Y-%m-%d}  ")
    out.append(f"**Основная когорта:** первый визит с {MIN_FIRST_VISIT:%Y-%m-%d} по {cutoff:%Y-%m-%d}, у каждого есть минимум {OBSERVATION_MONTHS} месяцев наблюдения  ")
    out.append(f"**Определение:** постоянный клиент = дошел до {REGULAR_VISITS}-го уникального визита / заказ-наряда в течение 12 месяцев\n")
    out.append("> Методика 2026-05-20: визиты построены через общий visit-level helper; `Материал Пленка` схлопнут с работой по плёнке, нулевая мойка внутри плёночного заказ-наряда не считается отдельной услугой/категорией.\n")

    out.append("## 1. Главные цифры\n")
    out.append("### 1.1. Строго: стали постоянными за первые 12 месяцев\n")
    out.append("| Сегмент | Клиентов | Стали постоянными за 12 мес | Доля | Медиана до 4-го визита | Среднее до 4-го визита | Медиана услуг до 4-го визита | Медиана разных категорий услуг |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for s in segments_12m:
        if s.get("n", 0) == 0:
            continue
        out.append(
            f"| {s['label']} | {fmt_int(s['n'])} | {fmt_int(s['regular_n'])} | {fmt_pct(s['regular_pct'])} | "
            f"{s.get('median_months_to_4th', float('nan')):.1f} мес | {s.get('avg_months_to_4th', float('nan')):.1f} мес | "
            f"{s.get('median_service_units_to_4th', float('nan')):.0f} | {s.get('median_distinct_services_to_4th', float('nan')):.0f} |"
        )
    out.append("")

    out.append("### 1.2. Контроль: дошли до 4-го визита за все доступное наблюдение\n")
    out.append("> У старших когорт наблюдение дольше 12 месяцев, поэтому этот блок нельзя сравнивать с молодыми когортами напрямую. Он нужен как контроль позднего дозревания.\n")
    out.append("| Сегмент | Клиентов | Дошли до 4-го визита когда-либо | Доля | Медиана до 4-го визита | Среднее до 4-го визита | 75-й перцентиль |")
    out.append("|---|---:|---:|---:|---:|---:|---:|")
    for s in segments_any:
        if s.get("n", 0) == 0:
            continue
        out.append(
            f"| {s['label']} | {fmt_int(s['n'])} | {fmt_int(s['regular_n'])} | {fmt_pct(s['regular_pct'])} | "
            f"{s.get('median_months_to_4th', float('nan')):.1f} мес | {s.get('avg_months_to_4th', float('nan')):.1f} мес | "
            f"{s.get('p75_months_to_4th', float('nan')):.1f} мес |"
        )
    out.append("")

    out.append("## 2. Насколько подтверждается гипотеза 3-4 месяцев\n")
    conv = conversion_condition_table(res)
    baseline = res["reached_4_12m"].mean() * 100
    out.append(f"Базово в этой когорте постоянными становятся **{fmt_pct(baseline)}** клиентов. Если клиент возвращается рано, вероятность резко растет:\n")
    out.append("| Условие раннего поведения | Клиентов | Из них стали постоянными | Конверсия в постоянного | Лифт к базе |")
    out.append("|---|---:|---:|---:|---:|")
    for _, row in conv.iterrows():
        lift = f"{row['lift']:.1f}x" if pd.notna(row["lift"]) else "-"
        out.append(f"| {row['condition']} | {fmt_int(row['clients'])} | {fmt_int(row['regular'])} | {fmt_pct(row['conversion'])} | {lift} |")
    out.append("")

    out.append("## 3. Когда постоянные достигают 4-го визита\n")
    out.append("| Срок от первого визита | Клиентов | Доля среди будущих постоянных | Доля от всей когорты |")
    out.append("|---|---:|---:|---:|")
    for months in [1, 2, 3, 4, 6, 12]:
        n = int((regular["months_to_4th"] <= months).sum())
        out.append(
            f"| До {months} мес | {fmt_int(n)} | {fmt_pct(n / len(regular) * 100 if len(regular) else 0)} | {fmt_pct(n / len(res) * 100 if len(res) else 0)} |"
        )
    out.append("")

    out.append("## 4. По первой услуге\n")
    first = []
    for svc, g in res.groupby("first_service"):
        if len(g) < 20:
            continue
        gr = g[g["reached_4_12m"]]
        first.append({
            "svc": svc,
            "clients": len(g),
            "regular": len(gr),
            "regular_pct": len(gr) / len(g) * 100,
            "median_months": gr["months_to_4th"].median() if len(gr) else None,
            "by4m_pct": (gr["months_to_4th"].le(4).sum() / len(g) * 100) if len(g) else 0,
        })
    first = sorted(first, key=lambda x: x["clients"], reverse=True)
    out.append("| Первая услуга | Клиентов | Постоянные 12м | Конверсия | Медиана до 4-го | Дошли до 4-го за 4 мес, от всех |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for row in first:
        median = f"{row['median_months']:.1f} мес" if row["median_months"] is not None and pd.notna(row["median_months"]) else "-"
        out.append(f"| {row['svc']} | {fmt_int(row['clients'])} | {fmt_int(row['regular'])} | {fmt_pct(row['regular_pct'])} | {median} | {fmt_pct(row['by4m_pct'])} |")
    out.append("")

    out.append("## 5. Самые частые последовательности первых 4 визитов\n")
    out.append("| Последовательность | Клиентов | Доля среди постоянных |")
    out.append("|---|---:|---:|")
    seq = regular["sequence_4"].value_counts().head(20)
    for sequence, n in seq.items():
        out.append(f"| {sequence} | {fmt_int(n)} | {fmt_pct(n / len(regular) * 100 if len(regular) else 0)} |")
    out.append("")

    if len(regular):
        out.append("## 6. Практический вывод\n")
        median = regular["months_to_4th"].median()
        p75 = regular["months_to_4th"].quantile(0.75)
        out.append(
            f"- До состояния постоянного клиенту нужен не абстрактный год, а **4 визита**. "
            f"У тех, кто реально становится постоянным, медианный срок до 4-го визита — **{median:.1f} месяца**, 75-й перцентиль — **{p75:.1f} месяца**."
        )
        out.append(
            "- Гипотеза про 3-4 месяца выглядит рабочей как операционная рамка: если клиенту обеспечить 2-й и особенно 3-й визит в первые 3-4 месяца, шанс стать постоянным кратно выше базы."
        )
        out.append(
            "- Но бонусы сами по себе не доказаны данными: в базе нет признака `бонус был/не был`. Данные доказывают связь ранних повторных визитов с постоянством, а механику бонусов нужно тестировать пилотом."
        )
    out.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = base.fetch_sheet()
    df = base.parse_to_long(rows)
    visits = build_visits(df)

    max_date = visits["date"].max()
    observation_cutoff = max_date - pd.DateOffset(months=OBSERVATION_MONTHS)
    first_visit = visits.groupby("client")["date"].min()
    cohort_clients = first_visit[
        (first_visit >= MIN_FIRST_VISIT) & (first_visit <= observation_cutoff)
    ].index

    res = client_rows(visits, cohort_clients, observation_cutoff)
    out_path = f"{OUT_DIR}/client-habit-threshold-{DATE_TAG}.md"
    make_report(visits, res, out_path)

    regular = res[res["reached_4_12m"]]
    print(f"Клиентов в когорте: {fmt_int(len(res))}")
    print(f"Стали постоянными 4+ за 12 мес: {fmt_int(len(regular))} ({fmt_pct(len(regular) / len(res) * 100 if len(res) else 0)})")
    if len(regular):
        print(f"Медиана до 4-го визита: {regular['months_to_4th'].median():.1f} мес")
        print(f"Среднее до 4-го визита: {regular['months_to_4th'].mean():.1f} мес")
        print(f"75-й перцентиль: {regular['months_to_4th'].quantile(0.75):.1f} мес")
    print(f"Отчет: {out_path}")


if __name__ == "__main__":
    main()
