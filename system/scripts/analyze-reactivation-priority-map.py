#!/usr/bin/env python3
"""
Build a prioritized reactivation map for Levsha sleeping clients.
"""

from __future__ import annotations

import os
import sys
from importlib import import_module

import pandas as pd


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

base = import_module("analyze-detailing-base")
ticket = import_module("analyze-ticket-depth-monthly")

OUT_DIR = os.path.join(ROOT, "projects", "detailing-samara", "analytics")
SALES_DIR = os.path.join(ROOT, "projects", "detailing-samara", "sales")
DATE_TAG = "2026-05-20"
REPORT_PATH = os.path.join(OUT_DIR, f"reactivation-priority-map-{DATE_TAG}.md")
CSV_PATH = os.path.join(SALES_DIR, f"reactivation-priority-map-{DATE_TAG}.csv")
SUMMARY_CSV_PATH = os.path.join(OUT_DIR, f"reactivation-priority-summary-{DATE_TAG}.csv")

MIN_SLEEP_DAYS = 90
MAX_SLEEP_DAYS = 548


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def integer(value: float) -> str:
    return f"{int(value):,}".replace(",", " ")


def num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value: float, digits: int = 1) -> str:
    return f"{num(value, digits)}%"


def is_b2b_like(name: str) -> bool:
    value = f" {str(name or '').upper()} "
    markers = [
        " ООО ", " АО ", " ЗАО ", " ОАО ", " ИП ", " ПАО ", " НКО ", " ФГБУ ",
        " ФГУП ", " МБУ ", " ГК ", " ТД ", " ТК ", " СК ", " ПП ", " ПО ",
        " НПП ", " ФИРМА ", " КОМПАНИЯ ", " АВТОЦЕНТР ", " ДИЛЕР ",
    ]
    return any(marker in value for marker in markers)


def visit_segment(visits: int) -> str:
    if visits >= 10:
        return "10+ визитов"
    if visits >= 4:
        return "4-9 визитов"
    if visits >= 2:
        return "2-3 визита"
    return "1 визит"


def dormancy_bucket(days: int) -> str:
    if days < 180:
        return "3-6 мес"
    if days <= 365:
        return "6-12 мес"
    return "12-18 мес"


def service_offer(service: str, segment: str, b2b_like: bool) -> str:
    if b2b_like:
        return "Личный звонок Александра: флот/служебные авто, приоритетная запись, контроль текущих потребностей"
    if service == ticket.FILM_LABEL:
        return "Контроль плёнки + мойка/уход + осмотр открытых зон и лобового"
    if service == "Мойка":
        return "Премиальная мойка + быстрая диагностика кузова/салона после сезона"
    if service == "Полировка + защитные составы":
        return "Осмотр состояния защиты/блеска + предложение обновления защиты или локальной плёнки"
    if service == "Химчистка":
        return "Обновление салона + мойка снаружи, особенно если был годовой перерыв"
    if service == "Шиномонтаж":
        return "Сезонный повод: мойка, осмотр кузова/дисков, запись на удобное окно"
    if service == "Тонировка":
        return "Проверка комфорта/стёкол + расчёт защиты кузова зон риска"
    if service == "Пдр":
        return "Осмотр кузова на новые вмятины + мойка/локальная полировка"
    if service == "Ремонт стекол":
        return "Осмотр стекла после сезона + бронь лобового/зон риска"
    if service == "Бронь лобового":
        return "Проверка лобового + предложение защиты капота/фар/кромок"
    if segment == "1 визит":
        return "Мягкое сообщение с поводом вернуться: мойка/осмотр без агрессивной продажи"
    return "Персональный бонус на первый возвратный визит + диагностика авто"


def score_client(row: pd.Series) -> int:
    score = 0
    revenue = float(row["revenue"])
    visits = int(row["visits"])
    days = int(row["days_without_visit"])
    service = row["last_dominant_service"]

    if revenue >= 300_000:
        score += 35
    elif revenue >= 150_000:
        score += 28
    elif revenue >= 75_000:
        score += 20
    elif revenue >= 30_000:
        score += 12
    else:
        score += 5

    if visits >= 10:
        score += 30
    elif visits >= 4:
        score += 22
    elif visits >= 2:
        score += 12
    else:
        score += 3

    if days < 180:
        score += 18
    elif days <= 365:
        score += 14
    else:
        score += 6

    if bool(row["b2b_like"]):
        score += 8

    if service in {ticket.FILM_LABEL, "Бронь лобового"}:
        score += 10
    elif service in {"Мойка", "Шиномонтаж"}:
        score += 8
    elif service in {"Полировка + защитные составы", "Химчистка", "Тонировка"}:
        score += 6
    elif service in {"Пдр", "Ремонт стекол"}:
        score += 2

    return min(score, 100)


