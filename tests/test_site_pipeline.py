"""Regression tests for EasyBassMaster's editorial pipeline and privacy boundary."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from link_audit import audit
from site_core import DOMAIN, build, inspect_records, inspect_entrances, inspect_knowledge, inspect_model_publications, read_json
from entry_router import destination_for_family, destination_for_editorial_group
from validate_site import validate
from sensor_n0 import records as sensor_records
from modulation_audit import audit as modulation_audit


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.site = Path(self.temporary.name)
        for path in ("index.html", "styles.css", "collection/index.html",
                     "workshop/index.html", "meeting/index.html",
                     "experience/index.html", "delivery/index.html",
                     "workshop/maps/index.html"):
            target = self.site / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)
        # The approved hero is composed from exactly three image files.
        # Simulate Jekyll's copying of normal static artwork and foyer CSS.
        for source in (list((ROOT / "assets/photography").glob("*.webp")) +
                       [ROOT / "assets/visual/foyer.css"]):
            target = self.site / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        # Jekyll carries immutable, hand-authored vectors to the public build.
        for source in sorted((ROOT / "assets/maps").glob("*.svg")):
            target = self.site / "assets/maps" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        (self.site / "archive").mkdir(parents=True)
        (self.site / "archive/index.html").write_text(
            '<!doctype html><html lang="ru"><head><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><title>Подшивка</title>'
            '<link rel="stylesheet" href="../styles.css"></head><body>'
            '<h1>Подшивка</h1><a href="../">Главная</a>'
            '<!-- GENERATED_SUBJECT_INDEX --></body></html>', encoding="utf-8")

    def test_full_compilation_preserves_existing_home_and_publishes_only_ready(self):
        original = (self.site / "index.html").read_bytes()
        result = build(ROOT, self.site)
        self.assertEqual(result["generated_subjects"], 2)
        self.assertEqual(result["generated_pair_pages"], 4)
        self.assertEqual(result["hypotheses_retained"], 60)
        self.assertEqual(result["standalone_entrances"], 282)
        self.assertEqual(result["independent_knowledge_articles"], 11)
        self.assertEqual(result["official_model_articles"], 6)
        self.assertEqual(result["sensor_n0"]["n0_pages"], len(sensor_records(ROOT)))
        self.assertEqual(result["sensor_n0"]["synthetic_cartesian_pages"], 0)
        self.assertGreater(len(sensor_records(ROOT)), 100)
        self.assertEqual(result["sensor_n0"]["hubs"], 0)
        self.assertTrue(result["sensor_n0"]["closed_entrances"])
        self.assertIn("Пространство", (self.site / "index.html").read_text(encoding="utf-8"))
        self.assertNotEqual(original, (self.site / "index.html").read_bytes())  # one canonical added
        self.assertEqual(validate(self.site, ROOT)["errors"], [])

    def test_approved_home_is_single_room_without_secondary_homepage(self):
        from bs4 import BeautifulSoup
        home = BeautifulSoup((ROOT / "index.html").read_text(encoding="utf-8"), "html.parser")
        self.assertEqual(len(home.select("h1")), 1)
        self.assertEqual(home.select_one("h1").get_text(strip=True),
                         "Пространство, в котором можно найти свой.")
        self.assertEqual(len(home.select(".contact-block")), 1)
        self.assertEqual(len(home.select(".hero-stats .stat")), 4)
        self.assertIn("творчество", home.select_one(".hero-stats").get_text(" ", strip=True))
        self.assertIsNotNone(home.select_one("#modeSwitch"))
        self.assertEqual(len(list((ROOT / "assets/photography").glob("*.webp"))), 3)
        self.assertTrue(home.select("style"))  # exact room layout is intentionally self-styled
        self.assertFalse(home.select('link[href="styles.css"]'))  # no inherited typography conflict
        self.assertIn('src="assets/photography/room-golden.webp"', str(home))
        self.assertEqual(len(home.select(".foyer-door")), 0)

    def test_custom_domain_is_root_canonical_in_every_public_url(self):
        from site_core import BASE
        from validate_site import local_path

        self.assertEqual(DOMAIN, "https://easybassmaster.ru")
        self.assertEqual(BASE, "")
        jekyll = (ROOT / "_config.yml").read_text(encoding="utf-8")
        self.assertIn('baseurl: ""', jekyll)
        self.assertIn('url: "https://easybassmaster.ru"', jekyll)

        result = build(ROOT, self.site)
        # Local tests do not run Jekyll, so three issue pages join only during the real CI build.
        self.assertEqual(result["public_documents_in_sitemap"], len(list(self.site.rglob("*.html"))))
        sitemap = (self.site / "sitemap.xml").read_text(encoding="utf-8")
        robots = (self.site / "robots.txt").read_text(encoding="utf-8")
        home = (self.site / "index.html").read_text(encoding="utf-8")
        self.assertIn("https://easybassmaster.ru/", sitemap)
        self.assertNotIn("ontoslive.github.io/EasyBass.Master", sitemap)
        self.assertIn("Sitemap: https://easybassmaster.ru/sitemap.xml", robots)
        self.assertIn('<link rel="canonical" href="https://easybassmaster.ru/">', home)
        self.assertEqual(local_path(self.site, "/", "https://easybassmaster.ru/collection/"),
                         self.site / "collection/index.html")
        self.assertEqual(local_path(self.site, "/collection/", "../workshop/"),
                         self.site / "workshop/index.html")
        self.assertEqual(validate(self.site, ROOT)["errors"], [])

    def test_generated_page_titles_distinguish_access_and_knowledge(self):
        build(ROOT, self.site)
        access = (self.site / "kupit-masterovoy-kontrabas-v-moskve/index.html").read_text()
        deep = (self.site / "details/masterovoy-kontrabas/index.html").read_text()
        self.assertIn('<h1>Купить мастеровой контрабас в Москве</h1>', access)
        self.assertIn('<h1>Мастеровой контрабас</h1>', deep)
        self.assertIn('tel:+79096945544', access)
        self.assertIn('aria-label="Telegram"', deep)
        self.assertIn(DOMAIN + '/details/masterovoy-kontrabas/', deep)
        self.assertIn('class="max-contact-pending"', access)
        self.assertIn("https://t.me/+79096945544", access)
        self.assertNotIn('href="https://max.ru/', access)

    def test_internal_files_stay_outside_public_site(self):
        build(ROOT, self.site)
        for d in ("content", "docs", "scripts", "tests", "design"):
            self.assertFalse((self.site / d).exists())

    def test_prepublication_research_is_not_a_public_offer(self):
        records = inspect_records(ROOT)
        self.assertEqual(len(records), 2)
        self.assertEqual(len(inspect_entrances(ROOT)), 282)
        self.assertEqual(len(read_json(ROOT / "content/candidates.json")["candidates"]), 60)
        self.assertEqual(audit(ROOT)["errors"], [])
        candidates = read_json(ROOT / "content/candidates.json")["candidates"]
        self.assertEqual(sum(x["status"] == "entrance" for x in candidates), 56)
        self.assertEqual(sum(x["status"] == "implemented" for x in candidates), 2)
        self.assertEqual(sum(x["status"] == "research" for x in candidates), 2)

    def test_no_entry_fabricates_unwritten_knowledge_page(self):
        build(ROOT, self.site)
        example = inspect_entrances(ROOT)[0]
        self.assertTrue((self.site / example["slug"] / "index.html").exists())
        self.assertFalse((self.site / "details" / example["slug"] / "index.html").exists())
        self.assertIn(example["search_title"],
                      (self.site / example["slug"] / "index.html").read_text(encoding="utf-8"))

    def test_knowledge_is_independent_and_both_documents_are_indexable(self):
        essays = inspect_knowledge(ROOT, inspect_entrances(ROOT), inspect_records(ROOT))
        self.assertEqual(len(essays), 11)
        build(ROOT, self.site)
        for essay in essays:
            entry = (self.site / essay["entrance_slug"] / "index.html").read_text(encoding="utf-8")
            deep = (self.site / "details" / essay["slug"] / "index.html").read_text(encoding="utf-8")
            self.assertIn(essay["title"], deep)
            self.assertIn('<link rel="canonical" href="' + DOMAIN + "/details/" + essay["slug"] + '/">', deep)
            self.assertIn("../details/" + essay["slug"] + "/", entry)

    def test_five_workshop_maps_are_anatomical_and_connected_to_n1(self):
        import xml.etree.ElementTree as ET
        maps = (
            "anatomy.svg", "internal-structure.svg", "seams-cracks.svg",
            "neck-geometry.svg", "inspection-zones.svg",
        )
        for name in maps:
            asset = ROOT / "assets/maps" / name
            self.assertTrue(asset.is_file())
            doc = ET.parse(asset).getroot()
            self.assertEqual(doc.attrib["viewBox"], "0 0 1280 760")
            ns = {"svg": "http://www.w3.org/2000/svg"}
            self.assertIsNotNone(doc.find("svg:title", ns))
            self.assertIsNotNone(doc.find("svg:desc", ns))
            self.assertEqual(doc.findall(".//svg:script", ns), [])
            self.assertEqual(doc.findall(".//svg:image", ns), [])

        self.assertIn('href="maps/"', (ROOT / "workshop/index.html").read_text(encoding="utf-8"))
        essays = {a["slug"]: a for a in inspect_knowledge(ROOT, inspect_entrances(ROOT), inspect_records(ROOT))}
        assignments = {
            "pochemu-raskleivaetsya-kontrabas-shov-i-treschina":
                {"seams-cracks.svg", "internal-structure.svg"},
            "geometriya-grifa-kontrabasa-sheyka-nakladka":
                {"neck-geometry.svg"},
            "starinnyy-kontrabas-pered-remontom-osmotr-i-istoriya":
                {"anatomy.svg", "inspection-zones.svg"},
        }
        self.assertEqual({a["file"] for key in assignments for a in essays[key]["maps"]}, set(maps))
        for key, names in assignments.items():
            self.assertEqual({m["file"] for m in essays[key]["maps"]}, names)

        compiled = build(ROOT, self.site)
        self.assertEqual(compiled["public_documents_in_sitemap"], len(list(self.site.rglob("*.html"))))
        atlas = BeautifulSoup((self.site / "workshop/maps/index.html").read_text(encoding="utf-8"), "html.parser")
        self.assertEqual(len(atlas.select(".atlas-hub-figure img")), 5)
        self.assertEqual(len(atlas.select("main > .atlas-page")), 5)
        self.assertEqual(len(atlas.select("link[rel='canonical']")), 1)
        self.assertEqual(atlas.select_one("link[rel='canonical']")["href"], DOMAIN + "/workshop/maps/")
        self.assertEqual(len(atlas.select(".atlas-figure figcaption")), 5)
        self.assertTrue(all(x.get("alt", "").strip() for x in atlas.select(".atlas-figure img")))
        for key, names in assignments.items():
            page = BeautifulSoup((self.site / "details" / key / "index.html").read_text(encoding="utf-8"), "html.parser")
            self.assertEqual({img["src"].split("/")[-1] for img in page.select(".knowledge-text .atlas-figure img")}, names)
            self.assertIn("../../workshop/maps/", str(page.select("nav.master-links")))
            self.assertEqual(len(page.select(".knowledge-text > section")), 8)
        self.assertIn(DOMAIN + "/workshop/maps/", (self.site / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertEqual(validate(self.site, ROOT)["errors"], [])

    def test_three_repair_n1_articles_are_sourced_distinct_and_reachable(self):
        expected = {
            "pochemu-raskleivaetsya-kontrabas-shov-i-treschina":
                ("otoshel-shov-na-kontrabase", "Шов и трещина контрабаса: почему раскрывается корпус"),
            "geometriya-grifa-kontrabasa-sheyka-nakladka":
                ("remont-grifa-kontrabasa", "Гриф, шейка и накладка контрабаса: геометрия свободной игры"),
            "starinnyy-kontrabas-pered-remontom-osmotr-i-istoriya":
                ("kontrabas-posle-dlitelnogo-hraneniya", "Старинный контрабас перед ремонтом: как читать его состояние"),
        }
        essays = {e["slug"]: e for e in inspect_knowledge(ROOT, inspect_entrances(ROOT), inspect_records(ROOT))}
        self.assertEqual(len(essays), 11)
        for slug, (entry_slug, title) in expected.items():
            self.assertIn(slug, essays)
            essay = essays[slug]
            self.assertEqual(essay["entrance_slug"], entry_slug)
            self.assertEqual(essay["title"], title)
            self.assertGreaterEqual(len(essay["sections"]), 7)
            self.assertGreaterEqual(len(essay["sources"]), 3)
            words = sum(len(p.split()) for section in essay["sections"] for p in section["paragraphs"])
            self.assertGreater(words, 750)
            self.assertEqual(essay["status"], "ready")
            self.assertTrue(essay["reviewed"])

        result = build(ROOT, self.site)
        self.assertEqual(result["independent_knowledge_articles"], 11)
        sitemap = (self.site / "sitemap.xml").read_text(encoding="utf-8")
        archive = BeautifulSoup((self.site / "archive/index.html").read_text(encoding="utf-8"), "html.parser")
        self.assertNotIn("/vhod/", str(archive))
        for slug, (entry_slug, title) in expected.items():
            route = "/details/" + slug + "/"
            entry_html = (self.site / entry_slug / "index.html").read_text(encoding="utf-8")
            self.assertIn("../details/" + slug + "/", entry_html)
            page = BeautifulSoup((self.site / route.strip("/") / "index.html").read_text(encoding="utf-8"), "html.parser")
            self.assertEqual(page.h1.get_text(strip=True), title)
            self.assertEqual(page.select_one("link[rel='canonical']")["href"], DOMAIN + route)
            self.assertEqual(len(page.select(".knowledge-text > section")), 8)
            self.assertGreaterEqual(len(page.select(".knowledge-sources a[href]")), 3)
            self.assertIn(DOMAIN + route, sitemap)
            self.assertIn("details/" + slug + "/", str(archive))
            self.assertIsNotNone(page.select_one(".contact-block"))
        self.assertEqual(validate(self.site, ROOT)["errors"], [])

    def test_official_model_articles_are_sourced_not_storefronts(self):
        models = inspect_model_publications(ROOT)
        self.assertEqual(len(models), 6)
        build(ROOT, self.site)
        for model in models:
            html = (self.site / "models" / model["slug"] / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="../../styles.css"', html)
            self.assertIn('Данные изготовителя', html)
            self.assertIn(model["sources"][0]["url"], html)
            self.assertNotIn("в наличии", html.lower())

    def test_authored_short_entries_have_valid_canonical_and_no_fake_details(self):
        subjects = sensor_records(ROOT)
        self.assertGreater(len(subjects), 100)
        self.assertEqual(len({s["route"] for s in subjects}), len(subjects))
        self.assertTrue(all(s["source_status"] == "editorial_hypothesis_not_measured" for s in subjects))
        self.assertTrue(all("разница между размером и мензурой" not in s["title"] for s in subjects))
        build(ROOT, self.site)
        for topic in [subjects[0], subjects[len(subjects)//2], subjects[-1]]:
            filename = self.site / topic["route"].strip("/") / "index.html"
            self.assertTrue(filename.exists())
            html = filename.read_text(encoding="utf-8")
            self.assertIn(topic["title"], html)
            self.assertIn(DOMAIN + topic["route"], html)
            self.assertIn("tel:+79096945544", html)
            self.assertNotIn('href="../../../details/', html)

    def test_short_pages_route_to_contact_and_eight_live_site_paths(self):
        build(ROOT, self.site)
        examples = [
            "kupit-masterovoy-kontrabas-v-moskve/index.html",
            "kupit-kontrabas-v-moskve/index.html",
            "vhod/familiar-instruments/kontrabas-musima-kupit-v-moskve/index.html",
        ]
        # Resolve the generated sensor route from the actual registry.
        examples[-1] = sensor_records(ROOT)[0]["route"].strip("/") + "/index.html"
        for relative in examples:
            html = (self.site / relative).read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            self.assertEqual(len(soup.select(".entry-range-grid a[href]")), 4)
            self.assertEqual(len(soup.select(".entry-utilities a[href]")), 4)
            self.assertEqual(len(soup.select(".master-footer a[href]")), 2)
            self.assertEqual(len(soup.select(".footer-workshop-home[href]")), 1)
            for anchor in ("vremya-proishozhdenie", "uroven", "muzyka", "dostupnost"):
                self.assertIn("collection/#" + anchor, html)
            self.assertNotIn("showroom/", html)
            self.assertIn("collection/", html)
            self.assertIn("delivery/", html)
            self.assertEqual(len(soup.select(".contact-block")), 1)
            self.assertIsNone(soup.select_one(".brand-title"))
            self.assertIsNotNone(soup.select_one(".meta a[href]"))
            self.assertLess(html.index('class="contact-block'), html.index('class="entry-range-grid'))
            self.assertIn('href="tel:+79096945544"', html)
            self.assertEqual(len(soup.select(".max-contact-pending")), 1)
            self.assertIsNone(soup.select_one('a[aria-label="MAX"]'))
        self.assertIn("../details/masterovoy-kontrabas/",
                      (self.site / examples[0]).read_text(encoding="utf-8"))
        self.assertEqual(
            BeautifulSoup((self.site / examples[0]).read_text(encoding="utf-8"), "html.parser")
            .select(".master-footer a")[-1].get("href"), "../details/masterovoy-kontrabas/")
        for relative in examples:
            doc = BeautifulSoup((self.site / relative).read_text(encoding="utf-8"), "html.parser")
            self.assertTrue(doc.body.has_attr("class"))
            self.assertIn("entry-short", doc.body["class"])
            self.assertIsNone(doc.select_one(".master-lead .deck"))
            self.assertEqual(len(doc.select(".entry-signal,.n0-return,.entry-continuation")), 0)
            self.assertEqual(len(doc.select(".master-footer a[href]")), 2)
            self.assertNotIn("По теме", doc.get_text(" ", strip=True))
            self.assertNotIn("↗", doc.select_one(".master-footer").get_text(" ", strip=True))
        self.assertEqual(validate(self.site, ROOT)["errors"], [])

    def test_announcements_are_search_only_and_send_visitors_into_the_workshop(self):
        build(ROOT, self.site)
        self.assertFalse((self.site / "vhod/index.html").exists())
        self.assertFalse((self.site / "vhod/familiar-instruments/index.html").exists())
        archive = BeautifulSoup((self.site / "archive/index.html").read_text(encoding="utf-8"), "html.parser")
        self.assertFalse(archive.select(".archive-entrances,.n0-index-link"))
        self.assertNotIn("/vhod/", str(archive))
        example = sensor_records(ROOT)[0]
        ad = BeautifulSoup((self.site / example["route"].strip("/") / "index.html").read_text(encoding="utf-8"), "html.parser")
        target, label = destination_for_family(example["family_id"])
        self.assertEqual(ad.select(".master-footer a[href]")[-1].get("href"), "../../../" + target)
        self.assertEqual(ad.select(".footer-workshop-home")[0].get("href"), "../../../")
        self.assertEqual(len(ad.select("a[href*='/vhod/'],a[href='../']")), 0)
        unrelated = next(item for item in inspect_entrances(ROOT)
                         if item["slug"] not in {essay["entrance_slug"] for essay in
                         inspect_knowledge(ROOT, inspect_entrances(ROOT), inspect_records(ROOT))})
        old = BeautifulSoup((self.site / unrelated["slug"] / "index.html").read_text(encoding="utf-8"), "html.parser")
        dest, label = destination_for_editorial_group(unrelated["group"])
        self.assertEqual(old.select(".master-footer a[href]")[-1].get("href"), "../" + dest)
        self.assertEqual(len(archive.select("a[href*='/vhod/']")), 0)

    def test_generic_rental_and_setup_have_independent_commercial_entries(self):
        entries = {r["route"]: r for r in sensor_records(ROOT)}
        routes = {
            "/vhod/temporary-access/arenda-kontrabasa-v-moskve/": "Аренда контрабаса в Москве",
            "/vhod/acoustic-response/nastroyka-kontrabasa-v-moskve/": "Настройка контрабаса в Москве",
        }
        for route, heading in routes.items():
            self.assertIn(route, entries)
            self.assertEqual(entries[route]["title"], heading)
            self.assertTrue(entries[route]["bridge"])

        self.assertNotEqual(
            entries["/vhod/temporary-access/arenda-kontrabasa-v-moskve/"]["bridge"],
            entries["/vhod/acoustic-response/nastroyka-kontrabasa-v-moskve/"]["bridge"],
        )
        build(ROOT, self.site)
        for route, heading in routes.items():
            html = (self.site / route.strip("/") / "index.html").read_text(encoding="utf-8")
            parsed = BeautifulSoup(html, "html.parser")
            self.assertEqual(parsed.h1.get_text(strip=True), heading)
            self.assertEqual(parsed.select_one(".entry-modulation").get_text(strip=True), entries[route]["bridge"])
            self.assertIn("https://easybassmaster.ru" + route, html)
        self.assertEqual(validate(self.site, ROOT)["errors"], [])

    def test_repair_wave_one_has_independent_subjects_and_valid_public_paths(self):
        from sensor_n0 import records as repair_records
        expected = {
            "tresnula-obechayka-kontrabasa": "Треснула обечайка контрабаса",
            "razoshlas-fuga-deki-kontrabasa": "Разошлась фуга деки контрабаса",
            "kontrabas-gremit-vnutri-korpusa": "Контрабас гремит внутри корпуса",
            "grif-kontrabasa-othodit-ot-korpusa": "Гриф контрабаса отходит от корпуса",
            "remont-podgrifnika-kontrabasa": "Ремонт подгрифника контрабаса",
            "lyuftit-kreplenie-shpilya-kontrabasa": "Люфтит крепление шпиля контрабаса",
            "podstavka-kontrabasa-naklonilas": "Подставка контрабаса наклонилась",
            "treschina-kolkovoy-korobki-kontrabasa": "Трещина колковой коробки контрабаса",
            "otkleilas-pruzhina-kontrabasa": "Отклеилась пружина контрабаса",
            "prodavlena-deka-pod-dushkoy-kontrabasa": "Продавлена дека под душкой контрабаса",
            "slomalsya-verhniy-porozhek-kontrabasa": "Сломался верхний порожек контрабаса",
            "slomalsya-nizhniy-porozhek-kontrabasa": "Сломался нижний порожек контрабаса",
        }
        records = {record["route"]: record for record in repair_records(ROOT)}
        self.assertEqual(len(repair_records(ROOT)), 511)
        for slug, title in expected.items():
            route = "/vhod/repair-restoration/" + slug + "/"
            self.assertIn(route, records)
            self.assertEqual(records[route]["title"], title)
            self.assertTrue(40 <= len(records[route]["bridge"]) <= 160)

        build(ROOT, self.site)
        site_map = (self.site / "sitemap.xml").read_text(encoding="utf-8")
        for slug, title in expected.items():
            route = "/vhod/repair-restoration/" + slug + "/"
            filename = self.site / route.strip("/") / "index.html"
            self.assertTrue(filename.is_file())
            page = BeautifulSoup(filename.read_text(encoding="utf-8"), "html.parser")
            self.assertEqual(page.h1.get_text(strip=True), title)
            self.assertEqual(page.select_one(".entry-modulation").get_text(strip=True), records[route]["bridge"])
            self.assertEqual(len(page.select("link[rel='canonical']")), 1)
            self.assertEqual(page.select_one("link[rel='canonical']")["href"], DOMAIN + route)
            self.assertEqual(len(page.select(".entry-range-grid a[href]")), 4)
            self.assertEqual(len(page.select(".entry-utilities a[href]")), 4)
            self.assertEqual(len(page.select(".contact-block")), 1)
            self.assertIn(DOMAIN + route, site_map)
            self.assertFalse((self.site / "details" / slug / "index.html").exists())
            self.assertEqual(page.select(".master-footer a[href]")[-1]["href"], "../../../workshop/")
        self.assertEqual(validate(self.site, ROOT)["errors"], [])

    def test_request_specific_modulation_before_the_phone(self):
        build(ROOT, self.site)
        page = BeautifulSoup((self.site / "kontrabas-1-2-ili-3-4/index.html").read_text(encoding="utf-8"), "html.parser")
        bridge = page.select_one(".entry-modulation")
        self.assertIsNotNone(bridge)
        self.assertIn("рука достаёт позиции", bridge.get_text())
        self.assertLess(str(page).index('class="entry-modulation"'), str(page).index('class="contact-block'))
        musima = BeautifulSoup((self.site / "vhod/familiar-instruments/kontrabas-musima-kupit-v-moskve/index.html").read_text(encoding="utf-8"), "html.parser")
        self.assertIsNotNone(musima.select_one(".entry-modulation"))
        griff = BeautifulSoup((self.site / "vhod/ergonomic-neck/virtuoznyy-grif-dlya-kontrabasa/index.html").read_text(encoding="utf-8"), "html.parser")
        self.assertIn("накладку", griff.select_one(".entry-modulation").get_text())
        self.assertIn("высоту струн", griff.select_one(".entry-modulation").get_text())
        self.assertNotIn("наш конёк", griff.select_one(".entry-modulation").get_text())

    def test_all_modulation_debt_is_visible_in_editorial_audit(self):
        result = modulation_audit(ROOT)
        expected = len(inspect_records(ROOT)) + len(inspect_entrances(ROOT)) + len(sensor_records(ROOT))
        self.assertEqual(result["published_n0"], expected)
        self.assertEqual(result["critical_errors"], [])
        self.assertGreater(result["individual_gpt6_drafts"], 0)
        self.assertEqual(
            result["published_n0"],
            result["individual_gpt6_drafts"] + result["individual_gpt6_reviewed"] + result["editorial_backlog"]
        )
        # Existing indexed N.0 pages remain online while each gets its own GPT-6 text.
        self.assertEqual(result["editorial_backlog"], 0)
        self.assertEqual(result["individual_gpt6_drafts"] + result["individual_gpt6_reviewed"], result["published_n0"])
        self.assertTrue(result["complete"])

    def test_ranges_are_real_editorial_collection_anchors(self):
        from entry_router import RANGES, FACTS
        from bs4 import BeautifulSoup
        collection = BeautifulSoup((self.site / "collection/index.html").read_text(encoding="utf-8"), "html.parser")
        for target, label in RANGES:
            self.assertTrue(label)
            self.assertEqual(target.split("#")[0], "collection/")
            self.assertIsNotNone(collection.find(id=target.split("#")[1]))
        for target, label in FACTS:
            self.assertTrue(label)
            self.assertTrue((self.site / target / "index.html").exists())
        self.assertIn("пятидесяти", (self.site / "collection/index.html").read_text(encoding="utf-8"))
        self.assertFalse((self.site / "showroom/index.html").exists())

    def test_broken_archive_marker_stops_build(self):
        (self.site / "archive/index.html").write_text("<html><head></head><body></body></html>")
        with self.assertRaises(ValueError):
            build(ROOT, self.site)


if __name__ == "__main__":
    unittest.main()
