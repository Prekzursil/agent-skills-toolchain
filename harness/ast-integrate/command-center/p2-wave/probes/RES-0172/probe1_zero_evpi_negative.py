#!/usr/bin/env python3
"""Probe 1: negative control — at least one candidate is zero-EVPI.

A checkpoint set where every candidate survives has not applied the test.
Recomputes EVPI live from engine.py; does not trust the artifact's adjectives.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / E.OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0172-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if E.SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")

    live = E.score_all()
    live_by = {r["id"]: r for r in live}
    art_rows = doc.get("candidates") or []
    if len(art_rows) != len(live):
        return fail(f"candidate count artifact={len(art_rows)} live={len(live)}")
    for row in art_rows:
        cid = row.get("id")
        if cid not in live_by:
            return fail(f"unknown candidate {cid}")
        if row.get("disposition") != live_by[cid]["disposition"]:
            return fail(
                f"{cid} disposition artifact={row.get('disposition')} "
                f"live={live_by[cid]['disposition']}"
            )
        if bool(row.get("retain")) != live_by[cid]["retain"]:
            return fail(f"{cid} retain drifted")

    zeros = E.eliminated_zero_evpi(live)
    print(
        f"candidates={len(live)} retained={len(E.retained(live))} "
        f"zero_evpi={len(zeros)}"
    )
    print(f"zero_ids={[z['id'] for z in zeros]}")
    if not E.negative_control_ok(live):
        return fail("negative control: every candidate survived")
    if E.all_survive_mutant(live):
        return fail("mutant all-survive unexpectedly true")

    mutant = [dict(r) for r in live]
    for row in mutant:
        row["retain"] = True
        row["disposition"] = "RETAIN"
    if E.negative_control_ok(mutant):
        return fail("mutant all-retain still passes negative control")
    print("both-states: live eliminates >=1 zero-EVPI; all-retain mutant fails")

    required_zeros = {"CP-ACK-STATUS", "CP-SCHEMA-LOOKS-OK", "CP-CONTINUE-PROCEED"}
    got_zeros = {z["id"] for z in zeros}
    missing = required_zeros - got_zeros
    if missing:
        return fail(f"planted zero-EVPI missing {sorted(missing)}")
    for zid in required_zeros:
        if live_by[zid]["plans_diverge"]:
            return fail(f"{zid} plans unexpectedly diverge")
        if not live_by[zid]["permission_theatre"]:
            return fail(f"{zid} not marked permission theatre")

    nc = doc.get("negative_control") or {}
    if not nc.get("eliminated_at_least_one"):
        return fail("artifact negative_control.eliminated_at_least_one")
    if int(nc.get("eliminated_count") or 0) != len(zeros):
        return fail("artifact eliminated_count drifted")

    print("SUCCESS:RES-0172-probe1 zero-EVPI negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
