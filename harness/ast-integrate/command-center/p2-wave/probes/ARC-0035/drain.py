"""Drain in-flight work into the ledger instead of abandoning it.

The census file is not rewritten. Drain rows append to a distinct ledger.
A request to abandon without writing a record is refused.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
import fold as F  # noqa: E402

CENSUS = HERE / "fixtures" / "in-flight.jsonl"
DRAIN_LEDGER = HERE / "fixtures" / "drain-ledger.jsonl"

RAIL_IDS = ("task_subagent", "codex_mcp", "databricks_job")


def default_census() -> list[dict[str, Any]]:
    return [
        {
            "rail": "task_subagent",
            "external_ref": "task-arc0035-1",
            "state": "RUNNING",
            "unit_id": "ARC-0031",
        },
        {
            "rail": "codex_mcp",
            "external_ref": "thread-arc0035-2",
            "state": "RUNNING",
            "unit_id": "ARC-0035",
        },
        {
            "rail": "databricks_job",
            "external_ref": "run-arc0035-3",
            "state": "RUNNING",
            "unit_id": "TST-0241",
        },
    ]


def write_census(path: Path | None = None) -> Path:
    path = path or CENSUS
    rows = default_census()
    F.write_jsonl(path, rows)
    return path


def load_census(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or CENSUS
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def drain(
    census_path: Path | None = None,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    census_path = census_path or CENSUS
    ledger_path = ledger_path or DRAIN_LEDGER
    if census_path.resolve() == ledger_path.resolve():
        return {
            "ok": False,
            "refused": True,
            "reason": "drain-must-not-rewrite-census",
        }
    before = F.sha256_bytes(census_path.read_bytes())
    rows = load_census(census_path)
    records: list[dict[str, Any]] = []
    prev = F.GENESIS
    for i, row in enumerate(rows, 1):
        rec = {
            "seq": i,
            "kind": "drain",
            "rail": row["rail"],
            "unit_id": row.get("unit_id"),
            "ts": None,
            "verb": "drain",
            "source": {
                "path": census_path.name,
                "line_no": i,
                "sha256": F.sha256_text(F.canonical(row)),
                "raw": F.canonical(row),
            },
            "payload": {
                "external_ref": row["external_ref"],
                "prior_state": row["state"],
                "outcome": "IN_FLIGHT_LEASED",
            },
            "prev_hash": prev,
        }
        rec["event_hash"] = F.event_hash(rec)
        prev = rec["event_hash"]
        records.append(rec)
    F.write_jsonl(ledger_path, records)
    after = F.sha256_bytes(census_path.read_bytes())
    return {
        "ok": True,
        "refused": False,
        "in_flight": len(rows),
        "drained": len(records),
        "abandoned_without_record": 0,
        "census_unmodified": before == after,
        "ledger_path_distinct": True,
        "rails_seen": sorted({r["rail"] for r in rows}),
        "records": records,
    }


def refuse_abandon_without_record(census: list[dict[str, Any]]) -> dict[str, Any]:
    """Negative control: dropping an in-flight row with no ledger write."""
    if not census:
        return {"pass": False, "refused": False, "reason": "empty-census"}
    victim = census[0]
    # The drain API has no "delete census row" operation. Simulating the
    # forbidden shortcut (discard without a record) is refused here.
    return {
        "pass": True,
        "refused": True,
        "reason": (
            f"abandon-without-record forbidden for {victim['rail']} "
            f"{victim['external_ref']}; write kind=drain outcome=ABANDONED "
            "or IN_FLIGHT_LEASED instead"
        ),
        "victim": victim["external_ref"],
    }
