"""Append-only results ledger."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


from bench.oracle_first import LINT_CODE


class LedgerImmutableError(RuntimeError):
    pass


def _oracle_eligible(case: dict[str, Any] | None) -> bool:
    """A case is oracle-eligible when a deterministic oracle label exists for it."""
    if not isinstance(case, dict):
        return False
    if case.get("overlap") is False:
        return False
    return case.get("oracle") is not None


def lint_official_ledger(rows: list[dict[str, Any]], by_id: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Official deterministic rows must use the oracle, not a judge.

    When the case map is supplied, a row that launders a judge score behind
    ``oracle_kind != "deterministic"`` on an oracle-eligible case still fires:
    the label on the record is checked against the case map, not trusted.
    """
    findings = []
    for row in rows or []:
        kind = str(row.get("oracle_kind") or "")
        case = (by_id or {}).get(str(row.get("case_id")))
        if kind == "deterministic" and row.get("used_oracle") is not True:
            findings.append(
                {
                    "code": LINT_CODE,
                    "case_id": row.get("case_id"),
                    "detail": "official deterministic score used a judge",
                }
            )
        elif (
            kind != "deterministic"
            and row.get("used_oracle") is not True
            and row.get("role") == "official"
            and _oracle_eligible(case)
        ):
            findings.append(
                {
                    "code": LINT_CODE,
                    "case_id": row.get("case_id"),
                    "detail": "official row claims judged on an oracle-eligible case",
                }
            )
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

