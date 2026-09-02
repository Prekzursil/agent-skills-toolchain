"""Both-states controls for the quality-tier evidence gate.

These mutate a COPY of the estate. The live estate is left intact.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from gate import gate


def copy_estate(src: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    tmp = tempfile.TemporaryDirectory(prefix="wfa0135-")
    dest = Path(tmp.name) / "estate"
    shutil.copytree(src, dest)
    return tmp, dest


def first_flagship_id(estate: Path) -> str:
    led = gate(estate)
    for row in led["rows"]:
        if row["claimed_tier"] == "flagship" and row["outcome"] == "PROVEN":
            return row["blueprint_id"]
    raise RuntimeError("no proven flagship row to mutate")


def demote_experiment(live_estate: Path) -> dict[str, Any]:
    """Delete one flagship e2e test file; that row must leave flagship."""
    baseline = gate(live_estate)
    tmp, estate = copy_estate(live_estate)
    try:
        bid = first_flagship_id(estate)
        test = estate / "tests" / "e2e" / f"{bid}.py"
        if not test.is_file():
            raise RuntimeError(f"missing test {test}")
        test.unlink()
        after = gate(estate)
        row = next(r for r in after["rows"] if r["blueprint_id"] == bid)
        still_flagship = (
            row["resolved_tier"] == "flagship" and row["outcome"] == "PROVEN"
        )
        demoted_ok = (
            row["outcome"] == "DEMOTE"
            and row["resolved_tier"] != "flagship"
            and not still_flagship
            and after["counts"]["proven_flagship"]
            == baseline["counts"]["proven_flagship"] - 1
            and after["counts"]["demoted"] == baseline["counts"]["demoted"] + 1
        )
        if baseline["counts"]["proven_flagship"] >= 40:
            demoted_ok = demoted_ok and after["counts"]["proven_flagship"] < 40
        return {
            "ok": demoted_ok,
            "blueprint_id": bid,
            "deleted_test": test.name,
            "baseline_proven_flagship": baseline["counts"]["proven_flagship"],
            "after_proven_flagship": after["counts"]["proven_flagship"],
            "after_outcome": row["outcome"],
            "after_resolved_tier": row["resolved_tier"],
            "after_reasons": row["reasons"],
            "floor_met_after": after["counts"]["flagship_floor_met"],
        }
    finally:
        tmp.cleanup()


def unproven_experiment(live_estate: Path) -> dict[str, Any]:
    """Keep the e2e test path, strip the passing run: outcome must be UNPROVEN."""
    tmp, estate = copy_estate(live_estate)
    try:
        bid = first_flagship_id(estate)
        test = estate / "tests" / "e2e" / f"{bid}.py"
        if not test.is_file():
            raise RuntimeError("test path missing before strip")
        removed = []
        for rec in (estate / "runs").glob("*.json"):
            text = rec.read_text(encoding="utf-8")
            if f'"{bid}"' in text and '"kind": "e2e"' in text:
                rec.unlink()
                removed.append(rec.name)
        after = gate(estate)
        row = next(r for r in after["rows"] if r["blueprint_id"] == bid)
        ok = (
            test.is_file()
            and row["outcome"] == "UNPROVEN"
            and row["resolved_tier"] == "unproven"
            and "path-without-run" in row["reasons"]
            and row.get("run_id") in (None, "")
            and not (row["resolved_tier"] == "flagship" and row["outcome"] == "PROVEN")
        )
        return {
            "ok": ok,
            "blueprint_id": bid,
            "test_still_present": test.is_file(),
            "removed_receipts": removed,
            "after_outcome": row["outcome"],
            "after_resolved_tier": row["resolved_tier"],
            "after_reasons": row["reasons"],
            "after_run_id": row.get("run_id"),
        }
    finally:
        tmp.cleanup()
