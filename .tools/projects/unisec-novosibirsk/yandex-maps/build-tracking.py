from __future__ import annotations

import csv
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4] / "clients" / "unisec-novosibirsk"
LAUNCH = ROOT / "semantics" / "launch-clusters.csv"
OUT = ROOT / "yandex-maps-keywords-tracking.csv"
PLAIN_LIST = ROOT / "yandex-maps-keywords-list.txt"
MARKDOWN_LIST = ROOT / "yandex-maps-keywords-list.md"
LOG = ROOT / "yandex-maps-rank-log-template.csv"
SUMMARY = ROOT / "yandex-maps-keywords-tracking.md"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().lower().replace("ё", "е")
    return " ".join(value.split())


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# query, priority, tracking_type. Все небрендовые запросы, кроме явно помеченных synthetic,
# взяты из launch-clusters.csv и уже прошли проверку релевантности.
TRACKING = [
    ("unisec", "P0", "brand_control"),
    ("unisec новосибирск", "P0", "brand_control"),
    ("юнисэк химчистка", "P0", "brand_control"),

    ("химчистка", "P1", "core"),
    ("химчистка одежды", "P1", "core"),
    ("услуги химчистки", "P1", "core"),
    ("химчистка рядом", "P1", "local"),
    ("химчистка рядом со мной", "P1", "local_synthetic"),
    ("химчистка одежды рядом", "P1", "local"),
    ("химчистка новосибирск", "P1", "local"),
    ("химчистка одежды в новосибирске", "P1", "local"),
    ("прачечная", "P1", "core"),
    ("прачечная рядом", "P1", "local"),
    ("ремонт одежды", "P1", "core"),
    ("ремонт одежды рядом", "P1", "local"),
    ("ателье по ремонту одежды", "P1", "core"),
    ("химчистка обуви", "P1", "service"),
    ("химчистка кроссовок", "P1", "service"),
    ("химчистка пуховика", "P1", "service"),
    ("химчистка куртки", "P1", "service"),
    ("химчистка пальто", "P1", "service"),
    ("химчистка верхней одежды", "P1", "service"),
    ("химчистка свадебного платья", "P1", "service"),
    ("химчистка кожаной куртки", "P1", "service"),
    ("химчистка шубы", "P1", "service"),
    ("химчистка штор", "P1", "service"),
    ("чистка подушек", "P1", "service"),
    ("химчистка колясок", "P1", "service"),

    ("химчистка платья", "P2", "service"),
    ("химчистка костюма", "P2", "service"),
    ("химчистка пиджака", "P2", "service"),
    ("химчистка брюк", "P2", "service"),
    ("химчистка рубашки", "P2", "service"),
    ("химчистка джинсов", "P2", "service"),
    ("химчистка дубленки", "P2", "service"),
    ("химчистка сумок", "P2", "service"),
    ("химчистка одеяла", "P2", "service"),
    ("химчистка пледа", "P2", "service"),
    ("химчистка мягких игрушек", "P2", "service"),
    ("химчистка наматрасника", "P2", "service"),
    ("чистка детского автокресла", "P2", "service"),
    ("химчистка детской одежды", "P2", "service"),
    ("химчистка рюкзака", "P2", "service"),
    ("химчистка чемодана", "P2", "service"),
    ("стирка постельного белья", "P2", "service"),
    ("услуги глажки", "P2", "service"),
    ("замена молнии на куртке", "P2", "service"),
    ("ремонт молнии", "P2", "service"),
    ("подшить брюки", "P2", "service"),
    ("укоротить пальто", "P2", "service"),

    ("ушить одежду", "P3", "niche"),
    ("заузить брюки", "P3", "niche"),
    ("реставрация обуви", "P3", "niche"),
    ("реставрация сумок", "P3", "niche"),
    ("покраска одежды", "P3", "niche"),
    ("озонирование одежды", "P3", "niche"),
    ("озонирование хоккейной формы", "P3", "niche"),
    ("химчистка с доставкой", "P3", "niche"),
    ("аквачистка", "P3", "niche"),
    ("химчистка горнолыжной одежды", "P3", "niche"),

    ("сколько стоит химчистка", "P2", "price_modifier"),
    ("химчистка пуховика цены", "P2", "price_modifier"),
    ("химчистка куртки цена", "P2", "price_modifier"),
    ("замена молнии на куртке цена", "P2", "price_modifier"),
    ("сколько стоит подшить брюки", "P2", "price_modifier"),
]


MANUAL = {
    normalize("unisec"): ("brand", "Бренд", ""),
    normalize("unisec новосибирск"): ("brand", "Бренд", ""),
    normalize("юнисэк химчистка"): ("brand", "Бренд", ""),
    normalize("химчистка рядом со мной"): ("dry-clean-general", "Общая химчистка", "синтетический локальный вариант"),
    normalize("подшить брюки"): ("repair-hemming", "Подшив брюк и джинсов", "базовая формулировка услуги из прайса"),
}


SETTINGS = {
    "P0": ("weekly", "каждая действующая карточка + центр Новосибирска", "top_1"),
    "P1": ("weekly", "центр Новосибирска + координата каждой действующей точки", "top_3"),
    "P2": ("every_2_weeks", "координата каждой действующей точки", "top_5"),
    "P3": ("monthly", "центр Новосибирска + три пилотные точки", "top_10"),
}


