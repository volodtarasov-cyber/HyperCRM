"""Remove superseded agency adaptations; preserve course material and source uncertainty."""
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[3]
OUT = BASE / 'knowledge/frameworks/flagman-vii-2025'
BACKUP = BASE / '.tools/local/flagman-vii/analysis/before-course-only-edit'
BACKUP.mkdir(exist_ok=True)
changed = []
for path in (OUT / 'lessons').glob('v-*.md'):
    original = path.read_text(encoding='utf-8')
    body = re.sub(r'\n## Адаптация к агентству[^\n]*\n.*?(?=\n## |\Z)', '\n', original, flags=re.S)
    body = body.replace('## Что требует проверки', '## Границы сведений записи')
    body = re.sub(r'\*\*Граница источника:\*\*[^\n]*внешние правила[^\n]*',
                  '**Граница источника:** числа и биографические примеры переданы по записи; внешняя проверка в эту обработку не входит.', body)
    lines = []
    for line in body.splitlines():
        if 'reference-review' in line or 'проверку источников](../reference-review' in line or 'разборе применимости](../reference-review' in line:
            # Preserve paragraph context before the superseded final editorial sentence.
            if line.startswith('- '):
                continue
            sentences = re.split(r'(?<=[.!?])\s+(?=[А-ЯA-Z])', line)
            line = ' '.join(s for s in sentences if 'reference-review' not in s)
        if line.startswith('- ') and ('противоречат требованиям правдивого' in line or 'не включаются автоматически в рабочие стандарты' in line):
            continue
        lines.append(line)
    body = '\n'.join(lines).rstrip() + '\n'
    if body != original:
        (BACKUP / path.name).write_text(original, encoding='utf-8')
        path.write_text(body, encoding='utf-8')
        changed.append(path.name)
legacy = OUT / 'reference-review.md'
if legacy.exists():
    (BACKUP / legacy.name).write_bytes(legacy.read_bytes())
    legacy.unlink()
print({'notes_edited': len(changed), 'backup': str(BACKUP)})
