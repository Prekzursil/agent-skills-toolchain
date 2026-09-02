#!/usr/bin/env python3
"""WFA-0088 probe 2: durable partials + phase-only deadline is not enough.

Independent of probe 1's wait-all control:

  1. write-as-you-go: interrupt after N OK results; sibling files are on disk.
     memory-only twin of the same interrupt leaves zero files.
  2. phase-only deadline: siblings completed in RAM are discarded; zero
     durable unit files. A phase clock still loses every sibling's work.
  3. static scan: the repaired path fsyncs inside the unit pipeline; the
     broken wait-all path does not.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from wfa_fanout.pipeline import (  # noqa: E402
    DEADLINE_S,
    HANG_ID,
    MODE_MEMORY_ONLY,
    MODE_PHASE_DEADLINE,
    MODE_REPAIRED,
    STATUS_OK,
    STATUS_TIMEOUT,
    load_unit_records,
    run_cohort,
)

SRC = REPO / "tools" / "wfa_fanout" / "pipeline.py"
KILL_AFTER = 4


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0088-probe2 {msg}")
    return 1


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise SystemExit(f"FAILED:WFA-0088-probe2 missing def {name}")


def _calls_named(fn: ast.FunctionDef, name: str) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == name:
                return True
    return False


def static_scan() -> dict:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    pipeline = _function(tree, "_pipeline_one")
    run = _function(tree, "run_cohort")
    writes_in_pipeline = _calls_named(pipeline, "atomic_write_json")
    # broken wait-all must not call atomic_write_json (durability is the repair).
    run_src = ast.get_source_segment(SRC.read_text(encoding="utf-8"), run) or ""
    broken_slice = ""
    if "MODE_BROKEN_WAIT_ALL" in run_src:
        broken_slice = run_src.split("MODE_BROKEN_WAIT_ALL", 1)[1].split(
            "MODE_PHASE_DEADLINE", 1
        )[0]
    if "atomic_write_json" in broken_slice:
        raise SystemExit(
            "FAILED:WFA-0088-probe2 broken wait-all slice writes unit files"
        )
    if not writes_in_pipeline:
        raise SystemExit(
            "FAILED:WFA-0088-probe2 _pipeline_one does not call atomic_write_json"
        )
    # Per-agent deadline is stop.wait(timeout=...) inside _pipeline_one when
    # self_timeout, not a single phase wait on the whole cohort.
    has_self_timeout = False
    for node in ast.walk(pipeline):
        if isinstance(node, ast.If):
            test = ast.dump(node.test)
            if "self_timeout" in test:
                has_self_timeout = True
    if not has_self_timeout:
        raise SystemExit(
            "FAILED:WFA-0088-probe2 _pipeline_one has no self_timeout branch"
        )
    return {
        "pipeline_calls_atomic_write_json": writes_in_pipeline,
        "broken_slice_writes": False,
        "self_timeout_branch": has_self_timeout,
        "source": "tools/wfa_fanout/pipeline.py",
    }


def main() -> int:
    scan = static_scan()
    with tempfile.TemporaryDirectory(prefix="wfa0088-p2-") as tmp:
        tmp_path = Path(tmp)
        wayg_dir = tmp_path / "wayg"
        mem_dir = tmp_path / "memory"
        phase_dir = tmp_path / "phase"
        full_dir = tmp_path / "full"

        wayg = run_cohort(
            MODE_REPAIRED, wayg_dir, kill_after_n_ok=KILL_AFTER
        )
        if wayg.get("interrupted") is not True:
            return fail("write-as-you-go run was not interrupted")
        disk = load_unit_records(wayg_dir)
        ok_disk = [r for r in disk if r.get("status") == STATUS_OK]
        if len(ok_disk) < KILL_AFTER:
            return fail(
                f"write-as-you-go durable OK files={len(ok_disk)} want >={KILL_AFTER}"
            )
        for rec in ok_disk:
            if rec.get("payload") is None:
                return fail(f"{rec.get('unit_id')} OK payload missing")
            if rec.get("durable") is not True:
                return fail(f"{rec.get('unit_id')} OK not marked durable")

        mem = run_cohort(
            MODE_MEMORY_ONLY, mem_dir, kill_after_n_ok=KILL_AFTER
        )
        if mem.get("interrupted") is not True:
            return fail("memory-only run was not interrupted")
        mem_disk = load_unit_records(mem_dir)
        if mem_disk:
            return fail(f"memory-only interrupt left files {mem_disk}")
        if (mem_dir / "units").exists() and any((mem_dir / "units").glob("*.json")):
            return fail("memory-only units/ not empty")

        phase = run_cohort(MODE_PHASE_DEADLINE, phase_dir)
        if phase.get("barrier_resolved") is True:
            return fail("phase-deadline claimed the barrier resolved")
        if (phase.get("ram_completed_count") or 0) < KILL_AFTER:
            return fail(
                f"phase ram_completed_count={phase.get('ram_completed_count')} "
                f"want >={KILL_AFTER} (siblings finished in RAM)"
            )
        if (phase.get("phase_still_running") or 0) < 1:
            return fail("phase-deadline did not leave the hung unit running")
        phase_disk = load_unit_records(phase_dir)
        if phase_disk:
            return fail(f"phase-deadline flushed files {phase_disk}")
        lost = [r for r in phase["records"] if r.get("status") == "LOST"]
        if len(lost) != phase.get("n_units"):
            return fail(f"phase lost={len(lost)} n={phase.get('n_units')}")

        full = run_cohort(MODE_REPAIRED, full_dir)
        full_disk = load_unit_records(full_dir)
        if len(full_disk) != full.get("n_units"):
            return fail(f"full durable {len(full_disk)} != n {full.get('n_units')}")
        hang = next(r for r in full_disk if r["unit_id"] == HANG_ID)
        if hang.get("status") != STATUS_TIMEOUT or hang.get("payload") is not None:
            return fail(f"full hang record {hang}")
        siblings = [r for r in full_disk if r["unit_id"] != HANG_ID]
        if any(r.get("status") != STATUS_OK for r in siblings):
            return fail("full run lost a sibling after hang timeout")
        if not (full_dir / "partial.json").is_file():
            return fail("full run missing partial.json")

        out = {
            "pass": True,
            "probe": "probe2-durable-partial-and-phase-deadline",
            "unit_id": "WFA-0088",
            "deadline_s": DEADLINE_S,
            "write_as_you_go": {
                "interrupted": True,
                "durable_ok": len(ok_disk),
                "kill_after_n_ok": KILL_AFTER,
            },
            "memory_only": {
                "interrupted": True,
                "durable_files": len(mem_disk),
            },
            "phase_deadline": {
                "ram_completed_count": phase.get("ram_completed_count"),
                "phase_still_running": phase.get("phase_still_running"),
                "durable_files": len(phase_disk),
                "lost_count": len(lost),
            },
            "full_repaired": {
                "durable_files": len(full_disk),
                "hang_status": hang.get("status"),
                "sibling_ok": len(siblings),
            },
            "static": scan,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"wayg_ok={len(ok_disk)} mem_files={len(mem_disk)} "
            f"phase_ram={phase.get('ram_completed_count')} "
            f"phase_disk={len(phase_disk)} full_disk={len(full_disk)}"
        )
        print(
            "SUCCESS:WFA-0088-probe2 durable partial; phase deadline loses siblings"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
