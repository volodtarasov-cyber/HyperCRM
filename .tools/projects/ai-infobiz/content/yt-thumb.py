"""
Генератор обложек YouTube (нога 3, @lazyhim) из markdown.

Использование:
    .tools/venv/bin/python .tools/projects/ai-infobiz/content/yt-thumb.py \
        <input.md> [output_dir]

Формат input.md — варианты обложек разделяются строкой `---`:

    [dark]
    # ВТОРОЙ МОЗГ
    ## на Claude Code
    > Claude Code + Obsidian

Разметка внутри варианта:
    # ГЛАВНОЕ      — крупная строка (жёлтая), 2-4 слова максимум
    ## подзаголовок — вторая строка (белая/тёмная), опционально
    > надпись       — eyebrow сверху, опционально
    ! бейдж         — жёлтая плашка внизу, опционально

Тег первой строкой: [dark] (по умолчанию) / [light] / [split].
`split` оставляет правые 42% пустыми под фото лица.

Вывод: <output_dir>/thumb-01.png ... 1280×720, рендер ×2 = 2560×1440.
По умолчанию output_dir = .tools/thumb-out/<имя-входного-файла>/.

HTML-превью пишется всегда (_preview.html) — открывается в любом браузере,
даже если playwright недоступен (например, на Windows-машине без venv).

Правила читаемости (обложка живёт в ленте размером ~210×118):
  - главная строка ≤ 4 слов;
  - контраст тёмный #2B223A × жёлтый #FFBA24;
  - правый нижний угол свободен — там таймкод ютуба.
"""
import sys
import re
import asyncio
from pathlib import Path

# Консоль Windows по умолчанию cp1251 и падает на эмодзи в выводе.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Бренд ноги 3 (наследует палитру карусели) ───────────────────────────
HANDLE = "@lazyhim"

DARK = "#2B223A"
YELLOW = "#FFBA24"
TEXT = "#1F2937"
LIGHT_BG = "#F7F5FA"

W, H = 1280, 720

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Manrope', -apple-system, sans-serif; }}

.thumb {{
  width: {W}px;
  height: {H}px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 64px 72px;
  margin-bottom: 24px;
}}

.thumb.light {{ background: {LIGHT_BG}; color: {TEXT}; }}
.thumb.dark, .thumb.split {{
  background:
    radial-gradient(circle at 88% 10%, rgba(255,186,36,0.20), transparent 42%),
    {DARK};
  color: #fff;
}}

/* split — правые 42% под фото лица */
.thumb.split .inner {{ width: 58%; }}
.thumb.split::after {{
  content: "";
  position: absolute; right: 0; top: 0; bottom: 0; width: 42%;
  border-left: 2px dashed rgba(255,255,255,0.18);
  background: repeating-linear-gradient(
    45deg, rgba(255,255,255,0.03) 0 12px, transparent 12px 24px
  );
}}
.thumb.split .face-hint {{
  position: absolute; right: 21%; top: 50%;
  transform: translate(50%, -50%);
  font-size: 22px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; opacity: 0.35; white-space: nowrap;
}}

.inner {{ position: relative; z-index: 2; }}

.eyebrow {{
  color: {YELLOW}; font-size: 26px; font-weight: 800;
  letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 22px;
}}

.main {{
  font-size: 104px; font-weight: 800; line-height: 0.98;
  letter-spacing: -0.035em; color: {YELLOW};
  text-transform: uppercase;
}}
.thumb.light .main {{ color: {DARK}; }}

.sub {{
  font-size: 46px; font-weight: 700; line-height: 1.15;
  margin-top: 20px; opacity: 0.92;
}}

.badge {{
  display: inline-block; margin-top: 32px;
  background: {YELLOW}; color: {DARK};
  font-size: 28px; font-weight: 800; letter-spacing: 0.02em;
  padding: 14px 26px; border-radius: 10px;
}}

.handle {{
  position: absolute; left: 72px; bottom: 44px;
  font-size: 24px; font-weight: 800; opacity: 0.55; z-index: 2;
}}

.label {{
  font: 700 20px/1 'Manrope', sans-serif; color: #888;
  margin: 32px 0 10px; letter-spacing: 0.08em; text-transform: uppercase;
}}
"""

PAGE = """<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
<title>YT thumbnails — {handle}</title>
<style>{css}</style></head><body>{thumbs}</body></html>"""


def parse_variants(md_text: str):
    """Разбить md на варианты обложек по строкам-разделителям `---`."""
    if md_text.startswith("---"):
        end = md_text.find("\n---", 3)
        if end != -1:
            md_text = md_text[end + 4:].lstrip()
    parts = re.split(r"(?m)^\s*---\s*$", md_text)
    return [p.strip() for p in parts if p.strip()]


def render_thumb(raw: str, idx: int) -> str:
    kind = "dark"
    m = re.match(r"^\[(dark|light|split)\]\s*", raw, re.IGNORECASE)
    if m:
        kind, raw = m.group(1).lower(), raw[m.end():].strip()

    main = sub = eyebrow = badge = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            sub = line[3:].strip()
        elif line.startswith("# "):
            main = line[2:].strip()
        elif line.startswith("> "):
            eyebrow = line[2:].strip()
        elif line.startswith("! "):
            badge = line[2:].strip()

    inner = "".join([
        f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else "",
        f'<div class="main">{main}</div>' if main else "",
        f'<div class="sub">{sub}</div>' if sub else "",
        f'<div class="badge">{badge}</div>' if badge else "",
    ])
    face = '<div class="face-hint">фото сюда</div>' if kind == "split" else ""
    return (
        f'<div class="label">вариант {idx + 1} · {kind}</div>'
        f'<div class="thumb {kind}">'
        f'<div class="inner">{inner}</div>{face}'
        f'<div class="handle">{HANDLE}</div>'
        f'</div>'
    )


async def shoot(html: str, out_dir: Path, count: int):
    """Снять PNG через playwright. Молча пропустить, если его нет."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("⚠️  playwright недоступен — PNG не сняты, открой _preview.html вручную")
        return
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        page = await browser.new_page(
            viewport={"width": W, "height": H}, device_scale_factor=2
        )
        await page.set_content(html, wait_until="load")
        await page.wait_for_timeout(1500)  # дождаться Manrope с CDN
        for i, el in enumerate(await page.query_selector_all(".thumb"), 1):
            await el.screenshot(path=str(out_dir / f"thumb-{i:02d}.png"))
            print(f"  ✓ thumb-{i:02d}.png")
        await browser.close()


async def build(in_path: Path, out_dir: Path):
    variants = parse_variants(in_path.read_text(encoding="utf-8"))
    if not variants:
        print("⚠️ В файле нет вариантов (разделяй блоки строкой `---`).")
        return
    html = PAGE.format(
        handle=HANDLE,
        css=CSS,
        thumbs="".join(render_thumb(v, i) for i, v in enumerate(variants)),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_preview.html").write_text(html, encoding="utf-8")
    await shoot(html, out_dir, len(variants))
    print(f"✓ Обложки ({len(variants)} вар.) → {out_dir}/")
    print(f"  превью: {out_dir / '_preview.html'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: yt-thumb.py <input.md> [output_dir]")
        sys.exit(1)
    src = Path(sys.argv[1])
    tools_dir = Path(__file__).resolve().parents[3]
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        tools_dir / "thumb-out" / src.stem
    )
    asyncio.run(build(src, dst))
