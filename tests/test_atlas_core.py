"""Regression tests for the research atlas and its publication boundary."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atlas_core import audit

class AtlasContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit(ROOT)
        cls.atlas = json.loads((ROOT / "content/atlas/atlas.json").read_text(encoding="utf-8"))

    def test_full_hierarchy_and_research_counts(self):
        self.assertEqual(self.report["errors"], [])
        self.assertEqual(self.report["all_nodes"], 3987)
        self.assertEqual(self.report["all_research_leaf_nodes"], 3529)
        self.assertEqual(self.report["research_leaf_hypotheses"], 3290)
        self.assertEqual(self.report["verified_model_identities"], 45)

    def test_no_research_hypothesis_is_public_page(self):
        for node in self.atlas["nodes"]:
            if node["type"] in {"hypothesis", "model_research_question", "historical_object"}:
                self.assertIsNone(node.get("url"))
                self.assertFalse(node.get("publishable", False))

    def test_source_models_do_not_assert_stock(self):
        source = json.loads((ROOT / "content/model-registry.json").read_text(encoding="utf-8"))
        self.assertEqual(len(source["models"]), 45)
        for model in source["models"]:
            self.assertEqual(model["availability"], "unverified")
            self.assertIsNone(model["price"])
            self.assertIsNone(model["stock"])
            self.assertTrue(model["source"].startswith("https://"))

    def test_public_coverage_mapping_does_not_pretend_full_editorial_pass(self):
        self.assertEqual(self.report["mapped_published_entrances"], 200)
        self.assertEqual(self.report["mapped_published_pairs"], 2)

if __name__ == "__main__":
    unittest.main()
