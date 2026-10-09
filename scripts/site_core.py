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
from entry_router import route_panel, destination_for_editorial_group

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


def inspect_knowledge(root: Path, entrances: list[dict], paired: list[dict]) -> list[dict]:
    """Independent, source-aware N.1 editorial essays attached to existing N.0."""
    d = root / "content/knowledge"
    if not d.exists():
        return []
    entry_map = {p["slug"]: p for p in entrances}
    occupied = {p["slug"] for p in paired}
    result = []
    titles = set()
    subjects = set()
    for file in sorted(d.glob("*.json")):
        source = read_json(file)
        if source.get("version") != 1:
            raise ValueError(f"{file.name}: unsupported essay format")
        for item in source.get("articles", []):
            slug = item.get("slug", "")
            target = item.get("entrance_slug", "")
            if not SLUG.fullmatch(slug) or slug in occupied:
                raise ValueError(f"Duplicate or invalid knowledge slug: {slug}")
            if target not in entry_map or target in subjects:
                raise ValueError(f"{slug}: missing or already-claimed entrance {target}")
            if item.get("status") != "ready" or not item.get("reviewed"):
                raise ValueError(f"{slug}: cannot publish an unreviewed essay")
            if not item.get("provenance") or not item.get("title") or not item.get("lead"):
                raise ValueError(f"{slug}: missing provenance, title or lead")
            if norm(item["title"]) == norm(entry_map[target]["search_title"]):
                raise ValueError(f"{slug}: knowledge H1 is identical to commercial H1")
            if norm(item["title"]) in titles:
                raise ValueError(f"{slug}: repeated knowledge title")
            if len(item["title"]) > 120 or len(item["lead"]) > 250:
                raise ValueError(f"{slug}: excessively long page title or lead")
            sections = item.get("sections", [])
            if len(sections) < 4 or len(sections) > 15:
                raise ValueError(f"{slug}: substantial independent sections required")
            section_titles = set()
            body_words = 0
            for section in sections:
                if not section.get("heading") or norm(section["heading"]) in section_titles:
                    raise ValueError(f"{slug}: repeated or missing section heading")
                section_titles.add(norm(section["heading"]))
                if not isinstance(section.get("paragraphs"), list) or not section["paragraphs"]:
                    raise ValueError(f"{slug}: heading has no content")
                for para in section["paragraphs"]:
                    if len(para.split()) < 17 or len(para.split()) > 180:
                        raise ValueError(f"{slug}: a paragraph is missing or excessively large")
                    body_words += len(para.split())
            if body_words < 360:
                raise ValueError(f"{slug}: fewer than 360 authored words; not substantive")
            if any(not source.get("url", "").startswith("https://") for source in item.get("sources", [])):
                raise ValueError(f"{slug}: invalid cited source URL")
            if item.get("related") is not None:
                if not isinstance(item["related"], list) or any(x not in entry_map for x in item["related"]):
                    raise ValueError(f"{slug}: related entrances must exist")
            occupied.add(slug)
            titles.add(norm(item["title"]))
            subjects.add(target)
            result.append(item)
    return result


def inspect_model_publications(root: Path) -> list[dict]:
    """Only verified manufacturer model IDs gain reference articles, never stock pages."""
    folder = root / "content/model-publications"
    if not folder.exists():
        return []
    registry = {m["id"]: m for m in read_json(root / "content/model-registry.json")["models"]}
    used_slug, used_models, result = set(), set(), []
    for file in sorted(folder.glob("*.json")):
        data = read_json(file)
        if data.get("version") != 1:
            raise ValueError(f"{file.name}: invalid model article schema")
        for item in data.get("articles", []):
            id = item.get("model_id", "")
            slug = item.get("slug", "")
            if id not in registry or id in used_models or not SLUG.fullmatch(slug) or slug in used_slug:
                raise ValueError(f"{file.name}: invalid or duplicate verified model")
            model = registry[id]
            if model["source_status"] != "official_model_page" or model.get("availability") != "unverified":
                raise ValueError(f"{file.name}: model is not publication-ready")
            if item.get("status") != "ready" or not item.get("reviewed") or not item.get("provenance"):
                raise ValueError(f"{file.name}: unreviewed model article")
            if model["model_name"] not in item.get("title", "") or not item.get("lead"):
                raise ValueError(f"{file.name}: exact model identity not retained in title")
            facts = item.get("facts", [])
            if len(facts) < 3 or any(
                not isinstance(fact.get("label"), str) or not isinstance(fact.get("value"), str)
                for fact in facts
            ):
                raise ValueError(f"{file.name}: insufficient attributable official facts")
            sections = item.get("sections", [])
            if len(sections) < 3:
                raise ValueError(f"{file.name}: not a complete model-specific article")
            words = 0
            for section in sections:
                if not section.get("heading") or not section.get("paragraphs"):
                    raise ValueError(f"{file.name}: section incomplete")
                for para in section["paragraphs"]:
                    if len(para.split()) < 18:
                        raise ValueError(f"{file.name}: thin paragraph")
                    words += len(para.split())
            if words < 180:
                raise ValueError(f"{file.name}: not enough model-specific explanation")
            sources = item.get("sources", [])
            if not sources or not any(s.get("url") == model["source"] for s in sources):
                raise ValueError(f"{file.name}: missing verified manufacturer reference")
            if any(not s.get("url", "").startswith("https://") for s in sources):
                raise ValueError(f"{file.name}: invalid source URL")
            if item.get("availability") is not None or item.get("price") is not None:
                raise ValueError(f"{file.name}: cannot invent model inventory")
            used_models.add(id)
            used_slug.add(slug)
            result.append(item)
    return result


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


