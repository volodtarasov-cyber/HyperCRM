"""
Простой Markdown → PDF в фирменном стиле Ананас Маркетинг, БЕЗ обложки КП.
Для рабочих документов: брифы, опросники, чек-листы, отчёты.

Использование:
    python md-to-pdf-simple.py <input.md> <output.pdf> [--title "Заголовок документа"]
"""
import sys
import asyncio
import re
import argparse
from pathlib import Path
from typing import Optional
import markdown as md
from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[4]
BRAND_CSS_PATH = ROOT / "team/assets/ananas-marketing-brand.css"
BRAND_CSS = BRAND_CSS_PATH.read_text(encoding="utf-8") if BRAND_CSS_PATH.exists() else ""


CSS = BRAND_CSS + """
:root {
  --c-dark: #2B223A;
  --c-yellow: #FFBA24;
  --c-orange: #F26B1F;
  --c-text: #2A2A2A;
  --c-muted: #6B6B6B;
  --c-light: #F1F1F1;
}

@page {
  size: A4;
  margin: 18mm 16mm 22mm 16mm;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-family: 'Manrope', sans-serif;
    font-size: 9pt;
    color: #999;
  }
}

* { box-sizing: border-box; }

body {
  font-family: 'Manrope', -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.55;
  color: var(--c-text);
  margin: 0;
  padding: 0;
  background: #fff;
}

/* ========== Шапка документа ========== */
.doc-header {
  border-bottom: 3px solid var(--c-yellow);
  padding-bottom: 10pt;
  margin-bottom: 18pt;
}
.doc-header .brand {
  font-size: 9pt;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--c-muted);
}
.doc-header .brand .accent { color: var(--c-orange); }
.doc-header .title {
  font-size: 22pt;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--c-dark);
  margin: 6pt 0 0;
  line-height: 1.15;
  background: none;
  padding: 0;
  border: none;
  border-radius: 0;
}

/* ========== Контент ========== */

h1 {
  font-size: 18pt;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--c-dark);
  margin: 0 0 10pt;
  padding: 10pt 14pt;
  background: var(--c-dark);
  color: #fff;
  border-radius: 6pt;
  border-left: 6pt solid var(--c-yellow);
  page-break-after: avoid;
}

h2 {
  font-size: 14pt;
  font-weight: 800;
  color: var(--c-dark);
  margin: 18pt 0 8pt;
  padding-left: 10pt;
  border-left: 4pt solid var(--c-yellow);
  page-break-after: avoid;
}

h3 {
  font-size: 12pt;
  font-weight: 700;
  color: var(--c-dark);
  margin: 14pt 0 5pt;
  page-break-after: avoid;
}
h3::before {
  content: "■";
  color: var(--c-yellow);
  margin-right: 5pt;
}

h4 {
  font-size: 11pt;
  font-weight: 700;
  color: var(--c-dark);
  margin: 10pt 0 4pt;
}

p { margin: 0 0 7pt; }
ul, ol { margin: 0 0 7pt; padding-left: 18pt; }
li { margin-bottom: 2pt; }
li::marker { color: var(--c-yellow); }

strong { color: var(--c-dark); font-weight: 700; }
em { color: var(--c-muted); }

a { color: var(--c-orange); text-decoration: none; font-weight: 500; }

hr {
  border: none;
  border-top: 2px solid var(--c-light);
  margin: 14pt 0;
}

code {
  font-family: "SF Mono", Monaco, "Courier New", monospace;
  font-size: 9pt;
  background: var(--c-light);
  padding: 1pt 4pt;
  border-radius: 3pt;
}

blockquote {
  margin: 8pt 0;
  padding: 10pt 14pt;
  background: #FFF8E5;
  border-left: 4px solid var(--c-yellow);
  border-radius: 4pt;
  color: #582A06;
  font-size: 10pt;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 8pt 0 12pt;
  font-size: 9.5pt;
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
  padding: 6pt 9pt;
  font-size: 9.5pt;
}
td {
  padding: 5pt 9pt;
  border-bottom: 1px solid var(--c-light);
  vertical-align: top;
}
table tr:last-child td { border-bottom: none; }
table tr:nth-child(even) td { background: #FAFAFA; }
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="doc-header">
  <div class="brand">{brand}</div>
  <h1 class="title">{title}</h1>
</div>
{body}
</body>
</html>"""


def md_to_html(md_text: str) -> str:
    # Снять YAML frontmatter
    if md_text.startswith("---"):
        end = md_text.find("\n---", 3)
        if end != -1:
            md_text = md_text[end + 4:].lstrip()
    # Снять первый H1 (он в шапке документа)
    md_text = re.sub(r"^# .*\n", "", md_text, count=1)
    return md.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    )


def extract_title(md_text: str) -> str:
    if md_text.startswith("---"):
        end = md_text.find("\n---", 3)
        if end != -1:
            md_text = md_text[end + 4:].lstrip()
    m = re.search(r"^# (.+)$", md_text, re.MULTILINE)
    return m.group(1).strip() if m else "Документ"


DEFAULT_BRAND = '<span class="accent">АНАНАС</span> МАРКЕТИНГ · рабочий документ'


async def main(in_path: Path, out_path: Path, title_override: Optional[str], brand: Optional[str]):
    md_text = in_path.read_text(encoding="utf-8")
    title = title_override or extract_title(md_text)
    body = md_to_html(md_text)
    html = HTML_TEMPLATE.format(title=title, css=CSS, body=body, brand=brand or DEFAULT_BRAND)

    html_path = out_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="load")
        await page.wait_for_timeout(1200)
        await page.pdf(
            path=str(out_path),
            format="A4",
            print_background=True,
            margin={"top": "18mm", "bottom": "22mm", "left": "16mm", "right": "16mm"},
            display_header_footer=False,
        )
        await browser.close()

    print(f"✓ PDF saved: {out_path}")
    print(f"  HTML: {html_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to input markdown file")
    ap.add_argument("output", help="Path to output PDF")
    ap.add_argument("--title", help="Override document title", default=None)
    ap.add_argument("--brand", help="Override header brand line (HTML allowed). Default — Ананас Маркетинг.", default=None)
    args = ap.parse_args()
    asyncio.run(main(Path(args.input), Path(args.output), args.title, args.brand))
