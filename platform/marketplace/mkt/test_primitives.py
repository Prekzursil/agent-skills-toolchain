"""Tests for the marketplace primitives: canonical form, Ed25519, semver, permissions, schemas.

Half of these are NEGATIVE on purpose. A canonicaliser that never refuses, a verifier that never
rejects, and a permission model that never says no are all indistinguishable from no control at
all, so each positive assertion is paired with the input that must fail.
"""

from __future__ import annotations

import json

import pytest

from mkt import canon, crypto, permissions, schemas, versions

# --------------------------------------------------------------------------- #
# canonical form
# --------------------------------------------------------------------------- #


def test_canonical_bytes_sorts_keys_and_strips_whitespace():
    assert canon.canonical_bytes({"b": 1, "a": [1, 2]}) == b'{"a":[1,2],"b":1}'


def test_canonical_bytes_is_stable_under_key_order():
    left = canon.canonical_bytes({"x": {"p": 1, "q": 2}, "y": 3})
    right = canon.canonical_bytes({"y": 3, "x": {"q": 2, "p": 1}})
    assert left == right


@pytest.mark.parametrize(
    "doc",
    [
        {"score": 0.95},
        {"nested": {"list": [1, 2.5]}},
        [1, [2, 3.0]],
    ],
)
def test_canonical_bytes_refuses_floats(doc):
    """Floats have no portable JSON spelling; a signed float would break its own signature."""
    with pytest.raises(canon.CanonError, match="float"):
        canon.canonical_bytes(doc)


def test_canonical_bytes_refuses_non_string_keys_and_exotic_types():
    with pytest.raises(canon.CanonError, match="non-string object key"):
        canon.canonical_bytes({1: "a"})
    with pytest.raises(canon.CanonError, match="unserialisable type"):
        canon.canonical_bytes({"a": {1, 2}})


def test_payload_digest_is_order_independent_but_content_sensitive():
    a = [
        {"path": "b.txt", "sha256": "sha256:" + "1" * 64},
        {"path": "a.txt", "sha256": "sha256:" + "2" * 64},
    ]
    b = list(reversed(a))
    assert canon.payload_digest(a) == canon.payload_digest(b)
    c = [dict(a[0]), {"path": "a.txt", "sha256": "sha256:" + "3" * 64}]
    assert canon.payload_digest(a) != canon.payload_digest(c)


def test_payload_digest_covers_the_path_not_only_the_bytes():
    """Renaming a file must change the digest, or a rename is an undetected change."""
    same_hash = "sha256:" + "a" * 64
    assert canon.payload_digest(
        [{"path": "one.txt", "sha256": same_hash}]
    ) != canon.payload_digest([{"path": "two.txt", "sha256": same_hash}])


def test_ensure_within_rejects_sibling_prefix(tmp_path):
    """`<root>-evil` must NOT pass containment. This is the shipped-before prefix bug."""
    root = tmp_path / "site"
    root.mkdir()
    sibling = tmp_path / "site-evil"
    sibling.mkdir()
    assert canon.ensure_within(root, "a/b.txt").is_relative_to(root)
    with pytest.raises(canon.ContainmentError):
        canon.ensure_within(root, str(sibling / "x.txt"))


def test_ensure_within_rejects_traversal(tmp_path):
    with pytest.raises(canon.ContainmentError):
        canon.ensure_within(tmp_path / "site", "../../etc/passwd")


def test_write_json_is_atomic_and_readable(tmp_path):
    target = tmp_path / "deep" / "doc.json"
    canon.write_json(target, {"b": 2, "a": 1})
    assert canon.read_json(target) == {"a": 1, "b": 2}
    assert not list(tmp_path.rglob("*.tmp.*"))


def test_iso_round_trip_and_rejection():
    now = canon.iso_now()
    assert canon.parse_iso(now).tzinfo is not None
    with pytest.raises(canon.CanonError):
        canon.parse_iso("2026-08-10 09:00:00")


# --------------------------------------------------------------------------- #
# crypto
# --------------------------------------------------------------------------- #


def test_keypair_is_deterministic_from_a_seed():
    a = crypto.generate_keypair(bytes(range(32)))
    b = crypto.generate_keypair(bytes(range(32)))
    assert a == b
    assert a[1].startswith("ed25519:")


