#!/usr/bin/env python3
"""Named probe 2: independent pre/post hash census vs payload-derived expected set.

Signal (2) of the catalog evidence_requirement. Builds the expected post-census
from v1 payload ∪ foreign maps — not from rollback()'s own added/removed lists.
Exit code zero is not treated as evidence inside this probe; the census match is.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin import trees as T  # noqa: E402
from plugin.rollback import (  # noqa: E402
    census,
    census_from_mapping,
    diff_census,
    foreign_preserved,
    rollback,
    wholesale_snapshot_restore,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe2-census.raw.json"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0026-probe2-"))
    live = T.seed_v2_with_foreign(tmp / "home")
    v1 = T.seed_payload(tmp / "payload-v1", T.PAYLOAD_V1)
    pre = census(live)
    expected_post = census_from_mapping(T.expected_post_v1_with_foreign())
    expected_delta = diff_census(pre, expected_post)

    report = rollback(live, v1, T.OWNED_V2, T.OWNED_V1)
    post = census(live)
    observed_delta = diff_census(pre, post)

    # Independent negative control on a sibling tree (not the measured live tree).
    ctrl_live = T.seed_v2_with_foreign(tmp / "home-wholesale")
    ctrl_pre = census(ctrl_live)
    wholesale_snapshot_restore(ctrl_live, v1)
    ctrl_post = census(ctrl_live)
    wholesale_fails = not foreign_preserved(ctrl_pre, ctrl_post, T.FOREIGN_PATHS)

    census_match = post == expected_post
    delta_match = observed_delta == expected_delta
    foreign_ok = foreign_preserved(pre, post, T.FOREIGN_PATHS)
    unexpected = sorted(
        (set(observed_delta["added"]) | set(observed_delta["removed"]) | set(observed_delta["changed"]))
        - (set(expected_delta["added"]) | set(expected_delta["removed"]) | set(expected_delta["changed"]))
    )
    missing_expected = sorted(
        (set(expected_delta["added"]) | set(expected_delta["removed"]) | set(expected_delta["changed"]))
        - (set(observed_delta["added"]) | set(observed_delta["removed"]) | set(observed_delta["changed"]))
    )

    doc = {
        "probe": "probe2-census",
        "unit_id": "IMP-0026",
        "oracle": "census_from_mapping(PAYLOAD_V1 ∪ FOREIGN) independent of rollback report lists",
        "pre_count": len(pre),
        "post_count": len(post),
        "expected_post_count": len(expected_post),
        "census_match": census_match,
        "delta_match": delta_match,
        "foreign_ok": foreign_ok,
        "expected_delta": expected_delta,
        "observed_delta": observed_delta,
        "rollback_reported_added": report.added,
        "rollback_reported_removed": report.removed,
        "rollback_reported_changed": report.changed,
        "unexpected_paths": unexpected,
        "missing_expected_paths": missing_expected,
        "wholesale_negative_control_fails_preservation": wholesale_fails,
        "wholesale_lost_foreign": sorted(set(T.FOREIGN_PATHS) - set(ctrl_post)),
        "pass": False,
    }
    ok = (
        census_match
        and delta_match
        and foreign_ok
        and wholesale_fails
        and not unexpected
        and not missing_expected
        and report.error is None
    )
    doc["pass"] = ok
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0026-probe2 census did not match payload-derived expected set")
        return 1
    print(
        "changed="
        + str(len(observed_delta["changed"]))
        + " added="
        + str(len(observed_delta["added"]))
        + " removed="
        + str(len(observed_delta["removed"]))
        + " census_match=True wholesale_fails="
        + str(wholesale_fails)
    )
    print("SUCCESS:IMP-0026-probe2 independent hash census matched expected set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
