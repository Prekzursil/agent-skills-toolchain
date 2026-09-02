#!/usr/bin/env python3
"""Named probe 1: defense table, both classes, dual rails, live capture hashes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    AUTOMATABLE,
    CATALOG_SENTINEL,
    CLASS_KEY,
    MODERATION,
    NAMED_DEFENSES,
    OUTPUT_REL,
    UNIT_ID,
)
from mechanics import self_test  # noqa: E402
from rails_util import live_capture  # noqa: E402

ART = REPO / OUTPUT_REL
REQUIRED_RAIL_KEYS = (
    "kind",
    "permalink",
    "fetch_timestamp",
    "http_status",
    "sha256",
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0054-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 1024:
        return fail("artifact missing or tiny")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    table = doc.get("defense_table") or []
    if not isinstance(table, list) or len(table) < 4:
        return fail("defense_table too small")

    classes = []
    families = set()
    for row in table:
        if not isinstance(row, dict):
            return fail("defense row not object")
        if CLASS_KEY not in row:
            return fail(f"{row.get('id')} missing {CLASS_KEY} column")
        cls = row[CLASS_KEY]
        if cls not in {AUTOMATABLE, MODERATION}:
            return fail(f"{row.get('id')} bad class {cls}")
        classes.append(cls)
        fam = str(row.get("named_family") or row.get("defense") or "").lower()
        families.add(fam)
        rails = row.get("rails") or []
        kinds = set()
        if len(rails) < 2:
            return fail(f"{row.get('id')} single-rail (E3)")
        for r in rails:
            for k in REQUIRED_RAIL_KEYS:
                if k not in r:
                    return fail(f"{row.get('id')} rail missing {k}")
            kinds.add(r.get("kind"))
            status = r.get("http_status")
            if not isinstance(status, int) or status >= 400:
                return fail(f"{row.get('id')} rail http_status {status}")
            cap_name = Path(str(r.get("capture_path") or "")).name
            if not cap_name:
                return fail(f"{row.get('id')} rail missing capture_path")
            live = live_capture(cap_name)
            if not live["sha_match"] or live["sha256"] != r.get("sha256"):
                return fail(f"{row.get('id')} sha mismatch {cap_name}")
            body = (HERE / "captures" / cap_name).read_text(encoding="utf-8", errors="replace")
            for anchor in r.get("anchors") or []:
                if anchor not in body:
                    return fail(f"{row.get('id')} anchor missing in {cap_name}: {anchor!r}")
        if "structured_api_probe" not in kinds or "prose_source" not in kinds:
            return fail(f"{row.get('id')} rails not R1+R2 independent")
        if row.get("evidence_grade") == "E3":
            return fail(f"{row.get('id')} E3 cited as measured")

    if AUTOMATABLE not in classes or MODERATION not in classes:
        return fail("classification not honest: need at least one of each")
    joined_fams = " ".join(sorted(families))
    for named in NAMED_DEFENSES:
        if named not in joined_fams and named not in text.lower():
            return fail(f"named defense absent: {named}")

    mech = self_test()
    if not mech["ultranormalize_ok"]:
        return fail("ultranormalize cases drifted")
    if not mech["prefix_ok"]:
        return fail("prefix cases drifted")
    if not mech["scope_ok"]:
        return fail("scope cases drifted")
    stored = doc.get("mechanical_self_test") or {}
    for key in ("ultranormalize_ok", "prefix_ok", "scope_ok"):
        if stored.get(key) is not True:
            return fail(f"artifact mechanical_self_test.{key} not true")

    payload = {
        "rows": len(table),
        "automatable": classes.count(AUTOMATABLE),
        "moderation_dependent": classes.count(MODERATION),
        "dual_rail_rows": len(table),
        "ultranormalize_ok": True,
        "prefix_ok": True,
        "scope_ok": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"table={len(table)} automatable={payload['automatable']} "
        f"moderation-dependent={payload['moderation_dependent']} dual-rail=all"
    )
    print("SUCCESS:RES-0054-probe1 defense-table both-classes dual-rail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
