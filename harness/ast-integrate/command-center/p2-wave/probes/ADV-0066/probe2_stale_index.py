#!/usr/bin/env python3
"""Probe 2: stale fixture mirror that never mentions v2.

Mechanically different from probe 1 (no rollback/pin matrix). Serves an
expired index listing only v1 and records whether the client detects
expiry/omission or silently resolves to v1. Completeness ≠ freshness:
an unexpired index that still omits v2 also resolves to v1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    NOW,
    incomplete_unexpired_index,
    materialize,
    stale_index,
)
from resolver import V1, V2, StaleIndex, resolve  # noqa: E402

UNIT = "ADV-0066"
ART = REPO / "command-center/adversarial/ADV-0066-version-downgrade-attack.json"
SCHEMA = REPO / "command-center/schema/supply-chain-attestation.schema.json"
GARBAGE = (
    {},
    {"blob": "x" * 2000},
    {"report_kind": "supply-chain-attestation"},
)


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def measure() -> dict:
    materialize()
    stale = stale_index()
    incomplete = incomplete_unexpired_index()
    stale_versions = [p["version"] for p in stale["packages"]]
    mentions_v2 = V2 in stale_versions
    silent = resolve(
        stale, "latest", check_freshness=False, now=NOW
    )
    detected = False
    stale_error = None
    try:
        resolve(stale, "latest", check_freshness=True, now=NOW)
    except StaleIndex as exc:
        detected = True
        stale_error = str(exc)
    incomplete_sel = resolve(
        incomplete, "latest", check_freshness=True, now=NOW
    )
    ok = (
        not mentions_v2
        and silent["version"] == V1
        and silent["consulted_index"] is True
        and detected
        and incomplete_sel["version"] == V1
        and incomplete_sel["consulted_index"] is True
    )
    return {
        "probe": "probe2-stale-index",
        "unit_id": UNIT,
        "pass": bool(ok),
        "stale_label": stale["label"],
        "stale_generated_at": stale["generated_at"],
        "stale_expires_at": stale["expires_at"],
        "stale_index_versions": stale_versions,
        "stale_mentions_v2": mentions_v2,
        "production_like_version": silent["version"],
        "production_like_consulted_index": silent["consulted_index"],
        "production_like_silent_v1": silent["version"] == V1,
        "freshness_aware_detects_expiry": detected,
        "freshness_error": stale_error,
        "unexpired_incomplete_version": incomplete_sel["version"],
        "unexpired_incomplete_still_selects_v1": incomplete_sel["version"] == V1,
        "now": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "expired-mirror-omits-v2-plus-unexpired-incomplete",
    }


def main() -> int:
    live = measure()
    if not live["pass"]:
        return fail("stale-index matrix failed", live)
    if live["stale_mentions_v2"]:
        return fail("stale fixture mentioned v2; omission not tested", live)
    if not live["production_like_silent_v1"]:
        return fail("production-like client did not silently take v1", live)
    if not live["freshness_aware_detects_expiry"]:
        return fail("freshness-aware client did not detect expiry", live)

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:ADV-0066" not in json.dumps(doc):
        return fail("sentinel absent")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            return fail("schema accepts garbage", probe)
    errors = list(validator.iter_errors(doc))
    if errors:
        return fail("artifact fails schema", errors[0].message)

    recorded = doc.get("probe2") or {}
    for key in (
        "stale_mentions_v2",
        "production_like_version",
        "production_like_silent_v1",
        "freshness_aware_detects_expiry",
        "unexpired_incomplete_version",
        "stale_index_versions",
    ):
        if recorded.get(key) != live.get(key):
            return fail(
                f"artifact probe2 {key} mismatch",
                {"live": live.get(key), "art": recorded.get(key)},
            )

    cmds = [
        p.get("command")
        for p in (doc.get("named_probes") or [])
        if isinstance(p, dict)
    ]
    if not any("probe2_stale_index.py" in str(c) for c in cmds):
        return fail("named probe2 command absent", cmds)

    (HERE / "probe2-stale-index.raw.json").write_text(
        json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(live, sort_keys=True))
    print("SUCCESS:ADV-0066-probe2 stale index omits v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
