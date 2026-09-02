#!/usr/bin/env python3
"""Probe 2: record WHICH probe produced each original claim.

An undeclared source is zero signals, not one. This probe is a different
instrument from probe 1 (origin audit vs live re-measure).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

SIDECAR = HERE / "probe2-origin-audit.json"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0075-probe2 {msg}")
    return 1


def main() -> int:
    facts = E.pinned_facts()
    origins = []
    undeclared = 0
    declared = 0
    for fact in facts:
        source = fact.get("source")
        fp = E.fingerprint(source)
        declared_here = fp is not None
        if declared_here:
            declared += 1
            signals = 1
        else:
            undeclared += 1
            signals = 0
        origins.append(
            {
                "id": fact["id"],
                "pinned_claim": fact["pinned_claim"],
                "source_probe": source,
                "source_fingerprint": fp,
                "source_declared": declared_here,
                "source_signals": signals,
                "note": (
                    "source tuple present on the pin"
                    if declared_here
                    else "UNDECLARED_SOURCE: zero source signals"
                ),
            }
        )
    payload = {
        "probe": "probe2-origin-audit",
        "facts": len(facts),
        "declared_source_probes": declared,
        "undeclared_source_probes": undeclared,
        "source_signals": declared,
        "origins": origins,
        "independence_computable": declared > 0,
    }
    SIDECAR.write_text(E.dump(payload), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in (
        "probe",
        "facts",
        "declared_source_probes",
        "undeclared_source_probes",
        "source_signals",
        "independence_computable",
    )}, sort_keys=True))
    print(f"wrote={SIDECAR.relative_to(E.REPO).as_posix()}")

    if len(facts) != 12:
        return fail(f"expected 12 facts, got {len(facts)}")
    if undeclared != 12 or declared != 0 or payload["source_signals"] != 0:
        return fail("pinned block must yield 12 undeclared sources / 0 signals")
    if payload["independence_computable"]:
        return fail("independence must not be computable with zero source signals")

    art = E.REPO / E.OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text, doc = E.load_artifact()
    bad = E.artifact_ok(text, doc)
    if bad:
        return fail(bad)
    origin = doc.get("origin_audit") or {}
    if origin.get("undeclared_source_probes") != 12:
        return fail("artifact origin_audit.undeclared_source_probes != 12")
    if origin.get("source_signals") != 0:
        return fail("artifact origin_audit.source_signals != 0")
    rows = doc.get("facts") or []
    if len(rows) != 12:
        return fail(f"artifact facts={len(rows)}")
    for row in rows:
        if row.get("source_probe") not in (None, {}, []):
            return fail(f"{row.get('id')} unexpectedly declared a source")
        if row.get("source_signals") != 0:
            return fail(f"{row.get('id')} source_signals != 0")
        if row.get("independently_certified"):
            return fail(f"{row.get('id')} independently_certified with undeclared source")
    print("SUCCESS:AUD-0075-probe2 origin audit; 12 undeclared sources = 0 signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
