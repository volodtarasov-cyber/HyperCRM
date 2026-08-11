"""
Собирает заполненный Excel-скринер для пилота Левша / антигравийная плёнка.
Берёт шаблон `business-market-screening.xlsx` (пустой скринер),
заполняет E..K на листе «Скринер» данными из MD-отчёта пилота
и сохраняет рядом с отчётом в `projects/detailing-samara/analytics/`.
"""
import re
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill

ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_XLSX = ROOT / "projects/agency-os/templates/business-market-screening.xlsx"
REPORT_MD = ROOT / "projects/detailing-samara/analytics/business-market-screening-ppf-2026-06-03.md"
OUT_XLSX = ROOT / "projects/detailing-samara/analytics/business-market-screening-ppf-2026-06-03.xlsx"

# ============================================================
# 1. ПАРСЕР MD-ОТЧЁТА — раздел «Оценки Факторов»
# ============================================================
def parse_pilot_factors():
    text = REPORT_MD.read_text(encoding="utf-8")
    # Берём блок после "## Внутреннее Приложение: Оценки Факторов"
    block = text.split("## Внутреннее Приложение: Оценки Факторов", 1)[1]
    block = block.split("## Источники Пилота", 1)[0]
    # Строки таблицы: | F01 | ответ | балл | основание | уверенность | комментарий |
    rows = re.findall(
        r"^\| (F\d+) \| (.*?) \| (.*?) \| (.+?) \| (.+?) \| (.+?) \|$",
        block,
        re.MULTILINE,
    )
    by_id = {}
    for fid, answer, score, basis, conf, comment in rows:
        answer = answer.strip()
        score = score.strip()
        score_val = float(score.replace(",", ".")) if score else None
        by_id[fid] = {
            "answer": answer,
            "score": score_val,
            "basis": basis.strip(),
            "confidence": conf.strip(),
            "comment": comment.strip(),
        }
    return by_id


# ============================================================
# 2. МЕТАДАННЫЕ ПАСПОРТА (что напишем в начало листа «Сводка»)
# ============================================================
PASSPORT = [
    ("Компания", "Левша"),
    ("Направление / продукт", "Антигравийная плёнка / PPF"),
    ("География", "Самара"),
    ("Период анализа", "2025-01 — 2026-04"),
    ("Дата скрининга", "2026-06-03"),
    ("Кто проводил анализ", "Володя + Claude"),
    ("Источники", "1С, Б24, лендинг плёнки, рекламные кабинеты, аналитика проекта"),
    ("Бизнес-цель 3–6 мес", "Удвоить выручку плёнки и закрыть утечку A-клиентов"),
]


# ============================================================
# 3. ЗАПОЛНЕНИЕ XLSX
# ============================================================
DARK = "2B223A"
YELLOW = "FFBA24"
WHITE = "FFFFFF"


def fill_screener(ws, pilot):
    """Заполняем колонки E..K по факторам."""
    # Колонки: 5=ответ, 6=балл, 7=основание, 8=источник, 9=уверенность, 10=комментарий, 11=следующий шаг
    # Строки начинаются со 2.
    for row in range(2, 60):
        fid_cell = ws.cell(row=row, column=1).value
        if not fid_cell:
            continue
        fid = str(fid_cell).strip()
        data = pilot.get(fid)
        if not data:
            continue
        ws.cell(row=row, column=5, value=data["answer"] or "")
        ws.cell(row=row, column=6, value=data["score"] if data["score"] is not None else "")
        ws.cell(row=row, column=7, value=data["basis"])
        # Источник доказательства — берём из комментария / отдельных меток;
        # в этом пилоте используем общий блок "Источники Пилота" в MD, поэтому в колонку 8
        # кладём краткий тег:
        source_tag = source_tag_for(fid)
        ws.cell(row=row, column=8, value=source_tag)
        ws.cell(row=row, column=9, value=data["confidence"])
        ws.cell(row=row, column=10, value=data["comment"])
        # Следующий шаг: оставим пустым кроме факторов с пометкой "Неизвестно"
        if data["basis"] == "Неизвестно":
            ws.cell(row=row, column=11, value=next_step_for_unknown(fid))


