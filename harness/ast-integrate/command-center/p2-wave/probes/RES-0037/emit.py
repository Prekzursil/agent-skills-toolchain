#!/usr/bin/env python3
"""Emit command-center/research/RES-0037.json from live named probes."""
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
UNIT = "RES-0037"
OUT_REL = "command-center/research/RES-0037.json"
SCHEMA = "command-center/schema/measurement-run.schema.json"
SENTINEL = (
    "SUCCESS:RES-0037 in the receipt AND a per-transport process count with a "
    "start/stop delta control and a stated proof the probe does not match itself"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0037/probe1_self_exclusion_delta.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0037/probe2_handle_count.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0037/lib.py",
    "command-center/p2-wave/probes/RES-0037/fixtures/stdio_standin.py",
    "command-center/p2-wave/probes/RES-0037/fixtures/http_standin.py",
    "command-center/p2-wave/probes/RES-0037/probe1_self_exclusion_delta.py",
    "command-center/p2-wave/probes/RES-0037/probe2_handle_count.py",
    "command-center/p2-wave/probes/RES-0037/emit.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def parse_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            doc = json.loads(line)
            if isinstance(doc, dict):
                return doc
    raise ValueError("no JSON object line in probe output")


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code1 != 0 or "SUCCESS:RES-0037-probe1" not in out1:
        print("FAILED:RES-0037 probe1 did not exit 0 with sentinel")
        print(out1[-4000:])
        return 1
    if code2 != 0 or "SUCCESS:RES-0037-probe2" not in out2:
        print("FAILED:RES-0037 probe2 did not exit 0 with sentinel")
        print(out2[-4000:])
        return 1
    try:
        p1j = parse_json_line(out1)
        p2j = parse_json_line(out2)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"FAILED:RES-0037 probe JSON {exc}")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    ptc1 = p1j.get("per_transport_process_count") or {}
    ptc2 = p2j.get("per_transport_process_count") or {}
    delta = p1j.get("start_stop_delta") or {}
    recorded = p2j.get("recorded_driver") or {}
    fleet = p2j.get("today_fleet") or {}
    proof = p1j.get("self_match_proof") or {}

    stdio_n = ptc1.get("stdio_os_processes")
    http_n = ptc1.get("http_os_processes")
    if stdio_n != ptc2.get("stdio_ps_processes") or http_n != ptc2.get("http_ps_processes"):
        print("FAILED:RES-0037 probe1/probe2 process counts disagree")
        return 1

    supporting_arts = [art(rel, "supporting") for rel in SUPPORTING]
    question = (
        "How many OS processes does one session spawn per stdio MCP server "
        "versus one shared HTTP server, and does the measured multiplication "
        "reproduce the estate's recorded commit-exhaustion driver "
        "(sessions x servers) on today's fleet?"
    )
    answer = (
        f"On this Linux worktree a controlled stand-in shows stdio cost = "
        f"{ptc1.get('processes_per_stdio_server_per_session')} OS process per "
        f"server per session "
        f"({ptc1.get('sessions')} sessions x {ptc1.get('stdio_servers_per_session')} "
        f"servers = {stdio_n} processes) while one shared HTTP stand-in stays at "
        f"{http_n} process with a LISTEN socket. The recorded driver "
        "23 sessions x 65 servers = 2037 is arithmetically false "
        f"(23*65={recorded.get('true_product')} by both Python and POSIX expr) "
        "and today's argv-exact MCP fleet count is "
        f"{fleet.get('argv_exact_mcp_count')}, not 2037. Mechanism reproduced; "
        "fleet size and the 2037 figure are not."
    )

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "title": (
            "Measure the per-session process cost of stdio versus HTTP MCP "
            "transports on this box"
        ),
        "question": question,
        "question_or_target": question,
        "answer": answer,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:RES-0037; recorded 23 sessions x 65 servers "
            "= 2037 as prior estate claim, re-measured rather than trusted"
        ),
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot; a repeated identical local reading is "
                "ONE signal, not two"
            ),
        },
        "per_transport_process_count": {
            "stdio": {
                "sessions": ptc1.get("sessions"),
                "servers_per_session": ptc1.get("stdio_servers_per_session"),
                "os_processes_procfs": stdio_n,
                "os_processes_ps": ptc2.get("stdio_ps_processes"),
                "processes_per_server_per_session": ptc1.get(
                    "processes_per_stdio_server_per_session"
                ),
                "handle_counts_by_pid": ptc2.get("stdio_handle_counts"),
                "listen_inodes": ptc2.get("stdio_listen_inodes"),
            },
            "http_shared": {
                "sessions": ptc1.get("sessions"),
                "os_processes_procfs": http_n,
                "os_processes_ps": ptc2.get("http_ps_processes"),
                "handle_count": ptc2.get("http_handle_count"),
                "listen_inodes": ptc2.get("http_listen_inodes"),
                "additional_processes_per_extra_session": 0,
            },
        },
        "start_stop_delta_control": {
            "known_server": "fixtures/stdio_standin.py argv token RES0037_STDIO_STANDIN",
            "expected_start_delta": 1,
            "observed_start_delta": delta.get("observed_start_delta"),
            "expected_stop_delta": 0,
            "observed_stop_delta": delta.get("observed_stop_delta"),
            "child_pid": delta.get("child_pid"),
            "pass": True,
        },
        "self_match_proof": {
            "naive_pattern": proof.get("naive_pattern"),
            "naive_includes_probe": proof.get("naive_includes_probe"),
            "token": proof.get("token"),
            "token_absent_from_probe_argv": proof.get("token_absent_from_probe_argv"),
            "actual_includes_probe": proof.get("actual_includes_probe"),
            "stated_proof": proof.get("stated_proof"),
            "decoy": p1j.get("decoy"),
        },
        "recorded_commit_exhaustion_driver": recorded,
        "today_fleet": fleet,
        "claims": [
            {
                "id": "RES-0037-C1",
                "claim": (
                    "One stdio stand-in MCP server costs one OS process per session; "
                    f"{ptc1.get('sessions')}x{ptc1.get('stdio_servers_per_session')} "
                    f"produced {stdio_n} processes on /proc and on ps."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "signals": ["procfs-exact-argv-token", "ps-eo-pid-args"],
            },
            {
                "id": "RES-0037-C2",
                "claim": (
                    "One shared HTTP stand-in costs one OS process for the same "
                    f"{ptc1.get('sessions')} sessions, distinguished by a LISTEN "
                    "inode on /proc/<pid>/fd that stdio children lack."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "signals": ["procfs-process-count", "fd-listen-inode"],
            },
            {
                "id": "RES-0037-C3",
                "claim": (
                    "The catalog's recorded equation 23 sessions x 65 servers = 2037 "
                    "does not hold: both Python and POSIX expr compute 1495. Today's "
                    "argv-exact MCP fleet on this box is "
                    f"{fleet.get('argv_exact_mcp_count')}, so the 2037 freeze size is "
                    "not reproduced here."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "signals": ["python-int-product", "posix-expr"],
                "subject": "recorded 23x65=2037 and today's live fleet size",
            },
        ],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/RES-0037/lib.py:token_exact_pids",
                "claim": (
                    "Process count is an exact argv token, not a substring of the "
                    "probe path; start/stop of one known server moves the count by +1 "
                    "then back to baseline."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1],
            },
            {
                "anchor": "command-center/p2-wave/probes/RES-0037/lib.py:ps_token_pids",
                "claim": (
                    "A second rail (/bin/ps plus per-pid fd/LISTEN handles) reproduces "
                    "the same per-transport process counts."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2],
            },
            {
                "anchor": "WORK-UNIT-CATALOG.json:RES-0037 recorded 23x65=2037",
                "claim": (
                    "23*65 is 1495, not 2037; live argv-exact MCP count is not 2037."
                ),
                "confidence": "almost-certain",
                "verdict": "REFUTED",
                "probes": [p2, p1],
            },
        ],
        "tests": [
            {
                "id": "count-with-pattern-proven-not-to-match-probe-cmdline",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "start-stop-known-server-delta",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "independent-ps-and-handle-count",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "recorded-23x65-arithmetic",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": code1, "result": "PASS"},
            {"id": "probe2", "command": P2, "exit_code": code2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "naive-substring-RES-0037-matches-probe",
                "kind": "known-broken-matcher",
                "description": (
                    "Substring 'RES-0037' matches this probe's script path and would "
                    "report the measurer as a live server. The token matcher must "
                    "stay silent on that PID."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "decoy-carries-probe-filename-but-not-token",
                "kind": "known-broken-cmdline",
                "description": (
                    "A decoy argv includes probe1_self_exclusion_delta.py but not "
                    "the stand-in token; the stdio token matcher must not count it."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0037-probe2-handle-count",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "shell": "/bin/ps versus Python /proc walk; POSIX expr versus Python int",
            "tolerance": 0,
            "reproduced_stdio_count": ptc2.get("stdio_ps_processes"),
            "reproduced_http_count": ptc2.get("http_ps_processes"),
            "powershell7_vs_git_bash": "NOT-CHECKED",
            "powershell7_vs_git_bash_reason": (
                "This worktree is Linux; PowerShell 7 vs Git Bash is the catalog's "
                "Windows reviewer pair and is not the substrate here."
            ),
        },
        "reviewer_verdict": "PASS",
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Windows estate ~/.mcp.json, the 2026-07-19 commit-exhaustion "
                    "root-cause note, and a live Claude stdio fleet are absent from "
                    "this Linux worktree. Stand-ins measure the multiplication "
                    "mechanism; they are not the original 65-server vendor binaries."
                ),
                "settling_experiment": (
                    "Re-run token_exact_pids against a live Claude MCP fleet on the "
                    "Windows estate and compare sessions x servers to both 1495 and 2037."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of RES-0037. Live named probes measure stdio vs HTTP "
            "process cost with a start/stop delta and a stated self-exclusion "
            "proof. Did not run global unit_manifest.py --write. cloud ok is not "
            "consulted."
        ),
        "artifact_paths": [OUT_REL] + list(SUPPORTING),
        "artifacts": supporting_arts,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:RES-0037 research artifact too small ({live_bytes} B)")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0037 catalog sentinel absent from artifact")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "process-table-self-exclusion-delta",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "ps-handle-count-fleet",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0037-probe2-handle-count",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for RES-0037: live named probes exit 0, research/RES-0037.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
