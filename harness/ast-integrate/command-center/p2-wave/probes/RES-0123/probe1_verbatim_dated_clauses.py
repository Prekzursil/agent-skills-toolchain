#!/usr/bin/env python3
"""Probe 1: every rail has a verbatim dated clause present in its capture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import OUT, SENTINEL, collapse_ws  # noqa: E402
from model import QUOTES, quote_in_text  # noqa: E402

REQUIRED_RAILS = {"cursor", "anthropic", "openai", "google", "xai", "groq"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0123-probe1 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size < 200:
        return fail("artifact missing")
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0123":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("no_legal_conclusion") is not True:
        return fail("artifact rendered a legal conclusion or omitted the disclaimer")
    claims = doc.get("claims") or []
    rails = {c.get("rail") for c in claims if isinstance(c, dict)}
    if not REQUIRED_RAILS <= rails:
        return fail(f"rails {sorted(rails)}")
    by_id = {c["id"]: c for c in claims if isinstance(c, dict) and "id" in c}
    for spec in QUOTES:
        row = by_id.get(spec["id"])
        if not row:
            return fail(f"claim missing {spec['id']}")
        quote = row.get("verbatim_quote") or ""
        if collapse_ws(spec["quote"]) not in collapse_ws(quote) and collapse_ws(quote) != collapse_ws(spec["quote"]):
            # allow live window that still contains the catalogued clause
            if collapse_ws(spec["quote"]) not in collapse_ws(quote):
                return fail(f"quote drifted {spec['id']}")
        if not row.get("effective_date"):
            return fail(f"undated {spec['id']}")
        lineage = row.get("source_lineage") or []
        if not lineage or not lineage[0].get("sha256") or not lineage[0].get("fetched_at"):
            return fail(f"unpinned {spec['id']}")
        cap_id = spec["capture_id"]
        cap_path = HERE / "captures" / f"{cap_id}.txt"
        if not cap_path.is_file():
            return fail(f"capture missing {cap_id}")
        captured = cap_path.read_text(encoding="utf-8")
        if not quote_in_text(spec["quote"], captured) and not quote_in_text(quote, captured):
            return fail(f"verbatim quote not in capture {spec['id']}")
        if not row.get("found_in_capture"):
            return fail(f"found_in_capture false {spec['id']}")
    print(
        f"rails={sorted(REQUIRED_RAILS)} quotes={len(QUOTES)} "
        f"all_dated=True all_in_capture=True"
    )
    print("SUCCESS:RES-0123-probe1 verbatim-dated-clause-per-rail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
