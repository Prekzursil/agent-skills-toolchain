#!/usr/bin/env python3
"""Probe 1: live selector model — each test file mapped to PR CI steps.

The selector model is the claim. A planted file outside every selector must
appear in the orphan list; a known-gated suite must not. A vacuous mapper
that reports no orphans is the bad state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mapper as M  # noqa: E402

ART = REPO / "command-center/audit/AUD-0050-test-gate-coverage-map.json"
SENTINEL = (
    "SUCCESS:AUD-0050 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0050-probe1 {msg}")
    return 1


def main() -> int:
    live = M.compute(include_collection=False)
    ctl = live["control"]
    payload = {
        "probe": "probe1-selector-map",
        "n_test_files": live["n_test_files"],
        "n_gated": live["n_gated"],
        "n_orphan": live["n_orphan"],
        "fixture_in_orphan_list": ctl["fixture_in_orphan_list"],
        "known_gated_classified_gated": ctl["known_gated_classified_gated"],
        "vacuous_hides_fixture": ctl["vacuous_hides_fixture"],
        "orphans": live["orphan_list"],
        "gated": live["gated_list"],
    }
    print(json.dumps(payload, sort_keys=True))

    if not ctl["vacuous_hides_fixture"]:
        return fail("vacuous mapper did not hide the planted fixture")
    if not ctl["fixture_in_orphan_list"]:
        return fail("planted fixture missing from orphan list")
    if not ctl["known_gated_classified_gated"]:
        return fail(f"known-gated {M.KNOWN_GATED_REL} not classified GATED")
    if live["n_orphan"] == 0:
        return fail("orphan list empty — mapper is not discriminating")
    if M.CONTROL_REL in live["gated_list"]:
        return fail("planted fixture classified GATED")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")

    art_orphans = list(doc.get("orphan_list") or [])
    art_map = {
        r["path"]: r["classification"]
        for r in (doc.get("gate_map") or [])
        if isinstance(r, dict) and r.get("path")
    }
    live_map = {r["path"]: r["classification"] for r in live["gate_map"]}
    if art_orphans != live["orphan_list"]:
        return fail("artifact orphan_list drifted from live selector model")
    if art_map != live_map:
        return fail("artifact gate_map drifted from live selector model")
    if M.CONTROL_REL not in art_orphans:
        return fail("artifact omitted planted orphan fixture")
    if art_map.get(M.KNOWN_GATED_REL) != "GATED":
        return fail("artifact did not gate the known-gated suite")

    print(
        f"selector_model files={live['n_test_files']} gated={live['n_gated']} "
        f"orphan={live['n_orphan']} fixture_orphan=True known_gated=True"
    )
    print("SUCCESS:AUD-0050-probe1 live selector map matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
