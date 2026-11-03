"""Export authored agency carousels and check their small Instagram previews.

Usage: carousel-export.py source.html out_dir [--copy publication.md]
Requires the vault's Playwright and Pillow environment. No network or publishing.
"""
import argparse
import asyncio
import base64
import io
import json
import math
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright


def crop_bounds(width, height, ratio, zoom=1):
    crop_width = min(width, height * ratio)
    crop_height = min(height, width / ratio)
    crop_width /= zoom
    crop_height /= zoom
    return ((width-crop_width)/2, (height-crop_height)/2,
            (width+crop_width)/2, (height+crop_height)/2)


def thumb(im, ratio, zoom=1, width=130):
    box = crop_bounds(*im.size, ratio, zoom)
    return im.crop(box).resize((width, round(width/ratio)), Image.Resampling.LANCZOS)


def png_data(im):
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def font(size):
    for path in ('C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def profile_preview(cover):
    """Three real-size 390px grids, not enlarged thumbnail samples."""
    scenarios = [('3:4 · сетка профиля', 3/4, 1),
                 ('1:1 · проверка обрезки', 1, 1),
                 ('3:4 · увеличение 20%', 3/4, 1.2)]
    sheet = Image.new('RGB', (390, 840), 'white')
    draw = ImageDraw.Draw(sheet)
    y = 12
    draw.text((12,y), 'Превью при ширине экрана 390 px', font=font(16), fill='#2B223A')
    y += 34
    for title, ratio, zoom in scenarios:
        draw.text((12,y), title, font=font(14), fill='#626B87')
        y += 26
        tile = thumb(cover, ratio, zoom)
        sheet.paste(tile, (0,y))
        for col in (1,2):
            draw.rectangle((col*130+1,y,(col+1)*130-1,y+tile.height-1),fill='#EEEAF2')
            draw.text((col*130+12,y+tile.height//2), 'соседний пост',font=font(12),fill='#8D859A')
        # Approximation of the carousel indicator; the text must survive it.
        draw.rounded_rectangle((109,y+9,122,y+23),radius=2,fill='#FFFFFF',outline='#D2CCD9')
        draw.rounded_rectangle((106,y+6,119,y+20),radius=2,fill='#FFFFFF',outline='#D2CCD9')
        y += tile.height + 22
    return sheet.crop((0,0,390,y))


def copy_sections(copy_path, out):
    if copy_path is None:
        return []
    source = copy_path.read_text(encoding='utf-8')
    output = []
    for title, name in [
        ('Instagram — подпись','instagram-caption.txt'),
        ('Threads — основной пост','threads-post.txt'),
        ('Threads — пояснение к цифрам в продолжении','threads-followup.txt'),
        ('Telegram — пост для канала','telegram-post.txt'),
        ('Альтернативный текст к изображениям','alt-text.txt'),
    ]:
        heading = '## ' + title + '\n'
        if heading not in source:
            continue
        body = source.split(heading,1)[1].split('\n## ',1)[0].strip() + '\n'
        path = out/name
        path.write_text(body,encoding='utf-8')
        output.append(path)
    return output


async def run(args):
    source = args.source.resolve()
    out = args.out_dir.resolve()
    if source.parent == out:
        raise ValueError('Keep the authored source outside the generated output directory.')
    out.mkdir(parents=True,exist_ok=True)
    report = {'source':str(source),'errors':[], 'checks':{}}
    exports = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chromium',headless=True)
        page = await browser.new_page(viewport={'width':1080,'height':1350},device_scale_factor=1)
        await page.goto(source.as_uri(),wait_until='load')
        await page.evaluate('document.fonts.ready')
        await page.evaluate('Promise.all(Array.from(document.images,im=>im.decode()))')
        if not await page.locator('.deck .slide').count():
            raise ValueError('Expected slides at .deck .slide')
        await page.add_style_tag(content='''
          html,body{background:white;margin:0;padding:0;}
          .review,.review-end,.profile-review{display:none!important;}
          .deck{display:block!important;width:max-content!important;max-width:none!important;padding:0!important;margin:0!important;}
          .slide-slot{width:var(--export-width)!important;height:var(--export-height)!important;aspect-ratio:auto!important;box-shadow:none!important;border-radius:0!important;}
          .deck .slide{transform:none!important;}
        ''')
        dimensions = await page.locator('.deck .slide').first.evaluate('(s)=>({width:s.offsetWidth,height:s.offsetHeight})')
        w,h = dimensions['width'], dimensions['height']
        await page.evaluate('''({w,h})=>{
          document.documentElement.style.setProperty('--export-width',w+'px');
          document.documentElement.style.setProperty('--export-height',h+'px');
        }''',{'w':w,'h':h})
        report['layout'] = await page.locator('.deck .slide').evaluate_all('''slides=>slides.map((s,i)=>{
          const box=s.getBoundingClientRect();
          const content=s.querySelector('.content');
          const footer=s.querySelector('.footer');
          const end=footer?footer.getBoundingClientRect().top:box.bottom;
          const children=content?Array.from(content.children):[];
          return {slide:i+1,width:s.offsetWidth,height:s.offsetHeight,
            overlap:children.some(e=>e.getBoundingClientRect().bottom>end-8),
            textOverflow:children.some(e=>e.scrollWidth>e.clientWidth+1)};
        })''')
        for row in report['layout']:
            if (row['width'],row['height']) != (w,h):
                report['errors'].append(f"Slide {row['slide']}: inconsistent export size")
            if row['overlap'] or row['textOverflow']:
                report['errors'].append(f"Slide {row['slide']}: content clips or overlaps the footer")
        keys = await page.locator('.deck .slide').first.locator('[data-grid-key]').evaluate_all('''nodes=>nodes.map(e=>{
          const cover=e.closest('.slide').getBoundingClientRect();
          const b=e.getBoundingClientRect();
          return {text:e.textContent.trim(),x:b.left-cover.left,y:b.top-cover.top,
            width:b.width,height:b.height,font:parseFloat(getComputedStyle(e).fontSize)};
        })''')
        if not keys:
            report['errors'].append('Cover has no data-grid-key elements; mark the niche and meaningful result.')
        report['cover_keys'] = keys
        scenarios = [('3:4',3/4,1),('1:1',1,1),('3:4 zoom 20%',3/4,1.2)]
        for name,ratio,zoom in scenarios:
            left,top,right,bottom = crop_bounds(w,h,ratio,zoom)
            for key in keys:
                if key['x']<left-1 or key['y']<top-1 or key['x']+key['width']>right+1 or key['y']+key['height']>bottom+1:
                    report['errors'].append(f"Cover {name}: cropped key {key['text']!r}")
        # Brand safe rectangle, scaled from the authored 1080x1350 layout.
        for key in keys:
            if key['x'] < w*160/1080-1 or key['x']+key['width'] > w*920/1080+1 or key['y'] < h*240/1350-1 or key['y']+key['height'] > h*1110/1350+1:
                report['errors'].append(f"Cover: key outside brand safe area: {key['text']!r}")
            size = key['font']*130/w
            if size < 11:
                report['errors'].append(f"Cover: key {key['text']!r} becomes {size:.1f}px in the 130px tile")
        body = await page.locator('.deck [data-body-copy]').evaluate_all('nodes=>nodes.map(e=>({text:e.textContent.trim().slice(0,60),font:parseFloat(getComputedStyle(e).fontSize)}))')
        if not body:
            report['errors'].append('No data-body-copy elements; mark primary slide text for mobile-size checks.')
        for item in body:
            if item['font']*390/w < 11:
                report['errors'].append(f"Body text too small at 390px: {item['text']!r}")
        report['body_copy'] = body
        report['checks']['grid_scenarios'] = [s[0] for s in scenarios]
        report['checks']['thumbnail_width'] = 130
        slides = page.locator('.deck .slide')
        for i in range(await slides.count()):
            target=out/f'slide-{i+1:02}.png'
            await slides.nth(i).screenshot(path=str(target))
            exports.append(target)
        mobile=await browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
        await mobile.goto(source.as_uri(),wait_until='load')
        await mobile.evaluate('document.fonts.ready')
        report['checks']['mobile_horizontal_overflow'] = await mobile.evaluate('document.documentElement.scrollWidth>innerWidth')
        if report['checks']['mobile_horizontal_overflow']:
            report['errors'].append('Preview has horizontal overflow on a 390px screen')
        await mobile.screenshot(path=str(out/'mobile-preview.png'),full_page=True)
        await browser.close()
    cover=Image.open(exports[0]).convert('RGB')
    grid=profile_preview(cover)
    grid.save(out/'profile-grid-preview.png')
    grid_html = '''<section class="profile-review" style="max-width:1160px;margin:0 auto 28px;padding:0 24px;">
      <h2 style="font:700 22px Manrope,Arial;color:#2B223A;margin:0 0 12px;">Обложка в сетке профиля</h2>
      <p style="font:14px/1.5 Manrope,Arial;color:#626B87;margin:0 0 16px;">Проверочный макет: три колонки на экране 390 px. Ключевой текст должен читаться без увеличения.</p>
      <img src="GRID_DATA" alt="Превью обложки в трёхколоночной сетке: 3:4, квадрат и увеличение на 20 процентов" style="width:390px;max-width:100%;height:auto;display:block;border:1px solid #E7E3EC;">
    </section>'''.replace('GRID_DATA',png_data(grid))
    markup=source.read_text(encoding='utf-8')
    # The factory serves previews in a sandbox with scripts disabled. Container
    # units keep the fixed-size authored slide fitted without JavaScript.
    fit_css=f'<style id="carousel-preview-fit">.slide-slot{{container-type:inline-size}}.deck .slide{{transform:scale(calc(100cqw / {w}px))}}</style>'
    markup=markup.replace('</head>',fit_css+'\n</head>',1)
    markup=markup.replace('<main class="deck">',grid_html+'\n<main class="deck">',1)
    (out/'preview.html').write_text(markup,encoding='utf-8')
    cols=min(4,len(exports)); tw=270; th=round(tw*h/w); pad=24; gap=18; lh=32
    rows=math.ceil(len(exports)/cols)
    contact=Image.new('RGB',(cols*tw+(cols-1)*gap+2*pad,rows*(th+lh)+(rows-1)*gap+2*pad),'#E9E5ED')
    draw=ImageDraw.Draw(contact)
    for i,path in enumerate(exports):
        x=pad+(i%cols)*(tw+gap); y=pad+(i//cols)*(th+lh+gap)
        draw.text((x,y),f'{i+1:02}',font=font(16),fill='#2B223A')
        with Image.open(path) as im:
            contact.paste(im.convert('RGB').resize((tw,th),Image.Resampling.LANCZOS),(x,y+lh))
    contact.save(out/'contact-sheet.jpg',quality=92)
    texts=copy_sections(args.copy,out)
    (out/'README.txt').write_text(
        f'{len(exports)} карточек · {w}×{h} px\n\n'
        'slide-XX.png — карточки в порядке публикации.\n'
        'preview.html — автономный предпросмотр.\n'
        'profile-grid-preview.png — обложка в маленьких плитках.\n'
        'telegram-post.txt — самостоятельный пост для Telegram, если подготовлен в исходном файле.\n'
        'Макеты 3:4, 1:1 и увеличение 20% — проверки, а не гарантия интерфейса Instagram.\n'
        'При загрузке проверь выбранную обрезку и вид обложки.\n'
        'Публикация этим инструментом не выполняется.\n',encoding='utf-8')
    (out/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if report['errors']:
        print(json.dumps({'status':'needs_revision','errors':report['errors']},ensure_ascii=False,indent=2))
        return 1
    bundle=out/(args.zip_name or source.stem+'.zip')
    names=exports+texts+[out/name for name in ('preview.html','contact-sheet.jpg','profile-grid-preview.png','README.txt')]
    with ZipFile(bundle,'w',compression=ZIP_DEFLATED) as z:
        for path in names:
            z.write(path,path.name)
    print(json.dumps({'status':'passed','slides':len(exports),'size':[w,h], 'grid_keys':len(keys),
                      'body_copy_blocks':len(body),'preview':str(out/'preview.html'),'zip':str(bundle)},ensure_ascii=False,indent=2))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('out_dir',type=Path)
    parser.add_argument('--copy',type=Path)
    parser.add_argument('--zip-name')
    args=parser.parse_args()
    try:
        return asyncio.run(run(args))
    except (OSError,ValueError) as exc:
        print(f'Export error: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
