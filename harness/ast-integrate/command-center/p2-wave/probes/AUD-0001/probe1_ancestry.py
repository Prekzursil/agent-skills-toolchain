#!/usr/bin/env python3
"""Probe 1: git rev-list --count main..<branch> plus git cherry -v main <branch>."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

ART = REPO / C.OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0001-probe1 {msg}")
    return 1


def main() -> int:
    bundle = C.live_bundle()
    fixture = bundle["fixture"]
    squash = C.by_name(fixture, C.SQUASH_BRANCH)
    unmerged = C.by_name(fixture, C.UNMERGED_BRANCH)
    on_main = C.by_name(fixture, C.ON_MAIN_BRANCH)
    if squash is None:
        return fail("squash branch missing from fixture")
    if not squash["ancestry_ahead"] or int(squash["ancestry_ahead_count"]) <= 0:
        return fail(
            f"ancestry-only detector did not report squash branch ahead: {squash}"
        )
    if unmerged is None or not unmerged["ancestry_ahead"]:
        return fail("unmerged branch not ancestry-ahead")
    if on_main is None or on_main["ancestry_ahead"]:
        return fail("already-on-main must not be ancestry-ahead")
    if squash.get("cherry_exit") not in (0,):
        return fail(f"git cherry failed: {squash.get('cherry_raw')}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    blob = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(blob)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")
    if C.SENTINEL not in blob:
        return fail("sentinel-absent")
    headline = doc.get("headline") or {}
    if int(headline.get("ancestry_ahead") or 0) < 1:
        return fail("headline ancestry_ahead missing")
    rec = None
    for row in (doc.get("fixture") or {}).get("branches") or []:
        if row.get("branch") == C.SQUASH_BRANCH:
            rec = row
            break
    if rec is None:
        return fail("artifact missing squash branch row")
    if not rec.get("ancestry_ahead"):
        return fail("artifact squash row is not ancestry-ahead")
    if rec.get("head_sha") != squash["head_sha"]:
        return fail("artifact squash head_sha drifted from live fixture")
    probes = doc.get("named_probes") or []
    if len(probes) < 2:
        return fail("named probes not recorded")

    payload = {
        "pass": True,
        "probe": "probe1-ancestry",
        "unit_id": "AUD-0001",
        "squash_ahead_count": squash["ancestry_ahead_count"],
        "squash_cherry_plus": squash["cherry_plus"],
        "squash_cherry_minus": squash["cherry_minus"],
        "unmerged_ahead_count": unmerged["ancestry_ahead_count"],
        "already_on_main_ahead": on_main["ancestry_ahead"],
        "head_sha": squash["head_sha"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"squash_ahead={squash['ancestry_ahead_count']} "
        f"cherry=+{squash['cherry_plus']}/-{squash['cherry_minus']} "
        f"unmerged_ahead={unmerged['ancestry_ahead_count']}"
    )
    print("SUCCESS:AUD-0001-probe1 ancestry rev-list+cherry squash reports AHEAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
