"""Check local assembly only, without opening external sources."""
import json
from pathlib import Path
import re
import zipfile
import pymupdf

from lxml import etree
from lxml import html

BASE = Path(__file__).resolve().parents[3]
ROOT = BASE / 'knowledge/frameworks/flagman-vii-2025'
DATA = BASE / '.tools/local/flagman-vii'
EXPORT = DATA / 'exports'
missing, links = [], 0
for path in ROOT.rglob('*.md'):
    if '_archive' in path.parts:
        continue
    body = path.read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^)\n]+)\)', body):
        target = target.strip('<>')
        if re.match(r'^[a-z]+:', target, re.I) or target.startswith('#'):
            continue
        relative = target.partition('#')[0]
        links += 1
        if not (path.parent / relative).resolve().exists():
            missing.append({'source': str(path.relative_to(ROOT)), 'target': target})
doc = html.parse(str(EXPORT / 'flagman-vii-book.html'))
ids = doc.xpath('//@id')
id_set = set(ids)
anchors = doc.xpath('//a[starts-with(@href,"#")]/@href')
bad_anchors = sorted({value for value in anchors if value[1:] not in id_set})
duplicates = sorted({value for value in ids if ids.count(value) > 1})
epub_local_missing = []
with zipfile.ZipFile(EXPORT / 'flagman-vii-book.epub') as archive:
    for name in ['META-INF/container.xml', 'OEBPS/content.opf', 'OEBPS/nav.xhtml', 'OEBPS/main.xhtml']:
        etree.fromstring(archive.read(name))
    main = etree.fromstring(archive.read('OEBPS/main.xhtml'))
    for href in main.xpath('//@href'):
        if not href.startswith(('#', 'http:', 'https:', 'mailto:')) and href != 'style.css':
            epub_local_missing.append(href)
services = json.loads((DATA / 'service-mentions.json').read_text(encoding='utf-8'))
without_evidence = [s['name'] for s in services if not (s['video_mentions'] or s['documents'] or s['reading_evidence'])]
report = {'markdown_local_links': links, 'missing_targets': missing,
          'html_anchors': len(anchors), 'missing_html_anchors': bad_anchors, 'duplicate_html_ids': duplicates,
          'epub_xml_valid': True, 'epub_external_local_links': epub_local_missing,
          'service_entries': len(services), 'services_without_evidence': without_evidence}
pdf = pymupdf.open(EXPORT / 'flagman-vii-book.pdf')
pdf_text = '\n'.join(page.get_text() for page in pdf)
inventory = json.loads((DATA / 'inventory.json').read_text(encoding='utf-8'))
lesson_ids = {r['id'] for r in inventory['files'] if r.get('id') and r.get('id') == r.get('canonical_id')}
missing_pdf_lessons = sorted(value for value in lesson_ids if value not in pdf_text)
report.update({'pdf_pages': len(pdf), 'pdf_missing_lesson_ids': missing_pdf_lessons})
(DATA / 'analysis/delivery-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
if any([missing, bad_anchors, duplicates, epub_local_missing, without_evidence, missing_pdf_lessons]):
    raise SystemExit(1)
