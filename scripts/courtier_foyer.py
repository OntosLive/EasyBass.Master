#!/usr/bin/env python3
"""Turn each already-authored N.0 into its own foyer, without touching its copy.

The source still comes from site_core.py and author-written N.0 records.
This pass operates ONLY on the visual presentation. The text snapshot is
made before it runs. The Courtier is a role in the interaction, not a bot,
a new login gate, a human figure or a second compulsory URL.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

IMAGES = {
    "collection": ("assets/photography/row-amber.webp",
                   "Художественный вид контрабасов частной коллекции"),
    "room": ("assets/photography/room-golden.webp",
             "Художественный вид комнаты контрабасов"),
    "evening": ("assets/photography/room-evening.webp",
                "Художественный образ вечерней комнаты контрабасов"),
    "neck": ("assets/maps/neck-geometry.svg",
             "Чертёж геометрии грифа и накладки контрабаса; размеры условны"),
    "seams": ("assets/maps/seams-cracks.svg",
              "Схема устройства шва, фуги и трещины контрабаса; без масштаба"),
    "anatomy": ("assets/maps/anatomy.svg",
                "Схема анатомии контрабаса; обозначения условны"),
}

def scene_for(title: str) -> str:
    """Select verified EXISTING art, never fabricate a repair photograph.

    This chooses only presentation assets, not speech, editorial promises,
    prices, availability or search text. All source copy stays unchanged.
    """
    t = title.casefold().replace("ё", "е")
    if any(x in t for x in ("гриф", "шейк", "накладк", "мензур", "порожк")):
        return "neck"
    if any(x in t for x in ("шов", "трещин", "фуга", "обечайк", "пружин")):
        return "seams"
    if any(x in t for x in ("ремонт", "реставрац", "душк", "подставк", "настройк")):
        return "anatomy"
    if any(x in t for x in ("аренд", "времен", "прокат")):
        return "evening"
    if any(x in t for x in ("купить", "покуп", "мастеров", "музим", "москвич", "чешск")):
        return "collection"
    return "room"


def new_text(soup: BeautifulSoup, tag: str, class_name: str, value: str):
    t = soup.new_tag(tag)
    t["class"] = [class_name]
    t.string = value
    return t


def exact_one(parent, selector: str, label: str):
    matches = parent.select(selector)
    if len(matches) != 1:
        raise ValueError(f"{label}: expected 1 {selector}, got {len(matches)}")
    return matches[0]


def transform(raw: str, relative: Path) -> tuple[str, str]:
    """Return transformed HTML and scene ID, or raw HTML for non-N.0 pages."""
    soup = BeautifulSoup(raw, "html.parser")
    body = soup.body
    if body is None:
        raise ValueError(f"{relative}: no body")
    classes = set(body.get("class", []))
    if not {"entry-router", "entry-short"} <= classes:
        return raw, "not-n0"
    if "courtier-page" in classes:
        return raw, "already"
    if not relative.as_posix().endswith("/index.html"):
        raise ValueError(f"{relative}: expected pretty-route N.0")

    heading = exact_one(body, ".issue.master-lead h1", str(relative))
    title = heading.get_text(" ", strip=True)
    mode = scene_for(title)
    depth = len(relative.parts) - 1
    root = "../" * depth
    lead = exact_one(body, "section.issue.master-lead", str(relative))
    contact = exact_one(body, "section.contact-block", str(relative))
    router = exact_one(body, ".entry-router-links", str(relative))
    ranges = exact_one(router, "nav.entry-range-grid", str(relative))
    utilities = exact_one(router, "nav.entry-utilities", str(relative))
    footer = exact_one(body, "footer.master-footer", str(relative))
    brand = exact_one(body, "div.meta", str(relative))
    old_door = exact_one(body, ".foyer-door.foyer-door-search", str(relative))
    enter = exact_one(old_door, "a.foyer-door-enter", str(relative))

    if len(ranges.select("a[href]")) != 4 or len(utilities.select("a[href]")) != 4:
        raise ValueError(f"{relative}: expected four ranges and four witnesses")
    if not contact.select_one('a[href="tel:+79096945544"]'):
        raise ValueError(f"{relative}: verified contact missing")
    if not title or not lead.select_one(".entry-modulation"):
        raise ValueError(f"{relative}: source-authored query or answer missing")
    if len(footer.select("a[href]")) != 2:
        raise ValueError(f"{relative}: two editorial exits missing")

    for element in (lead, contact, router, footer, brand, enter):
        element.extract()
    body.clear()
    body["class"] = sorted(classes | {"courtier-page"})
    body["data-courtier"] = mode

    if soup.head is None:
        raise ValueError(f"{relative}: no head")
    if not soup.head.select_one('link[rel="canonical"]'):
        raise ValueError(f"{relative}: canonical missing")
    css = soup.new_tag("link", rel="stylesheet",
                       href=root + "assets/visual/courtier.css")
    soup.head.append(css)

    header = soup.new_tag("header")
    header["class"] = ["courtier-header"]
    header.append(brand)
    header.append(new_text(soup, "span", "courtier-header-tag",
                           "МАСТЕРСКАЯ · КОЛЛЕКЦИЯ · КЛУБ"))
    body.append(header)

    main = soup.new_tag("main")
    main["class"] = ["courtier-main"]
    body.append(main)

    stage = soup.new_tag("section")
    stage["class"] = ["courtier-stage"]
    stage["aria-label"] = "Встреча с мастерской контрабаса"
    main.append(stage)

    greeting = soup.new_tag("div")
    greeting["class"] = ["courtier-greeting"]
    stage.append(greeting)
    greeting.append(new_text(soup, "p", "courtier-foreword",
                             "ВАШ ВОПРОС · НАЧАЛО ЗНАКОМСТВА"))
    greeting.append(lead)

    choices = soup.new_tag("div")
    choices["class"] = ["courtier-choices"]
    choices["aria-label"] = "Связаться или войти"
    greeting.append(choices)

    phone = soup.new_tag("div")
    phone["class"] = ["courtier-call"]
    phone.append(new_text(soup, "span", "courtier-choice-label",
                          "СРАЗУ СВЯЗАТЬСЯ"))
    phone.append(contact)
    choices.append(phone)

    way_in = soup.new_tag("div")
    way_in["class"] = ["courtier-entry"]
    way_in.append(new_text(soup, "span", "courtier-choice-label",
                           "ИЛИ ВОЙТИ В КОМНАТУ"))
    enter["href"] = root
    enter["class"] = ["foyer-door-enter", "courtier-enter"]
    enter.clear()
    enter.append("Войти в мастерскую")
    enter.append(new_text(soup, "span", "courtier-enter-arrow", "↗"))
    way_in.append(enter)
    choices.append(way_in)

    art_path, alt = IMAGES[mode]
    portal = soup.new_tag("a", href=root)
    portal["class"] = ["courtier-portal"]
    portal["data-art"] = "diagram" if mode in {"neck","seams","anatomy"} else "photo"
    portal["aria-label"] = "Войти в общую комнату EasyBassMaster"
    image = soup.new_tag("img", src=root + art_path, alt=alt,
                         loading="eager", decoding="async")
    portal.append(image)
    caption = soup.new_tag("span")
    caption["class"] = ["courtier-portal-caption"]
    caption.append(new_text(soup, "span", "courtier-portal-eyebrow",
                            "ПО ТУ СТОРОНУ ДВЕРИ"))
    caption.append(new_text(soup, "span", "courtier-portal-title",
                            "Пространство, в котором можно найти свой."))
    caption.append(new_text(soup, "span", "courtier-portal-arrow", "↗"))
    portal.append(caption)
    stage.append(portal)

    horizon = soup.new_tag("section")
    horizon["class"] = ["courtier-horizon"]
    horizon["aria-label"] = "Возможности мастерской"
    horizon.append(new_text(soup, "p", "courtier-horizon-kicker",
                            "ЗА ПРЕДЕЛАМИ ПЕРВОГО ВОПРОСА"))
    horizon.append(new_text(soup, "h2", "courtier-horizon-title",
                            "Один инструмент открывает целый мир различий."))
    horizon.append(router)
    main.append(horizon)

    exit_section = soup.new_tag("div")
    exit_section["class"] = ["courtier-footer"]
    exit_section.append(footer)
    main.append(exit_section)

    result = str(soup)
    check = BeautifulSoup(result, "html.parser")
    if len(check.select("h1")) != 1 or len(check.select(".contact-block")) != 1:
        raise ValueError(f"{relative}: lost single answer or single contact")
    if len(check.select("a.foyer-door-enter[href]")) != 1:
        raise ValueError(f"{relative}: missing direct entry")
    if check.select_one("a.foyer-door-enter")["href"] != root:
        raise ValueError(f"{relative}: door does not open root directly")
    if check.select_one(".courtier-portal")["href"] != root:
        raise ValueError(f"{relative}: photograph is not a direct door")
    return result, mode


def build(site: Path) -> dict:
    stats = Counter()
    for path in sorted(site.rglob("*.html")):
        relative = path.relative_to(site)
        source = path.read_text(encoding="utf-8")
        output, kind = transform(source, relative)
        stats[kind] += 1
        if output != source:
            path.write_text(output, encoding="utf-8")
    if stats["not-n0"] < 1 or sum(
        amount for kind, amount in stats.items() if kind not in {"not-n0", "already"}
    ) < 1:
        raise ValueError("No individual search foyers created")
    return dict(stats)
