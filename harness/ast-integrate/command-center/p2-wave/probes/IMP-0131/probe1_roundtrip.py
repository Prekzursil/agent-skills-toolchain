#!/usr/bin/env python3
"""Probe 1: pause-then-resume preserves completed receipts byte-for-byte.

Evidence: (1) pause record exists and parses; (2) resume ledger dispatch
count for pre-checkpoint units is zero.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

from agentspec.checkpoint import (  # noqa: E402
    dispatch_count,
    load_pause_record,
)
from agentspec.envelope import STATUS_COMPLETED, STATUS_PAUSED  # noqa: E402
from agentspec.spec import HumanCheckpoint  # noqa: E402


def _read(path: Path) -> bytes:
    return path.read_bytes()


def main() -> int:
    # Frozen constructor contract: required fields exist and mutation is refused.
    fields = {
        "id",
        "prompt_ref",
        "allowed_responses",
        "default_if_unanswered",
        "pause_token",
    }
    if set(HumanCheckpoint.__dataclass_fields__) != fields:
        print(
            "FAILED:IMP-0131-probe1 HumanCheckpoint fields "
            f"{sorted(HumanCheckpoint.__dataclass_fields__)} != {sorted(fields)}"
        )
        return 1
    frozen_ok = False
    try:
        HumanCheckpoint(
            id="x",
            prompt_ref="p",
            allowed_responses=("a",),
            default_if_unanswered=None,
            pause_token="tok",
        ).id = "y"  # type: ignore[misc]
    except Exception:
        frozen_ok = True
    if not frozen_ok:
        print("FAILED:IMP-0131-probe1 HumanCheckpoint is not frozen")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0131-p1-") as tmp:
        store = Path(tmp)
        wf = S.sample_workflow()
        first = S.run_workflow(wf, store)
        if first.status != STATUS_PAUSED or not first.terminal:
            print(
                f"FAILED:IMP-0131-probe1 first-run status={first.status} "
                f"terminal={first.terminal} reason={first.reason}"
            )
            return 1
        pause_path = Path(first.pause_record_path or "")
        if not pause_path.is_file():
            print("FAILED:IMP-0131-probe1 pause record missing on disk")
            return 1
        record = load_pause_record(pause_path)
        if record["pause_token"] != S.PAUSE_TOKEN:
            print("FAILED:IMP-0131-probe1 pause_token mismatch")
            return 1
        if record["checkpoint_id"] != S.CHECKPOINT_ID:
            print("FAILED:IMP-0131-probe1 checkpoint_id mismatch")
            return 1

        receipts = store / "receipts"
        alpha_before = _read(receipts / "unit-alpha.json")
        beta_before = _read(receipts / "unit-beta.json")
        if not alpha_before or not beta_before:
            print("FAILED:IMP-0131-probe1 pre-checkpoint receipts empty")
            return 1
        if (receipts / "unit-gamma.json").is_file():
            print("FAILED:IMP-0131-probe1 unit-gamma ran before pause")
            return 1

        first_ledger = json.loads((store / "ledger.json").read_text(encoding="utf-8"))
        if dispatch_count(first_ledger, "unit-alpha") != 1:
            print("FAILED:IMP-0131-probe1 first-run alpha dispatch != 1")
            return 1
        if dispatch_count(first_ledger, "unit-beta") != 1:
            print("FAILED:IMP-0131-probe1 first-run beta dispatch != 1")
            return 1
        if dispatch_count(first_ledger, "unit-gamma") != 0:
            print("FAILED:IMP-0131-probe1 first-run gamma dispatched before pause")
            return 1

        resumed = S.run_workflow(
            wf, store, resume_token=S.PAUSE_TOKEN, owner_response="approve"
        )
        if resumed.status != STATUS_COMPLETED or not resumed.terminal:
            print(
                f"FAILED:IMP-0131-probe1 resume status={resumed.status} "
                f"reason={resumed.reason}"
            )
            return 1

        alpha_after = _read(receipts / "unit-alpha.json")
        beta_after = _read(receipts / "unit-beta.json")
        if alpha_before != alpha_after:
            print("FAILED:IMP-0131-probe1 unit-alpha receipt bytes changed on resume")
            return 1
        if beta_before != beta_after:
            print("FAILED:IMP-0131-probe1 unit-beta receipt bytes changed on resume")
            return 1
        gamma = receipts / "unit-gamma.json"
        if not gamma.is_file() or gamma.stat().st_size <= 0:
            print("FAILED:IMP-0131-probe1 unit-gamma missing after resume")
            return 1

        resume_ledger = json.loads(
            Path(resumed.ledger_path or store / "ledger-resume.json").read_text(
                encoding="utf-8"
            )
        )
        alpha_redispatch = dispatch_count(resume_ledger, "unit-alpha")
        beta_redispatch = dispatch_count(resume_ledger, "unit-beta")
        gamma_dispatch = dispatch_count(resume_ledger, "unit-gamma")
        skip_alpha = sum(
            1
            for row in resume_ledger
            if row.get("event") == "skip-completed" and row.get("unit_id") == "unit-alpha"
        )
        if alpha_redispatch != 0 or beta_redispatch != 0:
            print(
                "FAILED:IMP-0131-probe1 resume re-dispatched completed units "
                f"alpha={alpha_redispatch} beta={beta_redispatch}"
            )
            return 1
        if gamma_dispatch != 1:
            print(f"FAILED:IMP-0131-probe1 resume gamma dispatch={gamma_dispatch}")
            return 1
        if skip_alpha < 1:
            print("FAILED:IMP-0131-probe1 resume ledger missing skip-completed for alpha")
            return 1

        report = {
            "probe": "probe1-roundtrip",
            "unit_id": "IMP-0131",
            "frozen": True,
            "pause_record_exists": True,
            "pause_record_parsed": True,
            "pause_record_path": str(pause_path),
            "first_status": first.status,
            "resume_status": resumed.status,
            "alpha_bytes": len(alpha_before),
            "beta_bytes": len(beta_before),
            "receipts_byte_identical": True,
            "resume_dispatch_precheckpoint": {
                "unit-alpha": alpha_redispatch,
                "unit-beta": beta_redispatch,
            },
            "resume_dispatch_unit_gamma": gamma_dispatch,
            "pass": True,
        }
        print(json.dumps(report, sort_keys=True))
        print(
            "pause_parsed=True receipts_byte_identical=True "
            f"resume_redispatch_alpha={alpha_redispatch} "
            f"resume_redispatch_beta={beta_redispatch} "
            f"resume_dispatch_gamma={gamma_dispatch}"
        )
        print("SUCCESS:IMP-0131-probe1 pause-then-resume byte-for-byte")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