def source_tag_for(fid):
    """Источник доказательства — короткий тег. Для пилота — общий пул источников."""
    tags = {
        "F01": "Внеш.: 10+ детейлинг-центров Самары; внутр.: Я.Директ/Авито",
        "F02": "Внеш.: рейтинги SunTek/Llumar/Spectroll; внутр.: конкур. анализ",
        "F03": "Внутр.: service-seasonality-2026-05-19.md",
        "F05": "Отрасль / автопарк",
        "F07": "Косвенно из CRM и интервью",
        "F08": "1С: адреса клиентов",
        "F09": "film-orders-distribution-from2025-2026-06-02.md",
        "F10": "Прайс PPF, рынок",
        "F11": "Договоры / способ продажи",
        "F12": "Природа PPF",
        "F13": "film-orders-distribution-from2025-2026-06-02.md",
        "F15": "Cross-sell данные",
        "F16": "Линейка Quantum Pro / Rocket",
        "F17": "marketing/positioning.md",
        "F18": "Я.Директ, Авито, карты, рекомендации",
        "F19": "Список носителей Левши",
        "F23": "История компании",
        "F25": "Внеш.: Я.Карты №1 по оценкам (751 vs 675 GoodZone), 2ГИС 4,6/77; внутр.: VoC, рейтинг 5,0",
        "F26": "Б24 (актив)",
        "F27": "sales/first-touch-regulation.md",
        "F28": "film-orders-distribution-from2025-2026-06-02.md",
        "F31": "Контент-аудит, кейс-банк не запущен",
        "F32": "client-intelligence.md, JTBD-карта",
        "F33": "Лендинг плёнки, Авито-инфографика",
        "F34": "Б24 + 1С, нет КТ",
        "F35": "Оргструктура Левши",
        "F37": "ad-budget.md",
        "F38": "Бюджет одобрен, не запущен",
        "F39": "Командная рамка",
        "F40": "1С: география продаж",
        "F41": "Володя — КД",
        "F44": "marketing/film-funnel/_index.md",
        "F45": "Внутр.: разбор GoodZone+Манго+i-Graphics+Autoprotect; внеш.: Я.Карты + 2ГИС (нужно расширить на топ-7 и узкие PPF)",
        "F46": "Анализ кампаний",
        "F47": "marketing/positioning.md + traffic strategy",
        "F51": "abc-a-confirmed-clients-2026-05-26.csv",
        "F52": "Бизнес-модель",
        "F54": "Внеш.: Росстат — Самара 1 154 223 чел. (01.01.2025)",
        "F58": "Перечень регламентов проекта",
        "F55": "Внеш.: парк 1,086 млн (АВТОСТАТ); внутр.: 410 уник. клиентов",
    }
    return tags.get(fid, "")


def next_step_for_unknown(fid):
    steps = {
        "F04": "Сопоставить продажи с погодой",
        "F06": "Тест цены / A/B пакетов",
        "F14": "Считать дни от обращения до оплаты в Б24",
        "F20": "Собрать P&L плёнки за 6+ мес",
        "F21": "Учёт возвратов и переделок",
        "F22": "Учёт обращение → продажа после запуска КТ",
        "F24": "Аудит ключевых ролей",
        "F29": "Разрез выручки по пакетам/зонам",
        "F30": "Подтвердить P&L / ДДС по направлению",
        "F36": "Аудит форматов внутри Я.Директа и Авито",
        "F42": "Зафиксировать схему мотивации приёмщиков",
        "F43": "Уточнить контур внимания собственника",
        "F48": "Учёт обращений по PPF после КТ",
        "F49": "Сравнить поток и мощность загрузки",
        "F50": "Подтвердить мощность и загрузку PPF",
        "F53": "Анализ зависимости от Quantum-поставщиков",
        # F55 закрыт во внешнем слое — задачи нет
        "F56": "Зафиксировать численность команды",
        "F57": "Аудит карт процессов",
    }
    return steps.get(fid, "Поставить задачу на исследование")


# ============================================================
# 4. ЛИСТ «Паспорт» — добавляем в начало книги
# ============================================================
def add_passport_sheet(wb):
    if "Паспорт" in wb.sheetnames:
        return
    ws = wb.create_sheet("Паспорт", 0)
    # Заголовок
    ws["A1"] = "Паспорт пилота скрининга"
    ws["A1"].font = Font(name="Calibri", size=14, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=DARK)
    ws.merge_cells("A1:B1")
    ws.row_dimensions[1].height = 28
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

    # Поля паспорта
    for i, (k, v) in enumerate(PASSPORT, start=3):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
        ws.cell(row=i, column=1).alignment = Alignment(vertical="top", wrap_text=True)
        ws.cell(row=i, column=2).alignment = Alignment(vertical="top", wrap_text=True)

    # Пояснение
    note_row = 3 + len(PASSPORT) + 2
    ws.cell(row=note_row, column=1, value="Методология").font = Font(bold=True)
    ws.cell(row=note_row, column=2,
            value="projects/agency-os/modules/business-market-screening.md")
    ws.cell(row=note_row + 1, column=1, value="Полный отчёт").font = Font(bold=True)
    ws.cell(row=note_row + 1, column=2,
            value="analytics/business-market-screening-ppf-2026-06-03.md")

    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 80


# ============================================================
# MAIN
# ============================================================
def main():
    pilot = parse_pilot_factors()
    print(f"Распознано факторов в отчёте: {len(pilot)}")

    wb = load_workbook(TEMPLATE_XLSX)

    # Заполняем лист «Скринер»
    fill_screener(wb["Скринер"], pilot)

    # Добавляем лист паспорта
    add_passport_sheet(wb)

    wb.save(OUT_XLSX)
    print(f"✓ Сохранён: {OUT_XLSX}")


if __name__ == "__main__":
    main()
