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
    ("access", "kupit-masterovoy-kontrabas-v-moskve/index.html"),
    ("knowledge", "details/masterovoy-kontrabas/index.html"),
]
WIDTHS = (390, 1366)


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
                    overflow = max(0, dims["scroll"] - dims["width"])
                    checks.append({"page": name, "viewport": width, "overflow_px": overflow})
                    if overflow > 2:
                        raise AssertionError(f"{name} at width {width}: horizontal overflow {overflow}px")
                    if name in {"home", "archive", "access", "knowledge"}:
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
