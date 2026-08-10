"""Tests for the health registry (with its both-states control), conformance, and migration.

The headline assertion is ``test_every_probe_with_a_break_discriminates``: it is the mechanised
form of "a probe that is silent in both states measures nothing". Any probe whose ``break_`` does
not flip it PASS -> FAIL is reported INVALID and fails this test, so a decorative probe cannot
inflate a green health check.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from plugin import health, migrate
from plugin.build import build
from plugin.conformance import NOT_CHECKED, SATISFIED, VIOLATED, validate_package
from plugin.errors import PluginError
from plugin.journal import Prefix
from plugin.lifecycle import install
from plugin.manifest import MANIFEST_RELPATH


@pytest.fixture
def live_prefix(tmp_path: Path, repo_root: Path) -> Prefix:
    result, _ = build(repo_root, tmp_path / "dist")
    prefix = Prefix(tmp_path / "prefix")
    install(result.archive, prefix, live_root=tmp_path / "prefix" / "live")
    return prefix


# --------------------------------------------------------------------------- health


def test_healthy_prefix_passes_every_probe(live_prefix: Prefix) -> None:
    report = health.health_check(live_prefix)
    assert report.ok, [r.as_dict() for r in report.failed]
    assert report.as_dict()["probe_count"] == len(health.REGISTRY)


def test_every_probe_with_a_break_discriminates(live_prefix: Prefix) -> None:
    rows = health.control(live_prefix)
    assert len(rows) == len(health.REGISTRY)
    invalid = [r for r in rows if r["verdict"] == "INVALID"]
    assert invalid == [], f"non-discriminating probe(s): {invalid}"
    declared = [r for r in rows if r["verdict"] == "VALID"]
    assert len(declared) >= 6, f"only {len(declared)} probes carry a working break_()"


def test_probes_without_a_break_are_recorded_not_checked(live_prefix: Prefix) -> None:
    rows = health.control(live_prefix)
    no_break = {p.ident for p in health.REGISTRY if p.break_ is None}
    for row in rows:
        if row["probe"] in no_break:
            assert row["verdict"] == "NOT-CHECKED"
            assert row["discriminates"] is None
    doc = health.probe_control_document(rows)
    assert doc["valid"] + doc["invalid"] + doc["not_checked"] == doc["probe_count"]


def test_control_restores_the_prefix_afterwards(live_prefix: Prefix) -> None:
    before = health.health_check(live_prefix).as_dict()
    health.control(live_prefix)
    after = health.health_check(live_prefix).as_dict()
    assert before["probes"] == after["probes"], (
        "the control harness left the prefix altered"
    )


def test_probe_that_raises_is_a_fail_not_a_pass(
    live_prefix: Prefix, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_p: Prefix) -> health.ProbeResult:
        raise RuntimeError("probe exploded")

    registry = tuple(
        health.Probe(
            p.ident,
            p.description,
            boom if p.ident == "prefix-layout" else p.run,
            p.remediation,
            p.break_,
        )
        for p in health.REGISTRY
    )
    monkeypatch.setattr(health, "REGISTRY", registry)
    report = health.health_check(live_prefix)
    assert not report.ok
    failed = {r.ident: r for r in report.failed}
    assert (
        "prefix-layout" in failed and "probe raised" in failed["prefix-layout"].detail
    )


def test_doctor_names_a_command_for_every_failure(live_prefix: Prefix) -> None:
    (live_prefix.root / "live" / "hooks" / "plugin_health.py").unlink()
    adv = health.doctor(live_prefix)
    assert adv["ok"] is False
    assert adv["actions"], "doctor reported a failure with no remediating action"
    for action in adv["actions"]:  # type: ignore[union-attr]
        assert action["run"].startswith("astplugin ")


def test_empty_registry_cannot_produce_a_green_report(
    live_prefix: Prefix, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A green health check over zero probes is a broken harness, and the schema forbids it."""
    import jsonschema
    from plugin.schemas import SCHEMAS

    monkeypatch.setattr(health, "REGISTRY", ())
    doc = health.health_check(live_prefix).as_dict()
    assert doc["ok"] is True and doc["probe_count"] == 0
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, SCHEMAS["health-report"])


