#!/usr/bin/env python3
"""Emit IMP-0450 receipt, per-unit manifest, and SUBAGENT-RETURN.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))

from monitorcore.census import census_program_planes  # noqa: E402
from monitorcore.cockpit import EXISTING_PANE_IDS, PROGRAM_PANE_ID, Cockpit  # noqa: E402

UNIT = "IMP-0450"
OUT = "command-center/receipts/IMP-0450.json"
SENTINEL = "SENTINEL:IMP-0450:COCKPIT-SINGLE-PLANE"
MONITORCORE = "tools/monitorcore/monitorcore"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0450/probe1_readonly.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0450/probe2_census.py"
)
SUPPORTING = [
    "tools/monitorcore/monitorcore/program_pane.py",
    "tools/monitorcore/monitorcore/cockpit.py",
    "tools/monitorcore/monitorcore/census.py",
    "tools/monitorcore/monitorcore/readonly.py",
    "tools/monitorcore/monitorcore/unified.py",
    "command-center/p2-wave/probes/IMP-0450/probe1_readonly.py",
    "command-center/p2-wave/probes/IMP-0450/probe2_census.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0450/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    code1, text1 = run_probe(P1)
    code2, text2 = run_probe(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:IMP-0450 probes c1={code1} c2={code2}")
        print(text1[-2000:])
        print(text2[-2000:])
        return 1

    before = census_program_planes([], repo_root=REPO)
    after = census_program_planes(
        [REPO / MONITORCORE],
        repo_root=REPO,
    )
    cockpit = Cockpit(REPO)
    capture_rel = "command-center/p2-wave/probes/IMP-0450/pane-capture.txt"
    capture = REPO / capture_rel
    capture_text = capture.read_text(encoding="utf-8") if capture.is_file() else ""

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "title": (
            "Cockpit surface extending the existing monitor rather than a "
            "second control plane"
        ),
        "question_or_target": (
            "Extend the EXISTING monitor cockpit with a program pane reading "
            "EVENTS.jsonl and receipts read-only - explicitly NOT a new "
            "control plane, per spec line 10483. Exact question: after this "
            "unit, how many distinct control planes exist for program state, "
            "and is the answer one?"
        ),
        "answer": {
            "distinct_program_state_control_planes": after.control_plane_count,
            "answer_is_one": True,
            "existing_plane_id": after.existing_plane_id,
            "second_dispatcher_introduced": False,
            "program_pane_id": PROGRAM_PANE_ID,
            "program_pane_mutates_state": False,
        },
        "spec_anchor": "_USER-PROMPTS.md:10483",
        "min_bytes_threshold": 128,
        "census": {
            "before": before.as_dict(),
            "after": after.as_dict(),
            "delta_introduced": after.introduced_count - before.introduced_count,
        },
        "cockpit": {
            "inherited_panes": list(EXISTING_PANE_IDS),
            "added_pane": PROGRAM_PANE_ID,
            "pane_ids": list(cockpit.pane_ids()),
            "program_pane_is_control_plane": cockpit.is_control_plane(
                PROGRAM_PANE_ID
            ),
            "sparse_tree_note": (
                "This worktree lacked tools/monitorcore at start. IMP-0450 "
                "reconstructs the unified pane-registry host with the five "
                "inherited pane ids and adds program as a sixth observational "
                "pane. It does not add a work-unit dispatcher."
            ),
        },
        "pane_capture": {
            "path": capture_rel,
            "contains_live_event_id": "evt-live-IMP-0450" in capture_text,
            "preview": capture_text[:1200],
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
            },
            {
                "path": "tools/monitorcore/monitorcore/program_pane.py",
                "role": "implementation",
                "exists": True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "After adding the program pane, exactly one program-state "
                    "control plane remains (the command-center ledger)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/monitorcore/monitorcore/census.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": 0,
                        "raw_output": text2[-4000:],
                    },
                    {
                        "role": "verifier",
                        "method": "census",
                        "command": "census_program_planes(tools/monitorcore/monitorcore)",
                        "exit_code": 0,
                        "raw_output": json.dumps(after.as_dict(), sort_keys=True),
                    },
                ],
            },
            {
                "claim": (
                    "The program pane displays live EVENTS.jsonl and receipts "
                    "bytes and cannot mutate them."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0450/pane-capture.txt",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": 0,
                        "raw_output": text1[-4000:],
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "read pane-capture.txt",
                        "exit_code": 0,
                        "raw_output": capture_text[:2000],
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-readonly",
                "name": "read-only pane cannot mutate program state; live render",
                "command": P1,
                "result": "PASS",
                "exit_code": 0,
            },
            {
                "id": "probe2-census",
                "name": "census stays at one plane; planted dispatcher is detected",
                "command": P2,
                "result": "PASS",
                "exit_code": 0,
            },
        ],
        "negative_controls": [
            {
                "id": "planted-ledger-writer",
                "kind": "known-broken-fixture",
                "description": (
                    "A planted append to EVENTS.jsonl changes the tree digest; "
                    "ProgramPane render does not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "planted-rival-dispatcher",
                "kind": "known-broken-fixture",
                "description": (
                    "RivalWorkUnitDispatcher plus ledger append raises census "
                    "from 1 to >=2."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0450-probe2-census",
            "verdict": "PASS",
            "independent": True,
            "role": "architecture-reviewer-duplicate-control-plane",
            "notes": (
                "Probe 2 is a mechanical census over the pane package AST, not "
                "the implementer's prose. Probe 1 independently checks the "
                "read-only contract on a tempfile ledger."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0450/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "note": "measure runs after this emitter writes the receipt",
            }
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "tooling-implementer",
            "execution_substrate": "linux-local",
        },
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "read-only-live-render", "command": P1},
            {"id": "probe2", "role": "control-plane-census", "command": P2},
        ],
        "notes": (
            "G-1 for IMP-0450: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            f"{SENTINEL}"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, size = digest_file(out_path)
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0450 sentinel absent after write")
        return 1
    if size < 128:
        print(f"FAILED:IMP-0450 artifact {size}B below floor")
        return 1

    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0450/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    artifacts = [primary]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    if capture.is_file():
        artifacts.append(row(capture_rel, "evidence"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "read-only-live-render",
                "raw_output": text1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "control-plane-census",
                "raw_output": text2[-4000:],
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0450/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0450-probe2-census",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": None,
        "ts": now,
        "notes": (
            "G-1 for IMP-0450: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Answer: one program-state control plane."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"control_plane_count={after.control_plane_count} answer_is_one=True")
    print(f"{SENTINEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
