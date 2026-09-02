#!/usr/bin/env python3
"""Probe 2: signal-table split, two-rail claims, overclaim mutants."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402

ART = REPO / "command-center/research/RES-0038.json"


def fail(why: str) -> int:
    print(f"FAILED:RES-0038-probe2 {why}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = C.check_artifact(doc, text=text)
    print(f"checker_ok={ok} {why}")
    if not ok:
        return fail(why)

    mutant = C.mutant_display_only_recomputed(doc)
    mok, mwhy = C.check_artifact(mutant, text=json.dumps(mutant))
    print(f"mutant_display_only_recomputed ok={mok} {mwhy}")
    if mok:
        return fail("display-only-recompute-mutant-accepted")

    mutant2 = C.mutant_strip_rail(doc)
    m2ok, m2why = C.check_artifact(mutant2, text=json.dumps(mutant2))
    print(f"mutant_strip_rail ok={m2ok} {m2why}")
    if m2ok:
        return fail("single-rail-confirmed-mutant-accepted")

    empty_ok, empty_why = C.check_artifact({}, text="{}")
    print(f"garbage_empty ok={empty_ok} {empty_why}")
    if empty_ok:
        return fail("empty-object-accepted")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        return fail("reviewer-not-independent-scope")

    client = [
        r["id"]
        for r in doc["signal_table"]
        if r.get("class") == "client-verifiable"
    ]
    display = [
        r["id"]
        for r in doc["signal_table"]
        if r.get("class") == "display-only"
    ]
    print(f"signal_table client={len(client)} display={len(display)}")
    if len(client) < 2 or len(display) < 2:
        return fail("class-counts")

    print("SUCCESS:RES-0038-probe2 signal-table split two-rails overclaim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
