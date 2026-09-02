#!/usr/bin/env python3
"""Probe 1: schema-check every trail record; restore rehearsal of three collapses.

Evidence A: every collapse in the trail has required fields, checked by schema.
Evidence B: restore reconstructs pre-collapse records from the trail record
alone and diffs them against a snapshot taken before the collapse.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    load_report_schema,
    load_trail_schema,
    run_rehearsal,
    schema_rejects_garbage,
    validate_instance,
)

UNIT = "WFA-0099"
OUT_REL = "command-center/wfa/WFA-0099-collapse-audit-trail.json"
SENTINEL = "SUCCESS:WFA-0099"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / CATALOG).is_file():
            return p
    raise SystemExit("FAILED:WFA-0099-probe1 repo root not found")


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    repo = repo_root()
    art = repo / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    report_schema = load_report_schema()
    trail_schema = load_trail_schema()
    if not schema_rejects_garbage(report_schema):
        return fail("report schema accepted garbage")
    if not schema_rejects_garbage(trail_schema):
        return fail("trail schema accepted garbage")
    errs = validate_instance(report_schema, doc)
    if errs:
        print("\n".join(errs[:12]))
        return fail("artifact failed AuditReport schema")

    records = list(doc.get("trail_records") or [])
    if len(records) < 3:
        return fail(f"trail_records {len(records)} < 3")
    for i, rec in enumerate(records, 1):
        terr = validate_instance(trail_schema, rec)
        if terr:
            print("\n".join(terr[:12]))
            return fail(f"trail record {i} failed schema")
        for fld in (
            "surviving_id",
            "absorbed_ids",
            "deciding_signals",
            "preserved_union",
            "pre_records",
        ):
            if not rec.get(fld):
                return fail(f"trail record {i} missing {fld}")

    with tempfile.TemporaryDirectory(prefix="wfa0099-p1-") as tmp:
        live = run_rehearsal(Path(tmp) / "trail.jsonl")
    print(
        "live n={n} signals={s} all_restored={a} distinct={d}".format(
            n=live["n_collapses"],
            s=live["primary_signals"],
            a=live["all_restored"],
            d=live["three_distinct_signals"],
        )
    )
    if live["n_collapses"] < 3:
        return fail("live rehearsal ran fewer than 3 collapses")
    if not live["three_distinct_signals"]:
        return fail(f"signals not three distinct: {live['primary_signals']}")
    if not live["all_restored"]:
        return fail("live restore diffs non-empty")
    if not live["chain"].get("ok"):
        return fail(f"live chain {live['chain']}")

    art_signals = [r.get("primary_signal") for r in (doc.get("restore_rehearsals") or [])]
    if set(art_signals) != {"LEXICAL", "EMBEDDING", "STRUCTURAL"}:
        return fail(f"artifact restore signals {art_signals}")
    for row in doc.get("restore_rehearsals") or []:
        if row.get("equal") is not True:
            return fail(f"artifact restore not equal {row.get('primary_signal')}")
        if set(row.get("pre_sha256") or {}) != set(row.get("restored_sha256") or {}):
            return fail("artifact pre/restored sha key mismatch")
        if row.get("pre_sha256") != row.get("restored_sha256"):
            return fail("artifact pre_sha256 != restored_sha256")

    live_ids = {(h["surviving_id"], tuple(h["absorbed_ids"])) for h in live["rehearsals"]}
    art_ids = {
        (h["surviving_id"], tuple(h["absorbed_ids"]))
        for h in doc.get("restore_rehearsals") or []
    }
    if live_ids != art_ids:
        return fail(f"artifact collapse ids {art_ids} != live {live_ids}")

    for rec in records:
        union_m = set((rec.get("preserved_union") or {}).get("mechanisms") or [])
        pre = rec.get("pre_records") or {}
        for rec_id, body in pre.items():
            for mech in body.get("mechanisms") or []:
                if mech not in union_m:
                    return fail(f"union dropped mechanism {mech} from {rec_id}")

    print(
        f"schema_ok trail_n={len(records)} restore_n={len(doc.get('restore_rehearsals') or [])}"
    )
    print(f"SUCCESS:{UNIT}-probe1 schema-checked trail; restore rehearsal of three signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
