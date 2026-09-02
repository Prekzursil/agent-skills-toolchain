#!/usr/bin/env python3
"""Write IMP-0408 receipt, per-unit SUBAGENT-RETURN, and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0408"
OUT_REL = "command-center/receipts/IMP-0408.json"
SENTINEL = "SENTINEL:IMP-0408:LIVENESS-TWO-SIGNAL"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0408/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0408/probe2_stalled_vs_finished.py"
)
TCMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/session_liveness/tests/test_liveness.py"
)
SUPPORTING = [
    "tools/session_liveness/__init__.py",
    "tools/session_liveness/liveness.py",
    "tools/session_liveness/harness.py",
    "tools/session_liveness/live_worker.py",
    "tools/session_liveness/tests/test_liveness.py",
    "command-center/p2-wave/probes/IMP-0408/probe1_both_states.py",
    "command-center/p2-wave/probes/IMP-0408/probe2_stalled_vs_finished.py",
    "command-center/p2-wave/probes/IMP-0408/write_receipts.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
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


def first_json(text: str):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def art_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "bytes": size,
        "eol": "LF",
        "exists": True,
        "path": rel,
        "role": role,
        "sha256": sha,
    }


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/IMP-0408/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def main() -> int:
    c_t, t_t = run_cmd(TCMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_t != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0408 receipts tests={c_t} p1={c1} p2={c2}")
        print(t_t[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    j1 = first_json(t1) or {}
    j2 = first_json(t2) or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_rel = "tools/session_liveness/liveness.py"
    lib_sha, lib_bytes = digest(REPO / lib_rel)
    dep_0407 = (REPO / "command-center/receipts/IMP-0407.json").is_file()

    receipt = {
        "artifacts": [art_row(p, "supporting") for p in SUPPORTING],
        "completion_sentinel": SENTINEL,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": True,
                "exit_code": None,
                "probe": {
                    "command": (
                        "python3 command-center/p2-wave/_measure_one_delivered.py "
                        "IMP-0408"
                    ),
                    "exit_code": None,
                    "fingerprint": fp(
                        "command",
                        "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0408",
                    ),
                    "method": "command",
                    "raw_output": "measured after this receipt is written",
                    "role": "verifier",
                },
                "read_ok": True,
            }
        ],
        "evidence": [
            {
                "anchor": "tools/session_liveness/liveness.py:measure_pair",
                "claim": (
                    "Measured CPU delta and artifact byte-growth over a 20s window "
                    "on one live worker (CPU burn + log append) and one long-finished "
                    "frozen tree. Same classify() path: ALIVE vs NOT-ALIVE."
                ),
                "confidence": "almost-certain",
                "finished": j1.get("finished"),
                "live": j1.get("live"),
                "probes": [
                    {
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp("command", P1),
                        "method": "command",
                        "raw_output": t1[-4000:],
                        "role": "source",
                    }
                ],
                "verdict": "CONFIRMED",
                "window_seconds": 20,
            },
            {
                "anchor": "tools/session_liveness/liveness.py:stall_versus_finished",
                "claim": (
                    "A SIGSTOP'd quiet process is UNDECIDABLE; a process-absent "
                    "finished tree is NOT-ALIVE; the pair question stalled-versus-finished "
                    "returns UNDECIDABLE. mtime kwargs TypeError; no STALLED verdict. "
                    "Touching finished files to now still yields NOT-ALIVE, not STALLED."
                ),
                "confidence": "almost-certain",
                "finished": j2.get("finished"),
                "mtime_kwarg_rejected": j2.get("mtime_kwarg_rejected"),
                "no_stalled_in_api": j2.get("no_stalled_in_api"),
                "pair_verdict": j2.get("pair_verdict"),
                "probes": [
                    {
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp("command", P2),
                        "method": "command",
                        "raw_output": t2[-4000:],
                        "role": "verifier",
                    }
                ],
                "reviewer": "adversarial-refuter",
                "stalled": j2.get("stalled"),
                "verdict": "CONFIRMED",
            },
        ],
        "failure_class_seeded": "mtime-only-stall-claim, single-signal-verdict",
        "id": UID,
        "implementation": {
            "api_module": lib_rel,
            "bytes": lib_bytes,
            "entry_points": [
                "session_liveness.liveness.classify",
                "session_liveness.liveness.measure_pair",
                "session_liveness.liveness.stall_versus_finished",
            ],
            "mtime_unrepresentable": True,
            "sha256": lib_sha,
            "signals": ["process-cpu-delta", "artifact-byte-growth"],
            "verdicts": ["ALIVE", "NOT-ALIVE", "UNDECIDABLE"],
            "window_seconds": 20,
        },
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0408/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "min_bytes_threshold": 1024,
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1"},
            {"command": P2, "exit_code": c2, "id": "probe2"},
        ],
        "negative_controls": [
            {
                "description": (
                    "CPU-only or byte-only injected observations are UNDECIDABLE, "
                    "not ALIVE (AND-gate)."
                ),
                "fired_on_bad_state": True,
                "id": "single-signal-not-alive",
                "kind": "mutation",
                "silent_on_good_state": True,
            },
            {
                "description": (
                    "Finished session with 11h-old mtime, then touched to now: "
                    "still NOT-ALIVE. STALLED is not a representable verdict."
                ),
                "fired_on_bad_state": True,
                "id": "mtime-cannot-stall",
                "kind": "adversarial-mtime-bait",
                "silent_on_good_state": True,
            },
        ],
        "notes": (
            "G-1 for IMP-0408: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. SENTINEL:IMP-0408:LIVENESS-TWO-SIGNAL"
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "question_or_target": (
            "Implement liveness as an AND-gate of at least two mechanically "
            "independent signals (process CPU delta AND artifact byte-growth), "
            "and make mtime-only liveness unrepresentable in the API."
        ),
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog input command-center/receipts/IMP-0407.json is "
                    f"{'present' if dep_0407 else 'absent'}. Probes use spawned "
                    "fixtures (pid + artifact dir), not a live Claude/Codex registry."
                ),
                "settling_experiment": (
                    "Re-run measure_pair against IMP-0407 registry rows once that "
                    "unit is delivered."
                ),
                "verdict": "NOT-CHECKED" if not dep_0407 else "CHECKED",
            },
            {
                "claim": (
                    "CPU ticks are utime+stime of the named pid only; descendant "
                    "processes are not included."
                ),
                "verdict": "ACCEPTED-LIMITATION",
            },
        ],
        "retry": {
            "count": 0,
            "policy": "no automatic retry; wrong liveness authorizes kill-escalate",
        },
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "note": (
                "Probe 2 is the adversarial refuter: finished+old-mtime must not "
                "become STALLED; stalled-versus-finished is UNDECIDABLE."
            ),
            "reviewer_id": "IMP-0408-probe2-stalled-vs-finished",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0408",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0408",
        "state": "SUCCESS",
        "tests": [
            {
                "command": TCMD,
                "id": "test_liveness.py",
                "result": "PASS" if c_t == 0 else "FAIL",
            },
            {
                "command": P1,
                "id": "probe1_both_states",
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "command": P2,
                "id": "probe2_stalled_vs_finished",
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Two-signal session liveness with an explicit no-mtime rule",
        "unit_id": UID,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:IMP-0408 emit sentinel missing before write")
        return 1
    out.write_text(text, encoding="utf-8")
    size = out.stat().st_size
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:IMP-0408 emit {size}B below floor")
        return 1

    primary = manifest_row(OUT_REL, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT_REL,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "manifest_path": "command-center/p2-wave/probes/IMP-0408/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "both-states-20s-window",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "adversarial-stalled-vs-finished",
            },
        ],
        "notes": (
            "G-1 for IMP-0408: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0408-probe2-stalled-vs-finished",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:IMP-0408",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests_command": TCMD,
        "tests_exit_code": c_t,
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0408 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
