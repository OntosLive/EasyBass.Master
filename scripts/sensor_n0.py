#!/usr/bin/env python3
"""N.0 sensor publication: scene + focused distinction -> one brief public address.

N.1 is a separate editorial object. N.0 never fabricates detailed prose,
models in stock, a guaranteed price, or an offered service.
The public corpus is *short entrance pages*, not 3,290 full articles.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DICT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"
}
STOP = {"для", "без", "что", "этот", "перед", "после", "между", "пока", "того"}
ROUTE_ROOT = "/vhod/"


def slugify(raw: str) -> str:
    letters = "".join(DICT.get(c, c) for c in raw.lower())
    return re.sub(r"[^a-z0-9]+", "-", letters).strip("-")


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def intent_variant(s: str) -> str:
    """One short, human-scale interpretation of the actual situation."""
    lower = s.lower()
    cases = [
        (("ребён", "ученик"), "Растущая рука и ещё складывающаяся техника способны менять само ощущение размера."),
        (("студент", "училищ", "консерватор", "экзамен"), "Учебный репертуар даёт возможность проверять инструмент на знакомых трудных местах."),
        (("оркестр", "симфоничес"), "Смычковая атака и устойчивость звука становятся заметны внутри плотного ансамбля."),
        (("джаз", "пицц", "рокабилли"), "Здесь интерес часто связан с движением пальцев, ритмом и формой атаки."),
        (("соло", "конкурс", "прослушиван"), "В сольной работе и прослушивании особенно слышен отклик на тонкие исполнительские изменения."),
        (("гриф", "позици", "мензур", "высот"), "Геометрия проявляется в реальном движении руки, а не только в размере корпуса."),
        (("трещин", "шов", "разош", "слом", "поврежд"), "Видимый след способен оказаться частью более сложной конструктивной истории."),
        (("старин", "этикет", "истор", "атрибуц"), "Историческая версия и то, что можно наблюдать в инструменте, иногда расходятся."),
        (("перевоз", "гастрол", "переезд", "поезд"), "Большой инструмент существует в условиях дороги, пространства и ответственности за сохранность."),
        (("перв", "начал", "знакомств"), "У человека может ещё не быть собственного эталона, с которым он сравнивает контрабасы."),
        (("аренд", "временн", "срок", "сезон"), "Музыкальная практика уже существует, а форма будущего владения может оставаться открытой."),
        (("покуп", "купит", "дорог", "денег", "цен"), "Здесь могут существовать сразу два вопроса: ценность инструмента и время принятия решения."),
        (("прода", "владел", "выкуп", "обмен"), "Передача инструмента касается и его нынешнего владельца, и ещё неизвестного следующего музыканта."),
        (("смыч", "атак", "волос"), "Начало звука иногда рассказывает об инструменте больше, чем общая громкость."),
        (("струн", "натяжен", "канифол", "пьез"), "Комплект и настройка взаимодействуют с конкретным корпусом и исполнительским движением."),
        (("душк", "подставк", "настройк"), "Небольшая деталь может связывать удобство игры и поведение целого корпуса."),
        (("скрип", "альт", "виолон", "бас-гитар", "безлад"), "Опыт другого инструмента способен стать преимуществом и одновременно новым вопросом."),
    ]
    for words, insight in cases:
        if any(word in lower for word in words):
            return insight
    return "У этой ситуации есть собственные обстоятельства, которые становятся заметными при знакомстве с инструментом."


def lens(question: str, notes: list[dict], fallback: dict) -> dict:
    text = question.lower().replace("ё", "е")
    weighted = []
    for i, item in enumerate(notes):
        matches = [stem for stem in item["stems"] if len(stem) > 2 and stem.replace("ё", "е") in text]
        if matches:
            weighted.append((max(len(stem) for stem in matches), -i, item))
    return sorted(weighted, reverse=True)[0][2] if weighted else fallback


def records(root: Path = ROOT) -> list[dict]:
    seeds = json.loads((root / "content/atlas/family-seeds.json").read_text(encoding="utf-8"))
    copy = json.loads((root / "content/atlas/n0-sensor-copy.json").read_text(encoding="utf-8"))
    explanations = {f["family"]: f for f in copy["families"]}
    if {f["id"] for f in seeds["families"]} != set(explanations):
        raise ValueError("Every research family must have an authored N.0 basis")
    output = []
    seen_routes = set()
    seen_titles = set()
    for family in seeds["families"]:
        family_id = family["id"]
        original = explanations[family_id]
        for i, scene in enumerate(family["scenes"], 1):
            scene_slug = slugify(scene)
            if not scene_slug:
                raise ValueError("No Russian scene slug")
            for j, question in enumerate(family["questions"], 1):
                question_slug = slugify(question)
                route = f"{ROUTE_ROOT}{family_id}/{scene_slug}-{question_slug}/"
                if route in seen_routes:
                    raise ValueError(f"Repeated URL in atlas: {route}")
                seen_routes.add(route)
                title = f"{cap(scene)}: {question}"
                if title.casefold() in seen_titles:
                    raise ValueError(f"Duplicated H1 {title}")
                seen_titles.add(title.casefold())
                focus = lens(question, copy["lenses"], copy["default_lens"])
                output.append({
                    "id": f"H-{family_id}-{i}-{j}",
                    "route": route,
                    "hub": f"{ROUTE_ROOT}{family_id}/",
                    "family_id": family_id,
                    "family_title": family["title"],
                    "scene_id": i,
                    "question_id": j,
                    "scene": cap(scene),
                    "angle": cap(question),
                    "title": title,
                    "description": f"{cap(scene)}. {cap(question)}. Мастерская контрабаса, Москва.",
                    "lead": original["scene_note"],
                    "context": intent_variant(scene),
                    "family_context": original["context_note"],
                    "focus_observation": focus["observation"],
                    "residual_question": focus["question"],
                    "status": "n0",
                    "source_status": "hypothetical_intent",
                })
    if len(output) != 3290:
        raise ValueError(f"Expected 3290 rooted short entrances; got {len(output)}")
    return output


def html_for(record: dict, contact: str, frame) -> str:
    """One printed, short answer + direct phone; never imitates an N.1 encyclopedia."""
    route = record["route"]
    source = {
        "entry_slug": route.strip("/"),
        "search_title": record["title"],
        "entry_kicker": record["family_title"].upper(),
        "entry_deck": record["lead"],
        "description": record["description"],
    }
    p = (
        '<section class="master-text n0-sensor">'
        f'<p class="n0-context">{escape(record["scene"])}. {escape(record["context"])}</p>'
        f'<p>{escape(record["family_context"])}</p>'
        f'<p>{escape(record["angle"])}. {escape(record["focus_observation"])}</p>'
        f'<p class="entrance-question">{escape(record["residual_question"])}</p>'
        '</section>'
    )
    # Aside from the contact and common archive footer, one useful route goes up
    # to the question's own printed subject family, never to a fake product.
    p += (f'<nav class="n0-return" aria-label="Родственные вопросы">'
          f'<a href="../">Другие вопросы этой темы</a></nav>')
    return frame(source, "entry", p, contact, route_override=route)


def index_page(hub: str, family: dict, subset: list[dict], contact: str, frame) -> str:
    """An accessible reading index grouped by scene, not an unwieldy 3K card grid."""
    by_scene: dict[int, list[dict]] = defaultdict(list)
    for item in subset:
        by_scene[item["scene_id"]].append(item)
    items = ['<section class="n0-list" aria-label="Подшивка вопросов">']
    for scene_id, group in sorted(by_scene.items()):
        lead = group[0]
        items.append('<details class="n0-scene"><summary>'
                     + escape(lead["scene"]) + f' <small>{len(group)}</small></summary><ul>')
        for p in group:
            label = p["angle"]
            # Project Pages is mounted under /EasyBass.Master/, not the domain root.
            items.append('<li><a href="' + escape("/EasyBass.Master" + p["route"], quote=True)
                         + '">' + escape(label) + '</a></li>')
        items.append('</ul></details>')
    items.append('</section>')
    first = subset[0]
    source = {
        "entry_slug": hub.strip("/"),
        "search_title": family["title"],
        "entry_kicker": "ПОДШИВКА · ПРЕДМЕТНЫЕ ВОПРОСЫ",
        "entry_deck": ("Каждая запись начинает самостоятельный разговор о контрабасе. "
                       "Внутри собраны вопросы, которые могут возникать в разных жизненных ситуациях."),
        "description": family["title"] + ". Исследовательские входы EasyBassMaster.",
    }
    items.append('<nav class="n0-return"><a href="../">Все направления</a></nav>')
    return frame(source, "entry", "".join(items), contact, route_override=hub)


def root_page(families: list[dict], rows: list[dict], contact: str, frame) -> str:
    count = Counter(x["family_id"] for x in rows)
    sections = ['<section class="n0-list" aria-label="Подшивка входов">']
    for family in families:
        name, family_id = family["title"], family["id"]
        sections.append('<article class="n0-family-line"><h2><a href="'
                        + escape(f"/EasyBass.Master/vhod/{family_id}/", quote=True)
                        + '">' + escape(name) + '</a></h2>'
                        f'<p>{count[family_id]} предметных вопросов</p></article>')
    sections.append('</section>')
    source = {"entry_slug": "vhod", "search_title": "Подшивка входов",
              "entry_kicker": "МАСТЕРСКАЯ КОНТРАБАСА · ПОДШИВКА",
              "entry_deck": ("Короткие тексты о встрече музыканта с инструментом. "
                             "За каждым вопросом может начаться собственный разговор."),
              "description": "Предметные маршруты знакомства с контрабасом."}
    return frame(source, "entry", "".join(sections), contact, route_override="/vhod/")


def compile_site(root: Path, site: Path, contact: str, frame, write) -> dict:
    seed = json.loads((root / "content/atlas/family-seeds.json").read_text(encoding="utf-8"))
    all_rows = records(root)
    indexed = defaultdict(list)
    for item in all_rows:
        write(site, item["route"], html_for(item, contact, frame))
        indexed[item["family_id"]].append(item)
    for family in seed["families"]:
        hub = f"{ROUTE_ROOT}{family['id']}/"
        write(site, hub, index_page(hub, family, indexed[family["id"]], contact, frame))
    write(site, "/vhod/", root_page(seed["families"], all_rows, contact, frame))
    archive = site / "archive/index.html"
    markup = archive.read_text(encoding="utf-8")
    hook = '<!-- SENSOR_N0_INDEX -->'
    if markup.count(hook) != 1:
        raise ValueError("The archive must have exactly one sensor root insertion point")
    insertion = ('<section class="archive-list n0-index-link">'
                 '<p class="issue-kicker">ПОИСКОВЫЕ ВХОДЫ · САМЫЙ КОРОТКИЙ ТЕКСТ</p>'
                 '<article><h2><a href="/EasyBass.Master/vhod/">Подшивка вопросов о контрабасе</a></h2>'
                 f'<p>{len(all_rows)} коротких входов в двадцати семействах: каждый открывает одну'
                 ' предметную ситуацию и прямой контакт с мастерской.</p></article></section>')
    archive.write_text(markup.replace(hook, insertion), encoding="utf-8")
    return {"n0_pages": len(all_rows), "families": len(indexed),
            "hubs": len(indexed) + 1,
            "first": all_rows[0]["route"], "last": all_rows[-1]["route"]}


if __name__ == "__main__":
    summary = records()
    print(json.dumps({"records": len(summary), "first": summary[0]["route"],
                      "last": summary[-1]["route"]}, ensure_ascii=False))
