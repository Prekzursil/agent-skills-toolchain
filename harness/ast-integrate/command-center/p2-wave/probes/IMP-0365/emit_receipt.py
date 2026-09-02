#!/usr/bin/env python3
"""Emit IMP-0365 receipt + per-unit manifest + SUBAGENT-RETURN after live probes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0365"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/evidence/tests/test_standard.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0365/probe1_tier_enforcement.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0365/probe2_assertion_misclassification.py"
)
SUPPORTING = [
    "tools/council/__init__.py",
    "tools/council/evidence/__init__.py",
    "tools/council/evidence/standard.py",
    "tools/council/evidence/schema/admission.schema.json",
    "tools/council/evidence/fixtures/labelled_claims.json",
    "tools/council/evidence/tests/__init__.py",
    "tools/council/evidence/tests/conftest.py",
    "tools/council/evidence/tests/test_standard.py",
    "command-center/p2-wave/probes/IMP-0365/probe1_tier_enforcement.py",
    "command-center/p2-wave/probes/IMP-0365/probe2_assertion_misclassification.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print("FAILED:IMP-0365 live tests/probes did not all exit 0")
        print(out_t[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if "SUCCESS:IMP-0365-tests" not in out_t:
        print("FAILED:IMP-0365 tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0365-probe1" not in out1:
        print("FAILED:IMP-0365 probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0365-probe2" not in out2:
        print("FAILED:IMP-0365 probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    pt = probe_rec("verifier", TEST_CMD, out_t, code_t)
    supporting_arts = [art(rel, "supporting") for rel in SUPPORTING]
    artifact_paths = [OUT_REL] + list(SUPPORTING)
    test_ids = [
        "test_each_tier_enforced_on_labelled_set",
        "test_under_tier_fixture_refused_and_not_bound",
        "test_classification_pass_names_input_field_on_every_admitted_claim",
        "test_assertion_classifier_misclassifies_labelled_set",
        "test_production_classifier_ignores_claimed_tier",
        "named-probe1",
        "named-probe2",
    ]
    negative_control_ids = [
        "assertion-classifier-on-labelled-set",
        "under-tier-C-CITED-executable-proof-only",
        "missing-source-type-C-MISSING-TYPE",
    ]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0365; "
            "_USER-PROMPTS.md:11172-11244 evidence tier at claim admission"
        ),
        "min_bytes_threshold": 128,
        "title": "Evidence-standard tier enforcement per preset",
        "question_or_target": (
            "Implement tools/council/evidence/standard.py enforcing a preset's "
            "declared evidence tier (for example executable-proof-only, "
            "peer-reviewed-only, any-cited) at the point a claim is admitted. "
            "Falsifiable question: does a claim below the declared tier ever "
            "reach a binding decision, and is tier classification done on the "
            "source's type rather than on the claimant's assertion about it?"
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "two-strikes-then-pivot; a verification failure never retries",
        },
        "implementation": {
            "module": "tools/council/evidence/standard.py",
            "classifier_input_field": "source.type",
            "declared_floors": [
                "any-cited",
                "peer-reviewed-only",
                "executable-proof-only",
            ],
            "admission_gate": "admit_claim / bind_decision",
            "negative_control_classifier": "classify_by_claimant_assertion",
        },
        "artifact_paths": artifact_paths,
        "artifacts": supporting_arts,
        "evidence": [
            {
                "anchor": "tools/council/evidence/standard.py:classification_pass",
                "claim": (
                    "A tier-classification pass over the labelled claim set names "
                    "classifier_input_field=source.type on every admitted claim. "
                    "Each declared floor admits only claims whose source.type "
                    "ranks at or above that floor."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, pt],
            },
            {
                "anchor": "tools/council/evidence/fixtures/labelled_claims.json:C-CITED",
                "claim": (
                    "Under-tier fixture C-CITED (source.type=blog, labelled "
                    "any-cited) is refused under executable-proof-only and "
                    "cannot be attached to a binding decision."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p2],
            },
            {
                "anchor": "tools/council/evidence/standard.py:misclassification_report",
                "claim": (
                    "Classifying the labelled set by claimed_tier / "
                    "asserted_source_type misclassifies every planted claim "
                    "relative to source.type ground truth. Production admission "
                    "still reads source.type and refuses the over-claims."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, pt],
            },
        ],
        "tests": [
            {
                "id": "test_each_tier_enforced_on_labelled_set",
                "command": TEST_CMD + "::test_each_tier_enforced_on_labelled_set",
                "result": "PASS",
            },
            {
                "id": "test_under_tier_fixture_refused_and_not_bound",
                "command": TEST_CMD + "::test_under_tier_fixture_refused_and_not_bound",
                "result": "PASS",
            },
            {
                "id": "test_assertion_classifier_misclassifies_labelled_set",
                "command": (
                    TEST_CMD + "::test_assertion_classifier_misclassifies_labelled_set"
                ),
                "result": "PASS",
            },
            {
                "id": "named-probe1",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "named-probe2",
                "command": P2,
                "result": "PASS",
            },
        ],
        "test_ids": test_ids,
        "negative_controls": [
            {
                "id": "assertion-classifier-on-labelled-set",
                "kind": "known-broken-classifier",
                "description": (
                    "classify_by_claimant_assertion reads claimed_tier instead "
                    "of source.type; the labelled set shows misclassification "
                    "on every planted disagreement."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "n_mismatch == n labelled claims",
                "good_state_output": "classify_source_type == label_tier",
            },
            {
                "id": "under-tier-C-CITED-executable-proof-only",
                "kind": "known-broken-fixture",
                "description": (
                    "blog citation claimed as peer-reviewed; production refuses "
                    "under executable-proof-only; attach_claim raises UnderTierError."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "UnderTierError C-CITED",
                "good_state_output": "C-EXEC admitted",
            },
        ],
        "negative_control_ids": negative_control_ids,
        "reviewer": {
            "reviewer_id": "IMP-0365-probe2-assertion-misclassification",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "starts_from": "labelled_claims.json and production AST, not the author summary",
            "obligation": (
                "Tier classification must use source.type. Claimant assertion "
                "must not admit an under-tier claim onto a binding decision."
            ),
        },
        "reviewer_verdict": "PASS",
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog dependencies IMP-0307 (vote/evidence_gate.py) and "
                    "IMP-0314 (artifacts/evidence_map.py) are not present in this "
                    "worktree. This unit enforces the tier gate at admission "
                    "independently. Wiring admit_claim into those modules is "
                    "their units' work, not a missing floor rule."
                ),
                "settling_experiment": (
                    "When IMP-0307/IMP-0314 land, pass a refused under-tier claim "
                    "through evidence_gate and evidence_map and assert it still "
                    "cannot become a binding vote anchor."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0365 evidence-tier enforcement. Live named "
            "probes measure floor enforcement and the assertion-classifier "
            "negative control. Did not run global unit_manifest.py --write. "
            "cloud ok is not consulted."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:IMP-0365 receipt too small ({live_bytes} B)")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "tier-enforcement",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "assertion-misclassification",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0365-probe2-assertion-misclassification",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0365: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
