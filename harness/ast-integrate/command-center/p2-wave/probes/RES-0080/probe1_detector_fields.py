#!/usr/bin/env python3
"""Probe 1: each portable detector names a live transcript field; fixtures discriminate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detectors as D  # noqa: E402
import fixtures as F  # noqa: E402
from fields import inventory  # noqa: E402

OUT = REPO / "command-center/research/RES-0080.json"
UNIT = "RES-0080"
CATALOG_SENTINEL = (
    "SUCCESS:RES-0080 in the receipt AND a detector list where each entry "
    "names an existing transcript field, plus one not-portable measure"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0080-probe1 {msg}")
    return 1


def main() -> int:
    inv = inventory()
    names = set(inv["names"])
    if len(names) < 20:
        return fail(f"inventory too small {len(names)}")

    catalog = D.portable_catalog(inv)
    if len(catalog) < 3:
        return fail("need three portable detectors")
    field_rows = []
    for spec in catalog:
        if not spec["portable"]:
            return fail(f"{spec['id']} not portable {spec['missing_fields']}")
        for field, exists in spec["field_exists"].items():
            field_rows.append({"detector": spec["id"], "field": field, "exists": exists})
            if not exists:
                return fail(f"{spec['id']} names missing field {field}")

    asch = D.propose("asch_critical_trial_conformity_rate", D.ASCH_FIELDS, inv)
    if asch["portable"]:
        return fail("Asch detector must not be portable")
    if not asch["missing_fields"]:
        return fail("Asch propose() did not report missing fields")

    fixture_rows = []
    for fx in F.all_fixtures():
        result = D.run_all(fx)
        got = sorted(result["fired"])
        want = sorted(fx["expect_fired"])
        ok = got == want and result["pathological"] is bool(fx["expect_pathological"])
        fixture_rows.append(
            {
                "id": fx["id"],
                "got": got,
                "want": want,
                "pathological": result["pathological"],
                "ok": ok,
            }
        )
        if not ok:
            return fail(f"fixture {fx['id']} got={got} want={want}")

    healthy = next(r for r in fixture_rows if r["id"] == "healthy")
    planted = [r for r in fixture_rows if r["id"] != "healthy"]
    if healthy["pathological"]:
        return fail("healthy fixture fired")
    if not all(r["pathological"] for r in planted):
        return fail("a planted pathological fixture stayed silent")
    fired_ids = {f for r in planted for f in r["got"]}
    if fired_ids != {
        "premature_closure_instant_unanimity",
        "dissent_suppression_seat_drop",
        "dissent_suppression_vote_collapse",
    }:
        return fail(f"attribution collapsed fired={sorted(fired_ids)}")

    if not OUT.is_file() or OUT.stat().st_size < 200:
        return fail("research artifact missing")
    raw = OUT.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in raw:
        return fail("catalog sentinel absent")
    doc = json.loads(raw)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id mismatch")
    dets = doc.get("detectors") or []
    if len(dets) < 3:
        return fail("artifact detector list short")
    for d in dets:
        field = d.get("transcript_field") or d.get("transcript_fields")
        if not field:
            return fail(f"{d.get('id')} names no transcript field")
        listed = field if isinstance(field, list) else [field]
        for name in listed:
            if name not in names:
                return fail(f"artifact detector names absent field {name}")
            if d.get("field_exists") is False:
                return fail(f"{d.get('id')} field_exists is false")

    report = {
        "probe": "probe1-detector-fields",
        "unit_id": UNIT,
        "inventory_count": inv["count"],
        "detector_fields": field_rows,
        "asch_portable": asch["portable"],
        "asch_missing": asch["missing_fields"],
        "fixtures": fixture_rows,
        "healthy_silent": not healthy["pathological"],
        "planted_all_fire": all(r["pathological"] for r in planted),
        "pass": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"inventory={inv['count']} detectors={len(catalog)} "
        f"healthy_silent=True planted_fire={len(planted)}"
    )
    print("SUCCESS:RES-0080-probe1 each detector names an existing transcript field")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
