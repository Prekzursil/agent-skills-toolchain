#!/usr/bin/env python3
"""IMP-0067 tests: live index validates; six mutants fail distinctly."""
from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(TOOLS))
from marketplace import index_schema as S  # noqa: E402


def test_current_marketplace_json_validates() -> None:
    index = S.load_index()
    schema = S.load_schema()
    a = S.validate_engine_a(index, schema)
    b = S.validate_engine_b(index, schema)
    assert a.ok and b.ok, (a.as_dict(), b.as_dict())


def test_six_mutations_fail_distinctly() -> None:
    rows = S.mutation_verdicts()
    codes = [rows[mid]["engine_a"]["primary_code"] for mid in S.MUTATION_IDS]
    assert set(codes) == set(S.MUTATION_IDS)
    assert len(set(codes)) == 6
    assert all(not rows[mid]["engine_a"]["ok"] for mid in S.MUTATION_IDS)


def test_mutated_indexes_are_the_six_named_cases() -> None:
    assert tuple(S.MUTATION_IDS) == (
        "missing_owner",
        "bad_version",
        "duplicate_plugin_name",
        "unknown_key",
        "empty_plugins",
        "wrong_type",
    )


def test_engines_are_independent_modules() -> None:
    tree = ast.parse(inspect.getsource(S))
    top = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            top.add(node.module.split(".")[0])
    assert "jsonschema" not in top
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "validate_engine_b":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    assert all(a.name.split(".")[0] != "jsonschema" for a in sub.names)
                elif isinstance(sub, ast.ImportFrom) and sub.module:
                    assert not sub.module.startswith("jsonschema")


def test_extension_is_additive() -> None:
    index = S.load_index()
    ext = S.extended_example(index)
    schema = S.load_schema()
    assert S.validate_engine_a(index, schema).ok
    assert S.validate_engine_a(ext, schema).ok
    assert S.validate_engine_b(ext, schema).ok
    for key in ("packages", "channels", "provenance", "digest"):
        assert key in ext and key not in index


def test_live_report_green() -> None:
    report = S.live_report()
    assert report["current_ok_a"] and report["current_ok_b"]
    assert report["extended_ok_a"] and report["extended_ok_b"]
    assert report["mutation_codes_distinct"]
    assert report["mutation_primary_matches_id"]
    assert report["all_mutations_agree"]
    assert report["no_second_index"]


def test_no_second_index_file() -> None:
    assert S.scan_second_indexes() == []


def test_schema_file_is_the_authored_contract() -> None:
    schema = S.load_schema()
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("additionalProperties") is False
    for key in ("packages", "channels", "provenance", "digest"):
        assert key in schema["properties"]
    path = Path(__file__).resolve().parents[3] / S.SCHEMA_REL
    assert path.is_file() and path.stat().st_size > 200


def main() -> int:
    failed: list[str] = []
    names = [
        "test_current_marketplace_json_validates",
        "test_engines_are_independent_modules",
        "test_extension_is_additive",
        "test_live_report_green",
        "test_mutated_indexes_are_the_six_named_cases",
        "test_no_second_index_file",
        "test_schema_file_is_the_authored_contract",
        "test_six_mutations_fail_distinctly",
    ]
    g = globals()
    for name in names:
        try:
            g[name]()
            print(f"PASS {name}")
        except Exception as exc:
            failed.append(name)
            print(f"FAIL {name} {type(exc).__name__}: {exc}")
    if failed:
        print(f"FAILED:IMP-0067 tests {failed}")
        return 1
    print("SUCCESS:IMP-0067 tests 8 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
