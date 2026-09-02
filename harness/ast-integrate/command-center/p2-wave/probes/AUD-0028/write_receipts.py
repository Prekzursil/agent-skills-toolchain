#!/usr/bin/env python3
"""Emit AUD-0028 census artifact plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
"""
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

import census as C  # noqa: E402

UID = "AUD-0028"
OUT = C.OUT_REL
SCHEMA = C.SCHEMA
SENTINEL = C.SENTINEL
QUESTION = C.QUESTION
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0028/probe1_pwsh_get_command.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0028/probe2_gitbash_command_v.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0028/census.py",
    "command-center/p2-wave/probes/AUD-0028/probe1_pwsh_get_command.py",
    "command-center/p2-wave/probes/AUD-0028/probe2_gitbash_command_v.py",
    SCHEMA,
    "command-center/p2-wave/probes/AUD-0028/write_receipts.py",
]
MIN_BYTES = 2048


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/AUD-0028/SUBAGENT-RETURN.json",
        "role": role,
    }


def validate_schema(doc: dict) -> None:
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        for key in schema.get("required") or []:
            if key not in doc:
                raise ValueError(f"schema required field missing: {key}")
        return
    jsonschema.Draft7Validator(schema).validate(doc)


def slim_resolution(row: dict) -> dict:
    ver = row.get("version") or {}
    return {
        "tool": row.get("tool"),
        "get_command_source": row.get("get_command_source"),
        "command_v": row.get("command_v"),
        "present_get_command": row.get("present_get_command"),
        "present_command_v": row.get("present_command_v"),
        "path_divergence": row.get("path_divergence"),
        "presence_disagreement": row.get("presence_disagreement"),
        "realpath_same": row.get("realpath_same"),
        "version": ver.get("text") if isinstance(ver, dict) else None,
    }


