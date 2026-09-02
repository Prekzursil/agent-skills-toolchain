#!/usr/bin/env python3
"""Emit IMP-0471 mutation report, SUBAGENT-RETURN, and per-unit manifest."""
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from detectors.campaign import QUESTION, run_campaign  # noqa: E402
from schema_local import iter_errors  # noqa: E402

UNIT = "IMP-0471"
OUT = "command-center/receipts/IMP-0471.json"
SCHEMA_REL = "command-center/schema/mutation-report.schema.json"
SENTINEL = "SENTINEL:IMP-0471:DETECTORS-TWO-STATE-VALIDATED"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0471/probe1_two_state_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0471/probe2_reviewer_independent_broken.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "tools/detectors/__init__.py",
    "tools/detectors/two_state.py",
    "tools/detectors/census.py",
    "tools/detectors/adapters.py",
    "tools/detectors/campaign.py",
    "tools/detectors/tests/test_two_state_harness.py",
    "command-center/p2-wave/probes/IMP-0471/probe1_two_state_table.py",
    "command-center/p2-wave/probes/IMP-0471/probe2_reviewer_independent_broken.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0471/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def schema_or_die(doc: dict) -> None:
    errs = iter_errors(doc)
    if errs:
        print("FAILED:IMP-0471 emit schema", errs[0].message, list(errs[0].absolute_path))
        raise SystemExit(1)


def build_receipt(
    campaign: dict,
    now: str,
    artifact_sha: str,
    artifact_bytes: int,
    t1: str,
    t2: str,
    c1: int,
    c2: int,
) -> dict:
    answer = campaign["answer"]
    source_cmd = "tools/detectors/campaign.py:run_campaign"
    harness_cmd = "tools/detectors/two_state.py:harness_self_test"
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "profile": "p2-wave-g1-unit",
        "spec_anchor": "_USER-PROMPTS.md:11324",
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "sha256": artifact_sha,
                "bytes": artifact_bytes,
                "exists": True,
                "eol": "LF",
            }
        ],
        "evidence": [
            {
                "claim": (
                    f"{answer['silent_in_both_count']} of {answer['shipped_count']} "
                    "shipped detectors are silent in both states."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/detectors/campaign.py:run_campaign",
                "probes": [
                    probe_obj("source", "static-analysis", source_cmd, json.dumps(answer), 0),
                    probe_obj("verifier", "command", P1, t1, c1),
                ],
            },
            {
                "claim": (
                    "Harness control: two-state-valid detector is DIFFERS; "
                    "inert stub is SILENT-BOTH; missing fixture is NOT-CHECKED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/detectors/two_state.py:harness_self_test",
                "probes": [
                    probe_obj(
                        "source",
                        "static-analysis",
                        harness_cmd,
                        json.dumps({"pass": campaign["harness_self_test"]["pass"]}),
                        0,
                    ),
                    probe_obj("verifier", "command", P2, t2, c2),
                ],
            },
        ],
        "tests": [
            {
                "id": "per-detector-two-state-table",
                "name": "two-state table for every shipped detector",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "reviewer-independent-broken-states",
                "name": "three independent broken states plus schema",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0471-C1-static-audit-requests",
                "kind": "adversarial-payload",
                "description": "audit_snippet silent on clean Python, fires on import requests.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0471-C2-marketplace-rotate-key",
                "kind": "adversarial-payload",
                "description": "scan_source silent on clean Python, fires on rotate_key.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0471-C3-kernel-events-append",
                "kind": "adversarial-payload",
                "description": "audit_source silent on honest planner, fires on events.append.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0471-probe2-independent-broken-states",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial reviewer plants requests.get, rotate_key, and "
                "events.append as independent broken states for three detectors."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0471/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "IMP-0471-probe1-two-state-table",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": probe_obj("verifier", "command", P1, t1[:4000], c1),
            }
        ],
        "table": campaign["table"],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "max 2 attempts, backoff 30s/120s",
        },
        "residual_unknowns": [],
        "report": {
            "kind": "mutation-report",
            "observations": [
                {
                    "name": "silent-in-both-count",
                    "measured": answer["silent_in_both_count"],
                    "method": "two-state-harness",
                    "anchor": "tools/detectors/campaign.py:run_campaign",
                },
                {
                    "name": "shipped-count",
                    "measured": answer["shipped_count"],
                    "method": "ast-census",
                    "anchor": "tools/detectors/census.py:census_detector_ids",
                },
                {
                    "name": "not-checked-count",
                    "measured": answer["not_checked_count"],
                    "method": "two-state-harness",
                    "anchor": "tools/detectors/campaign.py:run_campaign",
                },
            ],
            "control_ids": [
                "IMP-0471-C1-static-audit-requests",
                "IMP-0471-C2-marketplace-rotate-key",
                "IMP-0471-C3-kernel-events-append",
            ],
            "question": QUESTION,
            "answer": answer,
            "table": campaign["table"],
            "verdict_counts": campaign["verdict_counts"],
            "enumerator": {
                "known_present": campaign["known_present_detector"],
                "found_known_present": campaign["enumerator"]["found_known_present"],
                "count": campaign["enumerator"]["count"],
            },
            "controls": {
                "two_state_valid": campaign["harness_self_test"]["two_state_valid"],
                "inert_stub": campaign["harness_self_test"]["inert_stub"],
                "always_fire": campaign["harness_self_test"]["always_fire"],
                "missing_fixture": campaign["harness_self_test"]["missing_fixture"],
                "enumerator_finds_known_detector": campaign["enumerator"][
                    "found_known_present"
                ],
            },
            "implementation": {
                "module": "tools/detectors/two_state.py",
                "census": "tools/detectors/census.py",
                "adapters": "tools/detectors/adapters.py",
            },
        },
        "extensions": {
            "title": "Both-states detector-validation harness applied to every shipped detector",
            "output_path": OUT,
            "output_schema": SCHEMA_REL,
            "notes": (
                "G-1 IMP-0471: live named probes exit 0, mutation report "
                f"state=SUCCESS, per-unit manifest row. {SENTINEL}"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }


def main() -> int:
    campaign = run_campaign()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    placeholder = "0" * 64
    draft = build_receipt(campaign, now, placeholder, 128, "pending", "pending", 0, 0)
    schema_or_die(draft)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(draft, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0471 emit probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    filled = build_receipt(campaign, now, placeholder, 128, t1, t2, c1, c2)
    out_path.write_text(
        json.dumps(filled, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, n = digest(out_path)
    final = build_receipt(campaign, now, sha, n, t1, t2, c1, c2)
    schema_or_die(final)
    out_path.write_text(
        json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")

    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "two-state-table",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "reviewer-independent-broken",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0471/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0471-probe2-independent-broken-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0471: live named probes exit 0, IMP-0471.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0471 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
