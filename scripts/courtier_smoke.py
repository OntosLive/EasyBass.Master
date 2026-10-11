#!/usr/bin/env python3
"""Real HTTP/browser review of the Courtier, its room and the /text/ mirror.

A successful CI deploy is not a visual acceptance. This smoke test checks the
*scene*: readable query, original authored response, immediate telephone, a
physical visual doorway, direct destination, and the original 4+4 routes.
"""
from __future__ import annotations

import argparse
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread
from urllib.parse import quote

from playwright.async_api import async_playwright

EXAMPLES = [
    ("purchase", "kupit-masterovoy-kontrabas-v-moskve/", "collection"),
    ("repair", "remont-grifa-kontrabasa/", "neck"),
    ("first-instrument", "kontrabas-1-2-ili-3-4/", "room"),
    ("musima", "vhod/familiar-instruments/kontrabas-musima-kupit-v-moskve/", "collection"),
]
WIDTHS = [390, 728, 820, 1366]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


async def inspect(site: Path, report: Path) -> dict:
    browser_exe = shutil.which("google-chrome") or shutil.which("chromium")
    if not browser_exe:
        raise RuntimeError("Chrome/Chromium required")
    report.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(site.resolve()))
    )
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    root = f"http://127.0.0.1:{server.server_address[1]}/"
    checks = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                executable_path=browser_exe, headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                for width in WIDTHS:
                    page = await browser.new_page(
                        viewport={"width":width,"height":900},device_scale_factor=1)
                    for name, route, mode in EXAMPLES:
                        await page.goto(root + route, wait_until="load")
                        await page.evaluate("document.fonts.ready")
                        if await page.locator("body.courtier-page").count() != 1:
                            raise AssertionError(f"{name} not a Courtier foyer")
                        if await page.locator(f'body[data-courtier="{mode}"]').count() != 1:
                            raise AssertionError(f"{name} chose irrelevant visual mode")
                        if await page.locator("h1").count() != 1:
                            raise AssertionError(f"{name}: duplicated question")
                        if await page.locator(".entry-modulation").count() != 1:
                            raise AssertionError(f"{name}: authored answer lost")
                        if await page.locator(".contact-block").count() != 1:
                            raise AssertionError(f"{name}: no direct contact")
                        if (await page.locator(".entry-range-grid a").count() != 4 or
                            await page.locator(".entry-utilities a").count() != 4):
                            raise AssertionError(f"{name}: missing 4+4 range/grounds")
                        if await page.locator(".master-footer a").count() != 2:
                            raise AssertionError(f"{name}: two editorial exits lost")
                        if await page.locator('a.courtier-enter[href]').count() != 1:
                            raise AssertionError(f"{name}: direct room action missing")
                        if await page.locator("a.courtier-portal[href]").count() != 1:
                            raise AssertionError(f"{name}: physical doorway missing")
                        await page.wait_for_function(
                            "() => {let i=document.querySelector('.courtier-portal img');"
                            "return i && i.complete && i.naturalWidth>0;}", timeout=15000)
                        check = await page.evaluate("""() => {
                          const box = sel => {
                             let el = document.querySelector(sel), r=el?.getBoundingClientRect();
                             return r ? {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom} : null;
                          };
                          return {
                            vw:document.documentElement.clientWidth,
                            scroll:document.documentElement.scrollWidth,
                            h1:document.querySelector('h1')?.innerText,
                            answered:document.querySelector('.entry-modulation')?.innerText,
                            phone:document.querySelector('.contact-phone')?.getAttribute('href'),
                            entrance:document.querySelector('.courtier-enter')?.getAttribute('href'),
                            portal:document.querySelector('.courtier-portal')?.getAttribute('href'),
                            title:box('.courtier-greeting h1'),call:box('.courtier-call'),
                            portal_box:box('.courtier-portal'),stage:box('.courtier-stage')
                          };
                        }""")
                        if check["scroll"] - check["vw"] > 2:
                            raise AssertionError(f"{name} {width}px: horizontally clipped {check}")
                        if (check["phone"] != "tel:+79096945544" or
                            check["entrance"] != "../" * len(route.strip("/").split("/")) or
                            check["portal"] != check["entrance"]):
                            raise AssertionError(f"{name} {width}px: route mismatch {check}")
                        if check["title"]["width"] < min(width * .5, 260):
                            raise AssertionError(f"{name} {width}px: crushed title {check}")
                        if (check["call"]["width"] < 175 or
                            check["portal_box"]["width"] < 240):
                            raise AssertionError(f"{name} {width}px: collapsed choice or doorway {check}")
                        if check["call"]["y"] > (1080 if width < 800 else 910):
                            raise AssertionError(f"{name} {width}px: telephone buried {check}")
                        if width > 1020 and check["title"]["right"] > check["portal_box"]["x"] - 8:
                            raise AssertionError(f"{name} {width}px: textual and visual frames overlap")
                        if width <= 800 and check["portal_box"]["y"] < check["call"]["bottom"] - 2:
                            raise AssertionError(f"{name} {width}px: phone hidden behind photo")
                        technical = root + "text/" + route
                        author_title = check["h1"]
                        author_copy = check["answered"]
                        await page.goto(technical, wait_until="load")
                        if await page.locator('meta[name="robots"][content="noindex,follow"]').count() != 1:
                            raise AssertionError(f"{name}: text mirror accidentally indexable")
                        if (await page.locator("h1").inner_text() != author_title or
                            await page.locator(".entry-modulation").inner_text() != author_copy):
                            raise AssertionError(f"{name}: text/visual authorship diverged")
                        await page.goto(root + route, wait_until="load")
                        await page.locator(".courtier-portal img").evaluate(
                            "(img) => img.decode()")
                        await page.evaluate("document.fonts.ready")
                        await page.screenshot(
                            path=str(report / f"courtier-{name}-{width}.png"),
                            full_page=True,animations="disabled")
                        await page.locator(".courtier-enter").click()
                        await page.wait_for_load_state("load")
                        if page.url.rstrip("/") != root.rstrip("/"):
                            raise AssertionError(f"{name}: clicked door did not enter the room: {page.url}")
                        if await page.locator('body.room-home').count() != 1:
                            raise AssertionError(f"{name}: entered another foyer, not the room")
                        checks.append({"scene":name,"width":width,"status":"pass",
                                       "title":author_title,"visual":mode})
                    await page.close()
                # Knowledge remains independent and exits directly to the room.
                page=await browser.new_page()
                await page.goto(root+"details/geometriya-grifa-kontrabasa-sheyka-nakladka/")
                if await page.locator("body.courtier-page").count():
                    raise AssertionError("N.1 was turned into a commercial foyer")
                if await page.locator(".knowledge-text > section").count() < 3:
                    raise AssertionError("N.1 lost substantial independent research")
                doors=page.locator("a.foyer-door-enter")
                if await doors.count()!=1 or await doors.get_attribute("href")!="../../":
                    raise AssertionError("Knowledge exits through the wrong room door")
                await page.close()
            finally:
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=4)
    out={"checks":checks,"errors":[]}
    (report / "courtier-browser.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--site",type=Path,default=Path("_site"))
    parser.add_argument("--output",type=Path,default=Path("_audit/courtier-screens"))
    args=parser.parse_args()
    print(json.dumps(asyncio.run(inspect(args.site,args.output)),ensure_ascii=False))


if __name__=="__main__":
    main()
