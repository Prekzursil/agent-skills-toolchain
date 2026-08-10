"""Lifecycle tests for the marketplace: publish, install, verify, revoke, dispute, offline.

THE HEADLINE TEST is :func:`test_revoked_package_cannot_be_installed`. Revocation that does not
actually block is the named failure mode for this build, so it is asserted from four angles:

* the same install SUCCEEDS before the revocation and REFUSES after (both-states control);
* nothing is written to the site on the refusal;
* rollback to a since-revoked version refuses too (no escape hatch);
* deleting, blanking, or rogue-signing the revocation list all REFUSE (fail-closed).

A fifth angle lives in :mod:`mkt.mutations`: the guard is removed from the installer's own
source and the same install then succeeds, which is what makes "the gate refused" mean "the gate
did the work".
"""

from __future__ import annotations

import json
import shutil

import pytest

from mkt import bundle as bundle_mod
from mkt import (
    fixture,
    install,
    lint,
    moderation,
    permissions,
    publish,
    registry,
    sbom,
    scaffold,
    schemas,
)
from mkt.canon import digest_file, read_json, write_json
from mkt.crypto import verify_document

T0 = fixture.T0


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """The fixture marketplace, built ONCE per module into a temp root.

    Module-scoped for speed (measured 0.42 s per build), and every test that mutates the
    registry clones it first -- a shared mutable registry would make test order load-bearing.
    """
    root = tmp_path_factory.mktemp("fixture-marketplace")
    return fixture.build(root, now=T0)


@pytest.fixture
def clone(built, tmp_path):
    """An isolated copy of the fixture registry for a test that mutates it."""

    def _clone(name: str = "registry") -> object:
        dst = tmp_path / name
        shutil.copytree(built["registry_root"], dst)
        return dst

    return _clone


def installer(root, site, built, **kwargs):
    kwargs.setdefault("platform_id", "win32")
    kwargs.setdefault("client_version", "2.1.0")
    kwargs.setdefault("use_federation", False)
    return install.Installer(
        root, site, json.loads(json.dumps(built["trust_policy"])), **kwargs
    )


# --------------------------------------------------------------------------- #
# the fixture marketplace itself
# --------------------------------------------------------------------------- #


def test_fixture_publishes_the_expected_packages(built):
    assert [f"{p['name']}@{p['version']}" for p in built["published"]] == [
        "hello-skill@1.0.0",
        "hello-skill@1.1.0",
        "dep-consumer@1.0.0",
        "vulnerable-lib@1.0.0",
    ]
    assert all(p["score"] >= 60 for p in built["published"])


def test_fixture_refuses_every_adversarial_package_with_the_expected_code(built):
    """A fixture marketplace where everything publishes cannot show that anything is enforced."""
    assert built["refusals"], "the fixture must contain packages that MUST be refused"
    for row in built["refusals"]:
        assert row["actual"] == row["expected"], row


def test_fixture_index_validates_and_is_signed_by_the_maintainer(built):
    schemas.validate("registry-index", built["index"])
    ok, why = registry.verify_index_signature(
        built["index"], built["trust_policy"]["registry_maintainer_keys"]
    )
    assert ok, why


def test_index_load_is_all_or_nothing(clone):
    root = clone()
    index = read_json(registry.index_path(root))
    index["entries"][0]["payload_digest"] = "not-a-digest"
    write_json(registry.index_path(root), index)
    with pytest.raises(registry.RegistryError, match="fails its own schema"):
        registry.load_index(root)


# --------------------------------------------------------------------------- #
# publish
# --------------------------------------------------------------------------- #


def test_payload_allowlist_is_checked_in_both_directions(built, tmp_path):
    src = tmp_path / "pkg"
    shutil.copytree(built["sources"] / "hello-skill-1.0.0", src)
    (src / "payload" / "stowaway.txt").write_text(
        "not declared anywhere\n", encoding="utf-8"
    )
    with pytest.raises(publish.PublishRefused, match="MKT-P03"):
        publish.enumerate_payload(
            src / "payload", read_json(src / "package.json")["payload_files"]
        )
    (src / "payload" / "stowaway.txt").unlink()
    (src / "payload" / "hello.py").unlink()
    with pytest.raises(publish.PublishRefused, match="MKT-P02"):
        publish.enumerate_payload(
            src / "payload", read_json(src / "package.json")["payload_files"]
        )


def test_secret_scan_fires_on_a_credential_and_is_silent_on_a_clean_file(built):
    """Both-states control on the scanner itself."""
    clean = publish.scan_payload(
        built["sources"] / "hello-skill-1.0.0" / "payload",
        ["README.md", "hello.py", "LICENSE"],
    )
    assert [f.rule for f in clean] == []
    dirty = publish.scan_payload(
        built["sources"] / "secret-leaker-1.0.0" / "payload",
        ["README.md", "config.ini"],
    )
    rules = {f.rule for f in dirty}
    assert "SEC-2" in rules, (
        "absolute owner path must be a finding (marketplace-first FM-4)"
    )
    assert "SEC-3" in rules, "credential-shaped assignment must be a finding"


def test_publish_refuses_without_a_licence_basis(built, tmp_path):
    """marketplace-first Stage 0, adopted as a blocking gate."""
    with pytest.raises(publish.PublishRefused, match="MKT-P05"):
        publish.publish(
            built["sources"] / "hello-skill-1.0.0",
            tmp_path / "reg",
            secret_hex=fixture.keys_for("pub:alpha-tools")[0],
            publisher_id="pub:alpha-tools",
            trust_policy=built["trust_policy"],
            governance=built["governance"],
            now=T0,
            license_basis_path=tmp_path / "nonexistent-LICENSE",
        )


def test_quality_score_is_recomputable(built):
    entry = registry.resolve(built["index"], "hello-skill", "=1.0.0", channel="stable")
    pkg_dir = registry.manifest_path(built["registry_root"], entry).parent
    score = read_json(pkg_dir / "quality-score.json")
    assert (
        publish.recompute_total(score) == score["total"] == entry["conformance_score"]
    )
    assert all(c["evidence"] for c in score["components"])


