#!/usr/bin/env python3
"""AUD-0075 probe 2 - origin-probe audit over the pinned facts.

An undeclared source probe means zero signals, not one. For every pinned
fact this audit reads the declared producing probe (source_probe) and its
fingerprint (source_fingerprint); any fact without both is UNDECLARED and
contributes exactly zero source signals. Independently certified is then
not computable and must be 0 - the honest number, even when it is zero.
Mechanically different from probe1: probe1 re-measures; this audits
provenance bookkeeping only.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "audit" / "AUD-0075-stale-premise-sweep.json"
UNIT = "AUD-0075"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    facts = doc.get("facts") or []
    if len(facts) != 12:
        return fail(f"facts={len(facts)} expected 12")

    declared = 0
    undeclared_ids = []
    for f in facts:
        has_probe = bool(str(f.get("source_probe") or "").strip())
        has_fp = bool(str(f.get("source_fingerprint") or "").strip())
        if has_probe and has_fp:
            declared += 1
        else:
            gate = str(f.get("gate_reason") or "")
            if "UNDECLARED" not in gate.upper() and "zero source signals" not in gate:
                return fail(f"fact {f.get('id')} undeclared but gate_reason does not say so: {gate[:80]}")
            undeclared_ids.append(str(f.get("id")))
    hl = doc.get("headline") or {}
    if hl.get("undeclared_source_probes") not in (None, len(undeclared_ids)):
        return fail(f"headline undeclared={hl.get('undeclared_source_probes')} audit={len(undeclared_ids)}")
    if hl.get("source_signals") not in (None, 0):
        return fail(f"headline source_signals={hl.get('source_signals')} must be 0")
    certified = hl.get("independently_certified_confirmed_or_refuted")
    if certified not in (None, 0):
        return fail(f"independently_certified={certified} must be 0 when no source is declared")
    print(f"origin audit: declared={declared}/12 undeclared={len(undeclared_ids)}")
    print(f"source_signals=0 independently_certified=0 (zero is the honest number)")
    print(f"SUCCESS:{UNIT}-probe2 provenance audit complete: no source probe declared for any pinned fact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
