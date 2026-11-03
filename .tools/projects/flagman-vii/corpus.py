"""Read complete course transcripts in compact, source-linked order."""
import argparse
import collections
import importlib.util
import json
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('course', Path(__file__).with_name('course.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def rows():
    inv = c.read_inventory()
    return [r for r in inv['files'] if r['extension'] == '.mp4' and r['id'] == r['canonical_id']]


def read(row):
    p = c.DATA / 'transcripts' / (row['id'] + '.json')
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


def group(row):
    parts = row['path'].split('/')
    if 'Подготовка' in parts[0]:
        return 'Подготовка / ' + parts[1].replace('[SWBAND.CO] ', '')
    if 'Бонус' in parts[0]:
        return 'Бонус / Позиционка 4.0'
    return parts[1].replace('[SWBAND.CO] ', '') + ' / ' + parts[2].replace('[SWBAND.CO] ', '')


def outline():
    groups = collections.defaultdict(list)
    for n, row in enumerate(rows(), 1):
        groups[group(row)].append((n, row))
    for title, members in groups.items():
        print('\n## ' + title)
        for n, row in members:
            data = read(row)
            chars = sum(len(s['text']) for s in data['segments']) if data else 0
            print(f'{n:03} {row["id"]} {row["seconds"]/60:.1f}min {chars}chars ' + Path(row['path']).stem.replace('[SWBAND.CO] ', ''))


def full(ids, skip, take):
    for n, row in enumerate(rows(), 1):
        if row['id'] not in ids and str(n) not in ids:
            continue
        data = read(row)
        print(f'\n=== {n:03} {row["id"]} | {row["path"]} ===')
        if not data:
            print('TRANSCRIPT NOT AVAILABLE')
            continue
        if data.get('audio_gaps'):
            print('AUDIO_GAPS ' + json.dumps(data['audio_gaps']))
        paras, current, start = [], [], None
        for seg in data['segments']:
            if start is None:
                start = seg['start']
            current.append(seg['text'])
            if seg['end'] - start >= 120:
                paras.append(f'[{c.stamp(start)}] ' + ' '.join(current))
                current, start = [], None
        if current:
            paras.append(f'[{c.stamp(start)}] ' + ' '.join(current))
        text = '\n'.join(paras)
        selected = text[skip:skip+take] if take else text[skip:]
        print(selected)
        print(f'=== CHAR_RANGE {skip}:{skip+len(selected)} / {len(text)} ===')


def find(pattern):
    regex = re.compile(pattern, re.I)
    for n, row in enumerate(rows(), 1):
        data = read(row)
        if not data:
            continue
        found = []
        for seg in data['segments']:
            if regex.search(seg['text']):
                found.append(f'[{c.stamp(seg["start"])}] ' + seg['text'])
        if found:
            print(f'\n{n:03} {row["id"]} | {Path(row["path"]).stem}')
            print('\n'.join(found))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['outline', 'read', 'find'])
    p.add_argument('ids', nargs='*')
    p.add_argument('--skip', type=int, default=0)
    p.add_argument('--take', type=int, default=0)
    a = p.parse_args()
    if a.command == 'outline':
        outline()
    elif a.command == 'read':
        full(set(a.ids), a.skip, a.take)
    else:
        find(' '.join(a.ids))