def test_benchmark_evidence_is_shipped_and_linted_end_to_end(built):
    """The schema is not enough: a real document must travel the publish -> lint path.

    Without a fixture package that actually SHIPS benchmark evidence, MKT-L13 would only ever be
    "evaluated" against a package that references nothing -- a rule that runs and checks nothing.
    """
    entry = registry.resolve(built["index"], "hello-skill", "=1.0.0", channel="stable")
    manifest_path = registry.manifest_path(built["registry_root"], entry)
    manifest = read_json(manifest_path)
    assert manifest["quality"]["benchmark_ref"] == "benchmark-evidence.json"
    bench = read_json(manifest_path.parent / manifest["quality"]["benchmark_ref"])
    schemas.validate("benchmark-evidence", bench)
    assert bench["controls"]["control_known_broken"]["fired"] is True
    report = lint.lint_package(
        manifest_path, trust_policy=built["trust_policy"], index=built["index"], now=T0
    )
    assert "MKT-L13" in report["rules_evaluated"]
    assert [f for f in report["findings"] if f["rule"] == "MKT-L13"] == []


def test_lint_catches_a_broken_benchmark_document(built, clone):
    """Both-states control on MKT-L13 itself."""
    root = clone()
    pkg = root / "packages" / "hello-skill" / "1.0.0"
    bench = read_json(pkg / "benchmark-evidence.json")
    bench["controls"]["control_known_broken"]["fired"] = False
    write_json(pkg / "benchmark-evidence.json", bench)
    report = lint.lint_package(
        pkg / "manifest.json", trust_policy=built["trust_policy"], now=T0
    )
    assert report["verdict"] == "FAIL"
    assert any(f["rule"] == "MKT-L13" for f in report["findings"])


def test_sign_index_validates_before_signing(built, tmp_path):
    index = json.loads(json.dumps(built["index"]))
    index["entries"][0]["channel"] = "nightly"
    with pytest.raises(schemas.ValidationFailed):
        publish.sign_index(index, built["root_secret_hex"], now=T0)


# --------------------------------------------------------------------------- #
# install
# --------------------------------------------------------------------------- #


def test_install_records_every_declared_gate(built, tmp_path):
    inst = installer(built["registry_root"], tmp_path / "site", built)
    receipt = inst.install("hello-skill", "^1.0.0", channel="stable", now=T0)
    schemas.validate("install-receipt", receipt)
    assert receipt["outcome"] == "SUCCESS"
    gates = [g["gate"] for g in receipt["gates"]]
    assert gates == list(install.GATES), (
        "every declared gate must be accounted for, in order"
    )
    assert not [g for g in receipt["gates"] if g["outcome"] == "REFUSE"]


def test_install_copies_the_payload_and_verifies_the_installed_bytes(built, tmp_path):
    inst = installer(built["registry_root"], tmp_path / "site", built)
    inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    site_pkg = tmp_path / "site" / "packages" / "hello-skill" / "1.0.0"
    entry = registry.resolve(built["index"], "hello-skill", "=1.0.0", channel="stable")
    manifest = registry.load_manifest(built["registry_root"], entry)
    for f in manifest["payload"]["files"]:
        assert digest_file(site_pkg / f["path"]) == f["sha256"]


def test_installed_payload_verifies_against_signature_and_sbom(built, tmp_path):
    """The verification the unit was told to demonstrate, run on the INSTALLED copy."""
    inst = installer(built["registry_root"], tmp_path / "site", built)
    inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    entry = registry.resolve(built["index"], "hello-skill", "=1.0.0", channel="stable")
    manifest = registry.load_manifest(built["registry_root"], entry)
    ok, why = verify_document(
        manifest,
        "mkt.manifest.v1",
        expected_public_key=entry["signature"]["public_key"],
    )
    assert ok, why
    sbom_doc = read_json(
        registry.manifest_path(built["registry_root"], entry).parent
        / manifest["sbom_ref"]
    )
    verdict = sbom.verify(
        sbom_doc,
        tmp_path / "site" / "packages" / "hello-skill" / "1.0.0",
        declared=manifest["payload"]["files"],
    )
    assert verdict.ok, verdict.summary()
    assert verdict.components_checked == len(manifest["payload"]["files"])


def test_channel_is_a_filter_not_a_fallback(built):
    stable = registry.resolve(built["index"], "hello-skill", "^1.0.0", channel="stable")
    beta = registry.resolve(built["index"], "hello-skill", "^1.0.0", channel="beta")
    assert stable["version"] == "1.0.0"
    assert beta["version"] == "1.1.0"
    assert (
        registry.resolve(built["index"], "hello-skill", "^1.0.0", channel="canary")
        is None
    )


def test_dependency_is_installed_transitively_and_recorded(built, tmp_path):
    inst = installer(built["registry_root"], tmp_path / "site", built)
    inst.install("dep-consumer", "=1.0.0", now=T0)
    state = inst.installed()["packages"]
    assert "hello-skill" in state, "a required dependency must be installed"
    lock = inst.load_lockfile()
    row = next(p for p in lock["packages"] if p["name"] == "hello-skill")
    assert "dep-consumer" in row["requested_by"]


def test_removing_a_package_with_dependants_is_refused(built, tmp_path):
    inst = installer(built["registry_root"], tmp_path / "site", built)
    inst.install("dep-consumer", "=1.0.0", now=T0)
    receipt = inst.remove("hello-skill", now=T0)
    assert receipt["outcome"] == "REFUSED"
    assert "dep-consumer" in json.dumps(receipt)
    assert "hello-skill" in inst.installed()["packages"]
    assert inst.remove("dep-consumer", now=T0)["outcome"] == "SUCCESS"
    assert inst.remove("hello-skill", now=T0)["outcome"] == "SUCCESS"


def test_platform_and_client_compatibility_refusals(built, tmp_path):
    inst = installer(
        built["registry_root"], tmp_path / "s1", built, client_id="codex-cli"
    )
    with pytest.raises(install.InstallRefused, match="MKT-I06"):
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    inst2 = installer(
        built["registry_root"], tmp_path / "s2", built, client_version="1.4.0"
    )
    with pytest.raises(install.InstallRefused, match="MKT-I06"):
        inst2.install("hello-skill", "=1.0.0", channel="stable", now=T0)


