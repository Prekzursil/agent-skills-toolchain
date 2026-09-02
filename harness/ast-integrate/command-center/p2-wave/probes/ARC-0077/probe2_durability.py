#!/usr/bin/env python3
"""Probe 2: durability + default-safety with both-states controls.

Durability: after the answer, OWNER-DECISIONS.md contains the ruling id and
the decision log references it. Removing the id from OWNER-DECISIONS.md must
make the checker fail; restoring it must pass.

Default-safety: the stated default is the reversible option. Pointing the
default at the irreversible option must make the checker fail.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import packet as P  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0077-probe2 {msg}")
    return 1


def main() -> int:
    doc = P.load_packet(REPO)
    durable, why = P.durability(REPO, doc)
    print(f"durability ok={durable} why={why}")
    if not durable:
        return fail(why)
    safe, swhy = P.default_safety(doc)
    print(f"default_safety ok={safe} why={swhy}")
    if not safe:
        return fail(swhy)

    dur = doc.get("durability") if isinstance(doc.get("durability"), dict) else {}
    ruling_id = str(dur.get("ruling_id") or P.RULING_ID)
    owner_rel = str(dur.get("owner_decisions_path") or P.OWNER_REL)
    owner_path = REPO / owner_rel
    original = owner_path.read_text(encoding="utf-8")
    try:
        owner_path.write_text(
            original.replace(ruling_id, "MISSING-RULING-ID"),
            encoding="utf-8",
        )
        stripped, s_why = P.durability(REPO, doc)
        print(f"durability_stripped ok={stripped} why={s_why}")
        if stripped:
            return fail("durability-did-not-fire-on-stripped-owner-file")
    finally:
        owner_path.write_text(original, encoding="utf-8")
    restored, r_why = P.durability(REPO, doc)
    print(f"durability_restored ok={restored} why={r_why}")
    if not restored:
        return fail("durability-failed-after-restore")

    mutant = P.mutant_irreversible_default(doc)
    m_safe, m_why = P.default_safety(mutant)
    print(f"default_mutant ok={m_safe} why={m_why}")
    if m_safe:
        return fail("default-safety-did-not-fire-on-irreversible-default")

    applied = doc.get("recorded_ruling") if isinstance(doc.get("recorded_ruling"), dict) else {}
    if applied.get("owner_signed") is True:
        return fail("overclaim-owner-signed")
    if applied.get("lock_in_force") is True:
        return fail("overclaim-lock-in-force")
    if str(applied.get("applied") or "") != "DEFAULT-APPLIED":
        return fail("applied-not-default")
    if applied.get("choice") != "OVERRIDE":
        return fail("recorded-choice-not-override-default")

    print("durability=True default_reversible=True both_states=True")
    print("SUCCESS:ARC-0077-probe2 durability default-safety")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
