#!/usr/bin/env python3
"""Real-browser responsive smoke checks of deployed HTML artifact, no external network."""
from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil

from playwright.async_api import async_playwright

ROUTES = [
    ("home", "index.html"),
    ("archive", "archive/index.html"),
    ("archive-issue", "archive/001/index.html"),
    ("collection", "collection/index.html"),
    ("workshop", "workshop/index.html"),
    ("workshop-maps", "workshop/maps/index.html"),
    ("repair-map-seams", "details/pochemu-raskleivaetsya-kontrabas-shov-i-treschina/index.html"),
    ("repair-map-neck", "details/geometriya-grifa-kontrabasa-sheyka-nakladka/index.html"),
    ("repair-map-inspection", "details/starinnyy-kontrabas-pered-remontom-osmotr-i-istoriya/index.html"),
    ("meeting", "meeting/index.html"),
    ("experience", "experience/index.html"),
    ("delivery", "delivery/index.html"),
    ("access", "kupit-masterovoy-kontrabas-v-moskve/index.html"),
    ("knowledge", "details/masterovoy-kontrabas/index.html"),
    ("essay", "details/vybor-kontrabasa-kak-znakomstvo/index.html"),
    ("model", "models/eastman-vb305/index.html"),
    ("size-compare", "kontrabas-1-2-ili-3-4/index.html"),
    ("sensor-n0", "vhod/familiar-instruments/kontrabas-musima-kupit-v-moskve/index.html"),
    ("sensor-long", "vhod/ergonomic-neck/kontrabas-posle-zameny-nakladki-stal-neudoben/index.html"),
    ("standalone", "kupit-kontrabas-v-moskve/index.html"),
]
WIDTHS = (390, 760, 820, 1366)