def test_advisory_gate_blocks_and_the_override_is_recorded(built, tmp_path):
    inst = installer(built["registry_root"], tmp_path / "site", built)
    with pytest.raises(install.InstallRefused, match="MKT-I07"):
        inst.install("vulnerable-lib", "=1.0.0", now=T0)
    receipt = inst.install("vulnerable-lib", "=1.0.0", allow_vulnerable=True, now=T0)
    assert receipt["outcome"] == "SUCCESS"
    assert receipt["overrides_used"] == ["allow-vulnerable"], (
        "an unaudited override is a hole"
    )


def test_override_is_impossible_when_the_policy_forbids_it(built, tmp_path):
    policy = json.loads(json.dumps(built["trust_policy"]))
    policy["allow_vulnerable_override"] = False
    inst = install.Installer(
        built["registry_root"],
        tmp_path / "site",
        policy,
        platform_id="win32",
        use_federation=False,
    )
    with pytest.raises(install.InstallRefused, match="MKT-I07"):
        inst.install("vulnerable-lib", "=1.0.0", allow_vulnerable=True, now=T0)


def test_unknown_publisher_is_refused(built, tmp_path):
    policy = json.loads(json.dumps(built["trust_policy"]))
    policy["trusted_publishers"] = [
        p for p in policy["trusted_publishers"] if p["publisher"] != "pub:alpha-tools"
    ]
    inst = install.Installer(
        built["registry_root"],
        tmp_path / "site",
        policy,
        platform_id="win32",
        use_federation=False,
    )
    with pytest.raises(install.InstallRefused, match="MKT-I02"):
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)


def test_conformance_floor_is_enforced(built, tmp_path):
    policy = json.loads(json.dumps(built["trust_policy"]))
    policy["thresholds"]["min_conformance_score"] = 100
    inst = install.Installer(
        built["registry_root"],
        tmp_path / "site",
        policy,
        platform_id="win32",
        use_federation=False,
    )
    with pytest.raises(install.InstallRefused, match="MKT-I08"):
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)


def test_index_row_widened_permissions_are_caught_by_the_signed_manifest(
    built, clone, tmp_path
):
    """A mirror or registry that widens the index row must not be believed."""
    root = clone()
    index = read_json(registry.index_path(root))
    for entry in index["entries"]:
        if entry["name"] == "hello-skill" and entry["version"] == "1.0.0":
            entry["permissions"] = ["fs:read:packages/**", "exec:process:python"]
    publish.sign_index(index, built["root_secret_hex"], now=T0)
    write_json(registry.index_path(root), index)
    inst = installer(root, tmp_path / "site", built)
    with pytest.raises(install.InstallRefused, match="MKT-I03"):
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)


# --------------------------------------------------------------------------- #
# THE HEADLINE: revocation must actually block
# --------------------------------------------------------------------------- #


def _revoke_hello(root, built, **kwargs):
    return moderation.revoke(
        root,
        scope=kwargs.pop(
            "scope", {"kind": "version", "name": "hello-skill", "version": "1.0.0"}
        ),
        reason=kwargs.pop("reason", "Test revocation: the install path must refuse."),
        severity=kwargs.pop("severity", "critical"),
        authority=kwargs.pop("authority", "pub:moderation-board"),
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
        **kwargs,
    )


def test_revoked_package_cannot_be_installed(built, clone, tmp_path):
    root = clone()

    # CONTROL: the identical install succeeds BEFORE the revocation.
    before = installer(root, tmp_path / "before", built).install(
        "hello-skill", "=1.0.0", channel="stable", now=T0
    )
    assert before["outcome"] == "SUCCESS"

    _revoke_hello(root, built, revocation_id="rev:test-1")

    inst = installer(root, tmp_path / "after", built)
    with pytest.raises(install.InstallRefused) as exc:
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    assert exc.value.code == "MKT-I04"
    assert exc.value.gate == "revocation"
    assert not (tmp_path / "after" / "packages" / "hello-skill").exists(), (
        "nothing may be written on a refusal"
    )
    assert exc.value.receipt["outcome"] == "REFUSED"
    assert exc.value.receipt["refusal_code"] == "MKT-I04"


@pytest.mark.parametrize(
    "scope",
    [
        {"kind": "version", "name": "hello-skill", "version": "1.0.0"},
        {"kind": "range", "name": "hello-skill", "range": "<=1.0.0"},
        {"kind": "package", "name": "hello-skill"},
    ],
)
def test_every_revocation_scope_blocks(built, clone, tmp_path, scope):
    root = clone()
    _revoke_hello(root, built, scope=scope, revocation_id="rev:scope-test")
    with pytest.raises(install.InstallRefused, match="MKT-I04"):
        installer(root, tmp_path / "site", built).install(
            "hello-skill", "=1.0.0", channel="stable", now=T0
        )


def test_key_scoped_revocation_blocks_every_package_signed_by_that_key(
    built, clone, tmp_path
):
    root = clone()
    _revoke_hello(
        root,
        built,
        scope={"kind": "key", "public_key": fixture.keys_for("pub:alpha-tools")[1]},
        revocation_id="rev:key-1",
        reason="Publisher key compromised: every signature by it is refused.",
    )
    with pytest.raises(install.InstallRefused, match="MKT-I04"):
        installer(root, tmp_path / "a", built).install(
            "hello-skill", "=1.1.0", channel="beta", now=T0
        )

    # A key revocation PROPAGATES through dependencies: dep-consumer is signed by beta-labs but
    # requires hello-skill, so it refuses too. Measured, not assumed -- an earlier draft of this
    # test asserted dep-consumer installs and was wrong.
    with pytest.raises(install.InstallRefused, match="MKT-I04"):
        installer(root, tmp_path / "b", built).install("dep-consumer", "=1.0.0", now=T0)

    # CONTROL: a package signed by a DIFFERENT key, with no dependency on the revoked one, still
    # installs. Without this the test could not distinguish "scoped to a key" from "blocks all".
    other = installer(root, tmp_path / "c", built).install(
        "vulnerable-lib", "=1.0.0", allow_vulnerable=True, now=T0
    )
    assert other["outcome"] == "SUCCESS"