def test_sign_and_verify_round_trip():
    secret, public = crypto.generate_keypair(bytes(range(32)))
    doc = {"name": "x", "value": 1}
    doc["signature"] = crypto.sign_document(doc, "mkt.manifest.v1", secret)
    ok, why = crypto.verify_document(doc, "mkt.manifest.v1", expected_public_key=public)
    assert ok, why


def test_verify_rejects_a_document_edited_after_signing():
    secret, _ = crypto.generate_keypair(bytes(range(32)))
    doc = {"name": "x", "value": 1}
    doc["signature"] = crypto.sign_document(doc, "mkt.manifest.v1", secret)
    doc["value"] = 2
    ok, why = crypto.verify_document(doc, "mkt.manifest.v1")
    assert not ok
    assert "digest mismatch" in why


def test_verify_rejects_a_replayed_signature_from_another_domain():
    """Domain separation: an index signature must not verify as a manifest signature."""
    secret, _ = crypto.generate_keypair(bytes(range(32)))
    doc = {"name": "x"}
    doc["signature"] = crypto.sign_document(doc, "mkt.index.v1", secret)
    ok, why = crypto.verify_document(doc, "mkt.manifest.v1")
    assert not ok
    assert "domain mismatch" in why


def test_verify_rejects_a_key_the_caller_did_not_expect():
    secret, _ = crypto.generate_keypair(bytes(range(32)))
    other = crypto.generate_keypair(bytes(range(1, 33)))[1]
    doc = {"name": "x"}
    doc["signature"] = crypto.sign_document(doc, "mkt.manifest.v1", secret)
    ok, why = crypto.verify_document(doc, "mkt.manifest.v1", expected_public_key=other)
    assert not ok
    assert "not trusted" in why


def test_verify_rejects_a_forged_signature_body():
    secret, _ = crypto.generate_keypair(bytes(range(32)))
    doc = {"name": "x"}
    doc["signature"] = crypto.sign_document(doc, "mkt.manifest.v1", secret)
    sig = doc["signature"]["signature"]
    doc["signature"]["signature"] = ("0" if sig[0] != "0" else "1") + sig[1:]
    ok, why = crypto.verify_document(doc, "mkt.manifest.v1")
    assert not ok
    assert "signature mismatch" in why


def test_verify_rejects_a_mismatched_key_id():
    secret, _ = crypto.generate_keypair(bytes(range(32)))
    doc = {"name": "x"}
    doc["signature"] = crypto.sign_document(doc, "mkt.manifest.v1", secret)
    doc["signature"]["key_id"] = "key:" + "0" * 16
    ok, why = crypto.verify_document(doc, "mkt.manifest.v1")
    assert not ok
    assert "key_id" in why


def test_unknown_signing_domain_raises():
    with pytest.raises(crypto.CryptoError, match="unknown signing domain"):
        crypto.signing_bytes("mkt.not-a-domain", {})


def test_cross_vendor_agreement_with_cryptography():
    """SECOND, MECHANICALLY INDEPENDENT INSTRUMENT.

    ``cryptography`` ships a Rust/OpenSSL Ed25519. If it is absent this test SKIPS and says so
    -- it is never silently folded into a pass.
    """
    ref = pytest.importorskip(
        "cryptography.hazmat.primitives.asymmetric.ed25519",
        reason="cryptography not installed: the cross-vendor signature check is NOT-CHECKED here",
    )
    secret, public = crypto.generate_keypair(bytes(range(2, 34)))
    message = b"mkt.manifest.v1|{}"
    ours = crypto.raw_sign(bytes.fromhex(secret), message)
    theirs = ref.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(secret)).sign(
        message
    )
    assert ours == theirs, (
        "two independent Ed25519 implementations must agree byte-for-byte"
    )
    ref.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public.split(":")[1])).verify(
        ours, message
    )
    assert crypto.raw_verify(bytes.fromhex(public.split(":")[1]), message, theirs)


