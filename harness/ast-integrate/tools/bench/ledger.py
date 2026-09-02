"""Append-only results ledger."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


from bench.oracle_first import LINT_CODE


class LedgerImmutableError(RuntimeError):
    pass


def lint_official_ledger(rows: list[dict[str, Any]], by_id: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Official deterministic rows must use the oracle, not a judge."""
    findings = []
    by_id = by_id or {}
    for row in rows or []:
        declared = str(row.get("oracle_kind") or "")
        # The row's own oracle_kind is self-reported and can be rewritten; the
        # case definition decides whether an oracle exists for it.
        case = by_id.get(str(row.get("case_id") or ""))
        if case is not None:
            has_oracle = case.get("overlap") is not False
        else:
            has_oracle = declared == "deterministic"
        judged = row.get("used_oracle") is not True or row.get("judge_id") is not None
        if str(row.get("role") or "official") != "official":
            continue
        if has_oracle and judged:
            detail = "official deterministic score used a judge"
            if declared != "deterministic":
                detail += f" (row oracle_kind rewritten to {declared!r})"
            findings.append({"code": LINT_CODE, "case_id": row.get("case_id"), "detail": detail})
    return findings


class ResultsLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self.path.write_text("", encoding="utf-8")

    def append(self, row: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def rows(self) -> list[dict[str, Any]]:
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def records(self) -> list[dict[str, Any]]:
        return self.rows()

    def row_count(self) -> int:
        return len(self.rows())

    # -- hash-chained run rows and metric status events (TST-0308) -----------

    @staticmethod
    def _row_hash(row: dict[str, Any]) -> str:
        body = {k: v for k, v in row.items() if k != "hash"}
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _chained_rows(self) -> list[dict[str, Any]]:
        return [r for r in self.rows() if "hash" in r and "seq" in r]

    def _append_chained(self, row: dict[str, Any]) -> dict[str, Any]:
        chain = self._chained_rows()
        row = dict(row)
        row["seq"] = (int(chain[-1]["seq"]) + 1) if chain else 1
        row["prev_hash"] = chain[-1]["hash"] if chain else "0" * 64
        row["hash"] = self._row_hash(row)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def append_runs(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Append campaign run rows (one per case per iteration) to the chain."""
        written = []
        for src in rows:
            metrics = dict(src.get("metrics") or {})
            outcomes = dict(src.get("outcomes") or {})
            written.append(
                self._append_chained(
                    {
                        "kind": "run",
                        "iteration": int(src.get("iteration", src.get("iter", 0))),
                        "case_id": str(src.get("case_id") or src.get("case") or ""),
                        "campaign": src.get("campaign"),
                        "metrics": metrics,
                        "outcomes": outcomes,
                        "metric_ids": sorted(metrics),
                    }
                )
            )
        return written

    def snapshot_bytes(self) -> bytes:
        return self.path.read_bytes()

    def run_records(self, metric_id: str | None = None) -> list[dict[str, Any]]:
        """Every run row ever written for the metric; history is never filtered."""
        out = []
        for row in self._chained_rows():
            if row.get("kind") != "run":
                continue
            if metric_id is None or metric_id in (row.get("metrics") or {}):
                out.append(row)
        return out

    def history(self, metric_id: str) -> list[dict[str, Any]]:
        return [
            {
                "seq": r["seq"],
                "iteration": r["iteration"],
                "case_id": r["case_id"],
                "metric_value": (r.get("metrics") or {}).get(metric_id),
                "outcomes": dict(r.get("outcomes") or {}),
                "hash": r["hash"],
            }
            for r in self.run_records(metric_id)
        ]

    def status_events(self, metric_id: str | None = None) -> list[dict[str, Any]]:
        return [
            r
            for r in self._chained_rows()
            if r.get("kind") == "metric-status" and (metric_id is None or r.get("metric_id") == metric_id)
        ]

    def metric_status(self, metric_id: str) -> str:
        events = self.status_events(metric_id)
        return str(events[-1]["status"]) if events else "active"

    def demote_metric(
        self,
        metric_id: str,
        *,
        reason: str,
        iteration: int,
        finding: dict[str, Any] | None = None,
        status: str = "demoted",
    ) -> dict[str, Any]:
        """Retire a metric by appending a status event; history rows are untouched."""
        return self._append_chained(
            {
                "kind": "metric-status",
                "metric_id": metric_id,
                "status": status,
                "reason": reason,
                "iteration": int(iteration),
                "finding": dict(finding or {}),
            }
        )

    def active_metric_ids(self) -> list[str]:
        ids: list[str] = []
        for row in self.run_records():
            for mid in row.get("metric_ids") or sorted(row.get("metrics") or {}):
                if mid not in ids:
                    ids.append(mid)
        return [m for m in ids if self.metric_status(m) == "active"]

    def scoring_runs(self, metric_id: str) -> list[dict[str, Any]]:
        """Current scoring view: empty once the metric is demoted; history stays."""
        if self.metric_status(metric_id) != "active":
            return []
        return self.run_records(metric_id)

    def verify_chain(self) -> bool:
        prev = "0" * 64
        expected_seq = 1
        for row in self._chained_rows():
            if int(row["seq"]) != expected_seq or row.get("prev_hash") != prev:
                return False
            if self._row_hash(row) != row["hash"]:
                return False
            prev = row["hash"]
            expected_seq += 1
        return True

    def rewrite_run(self, seq: int, **changes: Any) -> None:
        """History is append-only: any in-place edit is refused before touching disk."""
        raise LedgerImmutableError(
            f"ledger row seq={seq} is immutable; append a status event instead of rewriting {sorted(changes)}"
        )


def load_ledger(path: str | Path) -> list[dict[str, Any]]:
    return ResultsLedger(path).rows()


def load_corpus(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        cases = [{"id": f"C{i:02d}", "n": i} for i in range(50)]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8")
        return {"cases": cases}
    return json.loads(p.read_text(encoding="utf-8"))


def cells_from_corpus(doc: dict[str, Any]) -> list:
    from bench.cell import Cell

    cases = doc.get("cases") or doc.get("cells") or []
    out = []
    for row in cases:
        cid = str(row.get("id") or row.get("cell_id") or "")
        out.append(Cell(cell_id=cid, payload=dict(row)))
    return out


def compare_ledgers(path_a: str | Path, path_b: str | Path) -> dict[str, Any]:
    a = ResultsLedger(path_a).records()
    b = ResultsLedger(path_b).records()
    ids_a = [r.get("cell_id") for r in a]
    ids_b = [r.get("cell_id") for r in b]
    mismatches = []
    by_a = {r.get("cell_id"): r for r in a}
    by_b = {r.get("cell_id"): r for r in b}
    for cid in sorted(set(ids_a) | set(ids_b)):
        ra, rb = by_a.get(cid), by_b.get(cid)
        if ra is None or rb is None:
            mismatches.append(cid)
            continue
        if (ra.get("result") or {}) != (rb.get("result") or {}):
            mismatches.append(cid)
    return {
        "row_count_equal": len(a) == len(b),
        "values_equal": not mismatches,
        "mismatch_count": len(mismatches),
        "mismatched_cell_ids": mismatches,
        "ordered_ids_equal": ids_a == ids_b,
        "duplicate_rows_a": len(ids_a) != len(set(ids_a)),
        "duplicate_rows_b": len(ids_b) != len(set(ids_b)),
    }


def index_by_run_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get("run_id") or row.get("id") or "")
        if rid:
            out[rid] = row
    return out


class Ledger(ResultsLedger):
    """Append-only jsonl ledger used by TST-0313 closure proofs."""

    def by_run_id(self) -> dict[str, dict[str, Any]]:
        return index_by_run_id(self.rows())

