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

from site_core import BASE, DOMAIN, PHONE, ROOT, SITEMAP_NS, inspect_records, inspect_entrances, inspect_knowledge, pretty_route


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
    expected = {f"/{p['entry_slug']}/" for p in ready}
    expected |= {f"/details/{p['slug']}/" for p in ready}
    expected |= {f"/{e['slug']}/" for e in entries}
    expected |= {f"/details/{e['slug']}/" for e in essays}
    errors, graph = [], defaultdict(set)
    docs = {}
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
                if fragment and not doc(dest).find(id=fragment):
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
            if not d.select_one(".brand-title"):
                errors.append(f"{route}: masthead not shared")
            if d.select_one('meta[name="robots"][content*="noindex"]'):
                errors.append(f"{route}: canonical page accidentally noindex")
    for entry in entries:
        route = "/" + entry["slug"] + "/"
        d = docs.get(route)
        if d:
            if not d.h1 or d.h1.get_text(" ", strip=True) != entry["search_title"]:
                errors.append(f"{route}: edited entrance title differs from source")
            if not d.select_one(".entrance-question"):
                errors.append(f"{route}: no meaningful final question")
            if d.select_one('.master-links'):
                errors.append(f"{route}: invented navigation instead of a direct relationship")
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
    archive = docs.get("/archive/")
    if not archive:
        errors.append("Archive missing")
    else:
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
    errors += [f"Duplicate sitemap URL: {link}" for link, count in counts.items() if count != 1]
    for loc in locations:
        if not loc or not loc.startswith(DOMAIN + "/"):
            errors.append(f"Foreign sitemap URL: {loc}")
        if not any(loc == DOMAIN + url for url in docs):
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
