"""Browser integration for the persistent factory; uses the established publisher."""
import asyncio
import re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse

from content_factory import FactoryError,TERMINAL,now,parse_time,public_link


def normal(text):
    return re.sub(r'\s+',' ',str(text)).strip().lower()


def parse_count(raw):
    raw=raw.lower().strip().replace('\u00a0','').replace('\u202f','').replace(' ','')
    match=re.fullmatch(r'(\d+(?:[.,]\d+)?)(тыс\.?|млн\.?|k|m)?',raw)
    if not match:return None
    number=float(match[1].replace(',','.'))
    return round(number*({'k':1000,'тыс':1000,'тыс.':1000,'m':1000000,'млн':1000000,'млн.':1000000}.get(match[2],1)))


class FactoryBrowser:
    def __init__(self,publisher,store,pack_class):
        self.publisher=publisher;self.store=store;self.pack_class=pack_class
        self.message='Готов к работе'

    async def prepare(self,rid):
        item=self.store.current(rid)
        if item['state'] in TERMINAL:raise FactoryError('Этот выпуск уже размещён или требует сверки. Повтор отключён.')
        if item['platform']=='telegram':raise FactoryError('Telegram @'+item['account']+': пока ручной выпуск. Текст доступен в карточке материала.')
        if not item['account']:raise FactoryError('Сначала укажи аккаунт выпуска.')
        pub=self.publisher
        if pub.pack.directory.resolve()!=Path(item['pack']).resolve():
            pub.prepared.clear()
            pub.pack=self.pack_class.read(item['pack'])
        await pub.prepare(item['platform'],item['account'],item['caption'])
        self.store.mark_prepared(rid)
        self.message='Черновик подготовлен: '+item['title']

    async def publish(self,rid,automatic=False):
        item=self.store.current(rid,require_approval=True)
        if item['platform']=='telegram':raise FactoryError('Автоматический выпуск Telegram не подключён.')
        if automatic:
            if rid not in self.store.due():raise FactoryError('Выпуск не разрешён текущим расписанием.')
            await self.prepare(rid)
            if not self.store.setting('autopublish'):raise FactoryError('Выпуск по времени поставлен на паузу.')
        ready=self.publisher.prepared.get(item['platform'])
        if not ready:raise FactoryError('Подготовь черновик в браузере перед отправкой.')
        await self.publisher.publish(item['platform'],item['account'],item['caption'])
        self.message='Отправка завершена: '+item['title']

    async def check_page(self,page,item,url):
        url=public_link(item['platform'],url)
        await page.goto(url,wait_until='domcontentloaded',timeout=30000)
        for _ in range(40):
            if await page.locator('input[type="password"]').count():raise FactoryError('Для сверки нужен вход в аккаунт.')
            if any(p in urlparse(page.url).path for p in ('/login','/challenge','/checkpoint')):
                raise FactoryError('Заверши вход или проверку аккаунта в браузере.')
            scope=page.locator('article')
            if await scope.count()!=1:scope=page.locator('body')
            text=normal(await scope.inner_text())
            fragment=normal(item['caption'])[:160]
            parsed=urlparse(page.url)
            owner=item['account']
            owner_ok=False
            if item['platform']=='threads':owner_ok=parsed.path.lower().startswith('/@'+owner+'/post/')
            elif item['platform']=='instagram':
                owner_ok=await scope.locator(f'a[href="/{owner}/"],a[href="https://www.instagram.com/{owner}/"]').count()>0
            else:owner_ok=parsed.hostname=='t.me' and parsed.path.lower().startswith('/'+owner+'/')
            if owner_ok and fragment and fragment in text:
                stamp=None
                times=await scope.locator('time[datetime]').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("datetime"))')
                if len(set(times))==1:
                    try:stamp=parse_time(times[0]).isoformat()
                    except FactoryError:pass
                self.store.verify(item['id'],url,stamp)
                return
            await page.wait_for_timeout(250)
        raise FactoryError('Не совпали аккаунт и текст поста. Ссылка сохранена, автоматическая сверка не подтверждена.')

    async def verify(self,rid,discover=False):
        item=self.store.get_release(rid)
        if item['state'] not in ('reported','published','verified','unknown'):raise FactoryError('Сначала отметь размещённый пост.')
        page=await self.publisher.context.new_page()
        page.set_default_timeout(10000)
        try:
            if not discover:
                if not item['permalink']:raise FactoryError('Добавь ссылку или нажми «Найти в профиле».')
                await self.check_page(page,item,item['permalink'])
            else:
                if item['platform']=='telegram':raise FactoryError('Для Telegram укажи прямую ссылку на сообщение канала.')
                await self.publisher.verify_account(page,item['platform'],item['account'])
                links=[]
                for _ in range(30):
                    links=await page.locator('a[href*="/p/"],a[href*="/post/"]').evaluate_all('(nodes)=>Array.from(new Set(nodes.map(n=>n.href)))')
                    if links:break
                    await page.wait_for_timeout(250)
                for link in links[:10]:
                    try:
                        public_link(item['platform'],link)
                    except FactoryError:continue
                    try:
                        await self.check_page(page,item,link)
                        break
                    except FactoryError:continue
                else:raise FactoryError('Среди последних постов совпадение не найдено. Укажи прямую ссылку.')
            self.message='Ссылка и текст проверены: '+item['title']+' · '+item['platform']
        finally:await page.close()

    async def collect(self,rid):
        item=self.store.get_release(rid)
        if not item['permalink']:raise FactoryError('Сначала добавь и проверь ссылку на пост.')
        if item['platform']=='telegram':raise FactoryError('Сбор статистики Telegram ещё не подключён. Доступен ручной ввод замеров.')
        page=await self.publisher.context.new_page();page.set_default_timeout(10000)
        try:
            await self.check_page(page,item,item['permalink'])
            pattern=re.compile(r'^(View insights|Post insights|Посмотреть статистику|Статистика публикации)$',re.I)
            button=None
            for _ in range(20):
                candidates=page.get_by_role('button',name=pattern).or_(page.get_by_role('link',name=pattern))
                visible=[candidates.nth(i) for i in range(await candidates.count()) if await candidates.nth(i).is_visible()]
                if len(visible)==1:button=visible[0];break
                text=page.get_by_text(pattern)
                visible=[text.nth(i) for i in range(await text.count()) if await text.nth(i).is_visible()]
                if len(visible)==1:button=visible[0];break
                await page.wait_for_timeout(200)
            if button is None:raise FactoryError('Соцсеть не показала однозначную кнопку статистики. Введи замер вручную.')
            await button.click()
            await page.wait_for_timeout(1500)
            dialogs=page.get_by_role('dialog')
            visible=[dialogs.nth(i) for i in range(await dialogs.count()) if await dialogs.nth(i).is_visible()]
            # Without a scoped statistics panel, numbers from the feed are unsafe.
            if len(visible)!=1:raise FactoryError('Не найдено отдельное окно статистики. Используй ручной ввод.')
            lines=[normal(v) for v in (await visible[0].inner_text()).splitlines() if normal(v)]
            labels={'views':('views','просмотры'),'reach':('accounts reached','охват','охваченные аккаунты'),
                'likes':('likes','отметки "нравится"','нравится'),'comments':('comments','комментарии'),
                'replies':('replies','ответы'),'shares':('shares','поделились','отправки'),
                'saves':('saves','сохранения'),'reposts':('reposts','репосты'),'quotes':('quotes','цитаты')}
            values={}
            for metric,names in labels.items():
                hits=[]
                for index,line in enumerate(lines):
                    if line in names:
                        adjacent=[parse_count(lines[j]) for j in (index-1,index+1) if 0<=j<len(lines)]
                        adjacent=[v for v in adjacent if v is not None]
                        if len(adjacent)==1:hits.append(adjacent[0])
                if len(hits)==1:values[metric]=hits[0]
            if not values:raise FactoryError('Числа не удалось уверенно связать с метриками. Используй ручной ввод.')
            stamp=now()
            for metric,value in values.items():
                self.store.measurement(rid,metric,value,measured_at=stamp,source='Playwright · окно статистики поста')
            self.message=f'Сохранено метрик: {len(values)}. Остальные доступны для ручного ввода.'
        finally:await page.close()

    async def scheduler(self):
        while not self.publisher.stop.is_set():
            self.store.setting('heartbeat',now())
            if not self.publisher.busy:
                jobs=self.store.due()
                if jobs:
                    try:self.publisher.enqueue({'action':'factory_run','release_id':jobs[0]})
                    except Exception:self.message='Очередь занята. Следующая проверка через 20 секунд.'
            try:await asyncio.wait_for(self.publisher.stop.wait(),timeout=20)
            except asyncio.TimeoutError:pass
