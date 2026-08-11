"""
Конвертер Markdown → PDF в фирменном стиле «Ананас Маркетинг» — обложка под демо «Скрининг».
Использование: python md-to-pdf-screening.py <input.md> <output.pdf>
Стиль (CSS) переиспользуется из md-to-pdf.py; меняется только обложка.
"""
import sys
import asyncio
import re
import importlib.util
from pathlib import Path
import markdown as md
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent

# переиспользуем CSS и HTML_TEMPLATE из соседнего md-to-pdf.py
spec = importlib.util.spec_from_file_location("base_pdf", HERE / "md-to-pdf.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

CSS = base.CSS
HTML_TEMPLATE = base.HTML_TEMPLATE

COVER = """
<div class="cover">
  <div>
    <div class="cover-logo">
      <span class="accent">АНАНАС</span> МАРКЕТИНГ
      <div class="cover-logo-sub">Системный маркетинг для сервисного бизнеса</div>
    </div>
  </div>

  <div>
    <div class="cover-eyebrow">Демонстрация услуги · Образец отчёта</div>
    <h1 class="cover-title">Скрининг бизнеса<br>и рынка</h1>
    <p class="cover-subtitle">Что вы получаете до того, как потратите первый рубль на рекламу: главное ограничение бизнеса, карта клиентов, путь к покупке с точкой перелома и план действий по приоритету.</p>
    <div class="cover-stages">
      <span class="cover-stage"><span class="dot"></span> Главное ограничение</span>
      <span class="cover-stage"><span class="dot"></span> Карта клиентов и пути</span>
      <span class="cover-stage"><span class="dot"></span> План по приоритету</span>
    </div>
  </div>

  <div class="cover-footer">
    <div>
      <strong>Владимир Тарасов</strong><br>
      Стратегия и ведение проекта<br>
      <span style="color:rgba(255,255,255,0.55)">@volodtarasov · volodtarasov@gmail.com</span>
    </div>
    <div style="text-align:right">
      <strong>Первый шаг проекта</strong><br>
      <span style="color:rgba(255,255,255,0.55)">До вложений в рекламу и сайт</span><br>
      <span style="color:#FFBA24; font-weight:700; font-size:14pt">Что вы получите →</span>
    </div>
  </div>
</div>
"""


def md_to_html(md_text: str) -> str:
    if md_text.startswith("---"):
        end = md_text.find("\n---", 3)
        if end != -1:
            md_text = md_text[end + 4:].lstrip()
    # Убираем H1 и первый H2/H3 — они вынесены на обложку
    md_text = re.sub(r"^# .*\n", "", md_text, count=1)
    md_text = re.sub(r"^## .*\n", "", md_text, count=1)
    return md.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    )


async def main(in_path: Path, out_path: Path):
    md_text = in_path.read_text(encoding="utf-8")
    body = md_to_html(md_text)
    html = HTML_TEMPLATE.format(title=in_path.stem, css=CSS, cover=COVER, body=body)

    html_path = out_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="load")
        await page.wait_for_timeout(1500)
        await page.pdf(
            path=str(out_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        await browser.close()

    print(f"✓ PDF saved: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: md-to-pdf-screening.py <input.md> <output.pdf>")
        sys.exit(1)
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2])))
