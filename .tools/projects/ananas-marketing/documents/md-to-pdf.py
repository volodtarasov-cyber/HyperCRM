"""
Конвертер Markdown → PDF в фирменном стиле «Ананас Маркетинг» (вариант B: гибрид).
Использование: python md-to-pdf.py <input.md> <output.pdf>
"""
import sys
import asyncio
import re
from pathlib import Path
import markdown as md
from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[4]
BRAND_CSS_PATH = ROOT / "team/assets/ananas-marketing-brand.css"
BRAND_CSS = BRAND_CSS_PATH.read_text(encoding="utf-8")


# ============================================================
# СТИЛЬ B — обложка тёмная, основной текст светлый, жёлтые акценты
# ============================================================
CSS = BRAND_CSS + """
@page {
  size: A4;
  margin: 18mm 16mm 18mm 16mm;
}
@page :first {
  margin: 0;
}

* { box-sizing: border-box; }

body {
  font-family: 'Manrope', -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.6;
  color: var(--c-text);
  margin: 0;
  padding: 0;
  background: #fff;
}

/* ========== ОБЛОЖКА ========== */
.cover {
  page-break-after: always;
  width: 210mm;
  height: 297mm;
  background: var(--c-dark);
  color: #fff;
  padding: 30mm 22mm;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.cover::before {
  content: "";
  position: absolute;
  top: -80mm;
  right: -80mm;
  width: 180mm;
  height: 180mm;
  background: radial-gradient(circle, rgba(255,186,36,0.25) 0%, rgba(255,186,36,0) 60%);
  pointer-events: none;
}

.cover-logo {
  font-family: 'Manrope', sans-serif;
  font-size: 18pt;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #fff;
  display: inline-block;
}
.cover-logo .accent {
  color: var(--c-yellow);
  font-weight: 800;
}
.cover-logo-sub {
  font-size: 9pt;
  font-weight: 500;
  color: rgba(255,255,255,0.65);
  margin-top: 4pt;
  letter-spacing: 0.02em;
}

.cover-eyebrow {
  font-size: 10pt;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--c-yellow);
  margin-bottom: 14pt;
}

.cover-title {
  font-size: 38pt;
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: -0.02em;
  color: #fff;
  margin: 0 0 16pt;
}

.cover-subtitle {
  font-size: 14pt;
  font-weight: 500;
  line-height: 1.4;
  color: rgba(255,255,255,0.85);
  max-width: 140mm;
  margin: 0 0 24pt;
}

.cover-stages {
  display: flex;
  gap: 6pt;
  margin-top: 12pt;
  flex-wrap: wrap;
}
.cover-stage {
  display: inline-flex;
  align-items: center;
  gap: 8pt;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,186,36,0.4);
  border-radius: 100px;
  padding: 6pt 14pt;
  font-size: 10pt;
  font-weight: 600;
  color: #fff;
}
.cover-stage .dot {
  width: 6pt;
  height: 6pt;
  border-radius: 50%;
  background: var(--c-yellow);
}

.cover-footer {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  font-size: 10pt;
  color: rgba(255,255,255,0.7);
  border-top: 1px solid rgba(255,255,255,0.12);
  padding-top: 14pt;
}
.cover-footer strong { color: #fff; font-weight: 700; }

/* ========== ОСНОВНОЙ КОНТЕНТ ========== */

h1 {
  font-size: 22pt;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--c-dark);
  margin: 0 0 10pt;
  padding: 14pt 16pt;
  background: var(--c-dark);
  color: #fff;
  border-radius: 6pt;
  border-left: 6pt solid var(--c-yellow);
  page-break-after: avoid;
}

h2 {
  font-size: 16pt;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--c-dark);
  margin: 22pt 0 10pt;
  padding-left: 12pt;
  border-left: 5pt solid var(--c-yellow);
  page-break-after: avoid;
}

h3 {
  font-size: 13pt;
  font-weight: 700;
  color: var(--c-dark);
  margin: 16pt 0 6pt;
  page-break-after: avoid;
}
h3::before {
  content: "■";
  color: var(--c-yellow);
  margin-right: 6pt;
}

h4 {
  font-size: 11.5pt;
  font-weight: 700;
  color: var(--c-dark);
  margin: 12pt 0 4pt;
}

p { margin: 0 0 8pt; }
ul, ol { margin: 0 0 8pt; padding-left: 20pt; }
li { margin-bottom: 3pt; }
li::marker { color: var(--c-yellow); }

strong { color: var(--c-dark); font-weight: 700; }
em { color: var(--c-muted); }

a { color: var(--c-orange); text-decoration: none; font-weight: 500; }

hr {
  border: none;
  border-top: 2px solid var(--c-light);
  margin: 18pt 0;
}

code {
  font-family: "SF Mono", Monaco, "Courier New", monospace;
  font-size: 9.5pt;
  background: var(--c-light);
  padding: 1pt 4pt;
  border-radius: 3pt;
}

blockquote {
  margin: 8pt 0;
  padding: 12pt 16pt;
  background: #FFF8E5;
  border-left: 4px solid var(--c-yellow);
  border-radius: 4pt;
  color: #582A06;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 10pt 0 14pt;
  font-size: 10pt;
  page-break-inside: avoid;
  border-radius: 6pt;
  overflow: hidden;
  border: 1px solid var(--c-light);
}
th {
  text-align: left;
  font-weight: 700;
  background: var(--c-dark);
  color: #fff;
  padding: 7pt 10pt;
  font-size: 10pt;
}
td {
  padding: 6pt 10pt;
  border-bottom: 1px solid var(--c-light);
  vertical-align: top;
}
table tr:last-child td { border-bottom: none; }
table tr:nth-child(even) td { background: #FAFAFA; }

/* Подсветка строки «Итого» в таблицах цен */
table tr:has(td strong:first-child:nth-of-type(1)) td { /* fallback */ }

/* Эмодзи и иконки в заголовках */
h1 em, h2 em, h3 em { font-style: normal; color: var(--c-yellow); }
</style>
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{cover}
{body}
</body>
</html>"""