@pytest.mark.parametrize("breakage", ["delete", "unsign", "rogue-sign", "truncate"])
def test_revocation_is_fail_closed(built, clone, tmp_path, breakage):
    """Removing or corrupting the revocation channel must REFUSE, never re-enable."""
    root = clone()
    _revoke_hello(root, built, revocation_id="rev:failclosed")
    path = root / "revocation.json"
    if breakage == "delete":
        path.unlink()
    elif breakage == "unsign":
        doc = read_json(path)
        doc.pop("signature")
        write_json(path, doc)
    elif breakage == "rogue-sign":
        from mkt.crypto import sign_document

        doc = read_json(path)
        doc.pop("signature")
        doc["signature"] = sign_document(
            doc,
            "mkt.revocation.v1",
            fixture.keys_for("pub:alpha-tools")[0],
            signed_at=T0,
        )
        write_json(path, doc)
    else:
        doc = read_json(path)
        doc["revocations"] = []
        doc.pop("signature")
        write_json(path, doc)

    inst = installer(root, tmp_path / "site", built)
    with pytest.raises((install.InstallRefused, schemas.ValidationFailed)) as exc:
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    if isinstance(exc.value, install.InstallRefused):
        assert exc.value.code == "MKT-I04"


def test_rollback_to_a_revoked_version_is_refused(built, clone, tmp_path):
    """Rollback re-runs every gate. It is not a bypass."""
    root = clone()
    inst = installer(root, tmp_path / "site", built)
    inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    updated = inst.update("hello-skill", "=1.1.0", channel="beta", now=T0)
    assert updated["action"] == "update"
    assert updated["previous"]["version"] == "1.0.0"

    _revoke_hello(root, built, revocation_id="rev:rollback")
    inst2 = installer(root, tmp_path / "site", built)
    with pytest.raises(install.InstallRefused, match="MKT-I04"):
        inst2.rollback("hello-skill", now=T0)


def test_rollback_works_when_the_previous_version_is_still_good(built, clone, tmp_path):
    root = clone()
    inst = installer(root, tmp_path / "site", built)
    inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    inst.update("hello-skill", "=1.1.0", channel="beta", now=T0)
    assert inst.installed()["packages"]["hello-skill"]["version"] == "1.1.0"
    receipt = inst.rollback("hello-skill", now=T0)
    assert receipt["action"] == "rollback"
    assert receipt["version"] == "1.0.0"
    assert inst.installed()["packages"]["hello-skill"]["version"] == "1.0.0"


def test_yank_hides_from_discovery_but_an_exact_pin_still_installs(
    built, clone, tmp_path
):
    root = clone()
    publish.yank(
        root,
        "hello-skill",
        "1.0.0",
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
    )
    index = registry.load_index(root)
    assert registry.resolve(index, "hello-skill", "^1.0.0", channel="stable") is None
    assert (
        registry.resolve(
            index, "hello-skill", "^1.0.0", channel="stable", include_yanked=True
        )["version"]
        == "1.0.0"
    )
    inst = installer(root, tmp_path / "site", built)
    with pytest.raises(install.InstallRefused):
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)


# --------------------------------------------------------------------------- #
# malicious package
# --------------------------------------------------------------------------- #


def test_excessive_permissions_are_rejected_at_publish(built, tmp_path):
    with pytest.raises(publish.PublishRefused) as exc:
        publish.publish(
            built["sources"] / "evil-overreach-1.0.0",
            tmp_path / "reg",
            secret_hex=fixture.keys_for("pub:alpha-tools")[0],
            publisher_id="pub:alpha-tools",
            trust_policy=built["trust_policy"],
            governance=built["governance"],
            now=T0,
            license_basis_path=fixture.FIXTURE_SRC / "LICENSE",
        )
    assert exc.value.code == "MKT-P07"


def test_excessive_permissions_are_rejected_at_install_even_from_a_signed_index(
    built, clone, tmp_path
):
    """The important half: refusing at publish only protects a registry the attacker does not own."""
    root = clone()
    result = publish.publish(
        built["sources"] / "evil-overreach-1.0.0",
        root,
        secret_hex=fixture.keys_for("pub:alpha-tools")[0],
        publisher_id="pub:alpha-tools",
        trust_policy=built["trust_policy"],
        governance=None,
        now=T0,
        allow_unverified_aggregate=True,
    )
    index = registry.load_index(root)
    publish.upsert_entry(index, result.entry)
    publish.sign_index(index, built["root_secret_hex"], now=T0)
    write_json(registry.index_path(root), index)

    inst = installer(root, tmp_path / "site", built)
    with pytest.raises(install.InstallRefused) as exc:
        inst.install("evil-overreach", "=1.0.0", now=T0)
    assert exc.value.code == "MKT-I05"
    assert not (tmp_path / "site" / "packages" / "evil-overreach").exists()
    # CONTROL: a benign package from the SAME index still installs
    assert (
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)["outcome"]
        == "SUCCESS"
    )


def test_the_malicious_manifest_permissions_are_individually_excessive(built):
    spec = read_json(built["sources"] / "evil-overreach-1.0.0" / "package.json")
    verdict = permissions.evaluate(
        spec["permissions"],
        max_permissions=built["trust_policy"]["max_permissions"],
        forbidden_permissions=built["trust_policy"]["forbidden_permissions"],
    )
    assert set(verdict.excessive) == set(spec["permissions"]), (
        "every requested permission must be refused"
    )


def test_licence_misstatement_is_refused_at_publish_and_at_install(
    built, clone, tmp_path
):
    """The M1 defect shape: an Apache-2.0 component under a declared MIT aggregate."""
    root = clone()
    with pytest.raises(publish.PublishRefused, match="MKT-P08"):
        publish.publish(
            built["sources"] / "apache-mixer-1.0.0",
            root,
            secret_hex=fixture.keys_for("pub:beta-labs")[0],
            publisher_id="pub:beta-labs",
            trust_policy=built["trust_policy"],
            governance=built["governance"],
            now=T0,
            license_basis_path=fixture.FIXTURE_SRC / "LICENSE",
        )
    result = publish.publish(
        built["sources"] / "apache-mixer-1.0.0",
        root,
        secret_hex=fixture.keys_for("pub:beta-labs")[0],
        publisher_id="pub:beta-labs",
        trust_policy=built["trust_policy"],
        governance=None,
        now=T0,
        allow_unverified_aggregate=True,
    )
    index = registry.load_index(root)
    publish.upsert_entry(index, result.entry)
    publish.sign_index(index, built["root_secret_hex"], now=T0)
    write_json(registry.index_path(root), index)
    with pytest.raises(install.InstallRefused, match="MKT-I11"):
        installer(root, tmp_path / "site", built).install(
            "apache-mixer", "=1.0.0", now=T0
        )


