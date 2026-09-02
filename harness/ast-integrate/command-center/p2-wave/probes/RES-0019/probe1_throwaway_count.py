#!/usr/bin/env python3
"""Named probe 1: throwaway-profile loaded-skill count vs the 110/222 fork.

Signal: the client's own loaded-skill report (inventory JSON names) inside
an isolated --settings home. Fixture skill must be visible in that listing.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenarios import scenario_no_contamination, scenario_throwaway_count  # noqa: E402

ART = REPO / "command-center/research/RES-0019.json"
SENTINEL = (
    "SUCCESS:RES-0019 in the receipt AND an observed integer skill count "
    "from a throwaway profile with the fixture skill visible in the listing, "
    "and an explicit CONFIRMED or REFUTED against the 110/222 fork"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0019-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("research artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("completion sentinel absent")
    if "SUCCESS:RES-0019" not in text:
        return fail("SUCCESS:RES-0019 absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    verdict = str(doc.get("verdict") or "")
    if "CONFIRMED" not in verdict and "REFUTED" not in verdict:
        return fail("artifact lacks CONFIRMED or REFUTED")

    with tempfile.TemporaryDirectory(prefix="res0019-p1-") as tmp:
        root = Path(tmp)
        count = scenario_throwaway_count(root)
        clean = scenario_no_contamination(root)

    if count["client_plugin_body"] != 110:
        return fail(f"plugin body {count['client_plugin_body']} != 110")
    if count["client_plugin_body"] == 222:
        return fail("loaded count matched 222 fork")
    if not count["fixture_visible"]:
        return fail("fixture not visible")
    if count["filesystem_skill_md_count"] == count["client_loaded_count"]:
        return fail("client report collapsed onto filesystem count")
    if clean["fresh_hits"]:
        return fail(f"contamination {clean['fresh_hits']}")

    payload = {
        "probe": "probe1-throwaway-loaded-count",
        "unit_id": "RES-0019",
        "pass": True,
        "throwaway_count": count,
        "no_contamination": clean,
        "receipt_state": doc.get("state"),
        "verdict": doc.get("verdict"),
        "observed_integer": count["client_plugin_body"],
        "fixture_visible": count["fixture_visible"],
        "fork_verdict": count["fork"]["fork_verdict"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "client_body="
        f"{count['client_plugin_body']} filesystem="
        f"{count['filesystem_plugin_body']} fixture="
        f"{count['fixture_name']} visible={count['fixture_visible']} "
        f"fork={count['fork']['fork_verdict']}"
    )
    print("SUCCESS:RES-0019-probe1 throwaway loaded-skill count vs 110/222")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
