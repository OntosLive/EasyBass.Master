#!/usr/bin/env python3
"""Publish authored N.0 entrance statements, never scene/question products.

2026-10-09: retired the synthetic 3290 scene × question site pages.
The old atlas is RESEARCH ONLY; it is not a publication queue.
Human-readable N.0 copy is authored beforehand in content/entrances-rewrite.
This module only reads, validates, deduplicates and renders.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
import json
from pathlib import Path
import re

from entry_router import route_panel

ROOT = Path(__file__).resolve().parents[1]
ROUTE_ROOT = "/vhod/"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def norm(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


def families(root: Path = ROOT) -> list[dict]:
    """Explicit model-authored families. No generation from a morphology matrix."""
    collection: list[dict] = []
    known_ids: set[str] = set()
    paths = sorted((root / "content/entrances-rewrite").glob("*.json"))
    if not paths:
        raise ValueError("Missing authored N.0 corpus")
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("version") != 1:
            raise ValueError(f"{path.name}: wrong corpus version")
        for family in raw.get("families", []):
            family_id = family.get("id", "")
            if not SLUG.fullmatch(family_id) or family_id in known_ids:
                raise ValueError(f"{path.name}: duplicate/invalid family {family_id}")
            known_ids.add(family_id)
            if not family.get("title") or not family.get("entries"):
                raise ValueError(f"{path.name}: empty family {family_id}")
            collection.append(family)
    return collection


def prior_titles(root: Path) -> set[str]:
    """Preserve previously edited announcements instead of republishing duplicates."""
    titles: set[str] = set()
    for file in sorted((root / "content/entrances").glob("*.json")):
        for item in json.loads(file.read_text(encoding="utf-8")).get("entries", []):
            titles.add(norm(item["search_title"]))
    paired = json.loads((root / "content/topics.json").read_text(encoding="utf-8"))
    for item in paired["pages"]:
        titles.add(norm(item["search_title"]))
    return titles


def records(root: Path = ROOT) -> list[dict]:
    """A page requires independently written H1 and offer; no auto-title synthesis."""
    used_titles = prior_titles(root)
    seen_routes: set[str] = set()
    seen_leads: set[str] = set()
    published: list[dict] = []
    for family in families(root):
        family_id = family["id"]
        for entry in family["entries"]:
            title = entry.get("search_title", "").strip()
            lead = entry.get("lead", "").strip()
            slug = entry.get("slug", "")
            if not SLUG.fullmatch(slug) or not title or not lead:
                raise ValueError(f"{family_id}: invalid authored N.0 record {slug}")
            if len(title) > 125 or not (45 <= len(lead) <= 300):
                raise ValueError(f"{family_id}: invalid editorial length for {slug}")
            if entry.get("origin") != "authored_research_hypothesis":
                raise ValueError(f"{family_id}: not an authored entrance {slug}")
            if norm(title) in used_titles:
                # Already covered by an existing independently edited N.0.
                continue
            route = f"{ROUTE_ROOT}{family_id}/{slug}/"
            if route in seen_routes or norm(lead) in seen_leads:
                raise ValueError(f"Duplicated authored N.0: {route}")
            if ":" in title and any(token in title.casefold() for token in
                                   ("разница между", "точное положение", "роль")):
                raise ValueError(f"Synthetic scene/question title forbidden: {title}")
            used_titles.add(norm(title))
            seen_routes.add(route)
            seen_leads.add(norm(lead))
            published.append({
                "route": route,
                "hub": f"{ROUTE_ROOT}{family_id}/",
                "family_id": family_id,
                "family_title": family["title"],
                "title": title,
                "lead": lead,
                "description": lead,
                "status": "n0",
                "source_status": "editorial_hypothesis_not_measured",
            })
    if not published:
        raise ValueError("No independent N.0 pages after checking legacy entries")
    return published


"""Two-level topic directory and standalone human-phrased N.0 notices.

