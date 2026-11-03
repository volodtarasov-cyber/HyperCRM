"""Render manually reviewed core lesson records; never infer notes from file names."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('corpus', HERE / 'corpus.py')
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)
OUT = corpus.c.VAULT / 'knowledge/frameworks/flagman-vii-2025/lessons'
DATA = corpus.c.DATA / 'analysis/core.json'


def save(records):
    prior = json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
    mapping = {r['id']: r for r in prior}
    source = {r['id']: r for r in corpus.rows()}
    for r in records:
        row = source[r['id']]
        r['source'] = row['path']
        mapping[r['id']] = r
        sections = [f'# {r["title"]}', '', f'**ID:** `{r["id"]}` · **Тип:** конспект источника · **Проверено:** 2026-10-29', '',
                    f'**Источник:** Антон Маркин, «Флагман VII» (2025), `{row["path"]}`.', '',
                    f'[Полная транскрибация](../../../../.tools/local/flagman-vii/transcripts/{r["id"]}.md). Автоматическая расшифровка; экранные действия без описания требуют сверки с видео.', '',
                    '## Суть и логика', '', r['summary'], '', '## Разбор урока', '']
        for title, body in r.get('sections', []):
            sections.extend(['### ' + title, '', body, ''])
        if r.get('processes'):
            sections.extend(['## Действия по источнику', ''])
            for p in r['processes']:
                sections.extend(['### ' + p['name'], '', '**Вход:** ' + p['inputs'], ''])
                sections.extend(f'{i}. {s}' for i, s in enumerate(p['steps'], 1))
                sections.extend(['', '**Результат:** ' + p['outputs'], '', '**Приёмка:** ' + p['acceptance'], '', '**Границы:** ' + p['limits'], ''])
        sections.extend(['## Сервисы и материалы', ''])
        if r.get('services'):
            sections.extend(f'- **{s["name"]}**, {s["timestamp"]}: {s["context"]}' for s in r['services'])
        else:
            sections.append('Отдельный программный инструмент в этом уроке не выделен.')
        sections.extend(['', '## Ограничения и проверка', ''])
        sections.extend('- ' + s for s in r.get('claims_to_verify', []))
        sections.extend(['', '## Адаптация к агентству — рекомендация', '', r.get('adaptation', 'Применять только после сопоставления с состоянием конкретного проекта; метод курса сам по себе не является доказательством результата агентства.'), '',
                         '## Короткая справка', '', r.get('quick', r['summary']), ''])
        corpus.c.write(OUT / (r['id'] + '.md'), '\n'.join(sections))
    ordered = sorted(mapping.values(), key=lambda r: next(i for i, s in enumerate(corpus.rows()) if s['id'] == r['id']))
    corpus.c.dump(DATA, ordered)
    print('Saved', len(records), 'records;', len(ordered), 'total')
