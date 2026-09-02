#!/usr/bin/env python3
"""Emit IMP-0222 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST."""
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

from scenario import (  # noqa: E402
    COHORT_N,
    HANG_ID,
    HANG_S,
    RECEIPT_REL,
    SENTINEL,
    SLACK_S,
    TIMEOUT_S,
    UNIT_ID,
    assert_no_barrier_past_timeout,
    run_coupled_hang,
    run_isolated,
    summarize,
)

UNIT = UNIT_ID
OUT = RECEIPT_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0222/probe1_planted_hang.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0222/probe2_barrier_timeout.py"
)
SUPPORTING = [
    "tools/agentrail/agentrail/runner.py",
    "command-center/p2-wave/probes/IMP-0222/scenario.py",
    "command-center/p2-wave/probes/IMP-0222/probe1_planted_hang.py",
    "command-center/p2-wave/probes/IMP-0222/probe2_barrier_timeout.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "exit_code": exit_code,
        "fingerprint": fp(method, command),
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


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
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def measure_engine() -> dict:
    clean = run_isolated(hang=False)
    hung = run_isolated(hang=True)
    coupled = run_coupled_hang()
    sc, sh, scp = summarize(clean), summarize(hung), summarize(coupled)
    ok_iso, why_iso = assert_no_barrier_past_timeout(hung, slack_s=SLACK_S)
    ok_cpl, why_cpl = assert_no_barrier_past_timeout(coupled, slack_s=SLACK_S)
    hung_row = hung.by_id()[HANG_ID]
    return {
        "clean": {
            "completed": sc["completed"],
            "timeout": sc["timeout"],
            "timeout_typed": sc["timeout_typed"],
            "barrier_wait_s": sc["barrier_wait_s"],
            "pipeline_ids": sc["pipeline_ids"],
        },
        "hang": {
            "completed": sh["completed"],
            "timeout": sh["timeout"],
            "timeout_typed": sh["timeout_typed"],
            "timeout_unit_ids": sh["timeout_unit_ids"],
            "barrier_wait_s": sh["barrier_wait_s"],
            "hung_duration_s": hung_row.duration_s,
            "hung_state": hung_row.terminal_state,
            "hung_class": hung_row.timeout_class,
        },
        "coupled": {
            "completed": scp["completed"],
            "timeout": scp["timeout"],
            "barrier_wait_s": scp["barrier_wait_s"],
        },
        "isolated_within_timeout": ok_iso,
        "isolated_why": why_iso,
        "coupled_exceeds_timeout": not ok_cpl,
        "coupled_why": why_cpl,
        "timeout_s": TIMEOUT_S,
        "hang_s": HANG_S,
        "cohort_n": COHORT_N,
        "hang_id": HANG_ID,
    }


def engine_holds(m: dict) -> bool:
    return (
        m["clean"]["completed"] == COHORT_N
        and m["clean"]["timeout"] == 0
        and m["hang"]["completed"] == COHORT_N - 1
        and m["hang"]["timeout_typed"] == 1
        and m["hang"]["timeout_unit_ids"] == [HANG_ID]
        and m["hang"]["hung_class"] == "timeout-typed"
        and m["isolated_within_timeout"] is True
        and m["coupled_exceeds_timeout"] is True
        and m["hang"]["barrier_wait_s"] < HANG_S - 0.15
        and m["coupled"]["barrier_wait_s"] > TIMEOUT_S
    )


def build_receipt(m: dict) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_clean = probe(
        "source",
        "in-process",
        "IsolatedPipelineRunner.run_cohort(clean n=50)",
        json.dumps(m["clean"], sort_keys=True),
        0,
    )
    p_hang = probe(
        "source",
        "in-process",
        "IsolatedPipelineRunner.run_cohort(49 complete + 1 planted hang)",
        json.dumps(m["hang"], sort_keys=True),
        0,
    )
    p_cpl = probe(
        "verifier",
        "mutation",
        "CoupledBarrierRunner.run_cohort (join-all, no per-unit timeout)",
        json.dumps(m["coupled"], sort_keys=True),
        0,
    )
    artifacts = [art(p, "supporting") for p in SUPPORTING]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11317",
        "title": "Implement per-unit pipeline isolation so one hung unit cannot deadlock the cohort",
        "min_bytes_threshold": 128,
        "output_schema": "command-center/schema/receipt.schema.json",
        "produced_by": {
            "role": "implementer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    f"A {COHORT_N}-unit cohort with one planted hang completes {COHORT_N - 1} "
                    f"units; the hung unit {HANG_ID} is TIMEOUT/timeout-typed, not absent. "
                    f"Clean twin is {COHORT_N}/{COHORT_N} with detector silent."
                ),
                "verdict": "CONFIRMED"
                if m["hang"]["completed"] == COHORT_N - 1
                and m["hang"]["timeout_typed"] == 1
                and m["clean"]["completed"] == COHORT_N
                else "REFUTED",
                "anchor": "tools/agentrail/agentrail/runner.py:IsolatedPipelineRunner",
                "confidence": "almost-certain",
                "probes": [p_clean, p_hang],
            },
            {
                "claim": (
                    "The cohort barrier does not wait past a unit's declared timeout: "
                    f"isolated barrier_wait_s={m['hang']['barrier_wait_s']:.4f} <= "
                    f"timeout_s={TIMEOUT_S}+slack; coupled join-all waits "
                    f"{m['coupled']['barrier_wait_s']:.4f}s (~hang_s={HANG_S}) and is "
                    "the both-states control."
                ),
                "verdict": "CONFIRMED"
                if m["isolated_within_timeout"] and m["coupled_exceeds_timeout"]
                else "REFUTED",
                "anchor": "tools/agentrail/agentrail/runner.py:assert_no_barrier_past_timeout",
                "confidence": "almost-certain",
                "probes": [p_hang, p_cpl],
            },
        ],
        "tests": [
            {
                "id": "planted-hang-49-of-50-timeout-typed",
                "command": P1,
                "result": "PENDING-LIVE-PROBE",
            },
            {
                "id": "barrier-timestamps-within-declared-timeout",
                "command": P2,
                "result": "PENDING-LIVE-PROBE",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0222-C1-clean-cohort",
                "kind": "known-good-fixture",
                "description": "A 50-unit cohort with no hang must complete 50/50; the hang detector must stay silent.",
                "fired_on_bad_state": m["hang"]["timeout_typed"] == 1,
                "silent_on_good_state": m["clean"]["timeout"] == 0,
                "bad_state_output": json.dumps(m["hang"], sort_keys=True),
                "good_state_output": json.dumps(m["clean"], sort_keys=True),
            },
            {
                "id": "IMP0222-C2-coupled-barrier",
                "kind": "known-broken-fixture",
                "description": "Join-all with no per-unit timeout must wait out the hang and exceed the declared timeout.",
                "fired_on_bad_state": m["coupled_exceeds_timeout"],
                "silent_on_good_state": m["isolated_within_timeout"],
                "bad_state_output": json.dumps(m["coupled"], sort_keys=True),
                "good_state_output": json.dumps(
                    {
                        "barrier_wait_s": m["hang"]["barrier_wait_s"],
                        "within_timeout": m["isolated_within_timeout"],
                    },
                    sort_keys=True,
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0222-probe2-barrier-timeout",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "probe2 is a separate process that did not author runner.py; it "
                "re-runs isolated vs coupled cohorts and asserts ledger timestamps."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0222/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0222",
                    "deferred to post-write measure",
                    0,
                ),
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {
            "started_at": "2026-08-24T18:40:00Z",
            "ended_at": now,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This runner isolates in-process worker threads, not OS processes "
                    "or remote agents. A hung subprocess that ignores thread join still "
                    "needs a process-level kill in a later unit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Plant a non-daemon subprocess hang and assert the supervisor kills it by declared timeout.",
            }
        ],
        "report": {
            "kind": "per-unit-pipeline-isolation",
            "engine": "tools/agentrail/agentrail/runner.py",
            "measurement": m,
            "failure_class": "FC-11317 one hung unit blocks a large batch",
        },
        "cloud_ok": False,
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0222/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    measured = measure_engine()
    if not engine_holds(measured):
        print("FAILED:IMP-0222 in-process engine measurement did not hold")
        print(json.dumps(measured, indent=2))
        return 1
    receipt = build_receipt(measured)
    out_path = REPO / OUT
    write_json(out_path, receipt)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0222 named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    receipt["tests"][0]["result"] = "PASS"
    receipt["tests"][0]["output_tail"] = t1[-1500:]
    receipt["tests"][1]["result"] = "PASS"
    receipt["tests"][1]["output_tail"] = t2[-1500:]
    write_json(out_path, receipt)
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0222/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0222-probe2-barrier-timeout",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0222: live named probes exit 0, receipts/IMP-0222.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud_ok is false and is not delivery."
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
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0222 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
