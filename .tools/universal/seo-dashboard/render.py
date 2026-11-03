"""Отрисовка дашборда SEO-заводов: один файл, вкладки «Все сайты» и по сайту.

Визуальный язык — как у «Командного центра» пакета завода (шрифты Unbounded / Onest /
JetBrains Mono, тёплая бумага, тёмный блок «Сегодня» с полосой), чтобы обе панели
читались одинаково. Данные — наши: согласование, отметки [вне], позиции, проверка
«как робот». Ряды выпуска, индекс и ядро семантики — из komcentr.json завода, если
он есть (пакет ≥1.32); нет — блок говорит «нет данных», а не рисует ноль.
"""
from __future__ import annotations

import datetime as dt
import html
from collections import Counter

e = html.escape
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@600;700'
         '&family=Onest:wght@400;500;600&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">')

CSS = """
:root{--paper:#f2f0ea;--card:#fbfaf7;--chip:#ece9e1;--hover:#f6f4ef;--ink:#14161a;--ink-2:#3b4048;--muted:#5c626b;--off:#8a8f97;
--line:#d9d5cb;--line-2:#e4e0d6;--blue:#2a44d8;--blue-wash:#eef0fc;--yellow:#ffcf33;--orange:#d9722b;
--ok:#1f7a45;--ok-bg:#e3f1e7;--bad:#b3261e;--bad-bg:#fbe4e1;--warn-tx:#5a4500;--warn-bg:#fff4cc;
--dark:#111317;--dark-card:#1a1d22;--dark-line:#2b3038;--dark-text:#eceae3;--dark-muted:#a2a8b0;
--f-d:"Unbounded","Arial Black",system-ui,sans-serif;--f-b:"Onest",system-ui,-apple-system,"Segoe UI",sans-serif;--f-m:"JetBrains Mono",ui-monospace,Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 var(--f-b)}
a{color:inherit}.wrap{max-width:1320px;margin:0 auto;padding:28px 20px 56px}
.eyebrow{font:500 11px/1 var(--f-m);letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.mono{font-family:var(--f-m)}.disp{font-family:var(--f-d)}
header.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:22px}
header.top .when{font:12px/1.6 var(--f-m);color:var(--muted);text-align:right}
nav.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
nav.tabs a{text-decoration:none;padding:8px 16px;border-radius:999px;border:1px solid var(--line);background:var(--card);font-weight:600;font-size:14px}
nav.tabs a.on{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.tab{display:none}.tab.on{display:block}
h1{font:700 40px/1.05 var(--f-d);margin:6px 0 6px;letter-spacing:-.01em}
.sub a,.domain{color:var(--blue);text-decoration:none;font-weight:500}
h2.sec{font:700 24px/1.1 var(--f-d);margin:34px 0 6px}.lead{color:var(--muted);margin:0 0 14px;font-size:14px}
.hero{background:var(--dark);color:var(--dark-text);border-radius:22px;overflow:hidden;margin:18px 0 22px}
.hero:before{content:"";display:block;height:12px;background:repeating-linear-gradient(-45deg,var(--yellow) 0 18px,var(--dark) 18px 36px)}
.hero .in{padding:16px 22px 22px}.hero .eyebrow{color:var(--yellow);margin-bottom:12px}
.hero .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.hc{background:var(--dark-card);border:1px solid var(--dark-line);border-radius:14px;padding:14px 16px;display:flex;gap:12px}
.hc b{display:block;font-size:17px;margin-bottom:2px}.hc p{margin:0;color:var(--dark-muted);font-size:13px}
.hc ul{margin:6px 0 0;padding:0;list-style:none;display:grid;gap:5px;font-size:13px;color:var(--dark-text)}
.hc li:before{content:"✦ ";color:var(--yellow)}.hc li.red:before{color:#ff8a80}
.hc .site{color:var(--yellow);font-weight:600;margin-right:4px}
.dot{flex:none;width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-weight:700;color:var(--dark);font-size:15px}
.dot.ok{background:#5fd394}.dot.warn{background:var(--yellow)}.dot.bad{background:#ff8a80}
.card{background:var(--card);border:1px solid var(--line-2);border-radius:18px;padding:18px 20px}
.card h3{margin:0 0 12px;font-size:15px;font-weight:600;display:flex;justify-content:space-between;gap:10px}
.card h3 small{font:400 12px var(--f-m);color:var(--muted)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:14px}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0;padding:0;overflow:hidden}
.kpi{padding:16px 18px;border-right:1px solid var(--line-2);display:flex;gap:12px;align-items:center;min-height:96px}
.kpi:last-child{border-right:0}.kpi .lbl{display:block;margin-bottom:6px}
.kpi b{font:700 26px/1 var(--f-d)}.kpi small{display:block;color:var(--muted);font-size:12px;margin-top:4px}
.kpi.dim b{color:var(--off)}
.list{margin:0;padding:0;list-style:none}.list li{display:grid;grid-template-columns:72px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--line-2);font-size:14px}
.list li:last-child{border-bottom:0}.list .d{font:12px var(--f-m);color:var(--muted);padding-top:2px}
.list .x{color:var(--muted);font-size:12px}.list a{text-decoration:none}.list a:hover{text-decoration:underline}
.chips{display:flex;gap:4px;flex-wrap:wrap;margin-top:3px}
.chip{font:11px var(--f-m);padding:2px 7px;border-radius:999px;background:var(--chip);color:var(--ink-2)}
.chip.ok{background:var(--ok-bg);color:var(--ok)}.chip.bad{background:var(--bad-bg);color:var(--bad);font-weight:700}.chip.warn{background:var(--warn-bg);color:var(--warn-tx)}
.note{background:var(--chip);border-radius:12px;padding:12px 14px;font-size:13px;color:var(--ink-2)}
.legend{display:grid;gap:6px;font-size:13px}.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.donutrow{display:flex;gap:18px;align-items:center}
.conn li{display:flex;gap:8px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--line-2);font-size:14px}
.conn li:last-child{border:0}.conn .st{margin-left:auto;font:12px var(--f-m);color:var(--muted);text-align:right}
.led{width:9px;height:9px;border-radius:50%;flex:none;background:var(--bad)}.led.on{background:var(--ok)}
table.sites{width:100%;border-collapse:collapse}table.sites th{font:500 11px var(--f-m);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
table.sites td{padding:14px 12px;border-bottom:1px solid var(--line-2);vertical-align:middle}table.sites tr:last-child td{border:0}
table.sites td b{font:700 22px var(--f-d)}table.sites small{display:block;color:var(--muted);font-size:12px}
table.sites a.nm{font-weight:600;text-decoration:none}table.sites a.nm:hover{text-decoration:underline}
details.more{margin-top:14px;background:var(--card);border:1px solid var(--line-2);border-radius:18px}
details.more summary{cursor:pointer;padding:16px 20px;font-weight:600;list-style:none}details.more summary:before{content:"+ ";color:var(--blue)}
details.more[open] summary:before{content:"− "}details.more summary small{color:var(--muted);font-weight:400;margin-left:8px;font-size:13px}
details.more .body{padding:0 20px 18px}
table.all{width:100%;border-collapse:collapse;font-size:14px}table.all th{font:500 11px var(--f-m);text-transform:uppercase;letter-spacing:.06em;color:var(--muted);text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
table.all td{padding:9px 10px;border-bottom:1px solid var(--line-2);vertical-align:top}table.all .sub{display:block;color:var(--muted);font-size:12px}
table.all a{font-weight:600}.s4{opacity:.55}
footer{margin-top:28px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
@media (max-width:760px){h1{font-size:30px}.kpi{border-right:0;border-bottom:1px solid var(--line-2)}.grid2,.grid3{grid-template-columns:1fr}
table.all thead{display:none}table.all,table.all tbody,table.all tr,table.all td{display:block}table.all tr{border-bottom:1px solid var(--line)}table.all td{border:0;padding:4px 10px}
table.sites thead{display:none}table.sites,table.sites tbody,table.sites tr,table.sites td{display:block}table.sites td{border:0;padding:6px 12px}table.sites tr{border-bottom:1px solid var(--line)}}
"""


