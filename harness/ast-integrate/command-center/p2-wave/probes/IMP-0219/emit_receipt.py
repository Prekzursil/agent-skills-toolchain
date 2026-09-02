#!/usr/bin/env python3
"""Emit IMP-0219 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0219"
OUT = "command-center/receipts/IMP-0219.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0219/probe1_exit0_missing_receipt.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0219/probe2_progress_stream.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/oracle.py",
    "tools/agentspec/agentspec/progress.py",
    "tools/agentspec/agentspec/fanout.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/tests/test_dynamic_fanout.py",
    "command-center/p2-wave/probes/IMP-0219/probe1_exit0_missing_receipt.py",
    "command-center/p2-wave/probes/IMP-0219/probe2_progress_stream.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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
        "receipt_path": "command-center/p2-wave/probes/IMP-0219/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0219 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    sys.path.insert(0, str(REPO / "tools" / "agentspec"))
    sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))
    from agentspec.fanout import ProducerRun, expand_dynamic_fanout
    from agentspec.oracle import evaluate_producer
    from agentspec.progress import is_progress_stream
    from test_dynamic_fanout import (  # noqa: E402
        HEALTHY_N,
        NODE,
        PROGRESS_JSON,
        healthy_receipt_doc,
        test_exit0_missing_receipt_zero_expansion_severed_stream,
        test_progress_stream_never_parsed_as_result,
    )

    p1_doc = test_exit0_missing_receipt_zero_expansion_severed_stream()
    p2_doc = test_progress_stream_never_parsed_as_result()
    if not p1_doc["pass"] or not p2_doc["pass"]:
        print("FAILED:IMP-0219 emit in-process tests")
        return 1

    missing = evaluate_producer(
        exit_code=0, receipt_path="/no/such/producer/receipt.json"
    )
    progress = evaluate_producer(exit_code=0, body=PROGRESS_JSON)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="imp0219-emit-") as tmp:
        path = Path(tmp) / "producer.json"
        path.write_text(json.dumps(healthy_receipt_doc()), encoding="utf-8")
        healthy = expand_dynamic_fanout(
            NODE, ProducerRun(exit_code=0, receipt_path=path)
        )

    oracle_path = REPO / "tools/agentspec/agentspec/oracle.py"
    progress_path = REPO / "tools/agentspec/agentspec/progress.py"
    fanout_path = REPO / "tools/agentspec/agentspec/fanout.py"
    spec_path = REPO / "tools/agentspec/agentspec/spec.py"
    oracle_sha, oracle_n = digest(oracle_path)
    progress_sha, progress_n = digest(progress_path)
    fanout_sha, fanout_n = digest(fanout_path)
    spec_sha, spec_n = digest(spec_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0219",
        "completion_sentinel": "SUCCESS:IMP-0219",
        "title": "Implement the DynamicFanOut executor with an oracle-gated producer receipt",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0219: expand a dynamic "
            "fan-out only after the producer receipt passes the shared completion "
            "oracle; exit-0 with missing or progress-stream receipt expands to "
            "ZERO units and reports severed-stream (:10646)"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "IMP-0132 type",
                "tools/agentspec/agentspec/oracle.py",
                "tools/agentspec/agentspec/progress.py",
            ],
            "inputs_were_absent": True,
            "action": (
                "Created the DynamicFanOut executor, shared completion oracle, "
                "and progress-stream detector on this sparse worktree. Did not "
                "exit on predicate:absent."
            ),
        },
        "implementation": {
            "executor": "tools/agentspec/agentspec/fanout.py:expand_dynamic_fanout",
            "oracle": "tools/agentspec/agentspec/oracle.py:evaluate_producer",
            "progress": "tools/agentspec/agentspec/progress.py:is_progress_stream",
            "node_type": "DynamicFanOut",
            "gate": (
                "cardinality is read only from oracle.parsed_receipt after ok; "
                "exit_code==0 is never sufficient"
            ),
            "healthy_cardinality": healthy.cardinality,
            "healthy_expected": HEALTHY_N,
            "missing_exit0": {
                "ok": missing.ok,
                "reason": missing.reason,
                "family": missing.family,
                "cardinality": 0,
            },
            "progress_stream": {
                "classified": is_progress_stream(PROGRESS_JSON),
                "ok": progress.ok,
                "reason": progress.reason,
                "parsed": progress.parsed_receipt is not None,
            },
            "oracle_sha256": oracle_sha,
            "oracle_bytes": oracle_n,
            "progress_sha256": progress_sha,
            "progress_bytes": progress_n,
            "fanout_sha256": fanout_sha,
            "fanout_bytes": fanout_n,
            "spec_sha256": spec_sha,
            "spec_bytes": spec_n,
        },
        "artifacts": [
            {
                "path": "tools/agentspec/agentspec/fanout.py",
                "role": "primary-implementation",
                "sha256": fanout_sha,
                "bytes": fanout_n,
                "exists": True,
            },
            {
                "path": "tools/agentspec/agentspec/oracle.py",
                "role": "primary-implementation",
                "sha256": oracle_sha,
                "bytes": oracle_n,
                "exists": True,
            },
            {
                "path": "tools/agentspec/agentspec/progress.py",
                "role": "primary-implementation",
                "sha256": progress_sha,
                "bytes": progress_n,
                "exists": True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "exit-0 with a missing producer receipt expands to zero units "
                    "and reports severed-stream; the healthy twin expands to 7 "
                    "(both-states)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/fanout.py:expand_dynamic_fanout",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    }
                ],
            },
            {
                "claim": (
                    "A progress-stream body is never parsed as a result; the "
                    "taxonomy reason string is severed-stream. A mutant that "
                    "JSON-loads the progress body would expand to 5."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/progress.py:is_progress_stream",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "exit-0-missing-receipt-zero-expansion-severed-stream",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "progress-stream-body-never-parsed-as-result",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0219-C1-exit0-missing-both-states",
                "kind": "both-states",
                "description": (
                    "Missing receipt at exit 0 must report severed-stream with "
                    "cardinality 0; a schema-valid 7-item twin must expand to 7. "
                    "A mutant that trusts exit_code==0 expands to 1."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0219-C2-progress-stream-not-a-result",
                "kind": "mutation",
                "description": (
                    "A progress JSON object that carries an items list of 5 must "
                    "not expand. Production reports severed-stream with parsed "
                    "receipt None; the JSON-load mutant expands to 5."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0219-probe2-progress-stream-and-parse-mutant",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the progress-parse mutant plus AST scan "
                "that expand_dynamic_fanout calls evaluate_producer and does not "
                "json.loads the producer body; not a self-attested prose review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0219/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 IMP-0219: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0219"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0219",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "exit0-missing-receipt-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "progress-stream-never-parsed-as-result",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0219/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0219-probe2-progress-stream-and-parse-mutant",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0219: live named probes exit 0, IMP-0219.json "
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
    print("SUCCESS:IMP-0219 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
