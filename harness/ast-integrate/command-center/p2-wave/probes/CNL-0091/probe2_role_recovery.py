#!/usr/bin/env python3
"""Probe 2: role-recovery (order-based, not bag L1) plus schema discrimination.

Mechanically different from probe 1: first matching speech-act phrase, not
the combined histogram/skew distance. Also reports false-positive rate as a
number and re-runs the both-states control from fixtures, not from the
artifact's claimed fields.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = HERE / "probe2-role-recovery.raw.json"
ART = REPO / "command-center/design/council/CNL-0091-role-collapse-participants-behaving-identically.md"
# Per-unit schema: the catalog output_schema path is a generated $ref shim to
# ast-integrate.invalid and cannot be retrieved. Discrimination lives here.
SCHEMA = HERE / "detector-spec.schema.json"
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000, "false_positive_rate": "low"},
]


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def main() -> int:
    scored = D.score_all()
    idx = by_id(scored)

    plant = idx["collapsed-calibrate"]
    good = idx["diverse-calibrate"]
    agree = idx["genuine-agreement"]
    if plant["role_guess_critic"] != "proposer":
        print("FAILED:CNL-0091-probe2 collapsed critic still recoverable as critic")
        return 1
    if agree["role_guess_critic"] != "critic":
        print("FAILED:CNL-0091-probe2 genuine-agreement critic not recoverable")
        return 1
    if good["role_guess_critic"] != "critic":
        print("FAILED:CNL-0091-probe2 diverse critic not recoverable")
        return 1
    if plant["role_guess_proposer"] != "proposer" or agree["role_guess_proposer"] != "proposer":
        print("FAILED:CNL-0091-probe2 proposer seat not recovered")
        return 1

    # Independent both-states re-run (does not read the artifact).
    if not plant["fired"] or good["fired"] or agree["fired"]:
        print("FAILED:CNL-0091-probe2 both-states re-run mismatch")
        return 1

    clean = [r for r in scored if not r["expect_fire"]]
    bad = [r for r in scored if r["expect_fire"]]
    fp = sum(1 for r in clean if r["fired"]) / float(len(clean))
    fn = sum(1 for r in bad if not r["fired"]) / float(len(bad))
    print(f"false_positive_rate={fp} n_clean={len(clean)}")
    print(f"false_negative_rate={fn} n_bad={len(bad)}")
    if fp != 0.0:
        print("FAILED:CNL-0091-probe2 false-positive rate is not 0")
        return 1
    if fn != 0.0:
        print("FAILED:CNL-0091-probe2 planted-bad miss")
        return 1

    if not SCHEMA.is_file():
        print("FAILED:CNL-0091-probe2 local schema missing")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    rejected = 0
    for g in GARBAGE:
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            rejected += 1
        else:
            print("FAILED:CNL-0091-probe2 schema accepted garbage", list(g)[:4])
            return 1
    print(f"schema_garbage_rejected={rejected}/3")

    artifact_checked = False
    if ART.is_file() and ART.stat().st_size > 0:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(doc, schema)
        except jsonschema.ValidationError as exc:
            print(f"FAILED:CNL-0091-probe2 artifact fails schema: {exc.message}")
            return 1
        artifact_checked = True
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:CNL-0091-probe2 artifact self-declared not delivering")
            return 1
        if "SUCCESS:CNL-0091" not in ART.read_text(encoding="utf-8"):
            print("FAILED:CNL-0091-probe2 sentinel absent")
            return 1
        live_agree = agree["d_combined"]
        claimed = doc["answers"]["genuine_agreement_distance"]
        if abs(float(claimed) - live_agree) > 1e-6:
            print("FAILED:CNL-0091-probe2 agreement distance does not match live", claimed, live_agree)
            return 1
        if abs(float(doc["false_positive_rate"]) - fp) > 1e-9:
            print("FAILED:CNL-0091-probe2 FP rate adjective-or-mismatch")
            return 1
        if not isinstance(doc["false_positive_rate"], (int, float)) or isinstance(doc["false_positive_rate"], bool):
            print("FAILED:CNL-0091-probe2 FP rate is not a number")
            return 1
        mutant = copy.deepcopy(doc)
        mutant["false_positive_rate"] = "low"
        try:
            jsonschema.validate(mutant, schema)
        except jsonschema.ValidationError:
            print("mutant_fp_adjective_rejected=True")
        else:
            print("FAILED:CNL-0091-probe2 schema accepted FP-rate adjective")
            return 1
        mutant2 = copy.deepcopy(doc)
        mutant2["both_states"]["known_present_evaluated_first"] = False
        try:
            jsonschema.validate(mutant2, schema)
        except jsonschema.ValidationError:
            print("mutant_skipped_control_rejected=True")
        else:
            print("FAILED:CNL-0091-probe2 schema accepted skipped detector-control")
            return 1
        print("artifact_schema_ok=True")

    doc = {
        "unit_id": "CNL-0091",
        "role_guess_collapsed_critic": plant["role_guess_critic"],
        "role_guess_agree_critic": agree["role_guess_critic"],
        "false_positive_rate": fp,
        "false_negative_rate": fn,
        "n_clean": len(clean),
        "n_bad": len(bad),
        "schema_garbage_rejected": rejected,
        "artifact_checked": artifact_checked,
        "reran_both_states": True,
        "fired_on_bad": True,
        "silent_on_good": True,
        "genuine_agreement_distance": agree["d_combined"],
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"role_guess_collapsed_critic={plant['role_guess_critic']} "
        f"role_guess_agree_critic={agree['role_guess_critic']} "
        f"d_agree={agree['d_combined']} artifact_checked={artifact_checked}"
    )
    print("SUCCESS:CNL-0091-probe2 role-recovery schema-discrimination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
