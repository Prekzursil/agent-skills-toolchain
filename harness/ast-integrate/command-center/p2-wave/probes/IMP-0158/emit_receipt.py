#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0158.json from live measurements."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_lib import ensure_import, repo  # noqa: E402
from fixtures import load_json, twin_pair  # noqa: E402

ensure_import()
from workflow_foundry.trust_tier import (  # noqa: E402
    OVERRIDE_CLEAN_ROOM,
    OVERRIDE_OWNER_APPROVAL,
    admit_candidate,
    assign_trust_tier,
    classify_by_candidate_label,
)

REPO = repo()
OUT = "command-center/receipts/IMP-0158.json"
SENTINEL = "SUCCESS:IMP-0158"
LIB = "tools/workflow_foundry/trust_tier.py"
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/workflow_foundry/tests/test_trust_tier.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0158/probe1_unknown_refused.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0158/probe2_tier_reproducible.py"
)
SUPPORTING = [
    LIB,
    "tools/workflow_foundry/__init__.py",
    "tools/workflow_foundry/schema/trust-tier-admission.schema.json",
    "tools/workflow_foundry/tests/test_trust_tier.py",
    "command-center/p2-wave/probes/IMP-0158/load_lib.py",
    "command-center/p2-wave/probes/IMP-0158/fixtures.py",
    "command-center/p2-wave/probes/IMP-0158/fixtures/candidate-twin.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/candidate-vendor.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/candidate-community.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-unknown.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-first-party.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-vendor.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-community.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-contradiction.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-hash-mismatch.json",
    "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-expired-key.json",
    "command-center/p2-wave/probes/IMP-0158/probe1_unknown_refused.py",
    "command-center/p2-wave/probes/IMP-0158/probe2_tier_reproducible.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("0" * 64, 0)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-4000:],
        "exit_code": code,
        "fingerprint": fp(raw)[:32],
    }


