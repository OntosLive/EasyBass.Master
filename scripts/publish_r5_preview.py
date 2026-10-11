#!/usr/bin/env python3
"""Expose a pinned, pre-built R5 PR artifact under /preview/r5/.

Production routes are not rebuilt or modified. This operation intentionally
runs only AFTER normal site compilation, verification and browser checks.
Temporary public preview pages are noindex and absent from the sitemap.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

PINNED_R5 = "3a9f71f49bdd999093311edf7284df8c919153cc"
PREVIEW_PATH = Path("preview/r5")
ROBOTS = '<meta name="robots" content="noindex,nofollow,noarchive">'
HEAD = re.compile(r"<head\b[^>]*>", re.I)
OLD_ROBOTS = re.compile(r'<meta\b(?=[^>]*\bname\s*=\s*[\'\"]robots[\'\"])[^>]*>\s*', re.I)
CANONICAL = re.compile(r'<link\b(?=[^>]*\brel\s*=\s*[\'\"]canonical[\'\"])[^>]*>\s*', re.I)


def publish(source: Path, site: Path) -> dict:
    source = source.resolve()
    site = site.resolve()
    assert source != site and not source.is_relative_to(site)
    expected = ("index.html", "kupit-masterovoy-kontrabas-v-moskve/index.html",
                "remont-grifa-kontrabasa/index.html", "text/index.html",
                "assets/photography/room-golden.webp")
    missing = [name for name in expected if not (source / name).is_file()]
    if missing:
        raise ValueError("Incomplete R5 CI artifact: " + ", ".join(missing))
    if not (site / "index.html").is_file():
        raise ValueError("The production site must be built first")
    output = site / PREVIEW_PATH
    if output.exists():
        raise ValueError("Preview target unexpectedly exists: " + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, output)
    for name in ("sitemap.xml", "robots.txt", "CNAME", ".nojekyll"):
        (output / name).unlink(missing_ok=True)
    rendered = 0
    for page in output.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        html = OLD_ROBOTS.sub("", html)
        html = CANONICAL.sub("", html)
        html, matches = HEAD.subn(lambda m: m.group() + "\n" + ROBOTS, html, count=1)
        if matches != 1:
            raise ValueError("R5 HTML has no unique head: " + str(page))
        page.write_text(html, encoding="utf-8")
        rendered += 1
    if rendered < 1650:
        raise ValueError(f"R5 preview page count unexpectedly low: {rendered}")
    for name in expected:
        if not (output / name).is_file():
            raise ValueError("R5 preview lost a required asset: " + name)
    manifest = {
        "path": "/preview/r5/",
        "artifact_commit": PINNED_R5,
        "html_pages": rendered,
        "robots": "noindex,nofollow,noarchive",
        "sitemap_included": False,
        "original_site_routes_unchanged": True,
        "review_routes": [
            "/preview/r5/",
            "/preview/r5/kupit-masterovoy-kontrabas-v-moskve/",
            "/preview/r5/remont-grifa-kontrabasa/",
            "/preview/r5/kontrabas-1-2-ili-3-4/",
        ],
    }
    (output / "preview-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--site", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(publish(args.source, args.site), ensure_ascii=False))


if __name__ == "__main__":
    main()
