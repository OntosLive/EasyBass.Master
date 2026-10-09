"""Eight compact ranges/facts and direct exits into the real master workshop.

N.0 is a search-only arrival. Visitors should be invited to the workshop,
collection, meeting or an existing N.1, never into another list of ads.
"""
from html import escape

RANGES = (
    ("collection/#vremya-proishozhdenie", "Старинные · современные\nФабричные · мастеровые"),
    ("collection/#uroven", "Ученические · профессиональные"),
    ("collection/#muzyka", "Соло · оркестр\nДжаз · рокабилли"),
    ("collection/#dostupnost", "Доступные · коллекционные"),
)

# Every item describes a real possibility and opens its corresponding room.
FACTS = (
    ("experience/", "15 лет работы · 1000+ контрабасов"),
    ("collection/", "Продажа · аренда · коллекция 50+"),
    ("workshop/", "Ремонт · реставрация · доработка"),
    ("delivery/", "Доставка по России"),
)

# An announcement always exits to a real institutional page, not another N.0.
AUTHOR_DESTINATIONS = {
    "familiar-instruments": ("collection/", "Коллекция"),
    "buy-and-compare": ("meeting/", "Знакомство"),
    "price-and-ownership": ("collection/", "Коллекция"),
    "learning-and-families": ("meeting/", "Знакомство"),
    "ergonomic-neck": ("workshop/", "Мастерская"),
    "acoustic-response": ("workshop/", "Мастерская"),
    "repair-restoration": ("workshop/", "Мастерская"),
    "body-compatibility": ("workshop/", "Мастерская"),
    "sell-and-transition": ("meeting/", "Предложить инструмент"),
    "appraisal-and-authentication": ("workshop/", "Мастерская"),
    "classical-performance": ("meeting/", "Знакомство"),
    "jazz-rockabilly": ("meeting/", "Знакомство"),
    "strings-bows-hardware": ("workshop/", "Мастерская"),
    "movement-and-logistics": ("delivery/", "Доставка"),
    "temporary-access": ("meeting/", "Обсудить аренду"),
    "sizes-and-form": ("collection/", "Коллекция"),
    "private-collection": ("meeting/", "Знакомство"),
    "recording-film-stage": ("meeting/", "Знакомство"),
}

OLD_EDITORIAL_DESTINATIONS = {
    "Покупка и подбор": ("meeting/", "Знакомство"),
    "Аренда и пользование": ("meeting/", "Обсудить аренду"),
    "Продажа владельцем и оценка": ("meeting/", "Предложить инструмент"),
    "Ремонт и реставрация": ("workshop/", "Мастерская"),
    "Конструкция и выбор": ("collection/", "Коллекция"),
    "Исполнительские ситуации": ("meeting/", "Знакомство"),
    "Струны, смычки и звук": ("workshop/", "Мастерская"),
    "Хранение и перевозка": ("delivery/", "Доставка"),
    "Происхождение и история": ("collection/", "Коллекция"),
    "Звучание и исполнительские препятствия": ("workshop/", "Мастерская"),
    "Покупка: обстоятельства и выбор": ("meeting/", "Знакомство"),
    "Продажа: история и выбор маршрута": ("meeting/", "Предложить инструмент"),
    "Бас-гитара, безлад и переход к контрабасу": ("meeting/", "Знакомство"),
    "Марки, школы и названия инструментов": ("collection/", "Коллекция"),
}


def destination_for_family(family: str) -> tuple[str, str]:
    try:
        return AUTHOR_DESTINATIONS[family]
    except KeyError as exc:
        raise ValueError(f"No institutional continuation for {family}") from exc


def destination_for_editorial_group(group: str) -> tuple[str, str]:
    try:
        return OLD_EDITORIAL_DESTINATIONS[group]
    except KeyError as exc:
        raise ValueError(f"No institutional continuation for {group}") from exc


def route_panel(route: str) -> str:
    """Eight site-internal routes, with one upper cell for each range."""
    if not (route.startswith("/") and route.endswith("/")):
        raise ValueError(f"Invalid entry route: {route}")
    prefix = "../" * len([part for part in route.strip("/").split("/") if part])
    def a(url: str, label: str) -> str:
        if url.split("#", 1)[0] == route.lstrip("/"):
            raise ValueError(f"Self-link on {route}")
        return f'<a href="{escape(prefix + url, quote=True)}"><span>{escape(label)}</span></a>'
    return ('<div class="entry-router-links">'
            '<nav class="entry-range-grid" aria-label="Диапазоны коллекции">'
            + ''.join(a(*item) for item in RANGES) + '</nav>'
            '<nav class="entry-utilities" aria-label="О мастерской">'
            + ''.join(a(*item) for item in FACTS) + '</nav></div>')
