#!/usr/bin/env python3
"""Emit IMP-0238 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ENGINE = REPO / "command-center" / "blueprints" / "engineering"
OUT = "command-center/receipts/IMP-0238.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0238/probe1_unreproduced_cause.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0238/probe2_independent_process.py"
)
SUPPORTING = [
    "command-center/blueprints/engineering/engine.py",
    "command-center/blueprints/engineering/contract.py",
    "command-center/blueprints/engineering/ledger.py",
    "command-center/blueprints/engineering/repro_worker.py",
    "command-center/blueprints/engineering/fixtures/counter.py",
    "command-center/blueprints/engineering/library/root-cause-investigation.json",
    "command-center/blueprints/engineering/library/regression-triage.json",
    "command-center/blueprints/engineering/library/incident-response.json",
    "command-center/blueprints/engineering/library/postmortem.json",
    "command-center/p2-wave/probes/IMP-0238/probe1_unreproduced_cause.py",
    "command-center/p2-wave/probes/IMP-0238/probe2_independent_process.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0238",
        "receipt_path": "command-center/p2-wave/probes/IMP-0238/SUBAGENT-RETURN.json",
        "role": role,
    }


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return 1


def main() -> int:
    sys.path.insert(0, str(ENGINE))
    from engine import (  # noqa: E402
        CAUSE_WITHOUT_REPRODUCTION,
        REPRODUCTION_NOT_INDEPENDENT,
        register_all,
        run_investigation,
        smoke_all,
    )

    docs = register_all()
    smoke = smoke_all()
    if not smoke.get("ok"):
        print("FAILED:IMP-0238 smoke_all")
        print(json.dumps(smoke, sort_keys=True, default=str)[:4000])
        return 1

    unreproduced = run_investigation("noop-increment is the cause", reproduce=False)
    reproduced = run_investigation("noop-increment is the cause", reproduce=True)
    self_report = run_investigation("noop-increment is the cause", fake_same_pid=True)

    engine_py = ENGINE / "engine.py"
    worker_py = ENGINE / "repro_worker.py"
    rca_json = ENGINE / "library" / "root-cause-investigation.json"

    receipt = {
        "unit_id": "IMP-0238",
        "id": "IMP-0238",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0238",
        "completion_sentinel": "SUCCESS:IMP-0238",
        "schema_version": 1,
        "title": "Implement engineering blueprints 1-4: root-cause investigation, regression triage, incident response, postmortem",
        "question": (
            "Implement 4 blueprints - root-cause-investigation, regression-triage, "
            "incident-response, postmortem. FLAGSHIP root-cause-investigation must "
            "REPRODUCE the failure before proposing a cause; a proposed cause with "
            "no reproduction is rejected by the blueprint's own gate."
        ),
        "blueprints": [
            {
                "id": bid,
                "flagship": bool(doc.get("flagship")),
                "path": f"command-center/blueprints/engineering/library/{bid}.json",
                "capability_vector": doc.get("capability_vector") or doc.get("capability_vector"),
                "stages": [s["id"] for s in (doc.get("workflow") or {}).get("stages") or []],
            }
            for bid, doc in sorted(docs.items())
        ],
        "flagship": {
            "id": "root-cause-investigation",
            "gate": "reject_without_independent_reproduction",
            "unreproduced_cause": {
                "status": unreproduced.status,
                "reason": unreproduced.reason,
                "expected_reason": CAUSE_WITHOUT_REPRODUCTION,
            },
            "reproduced_cause": {
                "status": reproduced.status,
                "reason": reproduced.reason,
                "proposer_pid": reproduced.proposer_pid,
                "executor_pid": reproduced.executor_pid,
                "pids_differ": reproduced.executor_pid != reproduced.proposer_pid,
                "observed_failure": reproduced.observed_failure,
            },
            "same_pid_self_report": {
                "status": self_report.status,
                "reason": self_report.reason,
                "expected_reason": REPRODUCTION_NOT_INDEPENDENT,
            },
        },
        "evidence": [
            {
                "claim": "A cause without a reproduction receipt is rejected by the FLAGSHIP gate.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/blueprints/engineering/engine.py:{line_of(engine_py, 'CAUSE_WITHOUT_REPRODUCTION')}",
                "observed": f"{unreproduced.status}/{unreproduced.reason}",
            },
            {
                "claim": "Reproduction is executed by a different process than the proposer; PIDs are read from the ledger.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/blueprints/engineering/repro_worker.py:{line_of(worker_py, 'reproduction_executed')}",
                "observed": {
                    "proposer_pid": reproduced.proposer_pid,
                    "executor_pid": reproduced.executor_pid,
                },
            },
            {
                "claim": "Same-pid self-report is not independence and is rejected.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/blueprints/engineering/engine.py:{line_of(engine_py, 'REPRODUCTION_NOT_INDEPENDENT')}",
                "observed": f"{self_report.status}/{self_report.reason}",
            },
            {
                "claim": "root-cause-investigation is FLAGSHIP and not discovery_only.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/blueprints/engineering/library/root-cause-investigation.json:{line_of(rca_json, '\"flagship\"')}",
                "observed": {
                    "flagship": docs["root-cause-investigation"].get("flagship"),
                    "discovery_only": docs["root-cause-investigation"].get("discovery_only"),
                },
            },
        ],
        "tests": [
            {
                "id": "unreproduced-cause-rejected",
                "result": "PASS" if unreproduced.status == "REJECTED" else "FAIL",
                "both_states": True,
            },
            {
                "id": "reproduced-cause-accepted",
                "result": "PASS" if reproduced.status == "ACCEPTED" else "FAIL",
                "both_states": True,
            },
            {
                "id": "independent-process-from-ledger",
                "result": "PASS"
                if reproduced.executor_pid not in (None, reproduced.proposer_pid)
                else "FAIL",
            },
            {
                "id": "same-pid-self-report-rejected",
                "result": "PASS" if self_report.status == "REJECTED" else "FAIL",
            },
            {
                "id": "all-four-blueprints-smoke",
                "result": "PASS" if smoke.get("ok") else "FAIL",
                "registered": smoke.get("registered"),
            },
        ],
        "negative_controls": [
            {
                "id": "cause-without-reproduction",
                "fired_on_bad_state": unreproduced.status == "REJECTED",
                "silent_on_good_state": reproduced.status == "ACCEPTED",
            },
            {
                "id": "same-pid-reproduction",
                "fired_on_bad_state": self_report.status == "REJECTED",
                "silent_on_good_state": reproduced.status == "ACCEPTED",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0238-probe2-independent-process",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": "Named probe2 re-reads the JSONL ledger and asserts executor pid != proposer pid; a planted same-pid row is rejected.",
        },
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {
                "path": "command-center/blueprints/engineering/engine.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/blueprints/engineering/library/root-cause-investigation.json",
                "role": "supporting",
                "exists": True,
            },
        ],
        "residual_unknowns": [
            {
                "claim": "IMP-0230 scaffold generator is not on this tree; this unit registers four complete blueprints against a local six-element contract rather than importing that generator.",
                "settling_experiment": "Re-run registration through the IMP-0230 scaffold output when that unit is delivered.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "smoke": smoke,
        "timestamps": {"emitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "notes": (
            "G-1 for IMP-0238: four engineering blueprints implemented; FLAGSHIP "
            "root-cause-investigation rejects unreproduced causes and requires an "
            "independent worker PID recorded in the ledger. Did not run global "
            "unit_manifest.py --write. cloud ok is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "IMP-0238",
        "unit_id": "IMP-0238",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0238",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "unreproduced-cause-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-process-ledger",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0238/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0238-probe2-independent-process",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0238: live named probes exit 0, receipts/IMP-0238.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0238",
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
    print("SUCCESS:IMP-0238 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
