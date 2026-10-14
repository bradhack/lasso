"""Plays Lasso like a fan in a phone-sized browser: onboard, open a live match, make calls, collect results.

    python web/e2e/play.py [base_url] [out_dir]
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e-shots")
MATCH = "S5-MD07-03"


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                        is_mobile=True, has_touch=True)
        page = await ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(BASE)
        await page.fill("input[autocomplete=nickname]", "Brad")
        await page.click('button[title="Eastholme Rangers"]')
        await page.click("text=Let's go")
        await page.wait_for_timeout(1500)
        await page.goto(f"{BASE}/#/match/{MATCH}")
        calls = 0
        for i in range(120):
            await page.wait_for_timeout(1000)
            opt = page.locator(".opt:not([disabled])").first
            if calls < 6 and await opt.count():
                try:
                    await page.evaluate("document.querySelector('.callit').scrollIntoView({block: 'center'})")
                    await opt.tap(timeout=3000)
                    await page.wait_for_timeout(250)
                    if calls == 0:
                        await page.screenshot(path=str(OUT / "a_pick.png"))
                    await page.locator(".callit .cta").tap(timeout=3000)
                    calls += 1
                    await page.wait_for_timeout(400)
                    if calls == 1:
                        await page.screenshot(path=str(OUT / "b_locked.png"))
                except Exception as e:  # noqa: BLE001  (market may close mid-tap)
                    print("tap skipped:", str(e).splitlines()[0])
            toast = await page.query_selector(".toast.win, .toast.card")
            if toast:
                await page.screenshot(path=str(OUT / f"c_toast_{i}.png"))
            if i in (30, 60, 90):
                await page.screenshot(path=str(OUT / f"d_match_{i}.png"))
        await page.goto(f"{BASE}/#/me")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUT / "e_me.png"), full_page=True)
        await page.goto(f"{BASE}/#/cards")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(OUT / "f_cards.png"))
        overlay = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await overlay.goto(f"{BASE}/#/overlay/{MATCH}/en")
        await overlay.wait_for_timeout(3000)
        await overlay.screenshot(path=str(OUT / "g_overlay.png"))
        print("calls placed:", calls, "page errors:", errors[:3])
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
