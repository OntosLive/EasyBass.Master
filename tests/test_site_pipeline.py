"""Regression tests for EasyBassMaster's editorial pipeline and privacy boundary."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from link_audit import audit
from site_core import DOMAIN, build, inspect_records, inspect_entrances, read_json
from validate_site import validate


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
            '<!-- GENERATED_SUBJECT_INDEX --></body></html>', encoding="utf-8")

    def test_full_compilation_preserves_existing_home_and_publishes_only_ready(self):
        original = (self.site / "index.html").read_bytes()
        result = build(ROOT, self.site)
        self.assertEqual(result["generated_subjects"], 2)
        self.assertEqual(result["generated_pair_pages"], 4)
        self.assertEqual(result["hypotheses_retained"], 60)
        self.assertEqual(result["standalone_entrances"], len(inspect_entrances(ROOT)))
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
        self.assertGreaterEqual(len(inspect_entrances(ROOT)), 55)
        self.assertEqual(len(read_json(ROOT / "content/candidates.json")["candidates"]), 60)
        self.assertEqual(audit(ROOT)["errors"], [])

    def test_no_entry_fabricates_unwritten_knowledge_page(self):
        build(ROOT, self.site)
        example = inspect_entrances(ROOT)[0]
        self.assertTrue((self.site / example["slug"] / "index.html").exists())
        self.assertFalse((self.site / "details" / example["slug"] / "index.html").exists())
        self.assertIn(example["search_title"],
                      (self.site / example["slug"] / "index.html").read_text(encoding="utf-8"))

    def test_broken_archive_marker_stops_build(self):
        (self.site / "archive/index.html").write_text("<html><head></head><body></body></html>")
        with self.assertRaises(ValueError):
            build(ROOT, self.site)


if __name__ == "__main__":
    unittest.main()
