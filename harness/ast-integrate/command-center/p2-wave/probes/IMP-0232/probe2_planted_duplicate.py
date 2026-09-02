#!/usr/bin/env python3
"""Probe 2: planted reworded duplicate is blocked; a distinct entry registers.

Both-states: a lexical (prose) gate accepts the paraphrase — proving the
structural gate is what blocks it, not id uniqueness alone.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "command-center"))

from blueprint_library.fingerprint import fingerprint  # noqa: E402
from blueprint_library.gate import Registry, lexical_registry  # noqa: E402
from blueprint_library.library import LIBRARY, distinct_mutant, paraphrase  # noqa: E402


def main() -> int:
    incumbent = next(e for e in LIBRARY if e["id"] == "deep-research")
    planted = paraphrase(incumbent, "deep-research-reworded")
    genuine = distinct_mutant(incumbent, "deep-research-fork")

    if fingerprint(planted) != fingerprint(incumbent):
        print("FAILED:IMP-0232-probe2 paraphrase fingerprint drifted")
        return 1
    if fingerprint(genuine) == fingerprint(incumbent):
        print("FAILED:IMP-0232-probe2 distinct mutant did not change fingerprint")
        return 1

    real = Registry()
    d0 = real.register(incumbent)
    d_planted = real.register(planted)
    d_genuine = real.register(genuine)
    print(f"real_incumbent_accepted={d0.accepted}")
    print(f"real_planted_accepted={d_planted.accepted} reason={d_planted.reason}")
    print(f"real_genuine_accepted={d_genuine.accepted} reason={d_genuine.reason}")

    broken = lexical_registry()
    b0 = broken.register(incumbent)
    b_planted = broken.register(planted)
    print(f"lexical_incumbent_accepted={b0.accepted}")
    print(f"lexical_planted_accepted={b_planted.accepted} reason={b_planted.reason}")

    if not d0.accepted:
        print("FAILED:IMP-0232-probe2 incumbent rejected")
        return 1
    if d_planted.accepted or d_planted.reason != "fingerprint-collision":
        print("FAILED:IMP-0232-probe2 planted paraphrase was not blocked")
        return 1
    if d_planted.incumbent_id != "deep-research":
        print("FAILED:IMP-0232-probe2 collision not attributed to incumbent")
        return 1
    if not d_genuine.accepted:
        print("FAILED:IMP-0232-probe2 genuinely distinct entry failed to register")
        return 1
    if not b_planted.accepted:
        print("FAILED:IMP-0232-probe2 lexical gate did not accept paraphrase (control silent)")
        return 1
    print("both_states=True structural_blocks=True lexical_accepts_paraphrase=True")
    print("SUCCESS:IMP-0232-probe2 planted duplicate blocked; distinct registers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
