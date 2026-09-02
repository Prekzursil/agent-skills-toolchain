"""Deterministic good and planted-bad turn schedules for each GENERATIVE record."""
from __future__ import annotations


def _emit_turns(act: str, n: int, prefix: str) -> list[dict]:
    return [{"act": act, "body": f"{prefix}-{i}"} for i in range(1, n + 1)]


def good_schedule(record: dict) -> dict:
    """Known-good: GENERATE counting acts, GENERATE_CLOSED, then CRITIQUE."""
    g_act = record["counting_acts"][0]
    c_act = record["critique_acts"][0]
    pid = record["id"]
    rounds: list[dict] = [
        {
            "id": "g1",
            "mode": "GENERATE",
            "turns": _emit_turns(g_act, 3, f"{pid}-a"),
        },
        {
            "id": "g2",
            "mode": "GENERATE",
            "turns": _emit_turns(g_act, 2, f"{pid}-b"),
        },
    ]
    if pid == "P30":
        rounds.insert(
            1,
            {
                "id": "white",
                "mode": "PROCESS",
                "turns": [{"act": "white_hat", "body": "facts-only"}],
            },
        )
    rounds.append({"id": "gate", "mode": "GENERATE_CLOSED", "turns": []})
    rounds.append(
        {
            "id": "c1",
            "mode": "CRITIQUE",
            "turns": [
                {"act": c_act, "target": f"{pid}-1"},
                {"act": c_act, "target": f"{pid}-2"},
            ],
        }
    )
    return {
        "id": f"{pid}-good",
        "record_id": pid,
        "kind": "known-good",
        "rounds": rounds,
    }


def planted_bad_schedule(record: dict) -> dict:
    """Planted-bad: a CRITIQUE act inside a GENERATE round (the leak this check rejects)."""
    g_act = record["counting_acts"][0]
    c_act = record["critique_acts"][0]
    pid = record["id"]
    return {
        "id": f"{pid}-planted-bad",
        "record_id": pid,
        "kind": "planted-bad",
        "rounds": [
            {
                "id": "g1",
                "mode": "GENERATE",
                "turns": [
                    {"act": g_act, "body": f"{pid}-a-1"},
                    {
                        "act": c_act,
                        "body": "planted-critique-in-generate",
                        "feed_critique_into_generate": True,
                    },
                    {"act": g_act, "body": f"{pid}-a-2"},
                ],
            },
            {"id": "gate", "mode": "GENERATE_CLOSED", "turns": []},
            {
                "id": "c1",
                "mode": "CRITIQUE",
                "turns": [{"act": c_act, "target": f"{pid}-1"}],
            },
        ],
    }


def suppression_bad_schedule(record: dict) -> dict:
    """Second planted defect: drop_idea during CRITIQUE would suppress the count."""
    g_act = record["counting_acts"][0]
    pid = record["id"]
    return {
        "id": f"{pid}-suppression-bad",
        "record_id": pid,
        "kind": "planted-bad-suppression",
        "rounds": [
            {
                "id": "g1",
                "mode": "GENERATE",
                "turns": _emit_turns(g_act, 2, f"{pid}-s"),
            },
            {"id": "gate", "mode": "GENERATE_CLOSED", "turns": []},
            {
                "id": "c1",
                "mode": "CRITIQUE",
                "turns": [{"act": "drop_idea", "target": f"{pid}-1"}],
            },
        ],
    }


def critique_before_gate_schedule(record: dict) -> dict:
    """Planted defect: CRITIQUE round before GENERATE_CLOSED."""
    g_act = record["counting_acts"][0]
    c_act = record["critique_acts"][0]
    pid = record["id"]
    return {
        "id": f"{pid}-before-gate-bad",
        "record_id": pid,
        "kind": "planted-bad-critique-before-gate",
        "rounds": [
            {
                "id": "g1",
                "mode": "GENERATE",
                "turns": _emit_turns(g_act, 2, f"{pid}-g"),
            },
            {
                "id": "c-early",
                "mode": "CRITIQUE",
                "turns": [{"act": c_act, "target": f"{pid}-1"}],
            },
            {"id": "gate", "mode": "GENERATE_CLOSED", "turns": []},
        ],
    }


good_schedule = good_schedule
planted_bad_schedule = planted_bad_schedule
suppression_bad_schedule = suppression_bad_schedule
good_schedule = good_schedule
planted_bad_schedule = planted_bad_schedule
suppression_bad_schedule = suppression_bad_schedule
