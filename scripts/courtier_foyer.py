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
    body["class"] = sorted(classes | {"courtier-page", "room-child"})
    body["data-courtier"] = mode

    if soup.head is None:
        raise ValueError(f"{relative}: no head")
    if not soup.head.select_one('link[rel="canonical"]'):
        raise ValueError(f"{relative}: canonical missing")
    # Text/newspaper styling stays exclusively in /text/. A build-time
    # extracted CSS snapshot from the approved ROOM is our only visual parent.
    for old_style in list(soup.head.select('link[rel="stylesheet"]')):
        old_style.decompose()
    for name in ("room-parent.css", "courtier.css"):
        css = soup.new_tag("link", rel="stylesheet",
                           href=root + "assets/visual/" + name)
        soup.head.append(css)

    # An N.0 is a CHILD of the already approved room, not a new design
    # and not the short newspaper skin. The room remains unchanged.
    def el(name: str, cls: str = "", txt: str | None = None, **attrs):
        item = soup.new_tag(name, **attrs)
        if cls:
            item["class"] = cls.split()
        if txt is not None:
            item.string = txt
        return item

    header = el("header", "topbar courtier-header")
    bar = el("div", "topbar-inner")
    logo = el("a", "brand", href=root)
    logo.append(el("span", "brand-mark", "EASYBASS.MASTER"))
    logo.append(el("span", "brand-sub", "Мастерская · коллекция · клуб"))
    bar.append(logo)
    nav = el("nav", "nav", **{"aria-label": "Основная навигация"})
    for anchor, label in (
        ("collection", "Коллекция"), ("workshop", "Мастерская"),
        ("selection", "Знакомство"), ("gallery", "Галерея"),
        ("contact", "Контакты"),
    ):
        nav.append(el("a", txt=label, href=root + "#" + anchor))
    bar.append(nav)
    bar.append(el("a", "mode-switch courtier-header-entry",
                  "Войти в мастерскую", href=root))
    header.append(bar)
    body.append(header)

    hero = el("section", "hero courtier-hero")
    media = el("div", "hero-media")
    media.append(el("img", src=root + "assets/photography/room-golden.webp",
                    alt="Коллекция контрабасов в мастерской",
                    loading="eager", decoding="sync"))
    hero.append(media)
    stage = el("div", "hero-grid courtier-stage",
               **{"aria-label": "Придворный принимает ваш запрос"})
    greeting = el("div", "hero-copy courtier-greeting")
    greeting.append(el("div", "eyebrow", "Москва · частная мастерская"))

    lead["class"] = ["issue", "master-lead", "courtier-lead"]
    heading["class"] = ["hero-title"]
    bridge = exact_one(lead, ".entry-modulation", str(relative))
    bridge["class"] = sorted(set(bridge.get("class", [])) | {"hero-subtitle"})
    greeting.append(lead)

    choices = el("div", "hero-actions courtier-choices",
                 **{"aria-label": "Позвонить или войти в мастерскую"})
    call = el("div", "courtier-call")
    contact["id"] = "contact-foyer"
    call.append(contact)
    choices.append(call)
    enter["class"] = ["btn", "primary", "courtier-enter", "foyer-door-enter"]
    enter["href"] = root
    enter.clear()
    enter.append("Войти в мастерскую")
    choices.append(enter)
    greeting.append(choices)
    stage.append(greeting)

    card_captions = {
        "collection": ("Коллекция", "Разные контрабасы рядом"),
        "room": ("Коллекция", "Комната контрабасов"),
        "evening": ("Коллекция", "Вечерний салон"),
        "neck": ("Мастерская", "Геометрия грифа и накладки"),
        "seams": ("Мастерская", "Швы и соединения корпуса"),
        "anatomy": ("Мастерская", "Устройство контрабаса"),
    }
    art_path, alt = IMAGES[mode]
    caption_tag, caption_title = card_captions[mode]
    portal = el("a", "card mini-card courtier-portal", href=root,
                **{"aria-label": "Открыть главную комнату мастерской",
                   "data-art": ("diagram" if mode in {"neck", "seams", "anatomy"}
                                else "photo")})
    card_media = el("span", "media courtier-art")
    card_media.append(el("img", src=root + art_path, alt=alt,
                         loading="eager", decoding="sync"))
    portal.append(card_media)
    card_content = el("span", "content courtier-portal-copy")
    card_content.append(el("span", "card-tag", caption_tag))
    card_content.append(el("span", "courtier-portal-title", caption_title))
    card_content.append(el("span", "courtier-portal-action",
                           "Войти в пространство ↗"))
    portal.append(card_content)
    stage.append(portal)
    hero.append(stage)
    body.append(hero)

    strip = el("div", "hero-strip courtier-range-strip")
    for item in ranges.select("a[href]"):
        item["class"] = sorted(set(item.get("class", [])) | {"stat"})
    ranges["class"] = ["hero-stats", "entry-range-grid"]
    strip.append(ranges)
    body.append(strip)

    main = el("main", "courtier-main")
    section = el("section", "section courtier-horizon", id="possibilities")
    head = el("div", "section-head")
    head.append(el("h2", txt="Больше, чем один вопрос."))
    head.append(el("p", txt="Коллекция, работа мастерской и знакомство "
                   "с инструментами. Можно продолжить с того, "
                   "что важно именно вам."))
    section.append(head)
    for item in utilities.select("a[href]"):
        item["class"] = sorted(set(item.get("class", [])) | {"card", "info-card"})
    utilities["class"] = ["cards-3", "entry-utilities"]
    section.append(utilities)
    main.append(section)
    body.append(main)

    page_footer = el("footer", "courtier-footer master-footer")
    inner = el("div", "footer-inner")
    for item in footer.select("a[href]"):
        inner.append(item.extract())
    page_footer.append(inner)
    body.append(page_footer)

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
