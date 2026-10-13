"""Снять quoted-частотность через XMLRiver модуль SEO-завода без изменения его конфига."""
import argparse
import csv
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', type=Path, required=True)
    parser.add_argument('--region', type=int, required=True)
    parser.add_argument('--region-name', required=True)
    parser.add_argument('--phrase', action='append', required=True)
    parser.add_argument('--date', required=True, help='Дата получения по клиентскому часовому поясу, YYYY-MM-DD')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.factory / 'engine/seo-agent'))
    from modules import xmlriver_api as xr
    xr.WORDSTAT_URL = 'https://xmlriver.com/wordstat/new/json'
    xr.MAX_RETRIES = 1
    if not xr.available():
        print('XMLRiver не настроен; ключи не выводятся. Частотность не получена.')
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for phrase in dict.fromkeys(args.phrase):
        value = None
        for attempt in range(2):
            try:
                value = xr.frequency([phrase], region=args.region, ws='quoted').get(phrase)
            except Exception as exc:
                print('Ошибка получения:', type(exc).__name__)
            if value is not None:
                break
        rows.append(dict(phrase=phrase, query='"' + phrase + '"', region=args.region,
                         region_name=args.region_name, quoted_frequency=value, measured_on=args.date,
                         metric='quoted_totalValue', period='previous_month_per_provider_docs',
                         devices='all', source='XMLRiver Wordstat New', state='measured' if value is not None else 'unknown'))
        args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'phrase': phrase, 'quoted_frequency': value}, ensure_ascii=True), flush=True)
    with args.out.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0 if all(r['quoted_frequency'] is not None for r in rows) else 2


if __name__ == '__main__':
    raise SystemExit(main())
