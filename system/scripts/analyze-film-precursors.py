#!/usr/bin/env python3
"""
Анализ: какие услуги предшествовали заказу плёнки.

Для каждого клиента, у которого есть хотя бы один заказ «Антигравийная пленка»:
- какая была его ПЕРВАЯ услуга (entry service)
- какая была услуга в ПОСЛЕДНЕМ визите ПЕРЕД первым плёнковым (если визитов >1)
- сколько было визитов до плёнки
- через сколько дней после первого визита пришёл на плёнку

Запуск:
    cd D:/SecondBrain/HyperCRM
    .tools/venv/Scripts/python.exe system/scripts/analyze-film-precursors.py
"""

import sys
import os
import pandas as pd

# Импортируем функции из основного скрипта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
base = import_module('analyze-detailing-base')
ticket = import_module('analyze-ticket-depth-monthly')

FILM_LABEL = 'Антигравийная пленка'
DATE_TAG = '2026-05-20'
OUT_DIR = f"{base.ROOT}/projects/detailing-samara/analytics"


def fmt_int(n):
    return f"{int(n):,}".replace(',', ' ')


def fmt_money(n):
    return f"{int(round(n)):,}".replace(',', ' ') + ' ₽'


def main():
    # 1. Тянем сырые данные через основной скрипт
    rows = base.fetch_sheet()
    long_df = base.parse_to_long(rows)
    clean_df, _source_summary = ticket.clean_source(long_df)
    visit = ticket.build_visit_table(clean_df).sort_values(['client', 'date', 'order_id']).reset_index(drop=True)

    # 4. Берём всех клиентов с плёнкой
    has_film_clients = visit[visit['services'].apply(lambda lst: FILM_LABEL in set(lst or []))]['client'].unique()
    print(f"Клиентов с плёнкой (за всю историю): {len(has_film_clients)}")

    # 5. Для каждого такого клиента — собрать историю визитов и первый плёнковый
    records = []
    for client in has_film_clients:
        cv = visit[visit['client'] == client].sort_values('date')
        # Найти первый визит с плёнкой
        film_visits = cv[cv['services'].apply(lambda lst: FILM_LABEL in set(lst or []))]
        if film_visits.empty:
            continue
        first_film_visit = film_visits.iloc[0]
        first_film_date = first_film_visit['date']

        # История ДО первого плёнкового (не включая)
        before = cv[cv['date'] < first_film_date]

        # Первая услуга клиента (на самом первом визите) — доминирующая
        first_visit = cv.iloc[0]
        first_service = FILM_LABEL if FILM_LABEL in set(first_visit['services'] or []) else first_visit['dominant_service']

        # Услуга в визите ПЕРЕД плёнкой (если был хоть один визит до)
        if not before.empty:
            last_before_film_service = before.iloc[-1]['dominant_service']
            visits_before_film = len(before)
            days_to_film = (first_film_date - first_visit['date']).days
        else:
            last_before_film_service = '— (плёнка сразу)'
            visits_before_film = 0
            days_to_film = 0

        # Был ли вход = плёнка (плёнка в первом же визите)?
        film_at_entry = FILM_LABEL in set(first_visit['services'] or [])

        # Если плёнка в первом визите — что было в комбо?
        combo_at_entry = None
        if film_at_entry:
            combo_at_entry = [s for s in first_visit['services'] if s != FILM_LABEL]

        records.append({
            'client': client,
            'first_service': first_service,
            'film_at_entry': film_at_entry,
            'combo_at_entry': combo_at_entry,
            'visits_before_film': visits_before_film,
            'last_before_film_service': last_before_film_service,
            'days_to_film': days_to_film,
            'first_film_revenue': first_film_visit['revenue'],
        })

    res = pd.DataFrame(records)
    print(f"Анализированных клиентов: {len(res)}")

    # ====================================================================
    # Формируем отчёт
    # ====================================================================
    out = []
    out.append(f"# Анализ: что предшествовало заказу плёнки\n")
    out.append(f"**Дата:** {DATE_TAG}  ")
    out.append(f"**Источник:** 1С-выгрузка через `analyze-film-precursors.py`  ")
    out.append(f"**Когорта:** все клиенты с хотя бы одним заказом «{FILM_LABEL}» с января 2024")
    out.append(f"**Размер когорты:** **{fmt_int(len(res))} клиентов**\n")
    out.append("> Методика 2026-05-20: используется общий visit-level helper; `Материал Пленка` схлопнут с работой по плёнке, нулевая мойка внутри плёночного заказ-наряда не считается отдельной услугой/комбо. Первая услуга = плёнка, если плёнка была в первом визите даже не как доминирующая по выручке.\n")
    out.append("---\n")

    # ============================
    # 1. Распределение по «как пришли на плёнку»
    # ============================
    out.append("## 1. Как клиенты приходят на плёнку\n")

    n_film_at_entry = res['film_at_entry'].sum()
    n_came_later = (~res['film_at_entry']).sum()
    out.append(f"- **Плёнка сразу (на первом визите):** {fmt_int(n_film_at_entry)} ({n_film_at_entry/len(res)*100:.1f}%)")
    out.append(f"- **Пришли через другую услугу, плёнка на 2-м или дальнейшем визите:** {fmt_int(n_came_later)} ({n_came_later/len(res)*100:.1f}%)\n")

    # ============================
    # 2. Распределение по visits_before_film
    # ============================
    out.append("## 2. Сколько визитов до плёнки\n")
    dist = res['visits_before_film'].value_counts().sort_index()
    out.append("| Визитов до плёнки | Клиентов | Доля |")
    out.append("|---|---:|---:|")
    for v, n in dist.items():
        out.append(f"| {v} | {fmt_int(n)} | {n/len(res)*100:.1f}% |")
    out.append("")

    # ============================
    # 3. Первая услуга клиента (entry service)
    # ============================
    out.append("## 3. Первая услуга клиентов, дошедших до плёнки\n")
    out.append("> Какая была САМАЯ ПЕРВАЯ услуга у клиента, который потом купил плёнку. Если плёнка была в первом визите, первая услуга = плёнка.\n")
    by_first = res['first_service'].value_counts()
    out.append("| Первая услуга | Клиентов | Доля |")
    out.append("|---|---:|---:|")
    for svc, n in by_first.items():
        out.append(f"| {svc} | {fmt_int(n)} | {n/len(res)*100:.1f}% |")
    out.append("")

    # ============================
    # 4. Услуга в визите ПЕРЕД плёнкой (только те, у кого был >=1 визит до)
    # ============================
    only_came_later = res[~res['film_at_entry']].copy()
    out.append(f"## 4. Услуга в последнем визите ПЕРЕД плёнкой\n")
    out.append(f"> Только клиенты, у которых был хотя бы 1 визит до плёнки — выборка **{fmt_int(len(only_came_later))} чел.**\n")
    by_last = only_came_later['last_before_film_service'].value_counts()
    out.append("| Услуга перед плёнкой | Клиентов | Доля |")
    out.append("|---|---:|---:|")
    for svc, n in by_last.items():
        out.append(f"| {svc} | {fmt_int(n)} | {n/len(only_came_later)*100:.1f}% |")
    out.append("")

    # ============================
    # 5. Комбо услуг в первом визите (если плёнка сразу)
    # ============================
    out.append(f"## 5. Что в комбо с плёнкой на первом визите\n")
    only_film_at_entry = res[res['film_at_entry']].copy()
    out.append(f"> Только клиенты, у которых плёнка была сразу — выборка **{fmt_int(len(only_film_at_entry))} чел.**\n")

    # Раскрываем combo_at_entry
    combo_counts = {}
    only_film_count = 0
    for combo in only_film_at_entry['combo_at_entry']:
        if not combo:
            only_film_count += 1
        else:
            for svc in combo:
                combo_counts[svc] = combo_counts.get(svc, 0) + 1

    out.append(f"- **Только плёнка, без комбо:** {fmt_int(only_film_count)} ({only_film_count/len(only_film_at_entry)*100:.1f}%)\n")
    out.append("**Что добавляли в визит к плёнке:**\n")
    out.append("| Услуга в комбо | Клиентов | Доля от пришедших с плёнкой сразу |")
    out.append("|---|---:|---:|")
    for svc, n in sorted(combo_counts.items(), key=lambda x: -x[1]):
        out.append(f"| {svc} | {fmt_int(n)} | {n/len(only_film_at_entry)*100:.1f}% |")
    out.append("")

    # ============================
    # 6. Время от первого визита до плёнки (для тех, кто пришёл не сразу)
    # ============================
    out.append("## 6. Через сколько дней после первого визита заказывают плёнку\n")
    out.append(f"> Только {fmt_int(len(only_came_later))} клиентов с visits_before_film ≥ 1.\n")
    days = only_came_later['days_to_film']
    out.append(f"- Медиана: **{int(days.median())} дн.**")
    out.append(f"- Среднее: **{int(days.mean())} дн.**")
    out.append(f"- 25-й перцентиль: **{int(days.quantile(0.25))} дн.**")
    out.append(f"- 75-й перцентиль: **{int(days.quantile(0.75))} дн.**")
    out.append(f"- Максимум: **{int(days.max())} дн.**\n")

    bins = [0, 7, 30, 90, 180, 365, 99999]
    labels = ['1-7 дн', '8-30 дн', '31-90 дн', '91-180 дн', '181-365 дн', '366+ дн']
    only_came_later['bucket'] = pd.cut(only_came_later['days_to_film'], bins=bins, labels=labels, right=True)
    bucket_dist = only_came_later['bucket'].value_counts().reindex(labels)
    out.append("| Период | Клиентов | Доля |")
    out.append("|---|---:|---:|")
    for label, n in bucket_dist.items():
        n = int(n) if not pd.isna(n) else 0
        out.append(f"| {label} | {fmt_int(n)} | {n/len(only_came_later)*100:.1f}% |")
    out.append("")

    # ============================
    # 7. Cross-tab: первая услуга × visits_before_film
    # ============================
    out.append("## 7. Cross-tab: первая услуга × количество визитов до плёнки\n")
    crosstab = pd.crosstab(res['first_service'], res['visits_before_film'])
    out.append("| Первая услуга | " + " | ".join([str(c) for c in crosstab.columns]) + " | Всего |")
    out.append("|---|" + "|".join(['---:' for _ in crosstab.columns]) + "|---:|")
    for svc in crosstab.index:
        row = crosstab.loc[svc]
        total = row.sum()
        out.append(f"| {svc} | " + " | ".join([str(int(x)) for x in row]) + f" | {int(total)} |")
    out.append("")

    # ============================
    # 8. Главные выводы (фактические)
    # ============================
    out.append("## 8. Что видно из цифр (только факты)\n")

    top_first = by_first.index[0] if not by_first.empty else '—'
    top_first_pct = by_first.iloc[0]/len(res)*100 if not by_first.empty else 0

    out.append(f"1. **Главный вход в клиентов с плёнкой — «{top_first}»** ({top_first_pct:.1f}% всех клиентов с плёнкой пришли первым визитом именно через эту услугу).")
    out.append(f"2. Из {fmt_int(len(res))} клиентов с плёнкой:")
    out.append(f"   - {n_film_at_entry/len(res)*100:.1f}% получили плёнку сразу (первый визит)")
    out.append(f"   - {n_came_later/len(res)*100:.1f}% дозрели до плёнки на 2-м или дальнейшем визите")
    if n_came_later > 0:
        top_last = by_last.index[0] if not by_last.empty else '—'
        top_last_pct = by_last.iloc[0]/len(only_came_later)*100 if not by_last.empty else 0
        out.append(f"3. Среди тех, кто пришёл не сразу, чаще всего ПЕРЕД плёнкой была услуга **«{top_last}»** ({top_last_pct:.1f}% случаев).")
    out.append(f"4. Медианное время от первого визита до плёнки (для дозревающих) — **{int(only_came_later['days_to_film'].median())} дней**.")
    out.append("")

    out.append("---\n")
    out.append("> Это сырой анализ цифр. Интерпретация и рекомендации — отдельно (не в этом файле).\n")

    # Сохраняем
    out_path = f"{OUT_DIR}/film-precursors-{DATE_TAG}.md"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f"\nГотово: {out_path}")


if __name__ == '__main__':
    main()