For short N.0 we intentionally follow ONTOS.RENT: H1, direct contact,
four meaningful ranges, four workshop facts, and contextual 'Подробнее'.
The separately edited lead is preserved as SEO description, never as an
extraneous sales speech on the public newspaper surface.
"""
DIRECTORY_SECTIONS = (
    ("Инструменты и коллекция", (
        "familiar-instruments", "sizes-and-form", "private-collection", "learning-and-families",
    )),
    ("Покупка и знакомство", ("buy-and-compare", "price-and-ownership")),
    ("Мастерская и звук", (
        "ergonomic-neck", "acoustic-response", "repair-restoration", "body-compatibility",
    )),
    ("Музыка и сцена", (
        "classical-performance", "jazz-rockabilly", "recording-film-stage",
    )),
    ("Пользование и дорога", (
        "temporary-access", "strings-bows-hardware", "movement-and-logistics",
    )),
    ("Передача и оценка", ("sell-and-transition", "appraisal-and-authentication")),
)


def html_for(record: dict, contact: str, frame) -> str:
    route = record["route"]
    source = {
        "entry_slug": route.strip("/"),
        "search_title": record["title"],
        "entry_kicker": "МАСТЕРСКАЯ КОНТРАБАСА",
        "entry_deck": record["lead"],
        "description": record["description"],
        "footer_href": "../",
        "footer_label": "По теме",
        "footer_title": record["family_title"],
    }
    return frame(source, "entry", route_panel(route), contact, route_override=route)


def index_page(hub: str, family: dict, subset: list[dict], contact: str, frame) -> str:
    source = {
        "entry_slug": hub.strip("/"),
        "search_title": family["title"],
        "entry_kicker": "ПОДШИВКА · ПО ТЕМЕ",
        "entry_deck": family["title"],
        "description": f"{family['title']}. Объявления мастерской контрабаса в Москве.",
        "is_index": True,
        "footer_href": "../",
        "footer_label": "Все направления",
    }
    links = "".join(
        '<a href="' + escape("/EasyBass.Master" + item["route"], quote=True)
        + '">' + escape(item["title"]) + '</a>' for item in subset
    )
    content = ('<nav class="n0-directory" aria-label="Объявления этого направления">'
               + links + '</nav>')
    return frame(source, "entry", content, contact, route_override=hub)


def root_page(groups: list[dict], rows: list[dict], contact: str, frame) -> str:
    indexed = {item["id"]: item for item in groups}
    counts = Counter(item["family_id"] for item in rows)
    published = {name for name, n in counts.items() if n}
    assigned = {name for _, family_ids in DIRECTORY_SECTIONS for name in family_ids}
    if published != assigned:
        raise ValueError("Directory chapters do not cover each live announcement family exactly")
    if len(assigned) != sum(len(ids) for _, ids in DIRECTORY_SECTIONS):
        raise ValueError("Directory chapter has a duplicate family")

    sections = ['<div class="n0-chapters">']
    for heading, family_ids in DIRECTORY_SECTIONS:
        links = []
        for family_id in family_ids:
            family = indexed[family_id]
            url = f"/EasyBass.Master/vhod/{family_id}/"
            links.append('<a href="' + escape(url, quote=True) + '">'
                         '<span>' + escape(family["title"]) + '</span>'
                         f'<small>{counts[family_id]}</small></a>')
        sections.append('<section class="n0-chapter"><h2>' + escape(heading) + '</h2>'
                        '<nav class="n0-directory" aria-label="' + escape(heading, quote=True)
                        + '">' + ''.join(links) + '</nav></section>')
    sections.append('</div>')
    source = {
        "entry_slug": "vhod",
        "search_title": "Объявления мастерской контрабаса",
        "entry_kicker": "ПОДШИВКА · ВСЕ НАПРАВЛЕНИЯ",
        "entry_deck": "Инструменты, мастерская, работа, выбор и знакомство.",
        "description": "Короткие объявления частной мастерской контрабаса.",
        "is_index": True,
        "footer_href": "../archive/",
        "footer_label": "Подшивка мастерской",
    }
    return frame(source, "entry", ''.join(sections), contact, route_override="/vhod/")

def compile_site(root: Path, site: Path, contact: str, frame, write) -> dict:
    authored = families(root)
    rows = records(root)
    by_family: dict[str, list[dict]] = defaultdict(list)
    for item in rows:
        write(site, item["route"], html_for(item, contact, frame))
        by_family[item["family_id"]].append(item)
    for family in authored:
        family_id = family["id"]
        if by_family[family_id]:
            hub = f"{ROUTE_ROOT}{family_id}/"
            write(site, hub, index_page(hub, family, by_family[family_id], contact, frame))
    write(site, "/vhod/", root_page(authored, rows, contact, frame))
    archive = site / "archive/index.html"
    markup = archive.read_text(encoding="utf-8")
    hook = "<!-- SENSOR_N0_INDEX -->"
    if markup.count(hook) != 1:
        raise ValueError("Missing unique authored entrance insertion point in archive")
    insertion = (
        '<section class="archive-list n0-index-link">'
        '<p class="issue-kicker">ОБЪЯВЛЕНИЯ · КОНТРАБАСНАЯ МАСТЕРСКАЯ</p>'
        '<article><h2><a href="/EasyBass.Master/vhod/">Подшивка коротких объявлений</a></h2>'
        + f'<p>{len(rows)} самостоятельных входов, написанных из конкретных '
        'потребностей и возможностей мастерской.</p></article></section>'
    )
    archive.write_text(markup.replace(hook, insertion), encoding="utf-8")
    return {"n0_pages": len(rows), "families": len(by_family),
            "hubs": len(by_family) + 1,
            "first": rows[0]["route"], "last": rows[-1]["route"],
            "source": "explicit-model-authored-corpus",
            "synthetic_cartesian_pages": 0}


if __name__ == "__main__":
    rows = records()
    print(json.dumps({"records": len(rows), "first": rows[0]["route"],
                      "last": rows[-1]["route"]}, ensure_ascii=False))
