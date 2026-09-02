#!/usr/bin/env python3
"""Probe 2: known-present unanchored meta-finding is caught; known-good is silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

OUT = REPO / "command-center" / "receipts" / "SYN-0039.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0039-probe2 {msg}")
    return 1


def main() -> int:
    with_plant = E.review(include_fixtures=True, depth=2)
    planted = with_plant["controls"]["planted_unanchored"]
    good = with_plant["controls"]["known_good"]
    if planted is None:
        return fail("planted unanchored finding missing from review")
    if planted.get("anchored") is not False:
        return fail(f"planted unanchored was not caught: {planted}")
    if "unanchored" not in (planted.get("failing_tests") or []):
        return fail(f"planted disposition missing unanchored: {planted.get('disposition')}")
    if good is None:
        return fail("known-good control missing")
    if good.get("anchored") is not True:
        return fail(f"known-good not anchored: {good}")
    if good.get("scoped") is not True:
        return fail(f"known-good not scoped: {good}")
    if good.get("remedy_named") is not True:
        return fail(f"known-good missing remedy: {good}")
    if good.get("disposition") != "ACCEPT":
        return fail(f"known-good held: {good.get('disposition')}")

    without = E.review(include_fixtures=False, depth=2)
    ids = {r["id"] for r in without["meta_findings"]}
    if "PLANT-UNANCHORED" in ids:
        return fail("plant leaked into include_fixtures=False corpus")
    if any(r["id"] == "CTRL-GOOD" for r in without["meta_findings"]):
        return fail("known-good leaked into include_fixtures=False corpus")

    if not OUT.is_file():
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    rows = {
        r["id"]: r
        for r in E.payload_from_artifact(doc)["meta_findings"]
        if isinstance(r, dict) and r.get("id")
    }
    art_plant = rows.get("PLANT-UNANCHORED")
    art_good = rows.get("CTRL-GOOD")
    if not art_plant or art_plant.get("anchored") is not False:
        return fail("artifact did not catch planted unanchored")
    if not art_good or art_good.get("disposition") != "ACCEPT":
        return fail("artifact known-good was not ACCEPT")

    print(
        "planted_anchored="
        f"{planted['anchored']} planted_disp={planted['disposition']}"
    )
    print(
        "good_anchored="
        f"{good['anchored']} good_scoped={good['scoped']} "
        f"good_remedy={good['remedy_named']} disp={good['disposition']}"
    )
    print("SUCCESS:SYN-0039-probe2 unanchored control caught; known-good silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
