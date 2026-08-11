"""Извлекает логотип Ananasm со страницы ananasm.ru."""
import asyncio
import re
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = ROOT / "team/assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)
URL = "https://ananasm.ru/ananasavito"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium", headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="load")
        await page.wait_for_timeout(2000)

        # Все картинки с упоминанием "logo" или "ananas" в URL
        srcs = await page.evaluate("""
            () => {
              const imgs = [...document.querySelectorAll('img')];
              return imgs.map(i => ({
                src: i.currentSrc || i.src,
                alt: i.alt,
                w: i.naturalWidth,
                h: i.naturalHeight,
              })).filter(i => i.src && (
                /logo|ananas|ananasm/i.test(i.src) ||
                /логотип|ананас/i.test(i.alt)
              ));
            }
        """)
        # Также — bg-images через computed style на хэдере
        bg_images = await page.evaluate("""
            () => {
              const els = [...document.querySelectorAll('header *, [class*="header" i] *, [class*="logo" i] *')];
              const out = [];
              for (const el of els) {
                const bg = getComputedStyle(el).backgroundImage;
                const m = /url\\(['"]?(.+?)['"]?\\)/.exec(bg);
                if (m) out.push(m[1]);
              }
              return [...new Set(out)];
            }
        """)
        print("=== Image candidates ===")
        for i, s in enumerate(srcs):
            print(f"  [{i}] {s['w']}x{s['h']}  {s['src']}  alt='{s['alt']}'")
        print("=== Background image candidates ===")
        for u in bg_images:
            print(f"  {u}")

        # Скачать топ-кандидата
        candidates = [s["src"] for s in srcs] + bg_images
        # фильтр — только svg/png, и желательно с "logo"
        priority = sorted(
            candidates,
            key=lambda u: (
                0 if u.endswith(".svg") else 1,
                0 if "logo" in u.lower() else 1,
                len(u),
            ),
        )
        for url in priority[:3]:
            if not url.startswith("http"):
                continue
            ext = ".svg" if url.lower().endswith(".svg") else ".png"
            fname = OUT_DIR / f"ananasm-logo{ext}"
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    fname.write_bytes(r.read())
                print(f"✓ saved: {fname} ← {url}")
                break
            except Exception as e:
                print(f"⚠ failed {url}: {e}")

        await browser.close()


asyncio.run(main())
