"""
Разбор выгрузки заявок из формы ВК «Бинго Самара» (B2C).

Вход:  CSV из ВК (cp1251, разделитель ';'), выгрузка «Запись открыта»
Выход: stdout — сводка по базе, удержанию, атрибуции, размеру компании,
       динамике по месяцам и по играм.

Запуск:
    .tools/venv/Scripts/python.exe .tools/projects/bingo-samara/analytics/zayavki-analysis.py <path.csv>

Зачем: закрывает блоки 3 (удержание), 6.2 (воронка) и часть 6.6 (рынок)
реестра неизвестных из projects/traffic-freelance/clients/bingo-samara/strategiya-b2c-2026-08-18.md
"""

import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else (
    r"C:\Users\User\Downloads\report-100188_9921312_6a8402df45f769.28025584.csv"
)


# ---------------------------------------------------------------- парсинг

def read_rows(path):
    """Первая строка — заголовок отчёта, вторая — дата выгрузки, третья — шапка."""
    with open(path, encoding="cp1251", errors="replace", newline="") as f:
        lines = f.read().split("\n")
    # ищем строку с шапкой таблицы
    start = next(i for i, l in enumerate(lines) if l.startswith("Дата создания;"))
    reader = csv.DictReader(lines[start:], delimiter=";")
    return [r for r in reader if r.get("Дата создания")]


def parse_dt(s):
    try:
        return datetime.strptime(s.strip(), "%d.%m.%Y %H:%M")
    except (ValueError, AttributeError):
        return None


SEATS_RE = re.compile(r"\d+")


def parse_seats(s):
    """«6», «5-6», «Пока 4, ищем до 6», «3 (3 пишем, 3 в уме)» → первое число.
    Мусор (телефоны, текст) отбрасываем."""
    if not s:
        return None
    nums = SEATS_RE.findall(s)
    if not nums:
        return None
    n = int(nums[0])
    if n < 1 or n > 40:          # телефоны и опечатки
        return None
    return n


GAME_DATE_RE = re.compile(r"^(\d{2}\.\d{2}\.\d{2})")
VENUE_RE = re.compile(r'""([^"]+)""\s*$|""([^"]+)""\s*\(')


def parse_game(s):
    """Из «28.08.26 ""Music Bingo: Большая игра"" 19:00 ""Максимилианс"" (600)»
    достаём дату игры и цену."""
    if not s:
        return None, None
    m = GAME_DATE_RE.match(s.strip())
    gdate = m.group(1) if m else None
    price = None
    pm = re.search(r"\((\d{3,4})\)", s)
    if pm:
        price = int(pm.group(1))
    return gdate, price


# ------------------------------------------------------- нормализация источника

SOURCE_RULES = [
    ("Реклама",      ["реклам", "таргет", "промо ст"]),
    ("Рассылка",     ["рассылк"]),
    ("Telegram",     ["тг", "телеграм", "telegram", "тeлеграм"]),
    ("Instagram",    ["инст", "instagram", "иг"]),
    ("Сарафан",      ["друз", "подруг", "знаком", "коллег", "мама", "сестра",
                      "рекоменд", "посовет", "приглас", "муж", "семья",
                      "скинули", "староста", "чат"]),
    ("На игре / офлайн", ["на игре", "на прошлой", "прошлой игре", "проходк",
                          "амбар", "в ресторане", "ресторан", "отдых",
                          "максимил", "жизнь удалась", "кислород", "ужин",
                          "мимо", "корпоратив", "на мероприятии", "на банках",
                          "в амбаре", "были на", "играли"]),
    ("Лояльные (следят сами)", ["давно", "фанат", "слежу", "везде", "подписан",
                                "сами", "мониторю", "жду", "постоянно",
                                "любим", "часто", "всегда", "не помню"]),
    ("Сайт / афиша",  ["сайт", "афиш", "интернет", "гугл", "google", "яндекс",
                       "поиск", "в сети", "нашла в"]),
    ("ВК",           ["вк", "vk", "контакт", "групп", "в вашей"]),
]


def norm_source(s):
    if not s or not s.strip():
        return "не указан"
    t = s.strip().lower().replace("ё", "е")
    for label, keys in SOURCE_RULES:
        for k in keys:
            if k in t:
                return label
    return "прочее"