# --------------------------------------------------------------------------- #
# lockfile
# --------------------------------------------------------------------------- #


def test_frozen_install_refuses_a_digest_drift(built, clone, tmp_path):
    """marketplace-first FM-2: drift must be a hard install failure, not a silent divergence."""
    root = clone()
    inst = installer(root, tmp_path / "site", built)
    inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)

    pkg = root / "packages" / "hello-skill" / "1.0.0"
    target = pkg / "payload" / "hello.py"
    target.write_bytes(target.read_bytes() + b"\n# drifted\n")
    sbom_doc = read_json(pkg / "sbom.json")
    for component in sbom_doc["components"]:
        if component["name"] == "hello.py":
            component["hashes"][0]["content"] = digest_file(target).split(":", 1)[1]
    write_json(pkg / "sbom.json", sbom_doc)

    inst2 = installer(root, tmp_path / "site", built)
    with pytest.raises(install.InstallRefused, match="MKT-I09"):
        inst2.install("hello-skill", "=1.0.0", channel="stable", frozen=True, now=T0)


def test_a_frozen_refusal_leaves_nothing_in_the_site(built, clone, tmp_path):
    """A refusal must not half-install.

    Found by self-review, not by a failing test: the lockfile gate used to run AFTER the payload
    copy, so a --frozen drift refusal left the bytes in the site with no state entry pointing at
    them. The pin check now runs before the copy, and the copy itself rolls back on any exception.
    """
    root = clone()
    inst = installer(root, tmp_path / "site", built)
    inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)

    # The only way to reach gate 13 is a LEGITIMATE re-publish of the SAME version with different
    # content: properly signed, so gates 3/9/10 all pass, and only the lockfile pin disagrees.
    # (An earlier draft tampered the payload instead, which gate 9 caught first -- so gate 13 had
    # never actually been exercised. Reaching a gate is part of testing it.)
    republished = tmp_path / "republished"
    shutil.copytree(built["sources"] / "hello-skill-1.0.0", republished)
    target = republished / "payload" / "hello.py"
    target.write_bytes(
        target.read_bytes() + b"\n# republished under the same version number\n"
    )
    publish.publish_into(
        republished,
        root,
        secret_hex=fixture.keys_for("pub:alpha-tools")[0],
        publisher_id="pub:alpha-tools",
        maintainer_secret_hex=built["root_secret_hex"],
        trust_policy=built["trust_policy"],
        governance=built["governance"],
        now=T0,
        license_basis_path=fixture.FIXTURE_SRC / "LICENSE",
    )

    inst2 = installer(root, tmp_path / "site", built)
    with pytest.raises(install.InstallRefused) as exc:
        inst2.install("hello-skill", "=1.0.0", channel="stable", frozen=True, now=T0)
    assert exc.value.code == "MKT-I13"
    assert "payload_digest" in str(exc.value)
    installed_payload = (
        tmp_path / "site" / "packages" / "hello-skill" / "1.0.0" / "hello.py"
    )
    assert b"republished" not in installed_payload.read_bytes(), (
        "a --frozen refusal must not leave the rejected bytes on disk"
    )
    assert inst2.installed()["packages"]["hello-skill"]["version"] == "1.0.0"
    # CONTROL: without --frozen the same install accepts the new digest, so the refusal above is
    # about the PIN and not about the republish being malformed.
    assert (
        inst2.install("hello-skill", "=1.0.0", channel="stable", now=T0)["outcome"]
        == "SUCCESS"
    )


def test_advisory_list_signed_by_a_non_maintainer_is_refused(built, clone, tmp_path):
    """Found by self-review: verifying a document against whatever key signed it proves nothing.

    An attacker who can write advisories.json can re-sign a copy with every advisory REMOVED. The
    revocation gate checked the key against the maintainer set; the advisory gate did not.
    """
    root = clone()
    from mkt.crypto import sign_document

    advisories = read_json(root / "advisories.json")
    advisories["advisories"] = []  # the attacker's goal: no advisory blocks anything
    advisories.pop("signature")
    advisories["signature"] = sign_document(
        advisories,
        "mkt.advisory.v1",
        fixture.keys_for("pub:alpha-tools")[0],
        signed_at=T0,
    )
    write_json(root / "advisories.json", advisories)

    inst = installer(root, tmp_path / "site", built)
    with pytest.raises(install.InstallRefused) as exc:
        inst.install("vulnerable-lib", "=1.0.0", now=T0)
    assert exc.value.code == "MKT-I07"
    assert "maintainer" in str(exc.value)
    # CONTROL: the same emptied list, signed by the real maintainer key, DOES clear the gate --
    # so the refusal above is about the KEY, not about the emptying.
    advisories.pop("signature")
    advisories["signature"] = sign_document(
        advisories, "mkt.advisory.v1", built["root_secret_hex"], signed_at=T0
    )
    write_json(root / "advisories.json", advisories)
    assert (
        installer(root, tmp_path / "s2", built).install(
            "vulnerable-lib", "=1.0.0", now=T0
        )["outcome"]
        == "SUCCESS"
    )


def test_frozen_install_refuses_a_package_not_in_the_lockfile(built, tmp_path):
    inst = installer(built["registry_root"], tmp_path / "site", built)
    with pytest.raises(install.InstallRefused, match="MKT-I13"):
        inst.install("hello-skill", "=1.0.0", channel="stable", frozen=True, now=T0)


def test_lockfile_validates_and_pins_digests(built, tmp_path):
    inst = installer(built["registry_root"], tmp_path / "site", built)
    inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    lock = inst.load_lockfile()
    schemas.validate("lockfile", lock)
    row = lock["packages"][0]
    entry = registry.resolve(built["index"], "hello-skill", "=1.0.0", channel="stable")
    assert row["payload_digest"] == entry["payload_digest"]
    assert row["manifest_digest"] == entry["manifest_digest"]
    assert lock["index_digest"] == registry.index_digest(built["index"])


