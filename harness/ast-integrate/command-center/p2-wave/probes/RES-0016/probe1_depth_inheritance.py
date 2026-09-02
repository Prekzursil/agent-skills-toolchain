#!/usr/bin/env python3
"""Probe 1: nest until refusal + two contrasting inheritance spawns.

Re-runs the runtime (not the artifact's self-report) and then checks the
emitted research file still holds the same numbers and verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from docs_extract import extract as extract_docs  # noqa: E402
from measure import (  # noqa: E402
    env_overrides,
    inheritance_contrasting_spawns,
    nest_until_refusal,
)
from payload import measurements_of  # noqa: E402
from runtime import DEFAULT_DEPTH, DEPTH_WITHHOLD_REFUSAL  # noqa: E402

ART = REPO / "command-center/research/RES-0016.json"
SENTINEL = (
    "SUCCESS:RES-0016 in the receipt AND a measured depth limit, an inheritance "
    "verdict backed by two contrasting spawns, and a twice-reproduced concurrency ceiling"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0016-probe1 {msg}")
    return 1


def main() -> int:
    docs = extract_docs()
    depth = nest_until_refusal()
    inh = inheritance_contrasting_spawns()
    env = env_overrides()
    print(
        json.dumps(
            {
                "probe": "probe1-depth-inheritance",
                "docs_depth": docs["depth_default"],
                "last_successful_depth": depth["last_successful_depth"],
                "refusal": depth["refusal"],
                "two_contrasting_spawns": inh["two_contrasting_spawns"],
                "estate_finding_refuted": inh["estate_finding_refuted"],
                "env_depth_1_last_success": env["depth_set_1_last_success"],
            },
            sort_keys=True,
        )
    )
    if docs["depth_default"] != DEFAULT_DEPTH:
        return fail("docs extract depth != 3")
    if depth["last_successful_depth"] != docs["depth_default"]:
        return fail("runtime depth != docs extract")
    if depth["refusal"]["message"] != DEPTH_WITHHOLD_REFUSAL:
        return fail("depth refusal message")
    if not depth["agent_tool_withheld_on_last_success"]:
        return fail("Agent tool still present at depth limit")
    if not inh["two_contrasting_spawns"]:
        return fail("parent-default WITH vs WITHOUT did not contrast")
    if inh["pair_parent_default"]["without_explicit"] != "default":
        return fail("unset did not inherit default")
    if inh["pair_parent_default"]["with_explicit_plan"] != "plan":
        return fail("explicit plan did not apply")
    if not inh["pair_parent_bypassPermissions"]["sticky_blocks_override"]:
        return fail("sticky parent did not block override")
    if not inh["estate_finding_refuted"]:
        return fail("estate no-inherit claim was not refuted by bypass parent")
    if env["depth_set_1_last_success"] != 1:
        return fail("env depth=1 did not cap at 1")
    if not env["depth_set_1_refuses_nested"]:
        return fail("env depth=1 nested spawn did not refuse")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("catalog completion sentinel absent")
    meas = measurements_of(doc)
    if int(meas.get("depth_limit") or -1) != depth["last_successful_depth"]:
        return fail("artifact depth_limit drift")
    if (meas.get("depth_refusal") or {}).get("message") != depth["refusal"]["message"]:
        return fail("artifact depth_refusal drift")
    art_inh = meas.get("inheritance") or {}
    if art_inh.get("two_contrasting_spawns") is not True:
        return fail("artifact missing contrasting spawns")
    if art_inh.get("estate_finding_refuted") is not True:
        return fail("artifact estate verdict drift")
    print(
        "SUCCESS:RES-0016-probe1 depth="
        f"{depth['last_successful_depth']} inheritance_contrast=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
