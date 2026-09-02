#!/usr/bin/env python3
"""Probe 1: every register row has an original-language quote on disk.

Re-builds the register from captures and checks the emitted artifact
matches. Does not import probe2.
"""
from __future__ import annotations

import json
from pathlib import Path

from quotes import quotes_ok, sentinel_ok
from register import SENTINEL, build

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0116.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0116-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = sentinel_ok(doc, text)
    print(f"sentinel_ok={ok} {why}")
    if not ok:
        return fail(why)
    ok, why = quotes_ok(doc)
    print(f"quotes_ok={ok} {why}")
    if not ok:
        return fail(why)
    live = build()
    art_ids = [r["id"] for r in doc.get("register") or []]
    live_ids = [r["id"] for r in live.get("register") or []]
    print(f"rows={len(art_ids)} live={len(live_ids)}")
    if art_ids != live_ids:
        return fail(f"register-id drift art={art_ids} live={live_ids}")
    for a, b in zip(doc["register"], live["register"]):
        if a.get("original_language_quote") != b.get("original_language_quote"):
            return fail(f"quote drift {a['id']}")
        if a.get("verdict") != b.get("verdict"):
            return fail(f"verdict drift {a['id']}")
        if a.get("evidence_grade") != b.get("evidence_grade"):
            return fail(f"grade drift {a['id']}")
    measured = [
        r["id"]
        for r in doc["register"]
        if r.get("verdict") == "NO-ENGLISH-EQUIVALENT-IN-CORPUS"
        and r.get("implementable_from_source_as_written")
        and r.get("evidence_grade") != "E3"
    ]
    print(f"measured_implementable={measured}")
    if "R-RINGI" not in measured or "R-HEYITING" not in measured:
        return fail("expected ringi and heyiting as measured implementable")
    scan = (doc.get("english_corpus") or {}).get("absence_scan") or {}
    print(f"corpus_absent={scan.get('absent')} hits={scan.get('hits')}")
    if not scan.get("absent"):
        return fail("english corpus already contains target needles")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    print("SUCCESS:RES-0116-probe1 quotes two-rail corpus-absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
