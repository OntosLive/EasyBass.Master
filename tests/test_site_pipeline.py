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
from validate_site import validate
from sensor_n0 import records as sensor_records


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.site = Path(self.temporary.name)
        for path in ("index.html", "styles.css", "collection/index.html",
                     "workshop/index.html", "meeting/index.html"):
            target = self.site / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)
        (self.site / "archive").mkdir(parents=True)
        (self.site / "archive/index.html").write_text(
            '<!doctype html><html lang="ru"><head><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><title>Подшивка</title>'
            '<link rel="stylesheet" href="../styles.css"></head><body>'
            '<h1>Подшивка</h1><a href="../">Главная</a>'
            '<!-- GENERATED_SUBJECT_INDEX --><!-- SENSOR_N0_INDEX --></body></html>', encoding="utf-8")

    def test_full_compilation_preserves_existing_home_and_publishes_only_ready(self):
        original = (self.site / "index.html").read_bytes()
        result = build(ROOT, self.site)
        self.assertEqual(result["generated_subjects"], 2)
        self.assertEqual(result["generated_pair_pages"], 4)
        self.assertEqual(result["hypotheses_retained"], 60)
        self.assertEqual(result["standalone_entrances"], 282)
        self.assertEqual(result["independent_knowledge_articles"], 8)
        self.assertEqual(result["official_model_articles"], 6)
        self.assertEqual(result["sensor_n0"]["n0_pages"], 3290)
        self.assertEqual(result["sensor_n0"]["hubs"], 21)
        self.assertIn("Пространство", (self.site / "index.html").read_text(encoding="utf-8"))
        self.assertNotEqual(original, (self.site / "index.html").read_bytes())  # one canonical added
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
        self.assertNotIn("MAX", access)

    def test_internal_files_stay_outside_public_site(self):
        build(ROOT, self.site)
        for d in ("content", "docs", "scripts", "tests"):
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
        self.assertEqual(len(essays), 8)
        build(ROOT, self.site)
        for essay in essays:
            entry = (self.site / essay["entrance_slug"] / "index.html").read_text(encoding="utf-8")
            deep = (self.site / "details" / essay["slug"] / "index.html").read_text(encoding="utf-8")
            self.assertIn(essay["title"], deep)
            self.assertIn('<link rel="canonical" href="' + DOMAIN + "/details/" + essay["slug"] + '/">', deep)
            self.assertIn("../details/" + essay["slug"] + "/", entry)

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

    def test_3290_short_entries_are_real_pages_with_stable_canonical_and_no_fake_details(self):
        subjects = sensor_records(ROOT)
        self.assertEqual(len(subjects), 3290)
        self.assertEqual(len({s["route"] for s in subjects}), 3290)
        self.assertTrue(all("?" in s["residual_question"] for s in subjects))
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
            "vhod/buy-entry/pervyy-kontrabas-dlya-rebenka-tochnoe-polozhenie-levoy-ruki/index.html",
        ]
        # Resolve the generated sensor route from the actual registry.
        examples[-1] = sensor_records(ROOT)[0]["route"].strip("/") + "index.html"
        for relative in examples:
            html = (self.site / relative).read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            self.assertEqual(len(soup.select(".entry-range-grid a[href]")), 4)
            self.assertEqual(len(soup.select(".entry-utilities a[href]")), 4)
            self.assertEqual(len(soup.select(".contact-block")), 1)
            self.assertIsNone(soup.select_one(".brand-title"))
            self.assertIsNotNone(soup.select_one(".meta a[href]"))
            self.assertLess(html.index('class="contact-block'), html.index('class="entry-range-grid'))
            self.assertIn('href="tel:+79096945544"', html)
            self.assertNotIn("MAX", html)
        self.assertIn("../details/masterovoy-kontrabas/",
                      (self.site / examples[0]).read_text(encoding="utf-8"))
        self.assertEqual(validate(self.site, ROOT)["errors"], [])

    def test_broken_archive_marker_stops_build(self):
        (self.site / "archive/index.html").write_text("<html><head></head><body></body></html>")
        with self.assertRaises(ValueError):
            build(ROOT, self.site)


if __name__ == "__main__":
    unittest.main()
