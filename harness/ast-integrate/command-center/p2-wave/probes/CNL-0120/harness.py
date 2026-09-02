"""Deterministic scripted-participant council for CNL-0120.

This is a unit-local stand-in for the CNL-0117 harness (that artifact is
absent on this worktree). Positions, votes and the single dissent are
scripted; the run is a function of the fixture JSON, not of an LLM.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "council.json"
GENERIC_DROP_PHRASE = "Dissent was considered."


def load_fixture(path: Path | None = None) -> dict[str, Any]:
    p = path or FIXTURE
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("fixture-not-object")
    return doc


def dissenters(script: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in script.get("participants") or []:
        if isinstance(p, dict) and str(p.get("vote") or "").upper() == "NO":
            out.append(p)
    return out


def assert_exactly_one_dissent(script: dict[str, Any]) -> dict[str, Any]:
    no = dissenters(script)
    if len(no) != 1:
        raise ValueError(f"expected-exactly-one-dissent got={len(no)}")
    d = no[0]
    for key in ("claim_id", "token", "counterexample", "brief"):
        if not str(d.get(key) or "").strip():
            raise ValueError(f"dissent-missing-{key}")
    return d


def transcript_of(script: dict[str, Any]) -> dict[str, Any]:
    """Transcript always records the live votes, including the dissent."""
    d = assert_exactly_one_dissent(script)
    turns = []
    for p in script["participants"]:
        turn = {
            "participant_id": p["id"],
            "role": p["role"],
            "vote": p["vote"],
            "brief": p["brief"],
        }
        if str(p.get("vote") or "").upper() == "NO":
            turn["claim_id"] = p["claim_id"]
            turn["token"] = p["token"]
            turn["counterexample"] = p["counterexample"]
        turns.append(turn)
    return {
        "council_id": script["id"],
        "question": script["question"],
        "turns": turns,
        "dissent": {
            "participant_id": d["id"],
            "claim_id": d["claim_id"],
            "token": d["token"],
            "claim": d.get("claim") or d["brief"],
            "counterexample": d["counterexample"],
        },
        "dissent_count": 1,
    }


def synthesize_intact(transcript: dict[str, Any]) -> dict[str, Any]:
    """Majority ADOPT plus a minority report that copies the dissent verbatim."""
    d = transcript["dissent"]
    yes = [t for t in transcript["turns"] if t["vote"] == "YES"]
    return {
        "decision": "ADOPT",
        "majority": [
            {"participant_id": t["participant_id"], "vote": t["vote"]} for t in yes
        ],
        "minority_report": [
            {
                "claim_id": d["claim_id"],
                "participant_id": d["participant_id"],
                "token": d["token"],
                "claim": d["claim"],
                "counterexample": d["counterexample"],
                "vote": "NO",
            }
        ],
        "recommendation": (
            "Adopt hashed-cache as the default session store. "
            f"Minority report {d['claim_id']} is attached verbatim, token "
            f"{d['token']}. Counterexample: {d['counterexample']}"
        ),
    }


def plant_drop(run: dict[str, Any]) -> dict[str, Any]:
    """Deliberately remove the dissent from synthesis only.

    Transcript is left intact. Generic language is planted so a presence-of-
    any-text check would still go green. The preservation check must not.
    """
    planted = copy.deepcopy(run)
    token = planted["transcript"]["dissent"]["token"]
    claim_id = planted["transcript"]["dissent"]["claim_id"]
    cex = planted["transcript"]["dissent"]["counterexample"]
    syn = {
        "decision": "ADOPT",
        "majority": copy.deepcopy(planted["synthesis"]["majority"]),
        "minority_report": [],
        "recommendation": f"Adopt hashed-cache as the default session store. {GENERIC_DROP_PHRASE}",
    }
    blob = json.dumps(syn, ensure_ascii=True)
    if token in blob or claim_id in blob or cex in blob:
        raise RuntimeError("plant-drop-failed-residue")
    planted["synthesis"] = syn
    planted["planted_drop"] = True
    return planted


def run_intact(script: dict[str, Any] | None = None) -> dict[str, Any]:
    script = script or load_fixture()
    transcript = transcript_of(script)
    synthesis = synthesize_intact(transcript)
    return {
        "script_id": script["id"],
        "transcript": transcript,
        "synthesis": synthesis,
        "planted_drop": False,
    }
