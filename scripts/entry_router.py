"""The ONTOS.RENT eight-link short-page contract, adapted to EasyBassMaster.

Four concrete relationship routes + four institutional rooms.
These are public navigation links, not HTTP redirects or inventory promises.
"""
from __future__ import annotations
from html import escape

# Each fallback avoids a self-link on the corresponding action's own entry.
ACTION_ROUTES = (
    ("kupit-kontrabas-v-moskve/", "Подобрать контрабас",
     "vybrat-kontrabas-s-vozmozhnostyu-proby/"),
    ("dolgosrochnaya-arenda-kontrabasa/", "Арендовать контрабас",
     "arenda-kontrabasa-dlya-zanyatiy/"),
    ("prodat-kontrabas-v-moskve/", "Продать контрабас",
     "otsenit-kontrabas-pered-prodazhey/"),
    ("remont-kontrabasa-v-moskve/", "Ремонт и настройка",
     "nastroyka-podstavki-kontrabasa/"),
)

SPACE_ROUTES = (
    ("collection/", "Коллекция"),
    ("workshop/", "Мастерская"),
    ("meeting/", "Знакомство"),
    ("archive/", "Подшивка"),
)


def route_panel(route: str) -> str:
    """Render eight verified site-internal routes relative to any N.0 depth."""
    if not route.startswith("/") or not route.endswith("/"):
        raise ValueError(f"Expected canonical short entry route: {route}")
    depth = len([part for part in route.strip("/").split("/") if part])
    prefix = "../" * depth
    current = route.lstrip("/")

    def link(target: str, label: str, alternate: str = "") -> str:
        destination = alternate if target == current else target
        if destination == current:
            raise ValueError(f"Self-link in short route panel: {route}")
        return (f'<a href="{escape(prefix + destination, quote=True)}">'
                f'<span>{escape(label)}</span></a>')

    opportunities = "".join(link(target, label, alternate)
                            for target, label, alternate in ACTION_ROUTES)
    spaces = "".join(link(target, label) for target, label in SPACE_ROUTES)
    return (
        '<div class="entry-router-links">'
        '<nav class="entry-range-grid" aria-label="Возможности мастерской">'
        + opportunities + '</nav>'
        '<nav class="entry-utilities" aria-label="Пространства мастерской">'
        + spaces + '</nav></div>'
    )
