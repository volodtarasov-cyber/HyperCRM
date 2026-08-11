#!/usr/bin/env python3
"""
Generate the remaining priority analytics reports for Levsha in one pass.
"""

from __future__ import annotations

import itertools
import math
import os
import sys
import warnings
from collections import Counter, defaultdict
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
DATE_TAG = "2026-05-20"

FILM_RETURN_MD = os.path.join(OUT_DIR, f"film-return-patterns-{DATE_TAG}.md")
CROSS_SELL_MD = os.path.join(OUT_DIR, f"cross-sell-combos-{DATE_TAG}.md")
B2B_MD = os.path.join(OUT_DIR, f"b2b-vs-private-{DATE_TAG}.md")
ATBV_MD = os.path.join(OUT_DIR, f"visit-intervals-atbv-{DATE_TAG}.md")
ONE_DONE_MD = os.path.join(OUT_DIR, f"one-and-done-clients-{DATE_TAG}.md")
WEEKDAY_MD = os.path.join(OUT_DIR, f"weekday-load-{DATE_TAG}.md")
RETURNS_MD = os.path.join(OUT_DIR, f"returns-cancellations-{DATE_TAG}.md")

ANALYSIS_START = pd.Timestamp("2024-01-01")
OBSERVATION_DAYS = 365
FILM_LABEL = "Антигравийная пленка"

RU_WEEKDAYS = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def integer(value: float) -> str:
    return f"{int(value):,}".replace(",", " ")


