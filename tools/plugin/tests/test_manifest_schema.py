"""IMP-0006: live plugin.json validates; six mutants fail distinctly; AP mutation proof."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest_schema as M  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def schema() -> dict:
    return M.load_schema(REPO)


@pytest.fixture(scope="module")
def live_doc() -> dict:
    return M.load_manifest(REPO / M.MANIFEST_RELPATH)


@pytest.fixture(scope="module")
def live_raw() -> str:
    return (REPO / M.MANIFEST_RELPATH).read_text(encoding="utf-8")


def test_current_manifest_validates(schema: dict, live_doc: dict) -> None:
    """Catalog node: tools/plugin/tests/test_manifest_schema.py::test_current_manifest_validates."""
    v1, v2 = M.validate_manifest(live_doc, schema)
    assert v1.ok is True, v1
    assert v2.ok is True, v2
    assert v1.ok == v2.ok
    # Wired assert helper must also stay silent on the live file.
    M.assert_valid(live_doc, schema)
    M.assert_live_manifest_valid(REPO)


def test_six_mutated_manifests_fail_distinctly(
    schema: dict, live_doc: dict, live_raw: str
) -> None:
    """NEGATIVE CONTROL: six mutants each fail with a distinct error code."""
    codes: list[str] = []

    # 1 missing name
    v1, v2 = M.validate_manifest(M.mutate_missing_name(live_doc), schema)
    assert not v1.ok and not v2.ok
    assert v1.error_code == M.ERR_MISSING_NAME
    codes.append(v1.error_code)

    # 2 bad semver
    v1, _ = M.validate_manifest(M.mutate_bad_semver(live_doc), schema)
    assert not v1.ok
    assert v1.error_code == M.ERR_BAD_SEMVER
    codes.append(v1.error_code)

    # 3 unknown top-level key
    v1, v2 = M.validate_manifest(M.mutate_unknown_top_level(live_doc), schema)
    assert not v1.ok and not v2.ok
    assert v1.error_code == M.ERR_UNKNOWN_TOP_LEVEL
    codes.append(v1.error_code)

    # 4 wrong type
    v1, v2 = M.validate_manifest(M.mutate_wrong_type(live_doc), schema)
    assert not v1.ok and not v2.ok
    assert v1.error_code == M.ERR_WRONG_TYPE
    codes.append(v1.error_code)

    # 5 empty keywords
    v1, v2 = M.validate_manifest(M.mutate_empty_keywords(live_doc), schema)
    assert not v1.ok and not v2.ok
    assert v1.error_code == M.ERR_EMPTY_KEYWORDS
    codes.append(v1.error_code)

    # 6 duplicate key (parse-time; both libraries never see the instance)
    dup_raw = M.mutate_duplicate_key_text(live_raw)
    with pytest.raises(M.ManifestSchemaError) as excinfo:
        M.parse_manifest_text(dup_raw)
    assert excinfo.value.code == M.ERR_DUPLICATE_KEY
    codes.append(excinfo.value.code)

    assert len(codes) == 6
    assert len(set(codes)) == 6, f"error codes must be distinct, got {codes}"


def test_relax_additional_properties_makes_unknown_key_green(
    schema: dict, live_doc: dict
) -> None:
    """MUTATION: relax additionalProperties → unknown-key mutant goes green."""
    unknown = M.mutate_unknown_top_level(live_doc)

    # Baseline: strict schema rejects.
    v1, v2 = M.validate_manifest(unknown, schema)
    assert not v1.ok and not v2.ok
    assert v1.error_code == M.ERR_UNKNOWN_TOP_LEVEL

    relaxed = M.with_additional_properties(schema, allowed=True)
    assert relaxed["additionalProperties"] is True
    assert schema["additionalProperties"] is False  # original untouched

    v1r, v2r = M.validate_manifest(unknown, relaxed)
    assert v1r.ok is True, v1r
    assert v2r.ok is True, v2r

    # Restoring the strict copy still rejects (rule identity proof).
    restored = M.with_additional_properties(relaxed, allowed=False)
    v1b, v2b = M.validate_manifest(unknown, restored)
    assert not v1b.ok and not v2b.ok


def test_phase4_fields_remain_contracted(schema: dict, live_doc: dict) -> None:
    """Phase-4 fields are optional properties; supplying them must still validate."""
    extended = copy.deepcopy(live_doc)
    extended["compatibility"] = {
        "min_client": "1.0.0",
        "platforms": ["linux"],
        "schema_version": 1,
    }
    extended["homepage"] = "https://example.invalid/ast"
    M.assert_valid(extended, schema)


def test_schema_path_is_existing_control_plane() -> None:
    """Do not introduce a second manifest file — only the existing plugin.json."""
    assert (REPO / M.MANIFEST_RELPATH).is_file()
    assert (REPO / M.SCHEMA_RELPATH).is_file()
    # Exactly one plugin.json under .claude-plugin/
    plugin_dir = REPO / ".claude-plugin"
    manifests = list(plugin_dir.glob("**/plugin.json"))
    assert manifests == [plugin_dir / "plugin.json"]
