"""Снимок только hero страницы Ananasm + сбор палитры."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".tools/snapshots"

URL = "https://ananasm.ru/ananasavito"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(URL, wait_until="load")
        await page.wait_for_timeout(2000)
        # Hero
        await page.screenshot(path=str(OUT / "ananasm-hero.png"), full_page=False)
        # Прокрутить
        await page.evaluate("window.scrollTo(0, 900)")
        await page.wait_for_timeout(700)
        await page.screenshot(path=str(OUT / "ananasm-2.png"), full_page=False)
        await page.evaluate("window.scrollTo(0, 1800)")
        await page.wait_for_timeout(700)
        await page.screenshot(path=str(OUT / "ananasm-3.png"), full_page=False)

        # Достать палитру и шрифты через JS
        meta = await page.evaluate("""
            () => {
              const body = document.body;
              const all = document.querySelectorAll('h1, h2, h3, button, a, p, div');
              const colors = new Set();
              const bgcolors = new Set();
              const fontsTitle = new Set();
              const fontsBody = new Set();
              all.forEach(el => {
                const cs = getComputedStyle(el);
                colors.add(cs.color);
                bgcolors.add(cs.backgroundColor);
                if (el.tagName.match(/^H[1-3]$/)) fontsTitle.add(cs.fontFamily);
                if (el.tagName === 'P') fontsBody.add(cs.fontFamily);
              });
              return {
                colors: [...colors].slice(0, 12),
                bgcolors: [...bgcolors].slice(0, 12),
                fontsTitle: [...fontsTitle].slice(0, 6),
                fontsBody: [...fontsBody].slice(0, 6),
                bodyBg: getComputedStyle(body).backgroundColor,
              };
            }
        """)
        import json
        print(json.dumps(meta, ensure_ascii=False, indent=2))

        await browser.close()

asyncio.run(main())