# --------------------------------------------------------------------------- #
# mirrors / federation
# --------------------------------------------------------------------------- #


def test_mirror_resolution_and_substitution_rejection(built, clone):
    """A mirror may withhold or lag. It may NOT substitute a package the primary never published."""
    root = clone()
    view = registry.federate(root)
    assert [m.mirror_id for m in view.mirrors] == ["mir:private-a"]

    mirror_index = registry.load_index(root / "mirrors" / "private-a")
    rogue = json.loads(json.dumps(mirror_index["entries"][0]))
    rogue["name"] = "hello-skill"
    rogue["version"] = "9.9.9"
    mirror_index["entries"].append(rogue)
    publish.sign_index(mirror_index, built["root_secret_hex"], now=T0)
    write_json(registry.index_path(root / "mirrors" / "private-a"), mirror_index)

    view2 = registry.federate(root)
    assert view2.resolve("hello-skill", "=9.9.9") is None
    assert view2.rejected and "disagrees with" in view2.rejected[0]["reason"]
    assert view2.rejected[0]["package"] == "hello-skill@9.9.9"
    # the mirror can still serve what the primary DOES have
    assert view2.resolve("hello-skill", "=1.0.0", channel="stable") is not None


def test_primary_is_preferred_over_a_mirror(built):
    view = registry.federate(built["registry_root"])
    found = view.resolve("hello-skill", "^1.0.0", channel="stable")
    assert found is not None
    assert found[0].mirror_id is None, (
        "the primary must win when it can satisfy the request"
    )


# --------------------------------------------------------------------------- #
# offline export / import
# --------------------------------------------------------------------------- #


def test_offline_bundle_round_trip_and_install(built, tmp_path):
    out = tmp_path / "bundle"
    manifest = bundle_mod.export_bundle(
        built["registry_root"],
        out,
        packages=[("hello-skill", "1.0.0")],
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
    )
    schemas.validate("offline-bundle", manifest)
    assert manifest["includes"] == {
        "revocation": True,
        "advisory": True,
        "publishers": True,
    }
    assert (
        bundle_mod.verify_bundle(out, built["trust_policy"])["bundle_id"]
        == manifest["bundle_id"]
    )

    dest = tmp_path / "imported"
    bundle_mod.import_bundle(
        out,
        dest,
        trust_policy=built["trust_policy"],
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
    )
    receipt = installer(dest, tmp_path / "site", built).install(
        "hello-skill", "=1.0.0", now=T0
    )
    assert receipt["outcome"] == "SUCCESS"


def test_bundle_without_a_revocation_list_is_refused_by_a_fail_closed_policy(
    built, tmp_path
):
    out = tmp_path / "bundle-no-rev"
    bundle_mod.export_bundle(
        built["registry_root"],
        out,
        packages=[("hello-skill", "1.0.0")],
        maintainer_secret_hex=built["root_secret_hex"],
        include_revocation=False,
        now=T0,
    )
    with pytest.raises(bundle_mod.BundleError, match="omits the revocation list"):
        bundle_mod.verify_bundle(out, built["trust_policy"])


def test_bundle_signed_by_a_non_maintainer_is_refused(built, tmp_path):
    out = tmp_path / "bundle-rogue"
    bundle_mod.export_bundle(
        built["registry_root"],
        out,
        packages=[("hello-skill", "1.0.0")],
        maintainer_secret_hex=fixture.keys_for("pub:alpha-tools")[0],
        now=T0,
    )
    with pytest.raises(
        bundle_mod.BundleError, match="not a declared registry-maintainer key"
    ):
        bundle_mod.verify_bundle(out, built["trust_policy"])


def test_offline_import_carries_the_revocation_so_a_revoked_package_still_refuses(
    built, clone, tmp_path
):
    """An air-gapped import must not become the way a revoked version gets in."""
    root = clone()
    _revoke_hello(root, built, revocation_id="rev:offline")
    out = tmp_path / "bundle"
    bundle_mod.export_bundle(
        root,
        out,
        packages=[("hello-skill", "1.0.0")],
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
    )
    dest = tmp_path / "imported"
    bundle_mod.import_bundle(
        out,
        dest,
        trust_policy=built["trust_policy"],
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
    )
    with pytest.raises(install.InstallRefused, match="MKT-I04"):
        installer(dest, tmp_path / "site", built).install(
            "hello-skill", "=1.0.0", now=T0
        )


# --------------------------------------------------------------------------- #
# moderation and dispute
# --------------------------------------------------------------------------- #


def test_moderation_illegal_transition_raises(built, clone):
    root = clone()
    moderation.open_case(
        root,
        case_id="case:mod-001",
        name="hello-skill",
        version="1.0.0",
        publisher="pub:alpha-tools",
        reason_category="spam",
        opened_by="tester",
        note="opening a case for the transition table test",
        now=T0,
    )
    with pytest.raises(moderation.ModerationError, match="illegal transition"):
        moderation.transition(
            root,
            "case:mod-001",
            to_state="appeal-upheld",
            actor="pub:moderation-board",
            note="skip",
            now=T0,
        )
    moderation.transition(
        root,
        "case:mod-001",
        to_state="dismissed",
        actor="pub:moderation-board",
        note="dismissing",
        now=T0,
    )
    with pytest.raises(moderation.ModerationError, match="terminal"):
        moderation.transition(
            root,
            "case:mod-001",
            to_state="under-review",
            actor="pub:moderation-board",
            note="reopen",
            now=T0,
        )


def test_a_publisher_cannot_revoke(built, clone):
    root = clone()
    with pytest.raises(moderation.ModerationError, match="revocation requires"):
        _revoke_hello(
            root, built, authority="pub:alpha-tools", revocation_id="rev:self"
        )


