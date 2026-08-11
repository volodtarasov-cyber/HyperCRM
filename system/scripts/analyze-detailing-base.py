#!/usr/bin/env python3
"""
Анализ клиентской базы Левши — формат отчёта «Продажи по заказам» из 1С.

Структура входа (3-уровневая иерархия в колонке A):
    Покупатель                              ← level 1
      Заказ-наряд N от DD.MM.YYYY            ← level 2 (есть дата!)
        , Услуга                             ← level 3

Колонки: A=иерархия, H/J=итог (кол-во/выручка), K..BN=по месяцам парами.

Запуск:
    cd D:/SecondBrain/HyperCRM
    .tools/venv/Scripts/python.exe system/scripts/analyze-detailing-base.py

Результат:
    projects/detailing-samara/analytics/clients-base-YYYY-MM-DD.md
"""

import os
import re
from datetime import datetime, timedelta
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "10tH-ihEClPbHqUjXWXeSgSV-uxb-UPWiQDql0lluc6Y"
SHEET_NAME = "Лист_1"

# Колонки итога — выручка (НЕ количество). По формату 1С: 9 = «Итого, Выручка»
SUM_COL_TOTAL = 9       # колонка «Итого, Выручка»
QTY_COL_TOTAL = 7       # колонка «Итого, Количество»

ANALYSIS_MONTHS = 12     # для основного анализа (последние 12 мес)
TOP_SERVICES = 15
TOP_CLIENTS = 50
SLEEPING_FROM_DAYS = 90
SLEEPING_TO_DAYS = 365
EXCLUDED_SERVICE_LABEL = 'Исключить: автосервис / запчасти'

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE_ACCOUNT_KEY = os.path.join(ROOT, "system", "secrets", "gsheets-key.json")
OUT_DIR = os.path.join(ROOT, "projects", "detailing-samara", "analytics")


def parse_num(x):
    if x is None or pd.isna(x): return 0.0
    s = str(x).replace(' ', '').replace('\xa0', '').replace('₽', '').strip()
    # 1С: "3 050,00" → 3050.00
    if ',' in s and '.' not in s: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0


# Регулярка заказ-наряда: "Заказ-наряд 409 от 02.02.2024"
ORDER_RE = re.compile(r'Заказ-наряд\s+(\d+)\s+от\s+(\d{1,2}\.\d{1,2}\.\d{4})')


def classify(cell_a):
    """Определяет уровень строки по содержимому колонки A."""
    s = (cell_a or '').strip()
    if not s: return ('empty', None, None)
    m = ORDER_RE.search(s)
    if m:
        try:
            d = datetime.strptime(m.group(2), '%d.%m.%Y')
            return ('order', m.group(1), d)
        except: return ('order', m.group(1), None)
    if s.startswith(','):
        # ", Услуга" — услуга без артикула
        return ('service', s.lstrip(', ').strip(), None)
    if ',' in s:
        # "Артикул, Услуга" — услуга с артикулом
        # берём часть после последней запятой как название
        return ('service', s.split(',', 1)[1].strip(), None)
    # Покупатель
    return ('client', s, None)


def fetch_sheet():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_KEY,
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    svc = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    print(f"Загружаю лист «{SHEET_NAME}»...")
    r = svc.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!A1:BN65000"
    ).execute()
    rows = r.get('values', [])
    print(f"  получено {len(rows):,} строк".replace(',', ' '))
    return rows


def parse_to_long(rows):
    """Преобразуем pivot в long-формат: 1 строка = 1 (клиент, заказ, услуга)."""
    records = []
    current_client = None
    current_order_id = None
    current_order_date = None
    skipped_orphan_services = 0

    # Пропускаем 5 верхних строк (заголовки)
    for row in rows[5:]:
        if not row: continue
        a = row[0] if len(row) > 0 else ''
        kind, name, date = classify(a)

        if kind == 'client':
            current_client = name
            # У клиента в колонках H, J — общие итоги по нему. Не используем для long.
        elif kind == 'order':
            current_order_id = name
            current_order_date = date
        elif kind == 'service':
            if current_client is None or current_order_date is None:
                skipped_orphan_services += 1
                continue
            qty = parse_num(row[QTY_COL_TOTAL]) if len(row) > QTY_COL_TOTAL else 0
            rev = parse_num(row[SUM_COL_TOTAL]) if len(row) > SUM_COL_TOTAL else 0
            if rev <= 0 and qty <= 0: continue
            records.append({
                'client':   current_client,
                'order_id': current_order_id,
                'date':     current_order_date,
                'service':  name,
                'quantity': qty,
                'revenue':  rev,
                'month':    current_order_date.strftime('%Y-%m'),
            })

    print(f"  выгружено в long: {len(records):,} услуг".replace(',', ' '))
    if skipped_orphan_services:
        print(f"  пропущено сирот (услуга без клиента/заказа): {skipped_orphan_services}")
    return pd.DataFrame(records)


