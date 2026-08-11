"""Снимает первые страницы PDF как PNG для предпросмотра."""
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

TOOLS_DIR = Path(__file__).resolve().parents[2]
OUT_DIR = TOOLS_DIR / "snapshots"


async def main(pdf_path: Path):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        ctx = await browser.new_context(viewport={"width": 900, "height": 1200})
        page = await ctx.new_page()
        await page.goto(f"file://{pdf_path}", wait_until="load")
        await page.wait_for_timeout(1500)
        await page.screenshot(
            path=str(OUT_DIR / "pdf-preview.png"),
            full_page=False,
        )
        # подкрутим
        await page.evaluate("window.scrollTo(0, 1000)")
        await page.wait_for_timeout(500)
        await page.screenshot(
            path=str(OUT_DIR / "pdf-preview-scrolled.png"),
            full_page=False,
        )
        await browser.close()
        print("✓ saved")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
