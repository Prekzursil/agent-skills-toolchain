"""IMP-0009: case-distinct and exact-duplicate JSON key collision guard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest_schema as M  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def live_raw() -> str:
    return (REPO / M.MANIFEST_RELPATH).read_text(encoding="utf-8")


def test_case_distinct_keys_rejected(live_raw: str) -> None:
    """Catalog node: tools/plugin/tests/test_case_collision.py::test_case_distinct_keys_rejected."""
    planted = M.mutate_case_collision_text(live_raw)
    with pytest.raises(M.ManifestSchemaError) as excinfo:
        M.parse_manifest_text(planted)
    assert excinfo.value.code == M.ERR_CASE_COLLISION
    assert "Name" in str(excinfo.value) and "name" in str(excinfo.value)


def test_exact_duplicate_keys_rejected(live_raw: str) -> None:
    """Catalog node: tools/plugin/tests/test_case_collision.py::test_exact_duplicate_keys_rejected."""
    planted = M.mutate_duplicate_key_text(live_raw)
    with pytest.raises(M.ManifestSchemaError) as excinfo:
        M.parse_manifest_text(planted)
    assert excinfo.value.code == M.ERR_DUPLICATE_KEY


def test_negative_control_clean_passes_planted_fails(live_raw: str) -> None:
    """NEGATIVE CONTROL: clean passes while planted fails in the same run."""
    # Clean live plugin.json + dispatch manifest both parse.
    M.assert_path_free_of_key_collisions(REPO / M.MANIFEST_RELPATH)
    M.assert_path_free_of_key_collisions(REPO / M.DISPATCH_MANIFEST_RELPATH)
    clean_doc = M.parse_manifest_text(live_raw)
    assert isinstance(clean_doc, dict)
    assert "name" in clean_doc

    case_planted = M.mutate_case_collision_text(live_raw)
    with pytest.raises(M.ManifestSchemaError) as case_exc:
        M.parse_manifest_text(case_planted)
    assert case_exc.value.code == M.ERR_CASE_COLLISION

    dup_planted = M.mutate_duplicate_key_text(live_raw)
    with pytest.raises(M.ManifestSchemaError) as dup_exc:
        M.parse_manifest_text(dup_planted)
    assert dup_exc.value.code == M.ERR_DUPLICATE_KEY


def test_pairs_hook_preserves_evidence_plain_dict_destroys_exact_dup(
    live_raw: str,
) -> None:
    """Reviewer-facing: pairs hook preserves; plain dict load measures nothing for exact dups."""
    exact = M.mutate_duplicate_key_text(live_raw)
    pairs_keys = M.top_level_key_occurrences(exact)
    assert pairs_keys.count("name") >= 2
    assert M.find_exact_duplicate_keys(pairs_keys) == ["name"]

    naive = json.loads(exact)
    # Plain dict collapsed the exact duplicate — evidence destroyed.
    assert list(naive.keys()).count("name") == 1

    case_planted = M.mutate_case_collision_text(live_raw)
    case_keys = M.top_level_key_occurrences(case_planted)
    collisions = M.find_case_collisions(case_keys)
    assert ("Name", "name") in collisions or any(
        a.casefold() == b.casefold() and a != b for a, b in collisions
    )
    # Case-insensitive fold would collapse to one identity.
    folded = {k.casefold() for k in case_keys}
    assert "name" in folded
    assert len([k for k in case_keys if k.casefold() == "name"]) == 2
