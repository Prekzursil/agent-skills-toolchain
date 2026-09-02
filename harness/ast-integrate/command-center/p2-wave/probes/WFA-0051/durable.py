"""Refuse a file that pretends to be a durable execution log."""
from __future__ import annotations

from pathlib import Path

from ir_vocab import ARCHITECTURE_LANE, REQUIRES_DURABLE_LOG
from mappings import architecture_tickets, assert_no_file_fake, mechanism_rows

FORBIDDEN_BASENAMES = (
    "temporal-history.json",
    "temporal-history.jsonl",
    "workflow-history.jsonl",
    "event-log.jsonl",
    "durable-log.sqlite",
)


def detect_file_fake(root: Path) -> list[str]:
    hits: list[str] = []
    if not root.is_dir():
        return hits
    for name in FORBIDDEN_BASENAMES:
        p = root / name
        if p.exists():
            hits.append(str(p))
    return hits


def routing_report(probe_dir: Path) -> dict:
    rows = mechanism_rows()
    assert_no_file_fake(rows)
    tickets = architecture_tickets(rows)
    fakes = detect_file_fake(probe_dir)
    durable = [r for r in rows if r["requires_durable_log"]]
    unrouted = [
        f"{r['framework']}:{r['mechanism']}"
        for r in durable
        if r["routed_to"] != ARCHITECTURE_LANE
    ]
    mapped_or_flagged = []
    for r in rows:
        ok = bool(r.get("ir_field")) or r["disposition"] == REQUIRES_DURABLE_LOG
        mapped_or_flagged.append(ok)
    return {
        "architecture_ticket_count": len(tickets),
        "durable_row_count": len(durable),
        "fake_history_files": fakes,
        "mapped_or_flagged_all": all(mapped_or_flagged),
        "row_count": len(rows),
        "unrouted": unrouted,
    }


def mutant_file_fake(rows: list[dict]) -> list[dict]:
    """BAD arm: Temporal replay backed by a JSONL file instead of architecture."""
    out = []
    for r in rows:
        item = dict(r)
        if r["framework"] == "temporal" and r["mechanism"] == "deterministic_replay":
            item["history_file"] = "temporal-history.jsonl"
            item["requires_durable_log"] = False
            item["routed_to"] = None
            item["architecture_ticket"] = None
            item["disposition"] = "FAKED-FILE-LOG"
        out.append(item)
    return out


def mutant_caught(rows: list[dict]) -> dict:
    bad = mutant_file_fake(rows)
    faked = [
        r
        for r in bad
        if r.get("history_file")
        or (
            r["framework"] == "temporal"
            and r["mechanism"] == "deterministic_replay"
            and r["routed_to"] != ARCHITECTURE_LANE
        )
    ]
    return {"caught": bool(faked), "faked_count": len(faked)}
