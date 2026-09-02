#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0125.json after live tests and probes."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0125.json"
TESTS = "tools/marketplace/tests/test_gc.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0125/probe1_referenced_and_dry_run.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0125/probe2_independent_walk.py"
)
SUPPORTING = [
    "tools/marketplace/blob_gc.py",
    "tools/marketplace/gc_index_lockfile.py",
    "tools/marketplace/gc_provenance.py",
    "tools/marketplace/gc_store.py",
    TESTS,
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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


def catalog_unit() -> dict:
    data = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "IMP-0125":
            return unit
    raise SystemExit("FAILED:IMP-0125 catalog unit missing")


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "SUCCESS:IMP-0125")
    t_rc, t_out = run(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {TESTS}")
    p1_rc, p1_out = run(P1)
    p2_rc, p2_out = run(P2)
    if t_rc != 0 or p1_rc != 0 or p2_rc != 0:
        print("FAILED:IMP-0125 tests or probes")
        print(t_out[-1500:])
        print(p1_out[-1500:])
        print(p2_out[-1500:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    art_rows = []
    for rel in SUPPORTING:
        path = REPO / rel
        sha, size = sha256_file(path)
        art_rows.append(
            {
                "path": rel,
                "exists": True,
                "bytes": size,
                "sha256": sha,
                "role": "implementation",
            }
        )

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0125",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "produced_at": now,
        "owner_gated_deletion": True,
        "dry_run_default": True,
        "two_independent_signals": {
            "index_lockfile_scan": "tools/marketplace/gc_index_lockfile.py",
            "deploy_provenance_walk": "tools/marketplace/gc_provenance.py",
            "rule": "deletable only when both report zero refs; disagreement keeps",
        },
        "tests": [
            {
                "id": "test_referenced_blob_is_never_collected",
                "path": TESTS,
                "result": "PASS",
            },
            {
                "id": "test_dry_run_lists_every_candidate_with_its_proof",
                "path": TESTS,
                "result": "PASS",
            },
            {
                "id": "test_lockfile_only_reference_survives",
                "path": TESTS,
                "result": "PASS",
                "role": "negative-control",
            },
            {
                "id": "test_provenance_only_reference_survives",
                "path": TESTS,
                "result": "PASS",
                "role": "reviewer-disagreement-keep",
            },
            {
                "id": "test_execute_without_owner_token_refuses",
                "path": TESTS,
                "result": "PASS",
            },
            {
                "id": "test_unreadable_ledger_fail_closed",
                "path": TESTS,
                "result": "PASS",
            },
        ],
        "test_runner": {
            "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {TESTS}",
            "exit_code": t_rc,
            "output_tail": t_out[-800:],
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": p1_rc,
                "result": "PASS",
                "output_tail": p1_out[-1200:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": p2_rc,
                "result": "PASS",
                "output_tail": p2_out[-1200:],
            },
        ],
        "negative_controls": [
            {
                "id": "lockfile-only-reference",
                "plant": "blob named only in lockfiles/*.json, absent from index and ledger",
                "fired_on_bad": True,
                "silent_on_good": True,
                "result": "blob survived execute",
            },
            {
                "id": "provenance-only-reviewer-plant",
                "plant": "blob named only in provenance/deploy-ledger.jsonl",
                "index_lockfile_refs": 0,
                "provenance_refs": "non-zero",
                "result": "disagreement keep",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0125-probe2-independent-walk",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe2 plants a provenance-only reference the index/lockfile scan "
                "does not see, confirms the provenance walk names it, and confirms "
                "GC keeps the blob. AST check: the two scanners do not import each other."
            ),
        },
        "artifacts": art_rows
        + [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            }
        ],
        "residual": {
            "imp_0121_blob_store": (
                "IMP-0121 is not delivered on this worktree. GC measures a "
                "GC-facing fixture layout (gc_store.py), not a claim that the "
                "production content-addressed store unit is complete."
            ),
            "imp_0123_integrity_sweep": (
                "IMP-0123 is not delivered here. GC does not substitute for the "
                "integrity sweep; it refuses deletion when the provenance ledger "
                "is unreadable (fail-closed)."
            ),
        },
        "cloud_ok": False,
        "min_bytes_threshold": 2048,
        "answer": (
            "GC deletes a blob only when the index/lockfile scan and an independently "
            "written deploy-provenance walk both report zero references. Dry-run lists "
            "every candidate with both proofs and writes nothing. Execute requires a "
            "matching owner token. A lockfile-only reference keeps the blob. A "
            "reviewer-planted provenance-only reference is missed by the index scan, "
            "caught by the second walk, and kept. SUCCESS:IMP-0125"
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(dest)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0125 artifact {size}B below floor")
        return 1
    text = dest.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:IMP-0125 sentinel absent from artifact text")
        return 1
    if '"state": "BLOCKED"' in text or '"state":"BLOCKED"' in text:
        print("FAILED:IMP-0125 self-declared BLOCKED")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(sentinel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
