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
                        if width <= 760:
                            panel = await page.locator(".atlas-pan").first.evaluate(
                                "(el) => ({client: el.clientWidth, scroll: el.scrollWidth})"
                            )
                            if panel["scroll"] <= panel["client"]:
                                raise AssertionError(f"{name}: mobile maps must scroll rather than shrink labels")
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
