"""Live proof for TST-0313: closure blocked without a pre-fix FAIL run."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

import sys

sys.path.insert(0, str(REPO / "tools"))

from bench.closure import (  # noqa: E402
    census,
    close_defect,
    stub_reviewer_close,
)
from bench.ledger import Ledger  # noqa: E402
from bench.two_commit import run_oracle, run_pair  # noqa: E402


def load_register() -> dict[str, Any]:
    return copy.deepcopy(json.loads((FIX / "register.json").read_text(encoding="utf-8")))


def load_cases() -> dict[str, dict[str, Any]]:
    raw = json.loads((FIX / "cases.json").read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for item in raw:
        out[item["id"]] = {
            "id": item["id"],
            "oracle": str((FIX / item["oracle_rel"]).resolve()),
            "pre_snapshot": str((FIX / item["pre_snapshot_rel"]).resolve()),
            "post_snapshot": str((FIX / item["post_snapshot_rel"]).resolve()),
            "provenance": item.get("provenance"),
        }
    return out


def load_historical() -> Ledger:
    src = FIX / "historical-ledger.jsonl"
    handle = tempfile.NamedTemporaryFile(
        prefix="tst0313-ledger-", suffix=".jsonl", delete=False
    )
    handle.write(src.read_bytes())
    handle.close()
    return Ledger(handle.name)


def run_proof() -> dict[str, Any]:
    register = load_register()
    cases = load_cases()
    ledger = load_historical()
    existence = cases["CASE-EXISTENCE"]
    noop = cases["CASE-NOOP"]

    pre, post = run_pair(existence, ledger)
    close_ok = close_defect(
        register,
        "B10-R1-EXISTENCE-ONLY",
        ledger,
        pre_run_id=pre["run_id"],
        post_run_id=post["run_id"],
    )

    missing = close_defect(
        register,
        "B10-R3-STILL-OPEN",
        ledger,
        pre_run_id=None,
        post_run_id=post["run_id"],
    )
    reviewer = close_defect(
        register,
        "B10-R3-STILL-OPEN",
        ledger,
        pre_run_id=None,
        post_run_id=post["run_id"],
        reviewer_ok=True,
    )
    single = close_defect(
        register,
        "B10-R3-STILL-OPEN",
        ledger,
        pre_run_id=post["run_id"],
        post_run_id=post["run_id"],
    )

    paper = {
        "run_id": "run-paper-unexecuted",
        "case_id": "CASE-EXISTENCE",
        "side": "pre-fix",
        "outcome": "FAIL",
        "executed": False,
        "commit": "claimed",
    }
    ledger.append(paper)
    unexecuted = close_defect(
        register,
        "B10-R3-STILL-OPEN",
        ledger,
        pre_run_id=paper["run_id"],
        post_run_id=post["run_id"],
    )

    npre, npost = run_pair(noop, ledger)
    silent = close_defect(
        register,
        "B10-R2-EMPTY-EXITZERO",
        ledger,
        pre_run_id=npre["run_id"],
        post_run_id=npost["run_id"],
    )

    swapped_pre = run_oracle(
        existence,
        "pre-fix",
        ledger,
        snapshot_override=Path(existence["post_snapshot"]),
    )
    swapped_post = run_oracle(
        existence,
        "post-fix",
        ledger,
        snapshot_override=Path(existence["pre_snapshot"]),
    )
    swapped = close_defect(
        register,
        "B10-R3-STILL-OPEN",
        ledger,
        pre_run_id=swapped_pre["run_id"],
        post_run_id=swapped_post["run_id"],
    )

    cen = census(register, ledger)
    stub_allows_missing = stub_reviewer_close(reviewer_ok=True, has_prefix_fail=False)

    closed = [
        item
        for item in register["defects"]
        if str(item.get("status") or "").upper() == "CLOSED"
    ]
    cited = []
    for item in closed:
        cited.append(
            {
                "defect_id": item.get("id"),
                "pre_fix_run_id": item.get("pre_fix_run_id"),
                "post_fix_run_id": item.get("post_fix_run_id"),
                "both_recorded": bool(item.get("pre_fix_run_id") and item.get("post_fix_run_id")),
            }
        )

    b10r1 = next(d for d in register["defects"] if d["id"] == "B10-R1-EXISTENCE-ONLY")
    b10r2 = next(d for d in register["defects"] if d["id"] == "B10-R2-EMPTY-EXITZERO")
    b10r3 = next(d for d in register["defects"] if d["id"] == "B10-R3-STILL-OPEN")

    return {
        "existence_pre_outcome": pre["outcome"],
        "existence_post_outcome": post["outcome"],
        "existence_pre_run_id": pre["run_id"],
        "existence_post_run_id": post["run_id"],
        "existence_pre_executed": pre["executed"],
        "existence_post_executed": post["executed"],
        "close_ok": close_ok,
        "missing_prefix": missing,
        "reviewer_bypass": reviewer,
        "single_passing": single,
        "unexecuted_claim": unexecuted,
        "silent_oracle": silent,
        "noop_pre_outcome": npre["outcome"],
        "noop_post_outcome": npost["outcome"],
        "swapped_pre_outcome": swapped_pre["outcome"],
        "swapped_post_outcome": swapped_post["outcome"],
        "swapped_close": swapped,
        "census": cen,
        "stub_allows_missing_prefix": stub_allows_missing,
        "b10r1_status": b10r1.get("status"),
        "b10r2_status": b10r2.get("status"),
        "b10r3_status": b10r3.get("status"),
        "cited_closed": cited,
        "git_checkout_used": False,
        "runner": "snapshot-two-commit",
    }
