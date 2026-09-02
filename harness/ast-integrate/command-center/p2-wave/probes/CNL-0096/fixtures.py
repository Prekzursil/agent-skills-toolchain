"""Named fixtures for CNL-0096 both-states and detector-control."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX_DIR = HERE / "fixtures"

SPEAKERS = ("architect", "skeptic", "pragmatist", "critic")

PLANTED = (
    "planted-masquerade",
    "planted-work-lost",
    "planted-false-exhaustion",
)
CLEAN = (
    "good-genuine-no-decision",
    "good-cap-exhausted",
    "good-decision-before-cap",
    "good-decision-on-last-round",
)
CONTROL_ID = "planted-masquerade"
PAIR_GENUINE = "good-genuine-no-decision"
PAIR_EXHAUSTED = "good-cap-exhausted"


def _transcript(n: int, last: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(n):
        text = (
            last
            if i == n - 1
            else f"round-{i + 1} position on option-{chr(65 + (i % 2))}"
        )
        rows.append(
            {
                "round": i + 1,
                "speaker": SPEAKERS[i % 4],
                "text": text,
            }
        )
    return rows


def _positions() -> dict[str, str]:
    return {
        "architect": "option-A",
        "skeptic": "option-B",
        "pragmatist": "option-A-with-conditions",
        "critic": "option-B",
    }


def _gain(n: int) -> list[int]:
    # Early rounds add claims; later rounds collapse — not used as the stop.
    out = []
    for i in range(n):
        out.append(max(0, 3 - i))
    return out


def _base(*, rid: str, rounds: int, cap: int, outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rid,
        "hard_cap": {"kind": "max_rounds", "value": cap},
        "rounds_consumed": rounds,
        "outcome": outcome,
        "transcript": _transcript(rounds, outcome.get("terminal_note") or "close"),
        "last_positions": _positions(),
        "vote_snapshot": {"option-A": 2, "option-B": 2},
        "dissent_ids": ["D1-option-B-risk"],
        "information_gain_by_round": _gain(rounds),
    }


def definitions() -> dict[str, dict[str, Any]]:
    masquerade = _base(
        rid="planted-masquerade",
        rounds=12,
        cap=12,
        outcome={
            "kind": "no-decision",
            "termination_cause": "deliberative",
            "no_decision_reason": "could not agree",
            "terminal_note": "stop labelled as genuine no-decision after the wall",
        },
    )
    work_lost = _base(
        rid="planted-work-lost",
        rounds=12,
        cap=12,
        outcome={
            "kind": "exhausted_without_decision",
            "termination_cause": "hard_cap",
            "terminal_note": "cap hit; payload then dropped",
        },
    )
    work_lost["transcript"] = []
    work_lost["last_positions"] = {}
    work_lost["vote_snapshot"] = {}
    work_lost["information_gain_by_round"] = []

    false_exh = _base(
        rid="planted-false-exhaustion",
        rounds=4,
        cap=12,
        outcome={
            "kind": "exhausted_without_decision",
            "termination_cause": "hard_cap",
            "terminal_note": "claimed exhaustion with budget remaining",
        },
    )

    genuine = _base(
        rid="good-genuine-no-decision",
        rounds=6,
        cap=12,
        outcome={
            "kind": "no-decision",
            "termination_cause": "deliberative",
            "no_decision_reason": "question underspecified; owner must reframe",
            "terminal_note": "chose not to decide with budget remaining",
        },
    )
    exhausted = _base(
        rid="good-cap-exhausted",
        rounds=12,
        cap=12,
        outcome={
            "kind": "exhausted_without_decision",
            "termination_cause": "hard_cap",
            "terminal_note": "hard cap; work preserved under a distinct kind",
        },
    )
    decided = _base(
        rid="good-decision-before-cap",
        rounds=8,
        cap=12,
        outcome={
            "kind": "decision",
            "termination_cause": "agreement",
            "chosen": "option-A-with-conditions",
            "terminal_note": "decided before the wall",
        },
    )
    last_round = _base(
        rid="good-decision-on-last-round",
        rounds=12,
        cap=12,
        outcome={
            "kind": "decision",
            "termination_cause": "agreement",
            "chosen": "option-A-with-conditions",
            "terminal_note": "agreement on the last allowed round is still a decision",
        },
    )
    return {
        masquerade["id"]: masquerade,
        work_lost["id"]: work_lost,
        false_exh["id"]: false_exh,
        genuine["id"]: genuine,
        exhausted["id"]: exhausted,
        decided["id"]: decided,
        last_round["id"]: last_round,
    }


def dump_json() -> None:
    FIX_DIR.mkdir(parents=True, exist_ok=True)
    for rid, doc in definitions().items():
        path = FIX_DIR / f"{rid}.json"
        path.write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def load(rid: str) -> dict[str, Any]:
    path = FIX_DIR / f"{rid}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return deepcopy(definitions()[rid])
