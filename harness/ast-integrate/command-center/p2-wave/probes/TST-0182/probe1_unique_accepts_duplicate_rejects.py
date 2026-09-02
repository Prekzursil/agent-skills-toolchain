#!/usr/bin/env python3
"""Probe 1: unique-key objects validate; duplicate keys are rejected with both
values; a raw token scan independently counts the repeated key.

Does not use json.load as the validator (that is the negative control in probe 2).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.json_key_scan import count_key_occurrences, scan_keys  # noqa: E402
from plugin.manifest_validator import validate_manifest_text  # noqa: E402
from plugin.strict_json import DuplicateKeyError, loads_strict  # noqa: E402

FIX = HERE / "fixtures"
FIRST = "first-owner-intent"
SECOND = "second-last-wins"


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0182-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def main() -> int:
    unique_plugin = read("unique-plugin.json")
    unique_market = read("unique-marketplace.json")
    duplicate = read("duplicate-name.json")
    nested = read("nested-duplicate.json")

    v_plugin = validate_manifest_text(unique_plugin)
    v_market = validate_manifest_text(unique_market)
    if not v_plugin.ok or v_plugin.document is None:
        return fail("unique-key plugin manifest was rejected", str(v_plugin.error))
    if not v_market.ok or v_market.document is None:
        return fail("unique-key marketplace manifest was rejected", str(v_market.error))
    if v_plugin.document.get("name") != "demo-plugin":
        return fail("unique plugin name mismatch", v_plugin.document)
    if v_market.document.get("name") != "harness-marketplace":
        return fail("unique marketplace name mismatch", v_market.document)

    plugin_counts = scan_keys(unique_plugin).counts_at("$")
    if any(n != 1 for n in plugin_counts.values()):
        return fail("token scan found a repeated key on the unique plugin", plugin_counts)
    if count_key_occurrences(unique_plugin, "name") != 1:
        return fail("token scan name count on unique plugin is not 1")

    v_dup = validate_manifest_text(duplicate)
    if v_dup.ok:
        return fail("duplicate-key object was accepted")
    if not isinstance(v_dup.error, DuplicateKeyError):
        return fail("duplicate-key error was not DuplicateKeyError", str(v_dup.error))
    err = v_dup.error
    if err.key != "name":
        return fail(f"duplicate error named key {err.key!r}, expected 'name'")
    if err.first_value != FIRST or err.second_value != SECOND:
        return fail(
            "validator did not report both owner values",
            {"first": err.first_value, "second": err.second_value},
        )
    if not err.reports_both_values():
        return fail("DuplicateKeyError message omitted a value", str(err))

    try:
        loads_strict(duplicate)
        return fail("loads_strict accepted duplicate-name.json")
    except DuplicateKeyError as exc:
        if exc.first_value != FIRST or exc.second_value != SECOND:
            return fail("loads_strict both-values mismatch", str(exc))
        validator_exc = str(exc)
    else:
        validator_exc = ""

    scan = scan_keys(duplicate)
    name_count = scan.counts_at("$").get("name", 0)
    name_values = scan.values_at("$", "name")
    if name_count != 2:
        return fail(f"token scan name count={name_count}, expected 2", scan.counts_at("$"))
    if name_values != [FIRST, SECOND]:
        return fail("token scan values did not match both owner intents", name_values)
    dups = scan.duplicate_keys()
    if not dups:
        return fail("token scan reported no duplicate keys")

    v_nested = validate_manifest_text(nested)
    if v_nested.ok:
        return fail("nested duplicate-key object was accepted")
    if not isinstance(v_nested.error, DuplicateKeyError):
        return fail("nested duplicate was not DuplicateKeyError", str(v_nested.error))
    if v_nested.error.key != "name":
        return fail(f"nested duplicate key {v_nested.error.key!r}")
    if v_nested.error.first_value != "first-author" or v_nested.error.second_value != "second-author":
        return fail(
            "nested duplicate did not report both author values",
            {
                "first": v_nested.error.first_value,
                "second": v_nested.error.second_value,
            },
        )
    nested_scan = scan_keys(nested)
    if nested_scan.counts_at("$.author").get("name") != 2:
        return fail(
            "token scan missed nested duplicate",
            nested_scan.counts_at("$.author"),
        )
    if nested_scan.values_at("$.author", "name") != ["first-author", "second-author"]:
        return fail(
            "token scan nested values mismatch",
            nested_scan.values_at("$.author", "name"),
        )

    summary = {
        "pass": True,
        "probe": "probe1-unique-accepts-duplicate-rejects",
        "unit_id": "TST-0182",
        "unique_plugin_ok": True,
        "unique_marketplace_ok": True,
        "duplicate_rejected": True,
        "duplicate_key": err.key,
        "first_value": err.first_value,
        "second_value": err.second_value,
        "both_values_in_error": err.reports_both_values(),
        "token_scan_name_count": name_count,
        "token_scan_values": name_values,
        "nested_duplicate_rejected": True,
        "validator_error": validator_exc,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"unique_ok plugin={v_plugin.ok} marketplace={v_market.ok} "
        f"dup_rejected key={err.key!r} first={FIRST!r} second={SECOND!r} "
        f"token_count={name_count}"
    )
    print("SUCCESS:TST-0182-probe1 unique-key validates; duplicate rejected with both values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
