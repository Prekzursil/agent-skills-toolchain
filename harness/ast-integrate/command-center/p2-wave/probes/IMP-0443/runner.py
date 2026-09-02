#!/usr/bin/env python3
"""Catalog runner bound to the append-only run ledger.

Executes only units not already completed. SIGKILL of this process leaves
completed records intact; a restart of this runner with the same ledger
resumes the remainder. --mutant disables both skip-completed and the
idempotent completed append (the IMP-0443 detector control).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))
from run_ledger import RunLedger  # noqa: E402


def execute_unit(unit_id: str) -> str:
    return hashlib.sha256(unit_id.encode("utf-8")).hexdigest()[:16]


def load_catalog(path: Path) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    units = doc.get("units") if isinstance(doc, dict) else doc
    if not isinstance(units, list) or not units:
        raise SystemExit("catalog must be a JSON object with a non-empty units list")
    return [str(u) for u in units]


def run(
    catalog: list[str],
    ledger_path: Path,
    *,
    delay_ms: int = 0,
    hold_file: Path | None = None,
    stall_after: int | None = None,
    mutant: bool = False,
    run_id: str | None = None,
) -> int:
    if hold_file is not None:
        while not hold_file.is_file():
            time.sleep(0.002)
    ledger = RunLedger(ledger_path, run_id=run_id)
    queue = list(catalog) if mutant else ledger.pending(catalog)
    for unit_id in queue:
        if stall_after is not None and len(ledger.completed_set()) >= stall_after:
            time.sleep(30.0)
        ledger.record_started(unit_id)
        execute_unit(unit_id)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        ledger.record_completed(unit_id, allow_duplicate=mutant)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="IMP-0443 ledger-backed catalog runner")
    p.add_argument("--catalog", required=True, type=Path)
    p.add_argument("--ledger", required=True, type=Path)
    p.add_argument("--delay-ms", type=int, default=0)
    p.add_argument("--hold-file", type=Path, default=None)
    p.add_argument("--stall-after", type=int, default=None)
    p.add_argument("--mutant", action="store_true")
    p.add_argument("--run-id", default=None)
    args = p.parse_args(argv)
    catalog = load_catalog(args.catalog)
    return run(
        catalog,
        args.ledger,
        delay_ms=args.delay_ms,
        hold_file=args.hold_file,
        stall_after=args.stall_after,
        mutant=args.mutant,
        run_id=args.run_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
