"""Shared eight-link navigator on short EasyBassMaster newspaper entrances.

One upper cell represents one RANGE; the first cell combines time and making.
Four lower cells introduce genuine features of the private master workshop.
No catalogue stock or lowest-market-price guarantee is inferred from these labels.
"""
from html import escape

RANGES = (
    ("collection/#vremya-proishozhdenie", "От старинных до современных\nОт фабричных до мастеровых"),
    ("collection/#uroven", "От ученических до профессиональных"),
    ("collection/#muzyka", "От сольной и оркестровой игры до джаза и рокабилли"),
    ("collection/#dostupnost", "От самых доступных до редких коллекционных"),
)
FACTS = (
    ("experience/", "15 лет · более 1000 контрабасов"),
    ("workshop/", "Только контрабасы"),
    ("collection/", "Частная коллекция · более 50"),
    ("delivery/", "Доставка по России"),
)

def route_panel(route: str) -> str:
    """Four meaningful ranges + four direct doors to the workshop."""
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
