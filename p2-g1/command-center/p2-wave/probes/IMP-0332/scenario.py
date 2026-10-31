"""Shared NGT fixture runner for IMP-0332 probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.ngt import NgtSession  # noqa: E402

FIXTURE = HERE / "fixtures" / "session.json"


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def canary_to_idea_id(session: NgtSession) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in session.catalog:
        text = row["text"]
        prefix = text.split(":", 1)[0].strip()
        mapping[prefix] = row["idea_id"]
    return mapping


def resolve_ranking(session: NgtSession, canaries: list[str]) -> list[str]:
    mapping = canary_to_idea_id(session)
    missing = [c for c in canaries if c not in mapping]
    if missing:
        raise KeyError(f"canary prefixes not in catalog: {missing}")
    return [mapping[c] for c in canaries]


def run_session(*, leak: dict[str, str] | None = None, midstream_rank: bool = True) -> dict[str, Any]:
    """Drive silent generation -> private ranking -> optional planted leak.

    midstream_rank: alice submits her ballot before bob/cara receive ranking
    prompts, so a broadcast-on-submit bug would show in bob's prompt.
    """
    fixture = load_fixture()
    session = NgtSession(fixture["question"], fixture["participants"])
    gen_first = {}
    for pid in fixture["participants"]:
        gen_first[pid] = session.deliver_generation_prompt(pid)
    alice = fixture["participants"][0]
    session.submit_ideas(alice, fixture["ideas"][alice])
    gen_after_alice = session.deliver_generation_prompt(fixture["participants"][1])
    for pid in fixture["participants"]:
        if pid == alice:
            continue
        session.submit_ideas(pid, fixture["ideas"][pid])
    session.close_generation()
    ranking_prompts: dict[str, dict[str, Any]] = {}
    order = list(fixture["participants"])
    if midstream_rank:
        first = order[0]
        ranking_prompts[first] = session.deliver_ranking_prompt(first)
        session.submit_ranking(
            first,
            resolve_ranking(session, fixture["rankings_by_canary"][first]),
        )
        rest = order[1:]
    else:
        rest = order
    for pid in rest:
        ranking_prompts[pid] = session.deliver_ranking_prompt(pid)
        session.submit_ranking(
            pid,
            resolve_ranking(session, fixture["rankings_by_canary"][pid]),
        )
    leaked = None
    if leak:
        leaked = session.leak_ranking_into_prompt(leak["source"], leak["dest"])
    return {
        "fixture": fixture,
        "session": session,
        "gen_first": gen_first,
        "gen_after_alice": gen_after_alice,
        "ranking_prompts": ranking_prompts,
        "leaked": leaked,
        "canary_map": canary_to_idea_id(session),
    }
