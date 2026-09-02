#!/usr/bin/env python3
"""Probe 1: incidence-matrix orphans, both-states, terminal gate.

Evidence A: implementing-candidate set ⊆ terminal-disposition set.
Empty implementer sets are excluded. A kept/shared mechanism must not
be reported as an orphan. Mutating ADOPT→RETIRE must create an orphan;
mutating RETIRE→ADOPT must clear one.

No terminal disposition may execute while an unsalvaged orphan depends
on it. This unit never executes terminals.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import salvage as S  # noqa: E402

ART = REPO / S.PRIMARY_OUT
REQUIRED_ORPHANS = (
    "orphan.hook-pre-tool",
    "orphan.reject-quorum",
    "false.orphan.extraction-miss",
    "orphan.not-worth.stub",
)
FORBIDDEN_ORPHANS = (
    "kept.stage-gate",
    "shared.handoff-token",
    "canary.known-present",
    "ghost.never-implemented",
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0064-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0064" not in text:
        return fail("sentinel-absent")

    estate = S.load_estate()
    live = S.analyze(estate)
    both = S.both_states(estate)

    art_orphans = list(doc.get("matrix_orphan_ids") or [])
    if art_orphans != live["matrix_orphan_ids"]:
        return fail(f"artifact-orphan-drift {art_orphans} != {live['matrix_orphan_ids']}")

    for mid in REQUIRED_ORPHANS:
        if mid not in live["matrix_orphan_ids"]:
            return fail(f"missing-matrix-orphan {mid}")
        print(f"matrix_orphan {mid} implementers={live['matrix_orphans'][mid]}")
    for mid in FORBIDDEN_ORPHANS:
        if mid in live["matrix_orphan_ids"]:
            return fail(f"false-matrix-orphan {mid}")
        print(f"not_orphan {mid}")

    if "ghost.never-implemented" not in live["empty_implementer_excluded"]:
        return fail("empty-implementer-not-excluded")

    impl_hook = set(live["matrix_orphans"]["orphan.hook-pre-tool"])
    term = set(live["terminal_candidates"])
    if not impl_hook or not impl_hook <= term:
        return fail(f"hook-implementers-not-subset-terminal {impl_hook} term={term}")

    print(
        json.dumps(
            {
                "probe": "probe1-incidence-orphans",
                "unit_id": "WFA-0064",
                "matrix_orphan_ids": live["matrix_orphan_ids"],
                "both_states": both,
                "gate_before": live["gate"]["before_salvage"],
                "gate_after": live["gate"]["after_salvage_retire_host"],
            },
            sort_keys=True,
        )
    )

    if not both.get("pass"):
        return fail(f"both-states-failed {both}")
    if not both["known_good_kept_not_orphan"]:
        return fail("known-good-kept-was-orphan")
    if not both["planted_retire_makes_kept_orphan"]:
        return fail("planted-retire-did-not-create-orphan")
    if not both["planted_adopt_clears_hook_orphan"]:
        return fail("planted-adopt-did-not-clear-hook-orphan")

    before = live["gate"]["before_salvage"]
    after = live["gate"]["after_salvage_retire_host"]
    if before.get("executed") or after.get("executed") or live["gate"].get("any_executed"):
        return fail("terminal-disposition-executed")
    if before.get("reason") != "unsalvaged-orphan":
        return fail(f"unsalvaged-gate-silent reason={before.get('reason')}")
    if "orphan.hook-pre-tool" not in (before.get("unsalvaged") or []):
        return fail("unsalvaged-gate-missed-hook")
    if after.get("reason") not in {"owner-signoff-required", "this-unit-does-not-execute-terminal-dispositions"}:
        return fail(f"after-salvage-gate-wrong reason={after.get('reason')}")
    adopt = live["gate"]["adopt_candidate"]
    if adopt.get("reason") != "not-a-terminal-disposition":
        return fail(f"adopt-gate-wrong {adopt}")

    art_both = doc.get("both_states") or {}
    if art_both.get("pass") is not True:
        return fail("artifact-both-states-not-pass")

    print("SUCCESS:WFA-0064-probe1 incidence orphans both-states terminal-gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
