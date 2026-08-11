"""
Генератор каруселей для Instagram (нога 3, @lazyhim) из markdown.

Использование:
    .tools/venv/bin/python .tools/projects/ai-infobiz/content/carousel.py \
        <input.md> [output_dir]

Формат input.md — слайды разделяются строкой `---`:

    Заголовок обложки
    подзаголовок обложки

    ---

    ## Заголовок слайда
    - тезис
    - тезис

    ---

    [cta]
    Подпишись
    что получишь в подписке

Авто-стиль по позиции: 1-й слайд = обложка (тёмная), последний = CTA (тёмная),
средние = контент (светлые). Переопределяется первой строкой-тегом слайда:
[cover] / [cta] / [dark] / [light].

Вывод: <output_dir>/slide-01.png ... в фирменном стиле (тёмный #2B223A + жёлтый #FFBA24).
По умолчанию output_dir = .tools/carousel-out/<имя-входного-файла>/.

Размер: 1080×1350 (4:5), рендер ×2 = 2160×2700 для чёткого текста.
"""
import sys
import re
import asyncio
from pathlib import Path

import markdown as md
from playwright.async_api import async_playwright

# ── Бренд ноги 3 (личный, наследует палитру из КП) ──────────────────────
HANDLE = "@lazyhim"
AUTHOR = "Володя"
TAGLINE = "маркетинг × ИИ"

DARK = "#2B223A"
YELLOW = "#FFBA24"
TEXT = "#1F2937"
MUTED = "#626B87"
LIGHT_BG = "#F7F5FA"

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Manrope', -apple-system, sans-serif; }}

.slide {{
  width: 1080px;
  height: 1350px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 96px 88px 84px;
}}

/* ── фоны ── */
.slide.light {{ background: {LIGHT_BG}; color: {TEXT}; }}
.slide.dark  {{
  background:
    radial-gradient(circle at 90% 4%, rgba(255,186,36,0.22), transparent 38%),
    {DARK};
  color: #fff;
}}

/* ── верхняя плашка бренда ── */
.brand {{
  display: flex; align-items: center; justify-content: space-between;
  font-size: 26px; font-weight: 800; letter-spacing: 0.02em;
}}
.brand .handle {{ color: inherit; }}
.brand .tag {{ font-size: 20px; font-weight: 600; opacity: 0.6; }}
.slide.dark .brand .dot, .slide.light .brand .dot {{ color: {YELLOW}; }}

/* ── контент-зона ── */
.body {{ flex: 1; display: flex; flex-direction: column; justify-content: center; }}

.eyebrow {{
  color: {YELLOW}; font-size: 24px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 28px;
}}

/* обложка */
.cover-title {{ font-size: 92px; font-weight: 800; line-height: 1.04; letter-spacing: -0.03em; }}
.cover-sub {{ font-size: 38px; font-weight: 500; line-height: 1.35; margin-top: 32px; opacity: 0.85; }}

/* заголовок контент-слайда */
h2, .body h2 {{
  font-size: 60px; font-weight: 800; line-height: 1.1; letter-spacing: -0.02em;
  padding-left: 30px; border-left: 12px solid {YELLOW}; margin-bottom: 40px;
}}
h3 {{ font-size: 40px; font-weight: 700; margin: 24px 0 14px; }}

/* текст и списки */
.body p {{ font-size: 38px; line-height: 1.45; margin-bottom: 22px; }}
.body ul, .body ol {{ list-style: none; }}
.body li {{
  font-size: 38px; line-height: 1.4; margin-bottom: 28px;
  padding-left: 52px; position: relative;
}}
.body li::before {{
  content: "→"; position: absolute; left: 0; top: 0;
  color: {YELLOW}; font-weight: 800;
}}
.body strong {{ font-weight: 800; }}
.slide.light .body strong {{ color: {DARK}; }}
.slide.dark .body strong {{ color: {YELLOW}; }}
.body em {{ font-style: normal; color: {YELLOW}; font-weight: 700; }}

/* CTA */
.cta-title {{ font-size: 76px; font-weight: 800; line-height: 1.08; letter-spacing: -0.02em; }}
.cta-sub {{ font-size: 38px; font-weight: 500; line-height: 1.4; margin-top: 28px; opacity: 0.85; }}
.cta-handle {{ font-size: 48px; font-weight: 800; color: {YELLOW}; margin-top: 56px; }}