def group_anchor(label: str) -> str:
    """An unchanging archive anchor for each existing editorial family."""
    return "entrance-" + sha256(label.encode("utf-8")).hexdigest()[:10]


def frame(p: dict, role: str, content: str, contact: str, route_override: str | None = None) -> str:
    access = role == "entry"
    route = "/" + (p["entry_slug"] if access else f"details/{p['slug']}") + "/"
    if route_override:
        route = route_override
    level = "../" * len([part for part in route.strip("/").split("/") if part])
    page_title = p["search_title"] if access else p["editorial_title"]
    desc = p["description"] if access else p["editorial_description"]
    kicker = p["entry_kicker"] if access else p["editorial_kicker"]
    mast = (f'<div class="rule"></div><div class="meta"><a href="{level}">'
            'EASYBASSMASTER</a><span>МОСКВА</span></div>' + ('' if access else brand()))

    # A few ambiguous requests need one genuine human bridge BEFORE the phone.
    # Never synthesize it for every topic or repeat the full SEO description.
    bridge = str(p.get("entry_modulation", "")).strip() if access else ""
    if bridge and (len(bridge) > 160 or "?" in bridge):
        raise ValueError(f"Entry modulation must be one brief assertion: {route}")
    lead = (f'<p class="entry-modulation">{escape(bridge)}</p>' if bridge
            else ('' if access else f'<p class="deck">{escape(p["editorial_deck"])}</p>'))
    header = ('<section class="issue master-lead">'
              f'<p class="issue-kicker">{escape(kicker)}</p>'
              f'<h1>{escape(page_title)}</h1>' + lead + '</section>')

    footer_href = p.get("footer_href") or (
        level + p.get("footer_target", "meeting/") if access else level + "archive/")
    footer_label = p.get("footer_label", "Знакомство" if access else "Подшивка")
    footer_title = p.get("footer_title", "")
    footer_attr = f' title="{escape(footer_title, quote=True)}"' if footer_title else ""
    footer_left = (f'<a class="footer-workshop-home" href="{level}">'
                   'МАСТЕРСКАЯ КОНТРАБАСА</a>' if access
                   else '<span>МАСТЕРСКАЯ КОНТРАБАСА</span>')
    footer = (f'<footer class="master-footer">{footer_left}'
              f'<a href="{escape(footer_href, quote=True)}"{footer_attr}>'
              f'{escape(footer_label)}</a></footer>')

    main_content = contact + content if access else content + contact
    full = mast + '<main>' + header + main_content + footer + '</main>'
    if access:
        page_class = 'entry-router entry-short'
        if bridge:
            page_class += ' entry-has-modulation'
    else:
        page_class = 'deep-editorial'
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(page_title)} · EasyBassMaster</title>'
            f'<meta name="description" content="{escape(desc, quote=True)}">'
            f'<link rel="canonical" href="{DOMAIN}{route}">'
            f'<link rel="stylesheet" href="{level}styles.css"></head>'
            f'<body class="new-master {page_class}">{full}</body></html>')

