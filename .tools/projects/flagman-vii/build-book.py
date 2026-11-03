"""Assemble the reviewed course artifacts; validate source coverage; export offline books."""
import argparse
import asyncio
import html
import json
import os
from pathlib import Path
import re
import zipfile

import markdown
from lxml import etree
from lxml import html as lhtml

BASE = Path(__file__).resolve().parents[3]
ROOT = BASE / 'knowledge/frameworks/flagman-vii-2025'
DATA = BASE / '.tools/local/flagman-vii'
EXPORT = DATA / 'exports'
TITLE = 'Флагман VII — книга, процессы и конспекты'
CHAPTERS = [
    'foundations', 'audits-part-one', 'technical-production',
    'traffic-part-one', 'traffic-part-two', 'traffic-part-three',
    'semantic-research', 'semantic-clustering', 'page-relevance',
    'template-diagnosis', 'content-production', 'links', 'growth-boosters',
    'positioning-reality', 'photo-reality', 'service-growth', 'work-organization',
]
CSS = '''
:root {color-scheme:light} * {box-sizing:border-box}
body {margin:0;color:#202832;background:#f6f3ec;font:18px/1.65 Georgia,"Times New Roman",serif}
main {max-width:1080px;margin:auto;padding:48px 56px;background:#fff}
h1,h2,h3,h4,h5 {font-family:Arial,sans-serif;line-height:1.22;color:#173a4a}
h1 {font-size:2.4em} h2 {font-size:1.75em} h3 {font-size:1.35em}
h4,h5 {font-size:1.1em} a {color:#126171;text-decoration-thickness:1px}
nav {padding:24px;background:#eef4f4;border-left:4px solid #176475}
nav li {margin:.25em 0} section {margin:64px 0} table {width:100%;border-collapse:collapse;font-size:.88em}
th,td {border:1px solid #cbd5d8;padding:7px 10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
th {background:#edf3f4} blockquote {border-left:3px solid #b78b4a;margin:1em 0;padding:0 1.2em}
pre {white-space:pre-wrap;background:#f2f4f5;padding:16px;font-size:.8em;overflow-wrap:anywhere}
code {font-size:.88em;overflow-wrap:anywhere} img {max-width:100%}
.cover {padding:72px 0;border-bottom:4px solid #b78b4a}
.eyebrow {font:14px Arial,sans-serif;text-transform:uppercase;letter-spacing:.12em;color:#65757b}
@page {size:A4;margin:19mm 16mm 19mm 19mm}
@media print {
 body {background:white;font-size:10.5pt;line-height:1.43} main {padding:0;max-width:none}
 .cover {min-height:220mm;padding-top:45mm;break-after:page}
 nav {background:white;border:0;padding:0;break-after:page;font-size:9pt}
 section {margin:0;break-before:page} h1,h2,h3,h4,h5 {break-after:avoid}
 h2 {font-size:21pt} h3 {font-size:15pt} h4 {font-size:12pt}
 p,li {orphans:3;widows:3} tr,blockquote {break-inside:avoid} thead {display:table-header-group}
 a {color:inherit;text-decoration:none} table {font-size:8.5pt} pre {font-size:8pt}
}
'''


def read(path):
    return path.read_text(encoding='utf-8')


def title(path):
    return next(line.lstrip('# ').strip() for line in read(path).splitlines() if line.startswith('# '))


def anchor(path):
    return 'doc-' + '-'.join(path.relative_to(ROOT).with_suffix('').parts)


def validate():
    inventory = json.loads(read(DATA / 'inventory.json'))
    videos = [r for r in inventory['files'] if r['extension'] == '.mp4']
    unique = [r for r in videos if r['id'] == r['canonical_id']]
    ids = {r['id'] for r in unique}
    notes = {p.stem for p in (ROOT / 'lessons').glob('v-*.md')}
    if ids != notes:
        raise ValueError({'missing_notes': sorted(ids - notes), 'extra_notes': sorted(notes - ids)})
    missing = []
    for row in videos:
        for ext in ('md', 'json', 'srt'):
            path = DATA / 'transcripts' / (row['canonical_id'] + '.' + ext)
            if not path.exists() or not path.stat().st_size:
                missing.append(str(path))
    if missing:
        raise ValueError({'missing_transcripts': missing})
    state = json.loads(read(DATA / 'reading-state.json'))
    if set(state['completed_note_ids']) != ids:
        raise ValueError('Reading state differs from reviewed note coverage')
    return unique, {'source_videos': len(videos), 'unique_videos': len(unique),
                    'exact_duplicates': len(videos) - len(unique), 'lesson_notes': len(notes),
                    'unique_hours': round(sum(r['seconds'] for r in unique) / 3600, 3)}


