#!/usr/bin/env python3
"""Probe 1: every reachable row has a LICENSE sha256 matching stored bytes."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graph as G  # noqa: E402
from schema_check import check_document, check_schema_file  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{G.UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    art = G.REPO / G.OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if G.CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != G.UNIT:
        return fail("unit_id mismatch")
    if doc.get("not_legal_advice") is not True:
        return fail("not_legal_advice missing")

    schema_errs = check_schema_file() + check_document(doc)
    if schema_errs:
        return fail(f"schema {schema_errs[0]}")
    if not check_document({}):
        return fail("schema checker accepted empty document")

    rows = (doc.get("graph") or {}).get("rows") or []
    e_ids = [str(r.get("id")) for r in rows if re.fullmatch(r"E\d{3}", str(r.get("id") or ""))]
    expected = [f"E{i:03d}" for i in range(1, G.REGISTER_EXPECTED + 1)]
    if e_ids != expected:
        return fail("E001-E189 span missing or reordered")

    live_rows, _register = G.build_rows()
    live_ok, live_problems = G.graph_ok(live_rows)
    if not live_ok:
        return fail(f"live graph_ok {live_problems}")

    art_ok, art_problems = G.graph_ok(rows)
    if not art_ok:
        return fail(f"artifact graph_ok {art_problems}")

    reach = G.reachable_rows(rows)
    if not reach:
        return fail("no reachable rows")
    missing = G.missing_sha256(rows)
    if missing:
        return fail(f"reachable missing sha256 {missing}")

    sha_matches = []
    for r in reach:
        stored = G.stored_license_sha(r)
        if stored is None:
            return fail(f"no stored LICENSE for {r.get('id')}")
        if stored != r.get("license_sha256"):
            return fail(f"sha256 drift {r.get('id')}")
        sha_matches.append(r.get("id"))

    counts = doc.get("counts") or {}
    recomputed = G.recompute_counts(rows)
    if counts.get("license_sha256_on_reachable") != recomputed["license_sha256_on_reachable"]:
        return fail("counts.license_sha256_on_reachable drifted")
    if counts.get("reachable") != len(reach):
        return fail("counts.reachable drifted")

    out = {
        "probe": "probe1-reachable-sha256",
        "unit_id": G.UNIT,
        "register_e_rows": len(e_ids),
        "reachable": len(reach),
        "sha_matches": sha_matches,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"e_rows={len(e_ids)} reachable={len(reach)} "
        f"sha_matches={len(sha_matches)}"
    )
    print(f"SUCCESS:{G.UNIT}-probe1 reachable LICENSE sha256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
