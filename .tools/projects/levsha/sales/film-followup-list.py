"""Рабочий список дожима незакрытых заявок по плёнке из выгрузки сделок Битрикс24 Левши.

Берёт сделки воронки «Пленка», отбирает незакрытые и проигранные с причиной,
которую можно вернуть, и раскладывает их по сегментам дожима с контекстом:
машина, что спрашивал, названная сумма, канал, где писать. Метод и тексты
касаний → clients/levsha/results/film-unclosed-followup-2026-10-15.md.

Запуск:
    .tools/venv/Scripts/python.exe .tools/projects/levsha/sales/film-followup-list.py <deals.csv>
        [--today YYYY-MM-DD] [--min-days 7] [--max-days 60] [--wave2-days 120] [--out DIR]

Вход — выгрузка сделок Б24 (CSV, «;»), лучше с полями контакта: без них в списке
нет телефонов и мессенджеров. Кладите её в inbox/ рядом со скриптом.
Выход — film-followup-<дата>.csv (UTF-8 с BOM, открывается в Excel) и summary.txt
в out/. В обоих — персональные данные клиентов: папки inbox/ и out/ не версионируются.
"""
import argparse
import csv
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Стадия → (сегмент, приоритет, шаблон первого касания). Названия стадий — как в Б24 Левши.
SEGMENTS = {
    "Новая заявка": ("заявка без расчёта", 1, "Ш1"),
    "Произведена оценка": ("цена названа, решения нет", 1, "Ш2"),
    "Плохо обработана менеджером": ("плохо обработали", 1, "Ш3"),
    "Не смогли записать на удобную дату": ("не нашли дату", 1, "Ш4"),
    "Изменились планы клиента": ("изменились планы", 2, "Ш5"),
    "Сделка провалена": ("проиграна без причины", 3, "Ш6"),
    "Нашел более выгодное предложение у конкурентов": ("ушёл к конкуренту", 3, "Ш7"),
}
# Клиент уже купил или записан: такие контакты в дожим не берём.
BOUGHT = {"Сделка успешна", "Автомобиль выдан клиенту", "Автомобиль в работе",
          "Записан на оклейку", "Произведена коррекция"}

# Причина паузы, которую менеджер вписал в название или комментарий сделки.
REASONS = [
    ("нет ответа", r"не отвеча|недоступ|не бер[её]т|не дозвон|сбрасыва|перезвон"),
    ("цена", r"дорог|денег нет|коп[ия]т|бюджет|дешевл"),
    ("сравнивает", r"собира\w* предлож|узна\w* цен|сравнива|изуча\w* цен|мониторит"),
    ("позже", r"осен|весн|зим|позже|отлож|не пришла|после ремонт|после отпуск|потом"),
    ("думает", r"дума"),
    ("сделал в другом месте", r"в другом месте|у конкурент|друг\w* студи"),
]

PHONE_COLS = ["Контакт: Мобильный телефон", "Контакт: Рабочий телефон",
              "Контакт: Другой телефон", "Контакт: Домашний телефон"]
CAR_COLS = ["АВТОМОБИЛЬ", "Какая_у_вас_марка_автомобиля", "Компания"]


def read_rows(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f, delimiter=";"))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Не прочитать {path}: ни UTF-8, ни cp1251")


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def phone_of(row: dict) -> str:
    for col in PHONE_COLS:
        digits = re.sub(r"\D", "", row.get(col, "") or "")
        if len(digits) >= 10:
            return "7" + digits[-10:]
    return ""


def first(row: dict, cols: list[str]) -> str:
    for col in cols:
        v = (row.get(col) or "").strip()
        if v:
            return v
    return ""


def has(row: dict, field: str) -> bool:
    return bool((row.get(field) or "").strip() or (row.get(f"Контакт: {field}") or "").strip())


def channel_of(row: dict, phone: str) -> str:
    """Где писать: там, где клиент уже общался; иначе — мессенджер из карточки; иначе звонок."""
    source = (row.get("Источник") or "").lower()
    if "avito" in source or has(row, "Avito_WZ"):
        return "Авито"
    if has(row, "MaxId_WZ"):
        return "MAX"
    if has(row, "WhatsappUsername_WZ") or has(row, "WhatsappLid_WZ"):
        return "WhatsApp"
    if has(row, "TelegramUsername_WZ") or has(row, "TelegramId_WZ"):
        return "Telegram"
    if "вконтакте" in source or has(row, "VK_WZ"):
        return "ВКонтакте"
    return "звонок, затем мессенджер" if phone else "нет контакта в выгрузке"


def reason_of(*texts: str) -> str:
    text = " ".join(texts).lower().replace("ё", "е")
    found = [name for name, pattern in REASONS if re.search(pattern, text)]
    return ", ".join(found)


