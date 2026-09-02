#!/usr/bin/env python3
"""Probe 2: independent reviewer + stdlib json.load negative control.

A checker built on json.load (file) / json.loads (string) silently
last-wins. That checker MUST fail this unit: it accepts the duplicate
object and cannot report both values. Probe 1 is not imported.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.json_key_scan import scan_keys  # noqa: E402
from plugin.manifest_validator import validate_manifest_text  # noqa: E402
from plugin.strict_json import DuplicateKeyError  # noqa: E402

FIX = HERE / "fixtures"
FIRST = "first-owner-intent"
SECOND = "second-last-wins"
DUP_PATH = FIX / "duplicate-name.json"


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0182-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def stdlib_json_load_checker(path: Path) -> dict:
    """Catalog negative control: json.load silently takes the last value."""
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    return {
        "accepted": True,
        "document": document,
        "name": document.get("name") if isinstance(document, dict) else None,
        "can_report_both_values": False,
    }


def stdlib_json_loads_checker(text: str) -> dict:
    document = json.loads(text)
    return {
        "accepted": True,
        "document": document,
        "name": document.get("name") if isinstance(document, dict) else None,
        "can_report_both_values": False,
    }


def checker_fails_this_test(result: dict) -> bool:
    """TST-0182 fails a checker that accepts duplicates or drops a value."""
    if result.get("accepted") is True:
        return True
    if result.get("can_report_both_values") is not True:
        return True
    return False


def main() -> int:
    unique = (FIX / "unique-plugin.json").read_text(encoding="utf-8")
    duplicate = DUP_PATH.read_text(encoding="utf-8")

    # Both-states: unique-key object still validates under the real validator.
    unique_verdict = validate_manifest_text(unique)
    if not unique_verdict.ok:
        return fail("reviewer unique-key object did not validate", str(unique_verdict.error))

    load_result = stdlib_json_load_checker(DUP_PATH)
    loads_result = stdlib_json_loads_checker(duplicate)
    if load_result["name"] != SECOND or loads_result["name"] != SECOND:
        return fail(
            "stdlib checker did not last-win as the catalog requires",
            {"load": load_result["name"], "loads": loads_result["name"]},
        )
    if FIRST in (load_result["document"] or {}):
        # The key exists once; the first value must be gone.
        pass
    if load_result["document"].get("name") == FIRST:
        return fail("stdlib json.load kept the first value; last-wins did not fire")
    if FIRST not in duplicate or SECOND not in duplicate:
        return fail("fixture no longer contains both owner values as source text")

    # json.load cannot recover the discarded first value from the dict.
    recovered = load_result["document"]
    if recovered.get("name") == FIRST:
        return fail("last-wins failed: first value still present as name")
    if list(recovered.keys()).count("name") != 1:
        return fail("collapsed dict still showed duplicate keys")

    stdlib_fails = checker_fails_this_test(load_result) and checker_fails_this_test(
        loads_result
    )
    if not stdlib_fails:
        return fail("stdlib json.load checker was scored as passing TST-0182")

    # Independent reproduction of the production validator (no probe1 import).
    live = validate_manifest_text(duplicate)
    if live.ok or not isinstance(live.error, DuplicateKeyError):
        return fail("reviewer: production validator did not reject duplicate", str(live.error))
    if live.error.first_value != FIRST or live.error.second_value != SECOND:
        return fail(
            "reviewer: both values missing from validator error",
            {"first": live.error.first_value, "second": live.error.second_value},
        )
    if not live.error.reports_both_values():
        return fail("reviewer: error text omitted a value", str(live.error))

    scan = scan_keys(duplicate)
    if scan.counts_at("$").get("name") != 2:
        return fail("reviewer token scan count != 2", scan.counts_at("$"))
    if scan.values_at("$", "name") != [FIRST, SECOND]:
        return fail("reviewer token scan values mismatch", scan.values_at("$", "name"))

    # StringIO json.load is the same last-wins collapse.
    sio = json.load(io.StringIO(duplicate))
    if sio.get("name") != SECOND:
        return fail("json.load(StringIO) did not last-win")

    # Mutation: if the production validator were replaced by json.load, this
    # test would go green on a last-wins document. Record that counterfactual.
    mutant_would_accept = load_result["accepted"] is True

    summary = {
        "pass": True,
        "probe": "probe2-stdlib-last-wins-fails-and-reviewer",
        "unit_id": "TST-0182",
        "unique_key_validates": True,
        "stdlib_json_load_accepted_duplicate": True,
        "stdlib_last_wins_value": load_result["name"],
        "stdlib_discarded_first_value": FIRST,
        "stdlib_checker_fails_this_test": True,
        "stdlib_can_report_both_values": False,
        "production_rejects_with_both_values": True,
        "token_scan_name_count": 2,
        "token_scan_values": scan.values_at("$", "name"),
        "mutant_json_load_as_validator_would_accept": mutant_would_accept,
        "reviewer_id": "TST-0182-probe2-stdlib-last-wins-fails-and-reviewer",
        "verdict": "PASS",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "stdlib_json.load accepted last-wins="
        f"{load_result['name']!r} discarded={FIRST!r} "
        "stdlib_fails_this_test=True production_rejects=True token_count=2"
    )
    print("SUCCESS:TST-0182-probe2 stdlib json.load last-wins fails this test; reviewer PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
