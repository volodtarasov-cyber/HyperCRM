"""Local Instagram/Threads carousel publisher driven by a visible Playwright browser.

Run with the vault Python. Login and final submission happen in a dedicated profile;
no passwords, undocumented APIs, browser-cookie imports, or automatic post retries.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image
from playwright.async_api import async_playwright, Error as BrowserError
from content_factory import FactoryStore, FactoryError, TERMINAL, inside
from factory_browser import FactoryBrowser

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PACK = ROOT / '.tools/carousel-out/avtosvet-avito-2026-10-20'
LOCAL = ROOT / '.tools/local/social-publisher'
PLATFORMS = ('instagram', 'threads')
HOME = {'instagram':'https://www.instagram.com/', 'threads':'https://www.threads.com/'}
LIMIT = {'instagram':2200, 'threads':500}
NAMES = {
    'edit': re.compile(r'^(Edit profile|Редактировать профиль)$', re.I),
    'create': re.compile(r'^(Create|New post|New thread|Создать|Новая публикация|Новый тред)$', re.I),
    'post_type': re.compile(r'^(Post|Публикация)$', re.I),
    'next': re.compile(r'^(Next|Далее)$', re.I),
    'crop': re.compile(r'^(Select crop|Crop|Обрезать|Выбрать формат|Выбрать размер и обрезать|Выбрать соотношение сторон)$', re.I),
    'ratio': re.compile(r'^(4:5|Original|Оригинал|Оригинальное)$', re.I),
    'publish_ig': re.compile(r'^(Share|Поделиться|Опубликовать)$', re.I),
    'publish_threads': re.compile(r'^(Post|Publish|Опубликовать)$', re.I),
    'success_ig': re.compile(r'(Your post has been shared|Your post has been published|Публикация опубликована|Ваша публикация опубликована|Публикация размещена)', re.I),
    'success_threads': re.compile(r'^(Posted|Thread posted|Your thread was posted|Your thread has been posted|Опубликовано|Публикация опубликована|Тред опубликован)$', re.I),
}


class WorkflowError(Exception):
    """A visible, actionable stop; never a reason to retry a final post click."""


def normalize_account(raw):
    account = str(raw or '').strip().lstrip('@').lower()
    if not re.fullmatch(r'[a-z0-9_.]{1,30}', account):
        raise WorkflowError('Укажи ник аккаунта: латиница, цифры, точка или подчёркивание, без ссылки.')
    return account


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def browser_proxy(server):
    """Use an explicit local VPN endpoint; never inherit or expose credentials."""
    if not server or server == 'direct':
        return None
    parsed = urlparse(server)
    try:
        valid = (parsed.scheme in ('http','socks5') and parsed.hostname in ('127.0.0.1','localhost','::1')
                 and parsed.port and not parsed.username and not parsed.password
                 and parsed.path in ('','/') and not parsed.query and not parsed.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise WorkflowError('Прокси должен быть локальным: http://127.0.0.1:порт или socks5://127.0.0.1:порт.')
    return {'server':server,'bypass':'localhost,127.0.0.1,[::1]'}


@dataclass(frozen=True)
class Pack:
    directory: Path
    images: tuple[Path, ...]
    width: int
    height: int

    @classmethod
    def read(cls, directory):
        directory = Path(directory).resolve()
        images = tuple(sorted(p for p in directory.glob('slide-*.png') if re.fullmatch(r'slide-\d{2}\.png', p.name)))
        if not 2 <= len(images) <= 10:
            raise WorkflowError('Для этого инструмента нужен комплект из 2–10 PNG slide-01.png, slide-02.png…')
        if [p.name for p in images] != [f'slide-{i:02}.png' for i in range(1,len(images)+1)]:
            raise WorkflowError('В нумерации карточек есть пропуск. Проверь порядок слайдов.')
        size = None
        for path in images:
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                if size is None:
                    size = im.size
                elif size != im.size:
                    raise WorkflowError('Карточки имеют разные размеры.')
        validation = directory/'validation.json'
        if validation.exists() and json.loads(validation.read_text(encoding='utf-8')).get('errors'):
            raise WorkflowError('Комплект не прошёл проверку вёрстки. Сначала пересобери карточки.')
        return cls(directory, images, *size)

    def caption(self, platform):
        path = self.directory/('instagram-caption.txt' if platform=='instagram' else 'threads-post.txt')
        return path.read_text(encoding='utf-8').strip() if path.exists() else ''

    def fingerprint(self, platform, account, caption):
        digest = hashlib.sha256()
        digest.update(json.dumps([platform,account,caption],ensure_ascii=False).encode('utf-8'))
        for path in self.images:
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()


async def unique_visible(locators):
    for locator in locators:
        visible = []
        for i in range(await locator.count()):
            item = locator.nth(i)
            if await item.is_visible():
                visible.append(item)
        if len(visible) == 1:
            return visible[0]
        if len(visible) > 1:
            raise WorkflowError('В интерфейсе несколько подходящих элементов. Остановился, чтобы не нажать не ту кнопку.')
    return None


async def control(root, pattern):
    return await unique_visible([root.get_by_role('button',name=pattern),root.get_by_role('link',name=pattern)])


async def caption_field(root, platform):
    if platform == 'instagram':
        named = root.get_by_role('textbox',name=re.compile(r'(Write a caption|Напишите подпись|Добавьте подпись|Подпись)',re.I))
    else:
        named = root.get_by_role('textbox',name=re.compile(r'(new post|new thread|empty text|новый тред|текст|публикаци)',re.I))
    return await unique_visible([named,root.locator('textarea,[contenteditable="true"][role="textbox"]'),root.locator('[contenteditable="true"]')])


class Publisher:
    def __init__(self, pack, state_dir=LOCAL):
        self.pack = pack
        self.local = Path(state_dir)
        self.local.mkdir(parents=True,exist_ok=True)
        self.lock = threading.RLock()
        self.busy = ''
        self.pages = {}
        self.prepared = {}
        self.context = None
        self.loop = None
        self.queue = None
        self.stop = None
        self.proxy = None
        self.factory = None
        self.factory_browser = None
        self.saved = self.read_json('accounts.json',{})
        self.ledger = self.read_json('receipts.json',{})
        self.platforms = {p:{'phase':'idle','message':'Войди в аккаунт, затем подготовь публикацию.',
                            'account':self.saved.get(p,''),'caption':pack.caption(p),
                            'verified':'','screenshot':'','permalink':''} for p in PLATFORMS}

    def read_json(self, name, default):
        path = self.local/name
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

    def status(self):
        with self.lock:
            return {'pack_name':self.pack.directory.name,'count':len(self.pack.images),
                    'width':self.pack.width,'height':self.pack.height,'files':[p.name for p in self.pack.images],
                    'busy':self.busy,'proxy':self.proxy['server'] if self.proxy else '',
                    'platforms':json.loads(json.dumps(self.platforms))}

    def update(self, platform, **changes):
        with self.lock:
            self.platforms[platform].update(changes)

    def enqueue(self, data):
        action = data.get('action')
        factory_job = action in ('factory_prepare','factory_publish','factory_run','factory_verify','factory_discover','factory_collect')
        if action not in ('login','inspect','prepare','publish','shutdown') and not factory_job:
            raise WorkflowError('Неизвестное действие.')
        if factory_job:
            if not self.factory:raise WorkflowError('Очередь ещё не запущена.')
            item=self.factory.get_release(data.get('release_id'))
            data['platform']=item['platform']
        platform = data.get('platform')
        if action != 'shutdown' and platform not in PLATFORMS and not factory_job:
            raise WorkflowError('Выбери Instagram или Threads.')
        if action in ('prepare','publish'):
            data['account'] = normalize_account(data.get('account'))
            data['caption'] = str(data.get('caption','')).strip()
            if not data['caption'] or len(data['caption']) > LIMIT[platform]:
                raise WorkflowError(f'Подпись должна содержать 1–{LIMIT[platform]} символов.')
        with self.lock:
            if self.busy:
                raise WorkflowError('Предыдущее действие ещё выполняется.')
            if action == 'publish':
                ready = self.prepared.get(platform)
                if not ready or self.platforms[platform]['phase'] != 'prepared':
                    raise WorkflowError('Сначала подготовь пост и проверь черновик.')
                if ready['account'] != data['account'] or ready['caption'] != data['caption']:
                    raise WorkflowError('Аккаунт или подпись изменились. Подготовь черновик заново.')
            self.busy = f'{platform or ""}: {action}'
            self.loop.call_soon_threadsafe(self.queue.put_nowait, data)

    async def page(self, platform):
        page = self.pages.get(platform)
        if page is None or page.is_closed():
            page = await self.context.new_page()
            page.set_default_timeout(12000)
            self.pages[platform] = page
        return page

    async def screenshot(self, platform, page):
        # No traces, storage-state dumps, or screenshots of password-entry pages.
        if await page.locator('input[type="password"]').count():
            return
        await page.screenshot(path=str(self.local/f'{platform}-draft.png'))
        self.update(platform,screenshot=str(time.time_ns()))

    async def inspect(self, platform):
        """Inspect controls without navigation, field values, cookies or page dumps."""
        page = await self.page(platform)
        address = urlparse(page.url)
        details = await page.evaluate('''()=>({
          passwordFields:document.querySelectorAll('input[type="password"]').length,
          dialogs:document.querySelectorAll('[role="dialog"]').length,
          uploaders:Array.from(document.querySelectorAll('input[type="file"]'),e=>({accept:e.accept,multiple:e.multiple,inDialog:!!e.closest('[role="dialog"]')})),
          controls:Array.from(new Set([...document.querySelectorAll('[role="dialog"] button,[role="dialog"] [role="button"],[role="dialog"] input,[role="dialog"] textarea,[role="dialog"] [contenteditable="true"],[role="dialog"] svg[aria-label]'),...document.querySelectorAll('button,[role="button"],input,textarea,[contenteditable="true"],svg[aria-label]')]))
            .filter(e=>e.getClientRects().length).slice(0,80).map(e=>({
              tag:e.tagName,role:e.getAttribute('role'),type:e.getAttribute('type'),
              aria:e.getAttribute('aria-label'),accept:e.getAttribute('accept'),multiple:e.hasAttribute('multiple'),
              parents:e.tagName.toLowerCase()==='svg'?Array.from((function*(n){for(let i=0;n&&i<4;i++,n=n.parentElement)yield n})(e.parentElement),n=>({tag:n.tagName,role:n.getAttribute('role'),aria:n.getAttribute('aria-label'),tabindex:n.getAttribute('tabindex'),text:(n.innerText||'').slice(0,80)})):undefined,
              label:(e.getAttribute('aria-label')||e.getAttribute('placeholder')||
                ((e.tagName==='BUTTON'||e.getAttribute('role')==='button')?e.innerText:'')||'').slice(0,160)
            }))
        })''')
        details.update(page=address.scheme+'://'+address.netloc+address.path,at=utc_now())
        atomic_json(self.local/f'{platform}-inspection.json',details)
        await self.screenshot(platform,page)

    async def verify_account(self, page, platform, account):
        profile = HOME[platform]+('@' if platform=='threads' else '')+account+'/'
        await page.goto(profile,wait_until='domcontentloaded',timeout=25000)
        expected_host = {'www.instagram.com','instagram.com'} if platform=='instagram' else {'www.threads.com','threads.com','www.threads.net','threads.net'}
        parsed = urlparse(page.url)
        if parsed.hostname not in expected_host or any(part in parsed.path for part in ('/login','/challenge','/checkpoint')):
            raise WorkflowError('Нужен вход или проверка аккаунта. Заверши её вручную в браузере и нажми «Подготовить» снова.')
        if parsed.path.rstrip('/').lower() != ('/@' if platform=='threads' else '/')+account:
            raise WorkflowError('Соцсеть перенаправила на другую страницу. Проверь вход и выбранный ник.')
        for _ in range(24):
            if await control(page,NAMES['edit']):
                self.update(platform,verified=account)
                return
            await page.wait_for_timeout(250)
        raise WorkflowError(f'Не подтвердил, что открыт твой аккаунт @{account}: нет кнопки редактирования профиля. Проверь ник и вход.')

    async def dialog(self, page):
        for _ in range(80):
            result = await unique_visible([page.get_by_role('dialog')])
            if result is not None:
                return result
            await page.wait_for_timeout(100)
        raise WorkflowError('Не нашёл окно создания поста. Интерфейс мог измениться; проверь открытый браузер.')

    async def open_composer(self, page, platform):
        if await page.get_by_role('dialog').count():
            raise WorkflowError('В браузере уже открыто окно. Закрой или отмени его вручную и повтори подготовку.')
        # Threads exposes both its navigation entry and a floating Create button.
        # Prefer the named navigation entry before considering generic controls.
        button = await control(page,re.compile(r'^(New post|New thread|Новая публикация|Новый тред)$',re.I)) if platform=='threads' else None
        if button is None:
            button = await control(page,NAMES['create'])
        if button is None:
            # Some navigation controls expose only the SVG accessible label.
            names = ['Create','New post','Создать','Новая публикация']
            selectors = [f'button:has(svg[aria-label="{name}"]),a:has(svg[aria-label="{name}"]),[role="button"]:has(svg[aria-label="{name}"])' for name in names]
            button = await unique_visible([page.locator(css) for css in selectors])
        if button is None:
            raise WorkflowError('Не нашёл кнопку создания поста. Нужна настройка под текущий интерфейс.')
        await button.click()
        if platform=='instagram':
            for _ in range(12):
                if await page.get_by_role('dialog').count():
                    break
                post_type = await control(page,NAMES['post_type'])
                if post_type is None:
                    # Instagram's Create menu uses clickable divs without roles.
                    post_type = await unique_visible([page.get_by_text(NAMES['post_type'])])
                if post_type:
                    await post_type.click()
                    break
                await page.wait_for_timeout(200)
        for _ in range(24):
            if await page.get_by_role('dialog').count():
                return await self.dialog(page)
            await page.wait_for_timeout(250)
        raise WorkflowError('Окно создания поста не открылось.')

    async def attach(self, page, dialog):
        select = await control(dialog,re.compile(r'^(Select from computer|Выбрать на компьютере)$',re.I))
        if select:
            async with page.expect_file_chooser(timeout=12000) as pending:
                await select.click()
            chooser = await pending.value
            if not chooser.is_multiple():
                raise WorkflowError('Загрузчик не поддерживает несколько файлов. Проверь режим карусели в браузере.')
            upload = chooser.element
            await self.set_files(upload)
            return
        files = dialog.locator('input[type="file"]')
        if not await files.count():
            files = page.locator('input[type="file"]')
        candidates = []
        for i in range(await files.count()):
            item = files.nth(i)
            accept = (await item.get_attribute('accept') or '').lower()
            if not accept or 'image' in accept or '.jpg' in accept or '.png' in accept:
                candidates.append(item)
        if len(candidates)!=1:
            raise WorkflowError('Не нашёл однозначный загрузчик изображений. Остановился до отправки файлов.')
        upload = await candidates[0].element_handle()
        if await upload.get_attribute('multiple') is None:
            raise WorkflowError('Загрузчик не поддерживает несколько файлов. Проверь режим карусели в браузере.')
        await self.set_files(upload)

    async def set_files(self, upload):
        # React clears input.files immediately after accepting the images. Capture
        # the actual change event before its handler resets or removes the input.
        await upload.evaluate('''e=>{e.__publisherFiles=null;e.addEventListener('change',()=>{
          e.__publisherFiles=Array.from(e.files||[],f=>f.name);
        },{capture:true,once:true})}''')
        await upload.set_input_files([str(p) for p in self.pack.images])
        names = await upload.evaluate('(e)=>e.__publisherFiles')
        if names != [p.name for p in self.pack.images]:
            raise WorkflowError('Браузер принял другой набор или порядок файлов.')

    async def instagram_caption(self, page):
        dialog = await self.dialog(page)
        crop = None
        for _ in range(40):
            crop = await unique_visible([dialog.locator('svg[aria-label="Выбрать размер и обрезать"],svg[aria-label="Select crop"],svg[aria-label="Выбрать формат"]')])
            if crop is None:
                crop = await control(dialog,NAMES['crop'])
            if crop is None:
                crop = await unique_visible([dialog.locator('button:has(svg[aria-label="Select crop"]),[role="button"]:has(svg[aria-label="Select crop"]),button:has(svg[aria-label="Выбрать формат"])')])
            if crop:
                break
            await page.wait_for_timeout(250)
        if crop is None:
            raise WorkflowError('Не подтвердил формат карусели. Проверь обрезку в браузере; автоматическую отправку не включаю.')
        await crop.click()
        ratio = None
        preferred = [re.compile(r'^4:5$'),re.compile(r'^(Original|Оригинал|Оригинальное)$',re.I)] if self.pack.width/self.pack.height==0.8 else [re.compile(r'^(Original|Оригинал|Оригинальное)$',re.I)]
        for pattern in preferred:
            ratio = await control(page,pattern)
            if ratio is None:
                ratio = await unique_visible([page.get_by_text(pattern)])
            if ratio:
                break
        if ratio is None:
            raise WorkflowError('Не нашёл исходный формат / 4:5. Проверь меню обрезки.')
        await ratio.click()
        for _ in range(3):
            dialog = await self.dialog(page)
            field = await caption_field(dialog,'instagram')
            if field:
                return field
            next_button = await control(dialog,NAMES['next'])
            if next_button is None:
                raise WorkflowError('Не нашёл следующий шаг создания Instagram-поста.')
            await next_button.click()
            await page.wait_for_timeout(300)
        raise WorkflowError('Не дошёл до поля подписи в Instagram.')

    async def signature(self, page):
        dialog = await self.dialog(page)
        return await dialog.evaluate('''d=>JSON.stringify({
          text:Array.from(d.querySelectorAll('textarea,[contenteditable="true"]'),e=>e.value??e.innerText),
          images:Array.from(d.querySelectorAll('img'),e=>({src:e.currentSrc||e.src,style:e.getAttribute('style')})),
          files:Array.from(d.querySelectorAll('input[type="file"]'),e=>Array.from(e.files||[],f=>f.name))
        })''')

    async def prepare(self, platform, account, caption):
        if self.factory:
            rid=self.factory.find_release(self.pack.directory,platform,account)
            if rid and self.factory.get_release(rid)['state'] in TERMINAL:
                raise WorkflowError('Этот материал уже размещён или требует сверки. Повторная подготовка заблокирована.')
        self.update(platform,phase='working',message='Проверяю аккаунт и открываю создание поста…',verified='',permalink='')
        self.prepared.pop(platform,None)
        key = self.pack.fingerprint(platform,account,caption)
        if key in self.ledger:
            raise WorkflowError('Для этого аккаунта и комплекта уже была попытка отправки. Проверь профиль; повторная публикация заблокирована.')
        page = await self.page(platform)
        await page.bring_to_front()
        await self.verify_account(page,platform,account)
        baseline = await page.locator('a[href*="/p/"],a[href*="/post/"]').evaluate_all('(a)=>a.map(x=>x.href)')
        dialog = await self.open_composer(page,platform)
        self.update(platform,message=f'Загружаю {len(self.pack.images)} карточек по порядку…')
        await self.attach(page,dialog)
        if platform=='instagram':
            field = await self.instagram_caption(page)
        else:
            field = await caption_field(await self.dialog(page),'threads')
        if field is None:
            raise WorkflowError('Не нашёл поле текста публикации.')
        await field.fill(caption)
        for _ in range(80):
            dialog = await self.dialog(page)
            button = await control(dialog,NAMES['publish_ig' if platform=='instagram' else 'publish_threads'])
            busy = await dialog.locator('[role="progressbar"]').count()
            if button and await button.is_enabled() and not busy:
                break
            await page.wait_for_timeout(250)
        else:
            raise WorkflowError('Загрузка не закончилась или кнопка публикации недоступна. Проверь браузер.')
        await page.wait_for_timeout(500)
        signature = await self.signature(page)
        self.prepared[platform]={'account':account,'caption':caption,'key':key,'signature':signature,'baseline':baseline}
        self.saved[platform]=account
        atomic_json(self.local/'accounts.json',self.saved)
        self.update(platform,phase='prepared',message='Черновик готов. Проверь текст, порядок карточек и обрезку. Кнопка «Опубликовать» отправит пост.',account=account,caption=caption)
        await self.screenshot(platform,page)

    async def publish(self, platform, account, caption):
        ready = self.prepared.get(platform)
        if ready is None or ready['account']!=account or ready['caption']!=caption:
            raise WorkflowError('Нет подготовленного черновика для этого аккаунта и текста.')
        if ready['key'] != self.pack.fingerprint(platform,account,caption):
            raise WorkflowError('Карточки изменились после подготовки. Подготовь черновик заново.')
        if ready['key'] in self.ledger:
            raise WorkflowError('Попытка отправки уже зафиксирована. Повторный клик заблокирован.')
        page = await self.page(platform)
        if ready['signature'] != await self.signature(page):
            raise WorkflowError('Черновик в браузере изменился. Подготовь его заново.')
        # Verify current session in a separate tab, keeping the composed post intact.
        check = await self.context.new_page()
        try:
            await self.verify_account(check,platform,account)
        finally:
            await check.close()
        if ready['signature'] != await self.signature(page):
            raise WorkflowError('Черновик изменился во время проверки аккаунта. Подготовь его заново.')
        dialog = await self.dialog(page)
        button = await control(dialog,NAMES['publish_ig' if platform=='instagram' else 'publish_threads'])
        if button is None or not await button.is_enabled():
            raise WorkflowError('Кнопка отправки недоступна.')
        factory_rid=self.factory.find_release(self.pack.directory,platform,account) if self.factory else None
        if self.factory and not factory_rid:
            raise WorkflowError('Импортируй комплект в очередь завода и одобри выпуск перед отправкой.')
        if factory_rid:
            release=self.factory.current(factory_rid,require_approval=True)
            if release['caption']!=caption:
                raise WorkflowError('Текст не совпадает с одобренной версией завода.')
            if release['auto'] and not self.factory.setting('autopublish'):
                raise WorkflowError('Выпуск по времени поставлен на паузу.')
            self.factory.begin_send(factory_rid)
        self.ledger[ready['key']]={'platform':platform,'account':account,'state':'submitting','at':utc_now()}
        atomic_json(self.local/'receipts.json',self.ledger)
        self.update(platform,phase='submitting',message='Отправляю пост. Повторный клик отключён.')
        try:
            await button.click(timeout=12000)  # Deliberately one final click, never retry.
            pattern = NAMES['success_ig' if platform=='instagram' else 'success_threads']
            success = False
            for _ in range(100):
                if await unique_visible([page.get_by_text(pattern)]):
                    success = True
                    break
                await page.wait_for_timeout(300)
            if not success:
                raise WorkflowError('Соцсеть не показала подтверждение. Проверь профиль вручную; повторная отправка заблокирована.')
            link = ''
            links = await page.locator('a[href*="/p/"],a[href*="/post/"]').evaluate_all('(a)=>a.map(x=>x.href)')
            fresh = [url for url in links if url not in ready['baseline'] and urlparse(url).hostname in {'www.instagram.com','instagram.com','www.threads.com','threads.com','www.threads.net','threads.net'}]
            if len(set(fresh))==1:
                link=fresh[0]
            self.ledger[ready['key']].update(state='published',permalink=link,confirmed_at=utc_now())
            atomic_json(self.local/'receipts.json',self.ledger)
            if factory_rid:self.factory.finish_send(factory_rid,'published',link)
            self.update(platform,phase='published',message='Соцсеть подтвердила публикацию.'+('' if link else ' Прямая ссылка не показана — открой профиль.'),permalink=link)
            self.prepared.pop(platform,None)
            try:
                await self.screenshot(platform,page)
            except (BrowserError,OSError):
                pass  # A failed screenshot must not erase the platform's confirmation.
        except Exception:
            if factory_rid:self.factory.finish_send(factory_rid,'unknown',detail='Нет надёжного подтверждения отправки. Сверь профиль.')
            self.ledger[ready['key']].update(state='unknown',checked_at=utc_now())
            atomic_json(self.local/'receipts.json',self.ledger)
            self.update(platform,phase='unknown',message='Отправка могла произойти. Проверь профиль вручную. Автоматического повтора не будет.')
            self.prepared.pop(platform,None)
            raise

    async def worker(self):
        while not self.stop.is_set():
            data=await self.queue.get()
            platform=data.get('platform')
            try:
                if data['action']=='shutdown':
                    self.stop.set()
                elif data['action'].startswith('factory_'):
                    rid=int(data['release_id']);action=data['action']
                    self.factory_browser.message='Выполняется действие с выпуском…'
                    if action=='factory_prepare':await self.factory_browser.prepare(rid)
                    elif action in ('factory_publish','factory_run'):await self.factory_browser.publish(rid,automatic=action=='factory_run')
                    elif action in ('factory_verify','factory_discover'):await self.factory_browser.verify(rid,discover=action=='factory_discover')
                    elif action=='factory_collect':await self.factory_browser.collect(rid)
                elif data['action']=='login':
                    self.prepared.pop(platform,None)
                    page=await self.page(platform)
                    await page.goto(HOME[platform],wait_until='domcontentloaded',timeout=25000)
                    await page.bring_to_front()
                    self.update(platform,phase='login',message='Войди в нужный аккаунт в окне браузера. Затем вернись в панель и нажми «Подготовить».')
                elif data['action']=='inspect':
                    await self.inspect(platform)
                elif data['action']=='prepare':
                    await self.prepare(platform,data['account'],data['caption'])
                else:
                    await self.publish(platform,data['account'],data['caption'])
            except Exception as exc:
                # Do not log page HTML, credentials, request headers or cookies.
                message='Действие остановлено: ошибка браузера или локальных файлов.'
                if isinstance(exc,(WorkflowError,FactoryError)):message=str(exc)
                if platform in self.platforms:
                    phase=self.platforms[platform]['phase']
                    message='Действие остановлено: ошибка браузера или локальных файлов. Проверь открытую вкладку.'
                    if isinstance(exc,(WorkflowError,FactoryError)):
                        message=str(exc)
                    elif isinstance(exc,BrowserError):
                        code=re.search(r'net::[A-Z_]+|Timeout \d+ms exceeded',str(exc))
                        if code:
                            route = self.proxy['server'] if self.proxy else 'системное подключение'
                            message=f'Браузер не загрузил страницу: {code.group(0)}. Маршрут: {route}. Проверь VPN и локальный порт прокси, затем нажми «Открыть / войти» снова.'
                    self.update(platform,phase='unknown' if phase=='unknown' else 'error',message=message)
                    self.prepared.pop(platform,None)
                if data['action'].startswith('factory_'):
                    self.factory_browser.message=message
                    if data['action'] not in ('factory_verify','factory_discover','factory_collect'):
                        self.factory.error(int(data['release_id']),message)
                print(f'Action stopped: {data["action"]} / {type(exc).__name__}',flush=True)
            finally:
                with self.lock:
                    self.busy=''
                self.queue.task_done()


def make_handler(publisher, token, port):
    origin=f'http://127.0.0.1:{port}'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def respond(self,status,body,content_type='application/json; charset=utf-8'):
            if isinstance(body,dict):
                body=json.dumps(body,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            policy="frame-ancestors 'none'"
            if urlparse(self.path).path.startswith('/factory-file/') and content_type.startswith('text/html'):
                policy+="; sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"
            self.send_header('Content-Security-Policy',policy)
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def host_ok(self):
            return self.headers.get('Host')==f'127.0.0.1:{port}'

        def do_GET(self):
            if not self.host_ok():
                return self.respond(403,{'error':'Forbidden host'})
            path=unquote(urlparse(self.path).path)
            if path=='/':
                template=Path(__file__).with_name('factory_ui.html').read_text(encoding='utf-8') if publisher.factory else Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
                return self.respond(200,template.replace('__TOKEN__',json.dumps(token)).encode('utf-8'),'text/html; charset=utf-8')
            if path=='/publisher':
                template=Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
                return self.respond(200,template.replace('__TOKEN__',json.dumps(token)).encode('utf-8'),'text/html; charset=utf-8')
            if path=='/api/factory' and publisher.factory:
                state=publisher.factory.snapshot()
                state['browser']={'busy':publisher.busy,'message':publisher.factory_browser.message,'proxy':publisher.proxy['server'] if publisher.proxy else ''}
                state['packs']=[p.name for p in sorted(publisher.factory.pack_root.iterdir()) if p.is_dir() and (p/'instagram-caption.txt').is_file()]
                return self.respond(200,state)
            if path.startswith('/factory-brief/') and publisher.factory:
                try:body=publisher.factory.brief(path.rsplit('/',1)[-1]).encode('utf-8')
                except FactoryError as exc:return self.respond(404,{'error':str(exc)})
                return self.respond(200,body,'text/plain; charset=utf-8')
            if path.startswith('/factory-file/') and publisher.factory:
                try:
                    parts=path.split('/')
                    if len(parts)!=4:raise FactoryError('Неверный путь.')
                    release=publisher.factory.get_release(int(parts[2]));name=parts[3]
                    allowed={p['name'] for p in release['assets']}|{'preview.html','profile-grid-preview.png','contact-sheet.jpg'}
                    if name not in allowed:raise FactoryError('Файл недоступен.')
                    file=inside(Path(release['pack'])/name,[publisher.factory.pack_root])
                    kind='text/html; charset=utf-8' if file.suffix=='.html' else 'image/jpeg' if file.suffix=='.jpg' else 'image/png'
                    return self.respond(200,file.read_bytes(),kind)
                except (FactoryError,TypeError,ValueError,OSError):return self.respond(404,{'error':'Файл не найден.'})
            if path=='/api/state':
                return self.respond(200,publisher.status())
            if path.startswith('/pack/'):
                name=path.removeprefix('/pack/')
                allowed={p.name for p in publisher.pack.images}|{'preview.html','profile-grid-preview.png'}
                if name not in allowed:
                    return self.respond(404,{'error':'Not found'})
                file=publisher.pack.directory/name
            elif path in ('/shot/instagram.png','/shot/threads.png'):
                file=publisher.local/(Path(path).stem+'-draft.png')
            else:
                return self.respond(404,{'error':'Not found'})
            if not file.is_file():
                return self.respond(404,{'error':'Not found'})
            kind='text/html; charset=utf-8' if file.suffix=='.html' else 'image/png'
            return self.respond(200,file.read_bytes(),kind)

        def do_POST(self):
            if not self.host_ok() or self.headers.get('Origin')!=origin or not secrets.compare_digest(self.headers.get('X-Local-Token',''),token):
                return self.respond(403,{'error':'Запрос разрешён только из локальной панели.'})
            if self.path not in ('/api/action','/api/factory-action'):
                return self.respond(404,{'error':'Not found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<20000:
                    raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):
                    raise ValueError('Expected an object')
                if self.path=='/api/factory-action':
                    self.factory_action(data)
                else:publisher.enqueue(data)
            except (WorkflowError,FactoryError) as exc:
                return self.respond(409,{'error':str(exc)})
            except (ValueError,TypeError):
                return self.respond(400,{'error':'Неверный формат запроса.'})
            return self.respond(202,{'queued':True})

        def factory_action(self,data):
            store=publisher.factory
            if not store:raise WorkflowError('Завод не запущен.')
            action=data.get('action');rid=int(data['release_id']) if data.get('release_id') else None
            if action in ('factory_prepare','factory_publish','factory_verify','factory_discover','factory_collect'):
                publisher.enqueue(data);return
            if publisher.busy and action not in ('measurement','lead','autopublish'):
                raise WorkflowError('Дождись завершения действия в браузере.')
            if action=='source':store.source(data.get('title',''),data.get('source',''),data.get('niche',''))
            elif action=='import':
                directory=inside(store.pack_root/str(data.get('pack','')),[store.pack_root])
                mid=data.get('material_id') or None
                if mid:
                    with store.db() as db:existing=db.execute('SELECT * FROM materials WHERE id=?',(mid,)).fetchone()
                    if not existing:raise FactoryError('Материал не найден.')
                    store.import_pack(directory,existing['title'],existing['source'],existing['niche'],mid)
                else:store.import_pack(directory,data.get('title') or directory.name,data.get('source',''),data.get('niche',''))
            elif action=='account':store.configure(rid,data.get('account'))
            elif action=='caption':store.edit_caption(rid,data.get('caption'))
            elif action=='approve':store.approve(rid)
            elif action=='schedule':
                if type(data.get('auto',False)) is not bool:raise FactoryError('Укажи режим выпуска.')
                store.schedule(rid,data.get('scheduled_at'),data.get('auto',False))
            elif action=='pause':store.pause(rid)
            elif action=='report':store.report(rid,data.get('permalink',''),data.get('published_at'))
            elif action=='measurement':store.measurement(rid,data.get('metric'),data.get('value'),data.get('status','ok'),data.get('measured_at'),data.get('source','Ручной ввод'))
            elif action=='lead':store.lead(rid,data.get('stage'),data.get('reference'),data.get('amount'),data.get('note',''))
            elif action=='autopublish':
                if type(data.get('enabled')) is not bool:raise FactoryError('Нужно включить или выключить режим.')
                store.setting('autopublish',data['enabled'])
            else:raise WorkflowError('Неизвестное действие завода.')
    return Handler


async def serve(args):
    pack=Pack.read(args.pack)
    if args.check:
        print(json.dumps({'status':'pack_valid','cards':len(pack.images),'size':[pack.width,pack.height],
                          'captions':{p:len(pack.caption(p)) for p in PLATFORMS}},ensure_ascii=False))
        return
    publisher=Publisher(pack)
    publisher.factory=FactoryStore(recover=True)
    publisher.factory.seed(args.pack)
    publisher.factory_browser=FactoryBrowser(publisher,publisher.factory,Pack)
    network=publisher.read_json('network.json',{})
    publisher.proxy=browser_proxy(args.proxy if args.proxy is not None else network.get('proxy',''))
    publisher.loop=asyncio.get_running_loop()
    publisher.queue=asyncio.Queue()
    publisher.stop=asyncio.Event()
    token=secrets.token_urlsafe(32)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(publisher,token,args.port))
    server.daemon_threads=True
    threading.Thread(target=server.serve_forever,daemon=True).start()
    worker=None;scheduler=None
    try:
        async with async_playwright() as driver:
            publisher.context=await driver.chromium.launch_persistent_context(
                str(LOCAL/'chromium'),channel='chromium',headless=args.headless,
                proxy=publisher.proxy,
                viewport={'width':1440,'height':1000},locale='ru-RU',timezone_id='Europe/Samara')
            publisher.context.on('close',lambda _:publisher.stop.set())
            dashboard=publisher.context.pages[0] if publisher.context.pages else await publisher.context.new_page()
            await dashboard.goto(f'http://127.0.0.1:{args.port}/')
            worker=asyncio.create_task(publisher.worker())
            scheduler=asyncio.create_task(publisher.factory_browser.scheduler())
            atomic_json(LOCAL/'running.json',{'url':f'http://127.0.0.1:{args.port}/','started':utc_now()})
            print(f'READY http://127.0.0.1:{args.port}/',flush=True)
            if args.proxy is not None:
                atomic_json(LOCAL/'network.json',{'proxy':publisher.proxy['server'] if publisher.proxy else ''})
            await publisher.stop.wait()
            await publisher.context.close()
    finally:
        if worker:
            worker.cancel()
        if scheduler:scheduler.cancel()
        server.shutdown()
        server.server_close()
        (LOCAL/'running.json').unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,default=DEFAULT_PACK)
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--check',action='store_true',help='Validate the pack without opening a browser')
    parser.add_argument('--headless',action='store_true',help='For local automated checks; normal use opens a visible browser')
    parser.add_argument('--proxy',help='Local VPN proxy URL, saved for later launches; direct resets it')
    args=parser.parse_args()
    try:
        asyncio.run(serve(args))
    except KeyboardInterrupt:
        pass
    except (OSError,WorkflowError,FactoryError,BrowserError) as exc:
        print(f'Не удалось запустить: {type(exc).__name__}. Проверь комплект, порт {args.port} и наличие Chromium.')
        raise SystemExit(1)


if __name__=='__main__':
    main()
