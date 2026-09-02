#!/usr/bin/env python3
"""Named probe 2: undocumented public removal is a defect even if unused in-repo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/confirmation/CNF-0056-api-surface-diff.json"

sys.path.insert(0, str(HERE))
import changelog as CL  # noqa: E402
import schema_offline as SO  # noqa: E402
import surface as SF  # noqa: E402


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0056-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errors = SO.validate_doc(doc)
    if errors:
        print("FAILED:CNF-0056-probe2 schema-invalid")
        for line in errors[:20]:
            print(" ", line)
        return 1
    payload = SO.artifact_payload(doc)

    before = SF.enumerate_surface(HERE / "fixtures" / "before", "cnf0056_probe2_before")
    after = SF.enumerate_surface(HERE / "fixtures" / "after", "cnf0056_probe2_after")
    text = (HERE / "fixtures" / "CHANGELOG.md").read_text(encoding="utf-8")
    recomputed = CL.classify_delta(before, after, text)

    # Independent recompute happens BEFORE trusting the artifact conclusion.
    undoc = [u["name"] for u in recomputed["undocumented_removals"]]
    docd = [u["name"] for u in recomputed["documented_removals"]]
    renamed = [(r["from"], r["to"]) for r in recomputed["renamed"]]

    if not any("PublicBeta" in n for n in undoc):
        print("FAILED:CNF-0056-probe2 PublicBeta not an undocumented removal")
        print(json.dumps(recomputed, indent=2))
        return 1
    if any("PublicBeta" in n for n in docd):
        print("FAILED:CNF-0056-probe2 PublicBeta wrongly marked documented")
        return 1
    if not any("legacy" in n for n in docd):
        print("FAILED:CNF-0056-probe2 documented CLI removal missing")
        print("documented", docd)
        return 1
    if not any("legacy_name" in a and "current_name" in b for a, b in renamed):
        print("FAILED:CNF-0056-probe2 documented rename missing")
        print("renamed", renamed)
        return 1

    consumer = (HERE / "fixtures" / "unused_in_repo_consumer.py").read_text(
        encoding="utf-8"
    )
    if "PublicBeta" in consumer:
        print("FAILED:CNF-0056-probe2 consumer fixture is contaminated")
        return 1
    if "PublicAlpha" not in consumer:
        print("FAILED:CNF-0056-probe2 consumer fixture does not import PublicAlpha")
        return 1

    art_undoc = [
        u["name"]
        for u in (payload.get("delta") or {}).get("undocumented_removals") or []
    ]
    if sorted(art_undoc) != sorted(undoc):
        print("FAILED:CNF-0056-probe2 artifact undocumented list disagrees")
        print("recomputed", undoc)
        print("artifact  ", art_undoc)
        return 1
    if not payload.get("unused_in_repo_control", {}).get(
        "PublicBeta_still_undocumented_removal"
    ):
        print("FAILED:CNF-0056-probe2 unused-in-repo control missing")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-undocumented-removal",
                "unit_id": "CNF-0056",
                "undocumented_removals": undoc,
                "documented_removals": docd,
                "renamed": renamed,
                "unused_in_repo_does_not_excuse_removal": True,
                "pass": True,
            },
            indent=2,
        )
    )
    print(
        "SUCCESS:CNF-0056-probe2 undocumented PublicBeta is a defect; "
        "in-repo non-use does not excuse it"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
