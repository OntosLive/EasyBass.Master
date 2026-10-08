#!/usr/bin/env python3
"""Audit the full EasyBassMaster research atlas without publishing a single hypothesis.

The research map is not a list of search keywords and does not create URLs.
The first stage compiles possible human situations; the editorial second pass
alone can turn a topic into a public page. This is the ONTOS.RENT distinction.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit(root: Path = ROOT) -> dict:
    atlas = read(root / "content/atlas/atlas.json")
    seeds = read(root / "content/atlas/family-seeds.json")
    models = read(root / "content/model-registry.json")
    coverage = read(root / "content/atlas/coverage.json")
    errors = []

    nodes = atlas["nodes"]
    by_id = {n["id"]: n for n in nodes}
    if len(nodes) != len(by_id):
        errors.append("duplicate atlas node IDs")
    rootids = {"R-" + x["id"] for x in seeds["categories"]}
    if rootids != {x["id"] for x in nodes if x["type"] == "root"}:
        errors.append("root mismatch")
    for node in nodes:
        parent = node.get("parent")
        if parent and parent not in by_id:
            errors.append(f'{node["id"]}: missing parent {parent}')
        if parent and parent in by_id and by_id[parent]["depth"] + 1 != node["depth"]:
            errors.append(f'{node["id"]}: invalid depth')
        if node["type"] in {"hypothesis", "model_research_question", "historical_object"}:
            if node.get("url") or node.get("planned_url"):
                errors.append(f'{node["id"]}: research must not pretend to have published URL')

    family_count = 0
    scene_count = 0
    research_count = 0
    for family in seeds["families"]:
        family_count += 1
        f_id = "F-" + family["id"]
        if f_id not in by_id:
            errors.append(f"family absent: {f_id}")
        for i, scene in enumerate(family["scenes"], start=1):
            scene_count += 1
            sid = f'S-{family["id"]}-{i}'
            if by_id.get(sid, {}).get("title") != scene:
                errors.append(f"scene mismatch: {sid}")
            for j, question in enumerate(family["questions"], start=1):
                research_count += 1
                hid = f'H-{family["id"]}-{i}-{j}'
                n = by_id.get(hid)
                if not n or n.get("question") != question or n.get("parent") != sid:
                    errors.append(f"hypothesis mismatch: {hid}")
    model_ids = {"M-" + m["id"] for m in models["models"]}
    if model_ids != {n["id"] for n in nodes if n["type"] == "model_identity"}:
        errors.append("model catalog and atlas differ")
    for m in models["models"]:
        if not str(m.get("source", "")).startswith("https://"):
            errors.append(f'{m["id"]}: missing official model source')
        if m.get("availability") != "unverified" or m.get("stock") is not None:
            errors.append(f'{m["id"]}: cannot claim live stock')
    for m in models["models"]:
        for j in range(1, 6):
            if f'MQ-{m["id"]}-{j}' not in by_id:
                errors.append(f'MQ-{m["id"]}-{j}: missing model question')

    existing = {}
    for file in sorted((root / "content/entrances").glob("*.json")):
        for entry in read(file)["entries"]:
            if entry["slug"] in existing:
                errors.append(f"duplicate published slug: {entry['slug']}")
            existing[entry["slug"]] = entry
    listed = {e["slug"] for e in coverage["published_entrances"]}
    if listed != set(existing):
        errors.append("published standalone routes differ from existing source")
    paired = read(root / "content/topics.json")["pages"]
    if {p["entry_slug"] for p in paired} != {e["slug"] for e in coverage["published_pairs"]}:
        errors.append("published pair routes differ from existing source")
    if listed & {p["entry_slug"] for p in paired}:
        errors.append("standalone URL collides with published pair")
    if any(item.get("atlas_leaf_id") for item in coverage["published_entrances"]):
        errors.append("unverified coverage link masquerades as confirmed research review")

    expected = {
        "roots": len(seeds["categories"]),
        "scenes": scene_count,
        "hypotheses": research_count,
        "verified_model_identities": len(models["models"]),
        "model_questions": len(models["models"]) * 5,
        "historic_objects": 14,
        "total_nodes": len(nodes)
    }
    for key, count in expected.items():
        if atlas["totals"].get(key) != count:
            errors.append(f"atlas totals {key}: expected {count}")
    if atlas["totals"].get("total_research_leaves") != research_count + len(models["models"]) * 5 + 14:
        errors.append("research leaf count mismatch")
    report = {
        "date": "2026-10-09",
        "roots": expected["roots"],
        "families": family_count,
        "scenes": scene_count,
        "research_leaf_hypotheses": research_count,
        "verified_model_identities": expected["verified_model_identities"],
        "model_questions": expected["model_questions"],
        "archived_instrument_identifiers": 14,
        "all_nodes": len(nodes),
        "all_research_leaf_nodes": atlas["totals"]["total_research_leaves"],
        "mapped_published_entrances": len(existing),
        "mapped_published_pairs": len(paired),
        "source_catalog_is_not_stock": True,
        "errors": errors[:100]
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("_audit/atlas.json"))
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