COVER_TEMPLATE = """
<div class="cover">
  <div>
    <div class="cover-logo">
      <span class="accent">АНАНАС</span> МАРКЕТИНГ
      <div class="cover-logo-sub">Системный маркетинг для сервисного бизнеса</div>
    </div>
  </div>

  <div>
    <div class="cover-eyebrow">Коммерческое предложение · 02.06.2026</div>
    <h1 class="cover-title">{cover_title}</h1>
    <p class="cover-subtitle">{cover_subtitle}</p>
    <div class="cover-stages">
      <span class="cover-stage"><span class="dot"></span> Маркетинговая база</span>
      <span class="cover-stage"><span class="dot"></span> Сайт под SEO</span>
      <span class="cover-stage"><span class="dot"></span> Трафик · Я.Карты + Я.Директ</span>
    </div>
  </div>

  <div class="cover-footer">
    <div>
      <strong>Владимир Тарасов</strong><br>
      Стратегия и ведение проекта<br>
      <span style="color:rgba(255,255,255,0.55)">@volodtarasov · volodtarasov@gmail.com</span>
    </div>
    <div style="text-align:right">
      <strong>Срок: 5 месяцев</strong><br>
      <span style="color:rgba(255,255,255,0.55)">Стоимость первого слоя</span><br>
      <span style="color:#FFBA24; font-weight:700; font-size:14pt">970 000 ₽</span>
    </div>
  </div>
</div>
"""


def md_to_html(md_text: str) -> str:
    # Убрать YAML frontmatter
    if md_text.startswith("---"):
        end = md_text.find("\n---", 3)
        if end != -1:
            md_text = md_text[end + 4:].lstrip()
    # Убрать первый H1 (он будет в обложке)
    md_text = re.sub(r"^# .*\n", "", md_text, count=1)
    # Убрать второй H2 (подзаголовок-описание) — он тоже на обложке
    md_text = re.sub(r"^## .*\n", "", md_text, count=1)
    md_text = re.sub(r"^### .*\n", "", md_text, count=1)
    return md.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    )


async def main(in_path: Path, out_path: Path):
    md_text = in_path.read_text(encoding="utf-8")

    # Параметры обложки — задаются прямо здесь под Карнелию
    cover_title = "Маркетинг и трафик для сети химчисток «Карнелия»"
    cover_subtitle = "Запускаем систему привлечения клиентов: позиционирование, сеошный сайт, трафик через Яндекс.Директ и Карты. Поэтапно, с прозрачной аналитикой и точками решения после каждого этапа."

    body = md_to_html(md_text)
    cover = COVER_TEMPLATE.format(
        cover_title=cover_title,
        cover_subtitle=cover_subtitle,
    )
    html = HTML_TEMPLATE.format(
        title=in_path.stem,
        css=CSS,
        cover=cover,
        body=body,
    )

    html_path = out_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="load")
        await page.wait_for_timeout(1500)  # подождать Manrope с CDN
        await page.pdf(
            path=str(out_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        await browser.close()

    print(f"✓ PDF saved: {out_path}")
    print(f"  HTML: {html_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: md-to-pdf.py <input.md> <output.pdf>")
        sys.exit(1)
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2])))