def processes():
    paths = sorted((ROOT / 'playbooks').glob('*.md'))
    lines = ['# Указатель процессов курса', '',
             '**Тип:** навигация по импортированным плейбукам. Это процессы из курса и явно помеченные редакторские сборки, не подтверждённый стандарт агентства.', '',
             f'В комплекте {len(paths)} плейбуков. В каждом указаны вход, действия/развилки, выход и источники. Примеры, исторические параметры и неизвестное отделяются от универсальных требований.', '',
             'Начать с маршрута [локальных услуг](launch-local-services.md) или [SEO для инфобизнеса](launch-infobusiness.md). По отдельному симптому выбирать нужный процесс ниже.', '',
             '| Процесс | Файл |', '|---|---|']
    for path in paths:
        lines.append(f'| {title(path)} | [{path.stem}](playbooks/{path.name}) |')
    lines.extend(['', 'Сопутствующие материалы: [шаблоны](templates.md), [промпты](prompt-library.md), [раздатка](attachments-guide.md), [сервисы](services.md).', ''])
    (ROOT / 'processes.md').write_text('\n'.join(lines), encoding='utf-8')
    return paths


def rebase(body, origin, included):
    def substitute(match):
        label, target = match.groups()
        raw = target.strip('<>')
        if re.match(r'^[a-z]+:', raw, re.I) or raw.startswith('#'):
            return match[0]
        rel, _, fragment = raw.partition('#')
        resolved = (origin.parent / rel).resolve()
        if resolved in included:
            return '[' + label + '](#' + anchor(resolved) + ')'
        if resolved.exists():
            rebased = os.path.relpath(resolved, EXPORT).replace('\\', '/')
            return '[' + label + '](<' + rebased + ('#' + fragment if fragment else '') + '>)'
        return match[0]
    return re.sub(r'(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)', substitute, body)


def clean_html(body):
    node = lhtml.fragment_fromstring(body, create_parent='div')
    for element in list(node.iter()):
        if element.tag in ('script', 'iframe', 'object', 'embed'):
            element.drop_tree()
        for key in list(element.attrib):
            if key.lower().startswith('on'):
                del element.attrib[key]
    return node