def clean(text: str, limit: int = 300) -> str:
    text = re.sub(r"\[/?p\]|BitrixGPT", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", type=Path)
    ap.add_argument("--today", type=date.fromisoformat, default=date.today(),
                    help="дата, от которой считать возраст заявки; для старой выгрузки — дата выгрузки")
    ap.add_argument("--min-days", type=int, default=7, help="моложе — ещё идёт обычная добивка")
    ap.add_argument("--max-days", type=int, default=60, help="граница первой волны")
    ap.add_argument("--wave2-days", type=int, default=120, help="граница второй волны; 0 — без неё")
    ap.add_argument("--out", type=Path, default=HERE / "out")
    args = ap.parse_args()

    rows = read_rows(args.export)
    film = [r for r in rows if (r.get("Воронка") or "").lower().replace("ё", "е").startswith("пленк")]
    if not film:
        raise SystemExit("В выгрузке нет сделок воронки «Пленка»")
    has_contacts = any(c in rows[0] for c in PHONE_COLS)

    bought_phones = {phone_of(r) for r in film if r.get("Стадия сделки") in BOUGHT} - {""}
    skipped = Counter()
    picked: dict[str, dict] = {}

    for r in film:
        stage = r.get("Стадия сделки", "")
        if stage not in SEGMENTS:
            skipped["купил, записан или в работе" if stage in BOUGHT else f"стадия «{stage}»"] += 1
            continue
        created = parse_date(r.get("Дата создания", ""))
        if not created:
            skipped["нет даты создания"] += 1
            continue
        age = (args.today - created).days
        if age < args.min_days:
            skipped[f"моложе {args.min_days} дней — обычная добивка"] += 1
            continue
        if age <= args.max_days:
            wave = 1
        elif args.wave2_days and age <= args.wave2_days:
            wave = 2
        else:
            skipped["старше границы волн"] += 1
            continue
        phone = phone_of(r)
        if phone and phone in bought_phones:
            skipped["этот контакт уже купил или записан"] += 1
            continue

        segment, priority, template = SEGMENTS[stage]
        last = parse_date(r.get("Дата последней коммуникации", "")) or parse_date(r.get("Дата изменения", ""))
        item = {
            "Приоритет": priority,
            "Волна": wave,
            "Сегмент": segment,
            "Шаблон": template,
            "ID сделки": r.get("ID", ""),
            "Дата заявки": created.strftime("%d.%m.%Y"),
            "Дней с заявки": age,
            "Дней с последнего контакта": (args.today - last).days if last else "",
            "Стадия": stage,
            "Машина": first(r, CAR_COLS),
            "Что спрашивал": "; ".join(v for v in (
                clean(r.get("Название сделки", ""), 120),
                (r.get("Какие_части_авто_хотите_оклеить") or "").strip(),
                (r.get("Какой_пленкой_хотите_оклеить") or "").strip(),
            ) if v),
            "Причина по записи": reason_of(r.get("Название сделки", ""), r.get("Комментарий", "")),
            "Сумма, ₽": int(float((r.get("Сумма") or "0").replace(",", ".") or 0)),
            "Источник": r.get("Источник", ""),
            "Канал дожима": channel_of(r, phone),
            "Телефон": phone,
            "Имя": r.get("Контакт", ""),
            "Ответственный": r.get("Ответственный", ""),
            "Комментарий из Б24": clean(r.get("Комментарий", "")),
            "Касание 1": "", "Касание 2": "", "Касание 3": "",
            "Результат": "", "Причина отказа": "", "Что сработало": "",
        }
        # Один клиент — одна строка: оставляем самую свежую заявку.
        key = phone or f"id{item['ID сделки']}"
        prev = picked.get(key)
        if prev is None or created > datetime.strptime(prev["Дата заявки"], "%d.%m.%Y").date():
            if prev is not None:
                skipped["повтор того же клиента"] += 1
            picked[key] = item
        else:
            skipped["повтор того же клиента"] += 1

    items = sorted(picked.values(), key=lambda i: (i["Приоритет"], i["Волна"], -i["Сумма, ₽"]))
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = args.today.isoformat()
    csv_path = args.out / f"film-followup-{stamp}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        if items:
            w = csv.DictWriter(f, fieldnames=list(items[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(items)

    lines = [
        f"Дожим плёнки — выгрузка {args.export.name}, отсчёт от {stamp}",
        f"Сделок в воронке «Пленка»: {len(film)}. Поля контакта в выгрузке: {'есть' if has_contacts else 'НЕТ — телефонов и мессенджеров в списке не будет'}",
        f"Волна 1: {args.min_days}–{args.max_days} дней с заявки; волна 2: {args.max_days + 1}–{args.wave2_days} дней" if args.wave2_days else
        f"Волна 1: {args.min_days}–{args.max_days} дней с заявки",
        "",
        f"В дожим: {len(items)} клиентов",
    ]
    by_seg = defaultdict(lambda: [0, 0, 0, 0])  # волна 1, волна 2, сумма, с суммой
    for i in items:
        s = by_seg[(i["Приоритет"], i["Сегмент"], i["Шаблон"])]
        s[i["Волна"] - 1] += 1
        s[2] += i["Сумма, ₽"]
        s[3] += 1 if i["Сумма, ₽"] else 0
    lines.append(f"{'приор.':<7}{'сегмент':<30}{'шабл.':<6}{'волна 1':>8}{'волна 2':>8}{'с суммой':>10}{'названо, ₽':>14}")
    for (prio, seg, tpl), (w1, w2, total, with_sum) in sorted(by_seg.items()):
        total_txt = f"{total:,}".replace(",", " ")
        lines.append(f"{prio:<7}{seg:<30}{tpl:<6}{w1:>8}{w2:>8}{with_sum:>10}{total_txt:>14}")
    reasons = Counter(r.strip() for i in items for r in (i["Причина по записи"] or "не записана").split(","))
    lines.append(f"\nПричина по записи менеджера: {dict(reasons.most_common())}")
    for seg in sorted({i["Сегмент"] for i in items}):
        seg_reasons = Counter(r.strip() for i in items if i["Сегмент"] == seg
                              for r in (i["Причина по записи"] or "не записана").split(","))
        lines.append(f"  {seg}: {dict(seg_reasons.most_common())}")
    lines.append(f"Каналы: {dict(Counter(i['Канал дожима'] for i in items).most_common())}")
    lines.append("\nНе взяли:")
    for reason, n in skipped.most_common():
        lines.append(f"  {n:4}  {reason}")
    lines.append(f"\nСписок: {csv_path}")

    summary = "\n".join(lines)
    (args.out / f"summary-{stamp}.txt").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