def num(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{num(value, digits)}%"


def month_label(month: str) -> str:
    return ticket.month_label(month)


def has_service(services, label: str) -> bool:
    return label in set(services or [])


def visit_key(df: pd.DataFrame) -> pd.Series:
    return (
        df["client"].astype(str)
        + "||"
        + df["order_id"].astype(str)
        + "||"
        + pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    )


def is_b2b_like(name: str) -> bool:
    value = f" {str(name or '').upper()} "
    markers = [
        " ООО ", " АО ", " ЗАО ", " ОАО ", " ИП ", " ПАО ", " НКО ", " ФГБУ ",
        " ФГУП ", " МБУ ", " ГК ", " ТД ", " ТК ", " СК ", " ПП ", " ПО ",
        " НПП ", " ФИРМА ", " КОМПАНИЯ ", " АВТОЦЕНТР ", " ДИЛЕР ",
    ]
    return any(marker in value for marker in markers)


def client_segment(visits_count: int) -> str:
    if visits_count >= 10:
        return "10+ визитов"
    if visits_count >= 4:
        return "4-9 визитов"
    if visits_count >= 2:
        return "2-3 визита"
    return "1 визит"


def parse_to_long_keep_nonzero(rows) -> pd.DataFrame:
    records = []
    current_client = None
    current_order_id = None
    current_order_date = None

    for row in rows[5:]:
        if not row:
            continue
        value = row[0] if len(row) > 0 else ""
        kind, name, date = base.classify(value)
        if kind == "client":
            current_client = name
        elif kind == "order":
            current_order_id = name
            current_order_date = date
        elif kind == "service":
            if current_client is None or current_order_date is None:
                continue
            qty = base.parse_num(row[base.QTY_COL_TOTAL]) if len(row) > base.QTY_COL_TOTAL else 0
            rev = base.parse_num(row[base.SUM_COL_TOTAL]) if len(row) > base.SUM_COL_TOTAL else 0
            if rev == 0 and qty == 0:
                continue
            records.append(
                {
                    "client": current_client,
                    "order_id": current_order_id,
                    "date": current_order_date,
                    "service": name,
                    "quantity": qty,
                    "revenue": rev,
                    "month": current_order_date.strftime("%Y-%m"),
                }
            )
    return pd.DataFrame(records)


def markdown_table(df: pd.DataFrame, columns: list[tuple[str, str, str]], max_rows: int = 30) -> str:
    if df.empty:
        return "_Нет данных._"
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
            elif kind == "date":
                values.append(pd.to_datetime(value).strftime("%d.%m.%Y") if pd.notna(value) else "")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def prepare(rows):
    long_df = base.parse_to_long(rows)
    clean_df, source_summary = ticket.clean_source(long_df)
    visits = ticket.build_visit_table(clean_df)
    visits = visits.sort_values(["client", "date", "order_id"]).reset_index(drop=True)
    visits["visit_key"] = visit_key(visits)
    visits["b2b_like"] = visits["client"].apply(is_b2b_like)
    visits["visit_month"] = visits["date"].dt.to_period("M").astype(str)
    visits["weekday_num"] = visits["date"].dt.weekday
    visits["weekday"] = visits["weekday_num"].map(RU_WEEKDAYS)

    clean_df = clean_df.copy()
    clean_df["visit_key"] = visit_key(clean_df)
    clean_df["b2b_like"] = clean_df["client"].apply(is_b2b_like)
    clean_df["date"] = pd.to_datetime(clean_df["date"])
    clean_df["weekday_num"] = clean_df["date"].dt.weekday
    clean_df["weekday"] = clean_df["weekday_num"].map(RU_WEEKDAYS)

    raw_keep = parse_to_long_keep_nonzero(rows)
    if not raw_keep.empty:
        raw_keep["date"] = pd.to_datetime(raw_keep["date"])
        raw_keep = raw_keep.loc[raw_keep["date"].ge(ANALYSIS_START)].copy()
        raw_keep["service_norm"] = raw_keep["service"].apply(base.normalize_service)
        raw_keep["visit_key"] = visit_key(raw_keep)

    return long_df, clean_df, visits, raw_keep, source_summary


def explode_visit_services(visits: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in visits.itertuples(index=False):
        for service in sorted(set(row.services or [])):
            rows.append(
                {
                    "visit_key": row.visit_key,
                    "service_norm": service,
                    "weekday_num": row.weekday_num,
                    "weekday": row.weekday,
                }
            )
    return pd.DataFrame(rows, columns=["visit_key", "service_norm", "weekday_num", "weekday"])


def report_film_returns(clean_df: pd.DataFrame, visits: pd.DataFrame) -> None:
    max_date = visits["date"].max()
    cutoff = max_date - pd.Timedelta(days=OBSERVATION_DAYS)
    film_visits = visits.loc[visits["services"].apply(lambda s: has_service(s, FILM_LABEL))].copy()
    first_film = film_visits.sort_values(["client", "date", "order_id"]).drop_duplicates("client")
    cohort = first_film.loc[first_film["date"].le(cutoff)].copy()
    cohort = cohort.rename(columns={"date": "first_film_date", "revenue": "first_film_revenue"})

    rows = []
    next_rows = []
    post_service_rows = []
    for row in cohort.itertuples():
        client_visits = visits.loc[visits["client"].eq(row.client)].sort_values(["date", "order_id"])
        future = client_visits.loc[client_visits["date"].gt(row.first_film_date)].copy()
        future_12m = future.loc[future["date"].le(row.first_film_date + pd.Timedelta(days=OBSERVATION_DAYS))]
        next_visit = future.iloc[0] if not future.empty else None
        next_12m = future_12m.iloc[0] if not future_12m.empty else None
        rows.append(
            {
                "client": row.client,
                "first_film_date": row.first_film_date,
                "first_film_revenue": row.first_film_revenue,
                "returned_anytime": not future.empty,
                "returned_3m": not future.loc[future["date"].le(row.first_film_date + pd.Timedelta(days=90))].empty,
                "returned_6m": not future.loc[future["date"].le(row.first_film_date + pd.Timedelta(days=180))].empty,
                "returned_12m": not future_12m.empty,
                "days_to_next": (next_visit["date"] - row.first_film_date).days if next_visit is not None else pd.NA,
                "next_dominant": next_visit["dominant_service"] if next_visit is not None else "",
                "days_to_next_12m": (next_12m["date"] - row.first_film_date).days if next_12m is not None else pd.NA,
                "next_12m_dominant": next_12m["dominant_service"] if next_12m is not None else "",
                "post_12m_visits": len(future_12m),
                "post_12m_revenue": float(future_12m["revenue"].sum()),
            }
        )
        if not future_12m.empty:
            for service in sorted(set(itertools.chain.from_iterable(future_12m["services"]))):
                post_service_rows.append(
                    {
                        "client": row.client,
                        "service_norm": service,
                        "post_12m_revenue": float(
                            clean_df.loc[
                                clean_df["visit_key"].isin(future_12m["visit_key"]) & clean_df["service_norm"].eq(service),
                                "revenue",
                            ].sum()
                        ),
                    }
                )
        if next_12m is not None:
            next_rows.append(
                {
                    "next_12m_dominant": next_12m["dominant_service"],
                    "next_12m_services": " + ".join(next_12m["services"]),
                    "days_to_next_12m": (next_12m["date"] - row.first_film_date).days,
                    "next_12m_revenue": next_12m["revenue"],
                }
            )

    cohort_df = pd.DataFrame(rows)
    next_df = pd.DataFrame(next_rows)
    post_services = pd.DataFrame(post_service_rows)

    next_summary = (
        cohort_df.loc[cohort_df["returned_12m"]]
        .groupby("next_12m_dominant", as_index=False)
        .agg(clients=("client", "nunique"), median_days=("days_to_next_12m", "median"))
        .sort_values("clients", ascending=False)
    )
    next_summary["share_of_returned"] = next_summary["clients"] / max(1, cohort_df["returned_12m"].sum()) * 100

    post_summary = (
        post_services.groupby("service_norm", as_index=False)
        .agg(clients=("client", "nunique"), revenue=("post_12m_revenue", "sum"))
        .sort_values("revenue", ascending=False)
        if not post_services.empty
        else pd.DataFrame(columns=["service_norm", "clients", "revenue"])
    )
    post_summary["share_of_cohort"] = post_summary["clients"] / len(cohort_df) * 100 if len(cohort_df) else 0

    cohort_df.to_csv(os.path.join(OUT_DIR, f"film-return-patterns-cohort-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    next_summary.to_csv(os.path.join(OUT_DIR, f"film-return-patterns-next-service-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    post_summary.to_csv(os.path.join(OUT_DIR, f"film-return-patterns-post-services-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")

    total = len(cohort_df)
    returned_12 = int(cohort_df["returned_12m"].sum())
    returned_any = int(cohort_df["returned_anytime"].sum())
    med_days = cohort_df.loc[cohort_df["returned_12m"], "days_to_next_12m"].median()

    write(
        FILM_RETURN_MD,
        f"""# Возвратные паттерны после плёнки

Дата расчета: {DATE_TAG}.

Когорта: клиенты, у которых первый визит с антигравийной плёнкой был с января 2024 до {cutoff:%d.%m.%Y}, чтобы у каждого было минимум 12 месяцев наблюдения. Возврат считается только после даты первого плёночного визита.

## Короткий вывод

- Клиентов в когорте: {integer(total)}.
- Вернулись в течение 3 месяцев: {integer(cohort_df["returned_3m"].sum())} = {pct(cohort_df["returned_3m"].mean() * 100)}.
- Вернулись в течение 6 месяцев: {integer(cohort_df["returned_6m"].sum())} = {pct(cohort_df["returned_6m"].mean() * 100)}.
- Вернулись в течение 12 месяцев: {integer(returned_12)} = {pct(returned_12 / total * 100 if total else 0)}.
- Вернулись когда-либо до конца выгрузки: {integer(returned_any)} = {pct(returned_any / total * 100 if total else 0)}.
- Медиана до следующего визита в 12-месячном окне: {num(med_days, 0)} дней.

## С чем возвращаются после плёнки

Первая доминирующая категория в следующем визите после плёнки:

{markdown_table(next_summary, [
    ("next_12m_dominant", "Следующая главная услуга", "text"),
    ("clients", "Клиентов", "int"),
    ("share_of_returned", "Доля среди вернувшихся", "pct"),
    ("median_days", "Медиана дней", "num"),
], 20)}

## Выручка следующих 12 месяцев по услугам

{markdown_table(post_summary, [
    ("service_norm", "Услуга после плёнки", "text"),
    ("clients", "Клиентов", "int"),
    ("share_of_cohort", "Доля всей когорты", "pct"),
    ("revenue", "Выручка 12м после", "money"),
], 20)}

## Практический смысл

Плёнка должна закрываться не финальной выдачей авто, а цепочкой следующего касания: контроль/мойка/уход, защита кузова, салон, бронь стекла, сезонные услуги. Этот отчет показывает, какие фактические направления уже появляются после плёнки и куда стоит строить continuity.
""",
    )


def report_cross_sell(clean_df: pd.DataFrame, visits: pd.DataFrame) -> None:
    categories = sorted(clean_df["service_norm"].unique())
    base_counts = Counter()
    pair_counts = Counter()
    pair_revenue = Counter()
    for row in visits.itertuples():
        services = sorted(set(row.services))
        for service in services:
            base_counts[service] += 1
        for a, b in itertools.combinations(services, 2):
            pair_counts[(a, b)] += 1
            pair_revenue[(a, b)] += row.revenue

    same_rows = []
    for (a, b), count in pair_counts.items():
        same_rows.append(
            {
                "service_a": a,
                "service_b": b,
                "visits": count,
                "support_share": count / len(visits) * 100,
                "avg_ticket": pair_revenue[(a, b)] / count,
                "revenue": pair_revenue[(a, b)],
                "confidence_a_to_b": count / base_counts[a] * 100,
                "confidence_b_to_a": count / base_counts[b] * 100,
            }
        )
    same_pairs = pd.DataFrame(same_rows).sort_values(["visits", "revenue"], ascending=False)

    def build_transitions(window: int) -> pd.DataFrame:
        base_by_source = Counter()
        conv = Counter()
        days = defaultdict(list)
        for _client, group in visits.groupby("client"):
            g = group.sort_values(["date", "order_id"]).reset_index(drop=True)
            for i, row in g.iterrows():
                source_services = set(row["services"])
                future = g.loc[(g["date"] > row["date"]) & (g["date"] <= row["date"] + pd.Timedelta(days=window))]
                future_services_by_target = {}
                for _, frow in future.iterrows():
                    delta = int((frow["date"] - row["date"]).days)
                    for target in set(frow["services"]):
                        future_services_by_target.setdefault(target, delta)
                for source in source_services:
                    base_by_source[source] += 1
                    for target, delta in future_services_by_target.items():
                        if target == source:
                            continue
                        conv[(source, target)] += 1
                        days[(source, target)].append(delta)
        rows = []
        for (source, target), count in conv.items():
            rows.append(
                {
                    "window_days": window,
                    "source_service": source,
                    "next_service": target,
                    "source_visits": base_by_source[source],
                    "converted_visits": count,
                    "conversion_rate": count / base_by_source[source] * 100,
                    "median_days": pd.Series(days[(source, target)]).median(),
                }
            )
        return pd.DataFrame(rows).sort_values(["converted_visits", "conversion_rate"], ascending=False)

    transitions = pd.concat([build_transitions(30), build_transitions(60), build_transitions(90)], ignore_index=True)
    same_pairs.to_csv(os.path.join(OUT_DIR, f"cross-sell-same-visit-pairs-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    transitions.to_csv(os.path.join(OUT_DIR, f"cross-sell-next-30-60-90-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")

    useful_90 = transitions.loc[
        transitions["window_days"].eq(90) & transitions["source_visits"].ge(100)
    ].sort_values(["converted_visits", "conversion_rate"], ascending=False)

    write(
        CROSS_SELL_MD,
        f"""# Cross-sell и связки услуг

Дата расчета: {DATE_TAG}.

Методика: анализируем все чистые визиты с января 2024. Отдельно считаем связки внутри одного заказ-наряда и переходы клиента к другой категории услуги в течение 30/60/90 дней после визита.

## Самые частые связки в одном визите

{markdown_table(same_pairs, [
    ("service_a", "Услуга A", "text"),
    ("service_b", "Услуга B", "text"),
    ("visits", "Визитов вместе", "int"),
    ("support_share", "Доля визитов", "pct"),
    ("avg_ticket", "Средний чек связки", "money"),
    ("revenue", "Выручка визитов", "money"),
], 25)}

## Что покупают в течение 90 дней после услуги

Только направления с базой от 100 исходных визитов.

{markdown_table(useful_90, [
    ("source_service", "После услуги", "text"),
    ("next_service", "Покупают услугу", "text"),
    ("source_visits", "База визитов", "int"),
    ("converted_visits", "Переходов", "int"),
    ("conversion_rate", "Конверсия", "pct"),
    ("median_days", "Медиана дней", "num"),
], 30)}

## Практический смысл

Связки внутри визита — это готовые скрипты докрутки на приемке. Переходы 30/60/90 дней — это основа для CRM-триггеров: кому и когда писать после визита, чтобы не ждать случайного возврата.
""",
    )


def report_b2b(visits: pd.DataFrame, clean_df: pd.DataFrame) -> None:
    client_rows = []
    for client, group in visits.groupby("client"):
        client_rows.append(
            {
                "client": client,
                "b2b_like": bool(group["b2b_like"].iloc[0]),
                "visits": len(group),
                "revenue": float(group["revenue"].sum()),
                "first_visit": group["date"].min(),
                "last_visit": group["date"].max(),
                "active_months": group["visit_month"].nunique(),
                "segment": client_segment(len(group)),
            }
        )
    clients = pd.DataFrame(client_rows)
    segment = (
        clients.groupby("b2b_like", as_index=False)
        .agg(
            clients=("client", "nunique"),
            visits=("visits", "sum"),
            revenue=("revenue", "sum"),
            median_client_revenue=("revenue", "median"),
            avg_visits_per_client=("visits", "mean"),
            regular_clients=("visits", lambda s: (s >= 4).sum()),
        )
        .sort_values("b2b_like", ascending=False)
    )
    segment["avg_ticket"] = segment["revenue"] / segment["visits"]
    segment["revenue_per_client"] = segment["revenue"] / segment["clients"]
    segment["regular_share"] = segment["regular_clients"] / segment["clients"] * 100
    segment["segment"] = segment["b2b_like"].map({True: "B2B-like", False: "Частные/не B2B"})

    monthly = (
        visits.groupby(["visit_month", "b2b_like"], as_index=False)
        .agg(visits=("visit_key", "nunique"), revenue=("revenue", "sum"), clients=("client", "nunique"))
    )
    monthly["segment"] = monthly["b2b_like"].map({True: "B2B-like", False: "Частные/не B2B"})

    service_mix = (
        clean_df.groupby(["b2b_like", "service_norm"], as_index=False)["revenue"]
        .sum()
        .sort_values(["b2b_like", "revenue"], ascending=[False, False])
    )
    service_mix["segment"] = service_mix["b2b_like"].map({True: "B2B-like", False: "Частные/не B2B"})
    service_mix["segment_revenue"] = service_mix.groupby("b2b_like")["revenue"].transform("sum")
    service_mix["revenue_share"] = service_mix["revenue"] / service_mix["segment_revenue"] * 100

    top_b2b = clients.loc[clients["b2b_like"]].sort_values("revenue", ascending=False).head(30)
    clients.to_csv(os.path.join(OUT_DIR, f"b2b-vs-private-clients-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    monthly.to_csv(os.path.join(OUT_DIR, f"b2b-vs-private-monthly-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    service_mix.to_csv(os.path.join(OUT_DIR, f"b2b-vs-private-service-mix-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")

    write(
        B2B_MD,
        f"""# B2B-like vs частные клиенты

Дата расчета: {DATE_TAG}.

Методика: B2B-like определяется эвристически по названию клиента (`ООО`, `АО`, `ИП`, `ПАО`, `ФГБУ`, `ТД`, `ГК` и похожие маркеры). Это не юридически чистая классификация, а рабочий срез для управленческого анализа.

## Сравнение сегментов

{markdown_table(segment, [
    ("segment", "Сегмент", "text"),
    ("clients", "Клиентов", "int"),
    ("visits", "Визитов", "int"),
    ("revenue", "Выручка", "money"),
    ("revenue_per_client", "Выручка/клиент", "money"),
    ("avg_ticket", "Средний чек", "money"),
    ("avg_visits_per_client", "Визитов/клиент", "num"),
    ("regular_share", "4+ визита", "pct"),
])}

## Микс услуг B2B-like

{markdown_table(service_mix.loc[service_mix["b2b_like"]], [
    ("service_norm", "Услуга", "text"),
    ("revenue", "Выручка", "money"),
    ("revenue_share", "Доля сегмента", "pct"),
], 15)}

## Топ B2B-like клиентов

{markdown_table(top_b2b, [
    ("client", "Клиент", "text"),
    ("visits", "Визитов", "int"),
    ("revenue", "Выручка", "money"),
    ("first_visit", "Первый визит", "date"),
    ("last_visit", "Последний визит", "date"),
    ("active_months", "Активных мес.", "int"),
    ("segment", "Частота", "text"),
], 30)}

## Практический смысл

Если B2B-like сегмент показывает больший чек, больше повторов и понятный микс услуг, его стоит вести отдельной воронкой: договоры, флот, приоритетная запись, персональная коммуникация от управляющего, а не общая рекламная воронка.
""",
    )


def report_atbv(visits: pd.DataFrame) -> None:
    client_counts = visits.groupby("client")["visit_key"].nunique().rename("client_visits")
    v = visits.merge(client_counts, on="client", how="left")
    v["client_segment"] = v["client_visits"].apply(client_segment)
    rows = []
    for client, group in v.groupby("client"):
        g = group.sort_values(["date", "order_id"]).reset_index(drop=True)
        for i in range(1, len(g)):
            rows.append(
                {
                    "client": client,
                    "b2b_like": bool(g.loc[i, "b2b_like"]),
                    "client_segment": g.loc[i, "client_segment"],
                    "prev_date": g.loc[i - 1, "date"],
                    "next_date": g.loc[i, "date"],
                    "days_between": int((g.loc[i, "date"] - g.loc[i - 1, "date"]).days),
                    "prev_dominant": g.loc[i - 1, "dominant_service"],
                    "next_dominant": g.loc[i, "dominant_service"],
                }
            )
    intervals = pd.DataFrame(rows)
    intervals.to_csv(os.path.join(OUT_DIR, f"visit-intervals-atbv-raw-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")

    def summarize(group_cols):
        return (
            intervals.groupby(group_cols, as_index=False)
            .agg(
                intervals=("days_between", "size"),
                avg_days=("days_between", "mean"),
                median_days=("days_between", "median"),
                p25=("days_between", lambda s: s.quantile(0.25)),
                p75=("days_between", lambda s: s.quantile(0.75)),
                p90=("days_between", lambda s: s.quantile(0.90)),
            )
            .sort_values("intervals", ascending=False)
        )

    by_segment = summarize(["client_segment"])
    by_service = summarize(["prev_dominant"])
    by_segment.to_csv(os.path.join(OUT_DIR, f"visit-intervals-atbv-segments-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    by_service.to_csv(os.path.join(OUT_DIR, f"visit-intervals-atbv-services-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")

    write(
        ATBV_MD,
        f"""# Среднее время между визитами / ATBV

Дата расчета: {DATE_TAG}.

Методика: для каждого клиента считаются интервалы между соседними визитами с января 2024. Это не прогноз спроса, а практическая база для CRM-триггеров и реактивации.

## По частоте клиента

{markdown_table(by_segment, [
    ("client_segment", "Сегмент клиента", "text"),
    ("intervals", "Интервалов", "int"),
    ("median_days", "Медиана дней", "num"),
    ("avg_days", "Среднее дней", "num"),
    ("p25", "P25", "num"),
    ("p75", "P75", "num"),
    ("p90", "P90", "num"),
])}

## После какой услуги когда возвращаются

{markdown_table(by_service, [
    ("prev_dominant", "Предыдущая главная услуга", "text"),
    ("intervals", "Интервалов", "int"),
    ("median_days", "Медиана дней", "num"),
    ("p75", "P75", "num"),
    ("p90", "P90", "num"),
], 20)}

## Практический смысл

P75 по сегменту или услуге можно использовать как момент мягкого касания: если типичный клиент уже должен был вернуться, но молчит, его лучше трогать не через 6-12 месяцев, а раньше.
""",
    )


def report_one_and_done(visits: pd.DataFrame) -> None:
    max_date = visits["date"].max()
    cutoff = max_date - pd.Timedelta(days=OBSERVATION_DAYS)
    first = visits.sort_values(["client", "date", "order_id"]).drop_duplicates("client")
    cohort_clients = first.loc[first["date"].le(cutoff), ["client", "date", "dominant_service", "revenue", "services"]].copy()
    rows = []
    for row in cohort_clients.itertuples():
        client_visits = visits.loc[visits["client"].eq(row.client)]
        in_12m = client_visits.loc[
            (client_visits["date"] >= row.date) & (client_visits["date"] <= row.date + pd.Timedelta(days=OBSERVATION_DAYS))
        ]
        rows.append(
            {
                "client": row.client,
                "first_date": row.date,
                "first_dominant": row.dominant_service,
                "first_revenue": row.revenue,
                "first_services": " + ".join(row.services),
                "visits_12m": len(in_12m),
                "revenue_12m": float(in_12m["revenue"].sum()),
                "one_and_done": len(in_12m) == 1,
            }
        )
    cohort = pd.DataFrame(rows)
    by_entry = (
        cohort.groupby("first_dominant", as_index=False)
        .agg(
            clients=("client", "nunique"),
            one_and_done=("one_and_done", "sum"),
            avg_first_ticket=("first_revenue", "mean"),
            median_first_ticket=("first_revenue", "median"),
            revenue_12m=("revenue_12m", "sum"),
        )
        .sort_values("clients", ascending=False)
    )
    by_entry["one_and_done_rate"] = by_entry["one_and_done"] / by_entry["clients"] * 100
    by_entry["returned_12m"] = by_entry["clients"] - by_entry["one_and_done"]
    by_entry["return_rate"] = by_entry["returned_12m"] / by_entry["clients"] * 100

    cohort.to_csv(os.path.join(OUT_DIR, f"one-and-done-clients-raw-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    by_entry.to_csv(os.path.join(OUT_DIR, f"one-and-done-by-entry-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")

    write(
        ONE_DONE_MD,
        f"""# One-and-done: кто попробовал и не вернулся

Дата расчета: {DATE_TAG}.

Когорта: клиенты, чей первый визит был до {cutoff:%d.%m.%Y}, чтобы у каждого было минимум 12 месяцев наблюдения. One-and-done = ровно 1 визит за первые 12 месяцев.

## По первой доминирующей услуге

{markdown_table(by_entry, [
    ("first_dominant", "Первая главная услуга", "text"),
    ("clients", "Клиентов", "int"),
    ("one_and_done", "1 визит", "int"),
    ("one_and_done_rate", "Доля 1 визит", "pct"),
    ("return_rate", "Вернулись 12м", "pct"),
    ("avg_first_ticket", "Средний первый чек", "money"),
    ("revenue_12m", "Выручка 12м", "money"),
], 25)}

## Практический смысл

Услуги с большой базой и высоким one-and-done rate — дырявые входы. Там нужно не просто докрутить рекламу, а менять выдачу, следующий шаг, напоминание и повод для второго визита.
""",
    )


def report_weekday(visits: pd.DataFrame, clean_df: pd.DataFrame) -> None:
    weekday = (
        visits.groupby(["weekday_num", "weekday"], as_index=False)
        .agg(visits=("visit_key", "nunique"), clients=("client", "nunique"), revenue=("revenue", "sum"))
        .sort_values("weekday_num")
    )
    weekday["avg_ticket"] = weekday["revenue"] / weekday["visits"]
    weekday["visit_share"] = weekday["visits"] / weekday["visits"].sum() * 100
    weekday["revenue_share"] = weekday["revenue"] / weekday["revenue"].sum() * 100

    service_revenue = clean_df.groupby(["visit_key", "service_norm"], as_index=False)["revenue"].sum()
    service_presence = explode_visit_services(visits).merge(
        service_revenue,
        on=["visit_key", "service_norm"],
        how="left",
    )
    service_presence["revenue"] = service_presence["revenue"].fillna(0)
    by_service = (
        service_presence.groupby(["service_norm", "weekday_num", "weekday"], as_index=False)
        .agg(revenue=("revenue", "sum"), visits=("visit_key", "nunique"))
        .sort_values(["service_norm", "weekday_num"])
    )
    service_total = by_service.groupby("service_norm")["revenue"].transform("sum")
    by_service["revenue_share_in_service"] = by_service["revenue"] / service_total * 100
    weekend = by_service.loc[by_service["weekday_num"].isin([5, 6])].groupby("service_norm", as_index=False).agg(
        weekend_revenue=("revenue", "sum"), weekend_visits=("visits", "sum")
    )
    totals = by_service.groupby("service_norm", as_index=False).agg(total_revenue=("revenue", "sum"), total_visits=("visits", "sum"))
    weekend = weekend.merge(totals, on="service_norm", how="right").fillna(0)
    weekend["weekend_revenue_share"] = weekend["weekend_revenue"] / weekend["total_revenue"].where(weekend["total_revenue"].gt(0), pd.NA) * 100
    weekend["weekend_visit_share"] = weekend["weekend_visits"] / weekend["total_visits"].where(weekend["total_visits"].gt(0), pd.NA) * 100
    weekend = weekend.sort_values("total_revenue", ascending=False)

    weekday.to_csv(os.path.join(OUT_DIR, f"weekday-load-summary-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    by_service.to_csv(os.path.join(OUT_DIR, f"weekday-load-by-service-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")

    write(
        WEEKDAY_MD,
        f"""# Распределение визитов по дням недели

Дата расчета: {DATE_TAG}.

Методика: чистые визиты с января 2024. В отчете есть только дата визита, без часов и фактической занятости боксов, поэтому это срез продаж/заказ-нарядов, а не точная операционная загрузка по часам.

## Все услуги

{markdown_table(weekday, [
    ("weekday", "День", "text"),
    ("visits", "Визитов", "int"),
    ("visit_share", "Доля визитов", "pct"),
    ("revenue", "Выручка", "money"),
    ("revenue_share", "Доля выручки", "pct"),
    ("avg_ticket", "Средний чек", "money"),
])}

## Доля выходных по услугам

{markdown_table(weekend, [
    ("service_norm", "Услуга", "text"),
    ("total_revenue", "Выручка", "money"),
    ("total_visits", "Визитов", "int"),
    ("weekend_revenue_share", "Выручка выходных", "pct"),
    ("weekend_visit_share", "Визиты выходных", "pct"),
], 20)}

## Практический смысл

Если выходные дают низкую долю визитов по мойке и быстрым услугам, туда можно переносить мягкие офферы, бонусы и реактивацию. Для дорогих услуг день недели менее важен: там решает запись и планирование производственной мощности.
""",
    )


def report_returns(raw_keep: pd.DataFrame) -> None:
    if raw_keep.empty:
        negative = pd.DataFrame()
    else:
        negative = raw_keep.loc[(raw_keep["revenue"] < 0) | (raw_keep["quantity"] < 0)].copy()

    if negative.empty:
        summary = pd.DataFrame(columns=["service_norm", "rows", "orders", "clients", "revenue"])
        monthly = pd.DataFrame(columns=["month", "rows", "orders", "clients", "revenue"])
    else:
        summary = (
            negative.groupby("service_norm", as_index=False)
            .agg(rows=("service", "size"), orders=("visit_key", "nunique"), clients=("client", "nunique"), revenue=("revenue", "sum"))
            .sort_values("revenue")
        )
        monthly = (
            negative.groupby("month", as_index=False)
            .agg(rows=("service", "size"), orders=("visit_key", "nunique"), clients=("client", "nunique"), revenue=("revenue", "sum"))
            .sort_values("month")
        )

    negative.to_csv(os.path.join(OUT_DIR, f"returns-cancellations-raw-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    summary.to_csv(os.path.join(OUT_DIR, f"returns-cancellations-by-service-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")
    monthly.to_csv(os.path.join(OUT_DIR, f"returns-cancellations-monthly-{DATE_TAG}.csv"), index=False, encoding="utf-8-sig")

    write(
        RETURNS_MD,
        f"""# Возвраты / отмены / отрицательные строки

Дата расчета: {DATE_TAG}.

Методика: для этого отчета использован отдельный парсер, который не отбрасывает отрицательные строки. Ищем строки с `revenue < 0` или `quantity < 0` с января 2024.

## Итог

- Отрицательных строк: {integer(len(negative))}.
- Заказ-нарядов с отрицательными строками: {integer(negative["visit_key"].nunique() if not negative.empty else 0)}.
- Клиентов с отрицательными строками: {integer(negative["client"].nunique() if not negative.empty else 0)}.
- Сумма отрицательных строк: {money(float(negative["revenue"].sum()) if not negative.empty else 0)} ₽.

## По услугам

{markdown_table(summary, [
    ("service_norm", "Категория", "text"),
    ("rows", "Строк", "int"),
    ("orders", "Заказов", "int"),
    ("clients", "Клиентов", "int"),
    ("revenue", "Сумма", "money"),
], 30)}

## По месяцам

{markdown_table(monthly, [
    ("month", "Месяц", "text"),
    ("rows", "Строк", "int"),
    ("orders", "Заказов", "int"),
    ("clients", "Клиентов", "int"),
    ("revenue", "Сумма", "money"),
], 40)}

## Практический смысл

Если отрицательных строк мало, это не крупный источник искажения выручки. Если есть концентрация по услуге/месяцу, эти кейсы нужно разобрать вручную: это возвраты денег, исправления документов, скидочные корректировки или технические минусы.
""",
    )


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = base.fetch_sheet()
    _long_df, clean_df, visits, raw_keep, _source_summary = prepare(rows)
    ticket.validate(clean_df, visits, ticket.monthly_summary(clean_df, visits))

    print("Generating film return patterns...")
    report_film_returns(clean_df, visits)
    print("Generating cross-sell report...")
    report_cross_sell(clean_df, visits)
    print("Generating B2B report...")
    report_b2b(visits, clean_df)
    print("Generating ATBV report...")
    report_atbv(visits)
    print("Generating one-and-done report...")
    report_one_and_done(visits)
    print("Generating weekday report...")
    report_weekday(visits, clean_df)
    print("Generating returns/cancellations report...")
    report_returns(raw_keep)

    for path in [FILM_RETURN_MD, CROSS_SELL_MD, B2B_MD, ATBV_MD, ONE_DONE_MD, WEEKDAY_MD, RETURNS_MD]:
        print(f"Report: {path}")


if __name__ == "__main__":
    main()
