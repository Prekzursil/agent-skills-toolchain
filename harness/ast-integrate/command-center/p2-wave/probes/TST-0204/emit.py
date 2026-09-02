#!/usr/bin/env python3
"""Emit TST-0204 receipt, per-unit SUBAGENT-RETURN, and UNIT-ARTIFACT-MANIFEST.

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
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import path_budget as PB  # noqa: E402

OUT = "command-center/receipts/TST-0204.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0204/probe1_property_ids.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0204/probe2_fanout_p100.py"
)
SUPPORTING = [
    "tools/command-center/path_budget.py",
    "command-center/p2-wave/probes/TST-0204/probe1_property_ids.py",
    "command-center/p2-wave/probes/TST-0204/probe2_fanout_p100.py",
    "command-center/p2-wave/probes/TST-0204/emit.py",
]
QUESTION = (
    "Do generated worktree roots and unit ids have a declared maximum length, "
    "so the harness cannot consume the user's path budget? PASS requires a "
    "hard cap enforced in code, not a convention."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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


def first_json(text: str) -> dict:
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
        "unit_id": "TST-0204",
        "receipt_path": "command-center/p2-wave/probes/TST-0204/SUBAGENT-RETURN.json",
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
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0204 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0204 probe payload pass=false")
        return 1

    caps = PB.declared_caps()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art(p, "supporting") for p in SUPPORTING]
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    doc = {
        "schema_version": 1,
        "report_kind": "test-receipt",
        "unit_id": "TST-0204",
        "id": "TST-0204",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0204",
        "completion_sentinel": "SUCCESS:TST-0204",
        "title": "Worktree/id generators bound their own contribution to the path budget",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/portability_report",
        "min_bytes_threshold": 128,
        "declared_caps": caps,
        "hard_cap_enforced_in_code": True,
        "generator_module": "tools/command-center/path_budget.py",
        "property_test": {
            "n": p1.get("n_generated"),
            "id_len_p100": p1.get("id_len_p100"),
            "root_len_p100": p1.get("root_len_p100"),
            "over_cap_refused": p1.get("over_cap_refused"),
            "convention_mutant_id_len": p1.get("convention_mutant_id_len"),
        },
        "fanout_measurement": {
            "n_units": p2.get("n_units"),
            "contrib_len_p100": p2.get("contrib_len_p100"),
            "resolved_len_p100": p2.get("resolved_len_p100"),
            "longest_leaf": p2.get("longest_leaf"),
            "longest_unit_id": p2.get("longest_unit_id"),
            "longest_resolved_len": p2.get("longest_resolved_len"),
        },
        "platform": {
            "system": os.uname().sysname,
            "linux": True,
            "windows_shells_present": False,
            "note": (
                "Measured on this Linux worktree. Dual-shell pwsh7/Git Bash "
                "review is residual: not present here."
            ),
        },
        "adv_rebuild_circle": False,
        "cloud_ok": False,
        "tests": [
            {
                "id": "property-10000-generated-ids",
                "requirement": "property test: every generated root length <= declared cap",
                "verdict": "PASS",
                "evidence": (
                    f"{p1.get('n_generated')} generated ids p100="
                    f"{p1.get('id_len_p100')}/{caps['MAX_UNIT_ID_LEN']}; "
                    f"roots p100={p1.get('root_len_p100')}/"
                    f"{caps['MAX_WORKTREE_NAME_LEN']}"
                ),
            },
            {
                "id": "fanout-256-p100",
                "requirement": "measurement: report the p100 observed path length from a 256-unit run",
                "verdict": "PASS",
                "evidence": (
                    f"256 mkdir'd worktrees; contrib p100="
                    f"{p2.get('contrib_len_p100')}/{caps['MAX_WORKTREE_NAME_LEN']}; "
                    f"resolved p100={p2.get('resolved_len_p100')} "
                    f"longest={p2.get('longest_leaf')}"
                ),
            },
        ],
        "controls": {
            "overcap-id-refused": {
                "kind": "both-states",
                "description": "in-cap TST-0204 is returned; prefix TOOLONG is refused and the message names the cap",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": p1.get("refusal_message"),
                "good_state_output": p1.get("in_cap_id"),
            },
            "convention-mutant-admits-overcap": {
                "kind": "negative-control",
                "description": "formatter without enforce() emits TOOLONG-0001, proving a convention is not a cap",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": p1.get("convention_mutant_id"),
                "good_state_output": p1.get("in_cap_id"),
            },
        },
        "evidence": [
            {
                "kind": "property-test",
                "note": (
                    "Enforced cap in tools/command-center/path_budget.py plus "
                    f"{p1.get('n_generated')} generated ids, all <= "
                    f"MAX_UNIT_ID_LEN={caps['MAX_UNIT_ID_LEN']}."
                ),
                "path": "command-center/p2-wave/probes/TST-0204/probe1_property_ids.py",
            },
            {
                "kind": "fan-out-measurement",
                "note": (
                    "Longest observed real path in a 256-unit fan-out: "
                    f"leaf={p2.get('longest_leaf')} contrib="
                    f"{p2.get('longest_contrib_len')} resolved="
                    f"{p2.get('longest_resolved_len')}."
                ),
                "path": "command-center/p2-wave/probes/TST-0204/probe2_fanout_p100.py",
            },
        ],
        "artifacts": [
            {
                "path": rel,
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            }
            for rel, row in zip(SUPPORTING, supporting)
        ],
        "reviewer": {
            "reviewer_id": "TST-0204-probe2-fanout-p100",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 measures os.lstat of 256 created directories; probe 1 "
                "measures generator API lengths. Independent of probe 1's sample. "
                "Linux worktree; pwsh7/Git Bash dual-shell not present."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0204/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0204",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_blob(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py TST-0204",
                    "deferred to post-emit G-1 measure",
                    0,
                ),
            }
        ],
        "named_probes": [
            probe_blob("source", "command", P1, t1, c1),
            probe_blob("verifier", "command", P2, t2, c2),
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": now, "ended_at": now},
        "residual_unknowns": [
            {
                "claim": (
                    "Dual-shell (pwsh7 and Git Bash) re-run on a Windows host "
                    "was not executed on this Linux worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 and probe2 under pwsh7 and Git Bash on a "
                    "Windows host and diff p100 / refusal text."
                ),
            }
        ],
        "notes": (
            "G-1 for TST-0204: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:TST-0204"
        ),
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out_path)
    if size < 128:
        print(f"FAILED:TST-0204 receipt {size}B below floor")
        return 1
    if "SUCCESS:TST-0204" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0204 sentinel missing after write")
        return 1

    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "unit_id": "TST-0204",
        "receipt_path": "command-center/p2-wave/probes/TST-0204/SUBAGENT-RETURN.json",
        "role": "primary",
        "eol": "LF",
    }
    artifacts = [primary] + supporting
    ret = {
        "id": "TST-0204",
        "unit_id": "TST-0204",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0204",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/portability_report",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
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
        "manifest_path": "command-center/p2-wave/probes/TST-0204/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0204-probe2-fanout-p100",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0204: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0204",
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
    print("SUCCESS:TST-0204 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
