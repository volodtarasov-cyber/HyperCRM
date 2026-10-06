from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4] / "clients" / "unisec-novosibirsk" / "semantics"
CLUSTERS = ROOT / "clusters.csv"
FREQUENCY = ROOT / "frequency-check.csv"
OUT = ROOT / "launch-clusters.csv"
SUMMARY = ROOT / "launch-cluster-summary.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def ru_plural(value: int, one: str, few: str, many: str) -> str:
    if value % 10 == 1 and value % 100 != 11:
        return one
    if value % 10 in {2, 3, 4} and value % 100 not in {12, 13, 14}:
        return few
    return many


GROUPS: dict[str, dict[str, object]] = {
    "child-clothing": {
        "campaign": "Небренд — детские изделия", "ad_group": "Детская одежда",
        "offer": "Химчистка детской одежды", "tier": "phase_2",
        "phrases": ["химчистка детских вещей", "химчистка детской одежды"],
    },
    "child-car-seats": {
        "campaign": "Небренд — детские изделия", "ad_group": "Детские автокресла",
        "offer": "Чистка детских автокресел", "tier": "phase_2",
        "phrases": ["химчистка детского автокресла", "чистка детского автокресла"],
    },
    "home-curtains": {
        "campaign": "Небренд — домашний текстиль", "ad_group": "Шторы и тюль",
        "offer": "Химчистка штор и тюля", "tier": "phase_1",
        "phrases": ["стирка штор", "химчистка тюля", "чистка штор"],
    },
    "home-blankets-plaids": {
        "campaign": "Небренд — домашний текстиль", "ad_group": "Одеяла, пледы и покрывала",
        "offer": "Химчистка одеял, пледов и покрывал", "tier": "phase_1",
        "phrases": ["химчистка пледа", "химчистка покрывала"],
    },
    "home-mattress-toppers": {
        "campaign": "Небренд — домашний текстиль", "ad_group": "Наматрасники",
        "offer": "Химчистка наматрасников", "tier": "phase_1",
        "phrases": ["химчистка наматрасника"],
    },
    "home-soft-toys": {
        "campaign": "Небренд — домашний текстиль", "ad_group": "Мягкие игрушки",
        "offer": "Химчистка мягких игрушек", "tier": "phase_1",
        "phrases": ["химчистка мягких игрушек", "чистка мягких игрушек", "чистка мягкой игрушки"],
    },
    "home-furniture-covers": {
        "campaign": "Небренд — домашний текстиль", "ad_group": "Чехлы на мебель",
        "offer": "Химчистка мебельных чехлов", "tier": "phase_1",
        "phrases": ["химчистка чехлов на диван"],
    },
    "accessories-travel-clean": {
        "campaign": "Небренд — обувь и сумки", "ad_group": "Рюкзаки и чемоданы",
        "offer": "Химчистка рюкзаков и чемоданов", "tier": "phase_1",
        "phrases": ["химчистка рюкзака", "химчистка чемодана", "чистка чемодана"],
    },
    "special-dyeing": {
        "campaign": "Небренд — специальные услуги", "ad_group": "Крашение одежды",
        "offer": "Профессиональное крашение одежды", "tier": "phase_2",
        "phrases": ["крашение одежды", "окрашивание одежды", "покраска джинсов", "покраска футболки"],
    },
    "footwear-repair": {
        "campaign": "Небренд — обувь и сумки", "ad_group": "Ремонт и восстановление обуви",
        "offer": "Ремонт и восстановление обуви", "tier": "phase_1",
        "phrases": ["восстановление кроссовок"],
    },
    "bags-repair": {
        "campaign": "Небренд — обувь и сумки", "ad_group": "Ремонт сумок",
        "offer": "Ремонт и реставрация сумок", "tier": "phase_1",
        "phrases": ["реставрация кожаной сумки"],
    },
    "footwear-clean": {
        "campaign": "Небренд — обувь и сумки", "ad_group": "Химчистка обуви",
        "offer": "Химчистка обуви", "tier": "phase_1",
        "phrases": ["химчистка ботинок", "химчистка замшевой обуви", "химчистка кожаной обуви", "чистка замшевой обуви", "чистка кожаной обуви"],
    },
    "bags-clean": {
        "campaign": "Небренд — обувь и сумки", "ad_group": "Химчистка сумок",
        "offer": "Химчистка сумок", "tier": "phase_1",
        "phrases": ["химчистка замшевой сумки", "химчистка кожаной сумки", "химчистка сумок"],
    },
    "special-ozonation": {
        "campaign": "Небренд — специальные услуги", "ad_group": "Озонирование одежды",
        "offer": "Озонирование одежды", "tier": "phase_2",
        "phrases": ["озонирование одежды"],
    },
    "special-ozonation-sports": {
        "campaign": "Небренд — специальные услуги", "ad_group": "Озонирование спортивной формы",
        "offer": "Озонирование спортивной формы", "tier": "phase_2",
        "phrases": ["озонирование хоккейной формы"],
    },
    "repair-fit": {
        "campaign": "Небренд — ремонт одежды", "ad_group": "Подгонка одежды по фигуре",
        "offer": "Подгонка одежды по фигуре", "tier": "phase_1",
        "phrases": ["заузить брюки", "ушить джинсы", "ушить одежду", "ушить платье"],
    },
    "laundry-ironing": {
        "campaign": "Небренд — прачечная и глажка", "ad_group": "Глажка",
        "offer": "Услуги глажки одежды и белья", "tier": "phase_1",
        "phrases": ["глажка одежды", "глажка постельного белья", "глажка рубашек", "услуги глажки"],
    },
    "laundry-linens": {
        "campaign": "Небренд — прачечная и глажка", "ad_group": "Стирка белья и полотенец",
        "offer": "Стирка постельного белья и полотенец", "tier": "phase_1",
        "phrases": ["стирка полотенец", "стирка постельного белья"],
    },
    "laundry-delivery": {
        "campaign": "Небренд — прачечная и глажка", "ad_group": "Прачечная с доставкой",
        "offer": "Прачечная с доставкой", "tier": "phase_1",
        "phrases": ["прачечная с доставкой"],
    },
    "dry-clean-delivery": {
        "campaign": "Небренд — химчистка", "ad_group": "Химчистка с доставкой",
        "offer": "Химчистка с доставкой", "tier": "phase_1",
        "phrases": ["химчистка с доставкой"],
    },
    "repair-leather-fur": {
        "campaign": "Небренд — ремонт одежды", "ad_group": "Ремонт кожи и меха",
        "offer": "Ремонт изделий из кожи и меха", "tier": "phase_1",
        "phrases": ["заплатка на кожаной куртке", "ремонт кожаной куртки", "реставрация кожаной куртки", "укоротить шубу"],
    },
    "repair-zippers": {
        "campaign": "Небренд — ремонт одежды", "ad_group": "Замена и ремонт молний",
        "offer": "Замена и ремонт молний на одежде", "tier": "phase_1",
        "phrases": ["замена бегунка на молнии", "замена молнии на брюках", "замена молнии на джинсах", "замена молнии на кожаной куртке", "замена молнии на юбке"],
    },
    "repair-lining": {
        "campaign": "Небренд — ремонт одежды", "ad_group": "Замена подкладки",
        "offer": "Замена подкладки на одежде", "tier": "phase_1",
        "phrases": ["замена подкладки на кожаной куртке", "замена подкладки на пальто", "замена подкладки на пиджаке"],
    },
    "repair-small-jobs": {
        "campaign": "Небренд — ремонт одежды", "ad_group": "Мелкий ремонт одежды",
        "offer": "Мелкий ремонт одежды", "tier": "phase_1",
        "phrases": ["зашить дырку на одежде", "пришить пуговицу", "ремонт трикотажа"],
    },
    "repair-curtains": {
        "campaign": "Небренд — ремонт одежды", "ad_group": "Подшив штор",
        "offer": "Подшив штор", "tier": "phase_1",
        "phrases": ["подшить шторы"],
    },
    "repair-shortening": {
        "campaign": "Небренд — ремонт одежды", "ad_group": "Укорачивание одежды",
        "offer": "Укорачивание одежды", "tier": "phase_1",
        "phrases": ["подшить платье", "подшить юбку", "укоротить пальто", "укоротить рукава"],
    },
    "dry-clean-businesswear": {
        "campaign": "Небренд — химчистка", "ad_group": "Костюмы и деловая одежда",
        "offer": "Химчистка костюмов и деловой одежды", "tier": "phase_1",
        "phrases": ["химчистка брюк", "химчистка галстука", "химчистка джинсов", "химчистка костюма", "химчистка пиджака", "химчистка рубашки"],
    },
    "dry-clean-dresses": {
        "campaign": "Небренд — химчистка", "ad_group": "Платья",
        "offer": "Химчистка платьев", "tier": "phase_1",
        "phrases": ["химчистка вечернего платья", "химчистка платья"],
    },
    "dry-clean-sportswear": {
        "campaign": "Небренд — химчистка", "ad_group": "Спортивная одежда",
        "offer": "Химчистка спортивной одежды", "tier": "phase_1",
        "phrases": ["химчистка горнолыжной одежды", "химчистка спортивной одежды"],
    },
    "dry-clean-leather": {
        "campaign": "Небренд — химчистка", "ad_group": "Кожа, замша и дублёнки",
        "offer": "Химчистка изделий из кожи и замши", "tier": "phase_1",
        "phrases": ["химчистка дубленки", "химчистка замшевой куртки", "химчистка кожаных изделий"],
    },
    "dry-clean-fur": {
        "campaign": "Небренд — химчистка", "ad_group": "Шубы и мех",
        "offer": "Химчистка шуб и меховых изделий", "tier": "phase_1",
        "phrases": ["химчистка искусственной шубы", "химчистка норковой шубы"],
    },
}


