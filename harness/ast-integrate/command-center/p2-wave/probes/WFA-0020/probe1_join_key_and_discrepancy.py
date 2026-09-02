#!/usr/bin/env python3
"""Probe 1: join on agentId; content-hash trap; both-way discrepancies kept."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import join as J  # noqa: E402
from corpus import materialize  # noqa: E402
from join import (  # noqa: E402
    CONTENT_HASH_FIELD,
    JOIN_ON,
    index_by_agent_id,
    join_transcripts_to_ledger,
    trap_collapse_on_content_hash,
)

UNIT = "WFA-0020"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def inspect_join_source() -> None:
    text = (HERE / "join.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    assigns = {
        node.targets[0].id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    join_on = assigns.get("JOIN_ON")
    trap_field = assigns.get("CONTENT_HASH_FIELD")
    if not isinstance(join_on, ast.Constant) or join_on.value != "agentId":
        raise SystemExit("JOIN_ON is not the asserted constant agentId")
    if not isinstance(trap_field, ast.Constant) or trap_field.value != "key":
        raise SystemExit("CONTENT_HASH_FIELD is not the journal key trap")
    if "CONTENT-HASH TRAP" not in text:
        raise SystemExit("join.py comment does not name the CONTENT-HASH TRAP")
    if "Never join on `key`" not in text and "Never join on journal `key`" not in text:
        if "join transcripts to the ledger on `key`" not in text:
            raise SystemExit("join.py does not name the key trap in comments")


def inner_join_dropper(
    transcripts_by_agent: dict, ledger_by_agent: dict
) -> dict:
    """Mutant: keep only the intersection (the forbidden drop)."""
    honest = join_transcripts_to_ledger(transcripts_by_agent, ledger_by_agent)
    keep = set(honest["matched_agent_ids"])
    return {
        "matched_agent_ids": honest["matched_agent_ids"],
        "transcript_only_agent_ids": [],
        "ledger_only_agent_ids": [],
        "discrepancies": [d for d in honest["discrepancies"] if d["agentId"] in keep],
        "union_agent_ids": sorted(keep),
        "dropped_count": len(honest["union_agent_ids"]) - len(keep),
    }


def main() -> int:
    inspect_join_source()
    if J.JOIN_ON != "agentId":
        return fail(f"JOIN_ON={J.JOIN_ON!r}")
    if J.CONTENT_HASH_FIELD != "key":
        return fail(f"CONTENT_HASH_FIELD={J.CONTENT_HASH_FIELD!r}")

    planted = materialize()
    tx = planted["transcripts"]
    led = index_by_agent_id(planted["ledger"])
    honest = join_transcripts_to_ledger(tx, led)
    trap = trap_collapse_on_content_hash(planted["journal"])

    kinds = {d["kind"] for d in honest["discrepancies"]}
    tx_only = set(honest["transcript_only_agent_ids"])
    led_only = set(honest["ledger_only_agent_ids"])
    matched = set(honest["matched_agent_ids"])

    if "ag-tx-only-01" not in tx_only:
        return fail(f"transcript-only agent dropped {sorted(tx_only)}")
    if "ag-led-only-01" not in led_only:
        return fail(f"ledger-only agent dropped {sorted(led_only)}")
    if "transcript-absent-from-ledger" not in kinds or "ledger-absent-from-transcripts" not in kinds:
        return fail(f"asymmetric kinds {sorted(kinds)}")
    if honest["dropped_count"] != 0:
        return fail(f"honest join dropped {honest['dropped_count']}")
    for aid in ("ag-match-01", "ag-orphan-01", "ag-hash-a", "ag-hash-b", "ag-inject-01"):
        if aid not in matched:
            return fail(f"expected matched {aid} not in {sorted(matched)}")

    dur = {row["agentId"]: row["duration_ms"] for row in honest["matched"]}
    if dur.get("ag-hash-a") == dur.get("ag-hash-b"):
        return fail("hash-collision agents should keep distinct ledger durations")
    if dur.get("ag-hash-a") != 240000 or dur.get("ag-hash-b") != 480000:
        return fail(f"durations {dur}")

    if trap["collision_count"] < 1:
        return fail("content-hash trap did not collide ag-hash-a/b")
    collided = trap["collisions"][0]["agent_ids"]
    if set(collided) != {"ag-hash-a", "ag-hash-b"}:
        return fail(f"trap agents {collided}")
    if trap["collisions"][0]["key"] != planted["shared_key"]:
        return fail("trap key mismatch")

    mutant = inner_join_dropper(tx, led)
    if mutant["dropped_count"] < 2:
        return fail("inner-join mutant did not drop the asymmetric runs")
    if "ag-tx-only-01" in mutant["union_agent_ids"] or "ag-led-only-01" in mutant["union_agent_ids"]:
        return fail("inner-join mutant still lists asymmetric agents")
    if mutant["dropped_count"] <= honest["dropped_count"]:
        return fail("mutant must drop more than the honest join")

    payload = {
        "pass": True,
        "probe": "probe1-join-key-and-discrepancy",
        "unit_id": UNIT,
        "join_key": JOIN_ON,
        "rejected_join_field": CONTENT_HASH_FIELD,
        "matched_agent_ids": honest["matched_agent_ids"],
        "transcript_only_agent_ids": honest["transcript_only_agent_ids"],
        "ledger_only_agent_ids": honest["ledger_only_agent_ids"],
        "discrepancy_kinds": sorted(kinds),
        "honest_dropped_count": honest["dropped_count"],
        "mutant_dropped_count": mutant["dropped_count"],
        "trap_collision_count": trap["collision_count"],
        "trap_agent_ids": collided,
        "hash_a_duration_ms": dur["ag-hash-a"],
        "hash_b_duration_ms": dur["ag-hash-b"],
        "both_states": {
            "honest_keeps_asymmetric": True,
            "inner_join_mutant_drops_asymmetric": True,
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0020-probe1 join=agentId; journal key trap collides hash-a/b; "
        "transcript-only and ledger-only reported, not dropped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
