"""Exercise publishing against local HTML fixtures; no social-network requests."""
import asyncio
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

SPEC=importlib.util.spec_from_file_location('local_social_publisher',Path(__file__).with_name('social-publisher.py'))
MODULE=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=MODULE
SPEC.loader.exec_module(MODULE)

FIXTURE=r'''<!doctype html><html><meta charset="utf-8"><body>
PROFILE_CONTROL
<button onclick="openComposer()">Create</button><div id="mount"></div>
<script>
const platform=PLATFORM;window.sent=0;window.selectedRatio='';window.uploaded=[];let step=0;
function openComposer(){document.getElementById('mount').innerHTML=`<div role="dialog"><input type="file" multiple accept="image/*" style="display:none" onchange="loaded(this)"><div id="stage"></div></div>`;render();}
function loaded(input){window.uploaded=Array.from(input.files,f=>f.name);render();}
function render(){const d=document.getElementById('stage');let images=window.uploaded.map(n=>`<img width="60" height="75" alt="${n}" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7#${n}">`).join('');
if(platform==='threads'){d.innerHTML=images+'<textarea aria-label="New thread"></textarea><button onclick="submitPost()">Post</button>';return;}
if(step===0){d.innerHTML=images+`<button onclick="cropMenu()">Select crop</button><div id="ratios"></div><button onclick="step=1;render()">Next</button>`;return;}
if(step===1){d.innerHTML=images+'<button onclick="step=2;render()">Next</button>';return;}
d.innerHTML=images+'<textarea aria-label="Write a caption"></textarea><button onclick="submitPost()">Share</button>';}
function cropMenu(){document.getElementById('ratios').innerHTML=`<button onclick="choose('Original')">Original</button><button onclick="choose('4:5')">4:5</button>`;}
function choose(r){window.selectedRatio=r;document.getElementById('ratios').innerHTML='';}
function submitPost(){window.sent++;console.log('submitted-fixture');document.getElementById('stage').innerHTML=platform==='instagram'?'<p>Your post has been shared</p><a href="/p/new-fixture/">View post</a>':'<p>Posted</p><a href="/@correct/post/new-fixture/">View post</a>';}
</script></body></html>'''


class BrowserWorkflow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=MODULE.ROOT/'tmp')
        root=Path(self.tmp.name)
        self.pack_dir=root/'pack';self.pack_dir.mkdir()
        for i in range(1,4):
            Image.new('RGB',(108,135),(i*40,40,40)).save(self.pack_dir/f'slide-{i:02}.png')
        self.pack=MODULE.Pack.read(self.pack_dir)
        self.publisher=MODULE.Publisher(self.pack,root/'state')
        self.driver=await async_playwright().start()
        self.browser=await self.driver.chromium.launch(channel='chromium',headless=True)
        self.context=await self.browser.new_context()
        async def route(request):
            url=request.request.url
            platform='instagram' if 'instagram.com' in url else 'threads'
            owner='/correct/' in url or '/@correct/' in url
            html=FIXTURE.replace('PLATFORM',json.dumps(platform)).replace('PROFILE_CONTROL','<button>Edit profile</button>' if owner else '<button>Follow</button>')
            await request.fulfill(status=200,content_type='text/html',body=html)
        await self.context.route('**/*',route)
        self.publisher.context=self.context

    async def asyncTearDown(self):
        await self.browser.close();await self.driver.stop();self.tmp.cleanup()

    async def test_prepare_does_not_post_and_preserves_order_and_ratio(self):
        for platform in MODULE.PLATFORMS:
            await self.publisher.prepare(platform,'correct','Проверенный текст кейса.')
            page=self.publisher.pages[platform]
            self.assertEqual(await page.evaluate('window.sent'),0)
            self.assertEqual(await page.evaluate('window.uploaded'),['slide-01.png','slide-02.png','slide-03.png'])
            if platform=='instagram':
                self.assertEqual(await page.evaluate('window.selectedRatio'),'4:5')
            self.assertEqual(self.publisher.platforms[platform]['phase'],'prepared')
            self.assertEqual(self.publisher.platforms[platform]['verified'],'correct')

    async def test_live_menu_without_roles_and_threads_two_create_entries(self):
        await self.context.unroute('**/*')
        async def route(request):
            platform='instagram' if 'instagram.com' in request.request.url else 'threads'
            if platform=='instagram':
                entry='''<button onclick="document.getElementById('menu').innerHTML=`<div onclick=&quot;openComposer()&quot;>Публикация</div>`">Create</button><div id="menu"></div>'''
            else:
                entry='<div role="button" onclick="openComposer();document.querySelector(\'[role=dialog]\').style.display=\'none\';setTimeout(()=>document.querySelector(\'[role=dialog]\').style.display=\'block\',200)">Новая публикация</div><div role="button" onclick="throw Error(\'Wrong create entry\')"><svg aria-label="Создать"></svg></div>'
            html=FIXTURE.replace('PLATFORM',json.dumps(platform)).replace('PROFILE_CONTROL','<button>Edit profile</button>').replace('<button onclick="openComposer()">Create</button>',entry)
            html=html.replace('window.uploaded=Array.from(input.files,f=>f.name);render();','window.uploaded=Array.from(input.files,f=>f.name);input.value="";render();')
            await request.fulfill(status=200,content_type='text/html',body=html)
        await self.context.route('**/*',route)
        for platform in MODULE.PLATFORMS:
            await self.publisher.prepare(platform,'correct','Caption')
            self.assertEqual(self.publisher.platforms[platform]['phase'],'prepared')
            self.assertEqual(await self.publisher.pages[platform].evaluate('window.sent'),0)

    async def test_only_one_submission_and_receipt_blocks_replay(self):
        for platform in MODULE.PLATFORMS:
            await self.publisher.prepare(platform,'correct','Caption')
            original_screenshot=self.publisher.screenshot
            async def failed_screenshot(*args):
                raise OSError('Fixture screenshot failure after confirmed posting')
            self.publisher.screenshot=failed_screenshot
            await self.publisher.publish(platform,'correct','Caption')
            self.publisher.screenshot=original_screenshot
            self.assertEqual(await self.publisher.pages[platform].evaluate('window.sent'),1)
            self.assertEqual(self.publisher.platforms[platform]['phase'],'published')
            self.assertTrue(self.publisher.platforms[platform]['permalink'])
            with self.assertRaises(MODULE.WorkflowError):
                await self.publisher.prepare(platform,'correct','Caption')
            self.assertEqual(await self.publisher.pages[platform].evaluate('window.sent'),1)

    async def test_changed_draft_and_changed_files_cannot_be_submitted(self):
        await self.publisher.prepare('threads','correct','Caption')
        page=self.publisher.pages['threads']
        await page.get_by_role('textbox').fill('Changed in browser')
        with self.assertRaises(MODULE.WorkflowError):
            await self.publisher.publish('threads','correct','Caption')
        self.assertEqual(await page.evaluate('window.sent'),0)
        await page.get_by_role('textbox').fill('Caption')
        Image.new('RGB',(108,135),'blue').save(self.pack.images[0])
        with self.assertRaises(MODULE.WorkflowError):
            await self.publisher.publish('threads','correct','Caption')
        self.assertEqual(await page.evaluate('window.sent'),0)

    async def test_wrong_account_stops_before_upload(self):
        with self.assertRaises(MODULE.WorkflowError):
            await self.publisher.prepare('threads','other','Caption')
        self.assertEqual(await self.publisher.pages['threads'].locator('input[type=file]').count(),0)

    async def test_inspection_does_not_navigate_or_submit_or_export_field_values(self):
        await self.publisher.prepare('threads','correct','Private draft contents')
        page=self.publisher.pages['threads']
        address=page.url
        signature=await self.publisher.signature(page)
        await self.publisher.inspect('threads')
        details=json.loads((self.publisher.local/'threads-inspection.json').read_text(encoding='utf-8'))
        self.assertNotIn('Private draft contents',json.dumps(details))
        self.assertEqual(page.url,address)
        self.assertEqual(await self.publisher.signature(page),signature)
        self.assertEqual(await page.evaluate('window.sent'),0)
        self.assertEqual(self.publisher.platforms['threads']['phase'],'prepared')
    async def test_interrupted_post_becomes_unknown_and_cannot_retry(self):
        await self.publisher.prepare('threads','correct','Caption')
        page=self.publisher.pages['threads']
        observed=[]
        def close_after_submission(message):
            if message.text=='submitted-fixture':
                observed.append(True)
                asyncio.create_task(page.close())
        page.on('console',close_after_submission)
        try:
            await self.publisher.publish('threads','correct','Caption')
        except Exception:
            pass
        self.assertEqual(len(observed),1)
        key=self.pack.fingerprint('threads','correct','Caption')
        self.assertEqual(self.publisher.ledger[key]['state'],'unknown')
        with self.assertRaises(MODULE.WorkflowError):
            await self.publisher.prepare('threads','correct','Caption')


