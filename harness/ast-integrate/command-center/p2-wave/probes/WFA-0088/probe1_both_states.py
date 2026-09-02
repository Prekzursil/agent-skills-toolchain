#!/usr/bin/env python3
"""WFA-0088 probe 1: both-states hang injection.

A: repaired pipelines — one hung unit, cohort still completes within the
   per-agent deadline with a recorded partial (TIMEOUT -> null).
B: pre-fix wait-all — the same hang is still RUNNING after a wait strictly
   longer than that deadline, so the barrier has not resolved.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from wfa_fanout.pipeline import (  # noqa: E402
    BROKEN_WAIT_S,
    DEADLINE_S,
    HANG_ID,
    MODE_BROKEN_WAIT_ALL,
    MODE_REPAIRED,
    N_UNITS,
    REPAIRED_MAX_S,
    STATUS_OK,
    STATUS_RUNNING,
    STATUS_TIMEOUT,
    load_unit_records,
    run_cohort,
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0088-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfa0088-p1-") as tmp:
        tmp_path = Path(tmp)
        broken_dir = tmp_path / "broken"
        repaired_dir = tmp_path / "repaired"

        broken = run_cohort(
            MODE_BROKEN_WAIT_ALL,
            broken_dir,
            wait_limit_s=BROKEN_WAIT_S,
        )
        repaired = run_cohort(MODE_REPAIRED, repaired_dir)

        if broken.get("barrier_resolved") is True:
            return fail("broken wait-all resolved; hang did not block the cohort")
        if broken.get("elapsed_s", 0) < BROKEN_WAIT_S * 0.90:
            return fail(
                f"broken elapsed {broken.get('elapsed_s')} "
                f"< 0.90*{BROKEN_WAIT_S}; did not wait past the deadline"
            )
        hang_broken = next(
            (r for r in broken["records"] if r["unit_id"] == HANG_ID), None
        )
        if hang_broken is None or hang_broken.get("status") != STATUS_RUNNING:
            return fail(f"broken hang status={hang_broken}")
        if hang_broken.get("elapsed_s", 0) <= DEADLINE_S:
            return fail(
                f"broken hang elapsed {hang_broken.get('elapsed_s')} "
                f"did not exceed per-agent deadline {DEADLINE_S}"
            )

        if repaired.get("barrier_resolved") is not True:
            return fail("repaired barrier did not resolve on the partial")
        if repaired.get("elapsed_s", 0) > REPAIRED_MAX_S:
            return fail(
                f"repaired elapsed {repaired.get('elapsed_s')} "
                f"> {REPAIRED_MAX_S}; cohort still blocked"
            )
        if repaired.get("elapsed_s", 0) >= broken.get("elapsed_s", 0):
            return fail(
                f"repaired elapsed {repaired.get('elapsed_s')} "
                f">= broken {broken.get('elapsed_s')}"
            )
        if repaired.get("elapsed_s", 0) > DEADLINE_S + 0.45:
            return fail(
                f"repaired elapsed {repaired.get('elapsed_s')} "
                f"exceeds per-agent deadline plus slack"
            )

        ok_ids = list(repaired.get("ok_ids") or [])
        timeout_ids = list(repaired.get("timeout_ids") or [])
        null_ids = list(repaired.get("null_ids") or [])
        if HANG_ID in ok_ids:
            return fail("hung unit recorded OK")
        if timeout_ids != [HANG_ID]:
            return fail(f"timeout_ids={timeout_ids} want [{HANG_ID}]")
        if HANG_ID not in null_ids:
            return fail(f"null_ids={null_ids} missing hang")
        want_ok = N_UNITS - 1
        if len(ok_ids) != want_ok:
            return fail(f"ok_ids={ok_ids} want {want_ok} siblings")

        hang_rep = next(r for r in repaired["records"] if r["unit_id"] == HANG_ID)
        if hang_rep.get("payload") is not None or hang_rep.get("null") is not True:
            return fail(f"hang payload was not null: {hang_rep}")
        if hang_rep.get("reason_id") != "per-agent-deadline":
            return fail(f"hang reason_id={hang_rep.get('reason_id')}")

        disk = load_unit_records(repaired_dir)
        if len(disk) != N_UNITS:
            return fail(f"durable files={len(disk)} want {N_UNITS}")
        disk_ok = [r["unit_id"] for r in disk if r.get("status") == STATUS_OK]
        disk_to = [r["unit_id"] for r in disk if r.get("status") == STATUS_TIMEOUT]
        if sorted(disk_ok) != sorted(ok_ids):
            return fail(f"disk OK {disk_ok} != barrier {ok_ids}")
        if disk_to != [HANG_ID]:
            return fail(f"disk timeout {disk_to}")
        barrier_path = repaired_dir / "barrier.json"
        if not barrier_path.is_file():
            return fail("repaired barrier.json missing")
        barrier = json.loads(barrier_path.read_text(encoding="utf-8"))
        if barrier.get("partial") is not True:
            return fail("barrier.json did not record a partial")
        if (broken_dir / "units").exists() and any(
            (broken_dir / "units").glob("*.json")
        ):
            return fail("broken wait-all wrote durable unit files")

        if not repaired.get("null_tolerant"):
            return fail("repaired barrier not marked null-tolerant")
        if not repaired.get("per_agent_deadline"):
            return fail("repaired barrier not marked per-agent deadline")
        if not repaired.get("write_as_you_go"):
            return fail("repaired barrier not marked write-as-you-go")

        out = {
            "pass": True,
            "probe": "probe1-both-states-hang",
            "unit_id": "WFA-0088",
            "deadline_s": DEADLINE_S,
            "broken": {
                "barrier_resolved": broken["barrier_resolved"],
                "elapsed_s": broken["elapsed_s"],
                "hang_status": hang_broken["status"],
                "hang_elapsed_s": hang_broken["elapsed_s"],
                "wait_limit_s": BROKEN_WAIT_S,
            },
            "repaired": {
                "barrier_resolved": repaired["barrier_resolved"],
                "elapsed_s": repaired["elapsed_s"],
                "ok_count": len(ok_ids),
                "timeout_ids": timeout_ids,
                "null_ids": null_ids,
                "durable_files": len(disk),
                "partial": True,
            },
            "both_states": {
                "hang_blocks_before_fix": True,
                "hang_does_not_block_after_fix": True,
            },
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"broken_elapsed={broken['elapsed_s']:.3f} "
            f"repaired_elapsed={repaired['elapsed_s']:.3f} "
            f"ok={len(ok_ids)} timeout={timeout_ids}"
        )
        print(
            "SUCCESS:WFA-0088-probe1 both-states hang blocks before, "
            "partial after"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
