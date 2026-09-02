"""Kill/resume tournament runner (TST-0320) and the read-only baseline benchmark run (TST-0229).

``TournamentRunner`` evaluates cells and appends to a results ledger, resuming
after a kill without re-evaluating finished cells.  ``run_benchmark`` is the
other entry point: it produces a candidate payload for a named baseline case,
compares it against the write-once ``BaselineStore`` and proves the store did
not move - a benchmark run never re-baselines.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from bench.cell import Cell
from bench.evaluate import evaluate_cell
from bench.ledger import ResultsLedger

# Verdicts of one read-only benchmark run against a baseline case.
MATCH = "MATCH"
MISMATCH = "MISMATCH"
NO_BASELINE = "NO-BASELINE"


class InterruptedRun(Exception):
    def __init__(self, progress_pct: float, written: int) -> None:
        super().__init__(f"interrupted at {progress_pct}%")
        self.progress_pct = progress_pct
        self.written = written


class StoreMutatedDuringRun(Exception):
    """A read-only benchmark run observed the baseline store change underneath it."""

    def __init__(self, case_id: str, before: str, after: str) -> None:
        super().__init__(
            f"baseline store moved during read-only run of {case_id!r}: "
            f"{before[:12]}... -> {after[:12]}..."
        )
        self.case_id = case_id
        self.before = before
        self.after = after


def _pointer(store: Any, case_id: str) -> str | None:
    """The digest ``case_id`` points at, or ``None`` when the store has no baseline for it."""
    pointers = getattr(store, "pointers", None)
    if callable(pointers):
        mapping = pointers()
        if isinstance(mapping, dict):
            value = mapping.get(case_id)
            return value if isinstance(value, str) else None
    return None


def run_benchmark(
    store: Any,
    case_id: str,
    produce: Callable[[], bytes],
    *,
    session: str = "run",
    ledger: ResultsLedger | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Run one benchmark case read-only against its baseline and report.

    Steps: snapshot the store digest and the case pointer; call ``produce()``
    for the candidate bytes; ``store.compare`` them (a read-only operation);
    snapshot again and record whether the store moved.  The run itself never
    writes to ``store`` (``wrote_store`` is always ``False``); changing a
    baseline is a separate, explicit ``store.write(..., rebaseline=...)`` with
    who/when/why.  With ``strict`` a moved store raises
    :class:`StoreMutatedDuringRun` instead of only being reported.  When a
    ``ledger`` is given the result row is appended there (the ledger is not the
    baseline store).

    Returns ``case_id``, ``session``, ``verdict`` (``MATCH`` / ``MISMATCH`` /
    ``NO-BASELINE``), ``comparison`` (the store's compare record, with
    ``match``), ``observed_digest`` / ``observed_bytes`` of the produced
    payload, ``wrote_store``, ``store_unchanged``, the two store digests and the
    two pointer readings.
    """
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    if not callable(produce):
        raise TypeError("produce must be a zero-argument callable returning bytes")
    for method in ("compare", "store_digest"):
        if not callable(getattr(store, method, None)):
            raise TypeError(f"store must provide {method}(); got {type(store).__name__}")

    digest_before = store.store_digest()
    pointer_before = _pointer(store, case_id)

    payload = produce()
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError(f"produce() must return bytes, not {type(payload).__name__}")
    payload = bytes(payload)
    observed_digest = hashlib.sha256(payload).hexdigest()

    comparison = store.compare(case_id, payload)
    if not isinstance(comparison, dict) or "match" not in comparison:
        raise TypeError("store.compare() must return a dict carrying 'match'")

    digest_after = store.store_digest()
    pointer_after = _pointer(store, case_id)
    store_unchanged = digest_before == digest_after and pointer_before == pointer_after
    if strict and not store_unchanged:
        raise StoreMutatedDuringRun(case_id, digest_before, digest_after)

    if not comparison.get("baseline_present", pointer_before is not None):
        verdict = NO_BASELINE
    elif comparison["match"]:
        verdict = MATCH
    else:
        verdict = MISMATCH

    result: dict[str, Any] = {
        "case_id": case_id,
        "session": session,
        "verdict": verdict,
        "comparison": dict(comparison),
        "observed_digest": observed_digest,
        "observed_bytes": len(payload),
        "wrote_store": False,
        "store_unchanged": store_unchanged,
        "store_digest_before": digest_before,
        "store_digest_after": digest_after,
        "store_digest": digest_after,
        "pointer_before": pointer_before,
        "pointer_after": pointer_after,
    }
    if ledger is not None:
        ledger.append(
            {
                "cell_id": f"benchmark:{case_id}",
                "kind": "benchmark-run",
                "session": session,
                "result": dict(result),
            }
        )
    return result


class TournamentRunner:
    def __init__(self, root: Path, cells: list[Cell], evaluate=None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cells = list(cells)
        self.ledger_path = self.root / "ledger.jsonl"
        self.ledger = ResultsLedger(self.ledger_path)
        self._evaluate = evaluate or evaluate_cell
        self._actions: dict[tuple[str, str], int] = {}
        self._done: set[str] = {r.get("cell_id") for r in self.ledger.records()}

    def count_actions(self, session: str, kind: str) -> int:
        return int(self._actions.get((session, kind), 0))

    def _bump(self, session: str, kind: str) -> None:
        key = (session, kind)
        self._actions[key] = self._actions.get(key, 0) + 1

    def run(
        self,
        session: str = "run",
        resume: bool = True,
        kill_at_pct: float | None = None,
    ) -> dict[str, Any]:
        total = len(self.cells)
        evaluated = skipped = 0
        written_this = 0
        if not resume:
            self.ledger.path.write_text("", encoding="utf-8")
            self._done.clear()
        for i, cell in enumerate(self.cells):
            cid = cell.cell_id
            if resume and cid in self._done:
                skipped += 1
                self._bump(session, "skip")
                continue
            result = self._evaluate(cell)
            rec = {
                "cell_id": cid,
                "cell": cell.to_dict(),
                "result": result,
                "session": session,
            }
            self.ledger.append(rec)
            self._done.add(cid)
            evaluated += 1
            written_this += 1
            self._bump(session, "evaluate")
            done_n = len(self._done)
            if kill_at_pct is not None:
                pct = (done_n / total) * 100.0
                if pct + 1e-9 >= kill_at_pct and done_n == int((kill_at_pct / 100.0) * total):
                    raise InterruptedRun(kill_at_pct, done_n)
        return {
            "state": "COMPLETE",
            "evaluated": evaluated,
            "skipped": skipped,
            "total": total,
        }