def main() -> None:
    launch = read_csv(LAUNCH)
    lookup = {normalize(row["normalized"]): row for row in launch}
    rows: list[dict[str, object]] = []
    missing: list[str] = []

    for query, priority, tracking_type in TRACKING:
        key = normalize(query)
        source = lookup.get(key)
        if source:
            cluster_id = source["cluster_id"]
            group = source["ad_group"]
            frequency = source["frequency"]
            quoted_frequency = source["quoted_frequency"]
            exact_frequency = source["exact_frequency"]
            note = ""
        elif key in MANUAL:
            cluster_id, group, note = MANUAL[key]
            frequency = quoted_frequency = exact_frequency = ""
        else:
            missing.append(query)
            continue

        cadence, points, benchmark = SETTINGS[priority]
        rows.append({
            "query": query,
            "priority": priority,
            "tracking_type": tracking_type,
            "cluster_id": cluster_id,
            "service_group": group,
            "frequency": frequency,
            "quoted_frequency": quoted_frequency,
            "exact_frequency": exact_frequency,
            "region": "Новосибирск",
            "cadence": cadence,
            "measurement_points": points,
            "benchmark": benchmark,
            "status": "active",
            "note": note,
        })

    if missing:
        raise AssertionError(f"Queries absent from launch semantics: {missing}")
    keys = [normalize(str(row["query"])) for row in rows]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise AssertionError(f"Duplicate queries: {duplicates}")
    banned = ("ковр", "диван")
    for row in rows:
        if any(word in normalize(str(row["query"])) for word in banned):
            raise AssertionError(f"Banned service in tracking: {row['query']}")

    fields = [
        "query", "priority", "tracking_type", "cluster_id", "service_group",
        "frequency", "quoted_frequency", "exact_frequency", "region", "cadence",
        "measurement_points", "benchmark", "status", "note",
    ]
    write_csv(OUT, rows, fields)

    PLAIN_LIST.write_text(
        "\n".join(str(row["query"]) for row in rows) + "\n",
        encoding="utf-8",
    )

    priority_titles = {
        "P0": "P0 — брендовый контроль",
        "P1": "P1 — основные запросы, еженедельно",
        "P2": "P2 — услуги и цена, раз в две недели",
        "P3": "P3 — нишевые запросы, раз в месяц",
    }
    markdown_lines = [
        "# Запросы для мониторинга UNISEC в Яндекс Картах",
        "",
        "Регион: Новосибирск  ",
        "Всего: 65 запросов  ",
        "Ковры и диваны исключены.",
    ]
    for priority in ("P0", "P1", "P2", "P3"):
        markdown_lines += ["", f"## {priority_titles[priority]}", ""]
        for row in rows:
            if row["priority"] == priority:
                markdown_lines.append(f"- {row['query']}")
    MARKDOWN_LIST.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    log_fields = [
        "check_date", "query", "measurement_point", "latitude", "longitude",
        "device", "signed_in", "target_branch", "displayed_unisec_branch",
        "position", "top_1_competitor", "top_2_competitor", "top_3_competitor",
        "screenshot_path", "comment",
    ]
    write_csv(LOG, [], log_fields)

    counts = Counter(str(row["priority"]) for row in rows)
    types = Counter(str(row["tracking_type"]) for row in rows)
    lines = [
        "# Ключевые запросы для мониторинга UNISEC в Яндекс Картах",
        "",
        "**Сформировано:** 2026-09-28  ",
        "**Регион:** Новосибирск  ",
        "**Контур:** B2C; ковры и диваны исключены",
        "",
        "## Состав",
        "",
        f"- Всего запросов: **{len(rows)}**.",
        f"- P0, брендовый контроль: **{counts['P0']}**.",
        f"- P1, основные запросы: **{counts['P1']}**.",
        f"- P2, услуги и ценовые модификаторы: **{counts['P2']}**.",
        f"- P3, нишевые направления: **{counts['P3']}**.",
        "",
        "## Как снимать позиции",
        "",
        "Позиция в Картах зависит от координаты пользователя. Поэтому один и тот же запрос нельзя сравнивать сегодня из центра города, а через неделю — рядом с филиалом.",
        "",
        "- P0 и P1 проверять еженедельно.",
        "- P2 — раз в две недели, P3 — раз в месяц.",
        "- Использовать одинаковые координаты, устройство, режим без авторизации и одинаковый масштаб карты.",
        "- Для каждой проверки сохранять: позицию, показанный филиал UNISEC, трёх лидеров выдачи и скриншот.",
        "- Если показываются разные филиалы UNISEC, фиксировать каждый отдельно: сеть нельзя оценивать одной общей позицией.",
        "- Адресные запросы не добавлены, пока не подтверждён актуальный список действующих карточек.",
        "",
        "## Метрики динамики",
        "",
        "- медианная позиция по P1 на каждой точке измерения;",
        "- доля запросов в Top-3, Top-5 и Top-10;",
        "- число запросов, по которым показан любой филиал UNISEC;",
        "- число запросов, по которым показана нужная ближайшая точка;",
        "- изменение позиции относительно первого замера и предыдущей проверки.",
        "",
        "## Файлы",
        "",
        "- `yandex-maps-keywords-tracking.csv` — активное ядро мониторинга.",
        "- `yandex-maps-keywords-list.txt` — чистый список: один запрос на строку.",
        "- `yandex-maps-keywords-list.md` — тот же список, разбитый по приоритетам.",
        "- `yandex-maps-rank-log-template.csv` — пустой шаблон для результатов замеров.",
        "",
        "## Ограничение частотности",
        "",
        "`exact_frequency` относится к исходной семантике, `quoted_frequency` — к расширению по прайсу. Пустая частотность означает, что запрос добавлен как брендовый контроль или синтетический локальный вариант; цифры разных типов не складываются.",
    ]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"queries={len(rows)} priorities={dict(counts)} types={dict(types)}")


if __name__ == "__main__":
    main()
