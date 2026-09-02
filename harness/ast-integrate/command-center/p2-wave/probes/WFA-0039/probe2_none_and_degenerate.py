#!/usr/bin/env python3
"""Probe 2: NONE is a finding, not a blank; degenerate always-true/false flagged.

Negative control: planted tautology and contradiction must be DEGENERATE.
Both-states: a non-degenerate extracted rule is NOT flagged degenerate.
Inexpressible runtime-over-prior-rounds is UNKNOWN-NEEDS-PROBE, never approximated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract import build_records  # noqa: E402
from grammar import differential  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0039-extract-stopping-rules.json"


def main() -> int:
    bundle = build_records()
    by_id = {r["id"]: r for r in bundle["records"]}

    none = by_id.get("planted-no-stop")
    if none is None or none["status"] != "NONE":
        print(f"FAILED:WFA-0039-probe2 NONE not recorded {none}")
        return 1
    if none.get("source_prose") not in (None, ""):
        print("FAILED:WFA-0039-probe2 NONE must not invent a predicate")
        return 1
    if none.get("normalized") is not None:
        print("FAILED:WFA-0039-probe2 NONE must not carry a tree")
        return 1

    taut = by_id.get("planted-degenerate-tautology")
    contra = by_id.get("planted-degenerate-contradiction")
    if taut is None or taut["status"] != "DEGENERATE" or taut.get("degenerate") != "always-true":
        print(f"FAILED:WFA-0039-probe2 tautology {taut}")
        return 1
    if (
        contra is None
        or contra["status"] != "DEGENERATE"
        or contra.get("degenerate") != "always-false"
    ):
        print(f"FAILED:WFA-0039-probe2 contradiction {contra}")
        return 1

    runtime = by_id.get("planted-runtime-over-prior-rounds")
    if runtime is None or runtime["status"] != "UNKNOWN-NEEDS-PROBE":
        print(f"FAILED:WFA-0039-probe2 inexpressible approximated {runtime}")
        return 1
    if runtime.get("normalized") is not None:
        print("FAILED:WFA-0039-probe2 inexpressible must not be normalised")
        return 1

    # Both-states: a real spec-shaped rule is not degenerate.
    live = differential("unique_ideas >= 100 AND completeness_score >= 0.90")
    if live["degenerate"] is not None or live["disagreements"] != 0:
        print(f"FAILED:WFA-0039-probe2 good rule flagged {live}")
        return 1
    if live["n_true"] == 0 or live["n_false"] == 0:
        print(f"FAILED:WFA-0039-probe2 good rule not both-states {live}")
        return 1

    in_tree = [
        r
        for r in bundle["records"]
        if r.get("kind") == "in-tree" and r["status"] == "EXTRACTED"
    ]
    if not in_tree:
        print("FAILED:WFA-0039-probe2 no in-tree EXTRACTED stopping object")
        return 1

    if not OUT.is_file():
        print("FAILED:WFA-0039-probe2 artifact missing")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    art = {r["id"]: r for r in doc.get("records") or []}
    for key, status in (
        ("planted-no-stop", "NONE"),
        ("planted-degenerate-tautology", "DEGENERATE"),
        ("planted-degenerate-contradiction", "DEGENERATE"),
        ("planted-runtime-over-prior-rounds", "UNKNOWN-NEEDS-PROBE"),
    ):
        if art.get(key, {}).get("status") != status:
            print(f"FAILED:WFA-0039-probe2 artifact {key} {art.get(key)}")
            return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0039-probe2 self-declared blocked")
        return 1

    print(
        f"none=NONE tautology=DEGENERATE:{taut['degenerate']} "
        f"contradiction=DEGENERATE:{contra['degenerate']} "
        f"runtime=UNKNOWN-NEEDS-PROBE in_tree_extracted={len(in_tree)} "
        f"good_rule_degenerate={live['degenerate']}"
    )
    print(
        "NEGATIVE-CONTROL: on planted tautology (unique_ideas >= 0) OR "
        "(unique_ideas < 0) status=DEGENERATE always-true; on planted NONE "
        "status=NONE with no invented tree; on planted runtime-over-prior-rounds "
        "status=UNKNOWN-NEEDS-PROBE."
    )
    print("SUCCESS:WFA-0039-probe2 none-and-degenerate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
