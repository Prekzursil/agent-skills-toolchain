#!/usr/bin/env python3
"""Named probe 1: empty harvest is FAILED even when the copy step exits 0.

Both-states: the live classifier fails the empty run; two mutants that treat
exit-0 or a pre-populated dest as SUCCESS do not. A probe silent on those
mutants would not detect the failure class this unit exists to close.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HARVEST = REPO / "tools" / "harvester"
sys.path.insert(0, str(HARVEST))

from harvest import run_harvest, transfer_tree  # noqa: E402
from postcondition import (  # noqa: E402
    REASON_SILENT_NOOP,
    classify,
    snapshot,
)

UNIT = "IMP-0431"
SENTINEL = "SENTINEL:IMP-0431:HARVEST-POSTCONDITION"
ART = REPO / "command-center" / "receipts" / "IMP-0431.json"
PRESEEDED = HERE / "fixtures" / "preseeded-dest"
CLI = HARVEST / "harvest.py"


def mutant_exit_zero_is_success(process_exit_code: int) -> str:
    """The FC-11319 defect: exit 0 is treated as SUCCESS with no delta check."""
    return "SUCCESS" if int(process_exit_code) == 0 else "FAILED"


def mutant_dest_populated_is_success(after_file_count: int, process_exit_code: int) -> str:
    """Stock-not-delta defect: dest already having files looks like a harvest."""
    if int(process_exit_code) == 0 and int(after_file_count) > 0:
        return "SUCCESS"
    return "FAILED"


def run_cli(remote: Path, dest: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [
            sys.executable,
            "-B",
            str(CLI),
            "--remote",
            str(remote),
            "--dest",
            str(dest),
            "--max-attempts",
            "2",
            "--backoff-seconds",
            "0",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            print("FAILED:IMP-0431-probe1 catalog sentinel absent from receipt")
            return 1
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0431-probe1 self-declared {st}")
            return 1

    with tempfile.TemporaryDirectory(prefix="imp0431-p1-") as tmp:
        tmp_path = Path(tmp)
        empty_remote = tmp_path / "remote-empty"
        empty_remote.mkdir()
        dest = tmp_path / "dest-empty"
        dest.mkdir()

        before = snapshot(dest)
        transfer = transfer_tree(empty_remote, dest)
        after = snapshot(dest)
        empty_v = classify(before, after, transfer.exit_code, attempts=1)

        run_v = run_harvest(
            empty_remote,
            dest,
            max_attempts=2,
            backoff_seconds=(0.0,),
        )
        cli_rc, cli_out = run_cli(empty_remote, tmp_path / "dest-cli")

        pre_dest = tmp_path / "dest-preseeded"
        shutil.copytree(PRESEEDED, pre_dest)
        pre_before = snapshot(pre_dest)
        pre_tr = transfer_tree(empty_remote, pre_dest)
        pre_after = snapshot(pre_dest)
        pre_v = classify(pre_before, pre_after, pre_tr.exit_code, attempts=1)

        mutant_empty = mutant_exit_zero_is_success(transfer.exit_code)
        mutant_pre = mutant_dest_populated_is_success(
            pre_after.file_count, pre_tr.exit_code
        )

        real_empty_failed = (
            empty_v.state == "FAILED"
            and empty_v.reason_id == REASON_SILENT_NOOP
            and transfer.exit_code == 0
            and empty_v.process_exit_code == 0
            and not empty_v.delta.nonempty
        )
        run_empty_failed = (
            run_v.state == "FAILED"
            and run_v.reason_id == REASON_SILENT_NOOP
            and run_v.attempts == 2
        )
        cli_failed = cli_rc != 0 and "silent-noop-harvest" in cli_out
        preseeded_failed = (
            pre_v.state == "FAILED"
            and pre_v.reason_id == REASON_SILENT_NOOP
            and pre_before.file_count >= 1
            and pre_after.file_count == pre_before.file_count
            and not pre_v.delta.nonempty
        )
        mutant_exit_fires = mutant_empty == "SUCCESS" and empty_v.state == "FAILED"
        mutant_stock_fires = mutant_pre == "SUCCESS" and pre_v.state == "FAILED"

        out = {
            "probe": "probe1-empty-harvest",
            "unit_id": UNIT,
            "empty": {
                "process_exit_code": transfer.exit_code,
                "classification": empty_v.state,
                "reason_id": empty_v.reason_id,
                "before_file_count": empty_v.before.file_count,
                "after_file_count": empty_v.after.file_count,
                "before_total_bytes": empty_v.before.total_bytes,
                "after_total_bytes": empty_v.after.total_bytes,
                "nonempty_delta": empty_v.delta.nonempty,
            },
            "run_harvest_empty": {
                "state": run_v.state,
                "reason_id": run_v.reason_id,
                "attempts": run_v.attempts,
            },
            "cli_exit_code": cli_rc,
            "preseeded_empty_remote": {
                "before_file_count": pre_v.before.file_count,
                "after_file_count": pre_v.after.file_count,
                "classification": pre_v.state,
                "reason_id": pre_v.reason_id,
            },
            "mutant_exit_zero_classifies_empty_success": mutant_empty == "SUCCESS",
            "mutant_dest_populated_classifies_preseeded_success": mutant_pre
            == "SUCCESS",
            "real_empty_not_success": empty_v.state != "SUCCESS",
            "pass": bool(
                real_empty_failed
                and run_empty_failed
                and cli_failed
                and preseeded_failed
                and mutant_exit_fires
                and mutant_stock_fires
            ),
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"empty_state={empty_v.state} reason={empty_v.reason_id} "
            f"copy_exit={transfer.exit_code} cli_rc={cli_rc} "
            f"attempts={run_v.attempts} preseeded={pre_v.state} "
            f"mutant_exit_fires={mutant_exit_fires} "
            f"mutant_stock_fires={mutant_stock_fires}"
        )
        if not out["pass"]:
            print("FAILED:IMP-0431-probe1 empty harvest was not classified FAILED")
            print(cli_out[-1500:])
            return 1
        print("SUCCESS:IMP-0431-probe1 empty harvest FAILED (exit-0 silent-noop)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
