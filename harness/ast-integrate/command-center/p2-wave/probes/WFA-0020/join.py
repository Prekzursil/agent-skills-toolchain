"""Join executed-run records on agentId.

JOIN KEY (asserted): agentId

CONTENT-HASH TRAP: the Claude Code journal field `key` is a hash of message
content. It does not label the agent. Joining transcripts to the ledger (or
collapsing journal rows) on `key` is a measured join defect on this estate:
two agents that emitted identical payloads (retries, shared templates) collide
and one run is silently dropped. Never join on `key`.
"""
from __future__ import annotations

from typing import Any, Iterable

# JOIN KEY (asserted): agentId — not journal `key` (content-hash trap, above).
JOIN_KEY = "agentId"
JOIN_ON = "agentId"
JOURNAL_CONTENT_HASH_FIELD = "key"
CONTENT_HASH_FIELD = "key"


def agent_id_of(record: dict[str, Any] | None) -> str | None:
    if not isinstance(record, dict):
        return None
    raw = record.get(JOIN_KEY)
    if raw is None:
        raw = record.get("agent_id")
    if raw is None or raw == "":
        return None
    return str(raw)


def journal_content_hash_of(record: dict[str, Any] | None) -> str | None:
    if not isinstance(record, dict):
        return None
    raw = record.get(JOURNAL_CONTENT_HASH_FIELD)
    if raw is None or raw == "":
        return None
    return str(raw)


def index_by_agent_id(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        aid = agent_id_of(rec)
        if aid is None:
            continue
        out.setdefault(aid, []).append(rec)
    return out


def index_by_content_hash(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Diagnostic only. This is the content-hash trap. Do not use for delivery joins."""
    out: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        key = journal_content_hash_of(rec)
        if key is None:
            continue
        out.setdefault(key, []).append(rec)
    return out


def join_transcripts_and_ledger(
    transcripts_by_agent: dict[str, list[dict[str, Any]]],
    ledger_by_agent: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Inner+outer join on agentId. Asymmetric presence is a discrepancy, never a drop."""
    tx_ids = set(transcripts_by_agent)
    led_ids = set(ledger_by_agent)
    matched = sorted(tx_ids & led_ids)
    tx_only = sorted(tx_ids - led_ids)
    led_only = sorted(led_ids - tx_ids)
    discrepancies = []
    for aid in tx_only:
        discrepancies.append(
            {
                "kind": "transcript-absent-from-ledger",
                "agentId": aid,
                "dropped": False,
                "transcript_event_count": len(transcripts_by_agent[aid]),
            }
        )
    for aid in led_only:
        rows = ledger_by_agent[aid]
        durations = [r.get("duration_ms") for r in rows if r.get("duration_ms") is not None]
        discrepancies.append(
            {
                "kind": "ledger-absent-from-transcripts",
                "agentId": aid,
                "dropped": False,
                "ledger_row_count": len(rows),
                "duration_ms": durations[0] if durations else None,
                "run_ids": [r.get("runId") or r.get("run_id") for r in rows],
            }
        )
    matched_rows = []
    for aid in matched:
        led_rows = ledger_by_agent[aid]
        durations = [r.get("duration_ms") for r in led_rows if r.get("duration_ms") is not None]
        run_ids = [r.get("runId") or r.get("run_id") for r in led_rows]
        matched_rows.append(
            {
                "agentId": aid,
                "transcript_event_count": len(transcripts_by_agent[aid]),
                "ledger_row_count": len(led_rows),
                "duration_ms": durations[0] if durations else None,
                "run_ids": run_ids,
            }
        )
    return {
        "join_key": JOIN_KEY,
        "rejected_join_field": JOURNAL_CONTENT_HASH_FIELD,
        "matched_agent_ids": matched,
        "matched": matched_rows,
        "transcript_only_agent_ids": tx_only,
        "ledger_only_agent_ids": led_only,
        "discrepancies": discrepancies,
        "union_agent_ids": sorted(tx_ids | led_ids),
        "dropped_count": 0,
    }


def trap_join_on_journal_key(journal_rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Show why joining on journal `key` is a trap: distinct agentIds collapse."""
    by_key = index_by_content_hash(journal_rows)
    collisions = []
    for key, rows in sorted(by_key.items()):
        aids = sorted({agent_id_of(r) or "" for r in rows} - {""})
        if len(aids) > 1:
            collisions.append(
                {
                    "key": key,
                    "agent_ids": aids,
                    "distinct_agentIds": aids,
                    "row_count": len(rows),
                }
            )
    return {
        "field": JOURNAL_CONTENT_HASH_FIELD,
        "groups": len(by_key),
        "collisions": collisions,
        "collision_count": len(collisions),
        "collisions_found": len(collisions),
    }


join_transcripts_to_ledger = join_transcripts_and_ledger
trap_collapse_on_content_hash = trap_join_on_journal_key