# --------------------------------------------------------------------------- #
# versions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("version", "range_text", "expected"),
    [
        ("1.2.3", "*", True),
        ("1.2.3", "1.2.3", True),
        ("1.2.3", "=1.2.3", True),
        ("1.2.4", "=1.2.3", False),
        ("1.9.0", "^1.0.0", True),
        ("2.0.0", "^1.0.0", False),
        ("0.2.5", "^0.2.0", True),
        ("0.3.0", "^0.2.0", False),
        ("1.2.9", "~1.2.0", True),
        ("1.3.0", "~1.2.0", False),
        ("1.0.0", ">=1.0.0", True),
        ("0.9.9", ">=1.0.0", False),
        ("1.0.0", "<1.0.0", False),
        ("1.0.0-rc1", "*", False),
        ("1.0.0-rc1", ">=1.0.0", False),
        ("1.0.0-rc2", ">=1.0.0-rc1", True),
    ],
)
def test_satisfies(version, range_text, expected):
    assert versions.satisfies(version, range_text) is expected


def test_prerelease_precedence():
    """Precedence follows semver 11.4, not intuition.

    An earlier draft of this test asserted ``rc2 < rc10``. That is WRONG per the spec: an
    identifier containing letters is compared lexically in ASCII order, so ``rc2 > rc10``. The
    numeric comparison people expect requires a DOT-separated numeric identifier (``rc.2`` vs
    ``rc.10``), which is asserted below. The implementation was right and the expectation was
    the defect; recording it here so the surprising case is not "fixed" later.
    """
    assert versions.compare("1.0.0", "1.0.0-rc1") > 0, (
        "a release outranks its prerelease"
    )
    assert versions.compare("1.0.0-rc2", "1.0.0-rc10") > 0, (
        "alphanumeric identifiers compare lexically"
    )
    assert versions.compare("1.0.0-rc.2", "1.0.0-rc.10") < 0, (
        "numeric identifiers compare numerically"
    )
    assert versions.compare("1.0.0-alpha", "1.0.0-1") > 0, (
        "numeric ranks below alphanumeric"
    )
    assert versions.compare("1.0.0+build1", "1.0.0+build2") == 0, (
        "build metadata is ignored"
    )


def test_unknown_range_grammar_raises_rather_than_admitting():
    with pytest.raises(versions.VersionError):
        versions.satisfies("1.0.0", ">=1.0.0 <2.0.0")
    with pytest.raises(versions.VersionError):
        versions.satisfies("1.0.0", "latest")


def test_best_picks_the_highest_match():
    assert versions.best(["1.0.0", "1.4.2", "1.4.10", "2.0.0"], "^1.0.0") == "1.4.10"
    assert versions.best(["2.0.0"], "^1.0.0") is None


# --------------------------------------------------------------------------- #
# permissions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("grant", "want", "expected"),
    [
        ("fs:read:a/**", "fs:read:a/b/c.txt", True),
        # `a/**` means ONE OR MORE trailing segments, so it does NOT cover bare `a`. An earlier
        # draft of this test expected True. The narrower reading is both the documented grammar
        # (common.schema.json permission) and the safe direction: a grant that quietly widened to
        # include its own parent would be the silent-widening defect this build refuses.
        ("fs:read:a/**", "fs:read:a", False),
        ("fs:read:a/*", "fs:read:a/b", True),
        ("fs:read:a/*", "fs:read:a/b/c", False),
        ("fs:read:a/b", "fs:read:a/b", True),
        ("fs:read:a/b", "fs:read:a/c", False),
        ("fs:read:**", "fs:write:x", False),
        ("fs:read:a/**", "fs:read:b/c", False),
    ],
)
def test_subsumption(grant, want, expected):
    assert permissions.subsumes(grant, want) is expected


def test_permission_grammar_is_closed():
    with pytest.raises(permissions.PermissionError_):
        permissions.parse("kernel:load:*")
    with pytest.raises(permissions.PermissionError_):
        permissions.parse("fs:read")


def test_excessive_dangerous_permission_needs_an_exact_grant():
    ceiling = ["secrets:read:**"]
    wide = permissions.evaluate(["secrets:read:**"], max_permissions=ceiling)
    assert wide.admissible, "an EXACT explicit grant is honoured"
    via_wildcard = permissions.evaluate(
        ["secrets:read:vault/token"], max_permissions=["secrets:read:**"]
    )
    assert via_wildcard.admissible
    universal_without_exact = permissions.evaluate(
        ["exec:process:**"], max_permissions=["exec:process:*"]
    )
    assert not universal_without_exact.admissible


