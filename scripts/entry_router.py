"""Eight concise, meaningful directions shared by newspaper entries.

Each of the four primary cells represents one RANGE of the collection,
not four product categories. Four small links open the real workshop.
"""
from html import escape

RANGES = (
    ("collection/#vremya-proishozhdenie", "Старинные · современные\nФабричные · мастеровые"),
    ("collection/#uroven", "Ученические · профессиональные"),
    ("collection/#muzyka", "Соло · оркестр\nДжаз · рокабилли"),
    ("collection/#dostupnost", "Доступные · коллекционные"),
)
FACTS = (
    ("experience/", "15 лет · 1000+ инструментов"),
    ("workshop/", "Только контрабасы"),
    ("collection/", "Коллекция · 50+"),
    ("delivery/", "Доставка по России"),
)


def route_panel(route: str) -> str:
    """Eight site-internal links, no self-links, no synthetic pages."""
    if not (route.startswith("/") and route.endswith("/")):
        raise ValueError(f"Invalid entry route: {route}")
    prefix = "../" * len([part for part in route.strip("/").split("/") if part])
    def a(url, label):
        if url.split("#", 1)[0] == route.lstrip("/"):
            raise ValueError(f"Self-link on {route}")
        return f'<a href="{escape(prefix + url, quote=True)}"><span>{escape(label)}</span></a>'
    return ('<div class="entry-router-links">'
            '<nav class="entry-range-grid" aria-label="Диапазоны коллекции">'
            + ''.join(a(*item) for item in RANGES) + '</nav>'
            '<nav class="entry-utilities" aria-label="О мастерской">'
            + ''.join(a(*item) for item in FACTS) + '</nav></div>')
