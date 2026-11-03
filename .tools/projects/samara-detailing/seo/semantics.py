"""Семантика детейлинга Самары: выдача Яндекса и частотность Wordstat через XMLRiver.

Ключи XMLRiver берутся из .env указанного SEO-завода через его же модуль, в вывод не попадают.
Запускать интерпретатором завода (там pyyaml):

    <завод>/.venv/Scripts/python.exe semantics.py serp   --factory D:/SecondBrain/seo-factory
    <завод>/.venv/Scripts/python.exe semantics.py ws     --factory D:/SecondBrain/seo-factory
    <завод>/.venv/Scripts/python.exe semantics.py report

Сырые ответы копятся в data/ (не версионируется), повторный запуск добирает только недостающее.
Фраза без замера пишется как «не замерено», а не как ноль.
"""
import argparse
import html
import re
import ssl
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
VAULT = HERE.parents[3]
SEEDS = VAULT / 'projects/seo-sites/samara-ppf-detailing/02-semantika/seeds.csv'
REGION = 51  # Самара
CITY = 'самара'
OWN = ('levsha-group.ru',)
# Площадки, которые занимают место в выдаче, но не являются сайтом исполнителя.
AGGREGATORS = ('2gis.', 'yandex.ru', 'avito.ru', 'zoon.ru', 'drive2.ru', 'vk.com', 'vk.ru', 'dzen.ru',
               'profi.ru', 'yell.ru', 'flamp.ru', 'otzovik', 'irecommend', 'youtube.com',
               'skidkom', 'orgpage', 'spravker', 'uslugio', 'kudago', 'tripadvisor', 'wikipedia',
               'ozon.ru', 'wildberries', 'market.yandex', 'auto.ru', 'drom.ru', 'mail.ru', 'pulscen')


def seeds():
    with SEEDS.open(encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def save(name, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')


def xmlriver(factory):
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(factory) / 'engine/seo-agent'))
    from modules import xmlriver_api as xr  # noqa: E402
    if not xr.available():
        sys.exit('XMLRiver не настроен в этом заводе.')
    return xr


def cmd_serp(a):
    xr = xmlriver(a.factory)
    name = 'serp.json' if a.region == REGION else f'serp-{a.region}.json'
    out = load(name)
    only = set(a.only.split(',')) if a.only else None
    for row in seeds():
        if only and row['cluster'] not in only:
            continue
        q = f"{row['phrase']} {a.city}"
        if out.get(q, {}).get('urls'):
            continue
        urls = xr.serp_top(q, region=a.region, depth=10)
        out[q] = {'cluster': row['cluster'], 'urls': urls, 'measured_on': str(date.today())}
        save(name, out)
        print(f'{len(urls):2d}  {q}', flush=True)
    print('Баланс XMLRiver:', xr.balance())


def ws_call(xr, query, pagetype):
    user, key = xr.get_credentials()
    url = ('https://xmlriver.com/wordstat/new/json?' + urllib.parse.urlencode(
        {'user': user, 'key': key, 'query': query, 'regions': REGION, 'device': '', 'pagetype': pagetype}))
    try:
        body = urllib.request.urlopen(url, timeout=120, context=xr._ssl_context()).read().decode('utf-8', 'replace')
        return json.loads(body)
    except Exception as exc:  # noqa: BLE001
        return {'error': type(exc).__name__}


def cmd_ws(a):
    xr = xmlriver(a.factory)
    out = load('wordstat.json')
    fails = 0
    for row in seeds():
        ph = row['phrase']
        rec = out.get(ph, {})
        if rec.get('quoted') is not None and rec.get('words_raw'):
            continue
        if rec.get('quoted') is None:
            data = ws_call(xr, f'"{ph}"', 'history')
            rec['quoted'] = None if data.get('error') else xr._dig_total(data)
            rec['quoted_error'] = data.get('error')
        if not rec.get('words_raw'):
            data = ws_call(xr, ph, 'words')
            rec['words_raw'] = None if data.get('error') else data
        rec.update(cluster=row['cluster'], measured_on=str(date.today()))
        out[ph] = rec
        save('wordstat.json', out)
        ok = rec['quoted'] is not None
        print(f"{'ok ' if ok else '---'} {ph}: {rec['quoted']}", flush=True)
        fails = 0 if ok else fails + 1
        if fails >= a.max_fails:
            print(f'{fails} отказов подряд — сервис Wordstat недоступен, повторить позже.')
            break
        time.sleep(a.pause)


UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
SKIP = re.compile(r'/(blog|news|novosti|stati|articles?|tag|tags|author|page/\d+|wp-content|upload|feed|otzyvy|reviews|akcii|sale)(/|$)|\.(jpg|jpeg|png|webp|pdf|xml)$', re.I)


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ru'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            return r.read(3_000_000).decode(r.headers.get_content_charset() or 'utf-8', 'replace')
    except Exception:  # noqa: BLE001
        return None


