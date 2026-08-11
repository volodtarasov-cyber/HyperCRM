#!/usr/bin/env python3
# Цикл 1 KPI: заполнение колонки "факт" в ретро по свежей выгрузке (01.01.2024–30.06.2026).
# Файл: ~/Downloads/Выгрузка клиентов.xlsx (помесячная сводка "Продажи по заказам").
# Структура (всё вложено в col0): Покупатель -> "Заказ-наряд N от DD.MM.YYYY" -> ", <услуга>"
# Ревеню лежит на строках-услугах в колонке соответствующего месяца.
import openpyxl, re, os
from collections import defaultdict, Counter
from datetime import date

F = os.path.expanduser("~/Downloads/Выгрузка клиентов.xlsx")
HDR = 3  # строка с месячными заголовками

wb = openpyxl.load_workbook(F, read_only=True)
ws = wb[wb.sheetnames[0]]
rows = list(ws.iter_rows(values_only=True)); wb.close()

# карта месяц -> индекс колонки "Количество" (Выручка = +1)
RU = {'янв':1,'февр':2,'март':3,'апр':4,'май':5,'июнь':6,'июль':7,'авг':8,'сент':9,'окт':10,'нояб':11,'дек':12}
lab = rows[HDR-1]
month_cols = {}   # (year,mon) -> rev_col
for i, v in enumerate(lab):
    if v and any(y in str(v) for y in ['2024','2025','2026']):
        s = str(v); yr = int(re.search(r'(202\d)', s).group(1))
        mon = next(m for k,m in RU.items() if k in s)
        month_cols[(yr,mon)] = i+1
all_months = sorted(month_cols)

date_re = re.compile(r'от\s+(\d{2})\.(\d{2})\.(\d{4})')

# парсинг
cur_client = None
client_orders = defaultdict(list)      # client -> list[date]
rev_by_month = defaultdict(float)      # (y,m) -> revenue (excl Материал)
rev_by_month_raw = defaultdict(float)  # с Материалом
seen_orders = set()

for r in rows[HDR+1:]:
    c0 = r[0]
    if not isinstance(c0, str):
        continue
    if c0.startswith('Заказ-наряд'):
        mm = date_re.search(c0)
        if mm and cur_client:
            d = date(int(mm.group(3)), int(mm.group(2)), int(mm.group(1)))
            key = (cur_client, c0)
            if key not in seen_orders:
                seen_orders.add(key)
                client_orders[cur_client].append(d)
    elif c0.startswith(','):
        is_material = 'Материал' in c0
        for (y,m), rc in month_cols.items():
            v = r[rc] if rc < len(r) else None
            if isinstance(v,(int,float)) and v:
                rev_by_month_raw[(y,m)] += v
                if not is_material:
                    rev_by_month[(y,m)] += v
    elif c0.startswith('Артикул'):
        continue
    else:
        cur_client = c0.strip()

# --- метрики по датам заказов ---
first_order = {c: min(ds) for c,ds in client_orders.items() if ds}
new_by_month = Counter()
active_by_month = defaultdict(set)
weekend = defaultdict(lambda: [0,0])  # (y,m) -> [weekend, total]
for c, ds in client_orders.items():
    fm = first_order[c]
    new_by_month[(fm.year, fm.month)] += 1
    for d in ds:
        active_by_month[(d.year,d.month)].add(c)
        w = weekend[(d.year,d.month)]
        w[1]+=1
        if d.weekday()>=5: w[0]+=1

# активная база "в месяц" (среднее distinct-клиентов за месяц) — берём по месяцам
def am(y,m): return len(active_by_month.get((y,m),[]))

# --- A-клиенты (proxy trailing 12m): клиенты, дающие 80% выручки за посл.12 мес ---
def a_clients_trailing(end_y, end_m):
    # окно: 12 месяцев по end
    months=[]
    yy,mm=end_y,end_m
    for _ in range(12):
        months.append((yy,mm)); mm-=1
        if mm==0: mm=12; yy-=1
    ms=set(months)
    rev=defaultdict(float)
    # пересчёт выручки по клиенту за окно
    return ms

# выручка по клиенту за trailing-12m
def client_rev_window(end_y,end_m):
    months=[]; yy,mm=end_y,end_m
    for _ in range(12):
        months.append((yy,mm)); mm-=1
        if mm==0: mm=12; yy-=1
    ms=set(months)
    rev=defaultdict(float)
    cur=None
    for r in rows[HDR+1:]:
        c0=r[0]
        if not isinstance(c0,str): continue
        if c0.startswith(','):
            if 'Материал' in c0: continue
            for (y,m),rc in month_cols.items():
                if (y,m) in ms:
                    v=r[rc] if rc<len(r) else None
                    if isinstance(v,(int,float)) and v and cur: rev[cur]+=v
        elif c0.startswith('Заказ-наряд') or c0.startswith('Артикул'):
            continue
        else:
            cur=c0.strip()
    return rev