def build():
    EXPORT.mkdir(parents=True, exist_ok=True)
    unique, report = validate()
    playbooks = processes()
    groups = [
        ('Введение', [ROOT / 'book-introduction.md']),
        ('Часть I. Логика и тематические главы', [ROOT / 'chapters' / (c + '.md') for c in CHAPTERS]),
        ('Часть II. Маршруты и плейбуки', [ROOT / n for n in ('launch-local-services.md', 'launch-infobusiness.md', 'processes.md')] + playbooks),
        ('Часть III. Рабочий справочник', [ROOT / n for n in ('prompt-library.md', 'templates.md', 'attachments-guide.md', 'services.md', 'services-clarifications.md', 'service-evidence.md')]),
        ('Часть IV. Конспекты всех уникальных видео', [ROOT / 'lessons' / (r['id'] + '.md') for r in unique]),
    ]
    included = {p.resolve() for _, paths in groups for p in paths}
    contents, sections, toc = [], [], []
    for group, paths in groups:
        toc.append('<li><strong>' + html.escape(group) + '</strong><ol>')
        contents.extend(['## ' + group, ''])
        for n, path in enumerate(paths, 1):
            text = read(path)
            heading = title(path)
            if group.startswith('Часть IV'):
                heading = str(n) + '. ' + heading
            key = anchor(path)
            toc.append('<li><a href="#' + key + '">' + html.escape(heading) + '</a></li>')
            contents.append('- [' + heading + '](#' + key + ')')
            text = re.sub(r'^# [^\n]*\n', '', text, count=1).strip()
            if group.startswith('Часть IV'):
                text = '**Видео:** ' + str(n) + ' · **ID:** `' + path.stem + '`\n\n' + text
            text = rebase(text, path, included)
            text = re.sub(r'^(#{2,5}) ', r'#\1 ', text, flags=re.M)
            section_md = '<a id="' + key + '"></a>\n\n## ' + heading + '\n\n' + text
            sections.append(section_md)
        toc.append('</ol></li>')
        contents.append('')
    combined = '# ' + TITLE + '\n\n' + '\n'.join(contents) + '\n\n' + '\n\n---\n\n'.join(sections)
    (EXPORT / 'flagman-vii-book.md').write_text(combined, encoding='utf-8')
    rendered_sections = []
    for section in sections:
        rendered_sections.append('<section>' + markdown.markdown(section, extensions=['tables', 'fenced_code', 'sane_lists']) + '</section>')
    body = '<div class="cover"><p class="eyebrow">Внутренняя библиотека · по материалам курса</p><h1>' + TITLE + '</h1><p>Антон Маркин и приглашённые лекторы</p><p>187 конспектов · 49 плейбуков · два маршрута запуска</p><p>Сборка 30 октября 2026 · без внешнего фактчекинга</p></div>'
    body += '<nav id="contents"><h2>Содержание</h2><ol>' + ''.join(toc) + '</ol></nav>' + ''.join(rendered_sections)
    node = clean_html(body)
    serialized = ''.join(lhtml.tostring(child, encoding='unicode', method='html') for child in node)
    page = '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + TITLE + '</title><style>' + CSS + '</style></head><body><main>' + serialized + '</main></body></html>'
    (EXPORT / 'flagman-vii-book.html').write_text(page, encoding='utf-8')
    # EPUB is self-contained for all reviewed content; local raw-file links remain in HTML/MD only.
    for link in node.xpath('.//a[@href]'):
        href = link.get('href')
        if not href.startswith(('#', 'http:', 'https:', 'mailto:')):
            del link.attrib['href']
    for child in node.iter():
        if 'id' in child.attrib and not child.get('id').strip():
            del child.attrib['id']
    xbody = ''.join(etree.tostring(child, encoding='unicode', method='xml') for child in node)
    xhtml = '<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ru"><head><title>' + TITLE + '</title><link rel="stylesheet" type="text/css" href="style.css"/></head><body>' + xbody + '</body></html>'
    nav = '<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ru"><head><title>Содержание</title></head><body><nav epub:type="toc"><h1>Содержание</h1><ol>' + ''.join(toc).replace('href="#', 'href="main.xhtml#') + '</ol></nav></body></html>'
    opf = '''<?xml version="1.0" encoding="UTF-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">urn:flagman-vii:reviewed-2026-10-30</dc:identifier><dc:title>''' + TITLE + '''</dc:title><dc:language>ru</dc:language><dc:creator>Конспекты по курсу Антона Маркина и приглашённых лекторов</dc:creator><meta property="dcterms:modified">2026-10-30T00:00:00Z</meta></metadata><manifest><item id="main" href="main.xhtml" media-type="application/xhtml+xml"/><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="css" href="style.css" media-type="text/css"/></manifest><spine><itemref idref="main"/></spine></package>'''
    for xml in (xhtml, nav, opf):
        etree.fromstring(xml.encode('utf-8'))
    with zipfile.ZipFile(EXPORT / 'flagman-vii-book.epub', 'w') as archive:
        archive.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        archive.writestr('META-INF/container.xml', '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>', compress_type=zipfile.ZIP_DEFLATED)
        for name, text in [('main.xhtml', xhtml), ('nav.xhtml', nav), ('content.opf', opf), ('style.css', CSS)]:
            archive.writestr('OEBPS/' + name, text, compress_type=zipfile.ZIP_DEFLATED)
    report.update({'playbooks': len(playbooks), 'thematic_chapters': len(CHAPTERS), 'book_documents': len(included),
                   'book_characters': len(combined), 'export_directory': str(EXPORT)})
    (DATA / 'analysis/book-build.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


async def pdf():
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', 'D:/.cache/ms-playwright')
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(offline=True)
        page = await context.new_page()
        page.set_default_timeout(180000)
        await page.goto((EXPORT / 'flagman-vii-book.html').as_uri(), wait_until='load', timeout=180000)
        await page.pdf(path=str(EXPORT / 'flagman-vii-book.pdf'), format='A4', print_background=True,
                       prefer_css_page_size=True, display_header_footer=True,
                       header_template='<span></span>',
                       footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#69727a"><span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        await browser.close()
    import pymupdf
    document = pymupdf.open(EXPORT / 'flagman-vii-book.pdf')
    stats = {'pdf_pages': len(document), 'pdf_bytes': (EXPORT / 'flagman-vii-book.pdf').stat().st_size}
    report_path = DATA / 'analysis/book-build.json'
    report = json.loads(read(report_path))
    report.update(stats)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(stats))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', action='store_true')
    args = parser.parse_args()
    if args.pdf:
        asyncio.run(pdf())
    else:
        build()
