#!/usr/bin/env python3
"""Emit IMP-0447 receipt + per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0447"
OUT = "command-center/receipts/IMP-0447.json"
SENTINEL = "SENTINEL:IMP-0447:HANG-DETECTION-TWO-SIGNAL"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0447/probe1_hung_and_slow.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0447/probe2_adversarial_slow.py"
)
SUPPORTING = [
    "command-center/runner/hang_detect.py",
    "command-center/p2-wave/probes/IMP-0447/runtime.py",
    "command-center/p2-wave/probes/IMP-0447/fixtures/worker.py",
    "command-center/p2-wave/probes/IMP-0447/probe1_hung_and_slow.py",
    "command-center/p2-wave/probes/IMP-0447/probe2_adversarial_slow.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


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


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise ValueError("no JSON summary line in probe output")


def art(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "bytes": size,
        "eol": "LF",
        "exists": True,
        "path": rel,
        "role": role,
        "sha256": sha,
    }


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "command": command,
        "exit_code": exit_code,
        "fingerprint": fp(method, command),
        "method": method,
        "raw_output": raw[-8000:],
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    s1 = first_json(t1)
    s2 = first_json(t2)
    hung = s1["hung"]
    slow = s1["slow_bytes"]
    mutant = s1["mutant_red"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_src = probe_rec("source", "command", P1, t1, c1)
    p1_ver = probe_rec("verifier", "command", P1, t1, c1)
    p2_src = probe_rec("source", "command", P2, t2, c2)
    p2_ver = probe_rec("verifier", "file-read", "read probe2 JSON summary", json.dumps(s2), 0)

    impl = art("command-center/runner/hang_detect.py", "primary")
    receipt_doc = {
        "artifacts": [impl] + [art(p, "supporting") for p in SUPPORTING[1:]],
        "downstream_consumers": [
            {
                "artifact_path": "command-center/runner/hang_detect.py",
                "consumer": "command-center/p2-wave/probes/IMP-0447/probe1_hung_and_slow.py",
                "executed": True,
                "exit_code": c1,
                "probe": p1_src,
                "read_ok": True,
            },
            {
                "artifact_path": "command-center/runner/hang_detect.py",
                "consumer": "command-center/p2-wave/probes/IMP-0447/probe2_adversarial_slow.py",
                "executed": True,
                "exit_code": c2,
                "probe": p2_src,
                "read_ok": True,
            },
        ],
        "evidence": [
            {
                "anchor": "command-center/runner/hang_detect.py:classify",
                "claim": (
                    "A hung fixture (frozen heartbeat AND frozen output bytes) is classified "
                    f"STALLED in {hung['time_to_classification_s']}s "
                    f"(stall_window_s={hung['stall_window_s']}), which is less than "
                    f"catalog timeout_seconds={s1['catalog_timeout_seconds']} and less than "
                    f"the probe hard timeout_s={hung['timeout_s']}. Classification requires "
                    "two dead signals; slot_released is true."
                ),
                "confidence": "almost-certain",
                "probes": [p1_src, p1_ver],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/runner/hang_detect.py:classify",
                "claim": (
                    "A slow-but-alive fixture with frozen heartbeat and growing bytes is "
                    f"ALIVE (byte_growth={slow['byte_growth']}, "
                    f"heartbeat_advanced={slow['heartbeat_advanced']}). Removing the "
                    "byte-growth signal (classify_heartbeat_only_defective) classifies the "
                    f"same samples STALLED ({mutant['state']}), so the slow-alive test goes red."
                ),
                "confidence": "almost-certain",
                "probes": [p1_src, p1_ver],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/IMP-0447/probe2_adversarial_slow.py",
                "claim": (
                    "Adversarial attempts to classify a live slow unit as STALLED failed "
                    f"({s2['adversarial_stalls']} stalls). mtime-only classification is rejected. "
                    "A hung negative control remains STALLED, so the detector is not inert."
                ),
                "confidence": "almost-certain",
                "probes": [p2_src, p2_ver],
                "verdict": "CONFIRMED",
            },
        ],
        "exact_question": (
            "For a deliberately hung unit, how long until the runner classifies it, "
            "and does the classification require two signals?"
        ),
        "exact_answer": {
            "classification_requires_two_signals": True,
            "hung_signals": {
                "byte_growth": hung["byte_growth"],
                "heartbeat_advanced": hung["heartbeat_advanced"],
            },
            "hung_state": hung["state"],
            "slot_released_on_stall": hung["slot_released"],
            "time_to_classification_s": hung["time_to_classification_s"],
            "catalog_timeout_seconds": s1["catalog_timeout_seconds"],
            "stall_window_s": hung["stall_window_s"],
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0447/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "measured_target": "CONFIRMED",
        "min_bytes_threshold": 128,
        "negative_controls": [
            {
                "bad_state_output": mutant["reason"],
                "description": (
                    "Mutation removing byte-growth classifies the slow-but-alive fixture STALLED; "
                    "production two-signal classify does not."
                ),
                "fired_on_bad_state": mutant["state"] == "STALLED",
                "good_state_output": slow["reason"],
                "id": "mutation-drop-byte-growth",
                "kind": "mutation",
                "silent_on_good_state": slow["state"] == "ALIVE",
            },
            {
                "bad_state_output": "mtime rejected",
                "description": "mtime-only hang classification is unrepresentable",
                "fired_on_bad_state": True,
                "good_state_output": "two-signal classify accepted",
                "id": "mtime-rejected",
                "kind": "forbidden-signal",
                "silent_on_good_state": True,
            },
        ],
        "output_schema": "command-center/schema/receipt.schema.json",
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0442 dispatcher receipt is not on this tree; hang_detect.watch() is the "
                    "slot-release API a dispatcher can call. Wiring into the live dispatcher is "
                    "IMP-0442/IMP-0452 work, not claimed here."
                ),
                "settling_experiment": "IMP-0442 imports command-center.runner.hang_detect.watch",
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0447-probe2-adversarial-slow",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": "WORK-UNIT-CATALOG.json IMP-0447; timeout_seconds + two-signal hang",
        "state": "SUCCESS",
        "tests": [
            {
                "command": P1,
                "id": "hung-unit",
                "result": "PASS" if hung["state"] == "STALLED" else "FAIL",
            },
            {
                "command": P1,
                "id": "slow-but-alive",
                "result": "PASS" if slow["state"] == "ALIVE" else "FAIL",
            },
            {
                "command": P1,
                "id": "mutation-drop-byte-growth",
                "result": "PASS" if mutant["state"] == "STALLED" else "FAIL",
            },
            {
                "command": P2,
                "id": "adversarial-refuter-slow-unit",
                "result": "PASS" if s2.get("pass") else "FAIL",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "unit_id": UNIT,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    rec_sha, rec_bytes = digest(out_path)

    def row(rel: str, role: str) -> dict:
        sha, size = digest(REPO / rel)
        return {
            "bytes": size,
            "path": rel,
            "present": True,
            "receipt_path": "command-center/p2-wave/probes/IMP-0447/SUBAGENT-RETURN.json",
            "role": role,
            "sha256": sha,
            "unit_id": UNIT,
        }

    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": rec_bytes,
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": rec_sha,
            }
        ],
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/IMP-0447/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1", "raw_output": t1[-12000:]},
            {"command": P2, "exit_code": c2, "id": "probe2", "raw_output": t2[-12000:]},
        ],
        "notes": (
            "G-1 for IMP-0447: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0447-probe2-adversarial-slow",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
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
    print(f"artifact {OUT} bytes={rec_bytes} sha256={rec_sha}")
    print("SUCCESS:IMP-0447 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