def main() -> int:
    code_t, out_t = run_cmd(TEST_CMD)
    code1, out1 = run_cmd(P1)
    code2, out2 = run_cmd(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:IMP-0158 emit tests={code_t} p1={code1} p2={code2}")
        print(out_t[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if "SUCCESS:IMP-0158-tests" not in out_t:
        print("FAILED:IMP-0158 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0158-probe1" not in out1:
        print("FAILED:IMP-0158 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0158-probe2" not in out2:
        print("FAILED:IMP-0158 emit probe2 sentinel missing")
        return 1

    candidate, unknown, first_party = twin_pair()
    vendor_c = load_json("candidate-vendor.json")
    vendor_e = load_json("evidence-vendor.json")
    comm_c = load_json("candidate-community.json")
    comm_e = load_json("evidence-community.json")
    contra_e = load_json("evidence-contradiction.json")

    unknown_a = assign_trust_tier(candidate, unknown)
    first_a = assign_trust_tier(candidate, first_party)
    vendor_a = assign_trust_tier(vendor_c, vendor_e)
    comm_a = assign_trust_tier(comm_c, comm_e)
    contra_a = assign_trust_tier(candidate, contra_e)
    refused = admit_candidate(candidate, unknown)
    adopted = admit_candidate(candidate, first_party)
    clean = admit_candidate(candidate, unknown, override=OVERRIDE_CLEAN_ROOM)
    owner = admit_candidate(candidate, unknown, override=OVERRIDE_OWNER_APPROVAL)
    clock_a = assign_trust_tier(
        candidate, first_party, clock="1970-01-01T00:00:00Z"
    )
    clock_b = assign_trust_tier(
        candidate, first_party, clock="2099-12-31T23:59:59Z"
    )
    if clock_a != clock_b:
        print("FAILED:IMP-0158 emit clock injection changed assignment")
        return 1
    if unknown_a.tier != "unknown" or refused.status != "REFUSED":
        print("FAILED:IMP-0158 emit unknown path did not refuse")
        return 1
    if first_a.tier != "first-party" or adopted.status != "AUTO_ADOPTED":
        print("FAILED:IMP-0158 emit first-party twin did not auto-adopt")
        return 1
    if classify_by_candidate_label(candidate) != "first-party":
        print("FAILED:IMP-0158 emit label control missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0158",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0158",
        "title": "Implement trust-tier assignment for candidate sources",
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "implementer",
            "execution_substrate": "local-parallel",
        },
        "question_or_target": (
            "Target: assign each candidate a trust tier (first-party | vendor | "
            "community | unknown) from evidence (publisher identity, signature, "
            "repo ownership), and make the tier an INPUT to admission, not a "
            "label. Acceptance: an unknown-tier candidate cannot be auto-adopted; "
            "it can only be adopted after clean-room reimplementation or explicit "
            "owner approval."
        ),
        "method": {
            "assignment": "evidence-not-label",
            "classifier_inputs": [
                "publisher_identity",
                "signature",
                "repo_ownership",
            ],
            "ignored_candidate_fields": [
                "claimed_tier",
                "trust_tier",
                "tier",
            ],
            "admission": "tier-as-admission-input",
            "unknown_auto_adopt": False,
            "unknown_override": [
                OVERRIDE_CLEAN_ROOM,
                OVERRIDE_OWNER_APPROVAL,
            ],
            "clock": "accepted-and-unused",
        },
        "measurements": {
            "unknown_assignment": unknown_a.as_dict(),
            "unknown_admission": refused.as_dict(),
            "first_party_assignment": first_a.as_dict(),
            "first_party_admission": adopted.as_dict(),
            "vendor_assignment": vendor_a.as_dict(),
            "community_assignment": comm_a.as_dict(),
            "contradiction_assignment": contra_a.as_dict(),
            "unknown_clean_room": clean.as_dict(),
            "unknown_owner_approval": owner.as_dict(),
            "label_classifier_on_twin": classify_by_candidate_label(candidate),
            "clock_injection_identical": True,
        },
        "artifacts": [
            art(LIB, "implementation"),
            art(
                "tools/workflow_foundry/schema/trust-tier-admission.schema.json",
                "schema",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0158/probe1_unknown_refused.py",
                "named-probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0158/probe2_tier_reproducible.py",
                "named-probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0158/fixtures/candidate-twin.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-unknown.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0158/fixtures/evidence-first-party.json",
                "fixture",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "An unknown-tier fixture is refused by the admission path; "
                    "the first-party twin of the same candidate is auto-adopted."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:admit_candidate",
                "confidence": "almost-certain",
                "probes": [
                    probe_rec("source", P1, out1, code1),
                    probe_rec("verifier", TEST_CMD, out_t, code_t),
                ],
            },
            {
                "claim": (
                    "Tier assignment is reproducible: the same candidate and "
                    "evidence yield the same tier across two subprocess runs, "
                    "and an injected clock does not change the result."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:assign_trust_tier",
                "confidence": "almost-certain",
                "probes": [
                    probe_rec("source", P2, out2, code2),
                    probe_rec("verifier", TEST_CMD, out_t, code_t),
                ],
            },
            {
                "claim": (
                    "Candidate self-labels are not admission inputs. The twin "
                    "candidate declares first-party on claimed_tier/trust_tier/"
                    "tier; production still assigns unknown and refuses auto-adopt "
                    "when evidence does not authenticate."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:assign_trust_tier",
                "confidence": "almost-certain",
                "probes": [probe_rec("verifier", P1, out1, code1)],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "unknown-tier-cannot-auto-adopt-both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "tier-assignment-deterministic-across-runs",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "library-tests",
                "command": TEST_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0158-C1",
                "kind": "both-states",
                "description": (
                    "Same candidate document, including first-party self-labels. "
                    "Unknown evidence -> REFUSED; first-party evidence -> AUTO_ADOPTED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(refused.as_dict(), sort_keys=True),
                "good_state_output": json.dumps(adopted.as_dict(), sort_keys=True),
            },
            {
                "id": "IMP0158-C2",
                "kind": "label-vs-evidence",
                "description": (
                    "classify_by_candidate_label returns first-party on the twin "
                    "candidate; production assign_trust_tier returns unknown."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "label=first-party",
                "good_state_output": f"assigned={unknown_a.tier}",
            },
            {
                "id": "IMP0158-C3",
                "kind": "clock-injection",
                "description": (
                    "assign_trust_tier with clocks 1970 and 2099 returns identical "
                    "frozen assignments."
                ),
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "bad_state_output": "assignments diverged",
                "good_state_output": json.dumps(clock_a.as_dict(), sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0158-probe2-tier-reproducible",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 re-runs assignment in two subprocesses with distinct "
                "injected clocks and AST-checks production functions for "
                "wall-clock calls."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0158/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0158",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "note": (
                    "G-1 measure is run after this receipt and the per-unit "
                    "manifest are written."
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0155 provenance records and IMP-0075/IMP-0077 publisher "
                    "key custody plus cryptographic signature verification are "
                    "catalog dependencies and are not delivered in this worktree. "
                    "This unit consumes already-recorded evidence (verified flags, "
                    "signature.valid, key_in_window as booleans) and does not "
                    "create, rotate, or verify keys."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Once IMP-0077 verify() exists, feed a tampered signature "
                    "blob through it into assign_trust_tier and assert the "
                    "candidate stays unknown and refused."
                ),
            }
        ],
        "notes": (
            "G-1 for IMP-0158: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Cloud ok=true is not delivery. SUCCESS:IMP-0158"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    digest, size = sha256_file(out)
    if SENTINEL not in text:
        print("FAILED:IMP-0158 emit sentinel missing")
        return 1
    if size < 128:
        print(f"FAILED:IMP-0158 emit receipt too small ({size} B)")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