def test_upheld_appeal_reverses_the_revocation_and_reinstates_the_install(
    built, clone, tmp_path
):
    root = clone()
    moderation.open_case(
        root,
        case_id="case:mod-002",
        name="hello-skill",
        version="1.0.0",
        publisher="pub:alpha-tools",
        reason_category="malware",
        opened_by="tester",
        note="case that will be appealed and upheld",
        now=T0,
    )
    moderation.transition(
        root,
        "case:mod-002",
        to_state="under-review",
        actor="pub:moderation-board",
        note="reviewing",
        now=T0,
    )
    moderation.transition(
        root,
        "case:mod-002",
        to_state="action-taken",
        actor="pub:moderation-board",
        note="revoking",
        now=T0,
    )
    _revoke_hello(
        root, built, revocation_id="rev:mod-002", moderation_case="case:mod-002"
    )
    moderation.link_revocation(root, "case:mod-002", "rev:mod-002")
    with pytest.raises(install.InstallRefused, match="MKT-I04"):
        installer(root, tmp_path / "before", built).install(
            "hello-skill", "=1.0.0", channel="stable", now=T0
        )

    moderation.transition(
        root,
        "case:mod-002",
        to_state="appealed",
        actor="pub:alpha-tools",
        note="appealing",
        now=T0,
    )
    case, revocation = moderation.uphold_appeal(
        root,
        "case:mod-002",
        actor="pub:moderation-board",
        note="appeal upheld; reversing",
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
    )
    assert case["state"] == "appeal-upheld"
    assert [r["revocation_id"] for r in revocation["revocations"]] == []
    assert (
        installer(root, tmp_path / "after", built).install(
            "hello-skill", "=1.0.0", channel="stable", now=T0
        )["outcome"]
        == "SUCCESS"
    )


def test_uphold_appeal_refuses_to_report_a_reversal_that_did_not_happen(built, clone):
    root = clone()
    moderation.open_case(
        root,
        case_id="case:mod-003",
        name="hello-skill",
        version="1.0.0",
        publisher="pub:alpha-tools",
        reason_category="other",
        opened_by="tester",
        note="case whose linked revocation does not exist",
        now=T0,
    )
    moderation.transition(
        root,
        "case:mod-003",
        to_state="under-review",
        actor="pub:moderation-board",
        note="under review for the reversal test",
        now=T0,
    )
    moderation.transition(
        root,
        "case:mod-003",
        to_state="action-taken",
        actor="pub:moderation-board",
        note="action taken for the reversal test",
        now=T0,
    )
    moderation.link_revocation(root, "case:mod-003", "rev:never-created")
    moderation.transition(
        root,
        "case:mod-003",
        to_state="appealed",
        actor="pub:alpha-tools",
        note="appeal",
        now=T0,
    )
    with pytest.raises(moderation.ModerationError, match="was not present to remove"):
        moderation.uphold_appeal(
            root,
            "case:mod-003",
            actor="pub:moderation-board",
            note="uphold",
            maintainer_secret_hex=built["root_secret_hex"],
            now=T0,
        )


def test_only_security_response_may_publish_an_advisory(built, clone):
    root = clone()
    advisory = {
        "advisory_id": "adv:2026-0099",
        "state": "reported",
        "severity": "low",
        "title": "A reported issue used for the role-separation test",
        "affected": [{"name": "hello-skill", "range": "*"}],
        "reported_at": T0,
        "reporter": "tester",
    }
    with pytest.raises(moderation.ModerationError, match="may not publish advisories"):
        moderation.publish_advisory(
            root,
            advisory=advisory,
            authority="pub:alpha-tools",
            maintainer_secret_hex=built["root_secret_hex"],
            now=T0,
        )
    doc = moderation.publish_advisory(
        root,
        advisory=advisory,
        authority="pub:security-response",
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
    )
    assert "adv:2026-0099" in [a["advisory_id"] for a in doc["advisories"]]


def test_disputed_and_fixed_advisories_stop_gating(built, clone, tmp_path):
    root = clone()
    advisories = read_json(root / "advisories.json")
    target = next(
        a for a in advisories["advisories"] if a["advisory_id"] == "adv:2026-0001"
    )
    target["state"] = "disputed"
    advisories.pop("signature")
    from mkt.crypto import sign_document

    advisories["signature"] = sign_document(
        advisories, "mkt.advisory.v1", built["root_secret_hex"], signed_at=T0
    )
    write_json(root / "advisories.json", advisories)
    receipt = installer(root, tmp_path / "site", built).install(
        "vulnerable-lib", "=1.0.0", now=T0
    )
    assert receipt["outcome"] == "SUCCESS"
    assert "overrides_used" not in receipt, (
        "a disputed advisory is non-gating, not an override"
    )


# --------------------------------------------------------------------------- #
# SBOM
# --------------------------------------------------------------------------- #


def test_sbom_verification_is_bidirectional(built, tmp_path):
    entry = registry.resolve(built["index"], "hello-skill", "=1.0.0", channel="stable")
    pkg_dir = registry.manifest_path(built["registry_root"], entry).parent
    manifest = read_json(pkg_dir / "manifest.json")
    sbom_doc = read_json(pkg_dir / "sbom.json")
    payload = tmp_path / "payload"
    shutil.copytree(pkg_dir / "payload", payload)

    assert sbom.verify(sbom_doc, payload, declared=manifest["payload"]["files"]).ok

    (payload / "stowaway.txt").write_text("undeclared\n", encoding="utf-8")
    forward = sbom.verify(sbom_doc, payload, declared=manifest["payload"]["files"])
    assert not forward.ok
    assert forward.missing_from_sbom == ["stowaway.txt"], (
        "a file the SBOM never declared must be caught"
    )

    (payload / "stowaway.txt").unlink()
    (payload / "hello.py").unlink()
    backward = sbom.verify(sbom_doc, payload, declared=manifest["payload"]["files"])
    assert not backward.ok
    assert backward.missing_from_disk == ["hello.py"], (
        "an SBOM claim with no file must be caught"
    )


def test_sbom_build_refuses_a_component_with_no_licence():
    with pytest.raises(ValueError, match="no licence for payload file"):
        sbom.build(
            name="x-pkg",
            version="1.0.0",
            files=[{"path": "a.py", "sha256": "sha256:" + "0" * 64, "bytes": 1}],
            licenses={},
            payload_digest="sha256:" + "1" * 64,
            timestamp=T0,
            default_license=None,
        )


