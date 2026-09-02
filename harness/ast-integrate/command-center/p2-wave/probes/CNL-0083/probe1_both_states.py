#!/usr/bin/env python3
"""Probe 1: both-states control + unsuccessful-search negative control.

FIRE on exhaustive closed-space fixture; SILENT on unsuccessful search.
A detector silent in both states measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import a10_grammar as G  # noqa: E402
import evaluate as E  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0083-executable-stopping-example-proof-of-impossibility-true.schema.json"
)
NEGATIVE_CONTROL = (
    "On the unsuccessful-search fixture (visited {0,1} of S={0,1,2,3}), "
    "proof_of_impossibility == true evaluates False because coverage 2/4 "
    "is incomplete; the stop does not fire. 'We searched and did not find it' "
    "is not recorded as 'it cannot be found'."
)


def main() -> int:
    ok, why = G.accepts_unchanged(G.UNIT_EXPRESSION)
    print(f"parse_unchanged={ok} why={why} expr={G.UNIT_EXPRESSION!r}")
    if not ok:
        print("FAILED:CNL-0083-probe1 A10 grammar rejected the spec expression")
        return 1

    examples = G.parse_all_spec_examples()
    bad = [r for r in examples if not r["accepted"]]
    print(f"spec_examples_accepted={len(examples) - len(bad)}/{len(examples)}")
    if bad:
        print(f"FAILED:CNL-0083-probe1 A10 rejected {bad}")
        return 1

    doc = E.run_named_fixtures()
    fire = doc["fixtures"]["fire"]
    silent = doc["fixtures"]["silent-search"]
    print(
        json.dumps(
            {
                "probe": "probe1-both-states",
                "expression": G.UNIT_EXPRESSION,
                "fire": {
                    "fires": fire["fires"],
                    "reason": fire["verdict"]["reason"],
                    "coverage": fire["verdict"].get("coverage"),
                    "cardinality": fire["verdict"].get("cardinality"),
                },
                "silent_search": {
                    "silent": silent["silent"],
                    "fires": silent["fires"],
                    "reason": silent["verdict"]["reason"],
                    "coverage": silent["verdict"].get("coverage"),
                    "cardinality": silent["verdict"].get("cardinality"),
                    "unseen": silent["verdict"].get("unseen"),
                },
                "both_states_pass": doc["both_states"]["pass"],
                "negative_control": NEGATIVE_CONTROL,
            },
            indent=2,
        )
    )
    print(
        f"fixture=fire fires={fire['fires']} silent={fire['silent']} "
        f"reason={fire['verdict']['reason']}"
    )
    print(
        f"fixture=silent-search fires={silent['fires']} silent={silent['silent']} "
        f"reason={silent['verdict']['reason']} "
        f"coverage={silent['verdict'].get('coverage')}/{silent['verdict'].get('cardinality')}"
    )
    print(
        "fixture=silent-unfalsifiable "
        f"silent={doc['fixtures']['silent-unfalsifiable']['silent']} "
        f"reason={doc['fixtures']['silent-unfalsifiable']['verdict']['reason']}"
    )
    print(
        "fixture=silent-circular "
        f"silent={doc['fixtures']['silent-circular']['silent']} "
        f"reason={doc['fixtures']['silent-circular']['verdict']['reason']}"
    )
    print(f"NEGATIVE_CONTROL: {NEGATIVE_CONTROL}")

    if not fire["fires"]:
        print("FAILED:CNL-0083-probe1 detector silent on exhaustive fixture")
        return 1
    if not silent["silent"]:
        print("FAILED:CNL-0083-probe1 unsuccessful search satisfied the stop")
        return 1
    if silent["verdict"]["reason"] != "unsuccessful-search-incomplete-coverage":
        print("FAILED:CNL-0083-probe1 planted-bad did not hit incomplete-coverage")
        return 1
    if not doc["extra_silents"]["unfalsifiable"]:
        print("FAILED:CNL-0083-probe1 unfalsifiable record fired")
        return 1
    if not doc["extra_silents"]["circular"]:
        print("FAILED:CNL-0083-probe1 circular record fired")
        return 1
    if fire["fires"] == silent["fires"]:
        print("FAILED:CNL-0083-probe1 detector silent in both states")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0083-probe1 design artifact missing")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0083-probe1 self-declared {art.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0083" not in text:
        print("FAILED:CNL-0083-probe1 sentinel absent")
        return 1
    if art.get("expression") != G.UNIT_EXPRESSION:
        print("FAILED:CNL-0083-probe1 artifact expression rewritten")
        return 1
    runs = art.get("fixture_runs") or {}
    if runs.get("fire", {}).get("fires") is not True:
        print("FAILED:CNL-0083-probe1 artifact did not record FIRE")
        return 1
    if runs.get("silent_search", {}).get("silent") is not True:
        print("FAILED:CNL-0083-probe1 artifact did not record SILENT unsuccessful search")
        return 1
    print("SUCCESS:CNL-0083-probe1 both-states FIRE/SILENT negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
