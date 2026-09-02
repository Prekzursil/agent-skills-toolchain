#!/usr/bin/env python3
"""Probe 2: independent tokenizer recount of headline counts.

Does not call detector.evaluate_pack. Re-extracts M-N / MECH-N with a
different regex family and re-derives fire/silent from those counts.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import LOG_NAME, ARCH_NAME, OPTION_NAME, ensure_fixtures  # noqa: E402

ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0188-stale-premise-detection-in-briefing-packs.json"
)
SENTINEL = "SUCCESS:RES-0188"

# Independent of census.py lookbehind: leading-class alternation + IGNORECASE MECH.
BARE_M = re.compile(r"(?:^|[^A-Z])M-(\d+)\b", re.MULTILINE)
MECH = re.compile(r"MECH-(\d+)", re.IGNORECASE)
OPEN = re.compile(r"is live|queued as p2-09", re.IGNORECASE)
CLOSED = re.compile(r"was re-prefixed|p2-09 is closed|collision count is 0", re.IGNORECASE)
COLLISION = re.compile(r"31-way|option-id collision", re.IGNORECASE)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0188-probe2 {msg}")
    return 1


def ids(pattern: re.Pattern, text: str) -> set[int]:
    return {int(m.group(1)) for m in pattern.finditer(text or "")}


def recount_tree(root: Path) -> dict:
    log = (root / "briefing" / LOG_NAME).read_text(encoding="utf-8")
    option = (root / "artifacts" / OPTION_NAME).read_text(encoding="utf-8")
    arch = (root / "artifacts" / ARCH_NAME).read_text(encoding="utf-8")
    opt_ids = ids(BARE_M, option)
    arch_bare = ids(BARE_M, arch)
    arch_mech = ids(MECH, arch)
    shared = opt_ids & arch_bare
    reprefix = len(arch_mech) > 0 and len(arch_bare) == 0
    open_assert = bool(OPEN.search(log) and COLLISION.search(log) and not CLOSED.search(log))
    stale_fire = open_assert and reprefix and len(shared) == 0
    current_fire = not reprefix
    return {
        "option_bare": len(opt_ids),
        "arch_bare": len(arch_bare),
        "arch_mech": len(arch_mech),
        "collision": len(shared),
        "reprefix": reprefix,
        "open_assert": open_assert,
        "stale_fire": stale_fire,
        "current_fire": current_fire,
        "log_mech_tokens": len(re.findall(r"MECH", log)),
    }


def main() -> int:
    paths = ensure_fixtures()
    known = recount_tree(paths["known-case"])
    inverted = recount_tree(paths["inverted"])
    reconciled = recount_tree(paths["reconciled"])
    print(json.dumps({"known": known, "inverted": inverted, "reconciled": reconciled}, sort_keys=True))

    if known["option_bare"] != 33:
        return fail(f"option_bare={known['option_bare']} want 33")
    if known["arch_mech"] != 38:
        return fail(f"arch_mech={known['arch_mech']} want 38")
    if known["arch_bare"] != 0 or known["collision"] != 0:
        return fail("known-case still shows a live collision")
    if known["log_mech_tokens"] != 0:
        return fail("known-case log contains MECH tokens")
    if not known["stale_fire"]:
        return fail("independent recount did not fire on stale-open")
    if known["current_fire"]:
        return fail("independent recount fired on current reprefix")
    if inverted["collision"] != 31:
        return fail(f"inverted collision={inverted['collision']} want 31")
    if inverted["stale_fire"] or not inverted["current_fire"]:
        return fail("inverted recount did not invert")
    if reconciled["stale_fire"] or reconciled["current_fire"]:
        return fail("reconciled recount fired")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    headline = doc.get("headline_counts") or {}
    if int(headline.get("known_case_collision", -1)) != known["collision"]:
        return fail("artifact headline collision disagrees with recount")
    if int(headline.get("inverted_collision", -1)) != inverted["collision"]:
        return fail("artifact inverted collision disagrees with recount")
    if headline.get("stale_fired") is not True:
        return fail("artifact headline stale_fired is not true")
    if headline.get("current_silent") is not True:
        return fail("artifact headline current_silent is not true")
    if doc.get("codex_reproduction", {}).get("attempted") is True:
        return fail("artifact claims a Codex run this worker did not perform")
    print(
        "headline collision_known={0} collision_inverted={1} stale_fire={2} current_fire={3}".format(
            known["collision"], inverted["collision"], known["stale_fire"], known["current_fire"]
        )
    )
    print("SUCCESS:RES-0188-probe2 independent-recount both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
