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


def html_for(record: dict, contact: str, frame) -> str:
    route = record["route"]
    source = {
        "entry_slug": route.strip("/"),
        "search_title": record["title"],
        "entry_kicker": record["family_title"].upper(),
        "entry_deck": record["lead"],
        "description": record["description"],
    }
    # No instruction, textbook, residual diagnostic question or invented stock.
    # The phone is inserted by frame() directly after the single authored line.
    content = (route_panel(route)
               + '<nav class="n0-return" aria-label="Соседние объявления">'
               '<a href="../">Другие объявления этого направления</a></nav>')
    return frame(source, "entry", content, contact, route_override=route)


def index_page(hub: str, family: dict, subset: list[dict], contact: str, frame) -> str:
    source = {
        "entry_slug": hub.strip("/"),
        "search_title": family["title"],
        "entry_kicker": "ПОДШИВКА · ОБЪЯВЛЕНИЯ",
        "entry_deck": "Обращения к частной мастерской контрабаса. Каждое объявление открывает прямой контакт.",
        "description": f"{family['title']}. Мастерская контрабаса в Москве.",
    }
    links = "".join(
        '<li><a href="' + escape("/EasyBass.Master" + item["route"], quote=True)
        + '">' + escape(item["title"]) + '</a></li>' for item in subset
    )
    content = ('<section class="n0-list" aria-label="Объявления этой темы"><ul>'
               + links + '</ul></section>'
               '<nav class="n0-return"><a href="../">Все направления</a></nav>')
    return frame(source, "entry", content, contact, route_override=hub)


def root_page(groups: list[dict], rows: list[dict], contact: str, frame) -> str:
    counts = Counter(item["family_id"] for item in rows)
    sections = ['<section class="n0-list" aria-label="Направления объявлений">']
    for family in groups:
        n = counts[family["id"]]
        if not n:
            continue
        url = f"/EasyBass.Master/vhod/{family['id']}/"
        sections.append(
            '<article class="n0-family-line"><h2><a href="' + escape(url, quote=True)
            + '">' + escape(family["title"]) + '</a></h2>'
            + f'<p>{n} самостоятельных объявлений</p></article>'
        )
    sections.append('</section>')
    source = {
        "entry_slug": "vhod",
        "search_title": "Объявления мастерской контрабаса",
        "entry_kicker": "МАСТЕРСКАЯ КОНТРАБАСА · ПОДШИВКА",
        "entry_deck": "Инструменты, настройка, реставрация и приглашение к знакомству.",
        "description": "Короткие объявления частной мастерской контрабаса.",
    }
    return frame(source, "entry", "".join(sections), contact, route_override="/vhod/")


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