REMAP_EXISTING = {
    "home-blankets": ("home-blankets-plaids", "Одеяла, пледы и покрывала", "Химчистка одеял, пледов и покрывал"),
    "repair-zippers": ("repair-zippers", "Замена и ремонт молний", "Замена и ремонт молний на одежде"),
    "dry-clean-leather": ("dry-clean-leather", "Кожа, замша и дублёнки", "Химчистка изделий из кожи и замши"),
    "dry-clean-fur": ("dry-clean-fur", "Шубы и мех", "Химчистка шуб и меховых изделий"),
}


def main() -> None:
    original = read_csv(CLUSTERS)
    freq_rows = read_csv(FREQUENCY)
    semantic_rows = [row for row in freq_rows if row["decision"] == "semantic_test"]
    b2c_rows = [row for row in semantic_rows if row["contour"] != "B2B optional"]
    b2b_rows = [row for row in semantic_rows if row["contour"] == "B2B optional"]

    phrase_to_group: dict[str, str] = {}
    for cluster_id, meta in GROUPS.items():
        for phrase in meta["phrases"]:
            if phrase in phrase_to_group:
                raise AssertionError(f"Duplicate phrase mapping: {phrase}")
            phrase_to_group[phrase] = cluster_id

    expected = {row["query_seed"] for row in b2c_rows}
    mapped = set(phrase_to_group)
    if expected != mapped:
        raise AssertionError(f"Mapping mismatch. Missing={sorted(expected-mapped)}; extra={sorted(mapped-expected)}")
    if len(b2b_rows) != 1 or b2b_rows[0]["query_seed"] != "стирка рабочей одежды":
        raise AssertionError(f"Unexpected B2B semantic rows: {b2b_rows}")

    out: list[dict[str, object]] = []
    for row in original:
        if row["status"] != "active":
            continue
        cluster_id = row["cluster_id"]
        ad_group = row["ad_group"]
        offer = row["offer"]
        if cluster_id in REMAP_EXISTING:
            cluster_id, ad_group, offer = REMAP_EXISTING[cluster_id]
        tier = "phase_2" if row["campaign"] in {"Небренд — специальные услуги", "Небренд — детские изделия"} else "phase_1"
        campaign = row["campaign"]
        if cluster_id in GROUPS:
            group_meta = GROUPS[cluster_id]
            campaign = str(group_meta["campaign"])
            ad_group = str(group_meta["ad_group"])
            offer = str(group_meta["offer"])
            tier = str(group_meta["tier"])
        out.append({
            "keyword": row["keyword"], "normalized": row["normalized"],
            "cluster_id": cluster_id, "campaign": campaign, "ad_group": ad_group,
            "intent": row["intent"], "offer": offer, "landing_page": row["landing_page"],
            "platform": row["platform"], "status": "active", "confidence": row["confidence"],
            "source": "initial_semantics", "launch_tier": tier,
            "frequency": row["frequency"], "quoted_frequency": "", "exact_frequency": row["exact_frequency"],
            "reason": row["reason"],
            "campaign_yandex": campaign, "ad_group_yandex": ad_group,
            "campaign_google": campaign, "ad_group_google": ad_group,
        })

    for row in b2c_rows:
        cluster_id = phrase_to_group[row["query_seed"]]
        meta = GROUPS[cluster_id]
        out.append({
            "keyword": row["query_seed"], "normalized": row["query_seed"],
            "cluster_id": cluster_id, "campaign": meta["campaign"], "ad_group": meta["ad_group"],
            "intent": "transactional", "offer": meta["offer"], "landing_page": "",
            "platform": "both", "status": "active", "confidence": "high",
            "source": "price_wordstat_expansion", "launch_tier": meta["tier"],
            "frequency": row["frequency"], "quoted_frequency": row["quoted_frequency"], "exact_frequency": "",
            "reason": "Услуга подтверждена прайсом; частотность в кавычках по Новосибирску выше нуля",
            "campaign_yandex": meta["campaign"], "ad_group_yandex": meta["ad_group"],
            "campaign_google": meta["campaign"], "ad_group_google": meta["ad_group"],
        })

    normalized = [str(row["normalized"]) for row in out]
    duplicates = [key for key, count in Counter(normalized).items() if count > 1]
    if duplicates:
        raise AssertionError(f"Duplicate launch keywords: {duplicates}")

    consistency: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    for row in out:
        consistency[(str(row["campaign"]), str(row["ad_group"]))].add(
            (str(row["cluster_id"]), str(row["offer"]), str(row["launch_tier"]))
        )
    conflicts = {key: values for key, values in consistency.items() if len(values) > 1}
    if conflicts:
        raise AssertionError(f"Group consistency conflicts: {conflicts}")

    cluster_consistency: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    for row in out:
        cluster_consistency[str(row["cluster_id"])].add(
            (str(row["campaign"]), str(row["ad_group"]), str(row["offer"]), str(row["launch_tier"]))
        )
    cluster_conflicts = {key: values for key, values in cluster_consistency.items() if len(values) > 1}
    if cluster_conflicts:
        raise AssertionError(f"Cluster consistency conflicts: {cluster_conflicts}")

    out.sort(key=lambda row: (str(row["launch_tier"]), str(row["campaign"]), str(row["ad_group"]), str(row["keyword"])))
    fields = [
        "keyword", "normalized", "cluster_id", "campaign", "ad_group", "intent", "offer",
        "landing_page", "platform", "status", "confidence", "source", "launch_tier",
        "frequency", "quoted_frequency", "exact_frequency", "reason",
        "campaign_yandex", "ad_group_yandex", "campaign_google", "ad_group_google",
    ]
    write_csv(OUT, out, fields)

    campaigns = sorted({str(row["campaign"]) for row in out})
    groups = sorted({(str(row["campaign"]), str(row["ad_group"])) for row in out})
    by_tier = Counter(str(row["launch_tier"]) for row in out)
    by_source = Counter(str(row["source"]) for row in out)

    group_rows: list[tuple[str, str, int, int, int]] = []
    for campaign, ad_group in groups:
        rows = [row for row in out if row["campaign"] == campaign and row["ad_group"] == ad_group]
        exact_sum = sum(int(row["exact_frequency"] or 0) for row in rows)
        quoted_sum = sum(int(row["quoted_frequency"] or 0) for row in rows)
        group_rows.append((campaign, ad_group, len(rows), exact_sum, quoted_sum))

    lines = [
        "# Финальная кластеризация семантики UNISEC для запуска",
        "",
        "Проверено: 2026-09-28  ",
        "Регион: Новосибирск  ",
        "Контур: B2C; B2B-запрос вынесен отдельно",
        "",
        "## Факты",
        "",
        f"- В запускном наборе **{len(out)}** уникальных запросов: {by_source['initial_semantics']} из исходной семантики и {by_source['price_wordstat_expansion']} новых, подтверждённых прайсом и Wordstat.",
        f"- Структура: **{len(campaigns)} {ru_plural(len(campaigns), 'кампания', 'кампании', 'кампаний')}**, **{len(groups)} {ru_plural(len(groups), 'группа', 'группы', 'групп')}**.",
        f"- Первая очередь: **{by_tier['phase_1']} {ru_plural(by_tier['phase_1'], 'запрос', 'запроса', 'запросов')}**; вторая очередь: **{by_tier['phase_2']} {ru_plural(by_tier['phase_2'], 'запрос', 'запроса', 'запросов')}**.",
        "- Все 208 новых формулировок проверены: 80 B2C-фраз с положительной частотностью в кавычках вошли в запускной набор; 45 фраз оставлены для расширения хвоста; 82 нулевые фразы сохранены в снимке, но не включены в запуск.",
        "- Запрос `стирка рабочей одежды` имеет WS 27 и `\"WS\"` 7, но относится к B2B и не смешан с B2C-кампаниями.",
        "- Посадочные страницы не назначены: их URL не были предоставлены.",
        "",
        "## Очереди запуска",
        "",
        "- `phase_1` — основной B2C-спрос: химчистка, ремонт, домашний текстиль, обувь и сумки, прачечная.",
        "- `phase_2` — детские изделия и специальные услуги (крашение, аквачистка, озонирование). Их лучше включать после проверки оффера и посадочной.",
        "",
        "## Структура кампаний и групп",
        "",
        "`[!WS]` относится только к исходной семантике, `\"WS\"` — только к новым фразам из прайса. Эти показатели нельзя складывать между собой как единый объём рынка.",
        "",
        "| Кампания | Группа | Запросов | Сумма `[!WS]` исходных | Сумма `\"WS\"` новых |",
        "|---|---|---:|---:|---:|",
    ]
    for campaign, ad_group, count, exact_sum, quoted_sum in group_rows:
        lines.append(f"| {campaign} | {ad_group} | {count} | {exact_sum} | {quoted_sum} |")

    lines += [
        "",
        "## Решение по остальным фразам",
        "",
        "- `expand_wordstat_tail` — 45 фраз: широкая частотность есть, но в кавычках ноль. Их использовать как маски для добора хвоста и чистки поисковых запросов, не как отдельные доказанные ключи.",
        "- `hold_zero_in_snapshot` — 82 фразы: сохранить как проверенные нули текущего снимка и не загружать в стартовые кампании.",
        "- B2B — отдельный тест с самостоятельными оффером, бюджетом и посадочной; не добавлять в B2C ради одной частотной фразы.",
        "",
        "## Ограничения перед загрузкой",
        "",
        "- Проверить, что каждая группа ведёт на страницу с тем же обещанием; без URL это пока не подтверждено.",
        "- Сверить актуальность цен, сроки, доставку и географию с клиентом перед написанием объявлений.",
        "- Минус-слова остаются кандидатами до просмотра поисковых запросов; общий минус `диван` сужен до фразы `химчистка дивана`, чтобы не заблокировать целевую химчистку чехлов.",
    ]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"launch rows={len(out)} campaigns={len(campaigns)} groups={len(groups)}")
    print(f"phase_1={by_tier['phase_1']} phase_2={by_tier['phase_2']}")
    print(f"new_b2c={len(b2c_rows)} b2b_separate={len(b2b_rows)}")


if __name__ == "__main__":
    main()
