#!/usr/bin/env python3
"""Probe 1: live needle grade of all 56 cells; both-states presence detector."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from grade import (  # noqa: E402
    DEFINITION_PATH,
    evaluate_presence,
    grade,
    sha256_file,
)
import sources as S  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / S.OUT_REL
SENTINEL = S.SENTINEL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0161-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    live_hash = sha256_file(DEFINITION_PATH)
    recorded = doc.get("definition") or {}
    if recorded.get("sha256") != live_hash:
        return fail("artifact definition.sha256 does not match DEFINITION.json")
    if recorded.get("frozen_before_count") is not True:
        return fail("definition not marked frozen_before_count")
    if recorded.get("same_rule_all_vendors") is not True:
        return fail("same_rule_all_vendors is not true")
    if doc.get("definition_locked_hash_before_enumerate") is not True:
        return fail("hash was not locked before enumeration")

    live = grade()
    if live["definition_sha256"] != live_hash:
        return fail("in-memory definition hash drifted from disk")
    if live["index_integrity_errors"]:
        return fail("integrity:" + ",".join(live["index_integrity_errors"][:6]))
    if live["n_ok"] != live["n_cells"] or live["n_cells"] != 56:
        return fail(f"cells ok={live['n_ok']} n={live['n_cells']}")
    if live["mismatches"]:
        return fail("mismatches:" + ";".join(live["mismatches"][:8]))

    art_cells = {
        (c["engine"], c["feature"]): c["presence"]
        for c in doc.get("cells") or []
        if isinstance(c, dict)
    }
    live_cells = {(c["engine"], c["feature"]): c["presence"] for c in live["cells"]}
    if art_cells != live_cells:
        return fail("artifact cell presence drifted from live grade")

    for c in live["cells"]:
        if len(c.get("rails") or []) < 2:
            return fail(f"{c['engine']}/{c['feature']}:need-two-rails")
        for r in c["rails"]:
            for key in ("permalink", "fetch_timestamp", "http_status", "sha256"):
                if r.get(key) in (None, ""):
                    return fail(f"{c['engine']}/{c['feature']}:missing-{key}")

    # Both-states: claiming PRESENT when needles miss must fail;
    # claiming ABSENT when needles hit must fail. Live cells must pass.
    miss_hits = [False, False]
    hit_hits = [True, True]
    if evaluate_presence("PRESENT", miss_hits):
        return fail("present-on-miss-silent")
    if evaluate_presence("ABSENT", hit_hits):
        return fail("absent-on-hit-silent")
    if not evaluate_presence("PRESENT", hit_hits):
        return fail("present-on-hit-failed")
    if not evaluate_presence("ABSENT", miss_hits):
        return fail("absent-on-miss-failed")
    if not evaluate_presence("PARTIAL", hit_hits):
        return fail("partial-on-hit-failed")

    payload = {
        "probe": "probe1-live-cells-and-rails",
        "unit_id": S.UNIT,
        "definition_sha256": live_hash,
        "frozen_before_count": True,
        "same_rule_all_vendors": True,
        "n_cells": live["n_cells"],
        "n_ok": live["n_ok"],
        "both_states": {
            "present_on_miss_fires": True,
            "absent_on_hit_fires": True,
            "live_passes": True,
        },
        "live_matches_artifact": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:RES-0161-probe1 56/56 cells match live needles; "
        "both-states presence detector fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
