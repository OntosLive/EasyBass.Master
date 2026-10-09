#!/usr/bin/env python3
"""Report each published N.0 that still needs an individually authored GPT-6 bridge.

Every N.0 must have individually authored copy. The --complete release gate
requires zero missing entries; --strict additionally requires all entries to
pass the editorial review state before considering the corpus final.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from site_core import ROOT, inspect_records, inspect_entrances
from sensor_n0 import records as authored_entries

SELF_PROMOTION = re.compile(
    r"наш кон[её]к|мы лучшие|наши эксперты|уникальные специалисты|"
    r"возможност[ьи] доработки становятс[яь] ясн|"
    r"свяжитесь с нами|получите консультацию",
    re.IGNORECASE,
)


def metadata(root: Path) -> dict[str, dict]:
    """Read declared model/editing provenance, not inferred model authorship."""
    out = {}
    for path in sorted((root / "content/entrances-rewrite").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for family in data["families"]:
            for entry in family["entries"]:
                route = f"/vhod/{family['id']}/{entry['slug']}/"
                out[route] = entry
    return out


def audit(root: Path = ROOT) -> dict:
    raw = metadata(root)
    items = []
    for p in inspect_records(root):
        items.append(("paired", f"/{p['entry_slug']}/", p))
    for p in inspect_entrances(root):
        items.append(("standalone", f"/{p['slug']}/", p))
    for p in authored_entries(root):
        items.append(("authored", p["route"], raw.get(p["route"], {})))

    issues = []
    missing = []
    drafted = []
    reviewed = []
    seen_text = {}
    for kind, route, record in items:
        bridge = record.get("bridge", "").strip()
        if not bridge:
            missing.append({"route": route, "kind": kind, "title": record.get("search_title", record.get("title", ""))})
            continue
        model = record.get("bridge_model", "")
        state = record.get("bridge_status", "")
        if model != "gpt-6":
            issues.append({"route": route, "issue": "bridge missing declared GPT-6 editorial provenance"})
        if state not in {"gpt6_draft", "gpt6_reviewed"}:
            issues.append({"route": route, "issue": "bridge lacks editing-state provenance"})
        if len(bridge) > 160 or len(bridge) < 40 or "?" in bridge:
            issues.append({"route": route, "issue": "bridge breaks short-page form"})
        if SELF_PROMOTION.search(bridge):
            issues.append({"route": route, "issue": "boastful CTA or deferred sales copy"})
        key = " ".join(bridge.casefold().replace("ё", "е").split())
        if key in seen_text:
            issues.append({"route": route, "issue": f"identical bridge reused from {seen_text[key]}"})
        seen_text[key] = route
        (reviewed if state == "gpt6_reviewed" else drafted).append(route)

    return {
        "published_n0": len(items),
        "individual_gpt6_drafts": len(drafted),
        "individual_gpt6_reviewed": len(reviewed),
        "editorial_backlog": len(missing),
        "missing_sample": missing[:30],
        "critical_errors": issues,
        "complete": len(missing) == 0 and len(issues) == 0,
        "strict_ready": len(missing) == 0 and len(drafted) == 0 and len(issues) == 0,
        "note": "Model labels are editorial declarations, not proof of an underlying execution engine. Human/LLM substantive review remains necessary.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("_audit/modulations.json"))
    parser.add_argument("--strict", action="store_true", help="Require all published N.0 to have reviewed GPT-6 modulation")
    parser.add_argument("--complete", action="store_true", help="Require an individually written bridge on every published N.0")
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("missing_sample", "critical_errors", "note")}, ensure_ascii=False))
    if result["critical_errors"] or (args.complete and not result["complete"]) or (args.strict and not result["strict_ready"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
