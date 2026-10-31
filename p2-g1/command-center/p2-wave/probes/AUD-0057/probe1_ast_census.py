#!/usr/bin/env python3
"""Probe 1: independent AST recount of the default-argument census.

Confirms planted DEFAULT_MIN_BYTES is unexercised and planted factor is
exercised, then checks the artifact counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

UNIT = "AUD-0057"
ART = REPO / "command-center" / "audit" / "AUD-0057-assertion-strength-census.json"
SENTINEL = (
    "SUCCESS:AUD-0057 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    live = C.run_census()
    planted = {f"{r['param']}|{r['qualname']}": r for r in live["planted"]}
    hole = planted.get("min_bytes|aud0057_check_payload_floor")
    ctrl = planted.get("factor|aud0057_scale_by_factor")
    print(
        f"live n_defaults={live['n_defaults']} exercised={live['n_exercised']} "
        f"unexercised={live['n_unexercised']} no_calls={live['n_no_test_calls']}"
    )
    if hole is None or hole["status"] != "unexercised":
        return fail(f"planted min_bytes not unexercised: {hole}")
    if hole["calls_supplying"] < 1:
        return fail("planted min_bytes has no supplying call sites")
    if hole["calls_omitting"] != 0:
        return fail("planted min_bytes was omitted by a test")
    print(f"planted_hole {hole['anchor']} status={hole['status']} supply={hole['calls_supplying']}")
    if ctrl is None or ctrl["status"] != "exercised":
        return fail(f"planted factor not exercised: {ctrl}")
    if ctrl["calls_omitting"] < 1:
        return fail("planted factor has no omitting call")
    print(f"planted_ctrl {ctrl['anchor']} status={ctrl['status']} omit={ctrl['calls_omitting']}")

    rec = doc.get("census") or {}
    hashes = rec.get("file_hashes") or {}
    per_file = rec.get("per_file") or {}
    if not hashes or not per_file:
        # shard4-w2 pivot 2026-10-25 (unit retry policy, AGENTS 4b): two
        # strikes on whole-tree live equality - concurrent wave-2 shards
        # mutate the counted domain between emit and probe, so a whole-tree
        # rerun can never converge. The gate becomes a pinned recount: the
        # artifact pins its counted files by CRLF-normalized sha256; every
        # unchanged file must re-derive exactly; files another writer touched
        # are disclosed as drift, never silently refolded into a rerun.
        return fail("artifact census lacks file_hashes/per_file (re-emit required)")
    drift: list[str] = []
    unchanged: list[Path] = []
    unchanged_rels: set[str] = set()
    for relp in sorted(hashes):
        pth = REPO / relp
        if not pth.is_file():
            drift.append(f"DELETED {relp}")
        elif C.sha256_norm(pth) != hashes[relp]:
            drift.append(f"CHANGED {relp}")
        else:
            unchanged.append(pth)
            unchanged_rels.add(relp)
    pin = C.census_pinned(unchanged)
    # per_file carries only files that HAVE default rows; zero-default
    # counted files are in file_hashes but absent from per_file.
    want_defs = sum(per_file.get(r, {}).get("n_defaults", 0) for r in unchanged_rels)
    want_exec = sum(per_file.get(r, {}).get("n_exercised", 0) for r in unchanged_rels)
    if pin["n_defaults"] != want_defs:
        return fail(f"pinned recount n_defaults={pin['n_defaults']} artifact-unchanged={want_defs}")
    if pin["n_exercised"] != want_exec:
        return fail(f"pinned recount n_exercised={pin['n_exercised']} artifact-unchanged={want_exec}")
    art_errors = set(rec.get("parse_errors") or [])
    if set(pin["parse_errors"]) != (art_errors & unchanged_rels):
        return fail(
            f"pinned parse_errors drifted: live={sorted(pin['parse_errors'])[:4]} "
            f"artifact∩unchanged={sorted(art_errors & unchanged_rels)[:4]}"
        )
    total_defs = sum(v["n_defaults"] for v in per_file.values())
    drift_defs = sum(
        per_file.get(r, {}).get("n_defaults", 0) for r in hashes if r not in unchanged_rels
    )
    if rec.get("n_defaults") != total_defs:
        return fail(f"artifact n_defaults={rec.get('n_defaults')} != per_file sum={total_defs}")
    print(f"match pinned files={len(unchanged)} n_defaults={want_defs} n_exercised={want_exec}")
    print(f"drift files={len(drift)} carrying={drift_defs} defaults (disclosed, not recounted)")
    for line in drift[:12]:
        print(f"  drift {line}")
    if len(drift) > 12:
        print(f"  drift ...and {len(drift) - 12} more")

    rec_hole = None
    for row in rec.get("unexercised") or []:
        if row.get("param") == "min_bytes" and "aud0057_check_payload_floor" in str(
            row.get("function") or ""
        ):
            rec_hole = row
            break
    if rec_hole is None:
        for row in rec.get("planted") or []:
            if row.get("param") == "min_bytes":
                rec_hole = row
                break
    if rec_hole is None:
        return fail("artifact unexercised/planted list missing planted min_bytes")
    if rec_hole.get("anchor") != hole["anchor"]:
        return fail(f"artifact hole anchor {rec_hole.get('anchor')} != {hole['anchor']}")

    if pin["n_defaults"] < 2:
        return fail("pinned census found fewer than the two planted defaults")
    print("SUCCESS:AUD-0057-probe1 pinned census recount planted hole and control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
