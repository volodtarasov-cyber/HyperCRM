"""Local, resumable Flagman VII ingestion. See adjacent README.md."""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
VAULT = HERE.parents[2]
DATA = VAULT / '.tools/local/flagman-vii'
SOURCE = Path(r'D:\Курсы\[SWBAND.CO] [Антон Маркин] Флагман VII (2025)\[SWBAND.CO] [Антон Маркин] Флагман VII (2025)')


def natural(value):
    return [int(x) if x.isdigit() else x.casefold() for x in re.split(r'(\d+)', str(value))]


def write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(body, encoding='utf-8')
    temp.replace(path)


def dump(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def read_inventory():
    return json.loads((DATA / 'inventory.json').read_text(encoding='utf-8'))


def inventory():
    import av
    rows, by_hash = [], {}
    files = sorted((p for p in SOURCE.rglob('*') if p.is_file()), key=lambda p: natural(p.relative_to(SOURCE)))
    # Main course is canonical when preparation/bonus contain the same bytes.
    files.sort(key=lambda p: 0 if p.relative_to(SOURCE).parts[0] == '[SWBAND.CO] Флагман 7' else 1)
    for p in files:
        rel = p.relative_to(SOURCE).as_posix()
        row = {'path': rel, 'bytes': p.stat().st_size, 'extension': p.suffix.lower()}
        if p.suffix.lower() == '.mp4':
            row['id'] = 'v-' + hashlib.sha256(rel.encode()).hexdigest()[:12]
            with p.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            row['sha256'] = digest
            row['canonical_id'] = by_hash.setdefault(digest, row['id'])
            try:
                with av.open(str(p)) as c:
                    row['seconds'] = c.duration / av.time_base if c.duration else None
                    row['audio_streams'] = len(c.streams.audio)
                    row['subtitle_streams'] = len(c.streams.subtitles)
            except Exception as exc:
                row['probe_error'] = str(exc)
        rows.append(row)
    videos = [r for r in rows if r['extension'] == '.mp4']
    canonical = [r for r in videos if r['id'] == r['canonical_id']]
    result = {'source': str(SOURCE), 'scanned_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'files': rows,
              'stats': {'files': len(rows), 'videos': len(videos), 'unique_videos': len(canonical),
                        'hours': sum(r.get('seconds') or 0 for r in videos) / 3600,
                        'unique_hours': sum(r.get('seconds') or 0 for r in canonical) / 3600,
                        'extensions': dict(collections.Counter(r['extension'] for r in rows))}}
    dump(DATA / 'inventory.json', result)
    print(json.dumps(result['stats'], ensure_ascii=False), flush=True)


def text_file(p):
    for encoding in ('utf-8-sig', 'utf-16', 'cp1251'):
        try:
            return p.read_text(encoding=encoding)
        except UnicodeError:
            pass
    raise ValueError('Unknown text encoding')


def xml_text(raw):
    root = ET.fromstring(raw)
    return '\n'.join(' '.join(t.itertext()) for t in root.iter() if t.tag.rsplit('}', 1)[-1] in ('p', 'title'))


def xlsx_without_styles(p):
    """Read values/formulas directly when a workbook has a broken stylesheet."""
    with zipfile.ZipFile(p) as z:
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(node.itertext()) for node in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        parts = ['[Извлечение OOXML без повреждённых стилей]']
        for name in sorted(z.namelist()):
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name):
                parts.append('## ' + name)
                root = ET.fromstring(z.read(name))
                for row in root.findall('.//s:sheetData/s:row', ns):
                    cells = []
                    for cell in row.findall('s:c', ns):
                        formula, value = cell.find('s:f', ns), cell.find('s:v', ns)
                        if formula is not None:
                            text = '=' + (formula.text or '')
                        elif cell.get('t') == 's' and value is not None:
                            text = shared[int(value.text)]
                        elif cell.get('t') == 'inlineStr':
                            text = ''.join(cell.find('s:is', ns).itertext())
                        else:
                            text = value.text if value is not None and value.text else ''
                        if text:
                            cells.append(cell.get('r', '') + ': ' + text)
                    if cells:
                        parts.append('\t'.join(cells))
                rels = name.replace('worksheets/', 'worksheets/_rels/') + '.rels'
                if rels in z.namelist():
                    parts.extend(node.attrib.get('Target', '') for node in ET.fromstring(z.read(rels))
                                 if node.attrib.get('Type', '').endswith('/hyperlink'))
        return '\n'.join(parts)


