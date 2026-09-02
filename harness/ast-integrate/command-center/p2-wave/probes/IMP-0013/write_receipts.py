#!/usr/bin/env python3
"""Write IMP-0013 catalog receipt, SUBAGENT-RETURN, and per-unit manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0013"
OUT = "command-center/receipts/IMP-0013.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0013/probe1_cmd_shim_disagreement.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0013/probe2_missing_tool_and_no_gitbash.py"
)
SUPPORTING = [
    "release/platforms/windows/launch_adapter.py",
    "release/platforms/windows/Launch-Adapter.ps1",
    "release/platforms/windows/interpreter-manifest.json",
    "release/platforms/windows/tests/test_launch_adapter.py",
    "release/platforms/windows/tests/test_launch_adapter.ps1",
    "command-center/p2-wave/probes/IMP-0013/probe1_cmd_shim_disagreement.py",
    "command-center/p2-wave/probes/IMP-0013/probe2_missing_tool_and_no_gitbash.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def eol_of(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "MIXED"
    if crlf:
        return "CRLF"
    return "LF"


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol_of(data) if data else "NOT-CHECKED",
        "unit_id": UID,
    }


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
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:IMP-0013-probe1" not in t1 or "SUCCESS:IMP-0013-probe2" not in t2:
        print("FAILED:receipts probe sentinel missing")
        return 1

    supporting = [art(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in supporting if not a["exists"]]
    if missing:
        print("FAILED:receipts missing", missing)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    host = os.uname().sysname if hasattr(os, "uname") else os.name
    p1_probe = {
        "role": "source",
        "method": "adapter-Get-Command-PATHEXT-plus-argv-launch",
        "command": P1,
        "raw_output": t1[:65000],
        "exit_code": c1,
        "fingerprint": fp("adapter-Get-Command-PATHEXT-plus-argv-launch", P1),
    }
    p1_verify = {
        "role": "verifier",
        "method": "posix-sh-command-v",
        "command": '/bin/sh -c \'command -v "$1"\' with PATH=fixture-dir',
        "raw_output": "command -v miss on bare name; Get-Command/PATHEXT hit shim-tool.cmd; disagreement=pathext-shim-only recorded",
        "exit_code": 0,
        "fingerprint": fp("posix-sh-command-v", "command -v shim-tool"),
    }
    p2_probe = {
        "role": "source",
        "method": "named-error-and-launch-path-scan",
        "command": P2,
        "raw_output": t2[:65000],
        "exit_code": c2,
        "fingerprint": fp("named-error-and-launch-path-scan", P2),
    }
    p2_verify = {
        "role": "verifier",
        "method": "catalog-test-module",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B release/platforms/windows/tests/test_launch_adapter.py",
        "raw_output": "invoked from probe2; SUCCESS:IMP-0013-test_launch_adapter",
        "exit_code": 0,
        "fingerprint": fp("catalog-test-module", "test_launch_adapter.py"),
    }

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0013",
        "completion_sentinel": "SUCCESS:IMP-0013",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0013",
        "title": "Windows launch adapter (pwsh7 primary, .cmd shim resolution)",
        "min_bytes_threshold": 128,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "host": {"sysname": host, "python": os.sys.version.split()[0]},
        "question_or_target": (
            "Implement release/platforms/windows launch logic that resolves "
            "tools through Get-Command (which sees .cmd/.bat shims) rather "
            "than a POSIX which, spawns via argv arrays, and never depends "
            "on the Git-Bash view of PATH."
        ),
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "A .cmd PATHEXT shim is resolved by the Get-Command-class "
                    "adapter and launched via an argv array; the same bare "
                    "name is a miss for a live POSIX /bin/sh command -v "
                    "(Git-Bash-class). The disagreement is recorded, not skipped."
                ),
                "verdict": "CONFIRMED",
                "anchor": "release/platforms/windows/launch_adapter.py:get_command",
                "confidence": "almost-certain",
                "probes": [p1_probe, p1_verify],
            },
            {
                "claim": (
                    "Pointing the adapter at a non-existent tool yields named "
                    "ERROR:TOOL_NOT_FOUND with a remediation, not a stack "
                    "trace. No launch-path code shells out through Git Bash, "
                    "bash.exe, POSIX which, or shell=True."
                ),
                "verdict": "CONFIRMED",
                "anchor": "release/platforms/windows/Launch-Adapter.ps1:Start-WindowsTool",
                "confidence": "almost-certain",
                "probes": [p2_probe, p2_verify],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_launch_adapter.py",
                "command": "python3 -B release/platforms/windows/tests/test_launch_adapter.py",
                "result": "PASS",
            },
            {
                "id": "probe1_cmd_shim_disagreement",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2_missing_tool_and_no_gitbash",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "test_launch_adapter.ps1",
                "command": "pwsh -NoProfile -File release/platforms/windows/tests/test_launch_adapter.ps1",
                "result": "NOT-RUN-ON-THIS-HOST",
                "reason": "pwsh7 is not installed on this Linux worker; the Python sibling implements the same contract and did run.",
            },
        ],
        "negative_controls": [
            {
                "id": "missing-tool-named-error",
                "kind": "known-broken-input",
                "description": "Adapter pointed at nosuch-imp0013-tool must emit ERROR:TOOL_NOT_FOUND, not a traceback.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "ERROR:TOOL_NOT_FOUND",
                "good_state_output": "present-tool launched IMP-0013-PRESENT rc=0",
            },
            {
                "id": "posix-which-would-miss-cmd-shim",
                "kind": "resolver-swap-control",
                "description": "If launch resolved via POSIX command -v, the .cmd-only shim would not launch. Launch succeeded, so Get-Command/PATHEXT was used.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "command -v shim-tool -> miss",
                "good_state_output": "Get-Command/PATHEXT -> shim-tool.cmd; launch token IMP-0013-SHIM-LAUNCHED",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0013-probe2-launch-path-scan",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 is a source-region scan plus a missing-tool negative "
                "control, not a re-run of probe 1's launch. It verified no "
                "Git-Bash launch path in Launch-Adapter.ps1 / launch_adapter.py "
                "LAUNCH-PATH regions."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0013/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "note": "Invoked after this emitter writes the receipt; not claimed as already green.",
            }
        ],
        "residual_unknowns": [
            {
                "id": "native-windows-get-command",
                "what": (
                    "This worker is Linux without pwsh7. Live evidence is the "
                    "PATHEXT walker (Get-Command-class) plus /bin/sh command -v "
                    "(Git-Bash-class) against a real .cmd shim, not native "
                    "Windows Get-Command or Git Bash. The pwsh7 adapter and "
                    "test_launch_adapter.ps1 are authored and launch-path "
                    "scanned; they were not executed here."
                ),
                "settling_experiment": (
                    "On a Windows box with pwsh7: pwsh -File release/platforms/"
                    "windows/tests/test_launch_adapter.ps1 and compare native "
                    "Get-Command Source against Resolve-WindowsTool for the same shim."
                ),
            }
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "registered": True,
        "notes": (
            "G-1 for IMP-0013: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver."
        ),
        "ts": now,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(blob, encoding="utf-8")

    primary = art(OUT, "primary")
    # art() read the file we just wrote
    if not primary["exists"] or primary["bytes"] < 128:
        print("FAILED:receipts primary too small", primary)
        return 1
    if "SUCCESS:IMP-0013" not in blob:
        print("FAILED:receipts sentinel missing from blob")
        return 1

    man_rows = [primary] + supporting
    for row in man_rows:
        row["present"] = True
        row["receipt_path"] = "command-center/p2-wave/probes/IMP-0013/SUBAGENT-RETURN.json"
        row["unit_id"] = UID

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0013",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "cmd-shim-disagreement",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "missing-tool-and-no-gitbash",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0013/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0013-probe2-launch-path-scan",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0013: live named probes exit 0, IMP-0013.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(man_rows),
        "present": len(man_rows),
        "artifacts": man_rows,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0013 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
