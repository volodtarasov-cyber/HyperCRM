"""Снимает конкретную секцию по селектору."""
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = ROOT / ".tools/snapshots"
URL = (ROOT / "projects/detailing-samara/marketing/film-landing/index.html").as_uri()


async def main(selector: str, out_name: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            locale="ru-RU",
        )
        page = await context.new_page()
        await page.goto(URL, wait_until="load")
        await page.wait_for_timeout(800)
        el = await page.query_selector(selector)
        if not el:
            print(f"⚠️ selector {selector} not found")
            return
        await el.scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        await el.screenshot(path=str(OUT_DIR / out_name))
        await browser.close()
        print(f"✓ {out_name}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
