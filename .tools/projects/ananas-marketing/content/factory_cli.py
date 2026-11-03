"""Manage the local content queue without opening or publishing anything."""
import argparse
import json
import sys
from pathlib import Path

from content_factory import FactoryStore,FactoryError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('list',help='Queue and release states')
    sub.add_parser('next',help='Print the brief of the first material without a pack')
    brief=sub.add_parser('brief');brief.add_argument('material_id')
    source=sub.add_parser('add');source.add_argument('--title',required=True);source.add_argument('--source',default='');source.add_argument('--niche',default='')
    bundle=sub.add_parser('import');bundle.add_argument('pack',type=Path);bundle.add_argument('--material-id');bundle.add_argument('--title',default='');bundle.add_argument('--source',default='');bundle.add_argument('--niche',default='')
    report=sub.add_parser('report');report.add_argument('release_id',type=int);report.add_argument('--link',default='');report.add_argument('--published-at')
    sub.add_parser('summary',help='Recorded results, with evidence and missing-data counts')
    args=parser.parse_args();store=FactoryStore()
    try:
        if args.command=='list':
            state=store.snapshot()
            print(json.dumps({'materials':state['materials'],'releases':[{k:r[k] for k in ('id','material_id','platform','account','state','scheduled_at','permalink')} for r in state['releases']]},ensure_ascii=False,indent=2))
        elif args.command in ('brief','next'):
            if args.command=='brief':mid=args.material_id
            else:
                state=store.snapshot();pending=[m for m in state['materials'] if not any(r['material_id']==m['id'] and r['version_id'] for r in state['releases'])]
                if not pending:print('Нет материалов без комплекта. Добавь источник через панель или команду add.');return 0
                mid=pending[-1]['id']
            print(store.brief(mid))
        elif args.command=='add':print(store.source(args.title,args.source,args.niche))
        elif args.command=='import':
            if args.material_id:
                with store.db() as db:row=db.execute('SELECT * FROM materials WHERE id=?',(args.material_id,)).fetchone()
                if not row:raise FactoryError('Материал не найден.')
                print(store.import_pack(args.pack,row['title'],row['source'],row['niche'],row['id']))
            else:print(store.import_pack(args.pack,args.title,args.source,args.niche))
        elif args.command=='report':store.report(args.release_id,args.link,args.published_at);print('Размещение записано как сообщение владельца; сверка отдельно.')
        elif args.command=='summary':
            state=store.snapshot()
            print(json.dumps({'counts':state['counts'],'measured_releases':sum(bool(r['metrics']) for r in state['releases']),
                'unverified_publications':sum(r['state'] in ('reported','published') for r in state['releases']),
                'unknown_lead_sources':sum(not l['release_id'] for l in state['leads']),
                'note':'Показатели отражают только учтённые данные; просмотры площадок не суммируются в уникальный охват.'},ensure_ascii=False,indent=2))
    except (FactoryError,OSError,ValueError) as exc:
        print(str(exc),file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
