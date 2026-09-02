#!/usr/bin/env python3
"""TST-0320 probe 1: kill at 40% and resume; ledger matches an uninterrupted run.

Evidence is per-cell values, not row count alone. A value-mutating resume is
the control that would pass a count-only check and fail this one.

Skip is counted from the dispatch log: resume must not re-evaluate completed
cells. A skip-less restart after the same kill re-evaluates the full roster.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from bench.cell import Cell  # noqa: E402
from bench.evaluate import evaluate_cell  # noqa: E402
from bench.ledger import compare_ledgers, load_corpus, cells_from_corpus  # noqa: E402
from bench.runner import InterruptedRun, TournamentRunner  # noqa: E402

UNIT = "TST-0320"
CORPUS = REPO / "command-center" / "bench" / "cases" / "corpus.json"
KILL_PCT = 40.0


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def load_cells() -> list[Cell]:
    return cells_from_corpus(load_corpus(CORPUS))


def main() -> int:
    cells = load_cells()
    total = len(cells)
    if total < 10:
        return fail(f"corpus too small: {total}")
    expected_kill_n = int((KILL_PCT / 100.0) * total)
    if expected_kill_n * 100 != int(KILL_PCT) * total / 1:
        # 50 cells * 40% = 20 exactly; require an exact grain so the kill
        # is at the named 40% mark, not "about 40".
        pass
    if (expected_kill_n / total) * 100 != KILL_PCT:
        return fail(
            f"kill grain not exact: {expected_kill_n}/{total} != {KILL_PCT}%"
        )

    with tempfile.TemporaryDirectory(prefix="tst0320-p1-") as tmp:
        tmp_path = Path(tmp)

        clean = TournamentRunner(tmp_path / "clean", cells=cells)
        clean_summary = clean.run(session="clean", resume=True)
        if clean_summary["state"] != "COMPLETE":
            return fail(f"clean state={clean_summary['state']}")
        if clean_summary["evaluated"] != total or clean_summary["skipped"] != 0:
            return fail(
                f"clean eval={clean_summary['evaluated']} skip={clean_summary['skipped']}"
            )
        if clean.ledger.row_count() != total:
            return fail(f"clean rows={clean.ledger.row_count()} want {total}")

        killed = TournamentRunner(tmp_path / "resume", cells=cells)
        try:
            killed.run(session="kill", resume=True, kill_at_pct=KILL_PCT)
            return fail("expected InterruptedRun at 40%")
        except InterruptedRun as exc:
            if abs(exc.progress_pct - KILL_PCT) > 0.01:
                return fail(f"progress_pct={exc.progress_pct} want {KILL_PCT}")
            if exc.written != expected_kill_n:
                return fail(f"killed written={exc.written} want {expected_kill_n}")
        kill_eval = killed.count_actions("kill", "evaluate")
        kill_skip = killed.count_actions("kill", "skip")
        if kill_eval != expected_kill_n or kill_skip != 0:
            return fail(f"kill dispatch eval={kill_eval} skip={kill_skip}")
        if killed.ledger.row_count() != expected_kill_n:
            return fail(f"partial rows={killed.ledger.row_count()}")

        resume_summary = killed.run(session="resume", resume=True)
        if resume_summary["state"] != "COMPLETE":
            return fail(f"resume state={resume_summary['state']}")
        resume_eval = killed.count_actions("resume", "evaluate")
        resume_skip = killed.count_actions("resume", "skip")
        remaining = total - expected_kill_n
        if resume_eval != remaining:
            return fail(f"resume eval={resume_eval} want {remaining}")
        if resume_skip != expected_kill_n:
            return fail(f"resume skip={resume_skip} want {expected_kill_n}")
        if resume_eval >= clean_summary["evaluated"]:
            return fail("resume evaluated as many cells as a clean run")

        cmp_ok = compare_ledgers(clean.ledger_path, killed.ledger_path)
        if not cmp_ok["row_count_equal"]:
            return fail(f"row count mismatch {cmp_ok}")
        if not cmp_ok["values_equal"]:
            return fail(
                f"per-cell values differ mismatch_count={cmp_ok['mismatch_count']} "
                f"ids={cmp_ok['mismatched_cell_ids']}"
            )
        if not cmp_ok["ordered_ids_equal"]:
            return fail("cell_id order differs; resume reordered the ledger")
        if cmp_ok["duplicate_rows_a"] or cmp_ok["duplicate_rows_b"]:
            return fail("duplicate cell rows present")

        # Independent recompute: stored scores must match evaluate_cell, not
        # the runner's self-report.
        for rec in killed.ledger.records():
            expected = evaluate_cell(rec["cell"])
            if rec["result"]["score"] != expected["score"]:
                return fail(f"stored score drifted for {rec['cell_id']}")
            if rec["result"]["digest"] != expected["digest"]:
                return fail(f"stored digest drifted for {rec['cell_id']}")

        # Skip is load-bearing: after the same 40% kill, a skip-less run
        # re-evaluates every cell.
        noskip = TournamentRunner(tmp_path / "noskip", cells=cells)
        try:
            noskip.run(session="kill", resume=True, kill_at_pct=KILL_PCT)
        except InterruptedRun:
            pass
        else:
            return fail("noskip kill did not interrupt")
        noskip.run(session="restart", resume=False)
        noskip_eval = noskip.count_actions("restart", "evaluate")
        if noskip_eval != total:
            return fail(f"skip-less restart eval={noskip_eval} want {total}")
        # Honest append still refuses a second row, so the ledger stays at
        # `total` even though every cell was re-evaluated.
        if noskip.ledger.row_count() != total:
            return fail(f"noskip rows={noskip.ledger.row_count()} (idempotent append should hold)")

        # Value-mutation control: row count would match; per-cell values must not.
        def mutant_eval(cell: Cell) -> dict:
            result = evaluate_cell(cell)
            result = dict(result)
            result["score"] = int(result["score"]) + 1
            result["mutated"] = True
            return result

        mutant = TournamentRunner(
            tmp_path / "mutant", cells=cells, evaluate=mutant_eval
        )
        try:
            mutant.run(session="kill", resume=True, kill_at_pct=KILL_PCT)
        except InterruptedRun:
            pass
        else:
            return fail("mutant kill did not interrupt")
        # First 40% were written with mutant scores already. Compare against
        # clean: same row count after resume, values must differ.
        mutant.run(session="resume", resume=True)
        cmp_mut = compare_ledgers(clean.ledger_path, mutant.ledger_path)
        if not cmp_mut["row_count_equal"]:
            return fail("mutant row count should still match (count-only would pass)")
        if cmp_mut["values_equal"]:
            return fail("mutant values matched clean; per-cell comparison is inert")
        if cmp_mut["mismatch_count"] < 1:
            return fail("mutant produced no per-cell mismatch")

        # Seed is part of the key: same candidate/case/harness, different seed
        # is a different cell.
        a = Cell("cand-alpha", "case-00", "tst-0320-h1", 320)
        b = Cell("cand-alpha", "case-00", "tst-0320-h1", 321)
        if a.id() == b.id():
            return fail("seed is not part of cell_id")

        out = {
            "unit_id": UNIT,
            "probe": "probe1-kill-resume",
            "pass": True,
            "total_cells": total,
            "kill_pct": KILL_PCT,
            "killed_rows": expected_kill_n,
            "clean_rows": clean.ledger.row_count(),
            "resume_rows": killed.ledger.row_count(),
            "resume_evaluated": resume_eval,
            "resume_skipped": resume_skip,
            "noskip_restart_evaluated": noskip_eval,
            "values_equal": cmp_ok["values_equal"],
            "row_count_equal": cmp_ok["row_count_equal"],
            "mutant_row_count_equal": cmp_mut["row_count_equal"],
            "mutant_values_equal": cmp_mut["values_equal"],
            "mutant_mismatch_count": cmp_mut["mismatch_count"],
            "seed_in_key": True,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"rows={total} kill={expected_kill_n} resume_eval={resume_eval} "
            f"resume_skip={resume_skip} values_equal={cmp_ok['values_equal']} "
            f"mutant_mismatches={cmp_mut['mismatch_count']}"
        )
        print(
            f"SUCCESS:{UNIT}-probe1 kill-at-40% resume matches uninterrupted "
            "per-cell values"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
