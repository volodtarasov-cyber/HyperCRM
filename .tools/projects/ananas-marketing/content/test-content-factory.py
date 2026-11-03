"""Behavioral tests for persistence, dispatch boundaries and the dashboard."""
import asyncio
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import requests
from PIL import Image
from playwright.async_api import async_playwright

from content_factory import FactoryStore,FactoryError,public_link,now,ROOT
from factory_browser import FactoryBrowser,parse_count

spec=importlib.util.spec_from_file_location('publisher_tests',Path(__file__).with_name('test-social-publisher.py'))
FIXTURES=importlib.util.module_from_spec(spec);spec.loader.exec_module(FIXTURES)
PUB=FIXTURES.MODULE


def make_pack(root):
    pack=root/'packs'/'sample';pack.mkdir(parents=True)
    for i in range(1,4):Image.new('RGB',(108,135),(i*40,45,65)).save(pack/f'slide-{i:02}.png')
    for filename in ['instagram-caption.txt','threads-post.txt','telegram-post.txt']:
        (pack/filename).write_text('Подтверждённый кейс. Без выдуманных продаж.',encoding='utf-8')
    (pack/'validation.json').write_text('{"errors":[]}',encoding='utf-8')
    (pack/'preview.html').write_text('<html><meta charset="utf-8"><h1>Case preview</h1></html>',encoding='utf-8')
    Image.new('RGB',(130,170)).save(pack/'profile-grid-preview.png')
    return pack