def extract():
    inv = read_inventory()
    results, links = [], []
    members_path = DATA / 'archive-members.json'
    members = json.loads(members_path.read_text(encoding='utf-8')) if members_path.exists() else []
    for row in inv['files'] + members:
        ext, rel = row['extension'], row['path']
        if ext not in ('.txt', '.docx', '.pdf', '.xlsx', '.xmind', '.csv', '.php', '.html'):
            continue  # .url files are distributor adverts, not course evidence.
        p = Path(row['local_path']) if 'local_path' in row else SOURCE / rel
        key = 'a-' + hashlib.sha256(rel.encode()).hexdigest()[:12]
        try:
            if ext in ('.txt', '.csv', '.php', '.html'):
                body = text_file(p)
            elif ext == '.docx':
                with zipfile.ZipFile(p) as z:
                    body = xml_text(z.read('word/document.xml'))
                    if 'word/_rels/document.xml.rels' in z.namelist():
                        for node in ET.fromstring(z.read('word/_rels/document.xml.rels')):
                            if node.attrib.get('Type', '').endswith('/hyperlink'):
                                body += '\n' + node.attrib.get('Target', '')
            elif ext == '.pdf':
                from pypdf import PdfReader
                body = '\n\n'.join(f'## Страница {i}\n\n{page.extract_text() or "[Нужна проверка изображения / OCR]"}'
                                   for i, page in enumerate(PdfReader(str(p)).pages, 1))
            elif ext == '.xlsx':
                from openpyxl import load_workbook
                try:
                    wb = load_workbook(p, read_only=False, data_only=False)
                except ValueError:
                    body = xlsx_without_styles(p)
                    wb = None
                parts = []
                for sheet in wb or []:
                    parts.append('## ' + sheet.title)
                    for cells in sheet.iter_rows():
                        values = [str(c.value) if c.value is not None else '' for c in cells]
                        if any(values):
                            parts.append('\t'.join(values))
                        parts.extend(c.hyperlink.target for c in cells if c.hyperlink and c.hyperlink.target)
                if wb is not None:
                    wb.close()
                    body = '\n'.join(parts)
            else:
                with zipfile.ZipFile(p) as z:
                    if 'content.xml' in z.namelist():
                        body = xml_text(z.read('content.xml'))
                    else:
                        content = json.loads(z.read('content.json'))
                        titles = []
                        def walk(value):
                            if isinstance(value, dict):
                                if isinstance(value.get('title'), str):
                                    titles.append(value['title'])
                                for child in value.values():
                                    walk(child)
                            elif isinstance(value, list):
                                for child in value:
                                    walk(child)
                        walk(content)
                        body = '\n'.join(titles)
            # Some PDF fonts produce UTF-16 surrogate pairs or isolated surrogates.
            body = body.encode('utf-16', errors='surrogatepass').decode('utf-16', errors='replace')
            write(DATA / 'attachments' / (key + '.md'), f'# {p.name}\n\nИсточник: `{rel}`\n\n{body}\n')
            results.append({'id': key, 'path': rel, 'characters': len(body), 'empty': not body.strip()})
            for line_no, line in enumerate(body.splitlines(), 1):
                for url in re.findall(r'https?://[^\s<>"\]]+', line):
                    links.append({'url': url.rstrip('.,;'), 'source': rel, 'line': line_no, 'context': line[:500]})
        except Exception as exc:
            results.append({'id': key, 'path': rel, 'error': str(exc)})
    dump(DATA / 'attachments.json', results)
    dump(DATA / 'links-unverified.json', links)
    print(json.dumps({'extracted': sum('error' not in r for r in results),
                      'errors': [r for r in results if 'error' in r], 'url_mentions': len(links),
                      'unique_urls': len({r['url'] for r in links})}, ensure_ascii=False), flush=True)


