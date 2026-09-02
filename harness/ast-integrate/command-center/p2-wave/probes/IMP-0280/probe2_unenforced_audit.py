#!/usr/bin/env python3
"""Probe 2: remove one enforcement call; the audit must report that right unenforced."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.roles.mandate import (  # noqa: E402
    MODULE_REL,
    RIGHTS,
    empty_mandate,
    load_source,
    point_of_use_audit,
    seat,
    strip_enforcement,
)

UNIT = "IMP-0280"
MUTANT_RIGHT = "vote"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def load_ns(source: str) -> dict:
    ns: dict = {}
    exec(compile(source, "<IMP-0280-mutant>", "exec"), ns)
    return ns


def main() -> int:
    path = REPO / MODULE_REL
    if not path.is_file():
        return fail(f"{MODULE_REL} missing")
    live_src = load_source(path)
    live_bytes = path.read_bytes()

    live_audit = point_of_use_audit(live_src)
    if live_audit.unenforced_rights():
        return fail(
            f"live audit already unenforced={list(live_audit.unenforced_rights())}"
        )
    if set(live_audit.enforced_rights()) != set(RIGHTS):
        return fail(f"live enforced={list(live_audit.enforced_rights())}")

    mutant_src = strip_enforcement(live_src, MUTANT_RIGHT)
    if mutant_src == live_src:
        return fail("strip_enforcement was a no-op")

    mutant_audit = point_of_use_audit(mutant_src)
    unenforced = list(mutant_audit.unenforced_rights())
    if MUTANT_RIGHT not in unenforced:
        return fail(f"mutant audit did not report {MUTANT_RIGHT} unenforced: {unenforced}")
    still = [r for r in RIGHTS if r != MUTANT_RIGHT]
    missing = [r for r in still if r not in mutant_audit.enforced_rights()]
    if missing:
        return fail(f"mutant over-reported unenforced {missing}")

    ns = load_ns(mutant_src)
    denied = ns["seat"]("mutant-empty", ns["empty_mandate"]("empty"))
    mutant_vote = ns["cast_vote"](denied, "aye")
    if mutant_vote.allowed is not True:
        return fail(
            f"mutant still refused vote without grant: {mutant_vote.to_dict()}"
        )
    live_vote = __import__(
        "council.roles.mandate", fromlist=["cast_vote"]
    ).cast_vote(seat("live-empty", empty_mandate("empty")), "aye")
    if live_vote.allowed:
        return fail("live cast_vote allowed an empty mandate")

    if path.read_bytes() != live_bytes:
        return fail(f"{MODULE_REL} bytes changed by the probe")
    relive = point_of_use_audit()
    if relive.unenforced_rights():
        return fail("live audit drifted after mutant exec")

    payload = {
        "probe": "probe2-unenforced-audit",
        "unit_id": UNIT,
        "mutant_right": MUTANT_RIGHT,
        "live_unenforced": list(live_audit.unenforced_rights()),
        "mutant_unenforced": unenforced,
        "mutant_vote_without_grant_allowed": True,
        "live_vote_without_grant_allowed": False,
        "source_unchanged": True,
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"mutant_right={MUTANT_RIGHT} mutant_unenforced={unenforced} "
        "live_refuses=True mutant_allows=True source_unchanged=True"
    )
    print(
        "SUCCESS:IMP-0280-probe2 remove vote enforcement; audit reports unenforced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
