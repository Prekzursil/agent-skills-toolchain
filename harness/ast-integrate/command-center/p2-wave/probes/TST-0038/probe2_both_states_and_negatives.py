"""Named probe 2 (independent reviewer): both-states + one negative per rule.

Does not import probe1. Rebuilds fixtures and re-derives the live items
defaults-only count from catalog.WORK_UNIT_FIELDS.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
import work_unit_conformance as wuc  # noqa: E402

UNIT = "TST-0038"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def rules_of(violations: list[dict]) -> set[str]:
    return {row["rule"] for row in violations}


def main() -> int:
    if wuc.RULES[0] != "R-PER-UNIT-KEY":
        return fail("rule table drifted")

    green = wuc.conforming_catalog()
    green_v = wuc.check_catalog(green, require_complete=True, enforce_enums=True)
    if green_v:
        return fail(f"GREEN fixture not silent: {green_v}")

    red = wuc.defaults_only_catalog()
    red_v = wuc.check_catalog(red, require_complete=True, enforce_enums=True)
    if "R-DEFAULTS-NOT-COMPLETE" not in rules_of(red_v):
        return fail(f"RED defaults-only did not fire R-DEFAULTS-NOT-COMPLETE: {red_v}")
    if not red_v:
        return fail("RED fixture silent")

    missing = copy.deepcopy(green)
    missing["items"][0].pop("title")
    missing_v = wuc.check_catalog(missing)
    if "R-PER-UNIT-KEY" not in rules_of(missing_v):
        return fail(f"missing title not R-PER-UNIT-KEY: {missing_v}")

    empty = copy.deepcopy(green)
    empty["items"][0]["title"] = ""
    empty_v = wuc.check_catalog(empty)
    if "R-EMPTY-REJECTED" not in rules_of(empty_v):
        return fail(f"empty title not R-EMPTY-REJECTED: {empty_v}")

    substrate = copy.deepcopy(green)
    substrate["items"][0]["execution_substrate"] = "quantum-substrate"
    sub_v = wuc.check_catalog(substrate)
    if "R-SUBSTRATE-ENUM" not in rules_of(sub_v):
        return fail(f"unknown substrate not R-SUBSTRATE-ENUM: {sub_v}")

    failure = copy.deepcopy(green)
    failure["items"][0]["failure_classification"] = ["not-a-real-class-xyzzy"]
    fail_v = wuc.check_catalog(failure)
    if "R-FAILURE-ENUM" not in rules_of(fail_v):
        return fail(f"unknown failure class not R-FAILURE-ENUM: {fail_v}")

    # Bare invocation is armed: omitting --allow-defaults must reject RED.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tst0038-p2-") as raw:
        tmp = Path(raw)
        gpath = tmp / "green.json"
        rpath = tmp / "red.json"
        gpath.write_text(json.dumps(green) + "\n", encoding="utf-8")
        rpath.write_text(json.dumps(red) + "\n", encoding="utf-8")
        rc_g = wuc.main(["--catalog", str(gpath), "--items-only"])
        rc_r = wuc.main(["--catalog", str(rpath), "--items-only"])
        rc_disarmed = wuc.main(
            ["--catalog", str(rpath), "--items-only", "--allow-defaults", "--no-enums"]
        )
    if rc_g != 0:
        return fail(f"bare GREEN rc={rc_g}")
    if rc_r == 0:
        return fail("bare RED rc=0 (checker disarmed)")
    if rc_disarmed != 0:
        return fail(f"--allow-defaults should silence defaults-only, rc={rc_disarmed}")

    # Independent live re-count: 11 fields present on 0/103 items.
    live = cat.load()
    defaults = live.get("defaults") if isinstance(live.get("defaults"), dict) else {}
    items = cat.items(live)
    if len(items) != 103:
        return fail(f"live items {len(items)}")
    zero_on_item = []
    for field in cat.WORK_UNIT_FIELDS:
        n = sum(1 for unit in items if field in unit)
        if n == 0 and field in defaults:
            zero_on_item.append(field)
    if len(zero_on_item) != 11:
        return fail(f"live defaults-only count {len(zero_on_item)} {zero_on_item}")

    payload = {
        "probe": "probe2-both-states-negatives",
        "unit_id": UNIT,
        "green_silent": True,
        "red_fires": True,
        "negatives": {
            "R-PER-UNIT-KEY": True,
            "R-DEFAULTS-NOT-COMPLETE": True,
            "R-SUBSTRATE-ENUM": True,
            "R-FAILURE-ENUM": True,
            "R-EMPTY-REJECTED": True,
            "R-BARE-ARMED": True,
        },
        "bare_green_rc": rc_g,
        "bare_red_rc": rc_r,
        "allow_defaults_red_rc": rc_disarmed,
        "live_items_defaults_only": zero_on_item,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "GREEN silent; RED fires; negatives="
        + ",".join(sorted(payload["negatives"]))
    )
    print(f"SUCCESS:{UNIT}-probe2 both-states and per-rule negatives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
