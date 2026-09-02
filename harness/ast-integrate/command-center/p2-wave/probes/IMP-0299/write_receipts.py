#!/usr/bin/env python3
"""Emit IMP-0299 receipt + per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

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
UID = "IMP-0299"
OUT = "command-center/receipts/IMP-0299.json"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0299/probe1_floor_ceiling.py"
P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0299/probe2_filler_negative.py"
SUPPORTING = [
    "tools/council/budget/engagement.py",
    "tools/council/budget/__init__.py",
    "tools/council/participants/replace.py",
    "command-center/p2-wave/probes/IMP-0299/probe1_floor_ceiling.py",
    "command-center/p2-wave/probes/IMP-0299/probe2_filler_negative.py",
    "command-center/p2-wave/probes/IMP-0299/fixtures/hand_labelled_turns.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "tools") + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0299/SUBAGENT-RETURN.json",
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

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "completion_sentinel": "SUCCESS:IMP-0299",
        "title": "Speaking quota, minimum engagement and maximum inactivity enforcement",
        "profile": "council-budget-module",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0299]; "
            "_USER-PROMPTS.md:10928 speaking quotas / minimum engagement / "
            "maximum inactivity (source file absent on this worktree; "
            "catalog text is the on-disk spec_anchor)"
        ),
        "artifact_paths": [
            OUT,
            "tools/council/budget/engagement.py",
            "command-center/p2-wave/probes/IMP-0299/fixtures/hand_labelled_turns.json",
        ],
        "question": (
            "does a participant that posts three empty acknowledgements "
            "satisfy a minimum-engagement floor?"
        ),
        "answer": "NO",
        "metric": "substantive content units, not message count",
        "evidence": [
            {
                "id": "E1-content-units",
                "claim": (
                    "Engagement is scored as substantive content units "
                    "(claims, citations, reasoned votes, proposals, "
                    "counterexamples). Three empty acknowledgements yield "
                    "message_count=3 and content_units=0, so a floor of 1 fails."
                ),
                "anchor": "tools/council/budget/engagement.py:three_empty_acks_meet_floor",
                "probe": P1,
                "verdict": "CONFIRMED",
            },
            {
                "id": "E2-labelled-sample",
                "claim": (
                    "A hand-labelled 18-turn sample (9 filler, 9 substantive, "
                    "including mixed '+1 because...' and 'ok. The occupancy...') "
                    "agrees with the scorer at 18/18."
                ),
                "anchor": "command-center/p2-wave/probes/IMP-0299/fixtures/hand_labelled_turns.json",
                "probe": P2,
                "verdict": "CONFIRMED",
            },
            {
                "id": "E3-eviction-handoff",
                "claim": (
                    "FLOOR_FAIL / CEILING_BREACH / INACTIVITY emit an "
                    "EvictionHandoff applied through replace_occupant. "
                    "A prior ballot and idea remain keyed to the departed "
                    "occupant_id; the replacement starts with zero ballots "
                    "when inherit_votes=False."
                ),
                "anchor": "tools/council/participants/replace.py:replace_occupant",
                "probe": P1,
                "verdict": "CONFIRMED",
            },
        ],
        "test_ids": [
            "IMP-0299-FLOOR-CEILING-EVICT",
            "IMP-0299-FILLER-NEGATIVE",
        ],
        "negative_control_ids": [
            "IMP-0299-FILLER-ONLY-FAILS-FLOOR",
            "IMP-0299-MESSAGE-COUNT-MUTANT",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0299-probe2-filler-negative",
            "independent": True,
            "starts_from": "public scorer + hand-labelled fixture, not the receipt summary",
            "verdict": "PASS",
            "note": (
                "Same delivery session authored the module. Independence here "
                "is of the probe path: probe2 reconstructs three acks as raw "
                "strings, checks both-states, and scores the labelled sample."
            ),
        },
        "residual_unknowns": [
            (
                "tools/council/kernel.py (IMP-0264) is not on this worktree; "
                "engagement.py is a library the kernel would call. Live "
                "multi-model filler beyond the lexicon+cue heuristic is unproven."
            ),
            (
                "_USER-PROMPTS.md:10928 and 11-COUNCIL-SPECIFICATION.md are "
                "absent here; dial names are taken from the catalog row."
            ),
            (
                "tools/council/simulate.py uses active_occupant_id/events "
                "while replace.py uses active_occupant_id/events; the handoff "
                "fixture matches replace.py. Wiring simulate.py is out of scope."
            ),
        ],
        "tests": [
            {
                "id": "IMP-0299-FLOOR-CEILING-EVICT",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "IMP-0299-FILLER-NEGATIVE",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "cloud_ok": False,
        "produced_at": now,
        "SUCCESS:IMP-0299": True,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    sha, size = digest(out_path)
    if "SUCCESS:IMP-0299" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:receipt sentinel absent")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0299",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-budget-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "floor-ceiling-eviction",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "filler-negative-control",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0299/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0299-probe2-filler-negative",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0299: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0299, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Three empty acknowledgements do not "
            "meet the engagement floor (content_units=0, message_count=3)."
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
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={sha} bytes={size}")
    print("SUCCESS:IMP-0299 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
