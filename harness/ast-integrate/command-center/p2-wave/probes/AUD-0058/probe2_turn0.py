#!/usr/bin/env python3
"""Named probe 2: direct turn-zero injection measurement.

Signal: bodies that landed in the context bag. Mechanically different from
probe 1 (which only parses frontmatter). An empty always-on set is a broken
instrument. Inference that disagrees with the bag loses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import OUT, UNIT  # noqa: E402
from measure import fixture_controls, live_census  # noqa: E402

ART = OUT


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:AUD-0058" not in json.dumps(doc):
        return fail("sentinel absent")

    ctl = fixture_controls()
    if not ctl["pass"]:
        return fail("fixture both-states / demotion / bag control failed", ctl)
    if not ctl["always_on_in_bag"]:
        return fail("known always-on body missing from turn-zero bag")
    if not ctl["instrument_named_always_on"]:
        return fail("empty always-on set; instrument is broken")
    if not ctl["naive_inference_loses_to_measurement"]:
        return fail("naive frontmatter-arms inference was not refuted by the bag")
    if not ctl["demoted_by_paths_star"]:
        return fail("adding paths **/* did not demote always-on")
    if not ctl["lazy_body_absent_at_t0"]:
        return fail("lazy body leaked into turn-zero bag")
    if not ctl["bare_rule_in_bag"]:
        return fail("no-frontmatter rule missing from turn-zero bag")

    live = live_census()
    art_ctl = ((doc.get("measurement") or {}).get("controls") or {})
    if art_ctl.get("always_on_in_bag") is not True:
        return fail("artifact did not record always_on_in_bag")
    if art_ctl.get("empty_always_on_set_rejected") is not True:
        return fail("artifact did not reject empty always-on set")
    if art_ctl.get("naive_inference_loses_to_measurement") is not True:
        return fail("artifact did not record inference-loses-to-measurement")
    if art_ctl.get("demoted_by_paths_star") is not True:
        return fail("artifact did not record demotion")

    art_live = (doc.get("measurement") or {}).get("live") or {}
    if art_live.get("repo_skill_md_count") != live["repo_skill_md_count"]:
        return fail("artifact repo_skill_md_count != live re-run")
    if art_live.get("catalog_eight_no_frontmatter_instantiated") != live[
        "catalog_eight_no_frontmatter_instantiated"
    ]:
        return fail("artifact catalog-eight instantiation flag drifted")

    rec2 = (doc.get("named_probe_records") or {}).get("probe2") or {}
    if rec2.get("always_on_in_bag") is not True:
        return fail("named_probe_records.probe2 missing always_on_in_bag")

    injected = (ctl["turn0"] or {}).get("injected_ids") or []
    out = {
        "probe": "probe2-turn0",
        "unit_id": UNIT,
        "pass": True,
        "instrument": (ctl["turn0"] or {}).get("instrument"),
        "injected_ids": injected,
        "always_on_in_bag": True,
        "bare_rule_in_bag": True,
        "lazy_body_absent_at_t0": True,
        "empty_always_on_set_rejected": True,
        "naive_inference_loses_to_measurement": True,
        "demoted_by_paths_star": True,
        "repo_skill_md_count": live["repo_skill_md_count"],
        "live_trees_present_count": len(live["live_trees_present"]),
        "grok_inspect_present": live["grok_inspect"]["binary_present"],
        "artifact_matches_live": True,
    }
    (HERE / "probe2-turn0.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:AUD-0058-probe2 turn0 bag measurement; inference loses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
