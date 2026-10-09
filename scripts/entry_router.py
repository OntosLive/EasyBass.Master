"""Shared N.0 navigation: four musical ranges and four real workshop facts."""
from html import escape

RANGES=(
 ("collection/#obuchenie","Обучение · от первого инструмента до консерватории"),
 ("collection/#orkestr","Оркестр · от ансамбля до профессиональной сцены"),
 ("collection/#solo","Соло · смычковая игра и выступления"),
 ("collection/#dzhaz","Джаз и рокабилли · пиццикато и слэп"),
)
FACTS=(
 ("experience/","15 лет · более 1000 контрабасов"),
 ("workshop/","Только контрабасы"),
 ("showroom/","Шоурум · более 50"),
 ("delivery/","Доставка по России"),
)

def route_panel(route: str) -> str:
    """Brief newspaper announcement: eight genuine site-internal links."""
    if not (route.startswith("/") and route.endswith("/")):
        raise ValueError(f"Invalid entry route: {route}")
    prefix="../"*len([part for part in route.strip("/").split("/") if part])
    def a(url,label):
        if url.split("#",1)[0]==route.lstrip("/"):
            raise ValueError(f"Self-link on {route}")
        return f'<a href="{escape(prefix+url,quote=True)}"><span>{escape(label)}</span></a>'
    return ('<div class="entry-router-links">'
            '<nav class="entry-range-grid" aria-label="Диапазоны музыкальной практики">'
            + ''.join(a(*item) for item in RANGES) + '</nav>'
            '<nav class="entry-utilities" aria-label="О мастерской">'
            + ''.join(a(*item) for item in FACTS) + '</nav></div>')
