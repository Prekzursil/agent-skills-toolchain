#!/usr/bin/env python3
"""Probe 1: both scripted councils × all six spec expressions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from stopping import SPEC_EXPRESSIONS, and_is_not_or_under_partial  # noqa: E402
from simulate import run_all  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0101-stopping-rule-both-directions.json"
UNIT = "ADV-0101"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0101-probe1 {msg}")
    return 1


def main() -> int:
    bundle = run_all()
    and_ctrl = and_is_not_or_under_partial()
    print(f"exercised={bundle['all_six_exercised']}")
    print(f"skipped={bundle['skipped_expressions']}")
    print(f"release_mode={bundle['release_mode']}")
    print(f"unsatisfiable={bundle['unsatisfiable_under_release_mode']}")
    print(f"premature_verdict={bundle['premature_verdict']} hits={bundle['premature_hits']}")
    print(f"endless_verdict={bundle['endless_verdict']} hits={bundle['endless_hits']}")
    print(f"e6_unsuccessful_search_did_not_fire={bundle['e6_unsuccessful_search_did_not_fire']}")
    print(f"e6_real_proof_fires_on_healthy={bundle['e6_real_proof_fires_on_healthy']}")
    print(f"and_did_not_behave_as_or={and_ctrl['and_did_not_behave_as_or']}")

    if bundle["all_six_exercised"] != [e["id"] for e in SPEC_EXPRESSIONS]:
        return fail("not-all-six")
    if bundle["skipped_expressions"]:
        return fail("skipped-expression")
    if "E6" not in bundle["all_six_exercised"]:
        return fail("proof-of-impossibility-not-exercised")
    if not bundle["e6_unsuccessful_search_did_not_fire"]:
        return fail("unsuccessful-search-counted-as-proof")
    if not bundle["e6_real_proof_fires_on_healthy"]:
        return fail("real-proof-did-not-fire")
    if bundle["premature_verdict"] != "CONFIRMED":
        return fail("premature-not-confirmed")
    if bundle["endless_verdict"] != "CONFIRMED":
        return fail("endless-not-confirmed")
    if not and_ctrl["and_did_not_behave_as_or"]:
        return fail("and-behaved-as-or")

    e3 = next(r for r in bundle["expression_runs"] if r["expression"]["id"] == "E3")
    inst = e3["councils"]["instant_agree"]
    print(
        f"E3 instant stop={inst['stop_reason']} at={inst['stopped_at']} "
        f"premature={inst['premature_stop']}"
    )
    if not inst["premature_stop"]:
        return fail("instant-unanimity-not-premature")

    e1 = next(r for r in bundle["expression_runs"] if r["expression"]["id"] == "E1")
    end = e1["councils"]["endless_low_info"]
    print(f"E1 endless stop={end['stop_reason']} rounds={end['rounds_run']}")
    if not end["failed_to_stop"]:
        return fail("e1-endless-stopped")

    healthy = e1["councils"]["healthy_progress"]
    print(
        f"E1 healthy stop={healthy['stop_reason']} at={healthy['stopped_at']} "
        f"premature={healthy['premature_stop']}"
    )
    if healthy["stop_reason"] != "expression" or healthy["premature_stop"]:
        return fail("healthy-control")

    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("unit_id")) != UNIT:
        return fail("unit_id")
    if "SUCCESS:ADV-0101" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    ids = [t.get("id") for t in doc.get("enumerated_targets") or []]
    if "premature_convergence" not in ids or "endless_low_information_loop" not in ids:
        return fail("targets-missing")
    by_id = {t["id"]: t for t in doc["enumerated_targets"]}
    if by_id["premature_convergence"]["verdict"] != bundle["premature_verdict"]:
        return fail("artifact-premature-drift")
    if by_id["endless_low_information_loop"]["verdict"] != bundle["endless_verdict"]:
        return fail("artifact-endless-drift")
    if doc["evidence"]["e6_unsuccessful_search_did_not_fire"] is not True:
        return fail("artifact-e6-drift")

    payload = {
        "pass": True,
        "probe": "probe1-paired-councils",
        "premature_verdict": bundle["premature_verdict"],
        "endless_verdict": bundle["endless_verdict"],
        "exercised": bundle["all_six_exercised"],
        "unit_id": UNIT,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:ADV-0101-probe1 paired councils both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