def fmt_money(n):
    return f"{int(round(n)):,}".replace(',', ' ') + ' ₽'


def fmt_int(n):
    return f"{int(n):,}".replace(',', ' ')


def section(t):
    return f"\n## {t}\n\n"


def is_excluded_service(s):
    """Отсекает автосервис и запчасти, чтобы они не смешивались с детейлингом."""
    s = s.lower().strip()
    if 'детейлинг подвес' in s:
        return False

    parts_patterns = [
        r'\b[a-zа-я]*\d{2,}[a-zа-я0-9./-]*\b.*(амортизатор|подшипник|ступиц|ремкомплект|болт|гайк|коллектор|грм)',
        r'амортизатор|подшипник|ступиц|рычаг|сайлент|стабилизатор|пружин|шарова|суппорт|колодк|диск тормозн',
        r'осмотр подвес|ремонт подвес|замен.*подвес|подвес.*замен',
        r'слесарн|тормозн|грм|антифриз|коллектор|щетк.*стеклоочист|ступич|шрус|свеч[аи]',
        r'болт\s|гайк\s|ремкомплект|автозапчаст|запчаст',
        r'масло мотор|масло двигателя|масло транс|фильтр .*замен|хладагент|кондиционер.*замен',
        r'углы установки колес|форсунк.*омывател|диагностик|сканер',
        r'панель крышки багажника|бампер задний gv80|накладка заднего бампера|накладка переднего бампера',
        r'эмблема|заглушка цо|гайка колес|аккумулятор|сцеплен|облицовка днища|тросс',
        r'фонарь заднего хода|втулка подвески|молдинг|вставка бампера|накладка зеркал|накладка зеркала',
    ]
    return any(re.search(pattern, s) for pattern in parts_patterns)


def normalize_service(s):
    """Группировка похожих услуг по корням (мойка, плёнка, и т.д.)."""
    s = s.lower().strip()
    if is_excluded_service(s):
        return EXCLUDED_SERVICE_LABEL

    rules = [
        (r'бронирован.*лоб|лобов.*pet|лобов.*плен|лобов.*брон', 'Бронь лобового'),
        (r'плён|пленк|оклейк|антиграв|ppf|полиуретан|car las|carlas', 'Антигравийная пленка'),
        (r'ш/м|шиномонтаж|балансиров|дошип|пакет.*колес|колес.*r\d|покрышк|шин|ремонт бокового пореза|правка дис|шлифовка.*диск|реставрация дис|чистка.*диск|алмазн.*проточ', 'Шиномонтаж'),
        (r'нано комплекс|керамо комплекс|евро комплекс|мойк|зимний пакет|детейлинг подвес|сложн.*загряз|битум|липа|тополи|след.*накле|удаление.*загряз|удаление накле|очистка хром|чистка хром|очистка.*металл|глубокая чистка кузова|чистка кузова', 'Мойка'),
        (r'полировк|керамик|нанокерамик|жидкое стекло|антидожд|консервац|leather protection|nanocrystal|гидрофоб|кварц|воск|защит|пропитка кожи|фар|koch chemie ceramic', 'Полировка + защитные составы'),
        (r'химчист|чистка руля|уборка багажника|комплексная уборка|пылесос|сушка полов|озоновая чистка|озониров|озон', 'Химчистка'),
        (r'pdr|вмятин|устранение одного дефекта', 'Пдр'),
        (r'шумоизол|шумк|вибро|comfortmat', 'Шумовиброизоляция'),
        (r'ремонт.*стекл|замена стекла|скол|трещин', 'Ремонт стекол'),
        (r'тониров', 'Тонировка'),
        (r'антихром|покра|малярн', 'Покраска'),
        (r'ремонт кожи|реставрац.*кож|кожан|перешив|обивк|экокожа|nappa', 'Ремонт кожи'),
        (r'^арм\.|арматурн|с/у|с\\у|демонтаж|монтаж|обшивка.*с/у|бампер.*с/у', 'Арматурные работы / с-у'),
        (r'сетк.*радиатор|сигнализац|доводчик|видеорегистратор|дефлектор|брызговик|магнитол|парковочный радар|датчик давления|установка оборудования|дооснащ', 'Дооснащение / установка оборудования'),
        (r'обучение', 'Обучение'),
        (r'омывающ|стеклоомыв|вода питьевая|кофта|штаны|материал|feron|монитор|teyes|продажа|спирт|ароматизатор|лезвия|набор инструмент', 'Товары / материалы'),
        (r'аренда|работа сотрудника|служебного парка|фотосессия|устранение косяков|для салынского', 'Админ / внутреннее / служебное'),
    ]
    for pattern, label in rules:
        if re.search(pattern, s):
            return label
    return 'Прочее'