/* ── нижняя плашка ── */
.foot {{
  display: flex; align-items: center; justify-content: space-between;
  font-size: 24px; font-weight: 600; opacity: 0.7;
}}
.foot .swipe {{ color: {YELLOW}; opacity: 1; }}
.num {{
  font-weight: 800; font-size: 26px;
  width: 56px; height: 56px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
}}
.slide.light .num {{ background: {DARK}; color: #fff; }}
.slide.dark .num {{ background: {YELLOW}; color: {DARK}; }}
"""

PAGE = """<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
<style>{css}</style></head><body>{slides}</body></html>"""


def parse_slides(md_text: str):
    """Разбить md на слайды по строкам-разделителям `---` (без YAML-фронтматтера)."""
    if md_text.startswith("---"):
        end = md_text.find("\n---", 3)
        if end != -1:
            md_text = md_text[end + 4:].lstrip()
    parts = re.split(r"(?m)^\s*---\s*$", md_text)
    return [p.strip() for p in parts if p.strip()]


def slide_kind(raw: str, idx: int, total: int):
    """Определить тип слайда: явный тег или авто по позиции."""
    m = re.match(r"^\[(cover|cta|dark|light)\]\s*", raw, re.IGNORECASE)
    if m:
        return m.group(1).lower(), raw[m.end():].strip()
    if idx == 0:
        return "cover", raw
    if idx == total - 1:
        return "cta", raw
    return "content", raw


def render_slide(raw: str, idx: int, total: int) -> str:
    kind, body = slide_kind(raw, idx, total)
    num = idx + 1
    brand = (
        f'<div class="brand"><span class="handle">{HANDLE}</span>'
        f'<span class="tag">{TAGLINE}</span></div>'
    )

    if kind == "cover":
        lines = [l for l in body.splitlines() if l.strip()]
        title = lines[0].lstrip("# ").strip() if lines else ""
        sub = " ".join(l.strip() for l in lines[1:]) if len(lines) > 1 else ""
        inner = (
            f'<div class="eyebrow">{AUTHOR} · {TAGLINE}</div>'
            f'<div class="cover-title">{title}</div>'
            + (f'<div class="cover-sub">{sub}</div>' if sub else "")
        )
        foot = f'<div class="foot"><span class="swipe">листай →</span><span></span></div>'
        return f'<div class="slide dark"><div class="body">{inner}</div>{foot}</div>'

    if kind == "cta":
        lines = [l for l in body.splitlines() if l.strip()]
        title = lines[0].lstrip("# ").strip() if lines else "Подпишись"
        sub = " ".join(l.strip() for l in lines[1:]) if len(lines) > 1 else ""
        inner = (
            f'<div class="cta-title">{title}</div>'
            + (f'<div class="cta-sub">{sub}</div>' if sub else "")
            + f'<div class="cta-handle">{HANDLE}</div>'
        )
        foot = (
            f'<div class="foot"><span></span>'
            f'<span class="num">{num}</span></div>'
        )
        return f'<div class="slide dark">{brand}<div class="body">{inner}</div>{foot}</div>'

    # content / dark / light
    css_kind = "dark" if kind == "dark" else "light"
    html_body = md.markdown(
        body, extensions=["tables", "fenced_code", "sane_lists", "nl2br"]
    )
    foot = (
        f'<div class="foot"><span>{HANDLE}</span>'
        f'<span class="num">{num}</span></div>'
    )
    return f'<div class="slide {css_kind}">{brand}<div class="body">{html_body}</div>{foot}</div>'


async def build(in_path: Path, out_dir: Path):
    slides = parse_slides(in_path.read_text(encoding="utf-8"))
    if not slides:
        print("⚠️ В файле нет слайдов (разделяй блоки строкой `---`).")
        return
    total = len(slides)
    html = PAGE.format(
        css=CSS,
        slides="".join(render_slide(s, i, total) for i, s in enumerate(slides)),
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_preview.html").write_text(html, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        page = await browser.new_page(
            viewport={"width": 1080, "height": 1350}, device_scale_factor=2
        )
        await page.set_content(html, wait_until="load")
        await page.wait_for_timeout(1500)  # дождаться Manrope с CDN
        els = await page.query_selector_all(".slide")
        for i, el in enumerate(els, 1):
            out = out_dir / f"slide-{i:02d}.png"
            await el.screenshot(path=str(out))
            print(f"  ✓ slide-{i:02d}.png")
        await browser.close()

    print(f"✓ Карусель ({total} слайд.) → {out_dir}/")
    print(f"  превью: {out_dir / '_preview.html'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: carousel.py <input.md> [output_dir]")
        sys.exit(1)
    src = Path(sys.argv[1])
    tools_dir = Path(__file__).resolve().parents[3]
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        tools_dir / "carousel-out" / src.stem
    )
    asyncio.run(build(src, dst))
