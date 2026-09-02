#!/usr/bin/env python3
"""Catalog tests for TST-0112: flags, keys, paths — both directions + both states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from parity import measure_fixture  # noqa: E402

ALIGNED = HERE / "fixtures" / "aligned"
MISMATCH = HERE / "fixtures" / "mismatch"


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def test_documented_flags_match_the_parser_both_directions() -> dict:
    aligned = measure_fixture(ALIGNED)["flags"]
    mismatch = measure_fixture(MISMATCH)["flags"]

    if aligned["documented_not_implemented_count"] != 0:
        _fail(f"aligned documented-absent flags: {aligned['documented_not_implemented']}")
    if aligned["implemented_not_documented_count"] != 0:
        _fail(f"aligned undocumented flags: {aligned['implemented_not_documented']}")

    if "--ghost-flag" not in mismatch["documented_not_implemented"]:
        _fail("planted documented-but-absent --ghost-flag not in documented_not_implemented")
    if "--undocumented-real" not in mismatch["implemented_not_documented"]:
        _fail("planted undocumented-but-real --undocumented-real not in implemented_not_documented")
    if "--ghost-flag" in mismatch["implemented_not_documented"]:
        _fail("documented-absent flag wrongly classified as undocumented-real")
    if "--undocumented-real" in mismatch["documented_not_implemented"]:
        _fail("undocumented-real flag wrongly classified as documented-absent")
    if "--legacy-removed" in mismatch["documented"]:
        _fail("removed-in-v2 mention counted as a live documented flag")
    if "--legacy-removed" not in mismatch["mention_only"]:
        _fail("removed-in-v2 mention not recorded in mention_only")
    if mismatch["documented_not_implemented"] == mismatch["implemented_not_documented"]:
        _fail("both-direction sets collapsed; documented-absent and undocumented-real must differ")

    return {
        "id": "test_documented_flags_match_the_parser_both_directions",
        "result": "PASS",
        "aligned_empty_both_ways": True,
        "planted_documented_absent": "--ghost-flag",
        "planted_undocumented_real": "--undocumented-real",
        "mention_suppressed": "--legacy-removed",
    }


def test_documented_config_keys_exist_in_the_schema() -> dict:
    aligned = measure_fixture(ALIGNED)["keys"]
    mismatch = measure_fixture(MISMATCH)["keys"]

    if aligned["documented_not_implemented_count"] != 0:
        _fail(f"aligned documented-absent keys: {aligned['documented_not_implemented']}")
    if "missing_key" not in mismatch["documented_not_implemented"]:
        _fail("planted missing_key not reported as documented-not-in-schema")
    if "retries" not in mismatch["implemented_not_documented"]:
        _fail("schema-only retries not reported as implemented-not-documented")
    if "missing_key" in mismatch["implemented_not_documented"]:
        _fail("documented-absent key classified as schema-only")
    if "retries" in mismatch["documented_not_implemented"]:
        _fail("schema-only key classified as documented-absent")

    return {
        "id": "test_documented_config_keys_exist_in_the_schema",
        "result": "PASS",
        "aligned_documented_in_schema": True,
        "planted_documented_absent": "missing_key",
        "planted_schema_only": "retries",
    }


def test_documented_paths_resolve() -> dict:
    aligned = measure_fixture(ALIGNED)["paths"]
    mismatch = measure_fixture(MISMATCH)["paths"]

    if aligned["documented_not_tree_count"] != 0:
        _fail(f"aligned documented paths missing: {aligned['documented_not_tree']}")
    if aligned["tree_not_documented_count"] != 0:
        _fail(f"aligned tree orphans: {aligned['tree_not_documented']}")
    if "nowhere/missing.txt" not in mismatch["documented_not_tree"]:
        _fail("planted missing path not in documented_not_tree")
    if "src/orphan.py" not in mismatch["tree_not_documented"]:
        _fail("planted tree orphan not in tree_not_documented")
    if "src/app.py" not in mismatch["resolved"]:
        _fail("existing documented path failed to resolve")

    return {
        "id": "test_documented_paths_resolve",
        "result": "PASS",
        "aligned_all_resolve": True,
        "planted_missing_path": "nowhere/missing.txt",
        "planted_tree_orphan": "src/orphan.py",
    }


TESTS = (
    test_documented_flags_match_the_parser_both_directions,
    test_documented_config_keys_exist_in_the_schema,
    test_documented_paths_resolve,
)


def run_tests() -> list[dict]:
    rows = []
    for fn in TESTS:
        try:
            row = fn()
        except AssertionError as exc:
            row = {"id": fn.__name__, "result": "FAIL", "error": str(exc)}
        rows.append(row)
    return rows


def main() -> int:
    rows = run_tests()
    failed = [r for r in rows if r.get("result") != "PASS"]
    print(json.dumps({"tests": rows}, indent=2, sort_keys=True))
    if failed:
        print("FAILED:TST-0112-tests " + ",".join(r["id"] for r in failed))
        return 1
    print("SUCCESS:TST-0112-tests flags-keys-paths both-directions both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
