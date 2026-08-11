"""
Снимает скриншоты страницы на desktop и mobile.
Использование: python snapshot.py <url> <output_prefix>
"""
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

TOOLS_DIR = Path(__file__).resolve().parents[2]
OUT_DIR = TOOLS_DIR / "snapshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def safe_goto(page, url: str, label: str):
    """Несколько стратегий загрузки, чтобы пережить медленные/защищённые сайты."""
    for strategy in ("load", "domcontentloaded", "commit"):
        try:
            await page.goto(url, wait_until=strategy, timeout=20000)
            print(f"  · {label}: loaded via {strategy}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"  · {label} {strategy} failed: {type(e).__name__}", file=sys.stderr)
            continue
    return False


async def shoot(url: str, prefix: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chromium",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        for label, viewport, is_mobile, ua in [
            (
                "desktop",
                {"width": 1440, "height": 900},
                False,
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ),
            (
                "mobile",
                {"width": 390, "height": 844},
                True,
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            ),
        ]:
            context = await browser.new_context(
                viewport=viewport,
                device_scale_factor=2 if is_mobile else 1,
                is_mobile=is_mobile,
                has_touch=is_mobile,
                user_agent=ua,
                locale="ru-RU",
                timezone_id="Europe/Samara",
            )
            page = await context.new_page()
            ok = await safe_goto(page, url, label)
            if not ok:
                print(f"⚠️ {label}: all strategies failed, snapping current state", file=sys.stderr)
            # дождаться рендера
            await page.wait_for_timeout(3500)
            # скролл — чтобы догрузились ленивые картинки
            try:
                await page.evaluate("""
                    () => new Promise(resolve => {
                        let total = 0;
                        const step = 400;
                        const interval = setInterval(() => {
                            window.scrollBy(0, step);
                            total += step;
                            if (total >= document.body.scrollHeight) {
                                clearInterval(interval);
                                window.scrollTo(0, 0);
                                setTimeout(resolve, 500);
                            }
                        }, 150);
                    })
                """)
            except Exception:
                pass
            await page.wait_for_timeout(1500)
            out = OUT_DIR / f"{prefix}-{label}.png"
            await page.screenshot(path=str(out), full_page=True)
            print(f"  ✓ {label} → {out.name}", file=sys.stderr)
            await context.close()

        await browser.close()
        print(f"✓ {prefix}: complete")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: snapshot.py <url> <prefix>")
        sys.exit(1)
    asyncio.run(shoot(sys.argv[1], sys.argv[2]))