def sitemap_urls(base):
    """Все URL из sitemap: robots.txt → Sitemap:, иначе /sitemap.xml; индексы раскрываются."""
    robots = fetch(base + '/robots.txt') or ''
    queue = re.findall(r'(?im)^\s*sitemap:\s*(\S+)', robots) or [base + '/sitemap.xml']
    seen, urls = set(), []
    while queue and len(seen) < 30:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        body = fetch(sm) or ''
        locs = [html.unescape(x.strip()) for x in re.findall(r'<loc>(.*?)</loc>', body, re.S)]
        if '<sitemapindex' in body:
            queue += locs
        else:
            urls += locs
    return list(dict.fromkeys(urls))


def tag(body, name):
    m = re.search(rf'<{name}[^>]*>(.*?)</{name}>', body, re.S | re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1)))).strip() if m else ''


def cmd_pages(a):
    """Структура сайтов конкурентов: страницы из sitemap с title и H1, без блога и служебных."""
    out = load('pages.json')
    for d in a.domains:
        host = d.encode('idna').decode() if not d.isascii() else d
        base = f'https://{host}'
        if out.get(d, {}).get('pages') and not a.force:
            continue
        urls = [u for u in sitemap_urls(base) if not SKIP.search(urllib.parse.urlsplit(u).path)]
        pages = []
        for u in urls[:a.limit]:
            body = fetch(u)
            if body:
                pages.append({'url': u, 'title': tag(body, 'title'), 'h1': tag(body, 'h1')})
            time.sleep(0.3)
        out[d] = {'sitemap_urls': len(urls), 'pages': pages, 'measured_on': str(date.today())}
        save('pages.json', out)
        print(f'{d}: sitemap {len(urls)}, снято {len(pages)}', flush=True)


def domain(url):
    host = urllib.parse.urlsplit(url).hostname or ''
    host = host.encode().decode('idna') if host.startswith('xn--') else host
    return host[4:] if host.startswith('www.') else host


def kind(d):
    if any(o in d for o in OWN):
        return 'Левша'
    return 'площадка' if any(x in d for x in AGGREGATORS) else 'исполнитель'


def cmd_report(a):
    serp = load('serp.json')
    if not serp:
        sys.exit('Нет data/serp.json — сначала serp.')
    hits, best = Counter(), {}
    by_cluster = defaultdict(list)
    lines = ['# Выдача Яндекса, Самара (lr=51)', '']
    for q, rec in serp.items():
        ds = [domain(u) for u in rec['urls']]
        agg = sum(kind(d) == 'площадка' for d in ds)
        lev = next((i + 1 for i, d in enumerate(ds) if kind(d) == 'Левша'), None)
        by_cluster[rec['cluster']].append((q, agg, lev, len(ds)))
        for i, d in enumerate(dict.fromkeys(ds)):
            hits[d] += 1
            best[d] = min(best.get(d, 99), ds.index(d) + 1)
    lines += ['## По запросам', '', '| Кластер | Запрос | Площадок в топ-10 | Левша | URL получено |', '|---|---|---|---|---|']
    for c, rows in by_cluster.items():
        for q, agg, lev, n in rows:
            lines.append(f"| {c} | {q} | {agg} | {lev or '—'} | {n} |")
    lines += ['', '## Домены по числу запросов в топ-10', '', '| Домен | Тип | Запросов | Лучшая позиция |', '|---|---|---|---|']
    for d, n in hits.most_common(a.top):
        lines.append(f'| {d} | {kind(d)} | {n} | {best[d]} |')
    ws = load('wordstat.json')
    if ws:
        lines += ['', '## Wordstat, фразовая частотность, Самара', '', '| Кластер | Фраза | "фраза" |', '|---|---|---|']
        for ph, rec in ws.items():
            v = rec.get('quoted')
            lines.append(f"| {rec['cluster']} | {ph} | {v if v is not None else 'не замерено'} |")
    text = '\n'.join(lines) + '\n'
    (DATA / 'report.md').write_text(text, encoding='utf-8')
    print(text)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('serp'); s.add_argument('--factory', required=True)
    s.add_argument('--region', type=int, default=REGION, help='51 Самара, 213 Москва')
    s.add_argument('--city', default=CITY); s.add_argument('--only', help='кластеры через запятую')
    s.set_defaults(f=cmd_serp)
    w = sub.add_parser('ws'); w.add_argument('--factory', required=True)
    w.add_argument('--pause', type=float, default=2); w.add_argument('--max-fails', type=int, default=3)
    w.set_defaults(f=cmd_ws)
    g = sub.add_parser('pages'); g.add_argument('domains', nargs='+')
    g.add_argument('--limit', type=int, default=250); g.add_argument('--force', action='store_true')
    g.set_defaults(f=cmd_pages)
    r = sub.add_parser('report'); r.add_argument('--top', type=int, default=40); r.set_defaults(f=cmd_report)
    a = p.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
