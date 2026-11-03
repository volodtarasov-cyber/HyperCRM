"""Общий дашборд SEO-заводов: сводка по всем сайтам + страница на каждый.

Сайты — sites.yml рядом. Для каждого собирает из того, что есть на диске и в сети:
  - статьи сайта (draft — на согласовании), очередь завода, очередь тем (hold — отложено);
  - проверку опубликованного «как робот» по живому сайту (если live);
  - входящие внутренние ссылки по сборке, которая на сервере;
  - последний техаудит завода, ошибки сегодняшнего прогона, подключённые ключи
    (по ИМЕНАМ в .env завода, значения не читаются);
  - отметки [вне] из карточки сайта в волте, которые давно не сверяли.
Из этого считается «Внимание» — что сейчас требует действия. Задачи при этом
живут в YouGile: дашборд их не хранит, только подсвечивает состояние.

    .tools/venv/Scripts/python.exe .tools/universal/seo-dashboard/build.py [--no-live] [--only arcars]

Результат — один файл out/index.html: вкладка «Все сайты» и по вкладке на сайт,
выбранная вкладка живёт в адресе (#arcars). out/ не версионируется.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

import render  # отрисовка — render.py рядом

HERE = Path(__file__).resolve().parent
VAULT = HERE.parents[2]
OUT = HERE / "out"
TODAY = dt.date.today()
ORDER = ["Опубликована", "На согласовании", "В очереди завода", "Тема свободна", "Отложена"]
CHECK_HINT = {
    "200": "страница отвечает 200", "canonical": "canonical указывает на себя", "индекс": "нет noindex",
    "sitemap": "есть в sitemap", "ссылки": "на статью ссылается хотя бы одна страница сайта",
    "title": "title 20–70 символов", "description": "description 70–170 символов",
}
AUDIT_RU = {
    "directive_external_dofollow": "внешние ссылки без nofollow",
    "directive_cta_in_heading": "кнопка-призыв внутри заголовка",
    "directive_faq_no_schema": "FAQ без разметки FAQPage",
    "canon_redirect_hops": "несколько редиректов до канонического адреса",
    "schema_type_missing": "не хватает типов Schema.org",
    "img_alt_formal": "одинаковые alt у картинок",
    "ai_dev_comment": "комментарии разработчика в HTML страницы",
}

sys.stdout.reconfigure(encoding="utf-8")
e = html.escape


# ── сбор ─────────────────────────────────────────────────────────────

def frontmatter(p: Path) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", p.read_text(encoding="utf-8"), re.S)
    try:
        return (yaml.safe_load(m.group(1)) or {}) if m else {}
    except yaml.YAMLError:
        return {}


def get(url: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 seo-dashboard"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def env_keys(factory: Path) -> dict[str, bool]:
    keys = {}
    env = factory / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.exists() else []:
        m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*)", line)
        if m:
            keys[m.group(1)] = bool(m.group(2).strip())
    return keys


def rubric_labels(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    # Только «слово: 'подпись'» в начале строки: LABELS с ключом 'koreya-auktsiony' в кавычках
    # иначе перетирал тему auktsiony у всех стран («Япония · Корея · Проверка авто»).
    text = path.read_text(encoding="utf-8")
    labels = dict(re.findall(r"^\s*([a-z]+)\s*:\s*['\"]([^'\"]+)['\"]", text, re.M))
    labels.update(re.findall(r"^\s*'([a-z]+-[a-z]+)'\s*:\s*'([^']+)'", text, re.M))   # подписи целиком
    return labels


def inbound_links(dist: Path) -> Counter:
    c: Counter = Counter()
    if not dist.exists():
        return c
    for f in dist.rglob("*.html"):
        own = "/" + f.relative_to(dist).parent.as_posix().strip(".") + "/"
        for slug in set(re.findall(r'href="(?:https?://[^/"]+)?/blog/([a-z0-9-]+)/?["#?]', f.read_text(encoding="utf-8"))):
            if own != f"/blog/{slug}/":
                c[slug] += 1
    return c


def robot_check(domain: str, slug: str, sitemap: set[str], inbound: int) -> dict:
    url = f"https://{domain}/blog/{slug}/"
    code, h = get(url + "?dash=1")
    head = h.split("</head>", 1)[0]
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', head)
    title = re.search(r"<title>(.*?)</title>", head, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', head)
    t = html.unescape(title.group(1)).strip() if title else ""
    d = html.unescape(desc.group(1)).strip() if desc else ""
    return {"inbound": inbound, "checks": {
        "200": code == 200,
        "canonical": bool(canon and canon.group(1).rstrip("/") == url.rstrip("/")),
        "индекс": "noindex" not in head,
        "sitemap": url in sitemap,
        "ссылки": inbound > 0,
        "title": 20 <= len(t) <= 70,
        "description": 70 <= len(d) <= 170,
    }}


def vault_marks(card: Path | None) -> list[dict]:
    """Отметки [вне] карточки: давно не сверенные (>30 дней) и ни разу не сверенные."""
    if not card or not card.exists():
        return []
    out = []
    for line in card.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*- \[вне\]\s*(.+?)\s*⟳\s*(\d{4}-\d{2}-\d{2}|—)\s*$", line)
        if not m:
            continue
        text, when = m.group(1), m.group(2)
        age = None if when == "—" else (TODAY - dt.date.fromisoformat(when)).days
        if age is None or age > 30:
            text = re.sub(r"`([^`]+)`", r"\1", re.sub(r"\*\*([^*]+)\*\*", r"\1", text))
            out.append({"text": text, "age": age})
    return out


def komcentr_site(factory: Path, domain: str) -> dict:
    """Данные командного центра завода (пакет ≥1.32) по этому домену; нет — пусто."""
    f = factory / "engine" / "komcentr" / "data" / "komcentr.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return next((x for x in data.get("sites", []) if x.get("domain") == domain), {})


def collect_site(conf: dict, live: bool) -> dict:
    factory = Path(conf["factory"])
    cfg = yaml.safe_load((factory / "site.config.yml").read_text(encoding="utf-8"))
    domain = cfg["site"]["domain"]
    site = (factory / cfg["stack"]["repo_path"]).resolve()
    content = site / cfg["stack"].get("content_dir", "src/content/blog")
    cf = factory / "engine" / "content-factory"
    card = (VAULT / conf["vault_card"]) if conf.get("vault_card") else None
    live = live and conf.get("live", False)
    labels = rubric_labels(site / conf["rubrics"]) if conf.get("rubrics") else {}

    sitemap: set[str] = set()
    if live:
        _, sm = get(f"https://{domain}/sitemap-0.xml")
        sitemap = set(re.findall(r"<loc>([^<]+)</loc>", sm))
    inbound = inbound_links(site / conf.get("dist", "dist"))
    docx = {p.stem: p for p in (card.parent / "reports").rglob("*.docx")} if card else {}

    rows: list[dict] = []
    seen: set[str] = set()
    for p in sorted(content.glob("*.md*")) if content.exists() else []:
        fm = frontmatter(p)
        slug = fm.get("slug", p.stem)
        seen.add(fm.get("primaryQuery", ""))
        doc = docx.get(slug)
        row = {"slug": slug, "title": fm.get("title", slug), "category": fm.get("category", ""),
               "query": fm.get("primaryQuery", ""), "freq": fm.get("queryFrequency") or "",
               "date": str(fm.get("date", "")), "status": "На согласовании" if fm.get("draft") else "Опубликована",
               "docx": doc,
               "waiting": (TODAY - dt.date.fromtimestamp((doc or p).stat().st_mtime)).days}
        if row["status"] == "Опубликована" and live:
            row["robot"] = robot_check(domain, slug, sitemap, inbound.get(slug, 0))
        rows.append(row)

    slugs = {r["slug"] for r in rows}
    for p in sorted((cf / "queue" / "blog").glob("*.md*")) if (cf / "queue" / "blog").exists() else []:
        fm = frontmatter(p)
        if fm.get("slug", p.stem) in slugs:
            continue
        seen.add(fm.get("primaryQuery", ""))
        rows.append({"slug": fm.get("slug", p.stem), "title": fm.get("title", p.stem), "category": fm.get("category", ""),
                     "query": fm.get("primaryQuery", ""), "freq": fm.get("queryFrequency") or "",
                     "date": str(fm.get("date", "")), "status": "В очереди завода"})

    used_csv, backlog_csv = cf / "data" / "topics_used.csv", cf / "data" / "topics_backlog.csv"
    used = {r["primary_keyword"] for r in csv.DictReader(open(used_csv, encoding="utf-8"))} if used_csv.exists() else set()
    for r in csv.DictReader(open(backlog_csv, encoding="utf-8")) if backlog_csv.exists() else []:
        if r["primary_keyword"] in seen or r["primary_keyword"] in used:
            continue
        rows.append({"slug": "", "title": r["topic"], "category": r.get("category", ""), "query": r["primary_keyword"],
                     "freq": r.get("wordstat_frequency", ""), "date": "",
                     "status": "Отложена" if (r.get("hold") or "").strip() else "Тема свободна",
                     "note": (r.get("hold") or "").strip()})

    for r in rows:
        c = r.get("category", "")
        r["rubric"] = labels.get(c) or (" · ".join(labels.get(x, x) for x in c.split("-", 1)) if c else "")

    keys = env_keys(factory)
    metrika = None
    for f in (site / "src" / "data" / "site.ts", site / "src" / "site.config.ts"):
        if f.exists() and (m := re.search(r"metrikaId:\s*['\"](\d+)['\"]", f.read_text(encoding="utf-8"))):
            metrika = m.group(1)
    log = cf / "logs" / f"run-{TODAY:%Y-%m-%d}.log"
    # Только последний прогон: утренний сбой, уже починенный, не должен висеть красным весь день
    # Самопроверка пакета (doctor, mechanics) гоняет тестовую статью во временной папке и пишет
    # в тот же лог без маркера запуска — её ошибки не считаем.
    text = log.read_text(encoding="utf-8") if log.exists() else ""
    marker = "=== content-factory: запуск"
    last_run = text.split(marker)[-1] if marker in text else ""
    errors_today = sum(1 for l in last_run.splitlines() if "[ERROR]" in l)

    audits = sorted((factory / "engine" / "seo-agent" / "data" / "audits").glob("*/report.md"))
    audit_groups: list[tuple[str, str, int]] = []
    if audits:
        level = ""
        for line in audits[-1].read_text(encoding="utf-8").splitlines():
            if m := re.match(r"## (\w+) \(\d+\)", line):
                level = m.group(1)
            elif m := re.match(r"### (\S+) \((\d+)\)", line):
                audit_groups.append((level, m.group(1), int(m.group(2))))

    # Позиции: последний снимок m3. Пусто в yandex_pos — «не замерено» или «нет в топ-30», не обвал
    snaps = sorted((factory / "engine" / "seo-agent" / "data" / "rankings").glob("????-??-??.csv"))
    ranks: list[tuple[str, float]] = []
    if snaps:
        with snaps[-1].open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("yandex_pos"):
                    ranks.append((r["keyword"], float(r["yandex_pos"])))
        ranks.sort(key=lambda x: x[1])

    gsc = bool(keys.get("GSC_SERVICE_ACCOUNT_FILE") or keys.get("GSC_OAUTH_REFRESH_TOKEN"))
    return {
        "id": conf["id"], "name": cfg["site"].get("name", conf["id"]), "domain": domain, "live": live,
        "configured_live": conf.get("live", False), "rows": rows, "vault": vault_marks(card),
        "card": card.relative_to(VAULT).as_posix() if card else "",
        "integrations": [
            ("Яндекс.Метрика", f"счётчик {metrika} на сайте" if metrika else "нет счётчика", bool(metrika)),
            ("Яндекс.Вебмастер (API)", "токен есть" if keys.get("YANDEX_WEBMASTER_TOKEN") else "нет токена", keys.get("YANDEX_WEBMASTER_TOKEN", False)),
            ("Search Console (API)", "ключ есть" if gsc else "нет ключа", gsc),
            ("Отчёты в Telegram", "подключены" if keys.get("TELEGRAM_BOT_TOKEN") else "нет бота", keys.get("TELEGRAM_BOT_TOKEN", False)),
        ],
        "errors_today": errors_today,
        "audit_date": audits[-1].parent.name if audits else None,
        "audit_groups": audit_groups,
        # Штатная панель завода (пакет ≥1.32): своя у каждой копии, открываем отсюда
        "kc": komcentr_site(factory, domain),
        "komcentr": (factory / "Командный-центр.html").as_uri() if (factory / "Командный-центр.html").exists() else "",
        "rank_date": snaps[-1].stem if snaps else None,
        "rank_total": sum(1 for _ in snaps[-1].open(encoding="utf-8")) - 1 if snaps else 0,
        "ranks": ranks,
    }


# ── «Внимание» ───────────────────────────────────────────────────────

def attention(s: dict) -> list[tuple[str, str]]:
    """(уровень, текст): red — сломано, amber — ждёт действия, grey — к сведению."""
    a: list[tuple[str, str]] = []
    rows = s["rows"]
    cnt = Counter(r["status"] for r in rows)
    for r in rows:
        if r.get("robot") and not all(r["robot"]["checks"].values()):
            bad = ", ".join(k for k, v in r["robot"]["checks"].items() if not v)
            a.append(("red", f"«{r['title']}» не проходит проверку: {bad}"))
    if s["errors_today"]:
        a.append(("red", f"Ошибок в последнем прогоне завода: {s['errors_today']} — лог engine/content-factory/logs"))
    issues = sum(n for _, _, n in s["audit_groups"])
    if s["configured_live"]:
        if not s["audit_date"]:
            a.append(("amber", "Техаудит не запускался"))
        else:
            age = (TODAY - dt.date.fromisoformat(s["audit_date"])).days
            if issues:
                a.append(("amber", f"Замечаний техаудита: {issues}"))
            if age > 14:
                a.append(("amber", f"Техаудит {age} дн. назад — пора повторить"))
    drafts = [r for r in rows if r["status"] == "На согласовании"]
    if drafts:
        oldest = max(r["waiting"] for r in drafts)
        a.append(("amber" if oldest >= 3 else "grey",
                  f"На согласовании у клиента: {len(drafts)}, самая давняя — {oldest} дн."))
    if cnt.get("В очереди завода"):
        a.append(("amber", f"В очереди завода: {cnt['В очереди завода']} — сверить с фактами и перенести на сайт"))
    if not cnt.get("Тема свободна") and cnt.get("Опубликована"):
        a.append(("amber", "Свободных тем нет — нужен сбор семантики"))
    if s["configured_live"]:
        for name, state, ok in s["integrations"]:
            if not ok:
                a.append(("grey", f"{name}: {state}"))
    else:
        a.append(("grey", "Сайт не выложен — живые проверки выключены"))
    for v in s["vault"]:
        when = "ни разу не сверялось" if v["age"] is None else f"сверено {v['age']} дн. назад"
        a.append(("grey", f"Сверить: {v['text'][:140]}{'…' if len(v['text']) > 140 else ''} ({when})"))
    order = {"red": 0, "amber": 1, "grey": 2}
    return sorted(a, key=lambda x: order[x[0]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-live", action="store_true", help="не ходить на живые сайты")
    ap.add_argument("--only", help="собрать только этот сайт (id из sites.yml)")
    a = ap.parse_args()
    confs = yaml.safe_load((HERE / "sites.yml").read_text(encoding="utf-8"))["sites"]
    if a.only:
        confs = [c for c in confs if c["id"] == a.only]
    sites = []
    for c in confs:
        try:
            sites.append(collect_site(c, live=not a.no_live))
        except Exception as err:  # noqa: BLE001 — один сломанный сайт не роняет весь дашборд
            print(f"✗ {c['id']}: {err}")
    built = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    OUT.mkdir(parents=True, exist_ok=True)
    atts = {s["id"]: attention(s) for s in sites}
    tabs = [("all", "Все сайты", render.render_index(sites, atts, TODAY))]
    tabs += [(s["id"], s["name"], render.render_site(s, atts[s["id"]], ORDER, CHECK_HINT, AUDIT_RU, TODAY)) for s in sites]
    for s in sites:
        (OUT / f"{s['id']}.html").unlink(missing_ok=True)   # до 2026-11-03 сайт был отдельной страницей
        c = Counter(r["status"] for r in s["rows"])
        print(f"{s['id']}: " + " · ".join(f"{k}: {c.get(k, 0)}" for k in ORDER))
    (OUT / "index.html").write_text(render.page(tabs, built), encoding="utf-8")
    print(OUT / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