class Storage(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.root=Path(self.tmp.name)
        self.pack=make_pack(self.root)
        self.store=FactoryStore(self.root/'state',self.root/'packs',[self.root])
        self.mid=self.store.import_pack(self.pack,'Реальный кейс',niche='Авто')
        self.rid=self.store.snapshot()['releases'][0]['id']
        self.store.configure(self.rid,'correct')

    def tearDown(self):self.tmp.cleanup()

    def test_queue_persists_and_duplicate_import_does_not_reset_approval(self):
        self.store.approve(self.rid)
        self.store.import_pack(self.pack,'Реальный кейс')
        again=FactoryStore(self.root/'state',self.root/'packs',[self.root])
        self.assertEqual(len(again.snapshot()['materials']),1)
        self.assertEqual(len(again.snapshot()['releases']),3)
        self.assertEqual(again.get_release(self.rid)['state'],'approved')

    def test_edit_revokes_only_this_release_and_asset_change_blocks_send(self):
        self.store.approve(self.rid)
        self.store.edit_caption(self.rid,'Изменённый текст')
        self.assertEqual(self.store.get_release(self.rid)['approval'],'')
        self.assertEqual(self.store.snapshot()['releases'][1]['caption'],'Подтверждённый кейс. Без выдуманных продаж.')
        with self.assertRaises(FactoryError):self.store.begin_send(self.rid)
        self.store.approve(self.rid)
        Image.new('RGB',(108,135),'red').save(self.pack/'slide-01.png')
        with self.assertRaises(FactoryError):self.store.begin_send(self.rid)
        self.store.import_pack(self.pack,'Реальный кейс')
        self.assertEqual(self.store.get_release(self.rid)['state'],'draft')

    def test_reported_post_never_reenters_queue_even_with_new_text(self):
        self.store.report(self.rid,'https://www.instagram.com/p/example/')
        for operation in [lambda:self.store.approve(self.rid),lambda:self.store.pause(self.rid),lambda:self.store.edit_caption(self.rid,'Другой текст')]:
            with self.assertRaises(FactoryError):operation()
        (self.pack/'instagram-caption.txt').write_text('Новая подпись',encoding='utf-8')
        self.store.import_pack(self.pack,'Реальный кейс')
        self.assertEqual(self.store.get_release(self.rid)['state'],'reported')

    def test_verified_post_can_get_missing_time_without_losing_verification(self):
        link='https://www.instagram.com/correct/p/example/'
        self.store.report(self.rid,link)
        self.store.verify(self.rid,link)
        stamp=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        self.store.report(self.rid,link,stamp)
        self.assertEqual(self.store.get_release(self.rid)['state'],'verified')
        self.assertEqual(self.store.get_release(self.rid)['published_at'],stamp)
        self.store.report(self.rid,'https://www.instagram.com/p/another/',stamp)
        self.assertEqual(self.store.get_release(self.rid)['state'],'reported')

    def test_transaction_reserves_one_send_and_restart_blocks_uncertain_result(self):
        self.store.approve(self.rid)
        def reserve(_):
            try:return self.store.begin_send(self.rid)
            except FactoryError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(reserve,range(2)))
        self.assertEqual(sum(r is not None for r in result),1)
        reader=FactoryStore(self.root/'state',self.root/'packs',[self.root])
        self.assertEqual(reader.get_release(self.rid)['state'],'submitting')
        restarted=FactoryStore(self.root/'state',self.root/'packs',[self.root],recover=True)
        self.assertEqual(restarted.get_release(self.rid)['state'],'unknown')
        with self.assertRaises(FactoryError):restarted.begin_send(self.rid)
        self.assertEqual(restarted.snapshot()['attempts'][0]['state'],'unknown')

    def test_schedule_is_aware_paused_by_default_and_skips_missed_days(self):
        self.store.approve(self.rid)
        with self.assertRaises(FactoryError):self.store.schedule(self.rid,'2026-10-21T12:00',True)
        future=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        self.store.schedule(self.rid,future,True)
        self.assertEqual(self.store.due(),[])
        self.store.setting('autopublish',True)
        with self.store.db() as db:db.execute('UPDATE releases SET scheduled_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),self.rid))
        self.assertEqual(self.store.due(),[self.rid])
        with self.store.db() as db:db.execute('UPDATE releases SET scheduled_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),self.rid))
        self.assertEqual(self.store.due(),[])
        self.assertTrue(self.store.snapshot()['releases'][0]['overdue'])

    def test_metrics_preserve_unknown_zero_age_and_history_without_summing(self):
        published=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
        self.store.report(self.rid,'https://www.instagram.com/p/example/',published)
        self.store.measurement(self.rid,'views',0,measured_at=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat())
        self.store.measurement(self.rid,'views',150,measured_at=now())
        self.store.measurement(self.rid,'reach',status='no_access')
        state=self.store.snapshot();row=state['releases'][0]
        self.assertEqual(len(state['measurements']),3)
        self.assertEqual(next(m for m in row['metrics'] if m['metric']=='views')['value'],150)
        self.assertIsNone(next(m for m in row['metrics'] if m['metric']=='reach')['value'])
        self.assertAlmostEqual(next(m for m in row['metrics'] if m['metric']=='views')['age_days'],8,places=2)
        for bad in [float('nan'),float('inf'),-1]:
            with self.assertRaises(FactoryError):self.store.measurement(self.rid,'views',bad)
        with self.assertRaises(FactoryError):self.store.measurement(self.rid,'views',20,measured_at=(datetime.now(timezone.utc)-timedelta(days=9)).isoformat())

    def test_lead_updates_do_not_duplicate_and_unknown_source_stays_unknown(self):
        self.store.lead(None,'new','CRM-123')
        self.store.lead(self.rid,'qualified','CRM-123')
        self.store.lead(self.rid,'won','CRM-123',35000)
        self.store.lead(None,'new','CRM-124')
        state=self.store.snapshot()
        self.assertEqual(state['counts']['leads'],2)
        self.assertEqual(state['counts']['revenue'],35000)
        self.assertEqual(sum(l['release_id'] is None for l in state['leads']),1)

    def test_public_links_and_paths_cannot_be_arbitrary_fetches(self):
        for bad in ['http://127.0.0.1/p/a','https://instagram.com.evil.org/p/a','https://www.instagram.com/owner/','https://evil.org/p/a']:
            with self.assertRaises(FactoryError):public_link('instagram',bad)
        with self.assertRaises(FactoryError):self.store.import_pack(self.root/'elsewhere')
        self.assertEqual(public_link('telegram','https://t.me/lazyhim/123?x=1'),'https://t.me/lazyhim/123')
        self.assertEqual(parse_count('1,2 тыс.'),1200)
        self.assertEqual(parse_count('1\u00a0234'),1234)
        self.assertIsNone(parse_count('нет доступа'))


class BrowserIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await FIXTURES.BrowserWorkflow.asyncSetUp(self)
        (self.pack_dir/'validation.json').write_text('{"errors":[]}',encoding='utf-8')
        (self.pack_dir/'preview.html').write_text('Preview',encoding='utf-8')
        Image.new('RGB',(130,170)).save(self.pack_dir/'profile-grid-preview.png')
        (self.pack_dir/'threads-post.txt').write_text('Caption',encoding='utf-8')
        self.store=FactoryStore(self.publisher.local,self.pack_dir.parent,[self.pack_dir.parent])
        self.store.import_pack(self.pack_dir,'Case')
        self.rid=self.store.snapshot()['releases'][1]['id']
        self.store.configure(self.rid,'correct');self.store.approve(self.rid)
        self.publisher.factory=self.store
        self.runner=FactoryBrowser(self.publisher,self.store,PUB.Pack)

    async def asyncTearDown(self):await FIXTURES.BrowserWorkflow.asyncTearDown(self)

    async def test_publisher_records_real_boundary_and_rejects_replay(self):
        await self.runner.prepare(self.rid)
        self.assertEqual(self.store.get_release(self.rid)['state'],'prepared')
        await self.runner.publish(self.rid)
        self.assertEqual(self.store.get_release(self.rid)['state'],'published')
        self.assertEqual(self.store.snapshot()['attempts'][0]['state'],'published')
        self.assertEqual(await self.publisher.pages['threads'].evaluate('window.sent'),1)
        with self.assertRaises(FactoryError):await self.runner.prepare(self.rid)

    async def test_due_approved_release_runs_once_without_a_second_manual_click(self):
        self.store.setting('autopublish',True)
        self.store.schedule(self.rid,(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),True)
        with self.store.db() as db:
            db.execute('UPDATE releases SET scheduled_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=20)).isoformat(),self.rid))
        await self.runner.publish(self.rid,automatic=True)
        self.assertEqual(self.store.get_release(self.rid)['state'],'published')
        self.assertEqual(await self.publisher.pages['threads'].evaluate('window.sent'),1)
        self.assertEqual(self.store.due(),[])


class Dashboard(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.root=Path(self.tmp.name)
        pack=make_pack(self.root)
        self.store=FactoryStore(self.root/'state',self.root/'packs',[self.root]);self.store.import_pack(pack,'Автосвет · тест')
        self.rid=self.store.snapshot()['releases'][0]['id']
        self.store.configure(self.rid,'correct');self.store.report(self.rid,'https://www.instagram.com/p/fixture/',(datetime.now(timezone.utc)-timedelta(days=1)).isoformat())
        self.publisher=PUB.Publisher(PUB.Pack.read(pack),self.root/'publisher')
        self.publisher.factory=self.store;self.publisher.factory_browser=SimpleNamespace(message='Готов к работе')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),PUB.make_handler(self.publisher,'fixture-token',0))
        self.port=self.server.server_address[1];self.server.RequestHandlerClass=PUB.make_handler(self.publisher,'fixture-token',self.port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.driver=await async_playwright().start();self.browser=await self.driver.chromium.launch(channel='chromium',headless=True)
        self.page=await self.browser.new_page(viewport={'width':1440,'height':1000})
        self.errors=[];self.page.on('pageerror',lambda error:self.errors.append(str(error)))

    async def asyncTearDown(self):
        await self.browser.close();await self.driver.stop();self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    async def test_dashboard_forms_persistence_csv_and_mobile_layout(self):
        await self.page.goto(f'http://127.0.0.1:{self.port}/')
        await self.page.get_by_role('button',name='Открыть →').click()
        await self.page.get_by_role('button',name='Добавить замер',exact=True).click()
        await self.page.locator('#measurement-value').fill('123')
        await self.page.locator('#measure-form').get_by_role('button',name='Сохранить замер').click()
        await self.page.wait_for_function('document.getElementById("measure").open===false')
        self.assertEqual(self.store.snapshot()['releases'][0]['metrics'][0]['value'],123)
        await self.page.get_by_role('button',name='Закрыть карточку').click()
        await self.page.get_by_role('button',name='Результаты',exact=False).first.click()
        await self.page.get_by_role('button',name='＋ Учесть обращение').click()
        await self.page.locator('#lead-form [name=reference]').fill('CRM-UI')
        await self.page.locator('#lead-form').get_by_role('button',name='Сохранить',exact=True).click()
        await self.page.wait_for_function('document.getElementById("lead").open===false')
        self.assertEqual(self.store.snapshot()['counts']['leads'],1)
        async with self.page.expect_download() as pending:await self.page.get_by_role('button',name='CSV',exact=True).click()
        download=await pending.value
        self.assertEqual(download.suggested_filename,'content-results.csv')
        await self.page.reload()
        await self.page.get_by_role('button',name='＋ Добавить материал').click()
        await self.page.locator('#new-form [name=title]').fill('Второй материал')
        await self.page.get_by_role('button',name='Добавить в очередь',exact=True).click()
        await self.page.wait_for_function('document.getElementById("new").open===false')
        self.assertEqual(self.store.snapshot()['counts']['materials'],2)
        await self.page.set_viewport_size({'width':390,'height':844})
        for name in ('Очередь','Календарь','Публикации','Результаты','Состояние'):
            await self.page.locator('nav').get_by_role('button',name=name,exact=False).click()
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth+1'),name)
        self.assertEqual(self.errors,[])

    async def test_factory_api_rejects_foreign_origin_and_preview_scripts(self):
        base=f'http://127.0.0.1:{self.port}'
        r=await asyncio.to_thread(requests.post,base+'/api/factory-action',json={'action':'autopublish','enabled':True},headers={'Origin':'https://evil.org','X-Local-Token':'fixture-token'})
        self.assertEqual(r.status_code,403);self.assertFalse(self.store.setting('autopublish'))
        r=await asyncio.to_thread(requests.get,base+f'/factory-file/{self.rid}/preview.html')
        self.assertIn('sandbox',r.headers['Content-Security-Policy'])
        r=await asyncio.to_thread(requests.get,base+f'/factory-file/{self.rid}/%2e%2e')
        self.assertEqual(r.status_code,404)


if __name__=='__main__':unittest.main(verbosity=2)
