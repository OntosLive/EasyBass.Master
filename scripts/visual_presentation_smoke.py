#!/usr/bin/env python3
"""Verify the approved room, institutional essays and direct Courtier foyer layout."""
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
WIDTHS = (390, 728, 760, 820, 1366)


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
                        hidden = await page.evaluate("""() => Array.from(document.querySelectorAll('.reveal'))
                          .filter(el => Number(getComputedStyle(el).opacity) < .99)
                          .slice(0, 5).map(el => el.className)""")
                        if hidden:
                            raise AssertionError(
                                f"Room sections must stay visible without scrolling/JS: {hidden}")
                        if await page.locator("h1").count() != 1:
                            raise AssertionError("Exactly one room H1 is required")
                        if await page.locator(".hero-stats .stat").count() != 4:
                            raise AssertionError("The four original room stats must stay intact")
                        if await page.locator(".contact-block").count() != 1:
                            raise AssertionError("The room must publish exactly one verified contact")
                        # A missing '</a>' used to capture most of the document inside
                        # a pill-shaped CTA without generating any horizontal overflow.
                        club_cta = page.locator(".cards-3 .info-card:last-child > a.btn[href='#contact']")
                        cta_count = await club_cta.count()
                        cta_text = await club_cta.text_content() if cta_count == 1 else None
                        if cta_count != 1 or cta_text.strip() != "Договориться о встрече":
                            club_debug = await page.evaluate("""() => [...document.querySelectorAll('.cards-3 a')]
                              .map(el => ({href:el.getAttribute('href'),text:el.innerText.slice(0,100),
                                html:el.outerHTML.slice(0,180)}))""")
                            raise AssertionError(
                                f"Malformed club CTA at {width}px: count={cta_count}, "
                                f"text={cta_text!r}, links={club_debug}")
                        contact_geometry = await page.evaluate("""() => {
                            const section = document.querySelector('#contact');
                            const panel = section?.querySelector('.contact-panel');
                            const copy = panel?.querySelector('.contact-copy');
                            const title = copy?.querySelector('h2');
                            if (!section || !panel || !copy || !title) return {missing: true};
                            return {
                                insideLink: !!section.closest('a'),
                                titleWidth: title.getBoundingClientRect().width,
                                copyWidth: copy.getBoundingClientRect().width,
                                panelWidth: panel.getBoundingClientRect().width,
                                sectionWidth: section.getBoundingClientRect().width,
                                paragraphTransform: getComputedStyle(copy.querySelector('p')).textTransform
                            };
                        }""")
                        if (contact_geometry.get("missing") or contact_geometry["insideLink"] or
                                contact_geometry["paragraphTransform"] == "uppercase" or
                                contact_geometry["panelWidth"] < contact_geometry["sectionWidth"] * .85 or
                                contact_geometry["titleWidth"] < contact_geometry["copyWidth"] * .75):
                            raise AssertionError(
                                f"Broken contact geometry at {width}px: {contact_geometry}")
                        await page.wait_for_function(
                            "() => { const img=document.querySelector('#heroImage');"
                            " return img && img.complete && img.naturalWidth > 0 }", timeout=10000)
                        if not await page.locator('h1').inner_text() == "Пространство, в котором можно найти свой.":
                            raise AssertionError("Original room H1 was changed")
                        switch = page.locator("#modeSwitch")
                        if not await switch.count():
                            raise AssertionError("The original daylight/evening switch is missing")
                        await switch.click()
                        await page.wait_for_function(
                            "() => document.querySelector('#heroImage').getAttribute('src').includes('room-evening.webp')",
                            timeout=10000)
                        await switch.click()
                        await page.wait_for_function(
                            "() => document.querySelector('#heroImage').getAttribute('src').includes('room-golden.webp')",
                            timeout=10000)
                        if width == 1366:
                            await page.locator("#galleryMain").click()
                            if not await page.locator("#lightbox").evaluate(
                                "(el) => el.classList.contains('open')"):
                                raise AssertionError("Original room gallery lightbox is not working")
                            await page.keyboard.press("Escape")
                            if await page.locator("#lightbox").evaluate(
                                "(el) => el.classList.contains('open')"):
                                raise AssertionError("Escape must close the room gallery")
                    else:
                        if await page.locator("body.foyer-page").count() != 1:
                            raise AssertionError(f"{name}: page lost its visual body marker")
                        if await page.locator("body.courtier-page").count() == 1:
                            if await page.locator(".foyer-door").count():
                                raise AssertionError(f"{name}: stale third-door advertising card")
                            if await page.locator(".courtier-portal[href]").count() != 1:
                                raise AssertionError(f"{name}: physical Courtier door missing")
                            if await page.locator(".foyer-door-enter[href]").count() != 1:
                                raise AssertionError(f"{name}: one direct CTA required")
                            await page.wait_for_function(
                                "() => { const img=document.querySelector('.courtier-portal img');"
                                " return img && img.complete && img.naturalWidth > 0 }", timeout=12000)
                        else:
                            door = page.locator(".foyer-door")
                            if await door.count() != 1:
                                raise AssertionError(f"{name}: one room invitation required")
                            if await page.locator(".foyer-door-enter[href]").count() != 1:
                                raise AssertionError(f"{name}: missing direct room-entry link")
                            if name in {"knowledge", "collection", "archive"} and width in (390, 1366):
                                await page.locator(".foyer-door-image img").evaluate("(img) => img.loading='eager'")
                                await page.wait_for_function(
                                    "() => { const img=document.querySelector('.foyer-door-image img');"
                                    " return img && img.complete && img.naturalWidth > 0 }", timeout=12000)
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
                        offenders = await page.evaluate("""() => {
                            const w = document.documentElement.clientWidth;
                            return [...document.querySelectorAll('body *')].map(el => {
                                const r = el.getBoundingClientRect();
                                return {tag: el.tagName.toLowerCase(), id: el.id,
                                        cls: typeof el.className === 'string' ? el.className.slice(0,65) : '',
                                        left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width)};
                            }).filter(x => x.right > w+3 && x.width > 0)
                              .sort((a,b) => b.right-a.right).slice(0,12);
                        }""")
                        meta = await page.evaluate("""() => {
                          const selectors=['.hero-grid','.grid-2','.contact-grid','.contact-copy','.hero-actions','.topbar-inner','.mobile-sheet','.btn'];
                          const dims=Object.fromEntries(selectors.map(sel=>{
                            const el=document.querySelector(sel);
                            if(!el) return [sel,null];
                            const r=el.getBoundingClientRect();const cs=getComputedStyle(el);
                            return [sel,{display:cs.display,columns:cs.gridTemplateColumns,flex:cs.flexDirection,
                              width:cs.width,minWidth:cs.minWidth,boxRight:r.right,scrollWidth:el.scrollWidth}];
                          }));
                          return {innerWidth:innerWidth,documentWidth:document.documentElement.clientWidth,
                            meta:document.querySelector('meta[name="viewport"]')?.content,
                            isMobile:matchMedia('(max-width:760px)').matches,
                            isTablet:matchMedia('(max-width:1180px)').matches,dims};
                        }""")
                        raise AssertionError(f"{name} at width {width}: horizontal overflow {overflow}px, offenders={offenders}, computed={meta}")
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
