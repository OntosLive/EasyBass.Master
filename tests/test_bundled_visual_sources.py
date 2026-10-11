"""The approved room is a source artifact of THIS repository, not a floating branch."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dual_view import design


# Exact git blob hashes: byte-identical to the last approved R3 source snapshot.
# A real change of art or composition must deliberately revise this list.
CANONICAL_BLOBS = {
    "design/visual-home/index.html": "4f5af4002043145d4125f2864f4862314af9b4fd",
    "design/foyer/index.html": "82aaa164530c4a2b92976b661704c3c087d7490f",
    "assets/photography/room-golden.webp": "0e7b960be06b3e9b27b1d83e3a591dda0c627d07",
    "assets/photography/room-evening.webp": "f21eb4881a4f691f6f80e7d5b2d36d792efdf9ba",
    "assets/photography/row-amber.webp": "a6bc112d0668eda2f64b190735457035ec7b2b2f",
}


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


class BundledVisualSources(unittest.TestCase):
    def test_canonical_room_and_art_are_byte_identical(self):
        for filename, expected_sha in CANONICAL_BLOBS.items():
            with self.subTest(path=filename):
                actual = design(filename)
                self.assertEqual(git_blob_sha(actual), expected_sha)
                self.assertLess(len(actual), 300_000)

    def test_approved_room_layout_and_verified_contact_survive(self):
        html = design("design/visual-home/index.html").decode("utf-8")
        doc = BeautifulSoup(html, "html.parser")
        self.assertEqual(len(doc.select("h1")), 1)
        self.assertIn("Пространство, в котором можно найти свой.",
                      doc.h1.get_text(" ", strip=True))
        self.assertEqual(len(doc.select("#heroImage")), 1)
        self.assertEqual(len(doc.select("#modeSwitch")), 1)
        self.assertEqual(len(doc.select("#galleryMain")), 1)
        self.assertEqual(len(doc.select(".contact-block")), 1)
        self.assertEqual(len(doc.select('a[href="tel:+79096945544"]')), 1)
        self.assertEqual(len(doc.select(".max-contact-pending")), 1)
        self.assertIn("творчество", doc.get_text(" ", strip=True))
        self.assertIn("--content-width", doc.head.style.get_text())
        self.assertIn("assets/photography/room-golden.webp", html)

    def test_compile_needs_no_nonlocal_git_reference(self):
        workflow = (ROOT / ".github/workflows/jekyll-gh-pages.yml").read_text(encoding="utf-8")
        source = (ROOT / "scripts/dual_view.py").read_text(encoding="utf-8")
        self.assertNotIn("git fetch", workflow)
        self.assertNotIn("FETCH_HEAD", workflow)
        self.assertNotIn('["git", "show"', source)
        self.assertIn("design/visual-home/index.html", source)
        self.assertIn("python scripts/dual_view.py compose", workflow)
        config = (ROOT / "_config.yml").read_text(encoding="utf-8")
        self.assertIn("  - design\n", config)

    def test_cannot_read_outside_checkout(self):
        with self.assertRaises(ValueError):
            design("../../etc/passwd")
        with self.assertRaises(ValueError):
            design("design/there-is-no-such-scene.html")


if __name__ == "__main__":
    unittest.main()
