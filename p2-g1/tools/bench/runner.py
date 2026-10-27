"""Kill/resume tournament runner (TST-0320)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bench.cell import Cell
from bench.evaluate import evaluate_cell
from bench.ledger import ResultsLedger


class InterruptedRun(Exception):
    def __init__(self, progress_pct: float, written: int) -> None:
        super().__init__(f"interrupted at {progress_pct}%")
        self.progress_pct = progress_pct
        self.written = written


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
