#!/usr/bin/env python3
"""Probe 1: both-states UNATTRIBUTED control + multi-cause DAG.

Green: protocol keeps F-USER-PROMPTS-ABSENT UNATTRIBUTED and F-G1-FAIL has
two or more parents. Red: nearest-parent mutant attaches the unknown-cause
finding. A method that always attaches or always refuses is not credited.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = (
    E.REPO
    / "command-center/research/deep-research-design"
    / "RES-0174-root-cause-hierarchy-extraction.json"
)
SENTINEL = "SUCCESS:RES-0174"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0174-probe1 {msg}")
    return 1


def main() -> int:
    proto = E.extract(mode="protocol")
    mutant = E.extract(mode="nearest-parent")
    print(
        json.dumps(
            {
                "protocol_unattributed": proto["metrics"]["unattributed_ids"],
                "protocol_multi_parent": proto["metrics"]["multi_parent_ids"],
                "protocol_max_depth": proto["metrics"]["max_depth"],
                "protocol_errors": E.protocol_errors(proto),
                "mutant_attached_unknown": any(
                    e.get("child") == "F-USER-PROMPTS-ABSENT" for e in mutant["edges"]
                ),
                "mutant_errors": E.protocol_errors(mutant),
            },
            sort_keys=True,
        )
    )

    errs = E.protocol_errors(proto)
    if errs:
        return fail("protocol " + ";".join(errs))

    unknown = next(
        n for n in proto["nodes"] if n["id"] == "F-USER-PROMPTS-ABSENT"
    )
    if unknown.get("role") != "UNATTRIBUTED":
        return fail("unknown-cause role is " + str(unknown.get("role")))
    if any(e.get("child") == "F-USER-PROMPTS-ABSENT" for e in proto["edges"]):
        return fail("protocol attached unknown-cause to a parent")

    g1_parents = [e["parent"] for e in proto["edges"] if e["child"] == "F-G1-FAIL"]
    if len(set(g1_parents)) < 2:
        return fail("F-G1-FAIL parents=" + ",".join(g1_parents))

    mutant_attached = any(
        e.get("child") == "F-USER-PROMPTS-ABSENT" for e in mutant["edges"]
    )
    if not mutant_attached:
        return fail("nearest-parent mutant did not attach (both-states silent)")
    if "unknown-cause-has-parent" not in E.protocol_errors(mutant):
        return fail("nearest-parent mutant not flagged as unknown-cause-has-parent")

    if proto["metrics"]["max_depth"] < 2:
        return fail("protocol max_depth < 2")

    if not ART.is_file():
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel missing from artifact")

    print(
        "unattributed_held=True nearest_parent_fires=True "
        f"g1_parents={len(set(g1_parents))} depth={proto['metrics']['max_depth']}"
    )
    print("SUCCESS:RES-0174-probe1 both-states UNATTRIBUTED vs nearest-parent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
