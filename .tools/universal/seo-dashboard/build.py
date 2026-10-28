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

Результат — out/index.html и out/<id>.html рядом (не версионируются).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

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
    return dict(re.findall(r"['\"]?([a-z]+)['\"]?\s*:\s*['\"]([^'\"]+)['\"]", path.read_text(encoding="utf-8")))


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
        r["rubric"] = " · ".join(labels.get(x, x) for x in c.split("-", 1)) if c else ""

    keys = env_keys(factory)
    metrika = None
    for f in (site / "src" / "data" / "site.ts", site / "src" / "site.config.ts"):
        if f.exists() and (m := re.search(r"metrikaId:\s*['\"](\d+)['\"]", f.read_text(encoding="utf-8"))):
            metrika = m.group(1)
    log = cf / "logs" / f"run-{TODAY:%Y-%m-%d}.log"
    # Только последний прогон: утренний сбой, уже починенный, не должен висеть красным весь день
    last_run = log.read_text(encoding="utf-8").split("=== content-factory: запуск")[-1] if log.exists() else ""
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


# ── отрисовка ────────────────────────────────────────────────────────

CSS = """
:root{--bg:#f4f5f7;--card:#fff;--ink:#14171c;--dim:#5d6470;--line:#e2e5ea;--ok:#1d7a46;--okb:#e3f3ea;--bad:#b3261e;--badb:#fbe7e6;--amb:#9a4a00;--ambb:#fff1e0;--acc:#d9531e}
@media (prefers-color-scheme: dark){:root{--bg:#111317;--card:#1a1d22;--ink:#e9ebef;--dim:#9aa1ad;--line:#2b2f36;--ok:#5fd394;--okb:#183526;--bad:#ff8a80;--badb:#3a1c1a;--amb:#ffb870;--ambb:#3a2a14}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:inherit}.wrap{max-width:1240px;margin:0 auto;padding:24px 16px 48px}
nav{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:20px}nav a{text-decoration:none;padding:6px 12px;border:1px solid var(--line);background:var(--card);font-weight:600;font-size:14px}nav a.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
h1{margin:0 0 4px;font-size:26px}h2{font-size:17px;margin:0 0 10px}.meta{color:var(--dim);margin:0 0 20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.tile{background:var(--card);border:1px solid var(--line);padding:14px 16px}.tile b{display:block;font-size:28px;line-height:1.1}.tile span{color:var(--dim)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}.box{background:var(--card);border:1px solid var(--line);padding:16px 18px}
.box ul{margin:0;padding:0;list-style:none;display:grid;gap:8px}.box li small{display:block;color:var(--dim)}
.ok b{color:var(--ok)}.off b{color:var(--bad)}
.att{list-style:none;margin:0;padding:0;display:grid;gap:6px}.att li{padding:8px 12px;border-left:4px solid var(--line);background:var(--card)}
.att .red{border-color:var(--bad);background:var(--badb)}.att .amber{border-color:var(--amb);background:var(--ambb)}.att .grey{color:var(--dim)}
.att .site{font-weight:700;margin-right:6px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line)}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:13px;color:var(--dim);font-weight:600}
td a{font-weight:600}.sub,td small{display:block;color:var(--dim);font-size:13px}
.st{font-size:12px;font-weight:600;padding:2px 8px;white-space:nowrap;border:1px solid var(--line)}
.s0 .st{background:var(--okb);color:var(--ok);border-color:transparent}.s1 .st{background:var(--ambb);color:var(--amb);border-color:transparent}
.s3 .st{color:var(--acc)}.s4{opacity:.6}
.chk{display:inline-block;font-size:12px;padding:1px 6px;margin:0 4px 4px 0}.chk.y{background:var(--okb);color:var(--ok)}.chk.n{background:var(--badb);color:var(--bad);font-weight:700}
.x{min-width:240px}section{margin-bottom:24px}
@media (max-width:820px){.grid{grid-template-columns:1fr}table,thead,tbody,tr,td{display:block}thead{display:none}tr{border-bottom:1px solid var(--line)}td{border:0;padding:6px 12px}}
"""


def page(title: str, nav: str, body: str, built: str) -> str:
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>'
            f"<style>{CSS}</style></head><body><div class=\"wrap\">{nav}{body}"
            f'<p class="meta">Собрано {e(built)}</p></div></body></html>')


def nav_html(sites: list[dict], current: str) -> str:
    links = [f'<a href="index.html" class="{"on" if current == "index" else ""}">Все сайты</a>']
    links += [f'<a href="{s["id"]}.html" class="{"on" if current == s["id"] else ""}">{e(s["name"])}</a>' for s in sites]
    return f"<nav>{''.join(links)}</nav>"


def tiles(rows: list[dict]) -> str:
    c = Counter(r["status"] for r in rows)
    return "".join(f'<div class="tile"><b>{c.get(s, 0)}</b><span>{e(s.lower())}</span></div>' for s in ORDER)


def att_html(items: list[tuple[str, str]], site: str = "") -> str:
    tag = f'<span class="site">{e(site)}</span>' if site else ""
    return "".join(f'<li class="{lvl}">{tag}{e(t)}</li>' for lvl, t in items)


