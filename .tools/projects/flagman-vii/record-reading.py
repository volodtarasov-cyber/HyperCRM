"""Persist reading position or a completed human-written source note without rereading the corpus."""
import argparse
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DATA = BASE / '.tools/local/flagman-vii'
NOTES = BASE / 'knowledge/frameworks/flagman-vii-2025/lessons'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source_id')
p.add_argument('--complete', action='store_true')
p.add_argument('--offset', type=int, default=0)
p.add_argument('--total', type=int)
a = p.parse_args()
state_path = DATA / 'reading-state.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
inv = json.loads((DATA / 'inventory.json').read_text(encoding='utf-8'))
source = next(r for r in inv['files'] if r.get('id') == a.source_id)
if a.complete:
    note = NOTES / (a.source_id + '.md')
    body = note.read_text(encoding='utf-8')
    ready = sorted(p.stem for p in NOTES.glob('*.md'))
    remaining = [r['id'] for r in inv['files'] if r.get('id') and r['id'] == r.get('canonical_id') and r['id'] not in ready]
    state.update(completed_note_ids=ready, remaining_note_ids=remaining,
                 last_completed_source_id=a.source_id, next_source_id=remaining[0] if remaining else None,
                 current_source_id=None, current_character_offset=0,
                 current_source_character_total=None, partial_note_path=None)
    state.pop('transcript_json_sha256', None)
    index_path = DATA / 'analysis/notes-index.json'
    records = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    records[a.source_id] = {'id': a.source_id, 'title': body.splitlines()[0].lstrip('# '),
                            'source': source['path'], 'read_complete': True,
                            'note_path': note.relative_to(BASE).as_posix()}
    index_path.write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Completed notes: {len(ready)}/187; next: {state["next_source_id"]}')
else:
    state.update(current_source_id=a.source_id, next_source_id=a.source_id,
                 current_character_offset=a.offset, current_source_character_total=a.total,
                 partial_note_path=f'.tools/local/flagman-vii/analysis/partial-{a.source_id}.md',
                 transcript_json_sha256=hashlib.sha256((DATA/'transcripts'/(a.source_id+'.json')).read_bytes()).hexdigest())
    print(f'Saved reading offset: {a.offset}/{a.total}')
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
