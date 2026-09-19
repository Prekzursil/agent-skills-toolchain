"""IMP-0007: accept ``x-`` extensions; reject bare unknown top-level fields.

Catalog tests_required:
* tools/plugin/tests/test_strict_parser_policy.py (accept x-, reject bare unknown)
* NEGATIVE CONTROL: prove the strict fixture parser actually rejects something
  known-bad before trusting its acceptance
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest_schema as M  # noqa: E402
import strict_parser_policy as P  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def schema() -> dict:
    return M.load_schema(REPO)


@pytest.fixture
def fixture_doc() -> dict:
    return P.fixture_base_manifest()


def test_accept_x_extension_reject_bare_unknown(
    schema: dict, fixture_doc: dict
) -> None:
    """Catalog node: accept key under x-, reject the same bare unknown key."""
    P.assert_frozen_matches_schema(schema)

    bare = P.mutate_bare_unknown(fixture_doc)
    under_x = P.mutate_under_extension(fixture_doc)

    # Policy linter (fixture strict parser).
    with pytest.raises(P.StrictParserPolicyError) as policy_exc:
        P.assert_policy(bare)
    assert policy_exc.value.code in {
        P.ERR_UNKNOWN_TOP_LEVEL,
        P.ERR_NON_EXTENSION_ADDITIVE,
    }
    P.assert_policy(under_x)

    # Dual-library schema path (IMP-0006) must agree: bare fails, x- passes.
    v_bad1, v_bad2 = M.validate_manifest(bare, schema)
    assert not v_bad1.ok and not v_bad2.ok
    assert v_bad1.error_code == M.ERR_UNKNOWN_TOP_LEVEL

    v_good1, v_good2 = M.validate_manifest(under_x, schema)
    assert v_good1.ok and v_good2.ok

    # Wired assert_valid (schema + policy) must fail closed on bare unknown.
    with pytest.raises(M.ManifestSchemaError):
        M.assert_valid(bare, schema)
    M.assert_valid(under_x, schema)


def test_negative_control_rejects_known_bad(schema: dict, fixture_doc: dict) -> None:
    """NEGATIVE CONTROL: known-bad fixture is rejected before trusting acceptances."""
    known_bad = copy.deepcopy(fixture_doc)
    known_bad["totally_not_in_schema"] = {"planted": True}

    # Policy must fire.
    verdict = P.lint_unknown_fields(known_bad)
    assert verdict.ok is False
    assert "totally_not_in_schema" in verdict.unknown_keys

    # Schema dual-library must also fail (not warn-as-green).
    v1, v2 = M.validate_manifest(known_bad, schema)
    assert not v1.ok and not v2.ok
    assert v1.error_code == M.ERR_UNKNOWN_TOP_LEVEL

    # Baseline fixture still accepted (silent on good).
    P.assert_policy(fixture_doc)
    M.assert_valid(fixture_doc, schema)


def test_accept_reject_pair_helper(fixture_doc: dict) -> None:
    pair = P.accept_reject_pair(fixture_doc)
    assert pair["pair_confirmed"] is True
    assert pair["reject_bare_unknown"] is True
    assert pair["accept_under_x"] is True
    assert pair["extension_prefix"] == "x-"


def test_frozen_keys_match_schema_and_client(schema: dict) -> None:
    """Frozen list matches schema properties; client ALLOWED[''] must agree too."""
    P.assert_frozen_matches_schema(schema)
    assert P.frozen_keys_from_schema(schema) == P.FROZEN_TOP_LEVEL_KEYS
    client = P.load_client_allowed_top_level(REPO)
    assert client == P.FROZEN_TOP_LEVEL_KEYS, (
        f"frozen drift vs real client ALLOWED['']: "
        f"policy_only={sorted(P.FROZEN_TOP_LEVEL_KEYS - client)} "
        f"client_only={sorted(client - P.FROZEN_TOP_LEVEL_KEYS)}"
    )


def test_mutation_relax_additional_properties_makes_bare_unknown_schema_green(
    schema: dict, fixture_doc: dict
) -> None:
    """MUTATION / red-proof: relaxing additionalProperties makes bare unknown schema-green.

    Policy linter still fails closed (blocking) — unknown fields must not warn-as-green
    through the wired assert_valid path.
    """
    bare = P.mutate_bare_unknown(fixture_doc)
    relaxed = M.with_additional_properties(schema, allowed=True)
    v1, v2 = M.validate_manifest(bare, relaxed)
    assert v1.ok and v2.ok

    # Policy remains blocking even when schema soft-accepts.
    with pytest.raises(P.StrictParserPolicyError):
        P.assert_policy(bare)

    # Wired path: policy runs before libraries and still fails closed.
    # Use require_strict_additional=False equivalent by calling policy then libraries.
    with pytest.raises(M.ManifestSchemaError) as excinfo:
        M.assert_valid(bare, schema)  # strict schema: both policy and libraries block
    assert "unknown" in str(excinfo.value).lower() or "surprise" in str(excinfo.value)
