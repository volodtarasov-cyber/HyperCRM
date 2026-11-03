"""Build a source-grounded service mention catalog; never infer a tariff or a recommendation."""
import collections
import importlib.util
import json
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('course', Path(__file__).with_name('course.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
OUT = c.VAULT / 'knowledge/frameworks/flagman-vii-2025'


def build():
    entries = json.loads(Path(__file__).with_name('services.json').read_text(encoding='utf-8'))
    manual_path = Path(__file__).with_name('manual-service-evidence.json')
    manual = json.loads(manual_path.read_text(encoding='utf-8')) if manual_path.exists() else {}
    inv = c.read_inventory()
    docs = json.loads((c.DATA / 'attachments.json').read_text(encoding='utf-8'))
    document_bodies = []
    for doc in docs:
        if 'error' not in doc:
            content = (c.DATA / 'attachments' / (doc['id'] + '.md')).read_text(encoding='utf-8')
            document_bodies.append((doc, content.split('\n\n', 2)[-1]))
    sources = []
    for row in inv['files']:
        if row['extension'] != '.mp4' or row['id'] != row['canonical_id']:
            continue
        path = c.DATA / 'transcripts' / (row['id'] + '.json')
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            sources.append((row, data['segments']))
    catalog = []
    for name, category, role, pattern, url in entries:
        rx = re.compile(pattern, re.I)
        found, attachments = [], []
        for row, segments in sources:
            for seg in segments:
                if rx.search(seg['text']):
                    found.append({'id': row['id'], 'source': row['path'], 'timestamp': c.stamp(seg['start']), 'text': seg['text']})
        for doc, content in document_bodies:
            if rx.search(content) or (url and url.rstrip('/') in content):
                attachments.append({'id': doc['id'], 'source': doc['path']})
        reading_evidence = manual.get(name, [])
        for evidence in reading_evidence:
            if not (OUT / evidence['note_path']).exists():
                raise ValueError('Missing reviewed note: ' + evidence['note_path'])
        if found or attachments or reading_evidence:
            catalog.append({'name': name, 'category': category, 'role': role, 'url_from_source': url or None,
                            'video_mentions': found, 'documents': attachments,
                            'reading_evidence': reading_evidence,
                            'current_tariff': None, 'recommendation': False})
    c.dump(c.DATA / 'service-mentions.json', catalog)
    categories = collections.defaultdict(list)
    for item in catalog:
        categories[item['category']].append(item)
    lines = ['# Сервисы, программы и площадки курса', '',
             '**Тип:** каталог упоминаний источника. **Составлено:** 2026-10-30.', '',
             'Сервис в этом списке означает упоминание в курсе или его раздатке. Это не список обязательных покупок и не рекомендация применять каждый подход. Рекламные ссылки раздачи и сайты конкурентов из рабочих таблиц не считаются SEO-сервисами.', '',
             'Названия нормализованы по речи и документам. Для редких или повреждённых распознаванием имён сохраняется пометка об уточнении. Функции ниже передают роль в курсе; текущие цены, акции, API-лимиты и доступность из конкретного аккаунта не установлены.', '',
             '[Контексты и таймкоды](service-evidence.md) · [Уточнения по полностью прочитанным урокам](services-clarifications.md) · [Обзор инструментов автором](lessons/v-a88ef2fced34.md)', '',
             f'В текущем каталоге {len(catalog)} именованных позиций. Повторяющиеся упоминания объединены; приложения и CMS отделены от специализированных SEO-инструментов.', '']
    detail = ['# Источники упоминаний сервисов', '',
              'Краткие контексты служат проверке названия и роли. Полный машинный указатель всех совпадений хранится в `.tools/local/flagman-vii/service-mentions.json`. Совпадение по имени не доказывает рекомендацию автора или успешное применение.', '']
    for category, items in categories.items():
        lines.extend(['## ' + category, '', '| Название | Роль в материале | Источник |', '|---|---|---|'])
        for item in items:
            name = item['name']
            anchor = 'service-' + str(catalog.index(item) + 1)
            label = f'[{name}]({item["url_from_source"]})' if item['url_from_source'] else name
            lines.append(f'| {label} | {item["role"]} | [Контекст](service-evidence.md#{anchor}) |')
            detail.extend([f'<a id="{anchor}"></a>', '', '## ' + name, '', '**Роль по материалу:** ' + item['role'], ''])
            for evidence in item['reading_evidence']:
                detail.append(f'- По полностью прочитанному [уроку {evidence["source_id"]} · {evidence["timestamp"]}]({evidence["note_path"]}): {evidence["role"]}')
            seen = set()
            for hit in item['video_mentions']:
                if hit['id'] in seen:
                    continue
                seen.add(hit['id'])
                excerpt = hit['text'].replace('\n', ' ')
                detail.append(f'- [{hit["id"]} · {hit["timestamp"]}](../../../.tools/local/flagman-vii/transcripts/{hit["id"]}.md): «{excerpt}»')
                if len(seen) >= 4:
                    break
            for hit in item['documents'][:3]:
                detail.append(f'- Раздатка: [{hit["id"]}](../../../.tools/local/flagman-vii/attachments/{hit["id"]}.md) — `{hit["source"]}`.')
            detail.append('')
        lines.append('')
    lines.extend(['## Границы каталога', '',
                  'Работа ведётся по курсу, без внешней проверки. Машинный поиск упоминаний не означает полного смыслового разбора каждого источника: роль и варианты названий уточняются по мере чтения. Сайты клиентов, конкурентов и рекламные вставки раздачи отделяются от инструментов.', '',
                  'Актуальные цены и доступность не устанавливаются. Неясные имена сохраняются отдельно с вопросом; догадка распознавания не превращается в точный адрес. Авторские методы описываются с их собственными оговорками.', ''])
    c.write(OUT / 'services.md', '\n'.join(lines))
    c.write(OUT / 'service-evidence.md', '\n'.join(detail))
    print(json.dumps({'catalog_entries': len(catalog), 'video_mentions': sum(len(i['video_mentions']) for i in catalog),
                      'entries_without_evidence': [e[0] for e in entries if e[0] not in {i['name'] for i in catalog}]}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build()