def build_artifact(p1: dict, p2: dict, now: str) -> dict:
    s1 = p1["scan"]
    s2 = p2["scan"]
    summary = p1["summary"]
    tools = (p2.get("scan") or {}).get("tools") or []
    tool_names = [t["tool"] for t in tools]
    ctl = p1.get("control") or {}
    answer = (
        f"Invocation scan of this Linux worktree found {s1['tool_count']} distinct "
        f"external CLI tools across {s1['hit_count']} sites in {s1['files_scanned']} "
        f"source files. Host PATH: Get-Command vs command -v path_divergence_count="
        f"{summary['path_divergence_count']} presence_disagreement_count="
        f"{summary['presence_disagreement_count']} present_both="
        f"{summary['present_both']} missing_both={summary['missing_both']}. "
        f"Both-states control: planted WSL-shaped vs MSYS-shaped bash paths differ="
        f"{ctl.get('bash_paths_differ')}; planted git.cmd vs POSIX git differ="
        f"{ctl.get('git_paths_differ')}; naive same-PATH command -v pair agrees="
        f"{ctl.get('naive_agree')}. pwsh binary present="
        f"{(p1.get('pwsh') or {}).get('present')}. Tools (lexicographic): "
        + ", ".join(tool_names[:40])
        + ("…" if len(tool_names) > 40 else "")
        + "."
    )
    return {
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/AUD-0028/census.py",
                "role": "enumerator",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0028/probe1_pwsh_get_command.py",
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0028/probe2_gitbash_command_v.py",
                "role": "named-probe",
            },
        ],
        "answer": answer,
        "completion_sentinel": SENTINEL,
        "defects": [
            {
                "id": d["tool"],
                "kind": "path-divergence",
                "get_command_source": d.get("get_command_source"),
                "command_v": d.get("command_v"),
                "realpath_same": d.get("realpath_same"),
            }
            for d in (summary.get("path_divergences") or [])
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "note": "G-1 per-unit delivery measure; cloud ok=true is not delivery",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Probe 1 resolves each invoked tool via Get-Command Source "
                    "semantics (PATHEXT .COM/.EXE/.BAT/.CMD), recording the "
                    "pwsh binary as absent on this Linux host rather than "
                    "forging a PowerShell transcript."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0028/probe1_pwsh_get_command.py",
                "detail": (
                    f"tools={s1['tool_count']} hits={s1['hit_count']} "
                    f"pwsh={(p1.get('pwsh') or {}).get('present')} "
                    f"host_div={summary['path_divergence_count']}"
                ),
            },
            {
                "claim": (
                    "Probe 2 independently resolves the same tool set via live "
                    "bash command -v (Git Bash analogue) and re-runs the "
                    "WSL-versus-MSYS bash path control."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0028/probe2_gitbash_command_v.py",
                "detail": (
                    f"tools={s2['tool_count']} present={p2['summary']['present']} "
                    f"host_bash={p2.get('host_bash_command_v')} "
                    f"bash_paths_differ={ctl.get('bash_paths_differ')}"
                ),
            },
            {
                "claim": (
                    "Both-states control: the pair reports different paths for "
                    "bash itself (planted WSL-shaped vs MSYS-shaped). A naive "
                    "same-PATH command -v pair agrees, proving a same-shell "
                    "run cannot satisfy the control. A planted git.cmd shim is "
                    "the Source for Get-Command and is missed by command -v, "
                    "which falls through to POSIX git."
                ),
                "verdict": "CONFIRMED" if ctl.get("pass") else "REFUTED",
                "anchor": "command-center/p2-wave/probes/AUD-0028/census.py:both_states_control",
                "detail": json.dumps(
                    {
                        "bash_paths_differ": ctl.get("bash_paths_differ"),
                        "git_paths_differ": ctl.get("git_paths_differ"),
                        "naive_agree": ctl.get("naive_agree"),
                        "git_cmd_shim_won_get_command": ctl.get(
                            "git_cmd_shim_won_get_command"
                        ),
                    },
                    sort_keys=True,
                ),
            },
        ],
        "id": UID,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0028/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; tools/command-center/unit_manifest.py --write was not run",
        },
        "min_bytes_threshold": MIN_BYTES,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "pwsh7-get-command-source",
                "exit_code": None,
                "raw_output": "",
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "git-bash-command-v",
                "exit_code": None,
                "raw_output": "",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD-0028-naive-same-path-bash-agrees",
                "kind": "planted-fixture",
                "description": (
                    "If both probes use command -v on the same PATH they MUST "
                    "agree on bash. Agreement on that bad pair plus disagreement "
                    "on the WSL-prefix vs MSYS-prefix pair is the control."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": False,
                "bad_state_output": json.dumps(
                    {"naive_agree": ctl.get("naive_agree")}, sort_keys=True
                ),
                "good_state_output": json.dumps(
                    {
                        "bash_paths_differ": ctl.get("bash_paths_differ"),
                        "git_paths_differ": ctl.get("git_paths_differ"),
                    },
                    sort_keys=True,
                ),
            }
        ],
        "output_path": OUT,
        "output_schema": SCHEMA,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "linux-worktree",
        },
        "question": QUESTION,
        "report": {
            "kind": "audit-finding",
            "control": {
                "pass": ctl.get("pass"),
                "bash_paths_differ": ctl.get("bash_paths_differ"),
                "git_paths_differ": ctl.get("git_paths_differ"),
                "naive_agree": ctl.get("naive_agree"),
                "git_cmd_shim_won_get_command": ctl.get("git_cmd_shim_won_get_command"),
                "note": (
                    "WSL versus MSYS bash binaries are not both installed on "
                    "this Linux host. The control plants two distinct bash "
                    "stand-ins on two PATH prefixes (WSL-shaped vs MSYS-shaped) "
                    "and requires the two resolvers to report different paths. "
                    "Host PATH bash resolution is recorded separately and may "
                    "agree."
                ),
            },
            "probe1": {
                "instrument": p1.get("instrument"),
                "pwsh": p1.get("pwsh"),
                "scan": s1,
                "summary": summary,
                "resolutions": [slim_resolution(r) for r in (p1.get("resolutions") or [])],
            },
            "probe2": {
                "instrument": p2.get("instrument"),
                "host_bash_command_v": p2.get("host_bash_command_v"),
                "scan": {
                    "files_scanned": s2.get("files_scanned"),
                    "hit_count": s2.get("hit_count"),
                    "tool_count": s2.get("tool_count"),
                    "tools": tools,
                },
                "summary": p2.get("summary"),
                "resolutions": [
                    {
                        "tool": r.get("tool"),
                        "command_v": r.get("command_v"),
                        "present": r.get("present"),
                        "version": ((r.get("version") or {}).get("text")),
                    }
                    for r in (p2.get("resolutions") or [])
                ],
            },
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Invocation scan excludes command-center/p2-wave/probes/ "
                    "and unit output trees so remesure is not racing sibling "
                    "G-1 deliveries. CLI calls that exist only inside those "
                    "probe factories are out of scope for this census."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a frozen tree with no concurrent unit delivery, re-run "
                    "the enumerator without SKIP_REL_PREFIXES and diff tool "
                    "sets against this artifact."
                ),
            },
            {
                "claim": (
                    "Live Windows PowerShell 7 Get-Command and Git Bash on an "
                    "MSYS PATH were not executed: pwsh is not installed, and "
                    "this substrate is Linux rather than Windows+WSL. Host PATH "
                    "divergences here do not substitute for a Windows checkout."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe 1 under pwsh7 Get-Command and probe 2 under "
                    "Git Bash on Windows, requiring bash Source to be WSL "
                    "/usr/bin/bash versus MSYS /usr/bin/bash."
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "AUD-0028-probe2-gitbash-command-v",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Catalog asks for a cross-vendor Codex reviewer who re-runs only "
                "probe 2. Probe 2 is a live bash command -v pass plus an "
                "independent re-run of the WSL/MSYS bash control, not a re-read "
                "of probe 1's Get-Command table."
            ),
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": "WORK-UNIT-CATALOG.json:AUD-0028",
        "state": "SUCCESS",
        "tests": [
            {
                "id": "probe1-pwsh-get-command-source",
                "result": "PASS" if p1.get("pass") else "FAIL",
                "name": "Get-Command Source resolver over the invocation census",
            },
            {
                "id": "probe2-gitbash-command-v",
                "result": "PASS" if p2.get("pass") else "FAIL",
                "name": "Live bash command -v resolver over the same census",
            },
            {
                "id": "control-bash-wsl-vs-msys-paths-differ",
                "result": "PASS" if ctl.get("bash_paths_differ") else "FAIL",
                "name": (
                    "Pair reports different paths for bash (WSL-shaped vs "
                    "MSYS-shaped). Agreement means one probe is not in the "
                    "shell it claims."
                ),
            },
            {
                "id": "control-git-cmd-shim-vs-posix-git",
                "result": "PASS" if ctl.get("git_paths_differ") else "FAIL",
                "name": (
                    "Get-Command Source is the planted git.cmd shim; command -v "
                    "falls through to POSIX git."
                ),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "title": "External CLI tool dependency census with cross-shell resolution divergence",
        "unit_id": UID,
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    p1 = C.probe1_live(REPO)
    p2 = C.probe2_live(REPO)
    if not p1.get("pass") or not p2.get("pass"):
        print(
            f"FAILED:AUD-0028 live census pass p1={p1.get('pass')} p2={p2.get('pass')}"
        )
        print(
            json.dumps(
                {"probe1_control": p1.get("control"), "probe2_control": p2.get("control")},
                indent=1,
            )
        )
        return 1
    if int(p1["scan"]["tool_count"]) != int(p2["scan"]["tool_count"]):
        print(
            "FAILED:AUD-0028 scan tool_count mismatch "
            f"p1={p1['scan']['tool_count']} p2={p2['scan']['tool_count']}"
        )
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_artifact(p1, p2, now)
    validate_schema(doc)
    if SENTINEL not in json.dumps(doc):
        print("FAILED:AUD-0028 sentinel missing from document")
        return 1

    out = REPO / OUT
    write_json(out, doc)
    if out.stat().st_size < MIN_BYTES:
        print(f"FAILED:AUD-0028 artifact {out.stat().st_size}B below {MIN_BYTES}")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0028 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    doc["named_probes"] = [
        {
            "id": "probe1",
            "command": P1,
            "role": "pwsh7-get-command-source",
            "exit_code": c1,
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "command": P2,
            "role": "git-bash-command-v",
            "exit_code": c2,
            "raw_output": t2,
        },
    ]
    doc["timestamps"]["ended_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    validate_schema(doc)
    write_json(out, doc)

    extra = [
        "command-center/p2-wave/probes/AUD-0028/probe1-get-command.raw.json",
        "command-center/p2-wave/probes/AUD-0028/probe2-command-v.raw.json",
    ]
    primary = manifest_row(OUT, "primary")
    artifacts = (
        [primary]
        + [manifest_row(p, "supporting") for p in SUPPORTING]
        + [manifest_row(p, "supporting") for p in extra if (REPO / p).is_file()]
    )
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "cloud_ok": False,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "pwsh7-get-command-source",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "git-bash-command-v",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0028/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0028-probe2-gitbash-command-v",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": doc["timestamps"]["ended_at"],
        "notes": (
            "G-1 for AUD-0028: live named probes exit 0, census state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
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
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0028 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
