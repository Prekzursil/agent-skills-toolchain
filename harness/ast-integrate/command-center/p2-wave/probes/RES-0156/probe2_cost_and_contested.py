#!/usr/bin/env python3
"""Probe 2: cost from recorded corpus + CONTESTED deciding experiment.

Negative control required by the catalog: at least one lens stays CONTESTED
with a deciding experiment (bind object_scope) rather than a preferred
standard. Cost figures are live measurements of citation counts and
duplicate Read tool-calls, not recollection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import checker as C  # noqa: E402
import corpus as K  # noqa: E402
from lenses import CONTESTED, GROUNDED, IDEATION, LENS_BY_ID, REPO  # noqa: E402

ART = (
    REPO
    / "command-center/research/gem-hunt"
    / "RES-0156-grounded-vs-ideation-evidence-split.json"
)
SENTINEL = "SUCCESS:RES-0156"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0156-probe2 {msg}")
    return 1


def main() -> int:
    contested = [
        row for row in LENS_BY_ID.values() if row["standard"] == CONTESTED
    ]
    if len(contested) < 1:
        return fail("no CONTESTED lens — assigned by preference")
    tqa = LENS_BY_ID["targeted-question-answering"]
    if tqa["standard"] != CONTESTED:
        return fail("targeted-question-answering was assigned a standard by preference")
    if tqa.get("deciding_experiment") != "bind-object-scope":
        return fail("CONTESTED lens missing deciding experiment")

    findings = json.loads(
        (HERE / "fixtures" / "findings.json").read_text(encoding="utf-8")
    )["findings"]
    unbound = C.check_finding(findings["contested_unbound"])
    estate = C.check_finding(findings["contested_estate"])
    external = C.check_finding(findings["contested_external"])
    estate_wrong = C.check_finding(findings["contested_estate_wrong"])
    external_wrong = C.check_finding(findings["contested_external_wrong"])

    if unbound.get("status") != CONTESTED:
        return fail(f"unbound was assigned {unbound}")
    if not estate.get("compliant") or estate.get("applied_standard") != GROUNDED:
        return fail(f"estate-bound should be GROUNDED PASS got {estate}")
    if not external.get("compliant") or external.get("applied_standard") != IDEATION:
        return fail(f"external-bound should be IDEATION PASS got {external}")
    if estate_wrong.get("status") != "WRONG_STANDARD":
        return fail(f"estate+url-only should WRONG_STANDARD got {estate_wrong}")
    if external_wrong.get("status") != "FORBIDDEN_GROUNDING":
        return fail(f"external+repo-only should FORBIDDEN_GROUNDING got {external_wrong}")

    live = K.measure()
    summary = live["summary"]
    planted = live["planted"]
    if not summary.get("planted_controls_pass"):
        return fail(f"planted controls failed {planted}")
    if not (HERE / "fixtures" / "prior_fanout_records.json").is_file():
        return fail("frozen prior-fan-out extract missing")
    if summary["n_live_records"] < 1:
        return fail("frozen prior-fan-out extract scored no records")
    # Cost figures must be integers computed from the scan, not placeholders.
    cost = summary["cost"]
    for key in (
        "duplicate_reads_ideation_repo_only",
        "zero_citation_grounded_outputs",
        "duplicate_repo_path_events",
    ):
        if not isinstance(cost.get(key), int) or cost[key] < 0:
            return fail(f"cost.{key} is not a measured integer")

    if not ART.is_file():
        return fail("catalog artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel missing")
    rec_cost = ((doc.get("design") or {}).get("cost") or {}).get("live") or {}
    for key, val in cost.items():
        if rec_cost.get(key) != val:
            return fail(f"artifact cost.live.{key}={rec_cost.get(key)!r} != {val!r}")
    rec_n = ((doc.get("design") or {}).get("cost") or {}).get("n_live_records")
    if rec_n != summary["n_live_records"]:
        return fail(f"artifact n_live_records drifted {rec_n} != {summary['n_live_records']}")

    rec_exp = ((doc.get("design") or {}).get("contested") or {}).get(
        "deciding_experiment"
    )
    if rec_exp != "bind-object-scope":
        return fail("artifact contested deciding_experiment missing")

    print(
        json.dumps(
            {
                "contested_lens": tqa["id"],
                "unbound": unbound["status"],
                "estate_bound": estate["applied_standard"],
                "external_bound": external["applied_standard"],
                "cost": cost,
                "n_live_records": summary["n_live_records"],
                "planted_ok": True,
            },
            indent=2,
        )
    )
    print("SUCCESS:RES-0156-probe2 cost-from-corpus + contested-experiment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