def unpack():
    """Extract ZIP members only into the ignored data folder; never run their code."""
    inv = read_inventory()
    rows = []
    for row in inv['files']:
        if row['extension'] != '.zip':
            continue
        archive = SOURCE / row['path']
        key = hashlib.sha256(row['path'].encode()).hexdigest()[:12]
        target = (DATA / 'unpacked' / key).resolve()
        with zipfile.ZipFile(archive) as z:
            if sum(i.file_size for i in z.infolist()) > 250 * 1024 * 1024:
                raise ValueError('Archive exceeds expected size: ' + row['path'])
            for info in z.infolist():
                if info.is_dir():
                    continue
                dest = (target / info.filename).resolve()
                dest.relative_to(target)  # Reject absolute paths and ../ escapes.
                if ':' in info.filename or '\\' in info.filename:
                    raise ValueError('Unexpected archive path: ' + info.filename)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(info))
                rows.append({'path': row['path'] + ' :: ' + info.filename, 'local_path': str(dest),
                             'extension': dest.suffix.lower(), 'bytes': info.file_size})
    dump(DATA / 'archive-members.json', rows)
    print(json.dumps({'archives': sum(r['extension'] == '.zip' for r in inv['files']),
                      'members': len(rows), 'extensions': dict(collections.Counter(r['extension'] for r in rows))}, ensure_ascii=False))


def stamp(seconds, srt=False):
    milliseconds = round(seconds * 1000)
    secs, ms = divmod(milliseconds, 1000)
    mins, sec = divmod(secs, 60)
    hour, minute = divmod(mins, 60)
    return f'{hour:02}:{minute:02}:{sec:02}' + (f',{ms:03}' if srt else '')


def decode(p):
    import av
    import numpy as np
    resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
    chunks = []
    with av.open(str(p)) as container:
        for frame in container.decode(audio=0):
            chunks.extend(f.to_ndarray().reshape(-1) for f in resampler.resample(frame))
    chunks.extend(f.to_ndarray().reshape(-1) for f in resampler.resample(None))
    if not chunks:
        raise ValueError('No decoded audio')
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def transcript_state(row):
    base = DATA / 'transcripts' / row['canonical_id']
    marker = base.with_suffix('.json')
    try:
        saved = json.loads(marker.read_text(encoding='utf-8'))
        if (saved.get('sha256') == row['sha256'] and saved.get('status') in ('complete', 'complete_with_gaps')
                and bool(saved.get('segments')) and base.with_suffix('.md').exists()
                and base.with_suffix('.srt').exists()):
            return saved['status']
    except (OSError, ValueError):
        pass
    return 'missing'


def complete(row):
    return transcript_state(row) != 'missing'


