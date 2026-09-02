#!/usr/bin/env python3
"""Probe 1: mechanical file:line resolution for every CLAIM-REGISTRY anchor.

Independent of probe 2. Does not classify SUPPORTS vs MENTIONS-ONLY.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.artifact_path()
SENTINEL = E.catalog_sentinel()
RAW = HERE / "probe1-mechanical-resolution.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0037-probe1 {msg}")
    return 1


def main() -> int:
    live = E.probe1_payload()
    RAW.write_text(json.dumps(live, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(live, sort_keys=True))
    if not live.get("pass"):
        return fail("mechanical controls or library agreement did not pass")
    if live.get("library_errors"):
        return fail(f"claims.resolve_anchor import/run errors: {live['library_errors']}")
    tally = live["live_tally"]
    if int(tally.get("n_claims") or 0) < 1:
        return fail("CLAIM-REGISTRY.json has zero claims")
    if int(tally.get("n_library_disagreements") or 0) != 0:
        return fail("local mechanical resolver disagrees with claims.resolve_anchor")
    ctrl = {c["control"]: c for c in live.get("controls") or []}
    for name in ("mentions-only", "missing-file", "line-past-eof"):
        if name not in ctrl:
            return fail(f"missing control {name}")
        if not ctrl[name].get("passed"):
            return fail(f"control {name} failed")
    if not ctrl["mentions-only"].get("got_mechanical"):
        return fail("subject-only fixture was not mechanically resolved")
    if ctrl["missing-file"].get("got_mechanical"):
        return fail("missing-file control resolved")
    if ctrl["line-past-eof"].get("got_mechanical"):
        return fail("line-past-eof control resolved")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != "AUD-0037":
        return fail(f"unit_id {doc.get('unit_id')}")
    recorded = ((doc.get("report") or {}).get("live_tally") or {})
    rec_n = recorded.get("n_claims")
    if rec_n is None or int(rec_n) != int(tally["n_claims"]):
        return fail(
            f"artifact n_claims {recorded.get('n_claims')} != live {tally['n_claims']}"
        )
    rec_mech = recorded.get("n_mechanically_resolved_claims")
    if rec_mech is None or int(rec_mech) != int(tally["n_mechanically_resolved_claims"]):
        return fail("artifact mechanically_resolved_claims mismatch")
    print(
        "SUCCESS:AUD-0037-probe1 mechanical resolution; "
        f"claims={tally['n_claims']} anchors={tally['n_anchors']} "
        f"resolved={tally['n_mechanically_resolved_claims']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
