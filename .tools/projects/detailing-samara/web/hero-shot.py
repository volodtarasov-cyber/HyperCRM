"""Снимает только верхний viewport (hero) без скролла."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = ROOT / ".tools/snapshots"
URL = (ROOT / "projects/detailing-samara/marketing/film-landing/index.html").as_uri()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)

        # desktop
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            locale="ru-RU",
        )
        page = await ctx.new_page()
        await page.goto(URL, wait_until="load")
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(OUT_DIR / "landing-hero-only.png"), full_page=False)
        await ctx.close()

        # mobile
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="ru-RU",
        )
        page = await ctx.new_page()
        await page.goto(URL, wait_until="load")
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(OUT_DIR / "landing-hero-mobile.png"), full_page=False)
        await ctx.close()

        await browser.close()
        print("✓ hero (desktop + mobile) saved")


asyncio.run(main())
