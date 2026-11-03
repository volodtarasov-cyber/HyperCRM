"""Package reviewed outputs and their local references; never include source video or unrelated vault data."""
import hashlib
import json
from pathlib import Path
import zipfile

BASE = Path(__file__).resolve().parents[3]
ROOT = BASE / 'knowledge/frameworks/flagman-vii-2025'
DATA = BASE / '.tools/local/flagman-vii'
EXPORT = DATA / 'exports'
inventory = json.loads((DATA / 'inventory.json').read_text(encoding='utf-8'))
ids = sorted({r['canonical_id'] for r in inventory['files'] if r.get('canonical_id')})
paths = list(ROOT.rglob('*.md'))
paths.extend(p for p in Path(__file__).resolve().parent.iterdir() if p.is_file() and p.suffix in ('.py', '.ps1', '.json', '.md'))
paths.extend(EXPORT / ('flagman-vii-book.' + ext) for ext in ('md', 'html', 'epub', 'pdf'))
paths.extend(DATA / 'transcripts' / (key + '.' + ext) for key in ids for ext in ('md', 'json', 'srt'))
paths.extend((DATA / 'attachments').glob('a-*.md'))
paths.extend(DATA / name for name in ('README.md', 'inventory.json', 'attachments.json', 'reading-state.json', 'service-mentions.json'))
paths.extend(DATA / 'analysis' / name for name in ('delivery-check.json', 'book-build.json', 'attachment-reading-state.json'))
target = EXPORT / 'flagman-vii-complete.zip'
readme = '''# «Флагман VII» — готовые материалы

Начать с [главного указателя](knowledge/frameworks/flagman-vii-2025/_index.md).

Книга: [.tools/local/flagman-vii/exports/](.tools/local/flagman-vii/exports/).
PDF и EPUB можно читать отдельно от остальных файлов.

Внутри: книга в четырёх форматах, 187 конспектов, 49 плейбуков, два маршрута, каталог сервисов, промпты/формы и транскрипты MD/JSON/SRT. Реестр связывает 198 исходных видео с 187 уникальными записями. В двух записях отмечены повреждения звука.

Архив предназначен для внутреннего использования. Видеофайлы и остальные данные CRM сюда не включены. Исходные адреса курса в реестре служат происхождению материала; для чтения книги сами видео не нужны.
'''
with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    archive.writestr('ОТКРЫТЬ.md', readme)
    for path in sorted(set(paths)):
        if not path.is_file():
            raise FileNotFoundError(path)
        archive.write(path, path.relative_to(BASE).as_posix())
with zipfile.ZipFile(target) as archive:
    bad = archive.testzip()
    count = len(archive.namelist())
if bad:
    raise ValueError('ZIP CRC error: ' + bad)
result = {'path': str(target), 'files': count, 'bytes': target.stat().st_size,
          'sha256': hashlib.file_digest(target.open('rb'), 'sha256').hexdigest(), 'zip_crc_valid': True}
(DATA / 'analysis/delivery-package.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