def analyze(df, excluded_summary=None):
    out = []
    today = df['date'].max()
    period_start = today - pd.DateOffset(months=ANALYSIS_MONTHS)
    period = df[df['date'] >= period_start].copy()

    out.append(f"# Анализ клиентской базы Левши — {datetime.now():%Y-%m-%d}\n")
    out.append(f"> Источник: 1С-выгрузка (GSheet `{SPREADSHEET_ID}`).\n")
    out.append(f"> Полный охват данных: {df['date'].min():%Y-%m-%d} → {today:%Y-%m-%d} "
               f"({(today - df['date'].min()).days // 30} мес).\n")
    out.append(f"> Окно основного анализа: последние **{ANALYSIS_MONTHS} мес** "
               f"({period_start:%Y-%m-%d} → {today:%Y-%m-%d}).\n")
    if excluded_summary:
        out.append(
            f"> Из аналитической базы исключены автосервис/запчасти: "
            f"**{fmt_int(excluded_summary['rows'])}** строк, "
            f"**{fmt_int(excluded_summary['orders'])}** заказов, "
            f"**{fmt_money(excluded_summary['revenue'])}**. "
            f"CSV: `{excluded_summary['file']}`.\n"
        )

    # ========================================================================
    # 1. Общие цифры
    # ========================================================================
    out.append(section("1. Общие цифры"))
    out.append(f"**За весь охват данных ({(today - df['date'].min()).days // 30} мес), без автосервиса/запчастей:**")
    out.append(f"- Услуг (визитов-услуг): **{fmt_int(len(df))}**")
    out.append(f"- Уникальных клиентов: **{fmt_int(df['client'].nunique())}**")
    out.append(f"- Уникальных заказ-нарядов (визитов): **{fmt_int(df['order_id'].nunique())}**")
    out.append(f"- Совокупная выручка: **{fmt_money(df['revenue'].sum())}**")
    out.append(f"\n**За последние {ANALYSIS_MONTHS} мес:**")
    out.append(f"- Услуг: **{fmt_int(len(period))}**")
    out.append(f"- Уникальных клиентов: **{fmt_int(period['client'].nunique())}**")
    out.append(f"- Визитов: **{fmt_int(period['order_id'].nunique())}**")
    out.append(f"- Выручка: **{fmt_money(period['revenue'].sum())}**")
    out.append(f"- Средняя выручка / клиент / период (LTV): **{fmt_money(period['revenue'].sum() / max(period['client'].nunique(), 1))}**")
    out.append(f"- Средний чек визита: **{fmt_money(period['revenue'].sum() / max(period['order_id'].nunique(), 1))}**")

    # ========================================================================
    # 2. Топ услуг (нормализованных)
    # ========================================================================
    period['service_norm'] = period['service'].apply(normalize_service)
    df['service_norm'] = df['service'].apply(normalize_service)

    out.append(section(f"2. Топ услуг по выручке (нормализованные группы) — {ANALYSIS_MONTHS} мес"))
    by_svc = period.groupby('service_norm').agg(
        cnt=('revenue', 'size'),
        revenue=('revenue', 'sum'),
        avg=('revenue', 'mean'),
    ).sort_values('revenue', ascending=False)
    total_rev = by_svc['revenue'].sum() or 1
    out.append("| Группа услуг | Услуг | Выручка | Доля | Средний чек строки |")
    out.append("|--------------|-------|---------|------|--------------------|")
    for svc, row in by_svc.iterrows():
        out.append(f"| {svc} | {fmt_int(row['cnt'])} | {fmt_money(row['revenue'])} | "
                   f"{row['revenue']/total_rev*100:.1f}% | {fmt_money(row['avg'])} |")

    # Топ конкретных услуг (не нормализованных)
    out.append(f"\n**Топ-{TOP_SERVICES} конкретных услуг** (без группировки):\n")
    by_raw = period.groupby('service').agg(cnt=('revenue', 'size'), revenue=('revenue', 'sum')).sort_values('revenue', ascending=False).head(TOP_SERVICES)
    out.append("| Услуга | Раз | Выручка |")
    out.append("|--------|-----|---------|")
    for svc, row in by_raw.iterrows():
        out.append(f"| {svc[:80]} | {fmt_int(row['cnt'])} | {fmt_money(row['revenue'])} |")

    # ========================================================================
    # 3. Помесячная динамика общей выручки
    # ========================================================================
    out.append(section("3. Помесячная динамика общей выручки (полный охват)"))
    by_month = df.groupby('month').agg(rev=('revenue', 'sum'), cnt=('revenue', 'size'), clients=('client', 'nunique')).reset_index()
    out.append("| Месяц | Услуг | Клиентов | Выручка | Δ vs пред. | Δ vs год.назад |")
    out.append("|-------|-------|----------|---------|-----------|---------------|")
    by_month_dict = dict(zip(by_month['month'], by_month['rev']))
    prev = None
    for _, row in by_month.iterrows():
        m = row['month']
        delta_prev = ''
        if prev is not None and prev > 0:
            d = (row['rev'] - prev) / prev * 100
            delta_prev = f"{d:+.1f}%"
        # Год назад
        try:
            year, mon = m.split('-')
            prev_year_key = f"{int(year)-1}-{mon}"
            if prev_year_key in by_month_dict and by_month_dict[prev_year_key] > 0:
                d = (row['rev'] - by_month_dict[prev_year_key]) / by_month_dict[prev_year_key] * 100
                delta_yoy = f"{d:+.1f}%"
            else: delta_yoy = ''
        except: delta_yoy = ''
        out.append(f"| {m} | {fmt_int(row['cnt'])} | {fmt_int(row['clients'])} | {fmt_money(row['rev'])} | {delta_prev} | {delta_yoy} |")
        prev = row['rev']

    # ========================================================================
    # 4. Где сидит провал — top-5 услуг помесячно за последние 12 мес
    # ========================================================================
    out.append(section("4. Динамика топ-5 услуг помесячно — где конкретно просело"))
    top5_norm = list(by_svc.head(5).index)
    pivot = period[period['service_norm'].isin(top5_norm)].pivot_table(
        index='month', columns='service_norm', values='revenue', aggfunc='sum', fill_value=0
    ).reindex(columns=top5_norm)
    out.append("| Месяц | " + " | ".join(top5_norm) + " | Сумма топ-5 |")
    out.append("|-------|" + "|".join(["---"] * (len(top5_norm) + 1)) + "|")
    for month, row in pivot.iterrows():
        cells = []
        for s in top5_norm:
            v = int(row[s])
            cells.append(f"{v//1000}к" if v >= 1000 else (f"{v}" if v else '-'))
        cells.append(f"{int(row.sum())//1000}к")
        out.append(f"| {month} | " + " | ".join(cells) + " |")

    # YoY топ-5: сравним последние 3 мес с теми же месяцами год назад
    out.append("\n**YoY последние 3 мес (в выручке) — где минус сильнее всего:**\n")
    last_3_months = sorted(period['month'].unique())[-3:]
    yoy_data = []
    for svc in top5_norm:
        last3_rev = period[(period['service_norm']==svc) & (period['month'].isin(last_3_months))]['revenue'].sum()
        prev_year_months = [f"{int(m.split('-')[0])-1}-{m.split('-')[1]}" for m in last_3_months]
        prev3_rev = df[(df['service_norm']==svc) & (df['month'].isin(prev_year_months))]['revenue'].sum()
        delta = (last3_rev - prev3_rev) / prev3_rev * 100 if prev3_rev > 0 else 0
        yoy_data.append((svc, last3_rev, prev3_rev, delta))
    out.append("| Услуга | Последние 3 мес | Год назад те же 3 мес | Δ |")
    out.append("|--------|-----------------|-----------------------|---|")
    for svc, l, p, d in sorted(yoy_data, key=lambda x: x[3]):
        out.append(f"| {svc} | {fmt_money(l)} | {fmt_money(p)} | {d:+.1f}% |")

    # ========================================================================
    # 5. Распределение клиентов
    # ========================================================================
    out.append(section("5. Клиенты — распределение по частоте визитов (за 12 мес)"))
    by_client_orders = period.groupby('client')['order_id'].nunique()
    by_client_rev = period.groupby('client')['revenue'].sum()
    bins = [
        ('Разовые (1 визит)',     by_client_orders[by_client_orders == 1].index),
        ('Случайные (2-3)',       by_client_orders[(by_client_orders >= 2) & (by_client_orders <= 3)].index),
        ('Постоянные (4-9)',      by_client_orders[(by_client_orders >= 4) & (by_client_orders <= 9)].index),
        ('Топ (10+)',             by_client_orders[by_client_orders >= 10].index),
    ]
    total_clients = period['client'].nunique()
    total_rev_period = period['revenue'].sum()
    out.append("| Категория | Клиентов | % | Сов. выручка | Доля выр. | Ср. LTV |")
    out.append("|-----------|----------|---|--------------|-----------|---------|")
    for label, idx in bins:
        n = len(idx)
        rev = by_client_rev.loc[idx].sum() if n else 0
        out.append(f"| {label} | {fmt_int(n)} | {n/max(total_clients,1)*100:.1f}% | "
                   f"{fmt_money(rev)} | {rev/max(total_rev_period,1)*100:.1f}% | "
                   f"{fmt_money(rev/max(n,1))} |")

    # ========================================================================
    # 6. Топ A-клиентов (выручка за весь охват)
    # ========================================================================
    out.append(section(f"6. Топ-{TOP_CLIENTS} A-клиентов за {ANALYSIS_MONTHS} мес — кого беречь"))
    top_clients = by_client_rev.sort_values(ascending=False).head(TOP_CLIENTS)
    last_visit = period.groupby('client')['date'].max()
    top_services_per_client = period.groupby('client').apply(
        lambda x: ', '.join(x.groupby('service_norm')['revenue'].sum().sort_values(ascending=False).head(2).index)
    )
    out.append("| # | Клиент | Визитов | Выручка | Топ-услуги | Последний визит |")
    out.append("|---|--------|---------|---------|------------|------------------|")
    for i, (cl, rev) in enumerate(top_clients.items(), 1):
        visits = by_client_orders.get(cl, 0)
        lv = last_visit[cl]
        svcs = top_services_per_client.get(cl, '')[:50]
        out.append(f"| {i} | {cl[:40]} | {int(visits)} | {fmt_money(rev)} | {svcs} | {lv:%Y-%m-%d} |")

    # ========================================================================
    # 7. Спящие клиенты — для reactivation Лии
    # ========================================================================
    out.append(section(f"7. Спящие клиенты ({SLEEPING_FROM_DAYS}–{SLEEPING_TO_DAYS} дней без визитов) — для reactivation Лии"))
    last_visit_all = df.groupby('client')['date'].max()
    revenue_all = df.groupby('client')['revenue'].sum()
    visits_all = df.groupby('client')['order_id'].nunique()
    cutoff_recent = today - timedelta(days=SLEEPING_FROM_DAYS)
    cutoff_old = today - timedelta(days=SLEEPING_TO_DAYS)
    sleeping_idx = last_visit_all[(last_visit_all < cutoff_recent) & (last_visit_all >= cutoff_old)].index
    sleeping_df = pd.DataFrame({
        'last_visit': last_visit_all.loc[sleeping_idx],
        'revenue':    revenue_all.loc[sleeping_idx],
        'visits':     visits_all.loc[sleeping_idx],
    }).sort_values('revenue', ascending=False)
    out.append(f"**Всего спящих:** {fmt_int(len(sleeping_df))} клиентов, потенциал: **{fmt_money(sleeping_df['revenue'].sum())}**.\n")
    out.append(f"**Топ-100 для приоритетного обзвона** (по прошлой выручке):\n")
    out.append("| Клиент | Визитов | Прошлая выручка | Последний визит |")
    out.append("|--------|---------|-----------------|------------------|")
    for cl, row in sleeping_df.head(100).iterrows():
        out.append(f"| {cl[:50]} | {int(row['visits'])} | {fmt_money(row['revenue'])} | {row['last_visit']:%Y-%m-%d} |")

    # Полный список — отдельным CSV
    full_csv_path = f"{OUT_DIR}/sleeping-clients-{datetime.now():%Y-%m-%d}.csv"
    sleeping_df.reset_index().rename(columns={'index': 'client'}).to_csv(full_csv_path, index=False, encoding='utf-8')
    out.append(f"\n📎 Полный список ({fmt_int(len(sleeping_df))} клиентов) в CSV: `{os.path.basename(full_csv_path)}`")

    # ========================================================================
    # 8. Когортный анализ
    # ========================================================================
    out.append(section("8. Когорты по месяцу первого визита — % возврата"))
    first_visit = df.groupby('client')['date'].min()
    df_c = df.merge(first_visit.rename('first_visit'), on='client', how='left')
    df_c['cohort'] = df_c['first_visit'].dt.to_period('M').astype(str)
    df_c['offset'] = ((df_c['date'].dt.year - df_c['first_visit'].dt.year) * 12
                       + (df_c['date'].dt.month - df_c['first_visit'].dt.month))
    cohort_counts = df_c.pivot_table(index='cohort', columns='offset', values='client', aggfunc='nunique', fill_value=0)
    if not cohort_counts.empty and 0 in cohort_counts.columns:
        cohort_pct = cohort_counts.div(cohort_counts[0], axis=0) * 100
        out.append("Возврат клиента к месяцу N после первого визита (% от когорты):\n")
        offsets = [0, 1, 2, 3, 6, 12]
        out.append("| Когорта | M0 (новых) | " + " | ".join(f"M+{m}" for m in offsets[1:]) + " |")
        out.append("|---------|-----------|" + "|".join(["---"] * (len(offsets) - 1)) + "|")
        for c in cohort_counts.tail(15).index:
            cells = [f"{int(cohort_counts.loc[c, 0])}"]
            for m in offsets[1:]:
                v = cohort_pct.loc[c].get(m, 0) if m in cohort_pct.columns else 0
                cells.append(f"{v:.0f}%" if v else '-')
            out.append(f"| {c} | " + " | ".join(cells) + " |")

    out.append("\n---\n")
    out.append(f"_Сгенерировано {datetime.now():%Y-%m-%d %H:%M} скриптом `system/scripts/analyze-detailing-base.py`_")
    out.append(f"\n_Перезапуск:_ `cd {ROOT} && .tools/venv/Scripts/python.exe system/scripts/analyze-detailing-base.py`")
    return "\n".join(out)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = fetch_sheet()
    df = parse_to_long(rows)
    if df.empty:
        print("⚠️ Не получилось распарсить ни одной строки — проверь формат таблицы.")
        return
    print(f"\nПериод: {df['date'].min():%Y-%m-%d} → {df['date'].max():%Y-%m-%d}")
    print(f"Уникальных клиентов: {df['client'].nunique():,}".replace(',', ' '))
    print(f"Уникальных заказ-нарядов: {df['order_id'].nunique():,}".replace(',', ' '))
    print(f"Услуг (строк): {len(df):,}".replace(',', ' '))
    print(f"Сов. выручка: {df['revenue'].sum():,.0f} ₽".replace(',', ' '))

    df['service_norm'] = df['service'].apply(normalize_service)
    excluded = df[df['service_norm'] == EXCLUDED_SERVICE_LABEL].copy()
    excluded_summary = None
    if not excluded.empty:
        excluded_file = f"excluded-autoservice-{datetime.now():%Y-%m-%d}.csv"
        excluded_path = f"{OUT_DIR}/{excluded_file}"
        excluded[['date', 'client', 'order_id', 'service', 'quantity', 'revenue']].sort_values(
            ['date', 'client', 'order_id']
        ).to_csv(excluded_path, index=False, encoding='utf-8')
        excluded_summary = {
            'rows': len(excluded),
            'orders': excluded['order_id'].nunique(),
            'revenue': excluded['revenue'].sum(),
            'file': excluded_file,
        }
        df = df[df['service_norm'] != EXCLUDED_SERVICE_LABEL].drop(columns=['service_norm']).copy()
        print(
            "Исключено автосервис/запчасти: "
            f"{excluded_summary['rows']:,} строк, ".replace(',', ' ')
            + f"{excluded_summary['orders']:,} заказов, ".replace(',', ' ')
            + f"{excluded_summary['revenue']:,.0f} ₽".replace(',', ' ')
        )
        print(f"CSV исключений: {excluded_path}")
        print(f"Осталось в аналитической базе: {len(df):,} строк".replace(',', ' '))
    else:
        df = df.drop(columns=['service_norm']).copy()

    print("\nГенерирую отчёт...")
    report = analyze(df, excluded_summary)
    out_path = f"{OUT_DIR}/clients-base-{datetime.now():%Y-%m-%d}.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n✅ Отчёт: {out_path}")
    print(f"📎 Размер: {len(report):,} символов".replace(',', ' '))


if __name__ == '__main__':
    main()
