#!/usr/bin/env python3
"""Build static EasyBassMaster editorial pairs after Jekyll has built the old newspaper.

Inherited from ONTOS.RENT: separate access and knowledge pages, structured records,
one contact, subject graph, archival index and public build validation.
Not inherited: rental-specific template logic, inventory, 1980 texts or operations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://ontoslive.github.io/EasyBass.Master"
BASE = "/EasyBass.Master"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PHONE = "+7 (909) 694-55-44"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


def inspect_records(root: Path) -> list[dict]:
    document = read_json(root / "content/topics.json")
    candidates = read_json(root / "content/candidates.json")["candidates"]
    if document.get("version") != 1 or len(candidates) != 60:
        raise ValueError("Expected v1 source records and 60 tracked hypotheses")
    indices = [item["id"] for item in candidates]
    if len(indices) != len(set(indices)) or indices != list(range(1, 61)):
        raise ValueError("Duplicate or missing candidate indices")
    pages = document["pages"]
    slugs, entries, titles = set(), set(), set()
    for p in pages:
        if p.get("status") != "ready" or not p.get("reviewed"):
            raise ValueError("Only reviewed, ready topics may be compiled")
        for field in ("slug", "entry_slug"):
            if not SLUG.fullmatch(p[field]):
                raise ValueError(f"Invalid {field} in {p}")
        if p["slug"] in slugs or p["entry_slug"] in entries:
            raise ValueError("Duplicate subject slug or entry route")
        slugs.add(p["slug"])
        entries.add(p["entry_slug"])
        if p["entry_slug"] in {"archive", "collection", "workshop", "meeting"}:
            raise ValueError(f"Reserved slug used: {p['entry_slug']}")
        for field in ("search_title", "editorial_title", "entry_deck", "entry_body", "editorial_deck"):
            if not isinstance(p.get(field), str) or not p[field].strip():
                raise ValueError(f"{p['slug']}: missing {field}")
        if len(p["search_title"]) > 120:
            raise ValueError(f"{p['slug']}: oversized search title")
        if norm(p["search_title"]) == norm(p["editorial_title"]):
            raise ValueError(f"{p['slug']}: duplicate roles of the two pages")
        if norm(p["search_title"]) in titles:
            raise ValueError(f"{p['slug']}: duplicated search intent")
        titles.add(norm(p["search_title"]))
        if not isinstance(p.get("editorial_paragraphs"), list) or len(p["editorial_paragraphs"]) < 2:
            raise ValueError(f"{p['slug']}: insufficient editorial content")
        if p.get("parent") not in {"collection", "workshop", "meeting"}:
            raise ValueError(f"{p['slug']}: missing real top-level parent")
        if not isinstance(p.get("related", []), list):
            raise ValueError(f"{p['slug']}: invalid related links")
        if not p.get("provenance") or not p.get("description") or not p.get("editorial_description"):
            raise ValueError(f"{p['slug']}: missing editorial provenance or descriptions")
    for p in pages:
        if p["slug"] in p.get("related", []):
            raise ValueError(f"{p['slug']}: self-reference")
        for sibling in p.get("related", []):
            if sibling not in slugs:
                raise ValueError(f"{p['slug']}: missing related subject {sibling}")
    implemented = {c["subject_slug"] for c in candidates if c["status"] == "implemented"}
    if not implemented <= slugs:
        raise ValueError("Published candidates missing from ready records")
    if any(c["status"] not in {"implemented", "research", "entrance"} for c in candidates):
        raise ValueError("Unexpected candidate status")
    if any(c["status"] == "research" and (c.get("subject_slug") or c.get("entrance_slug")) for c in candidates):
        raise ValueError("An unreviewed research hypothesis pretends to have a page")
    if any(c["status"] == "entrance" and (not c.get("entrance_slug") or c.get("subject_slug")) for c in candidates):
        raise ValueError("Standalone entrance must have its own route, not a forged deep pair")
    return pages


def inspect_entrances(root: Path, paired: list[dict] | None = None) -> list[dict]:
    """Accept distinct edited entrance scenes; never fabricate knowledge pairs."""
    paired = paired if paired is not None else inspect_records(root)
    occupied = {p["entry_slug"] for p in paired}
    occupied |= {p["slug"] for p in paired}
    occupied |= {"archive", "collection", "meeting", "workshop", "details"}
    titles = {norm(p["search_title"]) for p in paired}
    descriptions = set()
    ready = []
    records = sorted((root / "content/entrances").glob("*.json"))
    for path in records:
        data = read_json(path)
        if data.get("version") != 1:
            raise ValueError(f"{path.name}: invalid entrance schema version")
        for p in data.get("entries", []):
            slug = p.get("slug", "")
            if not SLUG.fullmatch(slug) or slug in occupied:
                raise ValueError(f"{path.name}: invalid, duplicated or reserved entrance URL: {slug}")
            occupied.add(slug)
            if (root / slug / "index.html").exists():
                raise ValueError(f"{slug}: existing handwritten page must not be replaced")
            if p.get("status") != "ready" or p.get("origin") != "editorial_hypothesis":
                raise ValueError(f"{slug}: unreviewed entrance or unsupported source origin")
            for field in ("search_title", "lead", "body", "open_question", "group"):
                if not isinstance(p.get(field), str) or not p[field].strip():
                    raise ValueError(f"{slug}: missing original {field}")
            if len(p["search_title"]) > 120 or len(p["lead"]) > 230:
                raise ValueError(f"{slug}: title/lead exceeds editorial bounds")
            if len(p["body"].split()) < 24 or len(p["body"].split()) > 115:
                raise ValueError(f"{slug}: body should contain a specific complete scene")
            if len(p["open_question"].split()) < 5 or not p["open_question"].rstrip().endswith("?"):
                raise ValueError(f"{slug}: meaningful residual question missing")
            if norm(p["search_title"]) in titles:
                raise ValueError(f"{slug}: duplicate search_title")
            titles.add(norm(p["search_title"]))
            if norm(p["lead"]) in descriptions:
                raise ValueError(f"{slug}: repeated generic lead")
            descriptions.add(norm(p["lead"]))
            ready.append(p)
    accepted = {p["slug"] for p in ready}
    previous = read_json(root / "content/candidates.json")["candidates"]
    for c in previous:
        if c["status"] == "entrance" and c["entrance_slug"] not in accepted:
            raise ValueError(f"Tracked query #{c['id']} points to missing entrance {c['entrance_slug']}")
    return ready


def heading(doc: dict, name: str) -> str:
    return escape(str(doc[name]))


def brand() -> str:
    return ('<header class="mast"><div class="mastline">'
            '<div class="brand-title" aria-label="EASYBASS.MASTER">EASYBASS<span>.</span>MASTER</div>'
            '<small>Мастерская контрабаса</small></div></header>')


def contact_from_home(site: Path) -> str:
    index = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "html.parser")
    block = index.select_one(".contact-block")
    if not block:
        raise ValueError("The approved shared contact does not exist on the homepage")
    a = block.select_one(".contact-phone")
    if not a or a.get("href") != "tel:+79096945544" or PHONE not in a.get_text(" ", strip=True):
        raise ValueError("Homepage contact number changed")
    for name in ("Telegram", "WhatsApp"):
        if not block.select_one(f'a[aria-label="{name}"] svg'):
            raise ValueError(f"Missing verified {name} contact icon")
    if block.select_one(".max-contact-pending"):
        raise ValueError("Disabled MAX markup must not leak into generated pages")
    return str(block)


def frame(p: dict, role: str, content: str, contact: str) -> str:
    access = role == "entry"
    level = "../" if access else "../../"
    route = "/" + (p["entry_slug"] if access else f"details/{p['slug']}") + "/"
    page_title = p["search_title"] if access else p["editorial_title"]
    desc = p["description"] if access else p["editorial_description"]
    kicker = p["entry_kicker"] if access else p["editorial_kicker"]
    mast = (f'<div class="rule"></div><div class="meta"><a href="{level}">'
            'EASYBASSMASTER</a><span>МОСКВА</span></div>' + brand())
    footer = (f'<footer class="master-footer"><span>МАСТЕРСКАЯ КОНТРАБАСА</span>'
              f'<a href="{level}archive/">Подшивка</a></footer>')
    full = (mast + '<main><section class="issue master-lead">'
            f'<p class="issue-kicker">{escape(kicker)}</p>'
            f'<h1>{escape(page_title)}</h1>'
            f'<p class="deck">{escape(p["entry_deck"] if access else p["editorial_deck"])}</p>'
            '</section>' + content + contact + footer + '</main>')
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(page_title)} · EasyBassMaster</title>'
            f'<meta name="description" content="{escape(desc, quote=True)}">'
            f'<link rel="canonical" href="{DOMAIN}{route}">'
            f'<link rel="stylesheet" href="{level}styles.css"></head>'
            f'<body class="new-master">{full}</body></html>')


def nav(items: list[tuple[str, str]]) -> str:
    cells = "".join(f'<a href="{escape(href, quote=True)}">{escape(label)}'
                    '<span aria-hidden="true">↗</span></a>' for href, label in items)
    return f'<nav class="master-links" aria-label="Дальше">{cells}</nav>'


def make_entry(p: dict, contact: str) -> str:
    links = [(f"../details/{p['slug']}/", "Подробнее об инструменте"),
             (f"../{p['parent']}/", "Коллекция" if p["parent"] == "collection" else "Мастерская")]
    content = (f'<section class="master-text"><p>{escape(p["entry_body"])}</p></section>'
               + nav(links))
    return frame(p, "entry", content, contact)


def make_standalone_entrance(p: dict, contact: str) -> str:
    """A complete contact opening, not a counterfeit abbreviated deep article."""
    source = {
        "entry_slug": p["slug"],
        "search_title": p["search_title"],
        "description": p["lead"],
        "entry_kicker": p["group"].upper(),
        "entry_deck": p["lead"],
    }
    content = ('<section class="master-text">'
               f'<p>{escape(p["body"])}</p>'
               f'<p class="entrance-question">{escape(p["open_question"])}</p>'
               '</section>')
    return frame(source, "entry", content, contact)


def make_deep(p: dict, by_slug: dict[str, dict], contact: str) -> str:
    paragraphs = "".join(f'<p>{escape(v)}</p>' for v in p["editorial_paragraphs"])
    links = [(f"../../{p['entry_slug']}/", "Покупка и знакомство"),
             (f"../../{p['parent']}/", "Коллекция" if p["parent"] == "collection" else "Мастерская")]
    links += [(f"../{slug}/", by_slug[slug]["editorial_title"]) for slug in p.get("related", [])]
    content = f'<section class="master-text">{paragraphs}</section>' + nav(links)
    return frame(p, "deep", content, contact)


def write(site: Path, route: str, html: str) -> None:
    file = site / route.strip("/") / "index.html"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(html, encoding="utf-8")


def archive_index(site: Path, pages: list[dict], entrances: list[dict]) -> None:
    path = site / "archive/index.html"
    text = path.read_text(encoding="utf-8")
    token = "<!-- GENERATED_SUBJECT_INDEX -->"
    if text.count(token) != 1:
        raise ValueError("Missing or duplicated subject index marker in Jekyll archive")
    entries = []
    for p in pages:
        deep = f"{BASE}/details/{p['slug']}/"
        entry = f"{BASE}/{p['entry_slug']}/"
        entries.append(
            '<article>'
            f'<h2><a href="{deep}">{escape(p["editorial_title"])}</a></h2>'
            f'<p>{escape(p["editorial_deck"])}</p>'
            f'<a href="{entry}">{escape(p["search_title"])}</a>'
            '</article>')
    generated = ('<section class="archive-list" aria-label="Предметная подшивка">'
                 '<p class="issue-kicker">КОНТРАБАСЫ · ПОДШИВКА</p>'
                 + "".join(entries) + '</section>')
    if entrances:
        grouped = {}
        for item in entrances:
            grouped.setdefault(item["group"], []).append(item)
        out = ['<section class="archive-entrances" aria-label="Входы и объявления">',
               '<p class="issue-kicker">САМОСТОЯТЕЛЬНЫЕ ВХОДЫ</p>']
        for group, records in grouped.items():
            out.append('<details class="archive-group"><summary>'
                       + escape(group) + f' <span>{len(records)}</span></summary>'
                       '<div class="archive-list">')
            for item in records:
                url = f"{BASE}/{item['slug']}/"
                out.append('<article>'
                           f'<h2><a href="{escape(url, quote=True)}">{escape(item["search_title"])}</a></h2>'
                           f'<p>{escape(item["lead"])}</p>'
                           '</article>')
            out.append('</div></details>')
        out.append('</section>')
        generated += "".join(out)
    path.write_text(text.replace(token, generated), encoding="utf-8")


def pretty_route(site: Path, path: Path) -> str:
    relative = path.relative_to(site).as_posix()
    return "/" + relative[:-len("index.html")] if relative.endswith("index.html") else "/" + relative


def canonicals_and_sitemap(site: Path) -> list[str]:
    urls = []
    for file in sorted(site.rglob("*.html")):
        route = pretty_route(site, file)
        content = file.read_text(encoding="utf-8")
        if "<head" not in content or "</head>" not in content:
            raise ValueError(f"Missing HTML head: {route}")
        url = DOMAIN + route
        doc = BeautifulSoup(content, "html.parser")
        canonical = doc.select('link[rel="canonical"]')
        if not canonical:
            content = content.replace("</head>", f'<link rel="canonical" href="{url}"></head>', 1)
            file.write_text(content, encoding="utf-8")
        elif len(canonical) != 1 or canonical[0].get("href") != url:
            raise ValueError(f"Wrong canonical at {route}")
        if not doc.select_one('meta[name="robots"][content*="noindex"]'):
            urls.append(url)
    ET.register_namespace("", SITEMAP_NS)
    urlset = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    for url in urls:
        ET.SubElement(ET.SubElement(urlset, f"{{{SITEMAP_NS}}}url"),
                      f"{{{SITEMAP_NS}}}loc").text = url
    ET.ElementTree(urlset).write(site / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    (site / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: " + DOMAIN + "/sitemap.xml\n",
        encoding="utf-8")
    (site / ".nojekyll").write_text("", encoding="utf-8")
    return urls


def build(root: Path = ROOT, site: Path | None = None) -> dict:
    if site is None:
        site = root / "_site"
    site = site.resolve()
    if not (site / "index.html").exists() or not (site / "archive/index.html").exists():
        raise ValueError("Jekyll output is missing: run Jekyll before compiling subjects")
    if not (site / "styles.css").exists():
        raise ValueError("Original stylesheet missing in Jekyll output")
    pages = inspect_records(root)
    by_slug = {p["slug"]: p for p in pages}
    entrances = inspect_entrances(root, pages)
    contact = contact_from_home(site)
    for p in pages:
        write(site, "/" + p["entry_slug"] + "/", make_entry(p, contact))
        write(site, "/details/" + p["slug"] + "/", make_deep(p, by_slug, contact))
    for item in entrances:
        write(site, "/" + item["slug"] + "/", make_standalone_entrance(item, contact))
    archive_index(site, pages, entrances)
    urls = canonicals_and_sitemap(site)
    return {
        "generated_subjects": len(pages),
        "generated_pair_pages": 2 * len(pages),
        "standalone_entrances": len(entrances),
        "hypotheses_retained": len(read_json(root / "content/candidates.json")["candidates"]),
        "public_documents_in_sitemap": len(urls),
        "site": str(site),
        "source_hash": sha256((root / "content/topics.json").read_bytes()).hexdigest()[:16],
        "entrance_routes": ["/" + p["slug"] + "/" for p in entrances],
        "pages": [{"slug": p["slug"], "entry": "/" + p["entry_slug"] + "/",
                   "deep": "/details/" + p["slug"] + "/"} for p in pages],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--site", type=Path)
    parser.add_argument("--report", type=Path, default=Path("_audit/build.json"))
    args = parser.parse_args()
    report = build(args.root, args.site)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