def run(limit):
    import msvcrt
    DATA.mkdir(parents=True, exist_ok=True)
    # OS lock is automatically released after a crash; a second worker cannot use the GPU.
    with (DATA / 'worker.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        inv = read_inventory()
        todo = [r for r in inv['files'] if r['extension'] == '.mp4' and r['id'] == r['canonical_id'] and not complete(r)]
        # Pilot is the shortest unique video; then preparation, main course, bonus, natural order.
        if limit:
            todo = sorted(todo, key=lambda r: r.get('seconds') or float('inf'))[:limit]
        else:
            todo.sort(key=lambda r: (0 if 'Подготовка/' in r['path'] else 2 if 'Бонус ' in r['path'] else 1, natural(r['path'])))
        print(f'Queue: {len(todo)} unique videos; PID {os.getpid()}', flush=True)
        if not todo:
            return
        # Reuse the established CUDA DLL and D:-cache setup from the existing tool.
        spec = importlib.util.spec_from_file_location('local_media', VAULT / '.tools/universal/media/transcribe-video.py')
        media = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(media)
        model = media.WhisperModel('large-v3', device='cuda', compute_type='int8', local_files_only=True)
        for index, row in enumerate(todo, 1):
            if (DATA / 'STOP').exists():
                print('STOP requested; stopping between videos', flush=True)
                break
            start = time.monotonic()
            dump(DATA / 'worker.json', {'pid': os.getpid(), 'video': row['id'], 'path': row['path'], 'state': 'transcribing'})
            print(f'[{index}/{len(todo)}] {row["path"]}', flush=True)
            try:
                audio = decode(SOURCE / row['path'])
                segments, info = model.transcribe(audio, language='ru', beam_size=5, vad_filter=True,
                                                  condition_on_previous_text=False)
                records = [{'start': s.start, 'end': s.end, 'text': s.text.strip(),
                            'avg_logprob': s.avg_logprob, 'no_speech_prob': s.no_speech_prob} for s in segments]
                if not records:
                    raise ValueError('Empty transcript requires manual review')
                elapsed = time.monotonic() - start
                base = DATA / 'transcripts' / row['id']
                body = '\n\n'.join(f'**{stamp(s["start"])}–{stamp(s["end"])}** — {s["text"]}' for s in records)
                write(base.with_suffix('.md'), f'# {Path(row["path"]).stem}\n\nИсточник: `{row["path"]}`\n\n'
                      f'Автоматическая транскрибация, не вычитана. large-v3, ru, int8, локально.\n\n{body}\n')
                write(base.with_suffix('.srt'), '\n\n'.join(f'{i}\n{stamp(s["start"], True)} --> {stamp(s["end"], True)}\n{s["text"]}' for i, s in enumerate(records, 1)) + '\n')
                # Completion marker is committed last, after both reader artifacts.
                dump(base.with_suffix('.json'), {'id': row['id'], 'source': row['path'], 'sha256': row['sha256'],
                     'status': 'complete', 'model': 'large-v3', 'language': 'ru', 'beam_size': 5,
                     'duration': info.duration, 'elapsed': elapsed, 'segments': records})
                print(f'OK {row["id"]}: {info.duration / 60:.1f} min in {elapsed:.1f}s; x{info.duration / elapsed:.2f}', flush=True)
                status()
                del audio
            except Exception as exc:
                dump(DATA / 'errors' / (row['id'] + '.json'), {'source': row['path'], 'error': str(exc)})
                print(f'ERROR {row["id"]}: {exc}', flush=True)
        dump(DATA / 'worker.json', {'pid': os.getpid(), 'state': 'stopped'})


def status():
    inv = read_inventory()
    videos = [r for r in inv['files'] if r['extension'] == '.mp4']
    unique = [r for r in videos if r['id'] == r['canonical_id']]
    ready = [r for r in unique if complete(r)]
    done_ids = {r['id'] for r in ready}
    stats = {'unique_complete': sum(transcript_state(r) == 'complete' for r in ready),
             'unique_with_gaps': sum(transcript_state(r) == 'complete_with_gaps' for r in ready),
             'unique_transcribed': len(ready), 'unique_total': len(unique),
             'source_videos_covered': sum(r['canonical_id'] in done_ids for r in videos),
             'source_videos_total': len(videos), 'unique_hours_remaining': round(sum((r.get('seconds') or 0) for r in unique if r['id'] not in done_ids) / 3600, 2)}
    lines = ['# Карта видео и транскрибаций', '',
             'Автоматически построено по inventory.json и полным комплектам MD/JSON/SRT.', '',
             f'Расшифровано уникальных: {len(ready)}/{len(unique)}, из них с повреждённым звуком: {stats["unique_with_gaps"]}. Покрыто исходных видео: {stats["source_videos_covered"]}/{len(videos)}.', '',
             '| Видео | Длительность | Транскрибация |', '|---|---|---|']
    for row in videos:
        target = row['canonical_id']
        result = f'[MD](transcripts/{target}.md) · [SRT](transcripts/{target}.srt)' if target in done_ids else 'Ожидает обработки'
        if transcript_state(row) == 'complete_with_gaps':
            result += ' · ЕСТЬ ПРОПУСКИ ЗВУКА'
        if target != row['id']:
            result += f' · точный дубль {target}'
        lines.append(f'| {row["path"].replace("|", "/")} | {stamp(row.get("seconds") or 0)} | {result} |')
    write(DATA / 'README.md', '\n'.join(lines) + '\n')
    print(json.dumps(stats, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inventory', 'unpack', 'extract', 'run', 'status'])
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    {'inventory': inventory, 'unpack': unpack, 'extract': extract, 'run': lambda: run(args.limit), 'status': status}[args.command]()
