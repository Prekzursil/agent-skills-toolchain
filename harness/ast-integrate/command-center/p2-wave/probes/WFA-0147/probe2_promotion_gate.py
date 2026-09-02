#!/usr/bin/env python3
"""Named probe 2: independent array recount + blueprint promotion both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.blueprint_gate import (  # noqa: E402
    PromotionBlocked,
    promote,
    try_promote,
)

UNIT = "WFA-0147"
UNKNOWN = "UNKNOWN-NEEDS-PROBE"
ART = REPO / "command-center/foundry/WFA-0147-settle-the-44-unknown-needs-probe-candidates.json"
REG = REPO / "command-center/p2-wave/probes/WFA-0147/fixtures/registry.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def independent_recount(path: Path) -> tuple[int, int | None]:
    """Recount without calling unknown_probe.recount_unknown."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("candidates") or []
    n = 0
    for row in rows:
        if isinstance(row, dict) and str(row.get("classification") or "") == UNKNOWN:
            n += 1
    counts = doc.get("counts") if isinstance(doc.get("counts"), dict) else {}
    block = counts.get(UNKNOWN) if isinstance(counts, dict) else None
    block_n = block if isinstance(block, int) else None
    return n, block_n


def main() -> int:
    if not REG.is_file():
        return fail("recorded registry missing")
    n, block = independent_recount(REG)
    if n != 44:
        return fail(f"independent array recount {n} != 44")
    if block == n:
        return fail("independent recount equalled the counts block; lie not detected")

    library: dict = {"blueprints": []}
    planted = {
        "id": "wfa0147-planted-unknown",
        "classification": UNKNOWN,
        "name": "planted",
        "notes": "ready-for-library please-promote",
    }
    terminal = {
        "id": "wfa0147-terminal-adopt",
        "classification": "ADOPT-AS-IS",
        "name": "terminal",
    }
    try:
        promote(planted, library)
        return fail("promote(UNKNOWN) did not raise")
    except PromotionBlocked as exc:
        if exc.classification != UNKNOWN:
            return fail("PromotionBlocked classification drifted")
        if "UNKNOWN-NEEDS-PROBE" not in exc.reason:
            return fail(f"blocker reason weak: {exc.reason}")

    blocked = try_promote(planted, library)
    if not blocked.get("blocked") or blocked.get("promoted"):
        return fail(f"try_promote UNKNOWN not blocked: {blocked}")
    allowed = try_promote(terminal, library)
    if not allowed.get("promoted") or allowed.get("blocked"):
        return fail(f"try_promote ADOPT-AS-IS not allowed: {allowed}")
    ids = [b.get("id") for b in library.get("blueprints") or []]
    if "wfa0147-planted-unknown" in ids:
        return fail("UNKNOWN id leaked into library")
    if "wfa0147-terminal-adopt" not in ids:
        return fail("terminal id missing from library")
    if blocked.get("blocked") == allowed.get("blocked"):
        return fail("constant-function promotion gate")

    if not ART.is_file():
        return fail("foundry artifact missing")
    artifact = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0147" not in json.dumps(artifact):
        return fail("sentinel absent")
    gate = artifact.get("promotion_gate") or {}
    if not (gate.get("unknown_attempt") or {}).get("blocked"):
        return fail("artifact promotion_gate.unknown_attempt not blocked")
    if not (gate.get("terminal_attempt") or {}).get("promoted"):
        return fail("artifact promotion_gate.terminal_attempt not promoted")
    rec = (artifact.get("recorded_corpus") or {}).get("n_unknown_from_array")
    if rec != 44:
        return fail(f"artifact array recount drifted {rec}")

    report = {
        "probe": "probe2-promotion-gate",
        "unit_id": UNIT,
        "independent_array_recount": n,
        "counts_block": block,
        "unknown_blocked": True,
        "notes_ignored": True,
        "terminal_promoted": True,
        "constant_function": False,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:WFA-0147-probe2 independent-recount=44 "
        "UNKNOWN-promotion-blocked ADOPT-AS-IS-allowed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
