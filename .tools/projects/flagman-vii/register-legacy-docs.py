"""Register read-only Word extractions with the other generated handouts."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DATA = BASE / '.tools/local/flagman-vii'
rows = json.loads((DATA / 'attachments.json').read_text(encoding='utf-8'))
legacy = json.loads((DATA / 'analysis/legacy-documents.json').read_text(encoding='utf-8'))
pack = []
for item in legacy:
    if 'error' in item:
        continue
    key = 'a-' + hashlib.sha1(item['path'].encode('utf-8')).hexdigest()[:12]
    body = Path(item['extracted_path']).read_text(encoding='utf-8').replace('\x07', '\t').replace('\r', '\n')
    text = '# ' + item['path'].split('/')[-1] + '\n\nSource: `' + item['path'] + '`\n\n' + body
    (DATA / 'attachments' / (key + '.md')).write_text(text, encoding='utf-8')
    if not any(row['id'] == key for row in rows):
        rows.append({'id': key, 'path': item['path'], 'characters': len(body), 'empty': not body.strip(),
                     'extraction': 'Word COM read-only; macros disabled'})
    pack.append('\n=== ' + key + ' | ' + item['path'] + ' ===\n' + body)
(DATA / 'attachments.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(DATA / 'analysis/legacy-reading.txt').write_text('\n'.join(pack), encoding='utf-8')
print(json.dumps({'registered': len(legacy), 'attachments': len(rows), 'reading_characters': sum(map(len, pack))}))
