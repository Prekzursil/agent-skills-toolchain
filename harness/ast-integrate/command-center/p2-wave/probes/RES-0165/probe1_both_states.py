#!/usr/bin/env python3
"""Probe 1: same-prompt noise floor, both-states, landscape vs targeted flatten."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402
from contract import OUT_REL, SENTINEL  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0165-probe1 {msg}")
    return 1


def main() -> int:
    live = M.run()
    floor = live["noise_floor"]
    both = live["both_states"]
    flat = live["flatten"]

    print(both["planted_bad"]["verbatim"])
    print(both["known_good"]["verbatim"])
    print(both["naive_counter"]["verbatim"])
    print(
        json.dumps(
            {
                "clone_clustered_added": floor["clustered_added"],
                "clone_naive_added": floor["naive_added"],
                "landscape_flatten_n": flat["landscape_n"],
                "targeted_flatten_n": flat["targeted_n"],
                "targeted_earlier": flat["targeted_flattens_earlier"],
                "discriminates": both["discriminates"],
                "land_cov": flat["landscape_contradiction_coverage_at_flatten"],
                "targ_cov": flat["targeted_contradiction_coverage_at_flatten"],
            },
            sort_keys=True,
        )
    )

    if int(floor["clustered_added"]) != 0:
        return fail(f"clone clustered added {floor['clustered_added']} != 0")
    if int(floor["naive_added"]) <= 0:
        return fail("naive counter did not treat clone paraphrases as new")
    if not both["discriminates"]:
        return fail("detector silent in both states")
    if not both["clustered_rejects_clone"]:
        return fail("clustered instrument accepted clone yield")
    if flat["landscape_n"] is None or flat["targeted_n"] is None:
        return fail("flatten n missing")
    if not flat["targeted_flattens_earlier"]:
        return fail(
            f"targeted flatten {flat['targeted_n']} not earlier than "
            f"landscape {flat['landscape_n']}"
        )
    if flat["targeted_contradiction_coverage_at_flatten"] != 1.0:
        return fail("targeted contradiction coverage at flatten != 1")
    if flat["landscape_contradiction_coverage_at_flatten"] != 1.0:
        return fail("landscape contradiction coverage at flatten != 1")
    targ_cov_n2 = live["targeted"]["author_curve"][1]["contradiction_coverage"]
    land_cov_n2 = live["landscape"]["author_curve"][1]["contradiction_coverage"]
    if not (targ_cov_n2 == 1.0 and land_cov_n2 == 0.0):
        return fail("targeted did not cover contradictions earlier than landscape")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    rec = (doc.get("measurements") or {}).get("flatten") or {}
    if rec.get("landscape_n") != flat["landscape_n"]:
        return fail("artifact landscape flatten drifted from live")
    if rec.get("targeted_n") != flat["targeted_n"]:
        return fail("artifact targeted flatten drifted from live")
    rec_floor = (doc.get("measurements") or {}).get("noise_floor") or {}
    if rec_floor.get("clustered_added") != floor["clustered_added"]:
        return fail("artifact noise floor drifted from live")

    print(
        f"SUCCESS:RES-0165-probe1 clone_floor=0 naive_added={floor['naive_added']} "
        f"targeted_n={flat['targeted_n']} landscape_n={flat['landscape_n']} both-states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