# --------------------------------------------------------------------------- conformance


def test_real_package_satisfies_every_condition(built_package: Path) -> None:
    report = validate_package(built_package)
    assert report.ok, [c.as_dict() for c in report.violated + report.not_checked]
    assert report.satisfied == len(report.conditions) >= 16
    assert (
        report.as_dict()["verdict"]
        == f"{report.satisfied}/{len(report.conditions)} conditions satisfied"
    )


def test_missing_package_is_a_violation_not_a_crash(tmp_path: Path) -> None:
    report = validate_package(tmp_path / "absent.zip")
    assert not report.ok and report.conditions[0].status == VIOLATED


def test_non_archive_is_reported(tmp_path: Path) -> None:
    junk = tmp_path / "j.zip"
    junk.write_bytes(b"nope")
    report = validate_package(junk)
    assert not report.ok
    assert any(c.ident == "C01" and c.status == VIOLATED for c in report.conditions)


def test_forbidden_member_is_detected(built_package: Path, tmp_path: Path) -> None:
    tainted = tmp_path / "tainted.zip"
    with zipfile.ZipFile(built_package) as zin:
        members = {
            i.filename: zin.read(i.filename) for i in zin.infolist() if not i.is_dir()
        }
    members[".git/config"] = b"[core]\n"
    with zipfile.ZipFile(tainted, "w") as zout:
        for name in sorted(members):
            zout.writestr(name, members[name])
    report = validate_package(tainted)
    c06 = next(c for c in report.conditions if c.ident == "C06")
    assert c06.status == VIOLATED and "vcs" in c06.evidence
    assert not report.ok


def test_credentialish_member_is_detected(built_package: Path, tmp_path: Path) -> None:
    tainted = tmp_path / "creds.zip"
    with zipfile.ZipFile(built_package) as zin:
        members = {
            i.filename: zin.read(i.filename) for i in zin.infolist() if not i.is_dir()
        }
    members["README.md"] = b"TOKEN = 'ghp_" + b"d" * 40 + b"'\n"
    with zipfile.ZipFile(tainted, "w") as zout:
        for name in sorted(members):
            zout.writestr(name, members[name])
    report = validate_package(tainted)
    c14 = next(c for c in report.conditions if c.ident == "C14")
    assert c14.status == VIOLATED


def test_manifest_failure_marks_dependent_conditions_not_checked(
    built_package: Path, tmp_path: Path
) -> None:
    """A condition that could not be evaluated is NOT-CHECKED and counts against the total."""
    broken = tmp_path / "broken.zip"
    with zipfile.ZipFile(built_package) as zin:
        members = {
            i.filename: zin.read(i.filename) for i in zin.infolist() if not i.is_dir()
        }
    members[MANIFEST_RELPATH] = b'{"name": "x"}'
    with zipfile.ZipFile(broken, "w") as zout:
        for name in sorted(members):
            zout.writestr(name, members[name])
    report = validate_package(broken)
    assert not report.ok
    ids = {c.ident: c.status for c in report.conditions}
    assert ids["C05"] == VIOLATED
    assert ids["C09"] == NOT_CHECKED and ids["C12"] == NOT_CHECKED
    assert report.satisfied < len(report.conditions)


def test_crlf_member_is_a_violation(built_package: Path, tmp_path: Path) -> None:
    tainted = tmp_path / "crlf.zip"
    with zipfile.ZipFile(built_package) as zin:
        members = {
            i.filename: zin.read(i.filename) for i in zin.infolist() if not i.is_dir()
        }
    members["README.md"] = members["README.md"].replace(b"\n", b"\r\n")
    with zipfile.ZipFile(tainted, "w") as zout:
        for name in sorted(members):
            zout.writestr(name, members[name])
    c15 = next(c for c in validate_package(tainted).conditions if c.ident == "C15")
    assert c15.status == VIOLATED


