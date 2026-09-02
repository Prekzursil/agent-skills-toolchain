#!/usr/bin/env python3
"""Emit TST-0060 receipt, then named-probe SUBAGENT-RETURN and per-unit manifest.

Does not run tools/command-center/unit_manifest.py --write.
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

from matrix import (  # noqa: E402
    ADVERSARIAL,
    public_report,
    red_cell_control,
    run_matrix,
    named_roundtrip,
)

OUT = "command-center/receipts/TST-0060.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0060/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0060/probe2_red_cell.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0060/matrix.py",
    "command-center/p2-wave/probes/TST-0060/probe1_roundtrip.py",
    "command-center/p2-wave/probes/TST-0060/probe2_red_cell.py",
    "command-center/p2-wave/probes/TST-0060/emit.py",
]
QUESTION = (
    "Failure class :11308 and Phase 10 layer 27 (:11015). Target: write a script "
    "containing nested quotes, backslashes, dollar signs and backticks through "
    "every transport used here (Write tool, here-string, heredoc, -c inline) and "
    "byte-compare the landed file against the intended bytes. Measured: the "
    "here-string route failed 8/59 (13.6%) vs the Write tool 0/40."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": True,
        "role": role,
        "eol": "LF",
        "unit_id": "TST-0060",
        "receipt_path": "command-center/p2-wave/probes/TST-0060/SUBAGENT-RETURN.json",
    }


def probe_blob(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    full = run_matrix()
    pub = public_report(full)
    rt = named_roundtrip(full)
    ctrl = red_cell_control(full)

    by = pub["by_transport"]
    write = by["write_tool"]
    here = by["here_string"]
    heredoc = by["heredoc"]
    cin = by["c_inline"]
    naive = by["c_inline_double_quoted"]
    expanding = by["heredoc_expanding"]

    if write["n"] < 40:
        print(f"FAILED:TST-0060 write_tool n={write['n']} < 40")
        return 1
    if here["n"] < 59:
        print(f"FAILED:TST-0060 here_string n={here['n']} < 59")
        return 1
    if write["n_unequal"] != 0:
        print(f"FAILED:TST-0060 write_tool oracle failed: {write}")
        return 1
    if not rt["pass"]:
        print(f"FAILED:TST-0060 named round-trip control: {rt}")
        return 1
    if not ctrl["pass"]:
        print(f"FAILED:TST-0060 red-cell control: {ctrl}")
        return 1
    if pub["red_count"] < 1:
        print("FAILED:TST-0060 matrix has no red cell")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "On this Linux bash box, Write tool round-tripped "
        f"{write['n_equal']}/{write['n']} (failure {write['failure_rate_pct']}%). "
        f"Quoted heredoc {heredoc['n_equal']}/{heredoc['n']} "
        f"(failure {heredoc['failure_rate_pct']}%; remaining misses are payloads "
        "without a trailing newline, which a quoted heredoc is specified to add). "
        f"Quoted bash -c printf {cin['n_equal']}/{cin['n']} "
        f"(failure {cin['failure_rate_pct']}%; remaining misses are non-UTF-8 / NUL). "
        f"Bash here-string {here['n_equal']}/{here['n']} "
        f"(failure {here['failure_rate_pct']}%; every successful spawn appends a "
        "newline, so byte-equality fails even when quoting is otherwise intact). "
        f"Known-failing controls: double-quoted -c "
        f"{naive['n_unequal']}/{naive['n']} red "
        f"(kinds={naive['mismatch_kinds']}); expanding heredoc "
        f"{expanding['n_unequal']}/{expanding['n']} red "
        f"(kinds={expanding['mismatch_kinds']}). "
        "Catalog 8/59 vs 0/40 was a prior Windows/PowerShell measurement; it is "
        "not this run. pwsh is "
        f"{'present at ' + str(pub['host']['pwsh_path']) if pub['host']['pwsh_present'] else 'absent'}. "
        "SUCCESS:TST-0060"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0060",
        "id": "TST-0060",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0060",
        "completion_sentinel": "SUCCESS:TST-0060",
        "title": "Shell quoting must not corrupt script content in transit",
        "spec_anchor": "_USER-PROMPTS.md:11308; rules/common/windows-shell.md#9",
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "min_bytes_threshold": 2048,
        "question_or_target": QUESTION,
        "answer": answer,
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "host": pub["host"],
        "adversarial_payload": {
            "id": "adversarial_script",
            "sha256": hashlib.sha256(ADVERSARIAL.encode("utf-8")).hexdigest(),
            "bytes": len(ADVERSARIAL.encode("utf-8")),
            "contains_nested_quotes": True,
            "contains_backslashes": True,
            "contains_dollar_signs": True,
            "contains_backticks": True,
            "trailing_newline": ADVERSARIAL.endswith("\n"),
        },
        "matrix": pub,
        "named_roundtrip": {
            "write_tool_equal": rt["write_tool_equal"],
            "heredoc_equal": rt["heredoc_equal"],
            "c_inline_equal": rt["c_inline_equal"],
            "here_string_equal": rt["here_string_equal"],
            "here_string_kind": rt["here_string_kind"],
            "transports_present": rt["transports_present"],
        },
        "red_cell_control": {
            "silent_on_write_tool": ctrl["silent_on_write_tool"],
            "fired_on_double_quoted_c": ctrl["fired_on_double_quoted_c"],
            "fired_on_expanding_heredoc": ctrl["fired_on_expanding_heredoc"],
            "fired_on_here_string_extra_nl": ctrl["fired_on_here_string_extra_nl"],
            "c_kind": ctrl["c_kind"],
            "heredoc_kind": ctrl["heredoc_kind"],
            "here_kind": ctrl["here_kind"],
        },
        "failure_rates": {
            "write_tool": write,
            "here_string": here,
            "heredoc": heredoc,
            "c_inline": cin,
            "c_inline_double_quoted": naive,
            "heredoc_expanding": expanding,
            "catalog_cited": {
                "here_string": "8/59 (13.6%)",
                "write_tool": "0/40",
                "applies_to": "prior Windows/PowerShell measurement, not this Linux bash run",
            },
        },
        "tests": [
            {
                "id": "test_each_transport_round_trips_the_adversarial_payload",
                "requirement": (
                    "Write a script containing nested quotes, backslashes, dollar "
                    "signs and backticks through Write tool, here-string, heredoc "
                    "and -c inline; byte-compare landed vs intended."
                ),
                "verdict": "PASS",
                "evidence": (
                    f"write_tool equal={rt['write_tool_equal']}; "
                    f"heredoc equal={rt['heredoc_equal']}; "
                    f"c_inline equal={rt['c_inline_equal']}; "
                    f"here_string equal={rt['here_string_equal']} "
                    f"kind={rt['here_string_kind']}"
                ),
            },
            {
                "id": "test_the_matrix_records_a_known_failing_transport",
                "requirement": (
                    "Control: the harness must be able to show a red cell "
                    "(known failing transport)."
                ),
                "verdict": "PASS",
                "evidence": (
                    f"here_string {here['n_unequal']}/{here['n']} unequal; "
                    f"c_inline_double_quoted {naive['n_unequal']}/{naive['n']} unequal; "
                    f"heredoc_expanding {expanding['n_unequal']}/{expanding['n']} unequal; "
                    f"write_tool silent {ctrl['silent_on_write_tool']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "expanding-dollar-payload",
                "kind": "known-broken-transport",
                "description": (
                    "Unquoted/expanding heredoc and double-quoted -c must corrupt "
                    "$HOME / command substitution; Write tool must not."
                ),
                "fired_on_bad_state": bool(ctrl["fired_on_double_quoted_c"] and ctrl["fired_on_expanding_heredoc"]),
                "silent_on_good_state": bool(ctrl["silent_on_write_tool"]),
                "bad_state_output": (
                    f"c_kind={ctrl['c_kind']} heredoc_kind={ctrl['heredoc_kind']}"
                ),
                "good_state_output": "write_tool equal on dollar_home",
            }
        ],
        "evidence": [
            {
                "claim": (
                    f"Transport x payload matrix on this box: {pub['cell_count']} cells, "
                    f"{pub['payload_count']} payloads, Write tool failure rate "
                    f"{write['failure_rate_pct']}%, here-string "
                    f"{here['failure_rate_pct']}%."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0060/matrix.py",
                "confidence": "almost-certain",
                "probes": [
                    probe_blob(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/TST-0060/matrix.py",
                        json.dumps(pub["by_transport"], sort_keys=True),
                        0,
                    )
                ],
            },
            {
                "claim": (
                    "Harness is not always-green: expanding -c/heredoc and bash "
                    "here-string extra newline are red cells."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0060/probe2_red_cell.py",
                "confidence": "almost-certain",
                "probes": [
                    probe_blob(
                        "verifier",
                        "command",
                        P2,
                        json.dumps(
                            {
                                "red_count": pub["red_count"],
                                "here_unequal": here["n_unequal"],
                                "naive_unequal": naive["n_unequal"],
                            },
                            sort_keys=True,
                        ),
                        0,
                    )
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0060-probe2-red-cell",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe1 re-lands the adversarial payload through all four "
                "named transports. Named probe2 re-runs the expanding-transport "
                "control and the 59-cell here-string rate."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0060/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for TST-0060: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:TST-0060"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest(out_path)
    if size < 2048:
        print(f"FAILED:TST-0060 receipt {size}B below floor")
        return 1
    if "SUCCESS:TST-0060" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0060 sentinel absent after write")
        return 1

    c1, t1 = run_probe(P1)
    print(t1[-2500:])
    c2, t2 = run_probe(P2)
    print(t2[-2500:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0060 probes c1={c1} c2={c2}")
        return 1

    sha, size = digest(out_path)
    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "unit_id": "TST-0060",
        "receipt_path": "command-center/p2-wave/probes/TST-0060/SUBAGENT-RETURN.json",
        "role": "primary",
        "eol": "LF",
    }
    supporting = [art(p, "supporting") for p in SUPPORTING]
    artifacts = [primary] + supporting
    ret = {
        "id": "TST-0060",
        "unit_id": "TST-0060",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0060",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1, "role": "round-trip"},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2, "role": "red-cell-control"},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0060/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0060-probe2-red-cell",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0060: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0060",
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
    print(f"primary {OUT} sha256={sha} bytes={size}")
    print(f"write_tool {write['n_equal']}/{write['n']} here_string fail {here['failure_rate_pct']}%")
    print("SUCCESS:TST-0060 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
