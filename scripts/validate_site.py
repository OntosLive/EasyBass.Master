#!/usr/bin/env python3
"""Validate rendered EasyBassMaster public site after the subject compiler."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict, deque
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from site_core import BASE, DOMAIN, PHONE, ROOT, SITEMAP_NS, inspect_records, inspect_entrances, inspect_knowledge, inspect_model_publications, pretty_route
from sensor_n0 import records as sensor_records


def doc(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def local_path(site: Path, relative_url: str, href: str) -> Path | None:
    if not href or href.startswith(("tel:", "mailto:", "javascript:", "#")):
        return site / relative_url.strip("/") / "index.html" if href.startswith("#") else None
    parts = urlsplit(href)
    if parts.scheme not in ("", "https") or parts.netloc not in ("", "ontoslive.github.io"):
        return None
    absolute = urlsplit(urljoin(DOMAIN + relative_url, href))
    path = unquote(absolute.path)
    if not (path == BASE or path.startswith(BASE + "/")):
        return None
    child = path[len(BASE):].lstrip("/")
    dest = site / child
    if not dest.suffix:
        dest /= "index.html"
    return dest


def validate(site: Path, root: Path = ROOT) -> dict:
    ready = inspect_records(root)
    entries = inspect_entrances(root, ready)
    essays = inspect_knowledge(root, entries, ready)
    models = inspect_model_publications(root)
    research_intersections = sensor_records(root)
    entry_urls = {f"/{p['entry_slug']}/" for p in ready} | {f"/{e['slug']}/" for e in entries}
    expected = {f"/{p['entry_slug']}/" for p in ready}
    expected |= {f"/details/{p['slug']}/" for p in ready}
    expected |= {f"/{e['slug']}/" for e in entries}
    expected |= {f"/details/{e['slug']}/" for e in essays}
    expected |= {f"/models/{m['slug']}/" for m in models}
    errors, graph = [], defaultdict(set)
    docs = {}
    anchor_cache: dict[Path, set[str]] = {}
    all_files = sorted(site.rglob("*.html"))
    for path in all_files:
        route = pretty_route(site, path)
        d = doc(path)
        docs[route] = d
        for c in d.select('link[rel="canonical"]'):
            if c.get("href") != DOMAIN + route:
                errors.append(f"{route}: incorrect self-canonical")
        if len(d.select('link[rel="canonical"]')) != 1:
            errors.append(f"{route}: exactly one canonical expected")
        if not d.select_one('meta[name="viewport"]'):
            errors.append(f"{route}: viewport missing")
        for link in d.select('link[rel="stylesheet"][href]'):
            target = local_path(site, route, link["href"])
            if target is not None and not target.exists():
                errors.append(f"{route}: CSS missing {link['href']}")
        for link in d.select('a[href]'):
            href = link["href"]
            dest = local_path(site, route, href)
            if dest is None:
                continue
            if not dest.exists():
                errors.append(f"{route}: broken link {href}")
            else:
                try:
                    target = pretty_route(site, dest) if dest.suffix == ".html" else route
                    graph[route].add(target)
                except ValueError:
                    errors.append(f"{route}: escaping site path {href}")
                fragment = urlsplit(href).fragment
                if fragment:
                    if dest not in anchor_cache:
                        anchor_cache[dest] = {e["id"] for e in doc(dest).find_all(id=True)}
                    if fragment not in anchor_cache[dest]:
                        errors.append(f"{route}: missing anchor {href}")
        if route in expected:
            if len(d.find_all("h1")) != 1:
                errors.append(f"{route}: one semantic H1 required")
            if len(d.select(".contact-block")) != 1:
                errors.append(f"{route}: shared contact missing or repeated")
            c = d.select_one(".contact-block")
            if c:
                if not c.select_one('a[href="tel:+79096945544"]'):
                    errors.append(f"{route}: wrong telephone")
                if PHONE not in c.get_text(" ", strip=True):
                    errors.append(f"{route}: wrong displayed telephone")
                for name in ("Telegram", "WhatsApp"):
                    if not c.select_one(f'a[aria-label="{name}"] svg'):
                        errors.append(f"{route}: {name} icon absent")
                if c.select_one(".max-contact-pending"):
                    errors.append(f"{route}: inactive MAX icon leaked")
            if route not in entry_urls and not d.select_one(".brand-title"):
                errors.append(f"{route}: masthead not shared")
            if route in entry_urls and not d.select_one(".meta a[href]"):
                errors.append(f"{route}: compact entry masthead missing")
            if d.select_one('meta[name="robots"][content*="noindex"]'):
                errors.append(f"{route}: canonical page accidentally noindex")
        if route in entry_urls and d.select(".entry-range-grid a, .entry-utilities a"):
            errors.append(f"{route}: obsolete eight-link router must not be published")
    for entry in entries:
        route = "/" + entry["slug"] + "/"
        d = docs.get(route)
        if d:
            if not d.h1 or d.h1.get_text(" ", strip=True) != entry["search_title"]:
                errors.append(f"{route}: edited entrance title differs from source")
            if not d.select_one(".entrance-question"):
                errors.append(f"{route}: no meaningful final question")
            authored_body = d.select_one(".entry-authored-body")
            if not authored_body or authored_body.get_text(" ", strip=True) != entry["body"]:
                errors.append(f"{route}: authored editorial body must appear unchanged")
            contextual = [e for e in essays if e["entrance_slug"] == entry["slug"]]
            navlinks = d.select(".entry-continuation a[href]")
            if contextual:
                target = f"../details/{contextual[0]['slug']}/"
                if len(navlinks) != 1 or navlinks[0].get("href") != target:
                    errors.append(f"{route}: expected one optional N.1 continuation")
            elif navlinks:
                errors.append(f"{route}: invented N.1 continuation")
    for essay in essays:
        route = f"/details/{essay['slug']}/"
        d = docs.get(route)
        if not d:
            errors.append(f"Missing editorial article {route}")
            continue
        if not d.h1 or d.h1.get_text(" ", strip=True) != essay["title"]:
            errors.append(f"{route}: N.1 headline differs from edited source")
        sections = d.select(".knowledge-text > section")
        if len(sections) != len(essay["sections"]):
            errors.append(f"{route}: paragraph/section material missing")
        if essay.get("sources") and len(d.select(".knowledge-sources a[href]")) != len(essay["sources"]):
            errors.append(f"{route}: documented sources not rendered")
        entry_route = f"/{essay['entrance_slug']}/"
        source_doc = docs.get(entry_route)
        if not source_doc or not any(
            a.get("href", "").endswith(route) for a in source_doc.select("a[href]")
        ):
            errors.append(f"{entry_route}: missing editorial continuation to {route}")
    for model in models:
        route = f"/models/{model['slug']}/"
        d = docs.get(route)
        if not d:
            errors.append(f"Missing official model publication {route}")
            continue
        if not d.h1 or d.h1.get_text(" ", strip=True) != model["title"]:
            errors.append(f"{route}: model title mismatch")
        if len(d.select(".model-facts dt")) != len(model["facts"]):
            errors.append(f"{route}: verified manufacturer specification missing")
        if not d.select(".knowledge-sources a[href]"):
            errors.append(f"{route}: missing official manufacturer source")
        if any(token in d.get_text(" ", strip=True).lower() for token in
               ("имеется в наличии", "купить сейчас", "доступен к заказу")):
            errors.append(f"{route}: unverifiable sales claim on reference page")
    # Publishing atlas cross-products would violate the author/editor boundary.
    if (site / "vhod").exists():
        errors.append("Research-only sensor pages leaked into public build")
    if any(route.startswith("/vhod/") for route in docs):
        errors.append("Research sensor pages were published")
    archive = docs.get("/archive/")
    if not archive:
        errors.append("Archive missing")
    else:
        # Every public entry must be an individually authored and reviewed route.
        for route in expected:
            if not any(link.get("href", "").endswith(route) for link in archive.select('a[href]')):
                errors.append(f"Archive does not link to {route}")
    seen, queue = set(), deque(["/"])
    while queue:
        route = queue.popleft()
        if route in seen:
            continue
        seen.add(route)
        queue.extend(graph[route] - seen)
    for route in expected:
        if route not in seen:
            errors.append(f"Unreachable publication: {route}")
    try:
        xml = ET.parse(site / "sitemap.xml").getroot()
        locations = [n.text for n in xml.findall(f"{{{SITEMAP_NS}}}url/{{{SITEMAP_NS}}}loc")]
    except (OSError, ET.ParseError) as exc:
        errors.append(f"Invalid sitemap: {exc}")
        locations = []
    for route in expected:
        if DOMAIN + route not in locations:
            errors.append(f"{route}: pair missing from sitemap")
    counts = Counter(locations)
    if any(url and "/vhod/" in url for url in locations):
        errors.append("Research intersections must not enter sitemap")
    errors += [f"Duplicate sitemap URL: {link}" for link, count in counts.items() if count != 1]
    existent_urls = {DOMAIN + url for url in docs}
    for loc in locations:
        if not loc or not loc.startswith(DOMAIN + "/"):
            errors.append(f"Foreign sitemap URL: {loc}")
        if loc not in existent_urls:
            errors.append(f"Sitemap points to missing HTML: {loc}")
    robots = site / "robots.txt"
    if not robots.exists() or DOMAIN + "/sitemap.xml" not in robots.read_text(encoding="utf-8"):
        errors.append("Canonical sitemap declaration missing from robots")
    for secret in ("docs", "content", "scripts", "tests", "_audit", ".github"):
        if (site / secret).exists():
            errors.append(f"Internal directory published: {secret}")
    css = (site / "styles.css").read_text(encoding="utf-8") if (site / "styles.css").exists() else ""
    for rule in ("@media(max-width:760px)", ".contact-phone", ".master-directions", ".new-master .issue h1"):
        if rule not in css:
            errors.append(f"Missing responsive CSS contract: {rule}")
    return {"html_documents": len(all_files), "expected_pair_documents": 2 * len(ready),
            "independent_knowledge_articles": len(essays),
            "official_model_articles": len(models),
            "short_sensor_pages": 0,
            "research_intersections": len(research_intersections),
            "n0_family_index_pages": 0,
            "expected_standalone_entrances": len(entries),
            "sitemap_entries": len(locations), "reachable_pair_documents": len(expected & seen),
            "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path("_site"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("_audit/validation.json"))
    args = parser.parse_args()
    report = validate(args.site, args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