def test_all_conditions_on_the_good_package_are_satisfied_not_merely_nonblocking(
    built_package: Path,
) -> None:
    report = validate_package(built_package)
    assert {c.status for c in report.conditions} == {SATISFIED}


# --------------------------------------------------------------------------- migration


def test_no_legacy_layout_is_a_no_op(tmp_path: Path) -> None:
    ledger = migrate.migrate(tmp_path, version="1.0.0")
    assert ledger["detected_layout"] == "none" and ledger["ok"] is True
    assert ledger["applied"] == []


def test_flat_v0_layout_migrates_and_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "plugin.json").write_text(
        '{"name":"x"}', encoding="utf-8", newline="\n"
    )
    (tmp_path / "commands").mkdir()
    (tmp_path / "commands" / "a.md").write_text("a\n", encoding="utf-8", newline="\n")
    assert migrate.detect_layout(tmp_path) == ["flat-v0"]
    ledger = migrate.migrate(tmp_path, version="1.0.0")
    assert ledger["ok"] and ledger["applied"]
    assert (tmp_path / "versions" / "1.0.0" / ".claude-plugin" / "plugin.json").exists()
    assert (tmp_path / "versions" / "1.0.0" / "commands" / "a.md").exists()
    assert migrate.detect_layout(tmp_path) == []
    again = migrate.migrate(tmp_path, version="1.0.0")
    assert again["detected_layout"] == "none"


def test_single_current_v1_layout_migrates(tmp_path: Path) -> None:
    cur = tmp_path / "current"
    cur.mkdir()
    (cur / "plugin.json").write_text('{"name":"x"}', encoding="utf-8", newline="\n")
    assert migrate.detect_layout(tmp_path) == ["single-current-v1"]
    migrate.migrate(tmp_path, version="2.0.0")
    assert (tmp_path / "versions" / "2.0.0" / ".claude-plugin" / "plugin.json").exists()
    assert not cur.exists()


def test_every_planned_step_declares_an_inverse(tmp_path: Path) -> None:
    (tmp_path / "plugin.json").write_text("{}", encoding="utf-8", newline="\n")
    plan = migrate.plan_migration(tmp_path, version="1.0.0")
    assert plan.steps
    for step in plan.steps:
        assert step.inverse_description.strip()
        assert callable(step.invert)


def test_steps_are_invertible_in_practice(tmp_path: Path) -> None:
    (tmp_path / "plugin.json").write_text(
        '{"name":"x"}', encoding="utf-8", newline="\n"
    )
    plan = migrate.plan_migration(tmp_path, version="1.0.0")
    for step in plan.steps:
        step.apply()
    assert (tmp_path / "versions" / "1.0.0" / ".claude-plugin" / "plugin.json").exists()
    for step in reversed(plan.steps):
        step.invert()
    assert (tmp_path / "plugin.json").exists(), (
        "inverting every step did not restore the old layout"
    )


def test_dry_run_migration_moves_nothing(tmp_path: Path) -> None:
    (tmp_path / "plugin.json").write_text("{}", encoding="utf-8", newline="\n")
    ledger = migrate.migrate(tmp_path, version="1.0.0", dry_run=True)
    assert ledger["dry_run"] is True and ledger["would_apply"]
    assert (tmp_path / "plugin.json").exists()
    assert not (tmp_path / "versions").exists()