def test_forbidden_cannot_be_re_enabled_by_a_publisher_grant():
    verdict = permissions.evaluate(
        ["secrets:read:vault/**"],
        max_permissions=["secrets:read:**"],
        grant_permissions=["secrets:read:vault/**"],
        forbidden_permissions=["secrets:read"],
    )
    assert not verdict.admissible
    assert "forbidden" in verdict.reasons["secrets:read:vault/**"]


def test_double_star_only_legal_as_last_segment():
    with pytest.raises(permissions.PermissionError_, match="last scope segment"):
        permissions.subsumes("fs:read:**/x", "fs:read:a/x")


def test_widest_reach_classification():
    assert permissions.widest_reach("fs:read:a/**") == "universal"
    assert permissions.widest_reach("fs:read:a/*") == "segment"
    assert permissions.widest_reach("fs:read:a/b") == "exact"


# --------------------------------------------------------------------------- #
# schemas
# --------------------------------------------------------------------------- #


def test_every_declared_schema_exists_and_compiles():
    """Assert the POSITIVE: N of N, not merely 'nothing raised'."""
    report = schemas.self_check()
    assert report["failures"] == []
    assert report["checked"] == report["declared"] == len(schemas.SCHEMA_NAMES)
    assert report["declared"] >= 19


def test_unknown_schema_name_raises_rather_than_defaulting():
    with pytest.raises(schemas.SchemaError, match="unknown marketplace schema"):
        schemas.load("not-a-schema")


def test_retrieval_refuses_a_non_local_uri():
    with pytest.raises(schemas.SchemaError, match="no network"):
        schemas._retrieve("https://example.invalid/evil.schema.json")


def test_cross_file_refs_resolve():
    """A manifest referencing common.schema.json must validate without any network retrieval."""
    errors = schemas.errors_for("package-manifest", {"schema_version": "9.9.9"})
    assert any("schema_version" in e for e in errors)


def test_relative_path_pattern_rejects_windows_and_traversal_shapes():
    validator = schemas.validator_for("common")
    defs = validator.schema["$defs"]["relative_path"]
    import jsonschema

    checker = jsonschema.Draft202012Validator(defs)
    for bad in ["/abs/path", "../up", "C:/win/path", "back\\slash", "with space.txt"]:
        assert list(checker.iter_errors(bad)), f"{bad!r} must be rejected"
    for good in ["a/b.txt", "README.md", "pkg/sub/mod.py"]:
        assert not list(checker.iter_errors(good)), f"{good!r} must be accepted"


def test_benchmark_evidence_cannot_record_a_control_that_did_not_fire():
    """`const: true` on `fired` -- the schema refuses to express evidence with a dead control."""
    doc = {
        "schema_version": "1.0.0",
        "name": "x-pkg",
        "version": "1.0.0",
        "measurements": [
            {
                "metric": "install",
                "unit": "ms",
                "value_milli": 12000,
                "samples": 3,
                "command": "mkt install x-pkg",
            }
        ],
        "environment": {
            "os": "win32",
            "python": "3.14",
            "captured_at": "2026-08-10T09:00:00Z",
        },
        "controls": {
            "control_known_good": {
                "description": "a valid package installs",
                "passed": True,
            },
            "control_known_broken": {
                "description": "a revoked package refuses",
                "fired": False,
            },
        },
    }
    assert schemas.errors_for("benchmark-evidence", doc), (
        "fired=False must be unrepresentable"
    )
    doc["controls"]["control_known_broken"]["fired"] = True
    assert schemas.errors_for("benchmark-evidence", doc) == []


def test_trust_policy_cannot_express_an_unsigned_install():
    doc = json.loads(json.dumps(_minimal_policy()))
    doc["on_missing"]["signature"] = "warn"
    assert schemas.errors_for("trust-policy", doc), (
        "signature: warn must be unrepresentable"
    )


def _minimal_policy() -> dict:
    return {
        "schema_version": "1.0.0",
        "policy_id": "pol:test",
        "registry_maintainer_keys": ["ed25519:" + "0" * 64],
        "trusted_publishers": [],
        "max_permissions": [],
        "license_policy": {"allowed_spdx": ["MIT"], "on_unknown": "refuse"},
        "thresholds": {"min_conformance_score": 0, "max_advisory_severity": "none"},
        "on_missing": {
            "revocation_list": "refuse",
            "advisory_list": "refuse",
            "sbom": "refuse",
            "signature": "refuse",
            "publisher": "refuse",
        },
    }
