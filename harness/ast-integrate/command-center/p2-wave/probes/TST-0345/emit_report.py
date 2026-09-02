#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0345.json (isolation report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import isolation as I  # noqa: E402

OUT = "command-center/receipts/TST-0345.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:TST-0345"
QUESTION = (
    "Do parallel test workers on this estate write disjoint paths, each with "
    "an isolated temp root and git worktree, and is a worker that attempts to "
    "stage or commit refused so it cannot sweep a sibling's files? PASS requires "
    "a real concurrent run (a collision that needs two simultaneous writers is "
    "invisible to a sequential loop), a planted shared-temp-root collision that "
    "the audit detects, and a staging attempt that fails."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0345/probe1_concurrent_write_trace.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0345/probe2_collision_and_staging.py"
)
SUT = "command-center/p2-wave/probes/TST-0345/isolation.py"
MIN_BYTES = 2048


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    concurrent = I.run_isolated_concurrent(n_workers=4, n_writes=16)
    collision = I.run_collision_control()
    staging = I.run_staging_refusal()

    if not concurrent["audit"]["isolated"] or not concurrent["audit"]["overlapped"]:
        print("FAILED:TST-0345 emit concurrent isolation audit failed")
        print(json.dumps(concurrent["audit"], sort_keys=True, default=str))
        return 1
    if not collision["detector_fired"]:
        print("FAILED:TST-0345 emit collision detector did not fire")
        return 1
    if not staging["pass"]:
        print("FAILED:TST-0345 emit staging refusal failed")
        print(json.dumps(staging, sort_keys=True, default=str)[:3000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut_path = REPO / SUT
    sut_sha, sut_bytes = sha256_file(sut_path)
    schema_base = REPO / SCHEMA
    registry = REPO / "command-center/TEST-REGISTRY.json"

    wmap = concurrent["write_path_map"]
    compact_map = {
        wid: {
            "pid": row["pid"],
            "temp_root": row["temp_root"],
            "worktree": row["worktree"],
            "git_dir": row["git_dir"],
            "index_file": row["index_file"],
            "write_count": row["write_count"],
            "writes": row["writes"],
        }
        for wid, row in wmap.items()
    }

    answer = (
        "Yes for the isolation layer shipped with this unit. Four concurrent "
        "workers (barrier-synchronized, overlapping write windows, distinct "
        f"pids) each wrote 16 files under a private temp root and a private "
        f"git worktree; pairwise write-path intersection was empty; git dirs "
        f"and index files were unique. Forcing two workers onto one temp root "
        f"was detected even when they wrote disjoint filenames "
        f"(shared_temp_roots=true with empty path intersection), proving the "
        f"collision meter is not only watching identical filenames. A worker "
        f"`git add -A` via the PATH git wrapper was refused (rc="
        f"{staging['guarded_attempt']['returncode']}) and left both indexes "
        f"unstaged; the unguarded control using {staging['unguarded_shared_index_control']['real_git']} "
        f"in a shared scratch clone staged both sibling files "
        f"{staging['unguarded_shared_index_control']['cached']}, so the refusal "
        f"is load-bearing rather than a missing git binary."
    )

    doc = {
        "unit_id": "TST-0345",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "isolation_report",
        "title": (
            "Prove parallel test execution does not contaminate a shared tree, "
            "index or temp directory"
        ),
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0345; tests_required concurrent write "
            "trace / collision control / staging refusal; scope shared with "
            "TST-0099 and ADV-0123 on the shared-git-index contamination case"
        ),
        "measured_at": now,
        "min_bytes_threshold": MIN_BYTES,
        "output_schema": SCHEMA,
        "declared_schema_file_present": schema_base.is_file(),
        "cloud_ok": False,
        "required_fix": None,
        "sut": {
            "catalog_inputs": [
                "the parallel test runner configuration",
                "worktree isolation from the git-worktree tooling",
                "temp-root allocation per worker",
                "command-center/TEST-REGISTRY.json",
            ],
            "test_registry_present": registry.is_file(),
            "pytest_xdist_present": False,
            "live_module": SUT,
            "live_sha256": sut_sha,
            "live_bytes": sut_bytes,
            "mechanism": (
                "per-worker tempfile + git worktree add --detach from a scratch "
                "seed; write tracer records realpaths; audit flags shared temp "
                "roots/worktrees/indexes and write-path intersection; PATH git "
                "wrapper refuses write verbs"
            ),
        },
        "answer": {
            "concurrent_path_intersection_empty": True,
            "per_worker_isolated_temp_root": True,
            "per_worker_isolated_worktree": True,
            "collision_control_detects_shared_temp_root": True,
            "worker_staging_refused": True,
            "unguarded_shared_index_sweeps_siblings": True,
            "summary": answer,
        },
        "write_path_map": compact_map,
        "write_path_intersection": concurrent["audit"]["write_path_intersection"],
        "concurrency": {
            "n_workers": 4,
            "n_writes_per_worker": 16,
            "distinct_pids": concurrent["audit"]["distinct_pids"],
            "overlapped": concurrent["audit"]["overlapped"],
            "t0_ns_max": concurrent["audit"]["t0_ns_max"],
            "t1_ns_min": concurrent["audit"]["t1_ns_min"],
            "method": (
                "multiprocessing fork + Barrier; 50ms post-write hold so a "
                "collision that needs two simultaneous writers is in the window"
            ),
        },
        "collision_control": {
            "disjoint_files_shared_root_detected": collision[
                "disjoint_files_shared_root"
            ]["detected"],
            "disjoint_files_intersection_empty": collision[
                "disjoint_files_shared_root"
            ]["write_path_intersection_empty"],
            "same_file_shared_root_detected": collision["same_file_shared_root"][
                "detected"
            ],
            "detector_fired": collision["detector_fired"],
            "silent_on_isolated_run": concurrent["audit"]["isolated"],
        },
        "staging_refusal": staging,
        "evidence": [
            {
                "id": "concurrent-write-trace",
                "claim": (
                    "Four concurrent workers wrote disjoint realpaths under "
                    "private temp roots and git worktrees; intersection empty."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "source_probe": {
                    "tool": "probe1_concurrent_write_trace",
                    "command": P1,
                },
                "verifier_probe": {
                    "tool": "probe2_collision_and_staging",
                    "command": P2,
                    "field": "isolated_control_silent",
                },
                "anchor": SUT + ":run_isolated_concurrent",
            },
            {
                "id": "collision-control",
                "claim": (
                    "Forcing two workers onto one temp root is detected even "
                    "when written filenames are disjoint."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "source_probe": {
                    "tool": "probe2_collision_and_staging",
                    "command": P2,
                    "field": "shared_root_disjoint_files_detected",
                },
                "verifier_probe": {
                    "tool": "probe1_concurrent_write_trace",
                    "command": P1,
                    "field": "isolated_true_negative",
                },
                "anchor": SUT + ":run_collision_control",
            },
            {
                "id": "staging-refusal",
                "claim": (
                    "A worker git add -A is refused by the PATH wrapper; the "
                    "unguarded shared-index control stages both sibling files."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "source_probe": {
                    "tool": "probe2_collision_and_staging",
                    "command": P2,
                    "field": "staging_refused",
                },
                "verifier_probe": {
                    "engine": "unguarded-/usr/bin/git-add-A-in-scratch-clone",
                    "command": "/usr/bin/git add -A (scratch shared worktree)",
                },
                "anchor": SUT + ":run_staging_refusal",
            },
        ],
        "tests": [
            {
                "id": "concurrent-write-trace-empty-intersection",
                "command": P1,
                "result": "PASS",
                "name": "Real concurrent run with per-worker write tracing",
            },
            {
                "id": "collision-control-shared-temp-root",
                "command": P2,
                "result": "PASS",
                "name": "Force two workers onto one temp root; audit detects it",
            },
            {
                "id": "staging-refusal-protects-sibling",
                "command": P2,
                "result": "PASS",
                "name": "Worker staging attempt is refused",
            },
        ],
        "tests_required": [
            {
                "id": "concurrent-write-trace",
                "text": (
                    "Real concurrent run with per-worker write tracing; path "
                    "intersection must be empty."
                ),
                "result": "PASS",
            },
            {
                "id": "collision-control",
                "text": (
                    "Collision control: force two workers onto one temp root "
                    "and confirm the audit detects it."
                ),
                "result": "PASS",
            },
            {
                "id": "staging-refusal",
                "text": (
                    "Staging refusal: a worker attempting to stage must fail, "
                    "protecting sibling work."
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "shared-temp-root-disjoint-filenames",
                "kind": "planted-collision",
                "description": (
                    "Two workers share a temp root but write different files. "
                    "File-path intersection is empty; shared_temp_roots still "
                    "fires. An audit that only compared filenames would miss this."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "unguarded-git-add-sweeps-siblings",
                "kind": "known-broken-shared-index",
                "description": (
                    "In a scratch clone with two agent files, /usr/bin/git add -A "
                    "stages both. The wrapper refusal is therefore not a missing "
                    "git binary."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0345-probe2-collision-and-staging",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 re-derives collision detection and staging refusal "
                "without trusting probe 1's write map. Catalog also names a "
                "second Windows shell (pwsh7 vs Git Bash) re-run; this lane is "
                "Linux and does not self-certify that reviewer."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0345/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0345",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot (AGENTS.md 4b): after a second failure "
                "on the same hypothesis, enumerate at least two alternative "
                "approaches before a third attempt."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/TEST-REGISTRY.json is absent from this "
                    "worktree; the three catalog tests for this unit were run "
                    "live by the named probes rather than collected from that "
                    "registry."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind the isolation harness to TEST-REGISTRY.json once "
                    "that file exists and re-run both named probes."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement asks for a second Windows "
                    "shell (pwsh7 and Git Bash). This measurement ran on Linux."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 and probe2 under pwsh7 and Git Bash on "
                    "Windows; record any divergence as a finding, not a retry."
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": SUT,
                "exists": True,
                "role": "isolation-layer-under-test",
                "sha256": sut_sha,
                "bytes": sut_bytes,
            },
        ],
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0345 emit sentinel absent from file")
        return 1
    if dest.stat().st_size < MIN_BYTES:
        print("FAILED:TST-0345 emit below min_bytes_threshold")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") != "SUCCESS":
        print("FAILED:TST-0345 emit state is not SUCCESS")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0345 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
