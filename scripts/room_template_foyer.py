#!/usr/bin/env python3
"""Render each editorial N.0 *inside the approved room HTML*.

The approved room (design/visual-home/index.html), not a second hand-built
Courtier page, is the template. Its exact layout, inline CSS, mood switch,
mobile navigation, gallery, lightbox and contact stage are inherited.
The author's short N.0 supplies the specific title, reply and 4+4 routes.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path

from bs4 import BeautifulSoup

ROOM = Path(__file__).resolve().parents[1] / "design/visual-home/index.html"

IMAGES = {
    "collection": ("assets/photography/row-amber.webp", "Ряд контрабасов частной коллекции"),
    "room": ("assets/photography/room-golden.webp", "Комната контрабасов"),
    "evening": ("assets/photography/room-evening.webp", "Вечерняя комната контрабасов"),
    "neck": ("assets/maps/neck-geometry.svg", "Схема геометрии грифа и накладки контрабаса"),
    "seams": ("assets/maps/seams-cracks.svg", "Схема шва, фуги и трещины контрабаса"),
    "anatomy": ("assets/maps/anatomy.svg", "Схема устройства контрабаса"),
}


def scene_for(title: str) -> str:
    """Select existing, verified image classes, never a fabricated repair photo."""
    text = title.casefold().replace("ё", "е")
    if any(term in text for term in ("гриф", "шейк", "накладк", "мензур", "порожк")):
        return "neck"
    if any(term in text for term in ("шов", "трещин", "фуга", "обечайк", "пружин")):
        return "seams"
    if any(term in text for term in ("ремонт", "реставрац", "душк", "подставк", "настройк")):
        return "anatomy"
    if any(term in text for term in ("аренд", "времен", "прокат")):
        return "evening"
    if any(term in text for term in ("купить", "покуп", "мастеров", "музим", "москвич", "чешск")):
        return "collection"
    return "room"


def one(node: BeautifulSoup, selector: str, name: str):
    matches = node.select(selector)
    if len(matches) != 1:
        raise ValueError(f"{name}: expected one {selector}, got {len(matches)}")
    return matches[0]


def transform(raw: str, relative: Path, room_html: str | None = None) -> tuple[str, str]:
    """Keep the source editorial text, replace content slots of the real room."""
    editorial = BeautifulSoup(raw, "html.parser")
    if editorial.body is None:
        raise ValueError(f"{relative}: missing body")
    klass = set(editorial.body.get("class", []))
    if not {"entry-router", "entry-short"} <= klass:
        return raw, "not-n0"
    if "room-foyer" in klass:
        return raw, "already"
    if not relative.as_posix().endswith("/index.html"):
        raise ValueError(f"{relative}: N.0 must have a pretty route")

    heading = one(editorial, ".issue.master-lead h1", str(relative))
    answer = one(editorial, ".issue.master-lead .entry-modulation", str(relative))
    kicker = one(editorial, ".issue.master-lead .issue-kicker", str(relative))
    contact = one(editorial, "section.contact-block", str(relative))
    ranges = one(editorial, ".entry-range-grid", str(relative))
    witnesses = one(editorial, ".entry-utilities", str(relative))
    editorial_footer = one(editorial, "footer.master-footer", str(relative))
    if (len(ranges.select("a[href]")) != 4 or
        len(witnesses.select("a[href]")) != 4 or
        len(editorial_footer.select("a[href]")) != 2 or
        len(contact.select('a[href="tel:+79096945544"]')) != 1):
        raise ValueError(f"{relative}: missing confirmed 4+4, footer, or phone")

    title = heading.get_text(" ", strip=True)
    mode = scene_for(title)
    root = "../" * (len(relative.parts) - 1)
    template = room_html if room_html is not None else ROOM.read_text(encoding="utf-8")
    approved = BeautifulSoup(template, "html.parser")
    body = approved.body
    if body is None or "room-home" not in body.get("class", []):
        raise ValueError("Approved room is not the original HTML template")
    for selector in (
        ".site-shell", ".topbar", "#mobileSheet", ".hero .hero-grid",
        "#modeSwitch", "#collection", "#workshop", "#selection", "#gallery",
        "#contact", "#galleryMain", "#lightbox",
        ".hero-strip .hero-stats", ".contact-block"
    ):
        one(approved, selector, "approved room")
    body["class"] = sorted(set(body.get("class", [])) | klass | {"room-foyer", "courtier-page"})
    body["data-courtier"] = mode
    body["data-room-template"] = "design/visual-home/index.html"

    # Editorial source, not the room, owns SEO, query and individual answer.
    approved.title.string = one(editorial, "head title", str(relative)).get_text(" ", strip=True)
    source_description = editorial.head.find("meta", attrs={"name": "description"})
    room_description = approved.head.find("meta", attrs={"name": "description"})
    if source_description is not None and room_description is not None:
        room_description["content"] = source_description.get("content", "")
    source_canonical = one(editorial, 'link[rel="canonical"]', str(relative))
    room_canonical = approved.head.select_one('link[rel="canonical"]')
    if room_canonical is None:
        room_canonical = approved.new_tag("link", rel="canonical")
        approved.head.append(room_canonical)
    room_canonical["href"] = source_canonical["href"]

    # Reuse the *actual* hero, not reconstructed tags with similar classes.
    hero_copy = one(approved, ".hero .hero-copy", "room hero")
    hero_copy["class"] = sorted(set(hero_copy.get("class", [])) | {
        "issue", "master-lead", "courtier-greeting"
    })
    one(hero_copy, ".eyebrow", "room hero").string = kicker.get_text(" ", strip=True)
    one(hero_copy, "h1.hero-title", "room hero").string = title
    subtitle = one(hero_copy, ".hero-subtitle", "room hero")
    subtitle.string = answer.get_text(" ", strip=True)
    subtitle["class"] = sorted(set(subtitle.get("class", [])) | {"entry-modulation"})
    buttons = one(hero_copy, ".hero-actions", "room hero").select("a.btn")
    if len(buttons) != 2:
        raise ValueError("Approved room has lost its two hero actions")
    buttons[0]["href"] = "tel:+79096945544"
    buttons[0]["class"] = sorted(set(buttons[0].get("class", [])) | {"courtier-call"})
    buttons[0].string = "Позвонить: +7 (909) 694-55-44"
    buttons[1]["href"] = root
    buttons[1]["class"] = sorted(set(buttons[1].get("class", [])) | {
        "courtier-enter", "foyer-door-enter"
    })
    buttons[1].string = "Войти в мастерскую"

    # 4 collection ranges retain the room's photographic hero-strip placement.
    old_stats = one(approved, ".hero-strip .hero-stats", "room stats")
    new_stats = approved.new_tag("nav", attrs={
        "class": "hero-stats entry-range-grid reveal visible",
        "aria-label": "Диапазоны коллекции"
    })
    for label, link in zip(
        ("Происхождение", "Уровень", "Музыка", "Доступность"),
        ranges.select("a[href]")
    ):
        item = deepcopy(link)
        item["class"] = ["stat"]
        item.clear()
        heading_tag = approved.new_tag("strong")
        heading_tag.string = label
        description = approved.new_tag("span")
        description.string = link.get_text(" ", strip=True)
        item.extend((heading_tag, description))
        new_stats.append(item)
    old_stats.replace_with(new_stats)

    # 4 real masterwork facts use the existing cards, not a second grid skin.
    cards = one(approved, "#workshop .cards-3", "room card grid")
    sample = cards.select_one("article.card.info-card")
    if sample is None:
        raise ValueError("Approved room cards missing")
    descriptions = (
        "Опыт мастерской в работе с контрабасами и музыкантами.",
        "Инструменты частной коллекции и возможные формы знакомства.",
        "Осмотр, настройка и работа с инструментом по согласованию.",
        "Возможность и условия перевозки уточняются при обращении.",
    )
    new_cards = approved.new_tag("nav", attrs={
        "class": "cards-3 entry-utilities",
        "aria-label": "Возможности мастерской"
    })
    for index, link in enumerate(witnesses.select("a[href]")):
        card = deepcopy(sample)
        card["class"] = sorted(set(card.get("class", [])) | {"reveal", "visible"})
        one(card, ".card-tag", "room card").string = (
            "Опыт", "Коллекция", "Ремесло", "Доставка"
        )[index]
        one(card, "h3", "room card").string = link.get_text(" ", strip=True)
        one(card, "p", "room card").string = descriptions[index]
        cta = one(card, "a.btn", "room card")
        cta["href"] = link["href"]
        cta.string = "Подробнее"
        new_cards.append(card)
    cards.replace_with(new_cards)

    # An existing verified diagram replaces one original room-card picture only
    # when the human query is really about a physical instrument component.
    if mode in {"neck", "seams", "anatomy"}:
        image = approved.select_one("#collection .mini-card .media img")
        if image is None:
            raise ValueError("Approved room comparison image missing")
        image["src"], image["alt"] = IMAGES[mode]
        image.attrs.pop("id", None)  # do not let the mood JS replace the diagram

    # Preserve source contact details while keeping the room's contact panel.
    one(approved, "#contact .contact-block", "room contact").replace_with(deepcopy(contact))
    footer = one(approved, ".site-shell > footer", "room footer")
    footer["class"] = sorted(set(footer.get("class", [])) | {"master-footer"})
    footer_links = one(footer, ".footer-inner > div:nth-of-type(2)", "room footer")
    footer_links.clear()
    footer_links.append("Москва · ")
    for link in editorial_footer.select("a[href]"):
        footer_links.append(deepcopy(link))
        footer_links.append(" · ")
    if footer_links.contents and footer_links.contents[-1] == " · ":
        footer_links.contents[-1].extract()

    # Rebase only asset paths originating in the room. The N.0's existing
    # contact/editorial destinations are already relative to its own route.
    for tag in approved.select("[src], [href]"):
        for attr in ("src", "href"):
            value = tag.get(attr, "")
            if not value or value.startswith(
                ("#", "/", "http:", "https:", "tel:", "mailto:", "data:")
            ):
                continue
            if value.startswith(("assets/", "archive/")):
                tag[attr] = root + value
    for script in approved.select("script:not([src])"):
        text = script.string or script.get_text()
        if text:
            script.string = text.replace("assets/photography/", root + "assets/photography/")

    # The complete original CSS is retained. These few scope-specific rules
    # only accommodate variable H1 lengths and the fourth genuine witness.
    patch = approved.new_tag("style")
    patch.string = """
      body.room-foyer .hero-title{font-size:clamp(2.65rem,5.5vw,5.75rem);overflow-wrap:anywhere}
      body.room-foyer .cards-3.entry-utilities{grid-template-columns:repeat(2,minmax(0,1fr))}
      body.room-foyer .entry-range-grid .stat{display:block;min-width:0;overflow-wrap:anywhere}
      body.room-foyer .entry-range-grid .stat strong{font-size:clamp(1.2rem,2vw,1.6rem)}
      @media(max-width:1180px){
        body.room-foyer .cards-3.entry-utilities{grid-template-columns:minmax(0,1fr)}
      }
    """
    approved.head.append(patch)

    rendered = str(approved)
    verify = BeautifulSoup(rendered, "html.parser")
    if (len(verify.select("h1")) != 1 or
        len(verify.select(".entry-modulation")) != 1 or
        len(verify.select("a.foyer-door-enter[href]")) != 1 or
        len(verify.select(".entry-range-grid a[href]")) != 4 or
        len(verify.select(".entry-utilities a[href]")) != 4 or
        len(verify.select(".contact-block")) != 1 or
        len(verify.select(".master-footer a[href]")) != 2 or
        len(verify.select(".hero .hero-media img")) != 1):
        raise ValueError(f"{relative}: room scene lost authored content or routes")
    return rendered, mode


def build(site: Path) -> dict:
    room_html = ROOM.read_text(encoding="utf-8")
    kinds = Counter()
    for file in sorted(site.rglob("*.html")):
        raw = file.read_text(encoding="utf-8")
        rendered, kind = transform(raw, file.relative_to(site), room_html)
        kinds[kind] += 1
        if rendered != raw:
            file.write_text(rendered, encoding="utf-8")
    return dict(kinds)
