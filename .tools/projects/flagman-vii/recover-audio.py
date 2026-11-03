"""Salvage decodable audio while preserving original timestamps and explicit gaps."""
import importlib.util
import json
import sys
import time
from pathlib import Path

import av
import numpy as np

spec = importlib.util.spec_from_file_location('course', Path(__file__).with_name('course.py'))
course = importlib.util.module_from_spec(spec)
spec.loader.exec_module(course)
IDS = {'v-ccd0a7049a14', 'v-506acadd15bd'}


def decode_with_gaps(path, seconds):
    audio = np.zeros(round((seconds + 2) * 16000), dtype=np.float32)
    valid = np.zeros(len(audio), dtype=bool)
    resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
    errors = []
    cursor = 0
    def place(frame):
        nonlocal cursor
        values = frame.to_ndarray().reshape(-1)
        offset = round(frame.time * 16000) if frame.time is not None else cursor
        start = max(offset, 0)
        stop = min(offset + len(values), len(audio))
        if stop > start:
            audio[start:stop] = values[start-offset:stop-offset].astype(np.float32) / 32768
            valid[start:stop] = True
        cursor = offset + len(values)
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        for packet in container.demux(stream):
            try:
                frames = packet.decode()
            except av.error.FFmpegError as exc:
                errors.append({'start': float(packet.pts * packet.time_base) if packet.pts is not None else None,
                               'duration': float((packet.duration or 0) * packet.time_base), 'error': str(exc)})
                continue
            for frame in frames:
                for output in resampler.resample(frame):
                    place(output)
        for output in resampler.resample(None):
            place(output)
    length = round(seconds * 16000)
    missing = ~valid[:length]
    edges = np.diff(np.concatenate(([False], missing, [False])).astype(np.int8))
    gaps = [{'start': int(a)/16000, 'end': int(b)/16000} for a, b in
            zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)) if b-a >= 1600]
    if not errors:
        raise ValueError('Expected known corrupt packets; review recovery assumptions')
    if sum(g['end']-g['start'] for g in gaps) > 90:
        raise ValueError('Recovery lost more audio than expected; manual review required')
    return audio[:length], gaps, errors


def main():
    inv = course.read_inventory()
    rows = [r for r in inv['files'] if r.get('id') in IDS and not course.complete(r)]
    media_spec = importlib.util.spec_from_file_location('local_media', course.VAULT / '.tools/universal/media/transcribe-video.py')
    media = importlib.util.module_from_spec(media_spec)
    media_spec.loader.exec_module(media)
    model = media.WhisperModel('large-v3', device='cuda', compute_type='int8', local_files_only=True)
    for row in rows:
        start = time.monotonic()
        print('Recovering ' + row['id'] + ': ' + row['path'], flush=True)
        audio, gaps, errors = decode_with_gaps(Path(inv['source']) / row['path'], row['seconds'])
        course.dump(course.DATA / 'recovery' / (row['id'] + '.json'), {'source': row['path'], 'gaps': gaps, 'packet_errors': errors})
        print('GAPS ' + json.dumps(gaps), flush=True)
        generated, info = model.transcribe(audio, language='ru', beam_size=5, vad_filter=True, condition_on_previous_text=False)
        records = [{'start': s.start, 'end': s.end, 'text': s.text.strip(),
                    'avg_logprob': s.avg_logprob, 'no_speech_prob': s.no_speech_prob} for s in generated]
        if not records:
            raise ValueError('Empty recovered transcript')
        notices = [{'start': g['start'], 'end': g['end'],
                    'text': '[ПОВРЕЖДЁН ЗВУК ИСХОДНИКА: слова не восстановлены]'} for g in gaps]
        combined = sorted(records + notices, key=lambda r: (r['start'], r['end']))
        gap_text = '\n'.join(f'- {course.stamp(g["start"], True)}–{course.stamp(g["end"], True)}: повреждён звук исходника.' for g in gaps)
        body = '\n\n'.join(f'**{course.stamp(s["start"])}–{course.stamp(s["end"])}** — {s["text"]}' for s in combined)
        base = course.DATA / 'transcripts' / row['id']
        course.write(base.with_suffix('.md'), f'# {Path(row["path"]).stem}\n\nИсточник: `{row["path"]}`\n\n'
                     f'Автоматическая транскрибация, не вычитана. large-v3, ru, int8, локально.\n\n'
                     f'## Повреждения источника\n\n{gap_text}\n\nТаймкоды соответствуют исходному видео; пропуски не сжаты.\n\n## Текст\n\n{body}\n')
        course.write(base.with_suffix('.srt'), '\n\n'.join(f'{i}\n{course.stamp(s["start"], True)} --> {course.stamp(s["end"], True)}\n{s["text"]}' for i,s in enumerate(combined,1))+'\n')
        course.dump(base.with_suffix('.json'), {'id': row['id'], 'source': row['path'], 'sha256': row['sha256'],
                    'status': 'complete_with_gaps', 'model': 'large-v3', 'language': 'ru', 'beam_size': 5,
                    'duration': info.duration, 'elapsed': time.monotonic()-start, 'segments': records,
                    'audio_gaps': gaps, 'decode_error_count': len(errors)})
        print('SAVED ' + row['id'], flush=True)
        course.status()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
