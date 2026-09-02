"""Sweep executed-workflow transcripts joined to the event ledger on agentId."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from corpus import H_FAMILY, h_family_candidates, materialize
from join import (
    CONTENT_HASH_FIELD,
    JOIN_ON,
    index_by_agent_id,
    join_transcripts_to_ledger,
    trap_collapse_on_content_hash,
)
from jsonl_io import read_jsonl
from locate import inspect_live
from neutralize import neutralize_events
from recover import match_h_family, recover_stages

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _load_jsonl_tree(root: Path | None) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad = 0
    if root is None or not root.is_dir():
        return rows, bad
    for path in sorted(root.rglob("*.jsonl")):
        chunk, nbad = read_jsonl(path)
        rows.extend(chunk)
        bad += nbad
    return rows, bad


def recover_runs(
    transcripts_by_agent: dict[str, list[dict[str, Any]]],
    join_result: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    duration_by_agent = {
        row["agentId"]: row.get("duration_ms") for row in join_result.get("matched") or []
    }
    recovered: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []
    matched_cands: list[dict[str, Any]] = []
    all_hits: list[dict[str, Any]] = []
    led_only_dur = {
        d["agentId"]: d.get("duration_ms")
        for d in (join_result.get("discrepancies") or [])
        if d.get("kind") == "ledger-absent-from-transcripts"
    }
    for aid in join_result["union_agent_ids"]:
        events = transcripts_by_agent.get(aid) or []
        cleaned, hits = neutralize_events(events)
        for hit in hits:
            tagged = dict(hit)
            tagged["agentId"] = aid
            all_hits.append(tagged)
        stages = recover_stages(cleaned)
        if not events:
            recovered.append(
                {
                    "agentId": aid,
                    "stages": [],
                    "stage_source": "ledger-only-no-transcript",
                    "duration_ms": led_only_dur.get(aid),
                    "registry": {
                        "matched": False,
                        "candidate_id": None,
                        "reason": "no-transcript-stages",
                    },
                    "neutralizations": 0,
                }
            )
            continue
        reg = match_h_family(stages, candidates)
        rec = {
            "agentId": aid,
            "stages": stages,
            "stage_source": "transcript-after-neutralize",
            "duration_ms": duration_by_agent.get(aid),
            "registry": reg,
            "neutralizations": len(hits),
        }
        recovered.append(rec)
        if stages and not reg["matched"]:
            orphans.append(
                {
                    "agentId": aid,
                    "stages": stages,
                    "reason": "executed-sequence-has-no-h-family-registry-candidate",
                }
            )
        elif reg["matched"]:
            matched_cands.append(
                {
                    "agentId": aid,
                    "candidate_id": reg["candidate_id"],
                    "stages": stages,
                }
            )
    return recovered, orphans, all_hits, matched_cands


def run_sweep() -> dict[str, Any]:
    planted = materialize()
    live = inspect_live()
    transcripts = {aid: list(rows) for aid, rows in planted["transcripts"].items()}
    ledger = list(planted["ledger"])
    journal = list(planted["journal"])
    candidates = h_family_candidates(planted["registry"])

    tx_root = Path(live["live_transcript_root"]) if live.get("live_transcript_root") else None
    led_root = Path(live["live_ledger_root"]) if live.get("live_ledger_root") else None
    live_tx, live_tx_bad = _load_jsonl_tree(tx_root)
    live_led, live_led_bad = _load_jsonl_tree(led_root)
    if live.get("live_transcript_count"):
        for aid, rows in index_by_agent_id(live_tx).items():
            transcripts.setdefault(aid, []).extend(rows)
    if live.get("live_ledger_present"):
        ledger_by = index_by_agent_id(ledger)
        for aid, rows in index_by_agent_id(live_led).items():
            ledger_by.setdefault(aid, []).extend(rows)
        ledger = [row for rows in ledger_by.values() for row in rows]

    tx_by = transcripts
    led_by = index_by_agent_id(ledger)
    joined = join_transcripts_to_ledger(tx_by, led_by)
    trap = trap_collapse_on_content_hash(journal)
    recovered, orphans, hits, matched_cands = recover_runs(tx_by, joined, candidates)
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    return {
        "corpus_mode": (
            "live+fixture"
            if live.get("live_transcript_count") or live.get("live_ledger_present")
            else "fixture-control"
        ),
        "live": live,
        "live_parse_errors": {"transcripts": live_tx_bad, "ledger": live_led_bad},
        "join": joined,
        "content_hash_trap": trap,
        "recovered_runs": recovered,
        "orphan_stage_sequences": orphans,
        "matched_registry_candidates": matched_cands,
        "neutralizations": hits,
        "h_family_candidates_in_play": [c["id"] for c in candidates],
        "h_family_claimed_n": 72,
        "schema_pack_present": schema_pack.is_file(),
        "schema_pack_path": "command-center/wfa/schema/wfa-schema-pack.json",
        "planted": {
            "shared_journal_key": planted["shared_key"],
            "inject_marker": planted["inject_marker"],
        },
        "join_key": JOIN_ON,
        "rejected_join_field": CONTENT_HASH_FIELD,
        "h_family": H_FAMILY,
        "transcript_event_count": sum(len(v) for v in tx_by.values()),
        "ledger_row_count": len(ledger),
    }