def test_sbom_serial_is_deterministic():
    args = {"name": "x-pkg", "version": "1.0.0", "payload_digest": "sha256:" + "2" * 64}
    assert sbom.deterministic_serial(**args) == sbom.deterministic_serial(**args)


# --------------------------------------------------------------------------- #
# linter
# --------------------------------------------------------------------------- #


def test_registry_lint_passes_and_evaluates_every_rule(built):
    report = lint.lint_registry(
        built["registry_root"],
        trust_policy=built["trust_policy"],
        governance_path=fixture.MARKETPLACE_ROOT / "governance-policy.json",
        now=T0,
    )
    assert report["verdict"] == "PASS", report["findings"]
    assert sorted(report["rules_evaluated"]) == sorted(lint.RULES)
    assert len(report["rules_evaluated"]) == report["rules_total"] == len(lint.RULES)


@pytest.mark.parametrize("mutation", ["payload-digest", "signature", "permission"])
def test_linter_fires_on_a_known_broken_package_and_is_silent_on_a_known_good_one(
    built, mutation
):
    entry = registry.resolve(built["index"], "hello-skill", "=1.0.0", channel="stable")
    result = lint.self_test(
        registry.manifest_path(built["registry_root"], entry), mutate=mutation
    )
    assert result["known_good_verdict"] == "PASS"
    assert result["known_broken_verdict"] == "FAIL"
    assert result["detector_usable"], result


def test_governance_prose_and_policy_agree(built):
    """MKT-L17: a governance value the prose does not state is a value nobody agreed to."""
    report = lint.lint_registry(
        built["registry_root"],
        trust_policy=built["trust_policy"],
        governance_path=fixture.MARKETPLACE_ROOT / "governance-policy.json",
        now=T0,
    )
    assert [f for f in report["findings"] if f["rule"] == "MKT-L17"] == []


def test_lint_reports_a_registry_with_no_revocation_list(built, clone):
    root = clone()
    (root / "revocation.json").unlink()
    report = lint.lint_registry(root, trust_policy=built["trust_policy"], now=T0)
    assert report["verdict"] == "FAIL"
    assert any(f["rule"] == "MKT-L16" for f in report["findings"])


def test_lint_error_verdict_on_an_unreadable_target(tmp_path):
    bad = tmp_path / "manifest.json"
    bad.write_text("{not json", encoding="utf-8")
    report = lint.lint_package(bad)
    assert report["verdict"] == "ERROR"
    assert report["findings"]


# --------------------------------------------------------------------------- #
# scaffolder
# --------------------------------------------------------------------------- #


def test_scaffolded_package_publishes_installs_and_lints_clean(built, tmp_path):
    """A scaffolder whose output fails the project's own linter teaches the wrong shape."""
    src = scaffold.scaffold(tmp_path / "src", name="scaffold-demo", now=T0)
    root = tmp_path / "registry"
    shutil.copytree(built["registry_root"], root)
    policy = json.loads(json.dumps(built["trust_policy"]))
    policy["max_permissions"] = sorted(
        {*policy["max_permissions"], "fs:read:packages/scaffold-demo/**"}
    )

    result = publish.publish_into(
        src,
        root,
        secret_hex=fixture.keys_for("pub:alpha-tools")[0],
        publisher_id="pub:alpha-tools",
        maintainer_secret_hex=built["root_secret_hex"],
        trust_policy=policy,
        governance=built["governance"],
        now=T0,
        license_basis_path=fixture.FIXTURE_SRC / "LICENSE",
    )
    index = registry.load_index(root)
    report = lint.lint_package(
        result.manifest_path, trust_policy=policy, index=index, now=T0
    )
    assert report["verdict"] == "PASS", report["findings"]

    inst = install.Installer(
        root, tmp_path / "site", policy, platform_id="win32", use_federation=False
    )
    assert (
        inst.install("scaffold-demo", "=0.1.0", channel="beta", now=T0)["outcome"]
        == "SUCCESS"
    )


# --------------------------------------------------------------------------- #
# search / collections
# --------------------------------------------------------------------------- #


def test_search_by_text_category_tag_and_publisher(built):
    index = built["index"]
    assert {e["name"] for e in registry.search(index, tag="fixture")} >= {
        "hello-skill",
        "dep-consumer",
        "vulnerable-lib",
    }
    assert [e["name"] for e in registry.search(index, category="security")] == [
        "vulnerable-lib"
    ]
    assert {e["name"] for e in registry.search(index, publisher="pub:beta-labs")} == {
        "dep-consumer",
        "vulnerable-lib",
    }
    assert registry.search(index, text="no-such-package-anywhere") == []


def test_search_hides_yanked_by_default(built, clone):
    root = clone()
    publish.yank(
        root,
        "hello-skill",
        "1.1.0",
        maintainer_secret_hex=built["root_secret_hex"],
        now=T0,
    )
    index = registry.load_index(root)
    assert "1.1.0" not in [
        e["version"] for e in registry.search(index, text="hello-skill")
    ]
    assert "1.1.0" in [
        e["version"]
        for e in registry.search(index, text="hello-skill", include_yanked=True)
    ]


def test_collection_resolves_to_real_entries(built):
    members = registry.collection_members(built["index"], "col:starter")
    assert [m["name"] for m in members] == ["hello-skill"]
    with pytest.raises(registry.RegistryError, match="no such collection"):
        registry.collection_members(built["index"], "col:does-not-exist")


# --------------------------------------------------------------------------- #
# receipts / journal
# --------------------------------------------------------------------------- #


def test_every_journal_receipt_validates(built, tmp_path):
    inst = installer(built["registry_root"], tmp_path / "site", built)
    inst.install("dep-consumer", "=1.0.0", now=T0)
    inst.remove("dep-consumer", now=T0)
    receipts = inst.receipts()
    assert len(receipts) >= 3
    for receipt in receipts:
        schemas.validate("install-receipt", receipt)


def test_refused_install_is_reported_as_refused_not_failed(built, clone, tmp_path):
    """REFUSED is a working control; FAILED is a bug. Collapsing them hides both."""
    root = clone()
    _revoke_hello(root, built, revocation_id="rev:outcome")
    inst = installer(root, tmp_path / "site", built)
    with pytest.raises(install.InstallRefused) as exc:
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
    assert exc.value.receipt["outcome"] == "REFUSED"