def a_count(end_y,end_m):
    rev=client_rev_window(end_y,end_m)
    tot=sum(rev.values())
    ranked=sorted(rev.values(),reverse=True)
    cum=0; a80=0
    for v in ranked:
        cum+=v; a80+=1
        if cum>=0.8*tot: break
    return len(rev), a80, round(tot)

# --- retention: доля новых клиентов месяца, вернувшихся в ≤90 дней ---
def m3_ret(y,m):
    from datetime import timedelta
    coh=[c for c in client_orders if first_order[c].year==y and first_order[c].month==m]
    if not coh: return None,0
    ret=0
    for c in coh:
        fd=first_order[c]
        if any(fd< d <= fd+timedelta(days=90) for d in client_orders[c]): ret+=1
    return round(100*ret/len(coh),1), len(coh)

print("### ВЫРУЧКА по месяцам (очищено от 'Материал Плёнка'), ₽")
for (y,m) in all_months:
    if (y,m) >= (2025,10):
        raw=rev_by_month_raw[(y,m)]; cl=rev_by_month[(y,m)]
        print(f"  {y}-{m:02d}: {round(cl):>12,}   (сырое {round(raw):>12,}, Материал {round(raw-cl):>10,})")

print("\n### НОВЫЕ клиенты / АКТИВНАЯ база / ДОЛЯ ВЫХОДНЫХ по месяцам")
print(f"  {'месяц':8} {'новых':>7} {'актив.база':>11} {'выходные%':>10}")
for (y,m) in all_months:
    if (y,m) >= (2025,10):
        w=weekend[(y,m)]; ws_pct = round(100*w[0]/w[1],1) if w[1] else 0
        print(f"  {y}-{m:02d}  {new_by_month[(y,m)]:>7} {am(y,m):>11} {ws_pct:>9}%")

print("\n### A-КЛИЕНТЫ (proxy: клиенты до 80% выручки за trailing-12м)")
for end in [(2026,4),(2026,6)]:
    tot_cl,a80,rev = a_count(*end)
    print(f"  на {end[0]}-{end[1]:02d}: активных за 12м={tot_cl}, A(80%выручки)={a80}, выручка12м={rev:,}")

print("\n### M+3 RETENTION новых клиентов (возврат ≤90 дней), % когорты")
print("  (сравнение: старт 2024 vs свежие вызревшие когорты)")
for (y,m) in [(2024,1),(2024,6),(2025,6),(2025,12),(2026,1),(2026,2),(2026,3)]:
    r,n=m3_ret(y,m)
    print(f"  {y}-{m:02d}: {r}%  (когорта {n})")

print("\n### СВОДКА цикла 1 (апрель baseline vs май-июнь факт)")
for (y,m) in [(2026,4),(2026,5),(2026,6)]:
    print(f"  {y}-{m:02d}: выручка {round(rev_by_month[(y,m)]):>11,} | новых {new_by_month[(y,m)]:>4} | актив {am(y,m):>4}")

# --- YoY тот же сезон (контроль сезонности) + глубина 3+ визита ---
from datetime import timedelta as _td
def deep(y,m,visits,days):
    coh=[c for c in client_orders if first_order[c].year==y and first_order[c].month==m]
    if not coh: return None
    cnt=sum(1 for c in coh if sum(1 for d in client_orders[c] if d<=first_order[c]+_td(days=days))>=visits)
    return round(100*cnt/len(coh),1)
print("\n### YoY тот же сезон — M+3 (возврат ≤90 дн)")
for mo,nm in [(1,'янв'),(2,'фев'),(3,'мар')]:
    print(f"  {nm}: 2024={m3_ret(2024,mo)[0]}% 2025={m3_ret(2025,mo)[0]}% 2026={m3_ret(2026,mo)[0]}%")
print("### YoY — 3+ визита за 120 дн (порог постоянного)")
for mo,nm in [(1,'янв'),(2,'фев'),(3,'мар')]:
    print(f"  {nm}: 2024={deep(2024,mo,3,120)}% 2025={deep(2025,mo,3,120)}% 2026={deep(2026,mo,3,120)}%")

# --- Mix-shift: retention по первой услуге (фев+мар 2025 vs 2026) ---
# см. отдельный прогон decompose (в записке). Категоризация первой услуги — по ключам:
# плёнка/керамика/полировка/химчистка/шумка/шиномонтаж/тонировка/PDR/фары/мойка/стекло/прочее.
# Итог: рост M+3 15.5%(2025)->24.8%(2026) широкий по категориям, не за счёт mix в плёнку;
# доля PDR (дырявый вход) выросла 7.8->16%, т.е. структура ухудшилась, а retention вырос.
