#!/usr/bin/env python3
# Таблица A + почти-A под сверку и объединение в Б24.
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "projects/detailing-samara/analytics/abc-a-clients-candidates-2026-05-26.csv"
OUT = ROOT / "projects/detailing-samara/sales/a-clients-handoff-bitrix-2026-06-08.csv"

def f(r,k):
    try: return float(r[k] or 0)
    except: return 0.0

rows=list(csv.DictReader(open(SRC,encoding="utf-8-sig")))

def dominant(r):
    m={"Плёнка":f(r,"ppf_revenue"),"Мойка":f(r,"wash_revenue"),
       "Полировка":f(r,"polish_revenue"),"Химчистка":f(r,"dryclean_revenue")}
    top=max(m,key=m.get)
    return top if m[top]>0 else "Прочее"

out=[]
for r in rows:
    conf = r["a_confirmed"]=="True"
    near = (not conf) and (150000<=f(r,"revenue")<200000 or
            (60000<=f(r,"wash_revenue")<80000 and f(r,"wash_avg_ticket_line")>=3500))
    if not (conf or near): continue
    out.append({
        "Сегмент":"A (подтверждён)" if conf else "Почти A",
        "Клиент":r["client"],
        "Тип":"B2B/флот" if r["b2b_like"]=="True" else "Частный",
        "Выручка 12 мес, ₽":int(f(r,"revenue")),
        "Визитов":int(f(r,"visits")),
        "Средний чек, ₽":int(f(r,"avg_ticket")),
        "Профиль услуг":dominant(r),
        "Первый визит":r["first_visit"],
        "Последний визит":r["last_visit"],
        "Активных мес":r["active_months"],
        # пустые поля под дозаполнение менеджером в Б24:
        "Телефон":"",
        "Марка/модель авто":"",
        "Есть контакт в Б24 (да/нет)":"",
        "Объединить/дубль":"",
        "Заметка менеджера":"",
    })

out.sort(key=lambda x:(0 if x["Сегмент"].startswith("A") else 1, -x["Выручка 12 мес, ₽"]))

cols=list(out[0].keys())
with open(OUT,"w",encoding="utf-8-sig",newline="") as fp:
    w=csv.DictWriter(fp,fieldnames=cols); w.writeheader(); w.writerows(out)

a=sum(1 for x in out if x["Сегмент"].startswith("A"))
print(f"Записано {len(out)} строк: {a} A + {len(out)-a} почти A")
print("Колонки:",", ".join(cols))