def priority_label(score: int, row: pd.Series) -> str:
    if score >= 78 or int(row["visits"]) >= 10 or float(row["revenue"]) >= 300_000:
        return "P1"
    if score >= 58:
        return "P2"
    if score >= 38:
        return "P3"
    return "P4"


def probability_band(score: int) -> str:
    if score >= 78:
        return "высокая"
    if score >= 58:
        return "средняя+"
    if score >= 38:
        return "средняя"
    return "низкая"


def owner(row: pd.Series) -> str:
    if row["priority"] == "P1" or bool(row["b2b_like"]):
        return "Александр"
    if row["priority"] == "P2":
        return "помощница + эскалация при интересе"
    return "помощница"


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
                values.append(pct(float(value)))
            elif kind == "num":
                values.append(num(float(value), 1))
            elif kind == "date":
                values.append(pd.to_datetime(value).strftime("%d.%m.%Y"))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SALES_DIR, exist_ok=True)

    rows = base.fetch_sheet()
    long_df = base.parse_to_long(rows)
    clean_df, _source_summary = ticket.clean_source(long_df)
    visits = ticket.build_visit_table(clean_df).sort_values(["client", "date", "order_id"]).reset_index(drop=True)
    max_date = visits["date"].max()
    client_service_revenue = (
        clean_df.groupby(["client", "service_norm"], as_index=False)["revenue"]
        .sum()
        .sort_values(["client", "revenue"], ascending=[True, False])
        .drop_duplicates("client")
        .set_index("client")["service_norm"]
        .to_dict()
    )

    client_rows = []
    for client, group in visits.groupby("client"):
        g = group.sort_values(["date", "order_id"]).reset_index(drop=True)
        last = g.iloc[-1]
        first = g.iloc[0]
        main_service = client_service_revenue.get(client, last.dominant_service)
        days = int((max_date - last["date"]).days)
        if days < MIN_SLEEP_DAYS or days > MAX_SLEEP_DAYS:
            continue
        segment = visit_segment(len(g))
        b2b_like = is_b2b_like(client)
        client_rows.append(
            {
                "client": client,
                "b2b_like": b2b_like,
                "visits": len(g),
                "segment": segment,
                "revenue": float(g["revenue"].sum()),
                "avg_ticket": float(g["revenue"].mean()),
                "first_visit": first["date"],
                "last_visit": last["date"],
                "days_without_visit": days,
                "dormancy_bucket": dormancy_bucket(days),
                "first_dominant_service": first["dominant_service"],
                "last_dominant_service": last["dominant_service"],
                "main_revenue_service": main_service,
                "last_services": " + ".join(last["services"]),
                "last_ticket": float(last["revenue"]),
            }
        )

    clients = pd.DataFrame(client_rows)
    if clients.empty:
        raise ValueError("No sleeping clients in selected window.")

    clients["score"] = clients.apply(score_client, axis=1)
    clients["priority"] = clients.apply(lambda row: priority_label(int(row["score"]), row), axis=1)
    clients["return_probability_proxy"] = clients["score"].apply(probability_band)
    clients["recommended_offer"] = clients.apply(
        lambda row: service_offer(row["last_dominant_service"], row["segment"], bool(row["b2b_like"])),
        axis=1,
    )
    clients["owner"] = clients.apply(owner, axis=1)
    clients = clients.sort_values(["priority", "score", "revenue", "visits"], ascending=[True, False, False, False])
    clients["rank"] = range(1, len(clients) + 1)

    export_cols = [
        "rank",
        "priority",
        "client",
        "owner",
        "return_probability_proxy",
        "score",
        "b2b_like",
        "segment",
        "dormancy_bucket",
        "days_without_visit",
        "last_visit",
        "visits",
        "revenue",
        "avg_ticket",
        "last_dominant_service",
        "main_revenue_service",
        "last_services",
        "recommended_offer",
    ]
    clients[export_cols].to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    summary = (
        clients.groupby(["priority", "dormancy_bucket"], as_index=False)
        .agg(clients=("client", "nunique"), revenue=("revenue", "sum"), avg_ltv=("revenue", "mean"))
        .sort_values(["priority", "dormancy_bucket"])
    )
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    by_priority = (
        clients.groupby("priority", as_index=False)
        .agg(
            clients=("client", "nunique"),
            revenue=("revenue", "sum"),
            avg_ltv=("revenue", "mean"),
            avg_visits=("visits", "mean"),
            b2b_clients=("b2b_like", "sum"),
        )
        .sort_values("priority")
    )
    by_priority["revenue_share"] = by_priority["revenue"] / clients["revenue"].sum() * 100

    by_service = (
        clients.groupby(["priority", "last_dominant_service"], as_index=False)
        .agg(clients=("client", "nunique"), revenue=("revenue", "sum"), avg_ltv=("revenue", "mean"))
        .sort_values(["priority", "clients", "revenue"], ascending=[True, False, False])
    )

    p1p2 = clients.loc[clients["priority"].isin(["P1", "P2"])].copy()
    total_revenue = float(clients["revenue"].sum())

    report = f"""# Карта реактивации: кого звать сейчас

Дата расчета: {DATE_TAG}.

Методика: берём клиентов без визита от {MIN_SLEEP_DAYS} до {MAX_SLEEP_DAYS} дней на дату последней выгрузки {max_date:%d.%m.%Y}. Приоритет — рабочий scoring, а не математический прогноз: учитываются прошлый LTV, число визитов, давность, B2B-like признак и последняя услуга.

## Короткий вывод

- В реактивационном окне 3-18 месяцев: {integer(len(clients))} клиентов.
- Их прошлая выручка: {money(total_revenue)} ₽.
- P1+P2 для ручной работы: {integer(len(p1p2))} клиентов, {money(float(p1p2["revenue"].sum()))} ₽ прошлой выручки.
- P1 лучше вести через Александра: там B2B-like, 10+ визитов или высокий LTV.
- P2 можно отдавать помощнице, но с эскалацией Александру при интересе/негативе.

## Приоритеты

{markdown_table(by_priority, [
    ("priority", "Приоритет", "text"),
    ("clients", "Клиентов", "int"),
    ("revenue", "Прошлая выручка", "money"),
    ("revenue_share", "Доля выручки окна", "pct"),
    ("avg_ltv", "LTV/клиент", "money"),
    ("avg_visits", "Визитов/клиент", "num"),
    ("b2b_clients", "B2B-like", "int"),
])}

## Топ клиентов для первого прохода

{markdown_table(clients, [
    ("priority", "P", "text"),
    ("client", "Клиент", "text"),
    ("owner", "Кто", "text"),
    ("return_probability_proxy", "Шанс", "text"),
    ("score", "Score", "int"),
    ("last_visit", "Последний визит", "date"),
    ("days_without_visit", "Дней", "int"),
    ("visits", "Визитов", "int"),
    ("revenue", "LTV", "money"),
    ("last_dominant_service", "Последняя услуга", "text"),
], 50)}

## Сегменты по последней услуге

{markdown_table(by_service, [
    ("priority", "P", "text"),
    ("last_dominant_service", "Последняя услуга", "text"),
    ("clients", "Клиентов", "int"),
    ("revenue", "Прошлая выручка", "money"),
    ("avg_ltv", "LTV/клиент", "money"),
], 40)}

## Как использовать

1. Начать с P1: персональные звонки Александра, особенно B2B-like и 10+ визитов.
2. P2 отдать помощнице как основной объём обзвона на 2 недели.
3. P3 использовать второй волной или мягким сообщением без давления.
4. P4 не трогать руками в первом пилоте: это слой для дешёвой рассылки или будущей автоматизации.
5. В Битрикс24 фиксировать `priority`, `score`, `dormancy_bucket`, `last_dominant_service`, `recommended_offer`.

## Файлы

- `{os.path.basename(CSV_PATH)}` — рабочий список для обзвона/Б24.
- `{os.path.basename(SUMMARY_CSV_PATH)}` — свод по приоритетам и давности.
"""

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report: {REPORT_PATH}")
    print(f"CSV: {CSV_PATH}")
    print(f"Summary CSV: {SUMMARY_CSV_PATH}")
    print(f"Sleeping clients: {len(clients):,}".replace(",", " "))
    print(f"P1+P2: {len(p1p2):,}".replace(",", " "))
    print(f"Past revenue: {money(total_revenue)} ₽")


if __name__ == "__main__":
    main()
