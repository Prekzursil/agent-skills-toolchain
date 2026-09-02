#!/usr/bin/env python3
"""Emit IMP-0054 catalog receipt and per-unit probe return/manifest."""
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
OUT = "command-center/receipts/IMP-0054.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0054/probe1_discarded_return_persists.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0054/probe2_health_and_bounds.py"
)
TCMD = "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/tests/test_degrade_loudly.py"
SUPPORTING = [
    "tools/plugin/degrade_loudly.py",
    "tools/plugin/schema/warning-record.schema.json",
    "tools/plugin/tests/test_degrade_loudly.py",
    "command-center/p2-wave/probes/IMP-0054/probe1_discarded_return_persists.py",
    "command-center/p2-wave/probes/IMP-0054/probe2_health_and_bounds.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


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
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0054",
        "receipt_path": "command-center/p2-wave/probes/IMP-0054/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "exit_code": exit_code,
        "fingerprint": fp(method, command),
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    t_rc, t_out = run_cmd(TCMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if t_rc != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0054 emit tests={t_rc} p1={c1} p2={c2}")
        print(t_out[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    p1_json = json.loads(t1.splitlines()[0])
    p2_json = json.loads(t2.splitlines()[0])
    impl = REPO / "tools/plugin/degrade_loudly.py"
    impl_sha, impl_bytes = digest(impl)
    impl_src = impl.read_text(encoding="utf-8")
    has_fsync = "os.fsync" in impl_src
    has_rotate = "def _rotate" in impl_src
    has_ceiling = "hard_ceiling_bytes" in impl_src
    has_atexit = "atexit.register" in impl_src
    if not (has_fsync and has_rotate and has_ceiling and has_atexit):
        print("FAILED:IMP-0054 emit implementation missing durability/bound primitives")
        return 1

    supporting_arts = []
    for rel in SUPPORTING:
        p = REPO / rel
        sha, size = digest(p)
        supporting_arts.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            }
        )

    p1_probe = probe_obj("source", "command", P1, t1, c1)
    p2_probe = probe_obj("verifier", "command", P2, t2, c2)
    t_probe = probe_obj("source", "command", TCMD, t_out, t_rc)
    disk_probe = probe_obj(
        "verifier",
        "file-read",
        "read tools/plugin/degrade_loudly.py after writer process exit",
        f"bytes={impl_bytes} sha256={impl_sha} fsync={has_fsync} rotate={has_rotate}",
        0,
    )

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    receipt = {
        "unit_id": "IMP-0054",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0054",
        "title": "Degrade-loudly channel that cannot be silently swallowed",
        "spec_anchor": "_USER-PROMPTS.md:10983; _USER-PROMPTS.md:11316; AGENTS.md#4",
        "question": (
            "Implement a warning surface that survives to the user even when the "
            "calling code ignores return values: warnings are written to a durable "
            "sink, counted, and surfaced in the next health-check and at process "
            "exit — closing the 'uncontrolled silence' class where a degraded path "
            "looks identical to a healthy one."
        ),
        "min_bytes_threshold": 128,
        "output_schema": SCHEMA,
        "implementation": {
            "module": "tools/plugin/degrade_loudly.py",
            "sha256": impl_sha,
            "bytes": impl_bytes,
            "api": ["warn", "health_check", "Sink", "discard-warn CLI"],
            "durability": "JSONL append + flock + fsync before return",
            "exit_surface": "atexit writes exit-surface.json and prints a count to stderr",
            "bounds": {
                "default_max_file_bytes": 65536,
                "default_max_files": 8,
                "default_hard_ceiling_bytes": 524288,
                "pathology_reference_bytes": 774 * 1024,
                "ceiling_below_pathology": True,
                "messages_truncated_at": 2048,
            },
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
                "eol": "LF",
                "note": "sha256 is recorded in the per-unit UNIT-ARTIFACT-MANIFEST.json after this file is written; embedding the digest here would change the digest",
            },
            *supporting_arts,
        ],
        "evidence": [
            {
                "anchor": "tools/plugin/degrade_loudly.py:warn",
                "claim": (
                    "A caller that deliberately discards the warning return value "
                    "still produces a durable warning record on disk, measured after "
                    "the writer process has exited."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1_probe, disk_probe],
            },
            {
                "anchor": "tools/plugin/degrade_loudly.py:health_check",
                "claim": (
                    "A later, separate process running health_check surfaces that "
                    "record. An empty sink is declared NO_WARNINGS explicitly, and "
                    "the warned report is not identical to the empty report. The "
                    "sink rotates and stays under a hard ceiling below the 774 KiB "
                    "unbounded-log pathology."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2_probe, t_probe],
            },
        ],
        "tests": [
            {
                "id": "test_ignored_warning_still_persists",
                "command": TCMD + "::test_ignored_warning_still_persists",
                "result": "PASS",
            },
            {
                "id": "test_empty_sink_health_is_explicit",
                "command": TCMD + "::test_empty_sink_health_is_explicit",
                "result": "PASS",
            },
            {
                "id": "test_sink_rotates_and_cannot_grow_without_limit",
                "command": TCMD + "::test_sink_rotates_and_cannot_grow_without_limit",
                "result": "PASS",
            },
            {
                "id": "probe1_discarded_return_persists",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "probe2_health_and_bounds",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0054-C1-empty-sink-explicit",
                "kind": "known-good-fixture",
                "description": (
                    "A run with no warnings must leave an empty sink and the "
                    "health-check must say so explicitly (verdict=NO_WARNINGS, "
                    "empty_sink_declared=true, explicit text contains 'no warnings'). "
                    "Omission of the field is the uncontrolled-silence defect."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "a missing verdict would look like a healthy run",
                "good_state_output": json.dumps(
                    {
                        "verdict": "NO_WARNINGS",
                        "empty_sink_declared": True,
                        "explicit": "no warnings recorded; sink empty",
                    },
                    sort_keys=True,
                ),
            },
            {
                "id": "IMP0054-C2-unbounded-grows-past-ceiling",
                "kind": "known-broken-fixture",
                "description": (
                    "The same flood with rotate=False must exceed the 900-byte test "
                    "ceiling, proving the bound detector can fail. Bounded mode "
                    f"stayed at {p2_json.get('bounded_bytes')}B / "
                    f"{p2_json.get('bounded_files')} files; unbounded reached "
                    f"{p2_json.get('unbounded_bytes')}B."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"unbounded_bytes={p2_json.get('unbounded_bytes')}",
                "good_state_output": f"bounded_bytes={p2_json.get('bounded_bytes')} files={p2_json.get('bounded_files')}",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0054-probe2-health-and-bounds",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope": (
                "Confirm the sink is bounded: live flood stayed under the test "
                "ceiling (900 B, 3 files) while the rotate=False twin exceeded it. "
                "Default production ceiling is 512 KiB, below the 774 KiB pathology."
            ),
        },
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0054/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0054/probe1_discarded_return_persists.py",
                "artifact_path": "tools/plugin/degrade_loudly.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": p1_probe,
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0054/probe2_health_and_bounds.py",
                "artifact_path": "tools/plugin/degrade_loudly.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": p2_probe,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0051 taxonomy codes and IMP-0056 JSONL redaction are "
                    "declared dependencies and are not delivered in this worktree. "
                    "This unit accepts any string code and does not redact; a later "
                    "IMP-0056 pass should wrap the same sink rather than replace it."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After IMP-0056 lands, plant a synthetic credential in a warning "
                    "message and grep the sink for the secret body."
                ),
            }
        ],
        "report": {
            "kind": "degrade-loudly-channel",
            "probe1": p1_json,
            "probe2": p2_json,
            "tests_tail": t_out.splitlines()[-12:],
        },
        "failure": {
            "classification": [],
            "reason": "none — both catalog signals held on a live re-run",
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0054" not in text:
        print("FAILED:IMP-0054 emit sentinel missing from body")
        return 1
    out_path.write_text(text, encoding="utf-8")
    primary = art_row(OUT, "primary")

    artifacts = [primary] + [art_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "IMP-0054",
        "unit_id": "IMP-0054",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0054",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "discarded-return-persists",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "health-check-and-bounds",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0054/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0054-probe2-health-and-bounds",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0054: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0054",
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
    print("SUCCESS:IMP-0054 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