class NetworkConfig(unittest.TestCase):
    def test_proxy_is_explicit_loopback_and_credentials_cannot_leak(self):
        self.assertIsNone(MODULE.browser_proxy('direct'))
        self.assertIsNone(MODULE.browser_proxy(''))
        self.assertEqual(MODULE.browser_proxy('http://127.0.0.1:10809')['server'],'http://127.0.0.1:10809')
        self.assertIn('127.0.0.1',MODULE.browser_proxy('socks5://localhost:10808')['bypass'])
        for bad in ['http://user:secret@127.0.0.1:10809','http://example.com:10809','http://127.0.0.1:bad','file:///tmp/config','http://127.0.0.1:10809/path']:
            with self.subTest(bad=bad),self.assertRaises(MODULE.WorkflowError):
                MODULE.browser_proxy(bad)


class LocalServerBoundaries(unittest.TestCase):
    def test_foreign_origin_and_path_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=MODULE.ROOT/'tmp') as directory:
            root=Path(directory);pack_dir=root/'pack';pack_dir.mkdir()
            for i in range(1,3):Image.new('RGB',(108,135)).save(pack_dir/f'slide-{i:02}.png')
            publisher=MODULE.Publisher(MODULE.Pack.read(pack_dir),root/'state')
            server=ThreadingHTTPServer(('127.0.0.1',0),MODULE.make_handler(publisher,'test-token',0))
            port=server.server_address[1]
            server.RequestHandlerClass=MODULE.make_handler(publisher,'test-token',port)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url=f'http://127.0.0.1:{port}'
            try:
                for headers in ({'Origin':'https://example.com','X-Local-Token':'test-token'}, {'Origin':url,'X-Local-Token':'wrong'}):
                    request=urllib.request.Request(url+'/api/action',data=b'{"action":"shutdown"}',headers=headers,method='POST')
                    with self.assertRaises(urllib.error.HTTPError) as failure:urllib.request.urlopen(request)
                    self.assertEqual(failure.exception.code,403)
                    failure.exception.close()
                with self.assertRaises(urllib.error.HTTPError) as failure:urllib.request.urlopen(url+'/pack/%2e%2e/accounts.json')
                self.assertEqual(failure.exception.code,404)
                failure.exception.close()
                with urllib.request.urlopen(url+'/api/state') as response:
                    self.assertIsInstance(json.load(response)['platforms'],dict)
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    unittest.main(verbosity=2)