async def run(site: Path, output: Path) -> dict:
    chrome = os.environ.get("CHROME_BIN") or shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        raise RuntimeError("A Chromium/Chrome executable is required for responsive tests")
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chrome, headless=True, args=[
            "--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
        try:
            for width in WIDTHS:
                page = await browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
                for name, route in ROUTES:
                    await page.goto((site / route).resolve().as_uri(), wait_until="load")
                    await page.evaluate("document.fonts.ready")
                    dims = await page.evaluate("""() => ({
                        width: document.documentElement.clientWidth,
                        scroll: document.documentElement.scrollWidth,
                        css: !!document.querySelector('link[rel="stylesheet"]')
                    })""")
                    if await page.locator(".contact-icons").count():
                        icons = await page.locator(".contact-icons").evaluate("""(container) => {
                            const tg = container.querySelector('a[aria-label="Telegram"]');
                            const wa = container.querySelector('a[aria-label="WhatsApp"]');
                            const max = container.querySelector('.max-contact-pending');
                            if (!tg || !wa || !max) return { missing: true };
                            const measured = (el) => {
                                const rect = el.getBoundingClientRect();
                                return { width: rect.width, centerY: rect.y + rect.height / 2,
                                         iconWidth: el.querySelector('svg').getBoundingClientRect().width,
                                         color: getComputedStyle(el).color };
                            };
                            const style = getComputedStyle(max);
                            return {
                                telegram: measured(tg), whatsapp: measured(wa), max: measured(max),
                                border: style.borderTopWidth,
                                radius: style.borderTopLeftRadius,
                                background: style.backgroundColor,
                                isSpan: max.tagName === 'SPAN',
                                bareGlyph: !!max.querySelector('svg path') && !max.querySelector('svg circle'),
                                activeMaxLink: !!container.querySelector('a[aria-label="MAX"]')
                            };
                        }""")
                        if icons.get("missing") or not icons["isSpan"] or not icons["bareGlyph"] or icons["activeMaxLink"]:
                            raise AssertionError(f"{name}: MAX must be a bare inert glyph: {icons}")
                        if icons["border"] != "0px" or icons["radius"] != "0px":
                            raise AssertionError(f"{name}: MAX has an unwanted square frame: {icons}")
                        for prop in ("width", "iconWidth", "centerY"):
                            target = icons["telegram"][prop]
                            if abs(icons["max"][prop] - target) > 0.5:
                                raise AssertionError(f"{name} {width}px: MAX {prop} differs from Telegram: {icons}")
                        if icons["max"]["color"] != icons["telegram"]["color"]:
                            raise AssertionError(f"{name}: MAX is not monochrome like Telegram")
                    if name == "home":
                        if not await page.locator('link[href="assets/visual/scene.css"]').count():
                            raise AssertionError("Photographic shell stylesheet missing on homepage")
                        if await page.locator(".cb-hero h1").count() != 1:
                            raise AssertionError("Cinematic home must retain one meaningful H1")
                        await page.wait_for_function(
                            "() => { const img=document.querySelector('#cb-hero-image');"
                            " return img && img.complete && img.naturalWidth > 0 }", timeout=10000)
                        mood = page.locator("#cb-atmosphere")
                        await mood.click()
                        if await mood.get_attribute("aria-pressed") != "true":
                            raise AssertionError("Home's light switch did not activate")
                        await page.wait_for_function(
                            "() => document.querySelector('#cb-hero-image')?.currentSrc.includes('room-evening.webp')",
                            timeout=10000)
                        await mood.click()
                        if await mood.get_attribute("aria-pressed") != "false":
                            raise AssertionError("Home's light switch did not reset")
                    if name == "archive":
                        banner=page.locator(".scene-banner img")
                        if await banner.count() != 1:
                            raise AssertionError("Archive lacks one photographic edition cover")
                        await banner.evaluate("(img) => img.loading = 'eager'")
                        await page.wait_for_function(
                            "() => { const img=document.querySelector('.scene-banner img');"
                            " return !!img && img.complete && img.naturalWidth > 0 }", timeout=12000)
                        overflow_x = await banner.evaluate("(img) => img.getBoundingClientRect().width")
                        if overflow_x > width:
                            raise AssertionError("Archive illustration must fit viewport")
                    if name in {"archive", "archive-issue"}:
                        visual_loaded = await page.evaluate(
                            "() => [...document.styleSheets].some(s => s.href && s.href.endsWith('/assets/visual/scene.css'))")
                        if not visual_loaded:
                            raise AssertionError(f"{name}: shared photographic CSS did not load")
                    if name in {"collection", "workshop", "meeting", "experience", "delivery"}:
                        image = page.locator(".scene-banner img")
                        if await image.count() != 1:
                            raise AssertionError(f"{name}: expected one photographic institutional banner")
                        await image.evaluate("(img)=>img.loading='eager'")
                        await page.wait_for_function(
                            "() => document.querySelector('.scene-banner img')?.complete"
                            " && document.querySelector('.scene-banner img')?.naturalWidth > 0",
                            timeout=12000)
                    if name in {"access", "standalone", "sensor-n0", "sensor-long", "size-compare", "knowledge", "essay", "model"}:
                        bg = await page.locator(".master-lead").evaluate(
                            "(el) => getComputedStyle(el).backgroundImage")
                        if ".webp" not in bg:
                            raise AssertionError(f"{name}: photographic visual skin not applied: {bg}")
                    if name == "home":
                        border_widths = await page.locator(".master-directions > a").evaluate_all(
                            "(items) => items.map(item => parseFloat(getComputedStyle(item).borderLeftWidth))")
                        if len(border_widths) != 3:
                            raise AssertionError("Homepage must retain three independent linked spaces")
                        if width > 760 and any(border < 1 for border in border_widths[1:]):
                            raise AssertionError(f"Missing desktop column divider at {width}px: {border_widths}")
                        if width <= 760 and any(border > 0 for border in border_widths):
                            raise AssertionError(f"Spurious mobile column divider at {width}px: {border_widths}")
                    if name in {"collection", "workshop", "meeting"}:
                        redundant = await page.locator("nav.master-links").count()
                        if redundant:
                            raise AssertionError(f"{name}: subject/navigation grid belongs to podshivka")
                    if name in {"access", "standalone", "sensor-n0", "sensor-long", "size-compare"}:
                        if await page.locator(".entry-router .deck,.entry-router .entry-signal,.entry-router .n0-return").count():
                            raise AssertionError(f"{name}: redundant text inserted in the short entry")
                        title = await page.locator(".entry-router .master-lead").bounding_box()
                        phone = await page.locator(".entry-router .contact-block").bounding_box()
                        if not title or not phone or phone["y"] <= title["y"] + title["height"]:
                            raise AssertionError(f"{name}: contact must follow the short request headline")
                        if width >= 820 and title["y"] < 90:
                            raise AssertionError(f"{name}: short publication loses its top breathing room")
                        if await page.locator(".master-footer a[href]").count() != 2:
                            raise AssertionError(f"{name}: footer must have two institutional exits")
                        if await page.locator(".master-footer").inner_text() and "По теме" in await page.locator(".master-footer").inner_text():
                            raise AssertionError(f"{name}: ad-directory footer resurrected")
                        if name == "size-compare":
                            bridge = page.locator(".entry-modulation")
                            if await bridge.count() != 1:
                                raise AssertionError("Ambiguous comparison must have a human bridge")
                            bridgebox = await bridge.bounding_box()
                            if not bridgebox or bridgebox["y"] + bridgebox["height"] >= phone["y"]:
                                raise AssertionError("The bridge must lead into, not follow, the telephone")
                        if name == "sensor-n0" and await page.locator(".entry-modulation").count() != 1:
                            raise AssertionError("The reviewed Musima example needs its own pre-phone modulation")
                    if name in {"workshop-maps", "repair-map-seams", "repair-map-neck",
                                "repair-map-inspection"}:
                        expected = 5 if name == "workshop-maps" else (1 if name == "repair-map-neck" else 2)
                        image_count = await page.locator(".atlas-figure img").count()
                        if image_count != expected:
                            raise AssertionError(f"{name}: expected {expected} valid technical maps, got {image_count}")
                        # The figures intentionally lazy-load on public pages. Force
                        # them eager in this browser test before checking decoding.
                        await page.locator(".atlas-figure img").evaluate_all(
                            "(images) => images.forEach(img => img.loading = 'eager')"
                        )
                        await page.wait_for_function(
                            "() => Array.from(document.querySelectorAll('.atlas-figure img')).every("
                            "img => img.complete && img.naturalWidth > 0)", timeout=12000
                        )
                        if width < 680:
                            panel = await page.locator(".atlas-pan").first.evaluate(
                                "(el) => ({client: el.clientWidth, scroll: el.scrollWidth})"
                            )
                            if panel["scroll"] <= panel["client"]:
                                raise AssertionError(
                                    f"{name} at {width}px: readable SVG plate must be scrollable: {panel}"
                                )
                    overflow = max(0, dims["scroll"] - dims["width"])
                    checks.append({"page": name, "viewport": width, "overflow_px": overflow})
                    if overflow > 2:
                        raise AssertionError(f"{name} at width {width}: horizontal overflow {overflow}px")
                    if name == "workshop-maps" and width in (390, 1366):
                        await page.locator(".atlas-hub-figure").first.screenshot(
                            path=str(output / f"workshop-maps-{width}.png"))
                    if name in {"home", "archive", "collection", "access", "knowledge", "standalone", "essay", "model", "sensor-n0", "sensor-long", "size-compare", "experience", "delivery"}:
                        await page.screenshot(path=str(output / f"{name}-{width}.png"),
                                              full_page=True)
                await page.close()
        finally:
            await browser.close()
    return {"browser": chrome, "checks": checks, "errors": []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path("_site"))
    parser.add_argument("--output", type=Path, default=Path("_audit/screens"))
    args = parser.parse_args()
    result = asyncio.run(run(args.site, args.output))
    report = args.output.parent / "visual.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
