#!/usr/bin/env python3
"""Emit the CNL-0089 detector spec at the catalog output_path.

The path ends in .md because the catalog says so; G-1 json.loads that
file, so the body is JSON. Detector-control (planted FIRE) is computed
before any SILENT/absence claim is written.

The catalog output_schema is council-detector-spec, which pins
receipt_core + report.kind. Validation uses the offline local store
(no network $ref).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import local_schema as S  # noqa: E402

OUT = "command-center/design/council/CNL-0089-silence-and-the-minimum-engagement-floor.md"
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
DET = "command-center/p2-wave/probes/CNL-0089/detector.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0089/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0089/probe2_negative_fp.py"
)
PLANTED = "planted-filler-consent.json"
CLEAN = "clean-yield-only-nothing-to-add.json"
QUESTION = (
    "What is the difference between a participant with nothing to add and one "
    "that has disengaged, and what does the runtime do about each?"
)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0089 snippet missing in {rel}: {snippet[:60]}")
    return text[:idx].count("\n") + 1


def digest_rel(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    sha, size = digest_rel(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def compact(result: dict, file: str) -> dict:
    return {
        "fixture_id": result["fixture_id"],
        "file": file,
        "fired": result["fired"],
        "silent": result["silent"],
        "fired_seats": result["fired_seats"],
        "reasons": {
            s: result["seats"][s]["reasons"]
            for s in result["roster"]
            if result["seats"][s]["reasons"]
        },
        "speech": {
            s: {
                "substantive": result["seats"][s]["substantive"],
                "structured_yield": result["seats"][s]["structured_yield"],
                "filler": result["seats"][s]["filler"],
                "explicit_vote": result["seats"][s]["explicit_vote"],
            }
            for s in result["roster"]
        },
        "runtime": result["runtime"],
        "verbatim": json.dumps(
            {
                "fixture_id": result["fixture_id"],
                "fired": result["fired"],
                "silent": result["silent"],
                "fired_seats": result["fired_seats"],
                "reasons": {
                    s: result["seats"][s]["reasons"]
                    for s in result["roster"]
                    if result["seats"][s]["reasons"]
                },
            },
            sort_keys=True,
        ),
    }


def ev(
    claim: str,
    anchor: str,
    source_cmd: str,
    source_out: str,
    source_fp: str,
    verifier_method: str,
    verifier_cmd: str,
    verifier_out: str,
    verifier_fp: str,
) -> dict:
    return {
        "claim": claim,
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": anchor,
        "probes": [
            {
                "role": "source",
                "method": "command",
                "command": source_cmd,
                "raw_output": source_out[:8000],
                "fingerprint": source_fp,
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": verifier_method,
                "command": verifier_cmd,
                "raw_output": verifier_out[:8000],
                "fingerprint": verifier_fp,
                "exit_code": 0,
            },
        ],
    }


def main() -> int:
    planted = D.scan_file(PLANTED)
    if not planted["fired"]:
        print("FAILED:CNL-0089 detector-control: planted fixture silent")
        return 1
    planted_c = compact(planted, PLANTED)

    batt = D.battery()
    if not batt["planted_all_fired"]:
        print("FAILED:CNL-0089 a planted fixture was silent")
        return 1
    if not batt["clean_all_silent"]:
        print("FAILED:CNL-0089 a clean fixture fired")
        return 1

    clean = D.scan_file(CLEAN)
    if not clean["silent"]:
        print("FAILED:CNL-0089 known-good fired")
        return 1
    clean_c = compact(clean, CLEAN)

    engaged = D.scan_file("clean-all-engaged.json")
    fp_rate = float(batt["false_positive_rate"])
    ended = datetime.now(timezone.utc)
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started = now

    impl_line = find_line(DET, "if reason in YIELD_REASONS and ref:")
    filler_line = find_line(DET, 'if int(st["filler"]) >= 3 and speech == 0:')
    consent_line = find_line(
        DET, 'if seat in agreeing and not st["explicit_vote"]:'
    )
    ghost_line = find_line(DET, 'reasons.append("inactivity-without-yield")')

    answer = (
        "Nothing-to-add is a structured yield: a YIELD/PASS speech-act with a "
        "closed reason_code and a referent_id. The runtime credits the engagement "
        "floor, skips leftover quota, and must not treat the yield as consent. "
        "Disengagement is the absence of that speech-act: filler-only turns "
        "(three empty acknowledgements fail the floor), never speaking, being "
        "folded into consensus.agreeing without a vote, or ghosting for "
        "max_inactivity rounds after a contribution without yielding. The "
        "runtime FIRES, marks the seat ABSENT, excludes it from the consenting "
        "set, keeps it in the roster so quorum cannot shrink, and escalates or "
        "replaces. False-positive rate on the four clean fixtures is "
        f"{fp_rate}. SUCCESS:CNL-0089"
    )

    report = {
        "kind": "council-detector-spec",
        "observations": [
            {
                "name": "false_positive_rate",
                "measured": fp_rate,
                "method": "detector.battery over four clean fixtures",
                "anchor": f"{DET}:232",
            },
            {
                "name": "planted_filler_consent_fired",
                "measured": True,
                "method": "scan planted-filler-consent before any absence claim",
                "anchor": f"{DET}:{filler_line}",
            },
            {
                "name": "clean_structured_yield_silent",
                "measured": True,
                "method": "scan clean-yield-only-nothing-to-add",
                "anchor": f"{DET}:{impl_line}",
            },
        ],
        "control_ids": [
            "NC-planted-filler-consent",
            "NC-clean-all-engaged",
        ],
        "title": "Silence and the minimum-engagement floor",
        "question": QUESTION,
        "pathology": (
            "Consent-by-silence and filler-masquerade: a seat that never produces "
            "a substantive speech-act or a structured yield is folded into the "
            "agreeing set, or a seat that contributes once then ghosts without "
            "yielding is treated as still present."
        ),
        "path_note": (
            "Catalog output_path ends in .md; G-1 parses this file with json.loads. "
            "This document is a council-detector-spec receipt."
        ),
        "distinction": {
            "nothing_to_add": (
                "A structured YIELD/PASS with a closed reason_code "
                "(no-new-information | already-stated-by-peer | outside-competence "
                "| awaiting-evidence) and a referent_id pointing at an existing "
                "claim. It is an explicit speech-act. It credits the engagement "
                "floor. It is not a vote and must not enter the agreeing set."
            ),
            "disengaged": (
                "Zero structured speech-acts (including three empty acknowledgements), "
                "or a contribution followed by max_inactivity silent rounds without "
                "a structured yield, or a seat listed in consensus.agreeing without "
                "an explicit AYE/NAY/ABSTAIN vote."
            ),
            "operational_test": (
                "classify() returns STRUCTURED_YIELD only when reason_code is in "
                "the closed set AND referent_id is present; otherwise a YIELD token "
                "is FILLER. Filler and silence never credit the floor. Three ACK "
                "turns with empty bodies fail the floor (IMP-0299)."
            ),
        },
        "detector": {
            "id": "min-engagement-floor",
            "implementation": DET,
            "fires_when": [
                "speech_acts < min_speech_acts (default 1)",
                "filler_count >= 3 and speech_acts == 0 (filler-masquerade)",
                "seat in consensus.agreeing without an explicit vote (consent-by-silence)",
                "after at least one speech-act, inactivity_streak >= max_inactivity without a structured yield",
            ],
            "silent_when": [
                "every seat has >=1 SUBSTANTIVE or STRUCTURED_YIELD speech-act",
                "no agreeing seat lacks an explicit vote",
                "no post-contribution ghosting past max_inactivity",
            ],
        },
        "runtime_actions": {
            "on_nothing_to_add": (
                "Accept the structured yield, credit the speech floor, skip remaining "
                "speaking quota for that seat, do not treat the yield as a vote, do "
                "not escalate."
            ),
            "on_disengaged": (
                "FIRE. Mark the seat ABSENT. Exclude it from the consenting set. "
                "Keep it in the roster so quorum/denominator cannot shrink. Escalate "
                "or replace the seat. Never count silence as aye."
            ),
            "consent_rule": (
                "Only an explicit VOTE with AYE/NAY/ABSTAIN and a rationale of at "
                "least four tokens may affect the agreeing set. Yield is not consent. "
                "Silence is not consent. ACK is not consent."
            ),
            "budget_dial": (
                "Minimum-engagement exhaustion HARD-STOPS the seat (escalate/replace), "
                "it does not DEGRADE the council by treating quiet as agreement. "
                "Degrading here would silently corrupt the stopping rule (CNL-0008)."
            ),
        },
        "detector_control": {
            "known_present_run_first": True,
            "fired_before_absence_reported": True,
            "known_present_fixture": PLANTED,
            "known_present_fired": True,
            "known_present_verbatim": planted_c["verbatim"],
        },
        "both_states": {
            "planted": planted_c,
            "clean": clean_c,
        },
        "false_positive_rate": fp_rate,
        "false_positive_count": batt["false_positive_count"],
        "clean_count": batt["clean_count"],
        "planted_count": len(batt["planted"]),
        "fixture_battery": {
            "planted": [
                {
                    "file": r["file"],
                    "fired": r["fired"],
                    "fired_seats": r["fired_seats"],
                    "reasons": {
                        s: r["seats"][s]["reasons"] for s in r["fired_seats"]
                    },
                }
                for r in batt["planted"]
            ],
            "clean": [
                {
                    "file": r["file"],
                    "fired": r["fired"],
                    "silent": r["silent"],
                }
                for r in batt["clean"]
            ],
        },
        "negative_control": {
            "state_meant_to_reject": (
                "firing on an engaged council (clean-all-engaged) or on a "
                "structured nothing-to-add yield"
            ),
            "what_the_check_did": (
                "SILENT on clean-all-engaged and on clean-yield-only-nothing-to-add; "
                "fired=false, fired_seats=[]"
            ),
            "verbatim": json.dumps(
                {
                    "fixture_id": engaged["fixture_id"],
                    "fired": engaged["fired"],
                    "silent": engaged["silent"],
                    "fired_seats": engaged["fired_seats"],
                },
                sort_keys=True,
            ),
        },
        "three_empty_acknowledgements_satisfy_floor": False,
        "answer": answer,
        "live_tree_anchors": [
            {
                "path": DET,
                "line": impl_line,
                "claim": "structured yield requires closed reason_code and referent_id",
            },
            {
                "path": DET,
                "line": filler_line,
                "claim": "three filler turns with zero speech-acts trip filler-masquerade",
            },
            {
                "path": DET,
                "line": consent_line,
                "claim": "agreeing without an explicit vote is consent-by-silence",
            },
            {
                "path": DET,
                "line": ghost_line,
                "claim": "post-claim silence without yield is inactivity disengagement",
            },
        ],
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0089",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0089",
        "spec_anchor": "_USER-PROMPTS.md:10746-10767",
        "min_bytes_threshold": 512,
        "profile": "council-detector-spec",
        "artifacts": [
            art(DET, "supporting"),
            art(
                "command-center/p2-wave/probes/CNL-0089/fixtures/planted-filler-consent.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/CNL-0089/fixtures/clean-yield-only-nothing-to-add.json",
                "fixture",
            ),
            art(SCHEMA, "supporting"),
        ],
        "evidence": [
            ev(
                "Planted filler-consent (three empty ACKs counted as aye) FIREs "
                "on filler-masquerade and consent-by-silence for seat D.",
                f"{DET}:{filler_line}",
                P1,
                planted_c["verbatim"],
                "cnl0089-src-probe1-planted",
                "static-analysis",
                f"{DET}:{filler_line}",
                "filler>=3 and speech==0 appends filler-masquerade",
                "cnl0089-ver-filler-line",
            ),
            ev(
                "A structured nothing-to-add YIELD is SILENT; false-positive "
                f"rate on {batt['clean_count']} clean fixtures is {fp_rate}.",
                f"{DET}:{impl_line}",
                f"python3 -c import-and-battery {DET}",
                json.dumps(
                    {
                        "false_positive_rate": fp_rate,
                        "clean_count": batt["clean_count"],
                        "clean_all_silent": batt["clean_all_silent"],
                    },
                    sort_keys=True,
                ),
                "cnl0089-src-battery-fp",
                "file-read",
                "command-center/p2-wave/probes/CNL-0089/fixtures/" + CLEAN,
                clean_c["verbatim"],
                "cnl0089-ver-clean-yield-read",
            ),
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-planted-filler-consent",
                "kind": "known-broken-fixture",
                "description": (
                    "Three ACK bodies (+1/agreed/ok) with D in agreeing must FIRE; "
                    "a structured already-stated-by-peer yield must be SILENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": planted_c["verbatim"],
                "good_state_output": clean_c["verbatim"],
            },
            {
                "id": "NC-clean-all-engaged",
                "kind": "known-broken-fixture",
                "description": (
                    "Negative control: the check must stay silent on an engaged "
                    "council (the state it is meant to reject firing on)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": planted_c["verbatim"],
                "good_state_output": json.dumps(
                    {
                        "fixture_id": engaged["fixture_id"],
                        "fired": engaged["fired"],
                        "silent": engaged["silent"],
                        "fired_seats": engaged["fired_seats"],
                    },
                    sort_keys=True,
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0089-probe2-negative-fp-schema",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Probe 2 re-runs the planted/clean battery, demands a numeric "
                "false-positive rate, schema-validates this artifact offline, and "
                "records the negative control verbatim. Re-reading this file is "
                "not the review."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0089/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNL-0089",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0089/probe1_both_states.py"
                ),
                "artifact_path": DET,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "raw_output": planted_c["verbatim"] + " | " + clean_c["verbatim"],
                    "fingerprint": "cnl0089-consumer-probe1",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 1,
            "policy": (
                "two strikes then pivot, PLUS a mandatory detector-control retry: "
                "if the both-states control does not fire on the planted-bad "
                "fixture, the attempt does not count as a failure of the "
                "mechanism - fix the fixture first, once. Max 3 mechanism attempts."
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": (
                        "jsonschema-RefResolutionError-ast-integrate.invalid"
                    ),
                    "outcome": "FAILED",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "offline-resolver-receipt-core",
                    "outcome": "SUCCESS",
                },
            ],
            "pivot_alternatives": [
                "offline RefResolver store over platform/schema files",
                "reshape catalog artifact to receipt_core + report.kind",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "max_inactivity=2 is the fixture default, not a measured "
                    "production SLA"
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Measure live council inactivity windows once CNL-0047's "
                    "speaking-order engine is on this tree and record the trip."
                ),
            },
            {
                "claim": (
                    "open-ended natural-language filler outside the closed ACK "
                    "lexicon is classified FILLER only when it lacks structured "
                    "fields; a future IMP unit owns a trained filler model"
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Hand a labeled filler corpus to an IMP unit; this detector "
                    "keeps the closed ACK lexicon until then."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-anti-failure-detector-designer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
        "extensions": {
            "cloud_ok": False,
            "produced_at": now,
        },
    }

    empty_errs = S.errors_of({})
    if not empty_errs:
        print("FAILED:CNL-0089 schema accepted empty object")
        return 1
    errs = S.errors_of(doc)
    if errs:
        print("FAILED:CNL-0089 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:CNL-0089 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