def norm_first(s):
    if not s:
        return None
    t = s.lower()
    if "перво" in t:
        return "новичок"
    if "опыт" in t:
        return "опытный"
    return None


# ---------------------------------------------------------------- отчёт

def pct(a, b):
    return f"{100 * a / b:5.1f}%" if b else "  n/a"


def main():
    rows = read_rows(CSV_PATH)

    # --- дедупликация: двойной клик по кнопке = тот же человек, тот же ДЕНЬ,
    # та же игра, то же число мест. День в ключе обязателен: у заявок до мая-2026
    # поле «дата мероприятия» пустое, и без дня разные игры схлопнулись бы в одну.
    seen = set()
    dedup = []
    dup_count = 0
    for r in rows:
        d = parse_dt(r["Дата создания"])
        key = (r["Id пользователя"],
               d.date() if d else None,
               r.get("Выберите дату мероприятия", ""),
               r.get("Сколько вам нужно мест (реалистично): ", ""))
        if key in seen:
            dup_count += 1
            continue
        seen.add(key)
        dedup.append(r)

    print("=" * 78)
    print("БИНГО САМАРА — РАЗБОР ЗАЯВОК ИЗ ФОРМЫ ВК")
    print("=" * 78)

    dts = [d for d in (parse_dt(r["Дата создания"]) for r in rows) if d]
    print(f"\nВсего строк в выгрузке:        {len(rows)}")
    print(f"Дублей (тот же id+игра+мест):  {dup_count}")
    print(f"Уникальных заявок:             {len(dedup)}")
    print(f"Период:                        {min(dts):%d.%m.%Y} — {max(dts):%d.%m.%Y}"
          f"  ({(max(dts) - min(dts)).days} дней)")

    # ---------------------------------------------------- 1. БАЗА
    ids = [r["Id пользователя"] for r in dedup if r["Id пользователя"]]
    uniq_ids = set(ids)
    with_phone = sum(1 for r in dedup
                     if re.search(r"\d{6,}", r.get("Номер телефона (по желанию):", "") or ""))
    phones = set()
    for r in dedup:
        p = re.sub(r"\D", "", r.get("Номер телефона (по желанию):", "") or "")
        if len(p) >= 10:
            phones.add(p[-10:])

    print("\n" + "-" * 78)
    print("1. РАЗМЕР БАЗЫ (актив, который лежит без дела)")
    print("-" * 78)
    print(f"Уникальных id ВК:              {len(uniq_ids)}")
    print(f"Заявок с телефоном:            {with_phone}  ({pct(with_phone, len(dedup))})")
    print(f"Уникальных телефонов:          {len(phones)}")
    print(f"→ на LAL нужно от 300 id:      {'ХВАТАЕТ с запасом' if len(uniq_ids) > 300 else 'НЕ ХВАТАЕТ'}")

    # ---------------------------------------------------- 2. УДЕРЖАНИЕ
    per_user = Counter(ids)
    dist = Counter(per_user.values())
    total_users = len(per_user)

    print("\n" + "-" * 78)
    print("2. УДЕРЖАНИЕ — сколько раз один человек подаёт заявку")
    print("-" * 78)
    print(f"{'Заявок':>8} | {'Людей':>6} | {'Доля':>6} | {'Заявок всего':>12}")
    print("-" * 45)
    cum_apps = 0
    for k in sorted(dist):
        apps = k * dist[k]
        cum_apps += apps
        label = f"{k}" if k < 10 else f"{k}+"
        print(f"{label:>8} | {dist[k]:>6} | {pct(dist[k], total_users)} | {apps:>12}")
    print("-" * 45)

    once = dist[1]
    repeat = total_users - once
    repeat_apps = sum(k * v for k, v in dist.items() if k > 1)
    print(f"\nПришли ОДИН раз:               {once} чел ({pct(once, total_users)})")
    print(f"Вернулись 2+ раз:              {repeat} чел ({pct(repeat, total_users)})")
    print(f"Заявок от вернувшихся:         {repeat_apps} ({pct(repeat_apps, len(dedup))} всех заявок)")
    print(f"Среднее число заявок на чел:   {len(dedup) / total_users:.2f}")
    top = per_user.most_common(10)
    print(f"\nТоп-10 по числу заявок:        {', '.join(str(c) for _, c in top)}")

    # LTV в местах
    seats_by_user = defaultdict(int)
    for r in dedup:
        s = parse_seats(r.get("Сколько вам нужно мест (реалистично): "))
        if s and r["Id пользователя"]:
            seats_by_user[r["Id пользователя"]] += s
    if seats_by_user:
        vals = sorted(seats_by_user.values())
        avg_seats_ltv = sum(vals) / len(vals)
        med_seats_ltv = vals[len(vals) // 2]
        print(f"\nLTV одного «организатора» (кто подаёт заявку) в местах:")
        print(f"  среднее                      {avg_seats_ltv:.1f} мест "
              f"→ прибыль {avg_seats_ltv * 300:,.0f} ₽".replace(",", " "))
        print(f"  МЕДИАНА                      {med_seats_ltv} мест "
              f"→ прибыль {med_seats_ltv * 300:,.0f} ₽".replace(",", " "))
        print(f"  (среднее задрано ядром: топ-1% привёл "
              f"{sum(vals[-17:]):,} мест)".replace(",", " "))
        print(f"  → потолок CAC за организатора считать по МЕДИАНЕ")

    # доля выручки, которую делает ядро
    tot_seats_all = sum(seats_by_user.values())
    core = sorted(seats_by_user.values(), reverse=True)
    for share in (0.05, 0.10, 0.20):
        n = int(len(core) * share)
        print(f"  топ-{int(share * 100)}% организаторов дают "
              f"{pct(sum(core[:n]), tot_seats_all)} всех мест")

    # --- ритм возврата и «спящая» часть базы
    hist = defaultdict(list)
    for r in dedup:
        d = parse_dt(r["Дата создания"])
        if d and r["Id пользователя"]:
            hist[r["Id пользователя"]].append(d)
    gaps = []
    for uid, ds in hist.items():
        ds.sort()
        gaps += [(ds[i + 1] - ds[i]).days for i in range(len(ds) - 1)]
    last_seen = {uid: max(ds) for uid, ds in hist.items()}
    now = max(dts)
    dormant = Counter()
    for uid, d in last_seen.items():
        age = (now - d).days
        for th in (60, 90, 180, 365):
            if age > th:
                dormant[th] += 1

    print("\n" + "-" * 78)
    print("2б. РИТМ ВОЗВРАТА И СПЯЩАЯ БАЗА")
    print("-" * 78)
    if gaps:
        gs = sorted(gaps)
        print(f"Интервал между заявками одного человека:")
        print(f"  медиана                      {gs[len(gs) // 2]} дней")
        print(f"  25-й / 75-й процентиль       {gs[len(gs) // 4]} / {gs[3 * len(gs) // 4]} дней")
        print(f"  до 45 дней (в цикле)         {pct(sum(1 for g in gs if g <= 45), len(gs))}")
    print(f"\nПоследняя заявка была раньше чем:")
    for th in (60, 90, 180, 365):
        print(f"  {th:>3} дней назад            {dormant[th]:>5} чел  ({pct(dormant[th], len(last_seen))} базы)")
    print(f"→ спящие 90+ дней — это и есть пул для реактивации рассылкой")

    # --- когорты: вернулся ли новичок в ОДИНАКОВОЕ окно (иначе сравнение нечестное:
    # у когорты 2023 было 3 года на возврат, у когорты 2026 — два месяца)
    WINDOW = 120
    print(f"\nКогорты по первой заявке — возврат в окно {WINDOW} дней "
          f"(равные условия для всех):")
    coh = defaultdict(lambda: [0, 0])
    for uid, ds in hist.items():
        first = min(ds)
        if (now - first).days < WINDOW:   # окно ещё не закрылось — не сравниваем
            continue
        k = f"{first.year}-H{1 if first.month <= 6 else 2}"
        coh[k][0] += 1
        if any(0 < (d - first).days <= WINDOW for d in ds):
            coh[k][1] += 1
    for k in sorted(coh):
        tot, ret = coh[k]
        bar = "#" * round(20 * ret / tot) if tot else ""
        print(f"  {k}  пришли впервые {tot:>4}, вернулись {ret:>4} = {pct(ret, tot)}  {bar}")

    print("\nТо же без ограничения окна (вернулся когда угодно, справочно):")
    coh2 = defaultdict(lambda: [0, 0])
    for uid, ds in hist.items():
        first = min(ds)
        if (now - first).days < WINDOW:
            continue
        k = f"{first.year}-H{1 if first.month <= 6 else 2}"
        coh2[k][0] += 1
        if len(ds) > 1:
            coh2[k][1] += 1
    for k in sorted(coh2):
        tot, ret = coh2[k]
        print(f"  {k}  {pct(ret, tot)}")

    # ---------------------------------------------------- 3. НОВИЧКИ
    firsts = Counter(norm_first(r.get("Вы собираетесь к нам впервые?")) for r in dedup)
    known = firsts["новичок"] + firsts["опытный"]
    print("\n" + "-" * 78)
    print("3. НОВИЧКИ vs ОПЫТНЫЕ (самоидентификация в форме)")
    print("-" * 78)
    print(f"«Да, я первоход»:              {firsts['новичок']}  ({pct(firsts['новичок'], known)})")
    print(f"«Нет, я опытный»:              {firsts['опытный']}  ({pct(firsts['опытный'], known)})")

    # по годам
    print("\nДоля новичков по кварталам:")
    q = defaultdict(Counter)
    for r in dedup:
        d = parse_dt(r["Дата создания"])
        f = norm_first(r.get("Вы собираетесь к нам впервые?"))
        if d and f:
            q[f"{d.year}-Q{(d.month - 1) // 3 + 1}"][f] += 1
    for k in sorted(q):
        n, o = q[k]["новичок"], q[k]["опытный"]
        bar = "#" * round(20 * n / (n + o)) if (n + o) else ""
        print(f"  {k}  новичков {n:>4} / опытных {o:>4}  = {pct(n, n + o)}  {bar}")

    # ---------------------------------------------------- 4. АТРИБУЦИЯ
    src = Counter(norm_source(r.get("Где вы увидели анонс игры? (вк\\тг\\реклама\\друзья\\свой вариант)"))
                  for r in dedup)
    print("\n" + "-" * 78)
    print("4. ОТКУДА УЗНАЛИ ОБ ИГРЕ (самоатрибуция, поле в форме)")
    print("-" * 78)
    tot_src = sum(v for k, v in src.items() if k != "не указан")
    for k, v in src.most_common():
        if k == "не указан":
            continue
        bar = "#" * round(40 * v / max(src.values()))
        print(f"{k:<26} {v:>5}  {pct(v, tot_src)}  {bar}")
    print(f"{'не указан':<26} {src['не указан']:>5}")

    # атрибуция отдельно у новичков — что реально ПРИВОДИТ
    print("\nТо же, только среди НОВИЧКОВ (что реально приводит нового человека):")
    src_new = Counter(
        norm_source(r.get("Где вы увидели анонс игры? (вк\\тг\\реклама\\друзья\\свой вариант)"))
        for r in dedup if norm_first(r.get("Вы собираетесь к нам впервые?")) == "новичок"
    )
    tot_new = sum(v for k, v in src_new.items() if k != "не указан")
    for k, v in src_new.most_common(9):
        if k == "не указан":
            continue
        print(f"  {k:<24} {v:>5}  {pct(v, tot_new)}")

    # ---------------------------------------------------- 5. РАЗМЕР КОМПАНИИ
    seats = [s for s in (parse_seats(r.get("Сколько вам нужно мест (реалистично): "))
                         for r in dedup) if s]
    seats_dist = Counter(seats)
    print("\n" + "-" * 78)
    print("5. РАЗМЕР КОМПАНИИ (мест в одной заявке)")
    print("-" * 78)
    print(f"Заявок с распознанным числом:  {len(seats)}")
    print(f"Всего мест заявлено:           {sum(seats)}")
    print(f"Среднее на заявку:             {sum(seats) / len(seats):.2f}")
    print(f"Медиана:                       {sorted(seats)[len(seats) // 2]}")
    print("\nРаспределение:")
    for k in sorted(seats_dist):
        if k > 15:
            continue
        bar = "#" * round(40 * seats_dist[k] / max(seats_dist.values()))
        print(f"  {k:>2} мест  {seats_dist[k]:>5}  {pct(seats_dist[k], len(seats))}  {bar}")
    big = sum(v for k, v in seats_dist.items() if k > 15)
    print(f"  16+     {big:>5}  {pct(big, len(seats))}")

    # ---------------------------------------------------- 6. ДИНАМИКА
    print("\n" + "-" * 78)
    print("6. ДИНАМИКА ПО МЕСЯЦАМ (по дате подачи заявки)")
    print("-" * 78)
    m_apps = Counter()
    m_seats = Counter()
    m_new = Counter()
    for r in dedup:
        d = parse_dt(r["Дата создания"])
        if not d:
            continue
        key = f"{d.year}-{d.month:02d}"
        m_apps[key] += 1
        s = parse_seats(r.get("Сколько вам нужно мест (реалистично): "))
        if s:
            m_seats[key] += s
        if norm_first(r.get("Вы собираетесь к нам впервые?")) == "новичок":
            m_new[key] += 1
    print(f"{'Месяц':<9} {'Заявок':>7} {'Мест':>7} {'Новичков':>9} {'Ср.чек мест':>12}")
    print("-" * 50)
    for k in sorted(m_apps):
        avg = m_seats[k] / m_apps[k] if m_apps[k] else 0
        bar = "#" * round(30 * m_seats[k] / max(m_seats.values()))
        print(f"{k:<9} {m_apps[k]:>7} {m_seats[k]:>7} {m_new[k]:>9} {avg:>11.1f}  {bar}")

    # ---------------------------------------------------- 7. ПО ИГРАМ
    print("\n" + "-" * 78)
    print("7. ПО ИГРАМ (последние 20 дат мероприятий)")
    print("-" * 78)
    g_apps = Counter()
    g_seats = Counter()
    g_new = Counter()
    for r in dedup:
        gdate, price = parse_game(r.get("Выберите дату мероприятия"))
        if not gdate:
            continue
        g_apps[gdate] += 1
        s = parse_seats(r.get("Сколько вам нужно мест (реалистично): "))
        if s:
            g_seats[gdate] += s
        if norm_first(r.get("Вы собираетесь к нам впервые?")) == "новичок":
            g_new[gdate] += 1

    def gkey(x):
        d, m, y = x.split(".")
        return (y, m, d)

    print(f"{'Игра':<10} {'Заявок':>7} {'Мест':>7} {'Новичков':>9} {'Доля нов.':>10}")
    print("-" * 48)
    for k in sorted(g_apps, key=gkey)[-20:]:
        print(f"{k:<10} {g_apps[k]:>7} {g_seats[k]:>7} {g_new[k]:>9} "
              f"{pct(g_new[k], g_apps[k]):>10}")

    all_games = [g for g in g_seats.values() if g]
    if all_games:
        print(f"\nВсего игр с заявками:          {len(g_apps)}")
        print(f"Медиана мест на игру:          {sorted(all_games)[len(all_games) // 2]}")
        print(f"Максимум мест на игру:         {max(all_games)}")

    # ---------------------------------------------------- 8. ПРОМО / ПРОХОДКИ
    promo = [r.get("Промокод, если вы его где-то достали:", "") or "" for r in dedup]
    free = sum(1 for p in promo
               if re.search(r"проходк|ваучер|бесплат|сертификат|пригласит|прохо",
                            p.lower()))
    any_promo = sum(1 for p in promo if p.strip() and p.strip() not in ("-", "нет", "Нет"))
    print("\n" + "-" * 78)
    print("8. ПРОМОКОДЫ И БЕСПЛАТНЫЕ ПРОХОДКИ")
    print("-" * 78)
    print(f"Заявок с чем-то в поле промо:  {any_promo}  ({pct(any_promo, len(dedup))})")
    print(f"Из них явные проходки/ваучеры: {free}  ({pct(free, len(dedup))} всех заявок)")

    # ---------------------------------------------------- 9. ГЕО / ПОЛ
    city = Counter((r.get("Город") or "не указан").strip() for r in dedup)
    gender = Counter((r.get("Пол") or "?").strip() for r in dedup)
    print("\n" + "-" * 78)
    print("9. ГЕО И ПОЛ")
    print("-" * 78)
    tot_city = sum(v for k, v in city.items() if k not in ("", "не указан"))
    for k, v in city.most_common(8):
        if k in ("", "не указан"):
            continue
        print(f"{k:<22} {v:>5}  {pct(v, tot_city)}")
    print(f"{'(не указан)':<22} {city['не указан'] + city['']:>5}")
    tot_g = gender["Ж"] + gender["М"]
    print(f"\nЖенщины: {gender['Ж']} ({pct(gender['Ж'], tot_g)})   "
          f"Мужчины: {gender['М']} ({pct(gender['М'], tot_g)})")

    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()
