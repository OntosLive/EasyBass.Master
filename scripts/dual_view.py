#!/usr/bin/env python3
"""One editorial corpus, two static presentations on easybassmaster.ru."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urljoin, urlsplit, unquote

from bs4 import BeautifulSoup
from courtier_foyer import transform as render_courtier

DOMAIN = "https://easybassmaster.ru"
COUNT = 825
TEXT_META = '<meta name="robots" content="noindex,follow">'
DOOR = re.compile(r'(<a class="foyer-door-enter" href=")([^"]+)(">)')


def pages(folder):
    return sorted(folder.rglob("*.html"))


def design(ref, name):
    p = subprocess.run(["git", "show", ref + ":" + name],
                       capture_output=True, check=False)
    if p.returncode:
        raise RuntimeError("Cannot read design " + name + ": " +
                           p.stderr.decode(errors="replace")[:300])
    return p.stdout


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def take_snapshot(site, snapshot):
    if snapshot.is_relative_to(site):
        raise ValueError("Snapshot cannot be inside deployed output")
    if len(pages(site)) != COUNT:
        raise ValueError("Unexpected number of source text pages")
    if snapshot.exists():
        shutil.rmtree(snapshot)
    shutil.copytree(site, snapshot)
    source = (snapshot / "index.html").read_text(encoding="utf-8")
    if 'class="new-master"' not in source:
        raise ValueError("Canonical text homepage is missing")
    return {"phase": "snapshot", "text_pages": COUNT}


def make_visual(site, snap, ref):
    if len(pages(snap)) != COUNT:
        raise ValueError("Text snapshot incomplete")
    if (site / "text").exists():
        raise ValueError("Refusing to recursively copy an existing /text/")

    for name in ["room-golden.webp", "room-evening.webp", "row-amber.webp"]:
        write(site / "assets/photography" / name,
              design(ref, "assets/photography/" + name))
    write(site / "assets/visual/foyer.css",
          design(ref, "assets/visual/foyer.css"))
    if not (site / "assets/visual/courtier.css").is_file():
        raise ValueError("Courtier CSS not in source build")

    home = design(ref, "index.html").decode("utf-8")
    if 'class="room-home"' not in home or "Пространство, в котором можно найти свой." not in home:
        raise ValueError("Visual homepage does not match approved room")
    if '<link rel="canonical"' not in home:
        if home.count("</head>") != 1:
            raise ValueError("Room has invalid head")
        home = home.replace("</head>", '<link rel="canonical" href="' + DOMAIN + '/">\n</head>', 1)
    if home.count('class="contact-block"') != 1:
        raise ValueError("Visual home lost the real contact")
    write(site / "index.html", home.encode("utf-8"))

    tool = snap.parent / "foyer_wrap_from_design.py"
    write(tool, design(ref, "scripts/foyer_wrap.py"))
    subprocess.run([sys.executable, str(tool), "--site", str(site),
                    "--report", str(snap.parent / "foyer-report.json")],
                   check=True)
    ndoors = 0
    n0_foyers = 0
    scenes = {}
    for path in pages(site):
        if path == site / "index.html":
            continue
        html = path.read_text(encoding="utf-8")
        if len(DOOR.findall(html)) != 1:
            raise ValueError("Visual page missing exactly one doorway: " + str(path))
        transformed, mode = render_courtier(html, path.relative_to(site))
        if mode != "not-n0":
            n0_foyers += 1
            scenes[mode] = scenes.get(mode, 0) + 1
            html = transformed
        # The source door already contains a relative link to /. It never
        # needs to pass through a compulsory second /foyer/ page.
        if len(BeautifulSoup(html, "html.parser").select("a.foyer-door-enter[href]")) != 1:
            raise ValueError("Courtier lost the direct-room door: " + str(path))
        path.write_text(html, encoding="utf-8")
        ndoors += 1
    if n0_foyers != 795:
        raise ValueError(f"Expected 795 individually authored N.0 foyers, got {n0_foyers}")

    foyer = design(ref, "design/foyer/index.html").decode("utf-8")
    if "<title>Прихожая" not in foyer:
        raise ValueError("Standalone foyer does not exist")
    foyer = foyer.replace("../preview-room/", "../")
    if "preview-room" in foyer:
        raise ValueError("Temporary preview link leaked into foyer")
    write(site / "foyer/index.html", foyer.encode("utf-8"))
    write(site / "foyer/assets/photography/room-golden.webp",
          design(ref, "assets/photography/room-golden.webp"))

    def ignore_root(dir_name, files):
        if Path(dir_name).resolve() == snap.resolve():
            return {"sitemap.xml", "robots.txt"}
        return set()

    shutil.copytree(snap, site / "text", ignore=ignore_root)
    text_docs = pages(site / "text")
    if len(text_docs) != COUNT:
        raise ValueError("Text files were not all mirrored")
    for path in text_docs:
        html = path.read_text(encoding="utf-8")
        if len(re.findall(r"</head\s*>", html, flags=re.I)) != 1:
            raise ValueError("Invalid text head: " + str(path))
        html = re.sub(r"</head\s*>", TEXT_META + "\n</head>", html,
                      count=1, flags=re.I)
        # Retain relative routes within /text; rebase root-absolute links.
        html = re.sub(r'(\b(?:href|src|action)\s*=\s*["\'])/(?!/)',
                      lambda m: m.group(1) + "/text/",
                      html, flags=re.I)
        path.write_text(html, encoding="utf-8")

    shutil.rmtree(snap)
    output = {"phase": "compose", "visual_pages": COUNT, "text_pages": COUNT,
              "visual_doors": ndoors, "courtier_foyers": n0_foyers,
              "art_modes": scenes, "standalone_foyer": 1,
              "public_base": "/", "reference_base": "/text/"}
    (snap.parent / "dual-view.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return output


def check_links(site, doc):
    soup = BeautifulSoup(doc.read_text(encoding="utf-8"), "html.parser")
    relative = doc.relative_to(site).parent.as_posix()
    origin = DOMAIN + ("/" if relative == "." else "/" + relative + "/")
    for tag in soup.select("a[href],img[src],link[href],script[src]"):
        key = "src" if tag.name in ("img", "script") else "href"
        href = tag.get(key, "")
        if not href or href.startswith(("#", "tel:", "mailto:", "javascript:", "data:")):
            continue
        resolved = urlsplit(urljoin(origin, href))
        if resolved.netloc != urlsplit(DOMAIN).netloc:
            continue
        file = site / unquote(resolved.path).lstrip("/")
        if not file.suffix:
            file /= "index.html"
        if not file.is_file():
            raise ValueError("Dead local link " + str(doc.relative_to(site)) +
                             " -> " + href)


def verify(site):
    visual = [p for p in pages(site) if p.relative_to(site).parts[0] not in {"text", "foyer"}]
    text = pages(site / "text")
    if len(visual) != COUNT or len(text) != COUNT:
        raise ValueError("Visual/text inventories are not both 825")
    assert {str(p.relative_to(site)) for p in visual} == {
        str(p.relative_to(site / "text")) for p in text
    }, "Visual and text URLs differ"
    htmlv = (site / "index.html").read_text(encoding="utf-8")
    htmlt = (site / "text/index.html").read_text(encoding="utf-8")
    if 'class="room-home"' not in htmlv or 'class="new-master"' not in htmlt:
        raise ValueError("Home pages do not have distinct presentations")
    if "Прихожая" not in (site / "foyer/index.html").read_text(encoding="utf-8"):
        raise ValueError("Standalone foyer lost")
    for doc in text:
        source = doc.read_text(encoding="utf-8")
        if source.count(TEXT_META) != 1:
            raise ValueError("Technical text copy can be indexed: " + str(doc))
    verified_foyers = 0
    for doc in visual:
        if doc == site / "index.html":
            continue
        d = BeautifulSoup(doc.read_text(encoding="utf-8"), "html.parser")
        a = d.select("a.foyer-door-enter[href]")
        expected_home = "../" * (len(doc.relative_to(site).parts) - 1)
        if len(a) != 1 or a[0]["href"] != expected_home:
            raise ValueError("Visual door must directly open the room: " + str(doc))
        if "courtier-page" in (d.body.get("class", []) if d.body else []):
            verified_foyers += 1
            source = site / "text" / doc.relative_to(site)
            reference = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
            if (len(d.select("h1")) != 1 or
                not d.select_one(".courtier-stage .courtier-portal") or
                d.select_one(".courtier-portal")["href"] != expected_home or
                len(d.select(".courtier-choices .contact-block")) != 1 or
                len(d.select(".entry-range-grid a")) != 4 or
                len(d.select(".entry-utilities a")) != 4 or
                len(d.select(".master-footer a")) != 2):
                raise ValueError("Incomplete Courtier scene: " + str(doc))
            for selector in (".issue.master-lead h1", ".entry-modulation", ".contact-phone"):
                lhs = d.select_one(selector)
                rhs = reference.select_one(selector)
                if (lhs is None or rhs is None or
                    lhs.get_text(" ", strip=True) != rhs.get_text(" ", strip=True)):
                    raise ValueError("Authored text and visual foyer disagree: " +
                                     str(doc) + " " + selector)
            if any("/foyer/" in link.get("href", "") for link in d.select("a[href]")):
                raise ValueError("N.0 still sends visitors through a third foyer: " + str(doc))
    if verified_foyers != 795:
        raise ValueError(f"Courtier page inventory differs: {verified_foyers} vs 795")
    for doc in visual + text + [site / "foyer/index.html"]:
        check_links(site, doc)
    sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
    if "/text/" in sitemap or "/foyer/" in sitemap:
        raise ValueError("Duplicate technical pages in sitemap")
    return {"phase": "verify", "visual": len(visual), "text": len(text),
            "courtier_foyers": verified_foyers, "noindex_copies": len(text),
            "standalone_foyer": True, "errors": 0}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=["snapshot", "compose", "verify"])
    p.add_argument("--site", type=Path, default=Path("_site"))
    p.add_argument("--snapshot", type=Path, default=Path("_audit/text-snapshot"))
    p.add_argument("--design-ref", default="FETCH_HEAD")
    opts = p.parse_args()
    site = opts.site.resolve()
    snap = opts.snapshot.resolve()
    if opts.phase == "snapshot":
        r = take_snapshot(site, snap)
    elif opts.phase == "compose":
        r = make_visual(site, snap, opts.design_ref)
    else:
        r = verify(site)
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
