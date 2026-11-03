"""Persistent local content queue. No network requests or publication side effects."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
LOCAL = ROOT/'.tools/local/social-publisher'
SAMARA = timezone(timedelta(hours=4))
CHANNELS = ('instagram','threads','telegram')
TERMINAL = ('reported','published','verified','submitting','unknown')
METRICS = ('views','reach','likes','comments','replies','shares','saves','reposts','quotes','profile_visits','follows')
LABELS = {'draft':'Черновик','approved':'Одобрено','scheduled':'Запланировано','prepared':'Черновик в браузере',
          'submitting':'Отправляется','published':'Опубликовано','verified':'Выход проверен',
          'reported':'Размещено — со слов владельца','error':'Ошибка','unknown':'Нужна сверка отправки','paused':'Пауза'}


class FactoryError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def parse_time(value):
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError,TypeError):
        raise FactoryError('Укажи дату и время с часовым поясом.') from None


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()


def inside(path, roots):
    path = Path(path).resolve()
    if not any(path.is_relative_to(Path(root).resolve()) for root in roots):
        raise FactoryError('Путь находится вне разрешённого каталога материалов.')
    return path


def account(platform, value):
    value = str(value or '').strip().lstrip('@').lower()
    pattern = r'[a-z0-9_.]{1,30}' if platform!='telegram' else r'[a-z][a-z0-9_]{3,31}'
    if not re.fullmatch(pattern,value):
        raise FactoryError('Укажи @username аккаунта или канала.')
    return value


def public_link(platform, value):
    value = str(value or '').strip()
    if not value:
        return ''
    parsed = urlparse(value)
    hosts = {'instagram':{'instagram.com','www.instagram.com'},
             'threads':{'threads.com','www.threads.com','threads.net','www.threads.net'},
             'telegram':{'t.me'}}
    patterns = {'instagram':r'/(?:[A-Za-z0-9_.]+/)?(?:p|reel)/[A-Za-z0-9_-]+/?',
                'threads':r'/@[a-zA-Z0-9_.]+/post/[A-Za-z0-9_-]+/?',
                'telegram':r'/[A-Za-z][A-Za-z0-9_]+/\d+/?'}
    if (parsed.scheme!='https' or parsed.hostname not in hosts[platform] or parsed.username or parsed.password
            or not re.fullmatch(patterns[platform],parsed.path) or parsed.port not in (None,443)):
        raise FactoryError('Нужна прямая HTTPS-ссылка на пост выбранной площадки.')
    return parsed._replace(query='',fragment='').geturl()


def read_pack(directory, allowed_root=ROOT/'.tools/carousel-out'):
    directory = inside(directory,[allowed_root])
    if not directory.is_dir():
        raise FactoryError('Папка комплекта не найдена.')
    files = sorted(p for p in directory.glob('slide-*.png') if re.fullmatch(r'slide-\d{2}\.png',p.name))
    if not 2<=len(files)<=10 or [p.name for p in files]!=[f'slide-{i:02}.png' for i in range(1,len(files)+1)]:
        raise FactoryError('Нужны 2–10 последовательно пронумерованных PNG-карточек.')
    assets=[]; size=None
    for path in files:
        inside(path,[directory])
        with Image.open(path) as picture:
            picture.verify()
        with Image.open(path) as picture:
            if size is not None and picture.size!=size:
                raise FactoryError('Карточки имеют разные размеры.')
            size=picture.size
        assets.append({'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    captions={}
    for p,name in [('instagram','instagram-caption.txt'),('threads','threads-post.txt'),('telegram','telegram-post.txt')]:
        file=inside(directory/name,[directory])
        captions[p]=file.read_text(encoding='utf-8').strip() if file.exists() else ''
    validation=directory/'validation.json'
    valid=False
    if validation.exists():
        report=json.loads(inside(validation,[directory]).read_text(encoding='utf-8'))
        valid=isinstance(report,dict) and report.get('errors')==[]
    valid=valid and all((directory/name).is_file() for name in ('preview.html','profile-grid-preview.png'))
    return {'directory':str(directory),'assets':assets,'size':size,'captions':captions,'validated':valid}


class FactoryStore:
    def __init__(self, directory=LOCAL, pack_root=None, source_roots=None,recover=False):
        self.local=Path(directory); self.local.mkdir(parents=True,exist_ok=True)
        self.path=self.local/'factory.sqlite3'
        self.pack_root=Path(pack_root or ROOT/'.tools/carousel-out').resolve()
        self.source_roots=source_roots or [ROOT/'agency/cases',ROOT/'clients',ROOT.parent/'agency-site/src/content/cases']
        self.lock=threading.RLock()
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS materials(id TEXT PRIMARY KEY,title TEXT NOT NULL,source TEXT NOT NULL DEFAULT '',
              niche TEXT NOT NULL DEFAULT '',format TEXT NOT NULL DEFAULT 'case',created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions(id INTEGER PRIMARY KEY,material_id TEXT NOT NULL REFERENCES materials(id),
              digest TEXT NOT NULL,pack TEXT NOT NULL,assets TEXT NOT NULL,captions TEXT NOT NULL,validated INTEGER NOT NULL,
              created_at TEXT NOT NULL,UNIQUE(material_id,digest));
            CREATE TABLE IF NOT EXISTS releases(id INTEGER PRIMARY KEY,material_id TEXT NOT NULL REFERENCES materials(id),
              platform TEXT NOT NULL,account TEXT NOT NULL DEFAULT '',version_id INTEGER REFERENCES versions(id),
              state TEXT NOT NULL DEFAULT 'draft',approval TEXT NOT NULL DEFAULT '',scheduled_at TEXT,
              auto INTEGER NOT NULL DEFAULT 0,published_at TEXT,permalink TEXT NOT NULL DEFAULT '',
              evidence TEXT NOT NULL DEFAULT '',error TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL,
              UNIQUE(material_id,platform));
            CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,release_id INTEGER NOT NULL REFERENCES releases(id),
              state TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,detail TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS measurements(id INTEGER PRIMARY KEY,release_id INTEGER NOT NULL REFERENCES releases(id),
              metric TEXT NOT NULL,value REAL,status TEXT NOT NULL,measured_at TEXT NOT NULL,source TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY,release_id INTEGER REFERENCES releases(id),
              stage TEXT NOT NULL,amount REAL,reference TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS measured_release ON measurements(release_id,metric,measured_at DESC);
            ''')
            db.execute("INSERT OR IGNORE INTO settings VALUES('autopublish','false')")
            # A crash after the send boundary must never make a job retryable.
            if recover:
                db.execute("UPDATE releases SET state='unknown',error='Инструмент прервался во время отправки. Сверь профиль.',updated_at=? WHERE state='submitting'",(now(),))
                db.execute("UPDATE attempts SET state='unknown',finished_at=? WHERE state='submitting'",(now(),))
                db.execute("UPDATE releases SET state=CASE WHEN approval<>'' THEN 'approved' ELSE 'draft' END WHERE state='prepared'")

    @contextmanager
    def db(self):
        with self.lock:
            con=sqlite3.connect(self.path,timeout=15)
            con.row_factory=sqlite3.Row
            con.execute('PRAGMA foreign_keys=ON')
            con.execute('PRAGMA journal_mode=WAL')
            try:
                yield con
                con.commit()
            except Exception:
                con.rollback();raise
            finally:
                con.close()

    def setting(self,key,value=None):
        with self.db() as db:
            if value is not None:
                db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
            row=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
            return json.loads(row[0]) if row else None

    def get_release(self,rid):
        with self.db() as db:
            row=db.execute('''SELECT r.*,m.title,m.source,m.niche,v.digest,v.pack,v.assets,v.captions,v.validated
              FROM releases r JOIN materials m ON m.id=r.material_id LEFT JOIN versions v ON v.id=r.version_id WHERE r.id=?''',(int(rid),)).fetchone()
            if not row:raise FactoryError('Выпуск не найден.')
            item=dict(row)
            for name in ('assets','captions'):item[name]=json.loads(item[name]) if item[name] else ([] if name=='assets' else {})
            item['caption']=item['captions'].get(item['platform'],'')
            return item

    def source(self,title,source='',niche='',material_id=None):
        title=str(title).strip()
        if not title or len(title)>180:raise FactoryError('Укажи название материала до 180 символов.')
        if source:
            path=inside(source,self.source_roots)
            if path.suffix.lower()!='.md' or not path.is_file() or path.name in ('access.md','_notes.md'):
                raise FactoryError('Нужен Markdown-источник кейса без файла доступов.')
            source=str(path)
        mid=material_id or digest(source or title)[:20]
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',mid):raise FactoryError('Недопустимый ID материала.')
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO materials VALUES(?,?,?,?,?,?)',(mid,title,source,str(niche)[:100],'case',now()))
            for platform in CHANNELS:
                db.execute('INSERT OR IGNORE INTO releases(material_id,platform,updated_at) VALUES(?,?,?)',(mid,platform,now()))
        return mid

    def import_pack(self,directory,title='',source='',niche='',material_id=None):
        pack=read_pack(directory,self.pack_root)
        mid=self.source(title or Path(directory).name,source,niche,material_id or digest(str(Path(directory).resolve()))[:20])
        version_hash=digest({'assets':pack['assets'],'captions':pack['captions']})
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO versions(material_id,digest,pack,assets,captions,validated,created_at) VALUES(?,?,?,?,?,?,?)',
                       (mid,version_hash,pack['directory'],json.dumps(pack['assets']),json.dumps(pack['captions'],ensure_ascii=False),int(pack['validated']),now()))
            vid=db.execute('SELECT id FROM versions WHERE material_id=? AND digest=?',(mid,version_hash)).fetchone()[0]
            # Importing or editing a pack cannot reset published/uncertain jobs.
            db.execute("""UPDATE releases SET version_id=?,state='draft',approval='',auto=0,scheduled_at=NULL,error='',updated_at=?
              WHERE material_id=? AND (version_id IS NULL OR version_id<>?) AND state NOT IN ('reported','published','verified','submitting','unknown')""",(vid,now(),mid,vid))
        return mid

    def find_release(self,pack,platform,owner):
        with self.db() as db:
            row=db.execute('''SELECT r.id FROM releases r JOIN versions v ON v.id=r.version_id
                WHERE v.pack=? AND r.platform=? AND r.account=?''',(str(Path(pack).resolve()),platform,owner)).fetchone()
            return row[0] if row else None

    def current(self,rid,require_approval=False):
        item=self.get_release(rid)
        if not item['version_id']:raise FactoryError('Сначала добавь готовый комплект карточек.')
        pack=read_pack(item['pack'],self.pack_root)
        if pack['assets']!=item['assets']:
            raise FactoryError('Карточки изменились. Импортируй новую версию и одобри её заново.')
        if require_approval and (item['approval']!=item['digest'] or not pack['validated']):
            raise FactoryError('Нужна одобренная версия с пройденной проверкой карточек.')
        return item

    def configure(self,rid,owner):
        item=self.get_release(rid);owner=account(item['platform'],owner)
        if item['state'] in TERMINAL:raise FactoryError('Аккаунт завершённого или неподтверждённого выпуска менять нельзя.')
        with self.db() as db:
            if owner!=item['account']:
                result=db.execute("UPDATE releases SET account=?,approval='',state='draft',auto=0,scheduled_at=NULL,updated_at=? WHERE id=? AND state NOT IN ('reported','published','verified','submitting','unknown')",(owner,now(),rid))
                if not result.rowcount:raise FactoryError('Состояние выпуска изменилось. Обнови карточку.')

    def edit_caption(self,rid,text):
        item=self.current(rid)
        if item['state'] in TERMINAL:raise FactoryError('Этот выпуск уже отправлен или требует сверки. Текст менять нельзя.')
        text=str(text).strip();limit={'instagram':2200,'threads':500,'telegram':4096}[item['platform']]
        if not text or len(text)>limit:raise FactoryError(f'Текст должен содержать 1–{limit} символов.')
        captions=dict(item['captions']);captions[item['platform']]=text
        hashed=digest({'assets':item['assets'],'captions':captions})
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO versions(material_id,digest,pack,assets,captions,validated,created_at) VALUES(?,?,?,?,?,?,?)',
                (item['material_id'],hashed,item['pack'],json.dumps(item['assets']),json.dumps(captions,ensure_ascii=False),item['validated'],now()))
            vid=db.execute('SELECT id FROM versions WHERE material_id=? AND digest=?',(item['material_id'],hashed)).fetchone()[0]
            if vid!=item['version_id']:
                result=db.execute("UPDATE releases SET version_id=?,approval='',state='draft',auto=0,scheduled_at=NULL,updated_at=? WHERE id=? AND version_id=? AND state NOT IN ('reported','published','verified','submitting','unknown')",(vid,now(),rid,item['version_id']))
                if not result.rowcount:raise FactoryError('Состояние или версия изменились. Обнови карточку.')

    def approve(self,rid):
        item=self.current(rid)
        if item['state'] in TERMINAL:raise FactoryError('Выпуск уже размещён или требует сверки.')
        account(item['platform'],item['account'])
        if not read_pack(item['pack'],self.pack_root)['validated']:raise FactoryError('Нужны успешная проверка и превью сетки Instagram.')
        limit={'instagram':2200,'threads':500,'telegram':4096}[item['platform']]
        if not item['caption'] or len(item['caption'])>limit:raise FactoryError('Проверь длину текста этой площадки.')
        with self.db() as db:
            result=db.execute("UPDATE releases SET approval=?,state='approved',error='',updated_at=? WHERE id=? AND version_id=? AND state NOT IN ('reported','published','verified','submitting','unknown')",(item['digest'],now(),rid,item['version_id']))
            if not result.rowcount:raise FactoryError('Состояние или версия изменились. Обнови карточку.')

    def schedule(self,rid,when,auto=False):
        item=self.current(rid,require_approval=True)
        if item['state'] in TERMINAL:raise FactoryError('Выпуск уже размещён или требует сверки.')
        planned=parse_time(when)
        if planned<=datetime.now(timezone.utc):raise FactoryError('Выбери время в будущем по Самаре.')
        if auto and item['platform']=='telegram':raise FactoryError('Автовыпуск Telegram ещё не подключён. Доступен календарь ручного выпуска.')
        with self.db() as db:
            result=db.execute("UPDATE releases SET state='scheduled',scheduled_at=?,auto=?,error='',updated_at=? WHERE id=? AND approval=? AND version_id=? AND state NOT IN ('reported','published','verified','submitting','unknown')",(planned.isoformat(),int(bool(auto)),now(),rid,item['digest'],item['version_id']))
            if not result.rowcount:raise FactoryError('Одобрение или состояние изменились. Обнови карточку.')

    def pause(self,rid):
        item=self.get_release(rid)
        if item['state'] in TERMINAL:raise FactoryError('Отправленный или неподтверждённый выпуск нельзя вернуть в очередь.')
        with self.db() as db:
            result=db.execute("UPDATE releases SET state='paused',auto=0,updated_at=? WHERE id=? AND state NOT IN ('reported','published','verified','submitting','unknown')",(now(),rid))
            if not result.rowcount:raise FactoryError('Выпуск уже отправляется или размещён.')

    def mark_prepared(self,rid):
        with self.db() as db:
            db.execute("UPDATE releases SET state='prepared',error='',updated_at=? WHERE id=? AND state NOT IN ('reported','published','verified','submitting','unknown')",(now(),rid))

    def begin_send(self,rid):
        # Recheck disk and reserve transactionally before a single external click.
        item=self.current(rid,require_approval=True)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state,approval,version_id FROM releases WHERE id=?',(rid,)).fetchone()
            if row['state'] not in ('approved','scheduled','prepared') or row['approval']!=item['digest'] or row['version_id']!=item['version_id']:
                raise FactoryError('Отправка уже начата, версия изменилась или выпуск не одобрен.')
            db.execute("UPDATE releases SET state='submitting',updated_at=? WHERE id=?",(now(),rid))
            cursor=db.execute("INSERT INTO attempts(release_id,state,started_at) VALUES(?,'submitting',?)",(rid,now()))
            return cursor.lastrowid

    def finish_send(self,rid,state,link='',detail=''):
        if state not in ('published','unknown'):raise FactoryError('Недопустимый исход отправки.')
        item=self.get_release(rid)
        link=public_link(item['platform'],link) if link else ''
        with self.db() as db:
            db.execute("UPDATE attempts SET state=?,finished_at=?,detail=? WHERE release_id=? AND state='submitting'",(state,now(),str(detail)[:400],rid))
            db.execute('''UPDATE releases SET state=?,permalink=?,published_at=?,evidence=?,error=?,auto=0,updated_at=? WHERE id=?''',
                (state,link,now() if state=='published' else None,'platform_confirmation' if state=='published' else '',str(detail)[:400],now(),rid))

    def error(self,rid,message):
        with self.db() as db:
            db.execute("UPDATE releases SET state=CASE WHEN state='submitting' THEN 'unknown' ELSE 'error' END,error=?,auto=0,updated_at=? WHERE id=? AND state NOT IN ('reported','published','verified','unknown')",(str(message)[:500],now(),rid))

    def report(self,rid,link='',published_at=None,note='Сообщено владельцем'):
        item=self.get_release(rid)
        if item['state']=='submitting':raise FactoryError('Дождись завершения отправки.')
        link=public_link(item['platform'],link)
        stamp=parse_time(published_at).isoformat() if published_at else None
        if stamp and parse_time(stamp)>datetime.now(timezone.utc):raise FactoryError('Дата выхода не может быть в будущем.')
        if item['state']=='verified' and link==item['permalink']:
            with self.db() as db:
                db.execute('UPDATE releases SET published_at=?,updated_at=? WHERE id=?',
                    (stamp or item['published_at'],now(),rid))
            return
        with self.db() as db:
            result=db.execute("UPDATE releases SET state='reported',permalink=?,published_at=?,evidence=?,auto=0,error='',updated_at=? WHERE id=? AND state<>'submitting'",(link,stamp,str(note)[:300],now(),rid))
            if not result.rowcount:raise FactoryError('Отправка началась. Обнови карточку.')

    def verify(self,rid,link,published_at=None):
        item=self.get_release(rid);link=public_link(item['platform'],link)
        if not link:raise FactoryError('Ссылка на пост не найдена.')
        if item['state'] not in ('reported','published','verified','unknown'):
            raise FactoryError('Сначала укажи размещённый пост.')
        with self.db() as db:
            stamp=parse_time(published_at).isoformat() if published_at else item['published_at']
            db.execute("UPDATE releases SET state='verified',permalink=?,published_at=?,evidence='browser_verified',error='',auto=0,updated_at=? WHERE id=?",(link,stamp,now(),rid))

    def measurement(self,rid,metric,value=None,status='ok',measured_at=None,source='Ручной ввод'):
        item=self.get_release(rid)
        if item['state'] not in ('reported','published','verified'):raise FactoryError('Замер относится к размещённому посту.')
        if metric not in METRICS or status not in ('ok','no_access','unsupported','error','not_measured'):raise FactoryError('Неизвестная метрика или состояние замера.')
        stamp=parse_time(measured_at or now())
        if stamp>datetime.now(timezone.utc)+timedelta(minutes=2):raise FactoryError('Замер не может быть из будущего.')
        if item['published_at'] and stamp<parse_time(item['published_at']):raise FactoryError('Замер сделан раньше публикации.')
        if status=='ok':
            try:value=float(value)
            except (ValueError,TypeError):raise FactoryError('Нужно числовое значение.') from None
            if not math.isfinite(value) or value<0:raise FactoryError('Значение должно быть конечным и неотрицательным.')
        else:value=None
        if not str(source).strip():raise FactoryError('Укажи источник замера.')
        with self.db() as db:
            db.execute('INSERT INTO measurements(release_id,metric,value,status,measured_at,source) VALUES(?,?,?,?,?,?)',
                (rid,metric,value,status,stamp.isoformat(),str(source)[:250]))

    def lead(self,rid,stage,reference,amount=None,note=''):
        if rid:self.get_release(rid)
        if stage not in ('new','qualified','won','lost') or not str(reference).strip():raise FactoryError('Укажи этап и ссылку/ID обращения в учёте продаж.')
        if amount not in (None,''):
            try:amount=float(amount)
            except (TypeError,ValueError):raise FactoryError('Некорректная сумма.') from None
            if stage!='won' or not math.isfinite(amount) or amount<0:raise FactoryError('Подтверждённая выручка учитывается только у сделки.')
        else:amount=None
        with self.db() as db:
            existing=db.execute('SELECT id FROM leads WHERE reference=?',(str(reference),)).fetchone()
            if existing:
                db.execute('UPDATE leads SET release_id=?,stage=?,amount=?,note=? WHERE id=?',(rid or None,stage,amount,str(note)[:500],existing[0]))
            else:
                db.execute('INSERT INTO leads(release_id,stage,amount,reference,note,created_at) VALUES(?,?,?,?,?,?)',(rid or None,stage,amount,str(reference)[:300],str(note)[:500],now()))

    def due(self):
        if not self.setting('autopublish'):return []
        current=datetime.now(timezone.utc)
        with self.db() as db:
            rows=db.execute("SELECT id,scheduled_at FROM releases WHERE state='scheduled' AND auto=1 ORDER BY scheduled_at,id").fetchall()
        # Do not drain days of missed publications after a machine was off.
        return [r['id'] for r in rows if timedelta(0)<=current-parse_time(r['scheduled_at'])<=timedelta(minutes=10)]

    def brief(self,mid):
        with self.db() as db:row=db.execute('SELECT * FROM materials WHERE id=?',(mid,)).fetchone()
        if not row:raise FactoryError('Материал не найден.')
        return (f"# Подготовить комплект: {row['title']}\n\nИсточник: {row['source'] or '? — нужен источник'}\n"
            f"ID материала в заводе: {mid}\nНиша: {row['niche'] or '?'}\n\n"
            "Примени .claude/skills/agency-carousel/SKILL.md, связанные copywriter и humanize-text. "
            "Прочитай источник; составь паспорт подтверждённых фактов и границ раскрытия. "
            "Не выдумывай цифры, город, продажи и доступы. Подготовь Instagram, Threads и самостоятельный Telegram-пост. "
            "Сохрани исходный сценарий и HTML по правилам навыка. Экспортируй комплект через carousel-export.py; "
            "проверь сетку профиля и изображения. Импортируй папку комплекта в этот материал по его ID. "
            "Публикация отдельным действием после одобрения версии.\n")

    def snapshot(self):
        with self.db() as db:
            materials=[dict(r) for r in db.execute('SELECT * FROM materials ORDER BY created_at DESC,id')]
            release_ids=[r[0] for r in db.execute('SELECT id FROM releases ORDER BY id')]
            metrics=[dict(r) for r in db.execute('''SELECT * FROM measurements ORDER BY measured_at DESC,id DESC''')]
            leads=[dict(r) for r in db.execute('SELECT * FROM leads ORDER BY created_at DESC,id DESC')]
            attempts=[dict(r) for r in db.execute('SELECT * FROM attempts ORDER BY id DESC LIMIT 100')]
            settings={r[0]:json.loads(r[1]) for r in db.execute('SELECT * FROM settings')}
        releases=[self.get_release(rid) for rid in release_ids]
        current=datetime.now(timezone.utc)
        for item in releases:
            item['label']=LABELS.get(item['state'],item['state'])
            item['overdue']=bool(item['state']=='scheduled' and item['scheduled_at'] and parse_time(item['scheduled_at'])<current-timedelta(minutes=10))
            item['metrics']=[]; seen=set()
            for point in metrics:
                if point['release_id']==item['id'] and point['metric'] not in seen:
                    point=dict(point)
                    point['age_days']=(parse_time(point['measured_at'])-parse_time(item['published_at'])).total_seconds()/86400 if item['published_at'] else None
                    item['metrics'].append(point);seen.add(point['metric'])
        return {'materials':materials,'releases':releases,'measurements':metrics,'leads':leads,'attempts':attempts,
            'settings':settings,'timezone':'Europe/Samara','now':now(),
            'counts':{'materials':len(materials),'scheduled':sum(r['state']=='scheduled' for r in releases),
              'published':sum(r['state'] in ('reported','published','verified') for r in releases),
              'attention':sum(r['state'] in ('error','unknown') or r['overdue'] for r in releases),
              'leads':len(leads),'qualified':sum(r['stage'] in ('qualified','won') for r in leads),
              'won':sum(r['stage']=='won' for r in leads),'revenue':sum(r['amount'] or 0 for r in leads if r['stage']=='won')}}

    def seed(self,pack):
        with self.db() as db:
            if db.execute('SELECT 1 FROM materials LIMIT 1').fetchone():return
        mid=self.import_pack(pack,'Автосвет · Авито',str(ROOT/'agency/cases/avtosvet-avito-carousel.md'),'Авто',material_id='avtosvet-avito')
        for item in self.snapshot()['releases']:
            if item['material_id']==mid and item['platform']!='telegram':
                self.configure(item['id'],'volodtarasov')
                self.report(item['id'],note='Владелец подтвердил размещение 20.10.2026; ссылка и точное время требуют сверки.')
            elif item['material_id']==mid:
                self.configure(item['id'],'lazyhim')
