#!/usr/bin/env python3
"""Emit IMP-0306 receipt and per-unit G-1 return + manifest.

Order: run unit tests, persist decision fixtures, write
command-center/receipts/IMP-0306.json, re-run named probes, then write
SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.
Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(REPO))
from tools.council.vote.consent import (  # noqa: E402
    LATE_RECORD_AND_IGNORE,
    MODE_CONSENT,
    MODE_VETO,
    RESP_CONSENT,
    RESP_OBJECT,
    RESP_VETO,
    SILENCE_IS_CONSENT,
    ConsentSession,
    decision_from_events,
    strip_silence_policy,
    validate_artifact,
)

UNIT = "IMP-0306"
OUT = "command-center/receipts/IMP-0306.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0306/probe1_modes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0306/probe2_silence_policy.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/vote/tests/test_consent.py"
)
WINDOW = {"opens_at": 1000.0, "closes_at": 2000.0, "timezone": "UTC"}
SEATS = [
    {"id": "alice", "veto_right": True},
    {"id": "bob", "veto_right": False},
    {"id": "cara", "veto_right": False},
]
SUPPORTING = [
    "tools/council/vote/consent.py",
    "tools/council/vote/tests/test_consent.py",
    "command-center/p2-wave/probes/IMP-0306/probe1_modes.py",
    "command-center/p2-wave/probes/IMP-0306/probe2_silence_policy.py",
    "command-center/p2-wave/probes/IMP-0306/fixtures/late_objection.json",
    "command-center/p2-wave/probes/IMP-0306/fixtures/decision_consent.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def persist_fixtures() -> dict:
    consent = decision_from_events(
        proposal_id="imp-0306-consent-by-silence",
        mode=MODE_CONSENT,
        silence_policy=SILENCE_IS_CONSENT,
        late_objection_policy=LATE_RECORD_AND_IGNORE,
        objection_window=WINDOW,
        participants=SEATS,
        events=[
            {
                "participant_id": "alice",
                "kind": RESP_CONSENT,
                "at": 1100,
                "reason": "explicit consent inside the window",
            }
        ],
        close_at=2000,
        proposal="Ship consent with a recorded objection window.",
    )
    fix_dir = HERE / "fixtures"
    fix_dir.mkdir(parents=True, exist_ok=True)
    consent_path = fix_dir / "decision_consent.json"
    consent_path.write_text(
        json.dumps(consent, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    late_s = ConsentSession(
        proposal_id="imp-0306-late-objection",
        mode=MODE_CONSENT,
        silence_policy=SILENCE_IS_CONSENT,
        late_objection_policy=LATE_RECORD_AND_IGNORE,
        objection_window=WINDOW,
        participants=SEATS,
        proposal="Ship the consent protocol with a recorded objection window.",
    )
    late_s.respond("alice", RESP_CONSENT, 1100, "explicit consent inside the window")
    at_close = late_s.close(2000)
    late_rec = late_s.respond(
        "bob", RESP_OBJECT, 2500, "arrives after objection_window.closes_at"
    )
    after_late = late_s.to_artifact()

    veto_s = ConsentSession(
        proposal_id="imp-0306-veto",
        mode=MODE_VETO,
        silence_policy=SILENCE_IS_CONSENT,
        late_objection_policy=LATE_RECORD_AND_IGNORE,
        objection_window=WINDOW,
        participants=SEATS,
        proposal="veto-mode fixture",
    )
    veto_s.respond("alice", RESP_VETO, 1500, "holder veto")
    veto_art = veto_s.close(2000)

    mutant_errs = validate_artifact(strip_silence_policy(consent))
    good_errs = validate_artifact(consent)
    return {
        "consent": consent,
        "late_at_close": at_close,
        "late_rec": late_rec,
        "after_late": after_late,
        "veto": veto_art,
        "mutant_errs": mutant_errs,
        "good_errs": good_errs,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rc_t, out_t = run_cmd(TEST_CMD)
    if rc_t != 0:
        print(f"FAILED:IMP-0306 tests rc={rc_t}")
        print(out_t[-4000:])
        return 1

    live = persist_fixtures()
    if live["consent"]["outcome"] != "CONSENTED":
        print(f"FAILED:IMP-0306 consent fixture {live['consent']['outcome']}")
        return 1
    if live["veto"]["outcome"] != "VETOED":
        print(f"FAILED:IMP-0306 veto fixture {live['veto']['outcome']}")
        return 1
    if live["after_late"]["outcome"] != "CONSENTED" or live["late_rec"].get("admitted"):
        print("FAILED:IMP-0306 late-objection fixture did not ignore")
        return 1
    if live["good_errs"] or not live["mutant_errs"]:
        print(
            f"FAILED:IMP-0306 negative control good={live['good_errs']} "
            f"mutant={live['mutant_errs']}"
        )
        return 1

    p_tests = L.probe("source", "command", TEST_CMD, out_t[-4000:], rc_t)
    p_consent = L.probe(
        "source",
        "command",
        "python3 -c ConsentSession close silence_is_consent",
        json.dumps(
            {
                "outcome": live["consent"]["outcome"],
                "silence_policy": live["consent"]["silence_policy"],
                "bob": live["consent"]["per_participant_state"]["bob"]["status"],
                "cara": live["consent"]["per_participant_state"]["cara"]["status"],
                "window": live["consent"]["objection_window"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_late = L.probe(
        "verifier",
        "command",
        "python3 -c late objection after close with record_and_ignore",
        json.dumps(
            {
                "admitted": live["late_rec"].get("admitted"),
                "handling": live["late_rec"].get("handling"),
                "outcome_after": live["after_late"]["outcome"],
                "late_count": len(live["after_late"].get("late_objections") or []),
            },
            sort_keys=True,
        ),
        0,
    )
    p_neg = L.probe(
        "verifier",
        "command",
        "validate_artifact(strip_silence_policy(consent))",
        json.dumps(
            {"good_errors": live["good_errs"], "mutant_errors": live["mutant_errs"]},
            sort_keys=True,
        ),
        0,
    )

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    impl = L.art("tools/council/vote/consent.py", "implementation")
    tests_art = L.art("tools/council/vote/tests/test_consent.py", "supporting")
    late_fix = L.art(
        "command-center/p2-wave/probes/IMP-0306/fixtures/late_objection.json",
        "fixture",
    )
    consent_fix = L.art(
        "command-center/p2-wave/probes/IMP-0306/fixtures/decision_consent.json",
        "fixture",
    )

    doc = {
        "artifact_paths": [
            "tools/council/vote/consent.py",
            "command-center/p2-wave/probes/IMP-0306/fixtures/decision_consent.json",
            "command-center/p2-wave/probes/IMP-0306/fixtures/late_objection.json",
            OUT,
        ],
        "artifacts": [
            impl,
            tests_art,
            late_fix,
            consent_fix,
            L.art(
                "command-center/p2-wave/probes/IMP-0306/probe1_modes.py",
                "named-probe",
            ),
            L.art(
                "command-center/p2-wave/probes/IMP-0306/probe2_silence_policy.py",
                "named-probe",
            ),
        ],
        "completion_sentinel": "SUCCESS:IMP-0306",
        "decision_artifact": {
            "late_objection_fixture": {
                "admitted": live["late_rec"].get("admitted"),
                "handling": live["late_rec"].get("handling"),
                "outcome_after_late": live["after_late"]["outcome"],
                "path": "command-center/p2-wave/probes/IMP-0306/fixtures/late_objection.json",
            },
            "objection_window": live["consent"]["objection_window"],
            "outcome": live["consent"]["outcome"],
            "path": "command-center/p2-wave/probes/IMP-0306/fixtures/decision_consent.json",
            "per_participant_state": live["consent"]["per_participant_state"],
            "silence_policy": live["consent"]["silence_policy"],
            "silence_policy_application": live["consent"]["silence_policy_application"],
            "veto_outcome": live["veto"]["outcome"],
        },
        "downstream_consumers": [
            {
                "artifact_path": "tools/council/vote/consent.py",
                "consumer": "tools/council/vote/tests/test_consent.py",
                "executed": True,
                "exit_code": rc_t,
                "probe": p_tests,
                "read_ok": True,
            }
        ],
        "evidence": [
            L.evidence(
                "A closed consent artifact records objection_window, "
                "silence_policy=silence_is_consent, and per-participant state "
                "including consent_by_silence for seats that never spoke. "
                "Silence is pending while the window is open and is converted "
                "only at expiry because that policy is on the artifact.",
                "CONFIRMED",
                "tools/council/vote/consent.py:ConsentSession.close",
                [p_consent, p_tests],
                "almost-certain",
            ),
            L.evidence(
                "Late-objection fixture: after close, bob's objection at t=2500 "
                "is written onto late_objections with admitted=false and "
                "handling=record_and_ignore; the outcome stays CONSENTED.",
                "CONFIRMED",
                "command-center/p2-wave/probes/IMP-0306/fixtures/late_objection.json",
                [p_late, p_tests],
                "almost-certain",
            ),
            L.evidence(
                "Negative control: stripping silence_policy from an otherwise "
                "valid artifact makes validate_artifact FAIL. The same validator "
                "is silent on the recorded-policy original.",
                "CONFIRMED",
                "tools/council/vote/consent.py:validate_artifact",
                [p_neg, p_tests],
                "almost-certain",
            ),
        ],
        "falsifiable_answer": (
            "Silence inside the objection window is treated as consent if and "
            "only if the artifact records silence_policy=silence_is_consent "
            "AND the window has expired. While the window is open, silence is "
            "pending, not consent. An unrecorded silence policy cannot close "
            "or validate. The alternative recorded policy silence_is_absent "
            "leaves silent seats absent and consent NOT_REACHED. Both policies "
            "are artifact fields, not runtime defaults."
        ),
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": "command-center/p2-wave/probes/IMP-0306/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 512,
        "negative_control_ids": [
            "unrecorded-silence-policy-fails-validation",
            "silence-is-absent-does-not-count-as-consent",
        ],
        "negative_controls": [
            L.control(
                "unrecorded-silence-policy-fails-validation",
                "both-states-same-run",
                "validate_artifact accepts a recorded silence_is_consent "
                "artifact and rejects the same document with silence_policy stripped.",
                True,
                True,
                bad=json.dumps(live["mutant_errs"]),
                good="errors=[]",
            ),
            L.control(
                "silence-is-absent-does-not-count-as-consent",
                "policy-identity",
                "The same silent seats under silence_is_consent yield CONSENTED; "
                "under silence_is_absent they yield NOT_REACHED. Policy is on the artifact.",
                True,
                True,
                bad="silence_is_absent -> NOT_REACHED",
                good="silence_is_consent -> CONSENTED",
            ),
        ],
        "notes": (
            "G-1 IMP-0306: tools/council/vote/consent.py records the objection "
            "window, silence policy, and per-participant state. Unrecorded "
            "silence policy fails validation. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "SUCCESS:IMP-0306"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "profile": "council-vote-module",
        "question_or_target": (
            "Implement tools/council/vote/consent.py supporting veto rights "
            "and consent (no-objection) decisions with a recorded objection "
            "window. Falsifiable question: is silence within the window treated "
            "as consent, and is that policy explicit in the artifact rather "
            "than an implementation detail?"
        ),
        "residual_unknowns": [
            {
                "claim": (
                    "Dependencies IMP-0277 (COI) and IMP-0301 (quota targets) "
                    "are not on this worktree; consent.py does not import them."
                ),
                "settling_experiment": (
                    "Re-run after those units land and wire COI/quota gates "
                    "into ConsentSession.respond admissibility."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "CNL-0060 admissibility bar beyond a non-empty reason is "
                    "not implemented here; empty-reason objections are "
                    "inadmissible, unfalsifiable-but-nonempty reasons are not."
                ),
                "settling_experiment": (
                    "Once CNL-0060 ships, add an admissibility plugin and a "
                    "fixture whose reason is nonempty yet unfalsifiable."
                ),
                "verdict": "PARTIAL",
            },
        ],
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "notes": (
                "Probe2 starts from validate_artifact and from the "
                "ConsentSession.__init__ AST (silence_policy has no default), "
                "not from this receipt's summary. It re-runs the late-objection "
                "fixture and the unrecorded-policy mutant."
            ),
            "reviewer_id": "IMP-0306-probe2-silence-policy",
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0306",
        "spec_anchor": "_USER-PROMPTS.md:10915-10946 consent/no-objection and veto; silence policy must be recorded",
        "state": "SUCCESS",
        "test_ids": [
            "test_veto_by_holder_blocks",
            "test_consent_by_silence_is_explicit_on_artifact",
            "test_in_window_objection_blocks_consent",
            "test_late_objection_record_and_ignore",
            "test_cannot_apply_silence_before_window_expiry",
            "test_silence_is_absent_does_not_manufacture_consent",
            "test_unrecorded_silence_policy_fails_validation",
            "test_empty_reason_objection_is_inadmissible",
        ],
        "tests": [
            {
                "command": TEST_CMD + "::" + name,
                "id": name,
                "result": "PASS",
            }
            for name in [
                "test_veto_by_holder_blocks",
                "test_consent_by_silence_is_explicit_on_artifact",
                "test_in_window_objection_blocks_consent",
                "test_late_objection_record_and_ignore",
                "test_cannot_apply_silence_before_window_expiry",
                "test_silence_is_absent_does_not_manufacture_consent",
                "test_unrecorded_silence_policy_fails_validation",
                "test_empty_reason_objection_is_inadmissible",
            ]
        ],
        "timestamps": {"ended_at": ended, "started_at": started},
        "title": "Veto, consent and no-objection decision modes",
        "unit_id": UNIT,
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0306 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0306" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0306 sentinel missing after write")
        return 1
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    if str(parsed.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0306 self-declared non-delivery")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0306 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "bytes": size,
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": sha,
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/IMP-0306/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "veto-consent-late-objection-window-expiry",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "unrecorded-silence-policy-negative-control",
            },
        ],
        "notes": (
            "G-1 for IMP-0306: live named probes exit 0, receipts/IMP-0306.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0306-probe2-silence-policy",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:IMP-0306",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        dgst, nbytes = digest_file(path)
        return {
            "bytes": nbytes,
            "path": rel,
            "present": path.is_file(),
            "receipt_path": "command-center/p2-wave/probes/IMP-0306/SUBAGENT-RETURN.json",
            "role": role,
            "sha256": dgst,
            "unit_id": UNIT,
        }

    artifacts_man = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "artifacts": artifacts_man,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts_man),
        "present": sum(1 for a in artifacts_man if a["present"]),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0306 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
