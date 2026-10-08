#!/usr/bin/env python3
"""Validate authored subjects before Jekyll and before any publication."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from site_core import ROOT, inspect_records, inspect_entrances, inspect_knowledge, norm, read_json


def audit(root: Path = ROOT) -> dict:
    errors = []
    pages = []
    try:
        pages = inspect_records(root)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    entrances = []
    try:
        entrances = inspect_entrances(root, pages)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    knowledge = []
    try:
        knowledge = inspect_knowledge(root, entrances, pages)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    candidates = read_json(root / "content/candidates.json").get("candidates", [])
    hypotheses = [norm(x["query_hypothesis"]) for x in candidates]
    for name, count in Counter(hypotheses).items():
        if count > 1:
            errors.append(f"Repeated unreviewed query: {name}")
    for route in ("collection", "workshop", "meeting", "archive"):
        if not (root / route / "index.html").exists():
            errors.append(f"Missing preserved institutional route: {route}")
    archive = (root / "archive/index.html").read_text(encoding="utf-8")
    if archive.count("<!-- GENERATED_SUBJECT_INDEX -->") != 1:
        errors.append("Archive must have exactly one generated index marker")
    if "site.pages" not in archive:
        errors.append("Historical Jekyll issue collection lost from archive")
    if "Пространство, в котором можно найти свой." not in (root / "index.html").read_text(encoding="utf-8"):
        errors.append("Approved homepage text lost")
    for p in pages:
        if not (root / p["parent"] / "index.html").exists():
            errors.append(f'{p["slug"]}: missing parent page')
    return {"ready_subjects": len(pages), "ready_entrances": len(entrances),
            "ready_knowledge": len(knowledge),
            "hypotheses": len(candidates),
            "hypothesis_repetitions": len(hypotheses) - len(set(hypotheses)),
            "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=Path("_audit/links.json"))
    args = parser.parse_args()
    result = audit(args.root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
