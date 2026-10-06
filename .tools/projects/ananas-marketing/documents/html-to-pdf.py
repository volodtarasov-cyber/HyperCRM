"""
Пересборка A4-документа «Ананас Маркетинг» из HTML в PDF + проверка вёрстки.

Использование:
    python html-to-pdf.py <input.html> [output.pdf]
    python html-to-pdf.py <input.html> --check      # только проверить, PDF не писать
    python html-to-pdf.py <input.html> --shots DIR  # плюс PNG каждой полосы

Документ должен состоять из блоков <div class="page"> высотой 297мм.
Печатные правила (margin: 0, отсутствие тени) обязаны стоять ПОСЛЕДНИМИ
в <style> — медиазапрос не добавляет специфичности, решает порядок.

Что проверяется — три ошибки, на которых documenты ломались раньше:
  1. Число страниц в PDF совпадает с числом блоков .page.
     Не совпало — значит полоса не влезает и каждая вторая страница пустая.
  2. Содержимое не вылезает за нижнюю границу полосы.
  3. Декор (.pineapple, .crown, .cover-pineapple) не пересекает текст —
     включая голые текстовые узлы внутри плашек.
"""
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

DECOR = ".pineapple, .crown, .cover-pineapple"

# перелив декора за край полосы — это выпуск под обрез, он гасится overflow: hidden
BLEED_OK = ("pineapple", "crown")

OVERFLOW_JS = """
e => {
    const r = e.getBoundingClientRect();
    let worst = 0, who = '';
    for (const c of e.querySelectorAll('*')) {
        if (c.classList.contains('foot')) continue;
        const cr = c.getBoundingClientRect();
        if (cr.height === 0) continue;
        const d = cr.bottom - r.bottom;
        if (d > worst) { worst = d; who = c.className || c.tagName; }
    }
    return {over: Math.round(worst), who: String(who)};
}
"""

OVERLAP_JS = """
(sel) => {
    const out = [];
    const textRects = (root) => {
        const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const res = [];
        let n;
        while (n = w.nextNode()) {
            if (!n.textContent.trim()) continue;
            const range = document.createRange();
            range.selectNodeContents(n);
            for (const rect of range.getClientRects())
                if (rect.width > 1 && rect.height > 1)
                    res.push({rect, text: n.textContent.trim().slice(0, 40)});
        }
        return res;
    };
    document.querySelectorAll(sel).forEach(img => {
        const ir = img.getBoundingClientRect();
        for (const {rect: r, text} of textRects(img.closest('.page'))) {
            const ox = Math.min(ir.right, r.right) - Math.max(ir.left, r.left);
            const oy = Math.min(ir.bottom, r.bottom) - Math.max(ir.top, r.top);
            if (ox > 1 && oy > 1)
                out.push({img: String(img.className), text,
                          ox: Math.round(ox), oy: Math.round(oy)});
        }
    });
    return out;
}
"""


def pdf_page_count(path: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", path.read_bytes()))


async def run(src: Path, out: Path | None, shots: Path | None) -> int:
    problems = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        page = await browser.new_page(viewport={"width": 840, "height": 1188},
                                      device_scale_factor=2)
        await page.goto(src.resolve().as_uri())
        await page.wait_for_timeout(3000)
        await page.emulate_media(media="print")
        await page.wait_for_timeout(400)

        blocks = await page.locator(".page").count()
        if blocks == 0:
            print("В документе нет блоков .page — это не полосовой макет.")
            await browser.close()
            return 1
        print(f"блоков .page: {blocks}")

        for i in range(blocks):
            el = page.locator(".page").nth(i)
            info = await el.evaluate(OVERFLOW_JS)
            bleed = any(k in info["who"] for k in BLEED_OK)
            if info["over"] > 2 and not bleed:
                problems.append(f"стр.{i + 1}: содержимое вылезает на {info['over']}px "
                                f"({info['who'][:32]})")
            if shots:
                shots.mkdir(parents=True, exist_ok=True)
                await el.screenshot(path=str(shots / f"{src.stem}-{i + 1}.png"))

        for x in await page.evaluate(OVERLAP_JS, DECOR):
            problems.append(f"декор {x['img']} перекрывает текст "
                            f"({x['ox']}×{x['oy']}px): «{x['text']}»")

        if out:
            await page.pdf(path=str(out), format="A4", print_background=True,
                           margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        await browser.close()

    if out:
        pages = pdf_page_count(out)
        print(f"страниц в PDF: {pages}")
        if pages != blocks:
            problems.append(
                f"в PDF {pages} страниц вместо {blocks} — полоса не влезает в A4. "
                f"Проверь, что печатные правила .page стоят последними в <style>: "
                f"margin: 0, height: 296mm, без box-shadow."
            )

    if problems:
        print("\nПРОБЛЕМЫ ВЁРСТКИ:")
        for x in problems:
            print("  •", x)
        return 1
    print("вёрстка чистая")
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return 2

    src = Path(args[0])
    if not src.exists():
        print(f"нет файла: {src}")
        return 2

    shots = None
    if "--shots" in args:
        shots = Path(args[args.index("--shots") + 1])

    if "--check" in args:
        out = None
    else:
        rest = [a for a in args[1:] if not a.startswith("--")]
        rest = [a for a in rest if shots is None or Path(a) != shots]
        out = Path(rest[0]) if rest else src.with_suffix(".pdf")

    return asyncio.run(run(src, out, shots))


if __name__ == "__main__":
    sys.exit(main())
