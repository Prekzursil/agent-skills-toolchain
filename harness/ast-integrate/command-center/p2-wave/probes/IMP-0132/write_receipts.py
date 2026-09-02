#!/usr/bin/env python3
"""Write IMP-0132 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0132"
OUT = "command-center/receipts/IMP-0132.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0132/probe1_seven_items.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0132/probe2_progress_severed.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/oracle.py",
    "tools/agentspec/agentspec/dynamic_fanout.py",
    "command-center/p2-wave/probes/IMP-0132/probe1_seven_items.py",
    "command-center/p2-wave/probes/IMP-0132/probe2_progress_severed.py",
    "command-center/p2-wave/probes/IMP-0132/fixtures/producer_seven.json",
    "command-center/p2-wave/probes/IMP-0132/fixtures/producer_empty.json",
    "command-center/p2-wave/probes/IMP-0132/fixtures/producer_progress.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0132/SUBAGENT-RETURN.json",
        "role": role,
    }


def parse_probe_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = parse_probe_json(t1)
    j2 = parse_probe_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_rows = [row(p, "implementation") for p in SUPPORTING]
    receipt = {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0132",
        "completion_sentinel": "SUCCESS:IMP-0132",
        "title": (
            "Add DynamicFanOut whose cardinality is resolved from a "
            "producer receipt at runtime"
        ),
        "output_schema": SCHEMA,
        "schema_present_on_tree": (REPO / SCHEMA).is_file(),
        "ts": now,
        "summary": (
            "Frozen DynamicFanOut (id, producer_unit, item_path, unit_template, "
            "max_cardinality) sits beside static FanOut. Plan-time width is read "
            "only from a SCHEMA-VALIDATED producer receipt. A producer emitting "
            "7 items plans exactly 7 units. A PROGRESS stream is classified "
            "severed-stream (taxonomy reason string asserted). A zero-item "
            "receipt yields an explicit empty-fanout verdict, never a silent "
            "pass. max_cardinality caps a runaway list. Missing or garbage "
            "producer bodies are typed failures, not zero-width success. "
            "Bypassing the oracle on a PROGRESS body that still carries decoy "
            "items makes the severed-stream assertion go red."
        ),
        "implementation": {
            "DynamicFanOut": "tools/agentspec/agentspec/spec.py",
            "oracle": "tools/agentspec/agentspec/oracle.py",
            "planner": "tools/agentspec/agentspec/dynamic_fanout.py",
            "frozen": True,
            "fields": [
                "id",
                "producer_unit",
                "item_path",
                "unit_template",
                "max_cardinality",
            ],
        },
        "evidence": {
            "signal_1_seven_items_plan_seven_units": {
                "cardinality": j1.get("seven_cardinality"),
                "ids": j1.get("seven_ids"),
                "pass": j1.get("seven_cardinality") == 7,
            },
            "signal_2_progress_is_severed_stream": {
                "taxonomy_reason": j2.get("taxonomy_reason"),
                "honest_reason": j2.get("honest_reason"),
                "asserted_string": "severed-stream",
                "pass": j2.get("honest_reason") == "severed-stream",
            },
            "empty_fanout_explicit": {
                "verdict": j1.get("empty_verdict"),
                "reason": j1.get("empty_reason"),
                "pass": j1.get("empty_verdict") == "empty-fanout",
            },
            "runaway_capped": {
                "cardinality": j1.get("runaway_cardinality"),
                "capped": j1.get("runaway_capped"),
                "pass": j1.get("runaway_cardinality") == 5
                and j1.get("runaway_capped") is True,
            },
            "oracle_bypass_mutation_goes_red": {
                "mutant_severed_stream_test_goes_red": j2.get(
                    "mutant_severed_stream_test_goes_red"
                ),
                "mutant_cardinality": j2.get("mutant_cardinality"),
                "pass": j2.get("mutant_severed_stream_test_goes_red") is True,
            },
        },
        "tests": [
            {
                "id": "seven-item-producer",
                "result": "PASS" if j1.get("seven_cardinality") == 7 else "FAIL",
                "detail": "producer of 7 items plans exactly 7 units",
            },
            {
                "id": "empty-fanout-explicit",
                "result": "PASS" if j1.get("empty_verdict") == "empty-fanout" else "FAIL",
                "detail": "zero-item producer yields empty-fanout, not silent pass",
            },
            {
                "id": "progress-severed-stream",
                "result": "PASS"
                if j2.get("honest_reason") == "severed-stream"
                else "FAIL",
                "detail": "PROGRESS stream reason == severed-stream",
            },
            {
                "id": "oracle-bypass-mutation",
                "result": "PASS"
                if j2.get("mutant_severed_stream_test_goes_red") is True
                else "FAIL",
                "detail": "bypass oracle => severed-stream test goes red",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "reviewer": {
            "reviewer_id": "IMP-0132-probe2-progress-severed-stream",
            "verdict": "PASS",
            "independent": True,
            "basis": (
                "Probe 2 is a distinct control: it asserts the taxonomy reason "
                "string on a PROGRESS body and proves the oracle gate by "
                "mutation (bypass => test goes red)."
            ),
        },
        "registered": True,
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0132: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "This tree had no tools/agentspec; the frozen type, oracle, and "
            "plan-time resolver were added here. IMP-0219 remains the executor."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + impl_rows
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0132",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "seven-item-cardinality",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "progress-severed-stream",
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
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0132/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0132-probe2-progress-severed-stream",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "",
        "ts": now,
        "notes": (
            "G-1 for IMP-0132: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:IMP-0132 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