def nav(items: list[tuple[str, str]]) -> str:
    cells = "".join(f'<a href="{escape(href, quote=True)}">{escape(label)}'
                    '<span aria-hidden="true">↗</span></a>' for href, label in items)
    return f'<nav class="master-links" aria-label="Дальше">{cells}</nav>'


def make_entry(p: dict, contact: str) -> str:
    """A real N.0 newspaper entrance with its already-written N.1 as 'Подробнее'."""
    route = f"/{p['entry_slug']}/"
    source = {**p, "footer_href": f"../details/{p['slug']}/",
              "footer_label": "Подробнее"}
    return frame(source, "entry", route_panel(route), contact)

def make_standalone_entrance(p: dict, contact: str, deeper: dict[str, dict] | None = None) -> str:
    """One direct human request, eight routes, and one deep editorial exit."""
    route = f"/{p['slug']}/"
    target, label = destination_for_editorial_group(p["group"])
    source = {
        "entry_slug": p["slug"],
        "search_title": p["search_title"],
        "description": p["lead"],
        "entry_kicker": "МАСТЕРСКАЯ КОНТРАБАСА",
        "entry_deck": p["lead"],
        "entry_modulation": p.get("bridge", ""),
        "footer_target": target,
        "footer_label": label,
    }
    if deeper and p["slug"] in deeper:
        source["footer_href"] = f"../details/{deeper[p['slug']]['slug']}/"
        source["footer_label"] = "Подробнее"
        source["footer_title"] = deeper[p["slug"]]["title"]
    return frame(source, "entry", route_panel(route), contact)

def make_deep(p: dict, by_slug: dict[str, dict], contact: str) -> str:
    paragraphs = "".join(f'<p>{escape(v)}</p>' for v in p["editorial_paragraphs"])
    links = [(f"../../{p['parent']}/", "Коллекция" if p["parent"] == "collection" else "Мастерская"),
             ("../../meeting/", "Знакомство")]
    links += [(f"../{slug}/", by_slug[slug]["editorial_title"]) for slug in p.get("related", [])]
    content = f'<section class="master-text">{paragraphs}</section>' + nav(links)
    return frame(p, "deep", content, contact)


def make_knowledge_article(item: dict, contact: str, entrance_names: dict[str, str]) -> str:
    """Use the same sober publication frame, with sectioned real editorial text."""
    slug = item["slug"]
    source = {
        "slug": slug,
        "editorial_title": item["title"],
        "editorial_description": item.get("description", item["lead"]),
        "editorial_kicker": item.get("kicker", "КОНТРАБАС · ПРЕДМЕТНОЕ ЗНАНИЕ"),
        "editorial_deck": item["lead"]
    }
    parts = ['<article class="knowledge-text" aria-label="Предметная статья">']
    for section in item["sections"]:
        parts.append(f'<section><h2>{escape(section["heading"])}</h2>')
        parts.extend(f'<p>{escape(para)}</p>' for para in section["paragraphs"])
        parts.append('</section>')
    parts.append('</article>')
    if item.get("sources"):
        parts.append('<details class="knowledge-sources"><summary>Документы и источники</summary><ul>')
        for source_item in item["sources"]:
            parts.append(f'<li><a href="{escape(source_item["url"], quote=True)}" '
                         'rel="noopener noreferrer">'
                         f'{escape(source_item["title"])}</a></li>')
        parts.append('</ul></details>')
    # Essays lead into the real institution rather than back into search ads.
    links = [("../../collection/", "Коллекция"), ("../../workshop/", "Мастерская"),
             ("../../meeting/", "Знакомство")]
    parts.append(nav(links))
    return frame(source, "deep", "".join(parts), contact)


def make_model_publication(item: dict, contact: str) -> str:
    spec = "".join('<div><dt>' + escape(f["label"]) + '</dt><dd>'
                   + escape(f["value"]) + '</dd></div>' for f in item["facts"])
    body = ('<article class="knowledge-text model-article">'
            '<dl class="model-facts">' + spec + '</dl>')
    for section in item["sections"]:
        body += '<section><h2>' + escape(section["heading"]) + '</h2>'
        body += "".join('<p>' + escape(paragraph) + '</p>' for paragraph in section["paragraphs"])
        body += '</section>'
    body += '</article><details class="knowledge-sources"><summary>Данные изготовителя</summary><ul>'
    for source in item["sources"]:
        body += '<li><a rel="noopener noreferrer" href="' + escape(source["url"], quote=True) + '">' + escape(source["title"]) + '</a></li>'
    body += '</ul></details>'
    p = {"slug": item["slug"],
         "editorial_title": item["title"],
         "editorial_description": item.get("description", item["lead"]),
         "editorial_kicker": "МОДЕЛЬ · ДАННЫЕ ИЗГОТОВИТЕЛЯ",
         "editorial_deck": item["lead"]}
    return frame(p, "deep", body, contact, route_override=f"/models/{item['slug']}/")


