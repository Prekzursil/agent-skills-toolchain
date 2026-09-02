#!/usr/bin/env python3
"""Probe 1: design table, git-file-index layouts, capture integrity, two-rail CONFIRMED claims."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/research/RES-0058.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0058-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if "SUCCESS:RES-0058" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if doc.get("unit_id") != "RES-0058":
        return fail(f"unit_id {doc.get('unit_id')}")

    live_table = E.design_table()
    art_table = doc.get("design_table") or []
    if len(art_table) < 4:
        return fail("design_table too small")
    live_map = {r["id"]: r for r in live_table}
    art_map = {r["id"]: r for r in art_table}
    if set(live_map) != set(art_map):
        return fail(f"design_table id mismatch live={sorted(live_map)} art={sorted(art_map)}")
    negatives = 0
    for rid, row in art_map.items():
        v = row.get("survives_git_file_index")
        if v not in {"SURVIVES", "DOES-NOT-SURVIVE"}:
            return fail(f"{rid} missing survives_git_file_index")
        if v != live_map[rid]["survives_git_file_index"]:
            return fail(f"{rid} verdict drift artifact={v} live={live_map[rid]['survives_git_file_index']}")
        if v == "DOES-NOT-SURVIVE":
            negatives += 1
            if not row.get("failing_property"):
                return fail(f"{rid} negative without failing_property")
    if negatives < 1:
        return fail("no negative survives_git_file_index row")

    layouts = {
        "git-file-ok": "SURVIVES",
        "cargo-sharded": "DOES-NOT-SURVIVE",
        "apt-style": "DOES-NOT-SURVIVE",
        "npm-couch": "DOES-NOT-SURVIVE",
    }
    for kind, expected in layouts.items():
        got = E.evaluate_layout(kind)
        if got["survives_git_file_index"] != expected:
            return fail(f"layout {kind} {got['survives_git_file_index']} != {expected}")

    index = E.load_captures()
    checked = 0
    for rec in index.get("captures") or []:
        if rec.get("error") or rec.get("http_status") != 200:
            continue
        E.verify_capture(rec)
        checked += 1
    if checked < 10:
        return fail(f"too few live captures verified: {checked}")

    confirmed = 0
    for claim in doc.get("claims") or []:
        if claim.get("verdict") != "CONFIRMED":
            continue
        confirmed += 1
        if claim.get("evidence_tier") not in {"E1", "E2"}:
            return fail(f"{claim.get('claim_id')} CONFIRMED but {claim.get('evidence_tier')}")
        rails = {r.get("rail") for r in claim.get("source_lineage") or []}
        if "structured-api" not in rails or "prose" not in rails:
            return fail(f"{claim.get('claim_id')} missing two rails")
        for rail in claim.get("source_lineage") or []:
            E.verify_capture(
                {
                    "id": rail.get("rail_id"),
                    "capture_path": rail.get("capture_path"),
                    "sha256": rail.get("sha256"),
                    "http_status": rail.get("http_status"),
                    "error": None,
                    "permalink": rail.get("permalink"),
                    "fetch_timestamp": rail.get("fetch_timestamp"),
                    "content_type": None,
                }
            )
    if confirmed < 3:
        return fail(f"too few CONFIRMED claims: {confirmed}")

    print(
        json.dumps(
            {
                "probe": "probe1-design-table",
                "unit_id": "RES-0058",
                "rows": len(art_table),
                "negatives": negatives,
                "captures_verified": checked,
                "confirmed_claims": confirmed,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"rows={len(art_table)} negatives={negatives} "
        f"captures={checked} confirmed={confirmed}"
    )
    print("SUCCESS:RES-0058-probe1 design table and git-file-index layouts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
