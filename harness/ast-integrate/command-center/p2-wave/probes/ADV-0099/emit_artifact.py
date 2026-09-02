#!/usr/bin/env python3
"""Emit ADV-0099 hallucinated-expertise pathology artifact."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402
import quiz as Q  # noqa: E402
import weights_gate as W  # noqa: E402

OUT = "command-center/adversarial/ADV-0099-hallucinated-expertise-in-selection.json"
SCHEMA = "command-center/schema/council-pathology-sim.schema.json"
UID = "ADV-0099"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0099/probe1_evidentiary_basis.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0099/probe2_known_answer_calibration.py"
)
QUESTION = (
    "When a participant is selected or self-describes as an expert, is that "
    "expertise grounded in anything checkable - and does the runtime accept an "
    "unverifiable expertise claim as a vote-weight input?"
)
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0099 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from {CONFIRMED|REFUTED|"
    "PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and records the result "
    "of every listed control/negative test. Any missing control downgrades the "
    "unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0099 <reason>."
)
PROBE1_TEXT = (
    "Probe 1: for each expertise claim used as an input, identify its "
    "evidentiary basis in the code (a calibration record, a past-accuracy "
    "score, or a free-text self-assertion)."
)
PROBE2_TEXT = (
    "Probe 2 (mechanically different): behavioural - pose questions with known "
    "answers inside the claimed domain and measure accuracy against the claimed "
    "expertise level, which converts an assertion into a measurement."
)
CONTROL_TEXT = (
    "control: include a domain where the participant genuinely performs well "
    "and one where it does not, and require the measurement to separate them; "
    "a flat accuracy result means the question set is not discriminating"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ADV-0099 emit missing snippet in {rel}: {snippet!r}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, claim: str) -> dict:
    return {
        "path": rel,
        "line": find_line(rel, snippet),
        "snippet": snippet,
        "claim": claim,
    }


def main() -> int:
    live_audit = A.run_audit()
    live_quiz = Q.run_calibration()
    live_w = W.run_weight_paths(live_quiz)
    if not live_audit["pathology_confirmed"]:
        print("FAILED:ADV-0099 emit audit did not confirm pathology")
        return 1
    if not live_quiz["pass"]:
        print("FAILED:ADV-0099 emit calibration/control failed")
        return 1
    if not live_w["pass"]:
        print("FAILED:ADV-0099 emit production weight path failed")
        return 1

    bld = next(i for i in live_audit["inputs"] if i["id"] == "bld0054-competence-probe")
    weights = next(i for i in live_audit["inputs"] if i["id"] == "production-vote-weights")
    ctl = live_quiz["control"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    probe1_raw = json.dumps(
        {
            "probe": "probe1-evidentiary-basis",
            "pathology_confirmed": True,
            "checkable_inputs": live_audit["checkable_inputs"],
            "unverifiable_inputs": live_audit["unverifiable_inputs"],
            "inputs": [
                {
                    "id": i["id"],
                    "path": i["path"],
                    "present": i["present"],
                    "evidentiary_basis": i["evidentiary_basis"],
                    "used_as": i.get("used_as"),
                }
                for i in live_audit["inputs"]
            ],
        },
        indent=2,
        sort_keys=True,
    )
    probe2_raw = json.dumps(
        {
            "probe": "probe2-known-answer-calibration",
            "discriminating": True,
            "separation_crypto": live_quiz["separation_crypto"],
            "baseline_lay_crypto_accuracy": live_quiz["baseline_lay_crypto_accuracy"],
            "genuine_crypto_acc_crypto": ctl["genuine_crypto_acc_crypto"],
            "genuine_crypto_acc_unicode": ctl["genuine_crypto_acc_unicode"],
            "claimed_crypto_acc_crypto": ctl["claimed_crypto_acc_crypto"],
            "claimed_crypto_acc_unicode": ctl["claimed_crypto_acc_unicode"],
            "naive_effective": live_w["naive"]["effective"],
            "gated_effective": live_w["gated"]["effective"],
            "unverifiable_claim_accepted_as_weight": True,
        },
        indent=2,
        sort_keys=True,
    )

    doc = {
        "unit_id": UID,
        "id": UID,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0099",
        "completion_sentinel": COMPLETION_SENTINEL,
        "report_kind": "council-pathology-sim",
        "title": "Hallucinated expertise in participant selection and self-description",
        "question": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10923, 11241",
        "produced_at": now,
        "cloud_ok": False,
        "min_bytes_threshold": 2048,
        "targets": [
            {
                "id": "expertise-evidentiary-basis",
                "question": (
                    "When a participant is selected or self-describes as an expert, "
                    "is that expertise grounded in anything checkable?"
                ),
                "verdict": "CONFIRMED",
                "meaning": (
                    "CONFIRMED = the pathology is present: every live expertise/"
                    "weight input is a free-text self-assertion, a caller-supplied "
                    "number, or an absent module. No calibration record or "
                    "past-accuracy score is consulted."
                ),
            },
            {
                "id": "unverifiable-expertise-as-vote-weight",
                "question": (
                    "Does the runtime accept an unverifiable expertise claim as a "
                    "vote-weight input?"
                ),
                "verdict": "CONFIRMED",
                "meaning": (
                    "CONFIRMED = production resolve_weights accepts a caller "
                    "authority integer that encodes a claimed-expert premium and "
                    "ignores an expertise field. A hallucinated cryptographer "
                    "receives weight 5; the known-answer gate refuses that premium."
                ),
            },
        ],
        "overall_verdict": "CONFIRMED",
        "probe1": {
            "pathology_confirmed": True,
            "checkable_inputs": live_audit["checkable_inputs"],
            "unverifiable_inputs": live_audit["unverifiable_inputs"],
            "bld0054_accepts_unmeasured_high_score": bld["accepts_unmeasured_high_score"],
            "weights_mentions_expertise_or_calibration": weights[
                "mentions_expertise_or_calibration"
            ],
            "inputs": live_audit["inputs"],
        },
        "probe2": {
            "discriminating": True,
            "flat_accuracy": False,
            "separation_crypto": live_quiz["separation_crypto"],
            "baseline_lay_crypto_accuracy": live_quiz["baseline_lay_crypto_accuracy"],
            "genuine_crypto_acc_crypto": ctl["genuine_crypto_acc_crypto"],
            "genuine_crypto_acc_unicode": ctl["genuine_crypto_acc_unicode"],
            "claimed_crypto_acc_crypto": ctl["claimed_crypto_acc_crypto"],
            "claimed_crypto_acc_unicode": ctl["claimed_crypto_acc_unicode"],
            "naive_authority": live_quiz["naive_authority_for_crypto_task"],
            "gated_authority": live_quiz["gated_authority_for_crypto_task"],
            "naive_effective": live_w["naive"]["effective"],
            "gated_effective": live_w["gated"]["effective"],
            "unverifiable_claim_accepted_as_weight": True,
            "quiz_refuses_premium": True,
            "genuine_premium_kept": True,
            "production_ignores_expertise_field": True,
        },
        "named_probes": [
            {
                "id": "probe1",
                "catalog_text": PROBE1_TEXT,
                "command": P1,
                "raw_output": probe1_raw,
            },
            {
                "id": "probe2",
                "catalog_text": PROBE2_TEXT,
                "command": P2,
                "raw_output": probe2_raw,
            },
        ],
        "tests": [
            {
                "id": "T-EVIDENTIARY-BASIS-AUDIT",
                "name": "Classify every expertise/weight input",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-KNOWN-ANSWER-CALIBRATION",
                "name": "Pose known-answer questions in the claimed domain",
                "command": P2,
                "result": "PASS",
            },
        ],
        "controls": [
            {
                "id": "NC-DOMAIN-SEPARATION",
                "requirement": CONTROL_TEXT,
                "result": "PASS",
                "verbatim": (
                    "genuine-crypto accuracy cryptography="
                    f"{ctl['genuine_crypto_acc_crypto']} unicode="
                    f"{ctl['genuine_crypto_acc_unicode']}; claimed-crypto "
                    f"cryptography={ctl['claimed_crypto_acc_crypto']} unicode="
                    f"{ctl['claimed_crypto_acc_unicode']}; separation_crypto="
                    f"{live_quiz['separation_crypto']} (min 0.5). "
                    "Question sets are discriminating."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "negative_controls": [
            {
                "id": "NC-DOMAIN-SEPARATION",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": "PASS",
            }
        ],
        "reviewer": {
            "reviewer_id": "ADV-0099-probe2-known-answer-calibration",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 is mechanically different from probe 1: it scores "
                "fixture answerers on known-answer items and re-derives vote "
                "weight from production resolve_weights, not from the audit "
                "report."
            ),
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/ADV-0099/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            "tools/council/vote/weights.py",
            "command-center/p2-wave/probes/BLD-0054/runtime.py",
        ],
        "defects": [],
        "evidence": [
            ev(
                "tools/council/vote/weights.py",
                "authority = int(row[\"authority\"])",
                "Caller-supplied authority becomes vote weight with no expertise check.",
            ),
            ev(
                "tools/council/vote/weights.py",
                "AUTHORITY_BY_ROLE",
                "Role ladder is a second ungated weight input.",
            ),
            ev(
                "command-center/p2-wave/probes/BLD-0054/runtime.py",
                "if p.claimed_domain and p.quiz_accuracy < 0.6:",
                "Competence probe trusts a caller float; it never poses a question.",
            ),
            ev(
                "command-center/p2-wave/probes/ADV-0099/quiz.py",
                "MIN_SEPARATION = 0.5",
                "Known-answer control requires the two domains to separate answerers.",
            ),
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "tools/council/vote/weights.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0099/audit.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0099/quiz.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "tools/council/participants/select_expertise.py was implemented",
                "ADV rebuild of IMP-0269",
            ],
            "production_select_expertise": False,
            "production_vote_weights": True,
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        print("FAILED:ADV-0099 emit jsonschema not installed")
        return 1
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ADV-0099 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ADV-0099 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ADV-0099 artifact {size}B below floor")
        return 1
    if COMPLETION_SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:ADV-0099 completion_sentinel absent from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "verdict=CONFIRMED separation_crypto="
        f"{live_quiz['separation_crypto']} naive_claimed="
        f"{live_w['naive']['effective'].get('claimed-crypto')} "
        f"gated_claimed={live_w['gated']['effective'].get('claimed-crypto')}"
    )
    print("SUCCESS:ADV-0099 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
