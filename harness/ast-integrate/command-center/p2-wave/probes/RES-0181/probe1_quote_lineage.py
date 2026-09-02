#!/usr/bin/env python3
"""Probe 1: recovered quotes are substrings of sha256-pinned captures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import archaeology as A  # noqa: E402
from corpus import LOAD_BEARING_IDS, OUT_REL, SENTINEL, UNIT_ID  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0181-probe1 {msg}")
    return 1


def main() -> int:
    out = REPO / OUT_REL
    if not out.is_file() or out.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(out.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    live = A.recover_all()
    claims = doc.get("claims") or []
    by_id = {c.get("mechanism_id"): c for c in claims if isinstance(c, dict)}
    missing = [i for i in LOAD_BEARING_IDS if i not in by_id]
    if missing:
        return fail(f"missing load-bearing rows {missing}")
    recovered = 0
    for mid in LOAD_BEARING_IDS:
        row = by_id[mid]
        live_row = live[mid]
        if row.get("recovery_status") != live_row.get("recovery_status"):
            return fail(
                f"{mid} status drifted artifact={row.get('recovery_status')} "
                f"live={live_row.get('recovery_status')}"
            )
        if row.get("recovery_status") != "RATIONALE-RECOVERED":
            continue
        recovered += 1
        quotes = row.get("history_quotes") or []
        if len(quotes) < 1:
            return fail(f"{mid} recovered but no quotes")
        mech = next(m for m in A.MECHANISMS if m["id"] == mid)
        for q in quotes:
            quote = q.get("quote") or ""
            if q.get("tag") == A.TAG_INFERRED:
                return fail(f"{mid} inferred quote presented as recovered")
            if not A.quote_in_captures(quote, mech["history_capture_ids"]):
                return fail(f"{mid} quote not in history captures")
        lineage = row.get("source_lineage") or []
        if len(lineage) < 2:
            return fail(f"{mid} needs two lineage rails, got {len(lineage)}")
        shas = {r.get("sha256") for r in lineage if r.get("sha256")}
        if len(shas) < 2:
            return fail(f"{mid} lineage rails not independently hashed")
        for rail in lineage:
            rel = rail.get("path") or ""
            path = REPO / rel
            if not path.is_file():
                return fail(f"{mid} lineage file missing {rel}")
            sha, n = A.digest_file(path)
            if sha != rail.get("sha256"):
                return fail(f"{mid} lineage sha mismatch {rel}")
            if n != rail.get("bytes"):
                return fail(f"{mid} lineage bytes mismatch {rel}")
        signals = row.get("independent_signals") or []
        if len(signals) < 2:
            return fail(f"{mid} fewer than two independent signals")
        if signals[0].get("sha256") == signals[1].get("sha256"):
            return fail(f"{mid} signals share sha256 (not independent)")
    if recovered < 1:
        return fail("zero recovered load-bearing rationales")
    counts = doc.get("counts") or {}
    if int(counts.get("load_bearing") or 0) != 12:
        return fail("counts.load_bearing != 12")
    print(
        json.dumps(
            {
                "probe": "probe1-quote-lineage",
                "unit_id": UNIT_ID,
                "recovered": recovered,
                "load_bearing": 12,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:RES-0181-probe1 quotes pinned recovered={recovered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