def render_site(s: dict, sites: list[dict], built: str) -> str:
    rows = sorted(s["rows"], key=lambda r: (ORDER.index(r["status"]), r.get("date") or "", r["title"]))
    integ = "".join(f'<li class="{"ok" if ok else "off"}"><b>{e(n)}</b> — {e(st)}</li>' for n, st, ok in s["integrations"])
    audit = "".join(f'<li><b>{n}</b> · {e(AUDIT_RU.get(k, k))}<small>{e(lvl.lower())}</small></li>'
                    for lvl, k, n in s["audit_groups"])
    audit = audit or ("<li>замечаний нет</li>" if s["audit_date"] else "<li>не запускался</li>")
    rk = s["ranks"]
    if s["rank_date"]:
        top10, top30 = sum(1 for _, p in rk if p <= 10), sum(1 for _, p in rk if p <= 30)
        pos = (f'<li><b>{top10}</b> · в топ-10 Яндекса</li><li><b>{top30}</b> · в топ-30</li>'
               f'<li><b>{s["rank_total"] - len(rk)}</b> · дальше 30-го места</li>'
               + "".join(f'<li><b>{p:.0f}</b> · {e(k)}</li>' for k, p in rk[:8]))
    else:
        pos = "<li>не снимались</li>"
    trs = []
    for r in rows:
        st = r["status"]
        link = (f'<a href="https://{s["domain"]}/blog/{r["slug"]}/" target="_blank" rel="noopener">{e(r["title"])}</a>'
                if st == "Опубликована" and s["configured_live"] else e(r["title"]))
        extra = ""
        if r.get("robot"):
            extra = "".join(f'<span class="chk {"y" if v else "n"}" title="{e(CHECK_HINT[k])}">{e(k)}</span>'
                            for k, v in r["robot"]["checks"].items())
            extra += f'<small>входящих ссылок: {r["robot"]["inbound"]}</small>'
        elif st == "На согласовании":
            extra = f'<small>ждёт {r["waiting"]} дн.</small>'
            if r.get("docx"):
                extra += f'<small>Word: {e(r["docx"].relative_to(VAULT).as_posix())}</small>'
        elif r.get("note"):
            extra = f'<small>{e(r["note"])}</small>'
        trs.append(f'<tr class="s{ORDER.index(st)}"><td><span class="st">{e(st)}</span></td>'
                   f'<td>{link}<div class="sub">{e(r.get("rubric", ""))}</div></td>'
                   f'<td>{e(r["query"])}<div class="sub">{e(str(r["freq"]))}</div></td>'
                   f'<td>{e(r.get("date") or "—")}</td><td class="x">{extra}</td></tr>')
    table = (f'<table><thead><tr><th>Статус</th><th>Статья / тема</th><th>Запрос · частота</th><th>Дата</th>'
             f'<th>Проверка</th></tr></thead><tbody>{"".join(trs)}</tbody></table>') if trs else '<p class="meta">Статей и тем пока нет.</p>'
    card = f' · карточка: {e(s["card"])}' if s["card"] else ""
    body = (f'<h1>{e(s["name"])} — {e(s["domain"])}</h1><p class="meta">Блог и SEO-завод{card}</p>'
            f'<section><h2>Внимание</h2><ul class="att">{att_html(attention(s)) or "<li class=grey>всё спокойно</li>"}</ul></section>'
            f'<div class="tiles">{tiles(s["rows"])}</div>'
            f'<div class="grid"><div class="box"><h2>Подключения</h2><ul>{integ}</ul></div>'
            f'<div class="box"><h2>Техаудит {e(s["audit_date"] or "")}</h2><ul>{audit}</ul></div>'
            f'<div class="box"><h2>Позиции в Яндексе {e(s["rank_date"] or "")}</h2><ul>{pos}</ul>'
            f'<p class="meta">из {s["rank_total"]} запросов · раз в неделю</p></div></div>'
            f'<section><h2>Статьи и темы</h2>{table}</section>')
    return page(f'{s["name"]} — дашборд', nav_html(sites, s["id"]), body, built)


def render_index(sites: list[dict], built: str) -> str:
    all_att = []
    for s in sites:
        all_att += [(lvl, t, s["name"]) for lvl, t in attention(s) if lvl != "grey"]
    order = {"red": 0, "amber": 1}
    all_att.sort(key=lambda x: order[x[0]])
    att = "".join(f'<li class="{lvl}"><span class="site">{e(n)}</span>{e(t)}</li>' for lvl, t, n in all_att)
    trs = []
    for s in sites:
        c = Counter(r["status"] for r in s["rows"])
        a = attention(s)
        issues = sum(n for _, _, n in s["audit_groups"])
        trs.append(
            f'<tr><td><a href="{s["id"]}.html">{e(s["name"])}</a><div class="sub">{e(s["domain"])}'
            f'{"" if s["configured_live"] else " · не выложен"}</div></td>'
            + "".join(f'<td>{c.get(st, 0)}</td>' for st in ORDER[:4])
            + f'<td>{issues if s["audit_date"] else "—"}</td>'
            f'<td>{sum(1 for x in a if x[0] == "red")} / {sum(1 for x in a if x[0] == "amber")}</td></tr>')
    body = ('<h1>SEO-заводы — все сайты</h1><p class="meta">Что требует действия сейчас. Серые пункты — на страницах сайтов.</p>'
            f'<section><h2>Внимание</h2><ul class="att">{att or "<li class=grey>всё спокойно</li>"}</ul></section>'
            '<section><h2>Сайты</h2><table><thead><tr><th>Сайт</th><th>Опубликовано</th><th>На согласовании</th>'
            '<th>В очереди завода</th><th>Свободных тем</th><th>Замечаний аудита</th><th>Сломано / ждёт</th></tr></thead>'
            f'<tbody>{"".join(trs)}</tbody></table></section>')
    return page("SEO-заводы — дашборд", nav_html(sites, "index"), body, built)


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
    for s in sites:
        (OUT / f"{s['id']}.html").write_text(render_site(s, sites, built), encoding="utf-8")
        c = Counter(r["status"] for r in s["rows"])
        print(f"{s['id']}: " + " · ".join(f"{k}: {c.get(k, 0)}" for k in ORDER))
    (OUT / "index.html").write_text(render_index(sites, built), encoding="utf-8")
    print(OUT / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
