#!/usr/bin/env python3
"""
Корректная конверсия «первая услуга → плёнка когда-либо».

Знаменатель: все клиенты с этой первой услугой за всю историю.
Числитель: из них — сколько потом купили плёнку (хоть когда-то).

ПРАВИЛО ОПРЕДЕЛЕНИЯ ПЕРВОЙ УСЛУГИ (исправлено 2026-05-05):
- Если в первом визите клиента есть «Антигравийная пленка» (даже как НЕ доминирующая по выручке)
  → первая услуга = «Антигравийная пленка». Логика: клиент пришёл, и плёнка была сразу.
- Иначе → доминирующая по выручке услуга первого визита.

Это устраняет искажение: раньше клиент с комбо «крупная мойка + мини-плёнка»
попадал в категорию «Мойка → дозрел до плёнки», хотя плёнка была сразу.

Запуск:
    cd D:/SecondBrain/HyperCRM
    .tools/venv/Scripts/python.exe system/scripts/analyze-film-conversion-by-entry.py
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
base = import_module('analyze-detailing-base')
ticket = import_module('analyze-ticket-depth-monthly')

FILM_LABEL = 'Антигравийная пленка'
DATE_TAG = '2026-05-20'
OUT_DIR = f"{base.ROOT}/projects/detailing-samara/analytics"


def fmt_int(n):
    return f"{int(n):,}".replace(',', ' ')


def main():
    rows = base.fetch_sheet()
    long_df = base.parse_to_long(rows)
    clean_df, _source_summary = ticket.clean_source(long_df)
    visit = ticket.build_visit_table(clean_df).sort_values(['client', 'date', 'order_id']).reset_index(drop=True)

    # Первый визит каждого клиента
    first_visit = visit.sort_values(['client', 'date', 'order_id']).groupby('client', as_index=False).first()

    # ====================================
    # ПРАВИЛО ОПРЕДЕЛЕНИЯ ПЕРВОЙ УСЛУГИ
    # ====================================
    # Если в первом визите есть плёнка (даже не как доминирующая) → первая услуга = плёнка
    # Иначе → доминирующая по выручке (service_norm)
    def define_first_service(row):
        if FILM_LABEL in row['services']:
            return FILM_LABEL
        return row['dominant_service']

    first_visit['first_service'] = first_visit.apply(define_first_service, axis=1)

    # Клиенты, у которых хоть когда-либо была плёнка
    clients_with_film = set(
        visit[visit['services'].apply(lambda lst: FILM_LABEL in set(lst or []))]['client'].unique()
    )

    first_visit['ever_film'] = first_visit['client'].isin(clients_with_film)

    # Доп. метрика: сколько клиентов в каждой категории первой услуги получили плёнку СРАЗУ
    # (т.е. в первом визите, в комбо или одиночно)
    first_visit['film_at_first_visit'] = first_visit['services'].apply(
        lambda lst: FILM_LABEL in set(lst or [])
    )

    # Группируем
    grp = first_visit.groupby('first_service').agg(
        clients_total=('client', 'count'),
        clients_to_film=('ever_film', 'sum'),
        clients_film_at_first=('film_at_first_visit', 'sum'),
    ).reset_index()
    grp['conversion_pct'] = (grp['clients_to_film'] / grp['clients_total'] * 100).round(1)
    grp['film_at_first_pct'] = (grp['clients_film_at_first'] / grp['clients_total'] * 100).round(1)
    grp = grp.sort_values('conversion_pct', ascending=False)

    # ==========
    # Отчёт
    # ==========
    out = []
    out.append("# Конверсия «первая услуга → плёнка когда-либо» (корректная, v3)\n")
    out.append(f"**Дата:** {DATE_TAG}  ")
    out.append(f"**Источник:** 1С-выгрузка через `analyze-film-conversion-by-entry.py` (v3)")
    out.append(f"**Когорта:** все клиенты за всю историю базы — **{fmt_int(len(first_visit))}** уникальных клиентов\n")
    out.append("> **Правило первой услуги (v3):** если в первом визите клиента есть плёнка (даже как не доминирующая по выручке), первая услуга = «Антигравийная пленка». Логика: клиент пришёл, плёнка была сразу — независимо от чека.")
    out.append("> `Материал Пленка` схлопнут с работой по плёнке; нулевая мойка внутри плёночного заказ-наряда не считается отдельной услугой/комбо.")
    out.append("> Знаменатель: все клиенты с такой первой услугой. Числитель: из них кто-либо когда-либо купил плёнку.\n")
    out.append("---\n")

    out.append("## Конверсия по первой услуге\n")
    out.append("| Первая услуга | Клиентов всего | Из них → плёнка когда-либо | Конверсия |")
    out.append("|---|---:|---:|---:|")
    for _, r in grp.iterrows():
        marker = " 🎯" if r['clients_total'] >= 50 and r['conversion_pct'] >= 25 and r['first_service'] != FILM_LABEL else ""
        out.append(f"| {r['first_service']} | {fmt_int(r['clients_total'])} | {fmt_int(r['clients_to_film'])} | **{r['conversion_pct']}%**{marker} |")
    out.append("")

    out.append("## Заметки\n")
    out.append("- 🎯 — пометка для услуг с **рабочей выборкой** (≥50 клиентов всего) И **высокой конверсией** (≥25%).")
    out.append(f"- Категория «{FILM_LABEL}» включает всех, у кого плёнка была в первом визите (одиночно или в комбо). Конверсия = 100% по определению.")
    out.append("- Сравнение с v1 (где «первая услуга» определялась только по доминирующей выручке): часть клиентов из «Мойка», «Покраска», «ПДР» переехала в «Антигравийная пленка» — они получили плёнку сразу в комбо, но не как самую дорогую услугу. Это устраняет завышение дозревающих.")
    out.append("- Сравнение с v2: теперь список услуг визита берётся из общего visit-level helper; техническая нулевая мойка при плёнке не влияет на комбо и первую услугу.")
    out.append("- Не путать со старым отчётом `path-to-a-client-2026-04-28.md` (там retention в когорте 2024-04→2025-04, со 12+ мес окном на возврат) и `film-precursors-2026-05-05.md` (там был сравнен числитель из всей истории и знаменатель из когорты — методологическая ошибка).")
    out.append("")

    out_path = f"{OUT_DIR}/film-conversion-by-entry-{DATE_TAG}.md"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f"\nГотово: {out_path}")
    print()
    print(grp.to_string(index=False))


if __name__ == '__main__':
    main()
