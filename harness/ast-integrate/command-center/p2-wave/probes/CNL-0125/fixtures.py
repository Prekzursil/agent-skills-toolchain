"""Council-result fixtures for the shared completion reducer."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
REL_GOOD = "command-center/p2-wave/probes/CNL-0125/fixtures/good_body.json"
REL_MISS = "command-center/p2-wave/probes/CNL-0125/fixtures/missing_sentinel_body.json"


def _payload() -> dict:
    return {
        "kind": "council-result",
        "recommendation": "Adopt the shared 12-condition reducer at council fan-in.",
        "action_plan": ["register result", "attach disjoint reviewer", "run consumer"],
        "lineage_root": "idea:I-cnl-0125",
        "dissent": "Minority: a council vote ought to count as C9; rejected as circular.",
        "claim_graph": [
            "idea:I-cnl-0125",
            "option:O1",
            "claim:C1",
            "vote:V1",
            "decision:D1",
        ],
        "pad": "x" * 80,
    }


def write_bodies() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_payload(), indent=2, sort_keys=True) + "\n"
    (REPO / REL_GOOD).write_text(text, encoding="utf-8")
    (REPO / REL_MISS).write_text(text, encoding="utf-8")


def _nbytes(rel: str) -> int:
    return (REPO / rel).stat().st_size


def base_env() -> dict:
    write_bodies()
    n = _nbytes(REL_GOOD)
    return {
        "id": "good",
        "state": "SUCCESS",
        "exit_code": 0,
        "artifact_relpath": REL_GOOD,
        "artifact_bytes": n,
        "min_bytes": 128,
        "schema_ok": True,
        "sentinel": "SUCCESS:COUNCIL-FIXTURE",
        "evidence_anchors": [
            "idea:I-cnl-0125",
            "option:O1",
            "claim:C1",
            "argument:A1",
            "vote:V1",
            "decision:D1",
        ],
        "tests": [{"id": "lineage-orphan-sentence", "result": "PASS"}],
        "negative_controls": [
            {"id": "NC-SENTINEL", "fired_on_bad": True, "silent_on_good": True}
        ],
        "seated_participants": ["alice", "bob", "carol"],
        "reviewer": {"reviewer_id": "external-dave", "verdict": "PASS"},
        "defects": [],
        "manifest": {"registered": True, "sha256_matches": True},
        "consumer": {
            "opened": True,
            "parsed": True,
            "extracted": [
                "sentinel",
                "recommendation",
                "lineage_root",
                "dissent",
            ],
        },
    }


def missing_sentinel() -> dict:
    env = deepcopy(base_env())
    env["id"] = "missing-sentinel"
    env["artifact_relpath"] = REL_MISS
    env["artifact_bytes"] = _nbytes(REL_MISS)
    env["sentinel"] = ""
    env["exit_code"] = 0
    return env


def circular_reviewer() -> dict:
    env = deepcopy(base_env())
    env["id"] = "circular-reviewer"
    env["reviewer"] = {"reviewer_id": "alice", "verdict": "PASS"}
    return env


def unread_consumer() -> dict:
    env = deepcopy(base_env())
    env["id"] = "unread-consumer"
    env["consumer"] = {
        "opened": True,
        "parsed": True,
        "extracted": ["sentinel"],
    }
    return env
