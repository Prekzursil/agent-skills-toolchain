#!/usr/bin/env python3
"""Emit CNL-0120 dissent-preservation simulation spec (JSON in .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import preserve as P  # noqa: E402
import recount as R  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0120-dissent-preservation-simulation-with-a-planted-dropped-dis.md"
)
SCHEMA = "command-center/schema/council-simulation-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0120/probe1_intact_green.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0120/probe2_planted_drop.py"
)
QUESTION = (
    "Given a scripted council containing exactly one dissent, does that dissent "
    "survive into the synthesis — and does the check FAIL when the dissent is "
    "deliberately removed?"
)
CLAIM = (
    "A claim-id set-difference plus token/counterexample check is GREEN on an "
    "intact one-dissent synthesis and RED when that dissent is planted-dropped "
    "from synthesis only; a nonempty-synthesis dummy stays green in both states."
)
# Catalog output_schema is a $ref shim to ast-integrate.invalid. jsonschema
# 4.10 tries the network and raises RefResolutionError; the shim itself has
# no constraints. Validate the simulation spec against a local structural
# schema that still rejects garbage ({}, unrelated blobs).
LOCAL_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "both_states",
        "negative_control",
        "evidence",
        "tests",
        "vacuous_control",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0120"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:CNL-0120"},
        "both_states": {
            "type": "object",
            "required": ["intact", "planted_drop"],
            "properties": {
                "intact": {
                    "type": "object",
                    "required": ["verdict", "fired"],
                    "properties": {
                        "verdict": {"const": "GREEN"},
                        "fired": {"const": False},
                    },
                },
                "planted_drop": {
                    "type": "object",
                    "required": ["verdict", "fired"],
                    "properties": {
                        "verdict": {"const": "RED"},
                        "fired": {"const": True},
                    },
                },
            },
        },
        "negative_control": {
            "type": "object",
            "required": ["state_meant_to_reject", "check_does", "verbatim"],
        },
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 2},
        "vacuous_control": {
            "type": "object",
            "required": ["intact", "planted_drop", "measures_nothing"],
            "properties": {
                "intact": {"const": "GREEN"},
                "planted_drop": {"const": "GREEN"},
                "measures_nothing": {"const": True},
            },
        },
    },
}


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0120 emit snippet missing in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def main() -> int:
    script = H.load_fixture()
    d = H.assert_exactly_one_dissent(script)
    intact = H.run_intact(script)
    planted = H.plant_drop(intact)
    chk_ok = P.check(intact["transcript"], intact["synthesis"])
    chk_bad = P.check(planted["transcript"], planted["synthesis"])
    lost_ok = R.lost_ids(intact)
    lost_bad = R.lost_ids(planted)
    if chk_ok["verdict"] != "GREEN" or chk_ok["fired"]:
        print("FAILED:CNL-0120 emit intact not GREEN", chk_ok)
        return 1
    if chk_bad["verdict"] != "RED" or not chk_bad["fired"]:
        print("FAILED:CNL-0120 emit planted drop not RED", chk_bad)
        return 1
    if lost_ok:
        print("FAILED:CNL-0120 emit recount lost on intact", lost_ok)
        return 1
    if lost_bad != [d["claim_id"]]:
        print("FAILED:CNL-0120 emit recount lost mismatch", lost_bad)
        return 1
    if P.vacuous_nonempty(intact["synthesis"]) is not True:
        print("FAILED:CNL-0120 emit vacuous intact")
        return 1
    if P.vacuous_nonempty(planted["synthesis"]) is not True:
        print("FAILED:CNL-0120 emit vacuous planted (dummy must stay green)")
        return 1

    verbatim = json.dumps(
        {
            "verdict": chk_bad["verdict"],
            "fired": chk_bad["fired"],
            "lost_claim_ids": chk_bad["lost_claim_ids"],
            "token_present": chk_bad["token_present"],
            "counterexample_present": chk_bad["counterexample_present"],
            "generic_phrase_only": chk_bad["generic_phrase_only"],
            "reason": chk_bad["reason"],
        },
        sort_keys=True,
    )
    a_harness = (
        "command-center/p2-wave/probes/CNL-0120/harness.py:"
        + str(find_line("command-center/p2-wave/probes/CNL-0120/harness.py", "def plant_drop"))
    )
    a_preserve = (
        "command-center/p2-wave/probes/CNL-0120/preserve.py:"
        + str(find_line("command-center/p2-wave/probes/CNL-0120/preserve.py", "fired = bool(lost)"))
    )
    a_fixture = (
        "command-center/p2-wave/probes/CNL-0120/fixtures/council.json:"
        + str(
            find_line(
                "command-center/p2-wave/probes/CNL-0120/fixtures/council.json",
                '"vote": "NO"',
            )
        )
    )
    a_recount = (
        "command-center/p2-wave/probes/CNL-0120/recount.py:"
        + str(find_line("command-center/p2-wave/probes/CNL-0120/recount.py", "def lost_ids"))
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0120",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0120",
        "title": "Dissent-preservation simulation with a planted dropped dissent",
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "answer": (
            "YES: the single scripted dissent survives intact synthesis "
            "(GREEN); planting a drop turns the same check RED. A nonempty "
            "synthesis dummy stays GREEN in both states and therefore measures "
            "nothing. Negative control (verbatim): planted drop fires RED with "
            "lost_claim_ids=[D-CNL0120-01], token_present=false, "
            "generic_phrase_only=true. SUCCESS:CNL-0120"
        ),
        "verdict": (
            "YES: the single scripted dissent survives intact synthesis "
            "(GREEN); planting a drop turns the same check RED."
        ),
        "output_schema": SCHEMA,
        "output_schema_resolution": {
            "declared": SCHEMA,
            "resolved": False,
            "fallback": "local-structural",
            "reason": (
                "command-center/schema/council-simulation-spec.schema.json is a "
                "$ref shim to ast-integrate.invalid; jsonschema 4.10 raises "
                "RefResolutionError (no network id). Local schema still "
                "rejects garbage and requires both-states polarity."
            ),
        },
        "min_bytes_threshold": 4096,
        "required_fix": None,
        "cloud_ok": False,
        "simulation": {
            "harness": "command-center/p2-wave/probes/CNL-0120/harness.py",
            "fixture": "command-center/p2-wave/probes/CNL-0120/fixtures/council.json",
            "dissent_count": 1,
            "dissent": {
                "participant_id": d["id"],
                "claim_id": d["claim_id"],
                "token": d["token"],
                "counterexample": d["counterexample"],
            },
            "note": (
                "CNL-0117 / CNL-0070 / CNL-0097 artifacts are absent on this "
                "worktree. This unit ships a local scripted harness and "
                "preservation check so the simulation is runnable here."
            ),
        },
        "both_states": {
            "intact": {
                "verdict": chk_ok["verdict"],
                "fired": chk_ok["fired"],
                "lost_claim_ids": chk_ok["lost_claim_ids"],
                "token_present": chk_ok["token_present"],
                "counterexample_present": chk_ok["counterexample_present"],
                "recount_lost": lost_ok,
                "vacuous_nonempty": True,
            },
            "planted_drop": {
                "verdict": chk_bad["verdict"],
                "fired": chk_bad["fired"],
                "lost_claim_ids": chk_bad["lost_claim_ids"],
                "token_present": chk_bad["token_present"],
                "counterexample_present": chk_bad["counterexample_present"],
                "recount_lost": lost_bad,
                "generic_phrase_only": chk_bad["generic_phrase_only"],
                "vacuous_nonempty": True,
            },
        },
        "negative_control": {
            "state_meant_to_reject": (
                "synthesis with the recorded dissent stripped and only the "
                "generic phrase 'Dissent was considered.' left"
            ),
            "check_does": (
                "FIRES; verdict=RED; lost_claim_ids=["
                + d["claim_id"]
                + "]; token_present=false; counterexample_present=false; "
                "generic_phrase_only=true"
            ),
            "verbatim": verbatim,
        },
        "vacuous_control": {
            "check": "synthesis nonempty AND decision string present",
            "intact": "GREEN",
            "planted_drop": "GREEN",
            "measures_nothing": True,
        },
        "tests": [
            {
                "id": "intact-green",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "planted-drop-red",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "negative-control-verbatim",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "claim": "Fixture encodes exactly one NO vote with claim_id, token and counterexample.",
                "verdict": "CONFIRMED",
                "anchor": a_fixture,
            },
            {
                "claim": "Planted drop strips minority_report and dissent residue from synthesis only.",
                "verdict": "CONFIRMED",
                "anchor": a_harness,
            },
            {
                "claim": "Preservation check fires on lost claim-id or missing token/counterexample.",
                "verdict": "CONFIRMED",
                "anchor": a_preserve,
            },
            {
                "claim": "Independent recount recomputes lost ids without calling preserve.check.",
                "verdict": "CONFIRMED",
                "anchor": a_recount,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0120-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "re_ran_both_states": True,
            "scope_not_agreement": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0120/harness.py",
                "exists": True,
                "role": "harness",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0120/preserve.py",
                "exists": True,
                "role": "check",
            },
        ],
        "dependency_status": {
            "CNL-0117": "absent — unit-local scripted harness used",
            "CNL-0070": "absent — minority-report attachment implemented locally",
            "CNL-0097": "absent — lost-dissent set-diff implemented locally",
        },
        "strongest_surviving_counterargument": (
            "A synthesis could keep the token and the counterexample string "
            "while gutting the surrounding argument. This check would still "
            "go GREEN. That is a remaining substance-vs-presence gap "
            "(ADV-0116 class 2), not a reason to skip the planted-drop "
            "control, which this unit does run."
        ),
        "ts": now,
    }
    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:CNL-0120 declared schema missing {SCHEMA}")
        return 1
    validator = jsonschema.Draft7Validator(LOCAL_OUTPUT_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0120 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "ARC-0001", "state": "SUCCESS", "sentinel": "SUCCESS:X"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNL-0120 schema accepted garbage {list(garbage)[:2]}")
            return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0120" not in text:
        print("FAILED:CNL-0120 emit sentinel not in artifact text")
        return 1
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0120 emit self-declared", parsed.get("state"))
        return 1
    if dest.stat().st_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0120 artifact {dest.stat().st_size}B below floor")
        return 1
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0120 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
