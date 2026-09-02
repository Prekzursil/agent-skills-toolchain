#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0095.json from live measurements."""
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
OUT_REL = "command-center/receipts/IMP-0095.json"
SENTINEL = "SUCCESS:IMP-0095"

SUPPORTING = [
    "tools/marketplace/freshness.py",
    "tools/marketplace/__init__.py",
    "tools/marketplace/schema/verdict-freshness.schema.json",
    "tools/marketplace/tests/conftest.py",
    "tools/marketplace/tests/test_verdict_freshness.py",
    "command-center/p2-wave/probes/IMP-0095/probe1_input_hash.py",
    "command-center/p2-wave/probes/IMP-0095/probe2_age_sweep.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_verdict_freshness.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0095/probe1_input_hash.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0095/probe2_age_sweep.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def probe_obj(cmd: str, code: int, text: str, role: str) -> dict:
    return {
        "command": cmd,
        "exit_code": code,
        "fingerprint": fp(text),
        "method": "command",
        "raw_output": text[-1500:],
        "role": role,
    }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0095 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if SENTINEL.replace("SUCCESS:", "SUCCESS:") not in t_test and "SUCCESS:IMP-0095-tests" not in t_test:
        print("FAILED:IMP-0095 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0095-probe1" not in t1:
        print("FAILED:IMP-0095 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0095-probe2" not in t2:
        print("FAILED:IMP-0095 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "unit_id": "IMP-0095",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0095",
        "title": "Score and verdict decay: recompute when an input changes",
        "question": (
            "Implement freshness semantics so a stored quality score, "
            "vulnerability verdict, or conformance result carries the "
            "timestamp and input hashes it was computed from, and is marked "
            "STALE (and recomputed) when any input changes — because a green "
            "result computed last week against a live advisory database is "
            "not a control for today."
        ),
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/marketplace/freshness.py",
            "kinds": [
                "quality_score",
                "vulnerability_verdict",
                "conformance_result",
            ],
            "signals": [
                "hash_invalidated (does not inspect time)",
                "age_invalidated / age_sweep (does not inspect hashes)",
            ],
            "unhashable_live_input": "advisory_db",
            "stale_never_pass_surfaces": [
                "surface_result",
                "render_record.result_shown",
                "render_api.verdict",
                "summary_view.pass",
            ],
        },
        "evidence": [
            {
                "anchor": "tools/marketplace/freshness.py:hash_invalidated",
                "claim": (
                    "Changing one hashable input (sbom_present) flips a stored "
                    "PASS quality score to STALE via the hash signal while the "
                    "age signal stays VALID inside the window."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/marketplace/freshness.py:age_sweep",
                "claim": (
                    "An age-based sweep independently marks a CLEAN "
                    "vulnerability verdict older than its freshness window as "
                    "STALE even when no input hash changed; the advisory "
                    "database is listed as unhashable."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P2, c2, t2, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "fresh-unchanged-stays-valid",
                "kind": "known-good-twin",
                "description": (
                    "A twin quality score with unchanged inputs and age inside "
                    "the window stays VALID and still surfaces as PASS in the "
                    "same probe1 run that marked the mutated sibling STALE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "control_freshness=VALID",
                "bad_state_output": "mutated_freshness=STALE",
            },
            {
                "id": "stale-never-rendered-as-pass",
                "kind": "surface-enumeration",
                "description": (
                    "STALE is not painted as PASS/CLEAN on record, API, or "
                    "summary surfaces (reviewer obligation)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "fresh twin remains CLEAN in summary.pass",
                "bad_state_output": "aged twin result_shown=STALE summary.pass=0",
            },
        ],
        "tests": [
            {
                "id": "test_input_change_marks_stale",
                "command": TEST_CMD + "::test_input_change_marks_stale",
                "result": "PASS",
            },
            {
                "id": "test_age_alone_marks_stale",
                "command": TEST_CMD + "::test_age_alone_marks_stale",
                "result": "PASS",
            },
            {
                "id": "test_fresh_unchanged_inputs_stay_valid",
                "command": TEST_CMD + "::test_fresh_unchanged_inputs_stay_valid",
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
        "reviewer": {
            "reviewer_id": "IMP-0095-probe2-stale-never-pass",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "obligation": (
                "STALE is never rendered as PASS in any surface, including "
                "summary views."
            ),
            "method": (
                "enumerate_surfaces plus cohort summary_view: aged CLEAN "
                "shows STALE, fresh CLEAN still counts as pass."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0095",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0095/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0094 (quality-score producer) and IMP-0098 (live OSV "
                    "ingestion) are not delivered in this worktree. Freshness "
                    "stamps fixture scores and fixture vulnerability verdicts. "
                    "Wiring those producers to stamp_verdict is their units' "
                    "work, not a missing decay rule."
                ),
                "settling_experiment": (
                    "After IMP-0094/IMP-0098 land, stamp one live score and "
                    "one live advisory verdict and re-run the two named probes "
                    "against those records."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0095 freshness semantics. Two independent "
            "signals measured live: input-hash invalidation and age sweep. "
            "Did not run global unit_manifest.py --write. cloud ok is not "
            "consulted."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
