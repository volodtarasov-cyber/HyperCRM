"""Prepare bounded attachment reading and distinguish narrative text from data tables."""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DATA = BASE / '.tools/local/flagman-vii'
INDEX = DATA / 'analysis/attachment-review-index.json'
PACK = DATA / 'analysis/attachment-narrative.txt'


def prepare():
    docs = json.loads((DATA / 'attachments.json').read_text(encoding='utf-8'))
    hashes = {}
    rows, parts = [], []
    offset = 0
    for doc in docs:
        body = (DATA / 'attachments' / (doc['id'] + '.md')).read_text(encoding='utf-8').split('\n\n', 2)[-1]
        digest = hashlib.sha256(body.encode()).hexdigest()
        row = dict(doc, body_sha256=digest)
        if digest in hashes:
            row['duplicate_of'] = hashes[digest]
        else:
            hashes[digest] = doc['id']
            ext = Path(doc['path']).suffix.lower()
            row['kind'] = 'table' if ext in ('.xlsx', '.csv') else 'narrative'
            if row['kind'] == 'narrative':
                section = '\n=== ' + doc['id'] + ' | ' + doc['path'] + ' ===\n' + body + '\n'
                row['start'] = offset
                offset += len(section)
                row['end'] = offset
                parts.append(section)
            else:
                lines = [s for s in body.splitlines() if s.strip()]
                row['nonempty_lines'] = len(lines)
                row['sheets'] = [s for s in lines if s.startswith('## ')]
        rows.append(row)
    PACK.write_text(''.join(parts), encoding='utf-8')
    INDEX.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(rows), 'unique': len(hashes), 'narrative_characters': offset,
                      'kinds': dict(collections.Counter(x.get('kind', 'duplicate') for x in rows))}))


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('command', choices=['prepare', 'read', 'tables', 'mark'])
parser.add_argument('--skip', type=int, default=0)
parser.add_argument('--take', type=int, default=14000)
parser.add_argument('--compact', action='store_true')
args = parser.parse_args()
if args.command == 'mark':
    state_path = DATA / 'analysis/attachment-reading-state.json'
    state = {'date': '2026-10-30', 'next_character': args.skip,
             'total_characters': len(PACK.read_text(encoding='utf-8')),
             'scope': 'unique narrative attachments; raw data tables reviewed separately'}
    state_path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(state))
elif args.command == 'prepare':
    prepare()
elif args.command == 'read':
    body = PACK.read_text(encoding='utf-8')
    end = min(len(body), args.skip + args.take)
    excerpt = body[args.skip:end]
    if args.compact:
        excerpt = re.sub(r'https?://\S+', lambda m: m[0] if '%' not in m[0] else '[percent-encoded reference URL]', excerpt)
        excerpt = re.sub(r'^.*SPONSOR.*$', '', excerpt, flags=re.M)
        excerpt = '\n'.join(line for line in excerpt.splitlines() if line.strip() and not line.startswith('## '))
    print(excerpt)
    print(f'\nCHAR_RANGE {args.skip}:{end}/{len(body)}')
else:
    rows = json.loads(INDEX.read_text(encoding='utf-8'))
    for row in rows:
        if row.get('kind') != 'table':
            continue
        body = (DATA / 'attachments' / (row['id'] + '.md')).read_text(encoding='utf-8').split('\n\n', 2)[-1]
        lines = [s for s in body.splitlines() if s.strip()]
        print('\n===', row['id'], row['path'], '| lines:', len(lines), '===')
        for line in lines[:8]:
            print(line[:450])