def write(site: Path, route: str, html: str) -> None:
    file = site / route.strip("/") / "index.html"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(html, encoding="utf-8")


def archive_index(site: Path, pages: list[dict], entrances: list[dict], knowledge: list[dict], models: list[dict]) -> None:
    path = site / "archive/index.html"
    text = path.read_text(encoding="utf-8")
    token = "<!-- GENERATED_SUBJECT_INDEX -->"
    if text.count(token) != 1:
        raise ValueError("Missing or duplicated subject index marker in Jekyll archive")
    entries = []
    for p in pages:
        deep = f"{BASE}/details/{p['slug']}/"
        entries.append(
            '<article>'
            f'<h2><a href="{deep}">{escape(p["editorial_title"])}</a></h2>'
            f'<p>{escape(p["editorial_deck"])}</p>'
            '</article>')
    generated = ('<section class="archive-list" aria-label="Предметная подшивка">'
                 '<p class="issue-kicker">КОНТРАБАСЫ · ПОДШИВКА</p>'
                 + "".join(entries) + '</section>')
    if knowledge:
        articles = "".join(
            '<article><h2><a href="' + BASE + '/details/' + escape(a["slug"]) + '/">'
            + escape(a["title"]) + '</a></h2><p>' + escape(a["lead"]) + '</p></article>'
            for a in knowledge)
        generated += ('<section class="archive-list" aria-label="Большие предметные статьи">'
                      '<p class="issue-kicker">ИССЛЕДОВАНИЯ · ПРЕДМЕТНОЕ ЗНАНИЕ</p>'
                      + articles + '</section>')
    if models:
        model_links = "".join(
            '<article><h2><a href="' + BASE + '/models/' + escape(m["slug"]) + '/">'
            + escape(m["title"]) + '</a></h2><p>' + escape(m["lead"]) + '</p></article>'
            for m in models
        )
        generated += ('<section class="archive-list" aria-label="Каталог подтверждённых моделей">'
                      '<p class="issue-kicker">МОДЕЛИ · ПЕРВОИСТОЧНИКИ</p>'
                      + model_links + '</section>')
    # Search-only N.0 entrances are intentionally not a public catalogue.
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
    knowledge = inspect_knowledge(root, entrances, pages)
    models = inspect_model_publications(root)
    by_entrance = {item["entrance_slug"]: item for item in knowledge}
    entrance_names = {item["slug"]: item["search_title"] for item in entrances}
    contact = contact_from_home(site)
    for p in pages:
        write(site, "/" + p["entry_slug"] + "/", make_entry(p, contact))
        write(site, "/details/" + p["slug"] + "/", make_deep(p, by_slug, contact))
    for item in entrances:
        write(site, "/" + item["slug"] + "/", make_standalone_entrance(item, contact, by_entrance))
    for item in knowledge:
        write(site, "/details/" + item["slug"] + "/", make_knowledge_article(item, contact, entrance_names))
    for item in models:
        write(site, "/models/" + item["slug"] + "/", make_model_publication(item, contact))
    archive_index(site, pages, entrances, knowledge, models)
    from sensor_n0 import compile_site as compile_sensor
    n0_report = compile_sensor(root, site, contact, frame, write)
    urls = canonicals_and_sitemap(site)
    return {
        "generated_subjects": len(pages),
        "generated_pair_pages": 2 * len(pages),
        "standalone_entrances": len(entrances),
        "sensor_n0": n0_report,
        "independent_knowledge_articles": len(knowledge),
        "official_model_articles": len(models),
        "hypotheses_retained": len(read_json(root / "content/candidates.json")["candidates"]),
        "public_documents_in_sitemap": len(urls),
        "site": str(site),
        "source_hash": sha256((root / "content/topics.json").read_bytes()).hexdigest()[:16],
        "entrance_routes": ["/" + p["slug"] + "/" for p in entrances],
        "knowledge_routes": ["/details/" + p["slug"] + "/" for p in knowledge],
        "model_routes": ["/models/" + p["slug"] + "/" for p in models],
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
