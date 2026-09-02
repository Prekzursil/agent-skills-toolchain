"""In-memory council transcripts. Synthetic token never written to a fixture file."""
from __future__ import annotations

import base64
from typing import Any

from contract import SYNTHETIC_TOKEN

CLEAN_COUNCIL_ID = "cnl-0127-clean"
PLANTED_COUNCIL_ID = "cnl-0127-planted"


def clean_transcript() -> dict[str, Any]:
    return {
        "council_id": CLEAN_COUNCIL_ID,
        "question": "May replay seeds be persisted without vendor credentials?",
        "rounds": [
            {
                "round": 1,
                "seats": [
                    {
                        "seat_id": "S1",
                        "role": "Architect",
                        "vote": "go",
                        "text": "Persist votes, dissent, and replay seeds. Never persist vendor auth.",
                    },
                    {
                        "seat_id": "S2",
                        "role": "Skeptic",
                        "vote": "hold",
                        "text": "Dissent: undeclared retention must refuse persist, not default to forever.",
                    },
                ],
            }
        ],
        "tally": {"go": 1, "hold": 1},
        "stopping_rule_id": "unanimous-or-record-dissent",
        "replay_seeds": {"sampling": 7, "tool_order": 3},
        "input_sha256": "0" * 64,
    }


def planted_plain() -> dict[str, Any]:
    t = clean_transcript()
    t["council_id"] = PLANTED_COUNCIL_ID + "-plain"
    t["rounds"][0]["seats"][0]["text"] = (
        "Injected synthetic token-shaped span for the pre-persist scan."
    )
    t["planted"] = SYNTHETIC_TOKEN
    return t


def planted_env() -> dict[str, Any]:
    t = clean_transcript()
    t["council_id"] = PLANTED_COUNCIL_ID + "-env"
    t["rounds"][0]["seats"][1]["text"] = (
        f"CNL0127_SYNTHETIC_API_KEY={SYNTHETIC_TOKEN}"
    )
    return t


def planted_json() -> dict[str, Any]:
    t = clean_transcript()
    t["council_id"] = PLANTED_COUNCIL_ID + "-json"
    t["rounds"][0]["seats"][0]["text"] = (
        '{"apiKey":"%s","note":"synthetic-only"}' % SYNTHETIC_TOKEN
    )
    return t


def planted_camel() -> dict[str, Any]:
    t = clean_transcript()
    t["council_id"] = PLANTED_COUNCIL_ID + "-camel"
    t["rounds"][0]["seats"][0]["text"] = f"config apiKey='{SYNTHETIC_TOKEN}'"
    return t


def planted_b64() -> dict[str, Any]:
    t = clean_transcript()
    t["council_id"] = PLANTED_COUNCIL_ID + "-b64"
    wrapped = base64.b64encode(SYNTHETIC_TOKEN.encode("utf-8")).decode("ascii")
    t["rounds"][0]["seats"][0]["text"] = f"envelope {wrapped}"
    return t


def planted_encodings() -> dict[str, dict[str, Any]]:
    return planted_encodings()


def planted_encodings() -> dict[str, dict[str, Any]]:
    return {
        "plain": planted_plain(),
        "env": planted_env(),
        "json": planted_json(),
        "camel": planted_camel(),
        "b64": planted_b64(),
    }
