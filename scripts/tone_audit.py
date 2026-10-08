#!/usr/bin/env python3
"""Editorial tone diagnostic: no imperative lecture in purchase/sale entrance texts.

Other historical editorial entries are reported for later human revision, not
silently rewritten by a regular-expression machine.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"(?<![А-Яа-яЁё])(нужно|должно|должен|должна|следует|обязательно|нельзя|надо|важно|стоит|рекомендуется|необходимо)(?![А-Яа-яЁё])", re.I)
FOCUS = {
    "Покупка и подбор",
    "Продажа владельцем и оценка",
    "Покупка: обстоятельства и выбор",
    "Продажа: история и выбор маршрута",
}

def report(root: Path = ROOT) -> dict:
    flags, count = [], 0
    for path in sorted((root / "content/entrances").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for entry in doc["entries"]:
            count += 1
            written = " ".join((entry["lead"], entry["body"], entry["open_question"]))
            matches = []
            for m in PATTERN.finditer(written):
                word = m.group(1).lower()
                # "задача стоит перед вами" and "сколько стоит" are not imperatives.
                if word == "стоит" and (
                    written[m.end():].lstrip().lower().startswith("перед ")
                    or written[:m.start()].rstrip().lower().endswith("сколько")
                ):
                    continue
                matches.append(word)
            if matches:
                flags.append({"path": path.relative_to(root).as_posix(),
                              "title": entry["search_title"], "terms": matches,
                              "critical": doc["group"] in FOCUS})
    return {"pages": count, "pages_with_directive_terms": len(flags),
            "focus_errors": [x for x in flags if x["critical"]],
            "old_corpus_review_queue": [x for x in flags if not x["critical"]]}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("_audit/tone.json"))
    a = parser.parse_args()
    r = report(a.root)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in r.items()}, ensure_ascii=False))
    if r["focus_errors"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