# ── мелкие рисунки ───────────────────────────────────────────────────

def ring(parts: list[tuple[float, str]], size: int = 56, stroke: int = 9) -> str:
    """Кольцо из долей (доля 0..1, цвет); остаток — серый трек."""
    r = (size - stroke) / 2
    c = 2 * 3.14159 * r
    out, off = [], 0.0
    for frac, color in parts:
        frac = max(0.0, min(1.0, frac))
        if frac:
            out.append(f'<circle r="{r}" cx="{size/2}" cy="{size/2}" fill="none" stroke="{color}" stroke-width="{stroke}" '
                       f'stroke-dasharray="{frac*c:.1f} {c:.1f}" stroke-dashoffset="{-off*c:.1f}" '
                       f'transform="rotate(-90 {size/2} {size/2})"/>')
        off += frac
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" aria-hidden="true">'
            f'<circle r="{r}" cx="{size/2}" cy="{size/2}" fill="none" stroke="var(--chip)" stroke-width="{stroke}"/>'
            + "".join(out) + "</svg>")


def bars(series: list[int], end: dt.date) -> str:
    n = len(series)
    if not n:
        return '<div class="note">Нет данных о выпуске.</div>'
    w, h, top = 600, 210, max(max(series), 1)
    bw = w / n
    rects = "".join(
        f'<rect x="{i*bw+bw*.2:.1f}" y="{h-(v/top)*(h-8):.1f}" width="{bw*.6:.1f}" height="{(v/top)*(h-8):.1f}" rx="2" fill="var(--blue)">'
        f'<title>{(end - dt.timedelta(days=n-1-i)).strftime("%d.%m")}: {v}</title></rect>'
        for i, v in enumerate(series) if v)
    start, mid = end - dt.timedelta(days=n - 1), end - dt.timedelta(days=n // 2)
    return (f'<svg viewBox="0 0 {w} {h+22}" width="100%" role="img" aria-label="Статьи по дням">'
            f'<line x1="0" y1="{h}" x2="{w}" y2="{h}" stroke="var(--line)"/>{rects}'
            f'<g font-family="JetBrains Mono,monospace" font-size="11" fill="var(--muted)">'
            f'<text x="0" y="{h+16}">{start:%d.%m}</text><text x="{w/2}" y="{h+16}" text-anchor="middle">{mid:%d.%m}</text>'
            f'<text x="{w}" y="{h+16}" text-anchor="end">сегодня</text></g></svg>')


def kpi(label: str, big: str, small: str = "", pic: str = "", dim: bool = False) -> str:
    return (f'<div class="kpi{" dim" if dim else ""}">{pic}<div><span class="eyebrow lbl">{e(label)}</span>'
            f'<b>{e(big)}</b><small>{e(small)}</small></div></div>')


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 19:
        return many
    return one if n % 10 == 1 else few if 2 <= n % 10 <= 4 else many


# ── сводные числа сайта ─────────────────────────────────────────────

def numbers(s: dict, today: dt.date) -> dict:
    rows = s["rows"]
    c = Counter(r["status"] for r in rows)
    pub = [r for r in rows if r["status"] == "Опубликована"]
    dates = [dt.date.fromisoformat(r["date"]) for r in pub if r.get("date", "")[:4].isdigit()]
    kc = s.get("kc") or {}
    series = (kc.get("pubs") or {}).get("series")
    if not series:                                   # нет komcentr — считаем по датам статей
        series = [sum(1 for d in dates if d == today - dt.timedelta(days=29 - i)) for i in range(30)]
    drafts = [r for r in rows if r["status"] == "На согласовании"]
    failing = [r for r in pub if r.get("robot") and not all(r["robot"]["checks"].values())]
    rk = s.get("ranks") or []
    return {
        "c": c, "pub": pub, "series": series,
        "d7": sum(series[-7:]), "d30": sum(series),
        "oldest": max((r["waiting"] for r in drafts), default=0),
        "failing": failing,
        "top10": sum(1 for _, p in rk if p <= 10), "top30": sum(1 for _, p in rk if p <= 30),
        "issues": sum(n for _, _, n in s["audit_groups"]),
        "index": (kc.get("index") or {}).get("ring") or {},
        "sem": kc.get("semantics") or {},
    }


def state_of(att: list[tuple[str, str]]) -> tuple[str, str, str]:
    red = sum(1 for a in att if a[0] == "red")
    amb = sum(1 for a in att if a[0] == "amber")
    if red:
        return "bad", "!", f"Сломано: {red}"
    if amb:
        return "warn", "−", f"Ждёт действия: {amb}"
    return "ok", "✓", "Всё спокойно"


def ru_day(d: dt.date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


# ── вкладка сайта ───────────────────────────────────────────────────

def render_site(s: dict, att: list[tuple[str, str]], order: list[str], check_hint: dict,
                audit_ru: dict, today: dt.date) -> str:
    n = numbers(s, today)
    c = n["c"]
    cls, mark, title = state_of(att)
    need = [a for a in att if a[0] != "grey"]
    status_line = (f'{c.get("Опубликована", 0)} опубликовано · {n["d7"]} за 7 дн. · '
                   f'на согласовании {c.get("На согласовании", 0)} · свободных тем {c.get("Тема свободна", 0)}')
    need_html = ("<ul>" + "".join(f'<li class="{lvl}">{e(t)}</li>' for lvl, t in need[:6]) + "</ul>") if need else \
        "<p>Сейчас от тебя ничего не нужно.</p>"
    hero = (f'<div class="hero"><div class="in"><div class="eyebrow">Сегодня · {ru_day(today)}</div><div class="cols">'
            f'<div class="hc"><span class="dot {cls}">{mark}</span><div><b>{e(title)}</b><p>{e(status_line)}</p></div></div>'
            f'<div class="hc"><span class="dot {"bad" if any(a[0] == "red" for a in need) else "warn" if need else "ok"}">'
            f'{len(need) or "✓"}</span><div><b>Нужны вы: {len(need)}</b>{need_html}</div></div></div></div></div>')

    ix, sem = n["index"], n["sem"]
    go_of = ix.get("of") or 0
    index_kpi = kpi("Индекс Google", f'{ix.get("go")} из {go_of}' if ix.get("go") is not None else "—",
                    "Яндекс: нет токена Вебмастера" if ix.get("ya") is None else f'Яндекс: {ix.get("ya")}',
                    ring([((ix.get("go") or 0) / go_of if go_of else 0, "var(--blue)")]), dim=ix.get("go") is None)
    sem_total = sem.get("total") or 0
    pub_n = c.get("Опубликована", 0)
    sem_kpi = kpi("Семантика", f"{round(pub_n / sem_total * 100)}%" if sem_total else "—",
                  f"закрыто {pub_n} из {sem_total} тем ядра" if sem_total else "ядро не прочиталось",
                  ring([(pub_n / sem_total if sem_total else 0, "var(--blue)")]), dim=not sem_total)
    kpis = ('<div class="card kpis">'
            + kpi("Опубликовано", str(pub_n), f'{n["d30"]} за 30 дн.')
            + kpi("На согласовании", str(c.get("На согласовании", 0)),
                  f'самая давняя {n["oldest"]} дн.' if c.get("На согласовании") else "ничего не ждёт")
            + kpi("Яндекс · топ-10", str(n["top10"]) if s["rank_date"] else "—",
                  f'в топ-30: {n["top30"]} из {s["rank_total"]}' if s["rank_date"] else "позиции не снимались",
                  dim=not s["rank_date"])
            + index_kpi
            + kpi("Техаудит", str(n["issues"]) if s["audit_date"] else "—",
                  f'замечаний · {s["audit_date"]}' if s["audit_date"] else "не запускался", dim=not s["audit_date"])
            + sem_kpi + "</div>")

    # Выпуск
    fresh = sorted(n["pub"], key=lambda r: r.get("date") or "", reverse=True)[:8]

    def fresh_li(r: dict) -> str:
        d = r.get("date") or ""
        when = "сегодня" if d == today.isoformat() else (dt.date.fromisoformat(d).strftime("%d.%m") if d[:4].isdigit() else "—")
        link = (f'<a href="https://{s["domain"]}/blog/{r["slug"]}/" target="_blank" rel="noopener">{e(r["title"])}</a>'
                if s["configured_live"] else e(r["title"]))
        chips = ""
        if r.get("robot"):
            bad = [k for k, v in r["robot"]["checks"].items() if not v]
            chips = ('<div class="chips">' + "".join(f'<span class="chip bad" title="{e(check_hint[k])}">{e(k)}</span>' for k in bad)
                     + "</div>") if bad else ""
        return f'<li><span class="d">{when}</span><div>{link}{chips}</div></li>'

    robot_ok = sum(1 for r in n["pub"] if r.get("robot") and all(r["robot"]["checks"].values()))
    robot_all = sum(1 for r in n["pub"] if r.get("robot"))
    robot_txt = (f'Проверка «как робот»: {robot_ok} из {robot_all} проходят все {len(check_hint)} проверок.'
                 if robot_all else 'Проверка «как робот» в этой сборке не запускалась.')
    release = (f'<h2 class="sec">Выпуск</h2><p class="lead">Статьи, вышедшие на сайт. {robot_txt}</p><div class="grid2">'
               f'<div class="card"><h3>Статьи по дням <small>за 30 дней · {n["d30"]}</small></h3>{bars(n["series"], today)}</div>'
               f'<div class="card"><h3>Свежие статьи <small>всего на сайте {pub_n}</small></h3>'
               f'<ul class="list">{"".join(fresh_li(r) for r in fresh) or "<li>пока нет</li>"}</ul></div></div>')

    # Поиск
    rk = s.get("ranks") or []
    if s["rank_date"]:
        far = s["rank_total"] - len(rk)
        pos_body = (f'<div class="donutrow">{ring([(n["top10"] / s["rank_total"] if s["rank_total"] else 0, "var(--blue)"), ((n["top30"] - n["top10"]) / s["rank_total"] if s["rank_total"] else 0, "#9aa8f0")], 84, 13)}'
                    f'<div class="legend"><span><i style="background:var(--blue)"></i>топ-10: <b>{n["top10"]}</b></span>'
                    f'<span><i style="background:#9aa8f0"></i>11–30: <b>{n["top30"] - n["top10"]}</b></span>'
                    f'<span><i style="background:var(--chip)"></i>дальше 30-го: <b>{far}</b></span></div></div>'
                    + ('<ul class="list" style="margin-top:10px">' + "".join(f'<li><span class="d">{p:.0f}-е</span><div>{e(k)}</div></li>' for k, p in rk[:6]) + "</ul>"
                       if rk else '<p class="note" style="margin-top:12px">Ни один запрос пока не в топ-30. Статьи молодые — смотрим динамику раз в неделю.</p>'))
    else:
        pos_body = '<div class="note">Позиции ещё не снимались — съём раз в неделю.</div>'
    conn = "".join(f'<li><span class="led{" on" if ok else ""}"></span>{e(nm)}<span class="st">{e(st)}</span></li>'
                   for nm, st, ok in s["integrations"])
    audit = "".join(f'<li><span class="d">{cnt}</span><div>{e(audit_ru.get(k, k))}<span class="x"> · {e(lvl.lower())}</span></div></li>'
                    for lvl, k, cnt in s["audit_groups"])
    audit = audit or (f'<li><span class="d">✓</span><div>замечаний нет</div></li>' if s["audit_date"] else '<li><span class="d">—</span><div>не запускался</div></li>')
    search = (f'<h2 class="sec">Поиск</h2><p class="lead">Где сайт в выдаче и что подключено для замеров.</p><div class="grid3">'
              f'<div class="card"><h3>Позиции в Яндексе <small>{e(s["rank_date"] or "")} · раз в неделю</small></h3>{pos_body}</div>'
              f'<div class="card"><h3>Подключения</h3><ul class="list conn">{conn}</ul></div>'
              f'<div class="card"><h3>Техаудит <small>{e(s["audit_date"] or "")} · каждый день</small></h3><ul class="list">{audit}</ul></div></div>')

    # Что дальше
    waiting = [r for r in s["rows"] if r["status"] in ("На согласовании", "В очереди завода")]
    nxt = sorted([r for r in s["rows"] if r["status"] == "Тема свободна"],
                 key=lambda r: -int(r["freq"]) if str(r.get("freq", "")).isdigit() else 0)[:7]

    def wait_li(r: dict) -> str:
        tag = f'ждёт {r["waiting"]} дн.' if r["status"] == "На согласовании" else "очередь"
        return f'<li><span class="d">{tag}</span><div>{e(r["title"])}</div></li>'

    queue_html = ("".join(wait_li(r) for r in waiting) or '<li><span class="d">—</span><div>на согласовании ничего нет</div></li>')
    next_html = "".join(f'<li><span class="d">{e(str(r["freq"]) or "—")}</span><div>{e(r["title"])}'
                        f'<span class="x"> · {e(r["query"])}</span></div></li>' for r in nxt)
    held, free = c.get("Отложена", 0), c.get("Тема свободна", 0)
    tot = pub_n + free + held + c.get("На согласовании", 0) + c.get("В очереди завода", 0)
    work = c.get("На согласовании", 0) + c.get("В очереди завода", 0)
    sem_card = (f'<div class="donutrow">{ring([(pub_n / tot if tot else 0, "var(--blue)"), (work / tot if tot else 0, "#9aa8f0"), (free / tot if tot else 0, "#cfc9bb")], 100, 16)}'
                f'<div class="legend"><span><i style="background:var(--blue)"></i>опубликовано <b>{pub_n}</b></span>'
                f'<span><i style="background:#9aa8f0"></i>согласование и очередь <b>{work}</b></span>'
                f'<span><i style="background:#cfc9bb"></i>свободные темы <b>{free}</b></span>'
                f'<span><i style="background:var(--chip)"></i>отложены <b>{held}</b></span></div></div>'
                + (f'<p class="note" style="margin-top:12px">В ядре завода {sem_total} тем, статьями закрыто {pub_n}.</p>' if sem_total else ""))
    nexts = (f'<h2 class="sec">Что дальше</h2><p class="lead">Что ждёт клиента и какие темы на очереди — по частоте запроса.</p><div class="grid2">'
             f'<div class="card"><h3>На согласовании и в очереди <small>{len(waiting)}</small></h3><ul class="list">{queue_html}</ul>'
             f'<h3 style="margin-top:16px">Следующие темы <small>частота · Wordstat</small></h3><ul class="list">{next_html or "<li>свободных тем нет</li>"}</ul></div>'
             f'<div class="card"><h3>Темы <small>{tot} в журнале</small></h3>{sem_card}</div></div>')

    # Сверить и всё подряд
    grey = [t for lvl, t in att if lvl == "grey"]
    check = ("<details class=\"more\"><summary>Сверить с внешним миром<small>" + str(len(grey)) + " — из карточки клиента и подключений</small></summary>"
             "<div class=\"body\"><ul class=\"list\">" + "".join(f'<li><span class="d">·</span><div>{e(t)}</div></li>' for t in grey)
             + "</ul></div></details>") if grey else ""
    rows = sorted(s["rows"], key=lambda r: (order.index(r["status"]), r.get("date") or "", r["title"]))
    trs = []
    for r in rows:
        st = r["status"]
        link = (f'<a href="https://{s["domain"]}/blog/{r["slug"]}/" target="_blank" rel="noopener">{e(r["title"])}</a>'
                if st == "Опубликована" and s["configured_live"] else e(r["title"]))
        if r.get("robot"):
            extra = '<div class="chips">' + "".join(
                f'<span class="chip {"ok" if v else "bad"}" title="{e(check_hint[k])}">{e(k)}</span>'
                for k, v in r["robot"]["checks"].items()) + f'</div><span class="sub">входящих ссылок: {r["robot"]["inbound"]}</span>'
        elif st == "На согласовании":
            extra = f'<span class="sub">ждёт {r["waiting"]} дн.</span>'
        else:
            extra = f'<span class="sub">{e(r.get("note") or "")}</span>'
        chip = {"Опубликована": "ok", "На согласовании": "warn"}.get(st, "")
        trs.append(f'<tr class="s{order.index(st)}"><td><span class="chip {chip}">{e(st)}</span></td>'
                   f'<td>{link}<span class="sub">{e(r.get("rubric", ""))}</span></td>'
                   f'<td>{e(r["query"])}<span class="sub">{e(str(r["freq"]))}</span></td>'
                   f'<td class="mono">{e(r.get("date") or "—")}</td><td>{extra}</td></tr>')
    table = (f'<details class="more"><summary>Все статьи и темы<small>{len(rows)} — статусы, проверки, причины отложенных</small></summary>'
             f'<div class="body"><table class="all"><thead><tr><th>Статус</th><th>Статья / тема</th><th>Запрос · частота</th>'
             f'<th>Дата</th><th>Проверка</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div></details>')

    links = [f'<a class="domain" href="https://{e(s["domain"])}/" target="_blank" rel="noopener">{e(s["domain"])} ↗</a>']
    if s.get("komcentr"):
        links.append(f'<a href="{e(s["komcentr"])}" target="_blank">Командный центр завода ↗</a>')
    if s["card"]:
        links.append(f'<span>карточка: {e(s["card"])}</span>')
    head = (f'<div class="eyebrow">Сайт под SEO-заводом{"" if s["configured_live"] else " · не выложен"}</div>'
            f'<h1>{e(s["name"])}</h1><div class="sub" style="display:flex;gap:16px;flex-wrap:wrap;font-size:14px">{"".join(links)}</div>')
    return head + hero + kpis + release + search + nexts + check + table


# ── вкладка «Все сайты» ─────────────────────────────────────────────

def render_index(sites: list[dict], atts: dict[str, list], today: dt.date) -> str:
    need = [(lvl, t, s["name"]) for s in sites for lvl, t in atts[s["id"]] if lvl != "grey"]
    need.sort(key=lambda x: x[0] != "red")
    red = sum(1 for x in need if x[0] == "red")
    cls, mark, title = ("bad", "!", f"Сломано: {red}") if red else ("warn", "−", f"Ждёт действия: {len(need)}") if need \
        else ("ok", "✓", "Всё спокойно")
    live = [s for s in sites if s["configured_live"]]
    pubs = sum(Counter(r["status"] for r in s["rows"]).get("Опубликована", 0) for s in sites)
    sub = f'{len(sites)} {plural(len(sites), "сайт", "сайта", "сайтов")}, выложено {len(live)} · опубликовано статей {pubs}'
    need_html = ("<ul>" + "".join(f'<li class="{lvl}"><span class="site">{e(n)}</span>{e(t)}</li>' for lvl, t, n in need[:8]) + "</ul>") \
        if need else "<p>Сейчас от тебя ничего не нужно.</p>"
    hero = (f'<div class="hero"><div class="in"><div class="eyebrow">Сегодня · {ru_day(today)}</div><div class="cols">'
            f'<div class="hc"><span class="dot {cls}">{mark}</span><div><b>{e(title)}</b><p>{e(sub)}</p></div></div>'
            f'<div class="hc"><span class="dot {"bad" if red else "warn" if need else "ok"}">{len(need) or "✓"}</span>'
            f'<div><b>Нужны вы: {len(need)}</b>{need_html}</div></div></div></div></div>')
    trs = []
    for s in sites:
        n = numbers(s, today)
        c = n["c"]
        st_cls, st_mark, st_title = state_of(atts[s["id"]]) if s["configured_live"] else ("ok", "·", "не выложен")
        ix = n["index"]
        trs.append(
            f'<tr><td><span class="dot {st_cls}" style="display:inline-grid;width:20px;height:20px;font-size:12px;margin-right:8px;vertical-align:-4px">{st_mark}</span>'
            f'<a class="nm" href="#{s["id"]}">{e(s["name"])}</a><small>{e(s["domain"])} · {e(st_title)}</small></td>'
            f'<td><b>{c.get("Опубликована", 0)}</b><small>{n["d7"]} за 7 дн.</small></td>'
            f'<td><b>{c.get("На согласовании", 0)}</b><small>{"самая давняя " + str(n["oldest"]) + " дн." if c.get("На согласовании") else "—"}</small></td>'
            f'<td><b>{n["top10"] if s["rank_date"] else "—"}</b><small>{"топ-30: " + str(n["top30"]) if s["rank_date"] else "не снимались"}</small></td>'
            f'<td><b>{ix.get("go") if ix.get("go") is not None else "—"}</b><small>{"из " + str(ix.get("of")) + " в Google" if ix.get("go") is not None else "нет данных"}</small></td>'
            f'<td><b>{n["issues"] if s["audit_date"] else "—"}</b><small>{s["audit_date"] or "не запускался"}</small></td>'
            f'<td><b>{c.get("Тема свободна", 0)}</b><small>отложено {c.get("Отложена", 0)}</small></td></tr>')
    table = ('<h2 class="sec">Свои сайты</h2><p class="lead">Главное по каждому сайту в одной строке. Нажми на имя — откроется вкладка сайта.</p>'
             '<div class="card" style="padding:4px 8px;overflow-x:auto"><table class="sites"><thead><tr><th>Сайт</th><th>Опубликовано</th>'
             '<th>На согласовании</th><th>Яндекс · топ-10</th><th>Индекс</th><th>Техаудит</th><th>Свободных тем</th></tr></thead>'
             f'<tbody>{"".join(trs)}</tbody></table></div>')
    head = '<div class="eyebrow">Все сайты</div><h1>SEO-заводы</h1>'
    return head + hero + table


def page(tabs: list[tuple[str, str, str]], built: str) -> str:
    """Один файл, вкладки: (id, подпись, тело). Без скрипта видны все подряд."""
    nav = "".join(f'<a href="#{i}" data-tab="{i}">{e(label)}</a>' for i, label, _ in tabs)
    panes = "".join(f'<div class="tab" id="{i}">{body}</div>' for i, _, body in tabs)
    js = ("<script>function show(){var h=location.hash.slice(1),p=document.getElementById(h);"
          "if(!p||!p.classList.contains('tab'))h='" + tabs[0][0] + "';"
          "document.querySelectorAll('.tab').forEach(function(x){x.classList.toggle('on',x.id===h)});"
          "document.querySelectorAll('nav.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.tab===h)});"
          "scrollTo(0,0)}addEventListener('hashchange',show);show()</script>")
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>SEO-заводы</title>{FONTS}'
            f"<style>{CSS}</style><noscript><style>.tab{{display:block}}</style></noscript></head>"
            f'<body><div class="wrap"><header class="top"><div><div class="eyebrow">Дашборд агентства</div>'
            f'<nav class="tabs">{nav}</nav></div><div class="when">данные на {e(built)}<br>обновляется каждый день в 08:00</div></header>'
            f'{panes}<footer>Задачи — в YouGile, дашборд их не хранит. Позиции — раз в неделю (XMLRiver, Самара). '
            f'Выпуск, индекс и ядро — из командного центра завода, если он есть. Нет источника — блок пишет «нет данных», а не ноль.</footer>'
            f'</div>{js}</body></html>')