def test_a_failing_step_rolls_the_migration_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "plugin.json").write_text(
        '{"name":"x"}', encoding="utf-8", newline="\n"
    )
    (tmp_path / "commands").mkdir()
    (tmp_path / "commands" / "a.md").write_text("a\n", encoding="utf-8", newline="\n")
    real_plan = migrate.plan_migration(tmp_path, version="1.0.0")

    def sabotaged(_root: Path, *, version: str) -> migrate.MigrationPlan:
        steps = list(real_plan.steps)
        steps.insert(
            1,
            migrate.MigrationStep(
                "explode",
                "a step that fails",
                lambda: (_ for _ in ()).throw(OSError("disk went away")),
                lambda: None,
                "nothing",
            ),
        )
        return migrate.MigrationPlan(layout=real_plan.layout, steps=steps)

    monkeypatch.setattr(migrate, "plan_migration", sabotaged)
    with pytest.raises(PluginError) as exc:
        migrate.migrate(tmp_path, version="1.0.0")
    assert exc.value.code == "E_MIGRATE"
    assert (tmp_path / "plugin.json").exists() or (
        tmp_path / "commands" / "a.md"
    ).exists(), "a failed migration left the tree half-moved"


def test_ambiguous_layout_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        migrate,
        "LEGACY_LAYOUTS",
        (
            migrate.LayoutFingerprint("a", "a", require=("plugin.json",)),
            migrate.LayoutFingerprint("b", "b", require=("plugin.json",)),
        ),
    )
    (tmp_path / "plugin.json").write_text("{}", encoding="utf-8", newline="\n")
    with pytest.raises(PluginError) as exc:
        migrate.plan_migration(tmp_path, version="1.0.0")
    assert exc.value.code == "E_MIGRATE" and "mutually exclusive" in exc.value.detail


# --------------------------------------------------------------------------- diagnostics


def test_diagnose_without_a_manifest_reports_facts_only() -> None:
    doc = migrate.diagnose()
    assert doc["compatible"] is None
    assert doc["os"] in {"windows", "macos", "linux"}
    assert any(
        i["interpreter"] == "python3" and i["found"] for i in doc["interpreters"]
    )  # type: ignore[union-attr]


def test_diagnose_with_the_real_manifest_is_compatible_here(
    live_prefix: Prefix,
) -> None:
    from plugin.manifest import load as load_manifest

    manifest = load_manifest(live_prefix.version_dir("1.0.0") / MANIFEST_RELPATH)
    doc = migrate.diagnose(manifest, client_version="1.2.3")
    assert doc["compatible"] is True, doc["reasons"]


def test_diagnose_flags_an_old_client(live_prefix: Prefix) -> None:
    from plugin.manifest import load as load_manifest

    manifest = load_manifest(live_prefix.version_dir("1.0.0") / MANIFEST_RELPATH)
    doc = migrate.diagnose(manifest, client_version="0.0.1")
    assert doc["compatible"] is False and any("min_client" in r for r in doc["reasons"])  # type: ignore[union-attr]


def test_shell_detection_names_the_wsl_bash_hazard() -> None:
    facts = migrate.detect_shell()
    assert "bash_is_probably_wsl" in facts and "git_bash_present" in facts


def test_adopt_live_tree_inventories_an_existing_target(tmp_path: Path) -> None:
    live = tmp_path / "live"
    (live / "commands").mkdir(parents=True)
    (live / "commands" / "hand.md").write_text(
        "hand written\n", encoding="utf-8", newline="\n"
    )
    doc = migrate.adopt_live_tree(tmp_path, live)
    assert doc["present"] is True and doc["file_count"] == 1
    assert doc["files"][0]["path"] == "commands/hand.md"  # type: ignore[index]
    absent = migrate.adopt_live_tree(tmp_path, tmp_path / "nope")
    assert absent["present"] is False


def test_migration_ledger_serialises(tmp_path: Path) -> None:
    ledger = migrate.migrate(tmp_path, version="1.0.0")
    out = tmp_path / "ledger.json"
    migrate.write_ledger(out, ledger)
    assert json.loads(out.read_text(encoding="utf-8"))["artifact"] == "migration-ledger"
