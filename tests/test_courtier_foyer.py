"""The Courtier is a rendered SEARCH document, not a second destination."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from courtier_foyer import transform, scene_for


def example(title: str, depth: int = 1) -> tuple[str, Path]:
    root = "../" * depth
    route = Path(*(["vhod"] + ["sample"] * (depth-1) + ["index.html"])) if depth > 1 else Path("sample/index.html")
    return f"""<!doctype html><html lang="ru"><head>
<title>{title} · EasyBassMaster</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="canonical" href="https://easybassmaster.ru/{route.parent.as_posix()}/">
<link rel="stylesheet" href="{root}styles.css">
<link rel="stylesheet" href="{root}assets/visual/foyer.css">
</head><body class="new-master entry-router entry-short entry-has-modulation foyer-page">
<div class="rule"></div>
<div class="meta"><a href="{root}">EASYBASSMASTER</a><span>МОСКВА</span></div>
<main>
<section class="issue master-lead">
<p class="issue-kicker">МАСТЕРСКАЯ КОНТРАБАСА</p>
<h1>{title}</h1><p class="entry-modulation">Индивидуальный ответ на конкретный вопрос.</p>
</section>
<section class="contact-block" aria-label="Контакт"><div class="contact">
<a class="contact-phone" href="tel:+79096945544">+7 (909) 694-55-44</a>
<div class="contact-icons">
<a aria-label="Telegram" href="https://t.me/+79096945544"><svg></svg></a>
<a aria-label="WhatsApp" href="https://wa.me/79096945544"><svg></svg></a>
<span class="max-contact-pending"><svg></svg></span>
</div></div></section>
<section class="foyer-door foyer-door-search">
<div class="foyer-door-image"><img src="{root}assets/photography/room-golden.webp" alt="Комната"></div>
<div class="foyer-door-copy"><h2>За вопросом есть комната.</h2>
<a class="foyer-door-enter" href="{root}">Войти в мастерскую <span>↗</span></a>
</div></section>
<div class="entry-router-links">
<nav class="entry-range-grid" aria-label="Диапазоны коллекции">
<a href="{root}collection/#a">A</a><a href="{root}collection/#b">B</a>
<a href="{root}collection/#c">C</a><a href="{root}collection/#d">D</a></nav>
<nav class="entry-utilities" aria-label="О мастерской">
<a href="{root}experience/">Факт</a><a href="{root}collection/">Коллекция</a>
<a href="{root}workshop/">Ремонт</a><a href="{root}delivery/">Доставка</a></nav></div>
<footer class="master-footer"><a href="{root}" class="footer-workshop-home">Мастерская</a>
<a href="{root}details/masterovoy-kontrabas/">Подробнее</a></footer>
</main></body></html>""", route


class FoyerTests(unittest.TestCase):
    def test_direct_entry_and_preserved_author_voice(self):
        for title,mode in [
            ("Купить мастеровой контрабас в Москве", "collection"),
            ("Ремонт грифа контрабаса", "neck"),
            ("Контрабас 1/2 или 3/4", "room"),
            ("Аренда контрабаса для концерта", "evening"),
            ("Отошёл шов на контрабасе", "seams"),
        ]:
            raw,route=example(title,depth=3)
            out,kind=transform(raw,route)
            self.assertEqual(kind,mode)
            doc=BeautifulSoup(out,"html.parser")
            self.assertEqual(doc.h1.get_text(" ",strip=True),title)
            self.assertEqual(doc.select_one(".entry-modulation").get_text(" ",strip=True),
                             "Индивидуальный ответ на конкретный вопрос.")
            self.assertEqual(doc.select_one(".courtier-enter")["href"],"../../../")
            self.assertEqual(doc.select_one(".courtier-portal")["href"],"../../../")
            self.assertFalse(doc.select('a[href*="/foyer/"]'))
            self.assertEqual(len(doc.select('a[href^="tel:"]')),1)
            self.assertEqual(len(doc.select(".entry-range-grid a")),4)
            self.assertEqual(len(doc.select(".entry-utilities a")),4)
            self.assertEqual(len(doc.select(".master-footer a")),2)
            self.assertEqual(len(doc.select("h1")),1)
            self.assertEqual(len(doc.select(".contact-block")),1)
            self.assertEqual(len(doc.select("a.foyer-door-enter")),1)
            self.assertEqual(len(doc.select('link[href$="courtier.css"]')),1)
            self.assertEqual(doc.select_one('link[rel="canonical"]')["href"],
                             f"https://easybassmaster.ru/{route.parent.as_posix()}/")
            # The APPROVED ROOM is the visual parent of every N.0. No
            # newspaper stylesheet or separately invented Courtier skin.
            styles = [x["href"] for x in doc.select('head link[rel="stylesheet"]')]
            self.assertEqual(styles, ["../../../assets/visual/room-parent.css",
                                      "../../../assets/visual/courtier.css"])
            self.assertIn("room-child", doc.body.get("class", []))
            self.assertEqual(len(doc.select(".topbar .brand-mark")), 1)
            self.assertEqual(len(doc.select(".hero .hero-media img")), 1)
            self.assertEqual(len(doc.select(".hero-grid.courtier-stage")), 1)
            self.assertEqual(len(doc.select(".hero-title")), 1)
            self.assertEqual(len(doc.select(".hero-strip .hero-stats a.stat")), 4)
            self.assertEqual(len(doc.select(".entry-utilities a.card.info-card")), 4)
            self.assertEqual(len(doc.select(".courtier-portal.card.mini-card")), 1)
            self.assertEqual(len(doc.select("a.courtier-enter.btn.primary")), 1)
            self.assertEqual(transform(out,route)[0],out)

    def test_non_n0_preserved(self):
        raw='<html><body class="new-master deep-editorial"><h1>Знание</h1></body></html>'
        out,kind=transform(raw,Path("details/knowledge/index.html"))
        self.assertEqual(kind,"not-n0")
        self.assertEqual(raw,out)

    def test_cannot_invent_a_missing_answer_or_contact(self):
        raw,route=example("Ремонт грифа контрабаса")
        with self.assertRaises(ValueError):
            transform(raw.replace('class="entry-modulation"','class="unwritten"'),route)
        with self.assertRaises(ValueError):
            transform(raw.replace("tel:+79096945544","tel:+79000000000"),route)

    def test_anatomical_visual_requires_actual_anatomical_query(self):
        self.assertEqual(scene_for("Ремонт грифа контрабаса"),"neck")
        self.assertEqual(scene_for("Восстановление фуги и трещины"),"seams")
        self.assertEqual(scene_for("Настройка контрабаса"),"anatomy")
        self.assertEqual(scene_for("Выбор первого контрабаса"),"room")


if __name__=="__main__":
    unittest.main()
