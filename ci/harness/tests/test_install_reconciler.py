from __future__ import annotations

import json

import pytest

from harness import install as install_mod
from harness.install import (
    DriftItem,
    _ensure_module_modes,
    _ensure_state_dirs,
    _structured_diff,
    _summarize,
    bootstrap,
    build_reconcile_report,
    deploy,
    desired_documents,
    install,
    main,
)
from harness.registration import build_hooks


def _write_settings(path, *, with_hooks=True, extra=None):
    document = {"model": "opus", "env": {"FOO": "bar"}}
    if with_hooks:
        document["hooks"] = build_hooks("claude")
    if extra:
        document.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return document


def _write_codex(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hooks": build_hooks("codex")}), encoding="utf-8")


# --------------------------------------------------------------------------- #
# desired_documents
# --------------------------------------------------------------------------- #


def test_desired_documents_injects_freshly_built_hooks(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"model": "opus", "hooks": {"stale": []}}), encoding="utf-8")

    claude, codex = desired_documents(settings)

    assert claude["model"] == "opus"
    assert claude["hooks"] == build_hooks("claude")
    assert codex == {"hooks": build_hooks("codex")}


def test_desired_documents_reads_module_global_when_no_arg(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"k": "v", "hooks": {}}), encoding="utf-8")
    monkeypatch.setattr(install_mod, "CLAUDE_SETTINGS", settings)

    claude, _ = desired_documents()

    assert claude["k"] == "v"
    assert claude["hooks"] == build_hooks("claude")


# --------------------------------------------------------------------------- #
# structured diff helpers
# --------------------------------------------------------------------------- #


def test_structured_diff_equal_is_empty():
    assert _structured_diff({"a": 1}, {"a": 1}) == {}
    assert _structured_diff([1, 2], [1, 2]) == {}


def test_structured_diff_reports_added_removed_changed_key_names_only():
    diff = _structured_diff({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 99, "d": 4})
    assert diff == {"added": ["d"], "removed": ["c"], "changed": ["b"]}
    # values must never appear in a dict diff (no secret leakage)
    assert "99" not in json.dumps(diff)


def test_structured_diff_non_dict_reports_pair():
    assert _structured_diff([1], [2]) == {"expected": [1], "actual": [2]}


def test_summarize_is_value_free():
    assert _summarize({"TOKEN": "secret-value"}) == {"keys": ["TOKEN"]}
    assert "secret-value" not in json.dumps(_summarize({"TOKEN": "secret-value"}))
    assert _summarize([1, 2, 3]) == {"count": 3}
    assert _summarize("x") == {"type": "str"}
    assert _summarize(None) is None


# --------------------------------------------------------------------------- #
# reconcile: hooks (always managed)
# --------------------------------------------------------------------------- #


def test_check_reports_clean_when_hooks_match(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(settings, with_hooks=True)
    _write_codex(codex)

    report = build_reconcile_report(claude_settings=settings, codex_hooks=codex)

    assert report["drift"] is False
    statuses = {item["section"]: item["status"] for item in report["items"]}
    assert statuses["hooks.claude"] == "ok"
    assert statuses["hooks.codex"] == "ok"


def test_check_reports_drift_when_claude_hooks_missing(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(settings, with_hooks=False)
    _write_codex(codex)

    report = build_reconcile_report(claude_settings=settings, codex_hooks=codex)

    assert report["drift"] is True
    claude_item = next(i for i in report["items"] if i["section"] == "hooks.claude")
    assert claude_item["status"] == "drift"
    assert claude_item["managed"] is True


def test_check_reports_drift_when_codex_hooks_absent(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"  # not created
    _write_settings(settings, with_hooks=True)

    report = build_reconcile_report(claude_settings=settings, codex_hooks=codex)

    assert report["drift"] is True
    codex_item = next(i for i in report["items"] if i["section"] == "hooks.codex")
    assert codex_item["status"] == "drift"


def test_codex_unexpected_top_level_keys_are_drift(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(settings, with_hooks=True)
    codex.write_text(
        json.dumps({"hooks": build_hooks("codex"), "stray": 1}), encoding="utf-8"
    )

    report = build_reconcile_report(claude_settings=settings, codex_hooks=codex)

    codex_item = next(i for i in report["items"] if i["section"] == "hooks.codex")
    assert codex_item["status"] == "drift"
    assert codex_item["detail"]["unexpected_keys"] == ["stray"]
    assert report["drift"] is True


# --------------------------------------------------------------------------- #
# reconcile: fail-open
# --------------------------------------------------------------------------- #


def test_check_is_fail_open_on_missing_settings(tmp_path):
    settings = tmp_path / "does-not-exist.json"
    codex = tmp_path / "codex.json"

    report = build_reconcile_report(claude_settings=settings, codex_hooks=codex)

    assert report["drift"] is True
    hooks_item = next(i for i in report["items"] if i["section"] == "hooks")
    assert hooks_item["status"] == "error"
    assert hooks_item["managed"] is True


def test_check_is_fail_open_on_invalid_json(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{not json", encoding="utf-8")
    codex = tmp_path / "codex.json"

    report = build_reconcile_report(claude_settings=settings, codex_hooks=codex)

    assert report["drift"] is True


def test_run_check_never_raises_even_when_report_builder_explodes(monkeypatch, capsys):
    def boom(**_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(install_mod, "build_reconcile_report", boom)
    code = install(check=True)
    out = capsys.readouterr().out
    assert code == 1
    payload = json.loads(out)
    assert payload["drift"] is True
    assert payload["error"] == "reconcile_failed"


# --------------------------------------------------------------------------- #
# reconcile: observed settings sections
# --------------------------------------------------------------------------- #


def test_settings_sections_unmanaged_without_baseline(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(
        settings,
        with_hooks=True,
        extra={"enabledPlugins": ["a@mkt"], "env": {"TOKEN": "sk-secret"}},
    )
    _write_codex(codex)

    report = build_reconcile_report(
        claude_settings=settings, codex_hooks=codex, baseline_path=tmp_path / "none.json"
    )

    assert report["drift"] is False
    sections = {i["section"]: i for i in report["items"]}
    for name in ("plugins", "enabledPlugins", "tasks", "env"):
        assert sections[name]["status"] == "unmanaged"
        assert sections[name]["managed"] is False
    # observe-only env detail exposes KEY names, never the secret value
    assert "sk-secret" not in json.dumps(report)
    assert sections["env"]["detail"] == {"observed": {"keys": ["TOKEN"]}}


def test_settings_sections_drift_with_baseline(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    baseline = tmp_path / "reconcile-baseline.json"
    _write_settings(
        settings,
        with_hooks=True,
        extra={"enabledPlugins": ["a@mkt"], "env": {"FOO": "bar", "GONE": "1"}},
    )
    _write_codex(codex)
    baseline.write_text(
        json.dumps(
            {
                "enabledPlugins": ["a@mkt", "b@mkt"],
                "env": {"FOO": "bar", "NEW": "2"},
            }
        ),
        encoding="utf-8",
    )

    report = build_reconcile_report(
        claude_settings=settings, codex_hooks=codex, baseline_path=baseline
    )

    assert report["drift"] is True
    sections = {i["section"]: i for i in report["items"]}
    assert sections["enabledPlugins"]["status"] == "drift"
    assert sections["enabledPlugins"]["managed"] is True
    env_item = sections["env"]
    assert env_item["status"] == "drift"
    # env dict-diff reports key names only (NEW missing, GONE unexpected)
    assert env_item["detail"] == {"added": ["GONE"], "removed": ["NEW"]}
    assert report["baseline"] == str(baseline)


def test_settings_section_ok_when_baseline_matches(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    baseline = tmp_path / "reconcile-baseline.json"
    _write_settings(settings, with_hooks=True, extra={"enabledPlugins": ["a@mkt"]})
    _write_codex(codex)
    baseline.write_text(json.dumps({"enabledPlugins": ["a@mkt"]}), encoding="utf-8")

    report = build_reconcile_report(
        claude_settings=settings, codex_hooks=codex, baseline_path=baseline
    )

    sections = {i["section"]: i for i in report["items"]}
    assert sections["enabledPlugins"]["status"] == "ok"
    assert report["drift"] is False


def test_invalid_baseline_is_ignored_as_unmanaged(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    baseline = tmp_path / "reconcile-baseline.json"
    _write_settings(settings, with_hooks=True)
    _write_codex(codex)
    baseline.write_text("[not, an, object]", encoding="utf-8")

    report = build_reconcile_report(
        claude_settings=settings, codex_hooks=codex, baseline_path=baseline
    )

    assert report["baseline"] is None
    sections = {i["section"]: i for i in report["items"]}
    assert sections["env"]["status"] == "unmanaged"
    assert report["drift"] is False


# --------------------------------------------------------------------------- #
# reconcile: skills symlink
# --------------------------------------------------------------------------- #


def _make_symlink(link: "object", target: "object") -> bool:
    import os

    target.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, link, target_is_directory=True)
        return link.is_symlink()
    except OSError:
        return False


def test_skills_symlink_unmanaged_without_baseline(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(settings, with_hooks=True)
    _write_codex(codex)
    link = tmp_path / "skills"  # does not exist

    report = build_reconcile_report(
        claude_settings=settings,
        codex_hooks=codex,
        skills_link=link,
        baseline_path=tmp_path / "none.json",
    )

    item = next(i for i in report["items"] if i["section"] == "skills_symlink")
    assert item["status"] == "unmanaged"
    assert item["managed"] is False
    assert report["drift"] is False


def test_skills_symlink_ok_and_drift_with_baseline(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(settings, with_hooks=True)
    _write_codex(codex)
    link = tmp_path / "skills"
    target = tmp_path / "skills.daily"
    if not _make_symlink(link, target):
        pytest.skip("symlink creation not permitted in this environment")

    ok_baseline = tmp_path / "ok.json"
    ok_baseline.write_text(
        json.dumps({"skills_symlink": {"target": str(target)}}), encoding="utf-8"
    )
    report_ok = build_reconcile_report(
        claude_settings=settings,
        codex_hooks=codex,
        skills_link=link,
        baseline_path=ok_baseline,
    )
    item_ok = next(i for i in report_ok["items"] if i["section"] == "skills_symlink")
    assert item_ok["status"] == "ok"
    assert report_ok["drift"] is False

    bad_baseline = tmp_path / "bad.json"
    bad_baseline.write_text(
        json.dumps({"skills_symlink": {"target": str(tmp_path / "elsewhere")}}),
        encoding="utf-8",
    )
    report_bad = build_reconcile_report(
        claude_settings=settings,
        codex_hooks=codex,
        skills_link=link,
        baseline_path=bad_baseline,
    )
    item_bad = next(i for i in report_bad["items"] if i["section"] == "skills_symlink")
    assert item_bad["status"] == "drift"
    assert report_bad["drift"] is True


def test_skills_symlink_pinned_without_target_requires_symlink(tmp_path):
    settings = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(settings, with_hooks=True)
    _write_codex(codex)
    # plain directory, not a symlink
    link = tmp_path / "skills"
    link.mkdir()
    baseline = tmp_path / "b.json"
    baseline.write_text(json.dumps({"skills_symlink": {}}), encoding="utf-8")

    report = build_reconcile_report(
        claude_settings=settings,
        codex_hooks=codex,
        skills_link=link,
        baseline_path=baseline,
    )

    item = next(i for i in report["items"] if i["section"] == "skills_symlink")
    assert item["status"] == "drift"
    assert report["drift"] is True


# --------------------------------------------------------------------------- #
# bootstrap
# --------------------------------------------------------------------------- #


def test_bootstrap_creates_state_dirs_and_module_modes(tmp_path):
    root = tmp_path / "state"
    created = _ensure_state_dirs(root)
    modes = _ensure_module_modes(root)

    for name in install_mod.STATE_SUBDIRS:
        assert (root / name).is_dir()
    assert {p.name for p in created} == set(install_mod.STATE_SUBDIRS)
    assert modes.exists()
    assert json.loads(modes.read_text(encoding="utf-8")) == {}


def test_bootstrap_is_idempotent_and_preserves_module_modes(tmp_path):
    root = tmp_path / "state"
    _ensure_state_dirs(root)
    modes = root / install_mod.MODULE_MODES_NAME
    modes.write_text(json.dumps({"my_gate": "enforce"}), encoding="utf-8")

    # run twice -> no error, and the owner's customization survives
    _ensure_module_modes(root)
    _ensure_state_dirs(root)
    _ensure_module_modes(root)

    assert json.loads(modes.read_text(encoding="utf-8")) == {"my_gate": "enforce"}


def test_bootstrap_without_install_only_prepares_state(tmp_path, monkeypatch):
    root = tmp_path / "state"
    calls = []
    monkeypatch.setattr(install_mod, "install", lambda **kw: calls.append(kw) or 0)

    code = bootstrap(state_root=root, do_install=False)

    assert code == 0
    assert calls == []  # install must NOT run when do_install=False
    assert (root / "shadow").is_dir()
    assert (root / install_mod.MODULE_MODES_NAME).exists()


def test_bootstrap_invokes_install_by_default(tmp_path, monkeypatch):
    root = tmp_path / "state"
    calls = []
    monkeypatch.setattr(install_mod, "install", lambda **kw: calls.append(kw) or 0)

    code = bootstrap(state_root=root)

    assert code == 0
    assert calls == [{"check": False}]


# --------------------------------------------------------------------------- #
# install write path preserves manifest shape (D5 contract)
# --------------------------------------------------------------------------- #


def test_install_write_path_preserves_manifest_shape(tmp_path, monkeypatch):
    claude = tmp_path / "claude" / "settings.json"
    codex = tmp_path / "codex" / "hooks.json"
    backups = tmp_path / "backups"
    manifest = tmp_path / "installed.json"
    claude.parent.mkdir(parents=True, exist_ok=True)
    claude.write_text(json.dumps({"model": "opus", "hooks": {"stale": []}}), encoding="utf-8")

    monkeypatch.setattr(install_mod, "CLAUDE_SETTINGS", claude)
    monkeypatch.setattr(install_mod, "CODEX_HOOKS", codex)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", backups)
    monkeypatch.setattr(install_mod, "INSTALLED_MANIFEST", manifest)

    code = install(check=False)
    assert code == 0

    written_claude = json.loads(claude.read_text(encoding="utf-8"))
    assert written_claude["hooks"] == build_hooks("claude")
    assert written_claude["model"] == "opus"
    assert json.loads(codex.read_text(encoding="utf-8")) == {"hooks": build_hooks("codex")}

    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    # D5 contract: modules.py._config_drift compares the live settings against
    # the "settings" snapshot; the sha256 fields are preserved alongside it.
    assert set(recorded) == {"installed_at", "backup", "sha256", "settings"}
    assert set(recorded["sha256"]) == {"claude", "codex"}
    assert len(recorded["sha256"]["claude"]) == 64
    assert len(recorded["sha256"]["codex"]) == 64
    # The snapshot carries exactly the three curated sections the gate compares;
    # "hooks" is the freshly-built block (mcp* are None here — absent in source).
    assert set(recorded["settings"]) == {"hooks", "mcpServers", "disabledMcpServers"}
    assert recorded["settings"]["hooks"] == build_hooks("claude")
    # atomic backup copy exists
    backup_dir = tmp_path / "backups"
    copies = list(backup_dir.rglob("claude-settings.json"))
    assert len(copies) == 1


def test_install_check_returns_zero_when_clean(tmp_path, monkeypatch):
    claude = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(claude, with_hooks=True)
    _write_codex(codex)
    monkeypatch.setattr(install_mod, "CLAUDE_SETTINGS", claude)
    monkeypatch.setattr(install_mod, "CODEX_HOOKS", codex)
    monkeypatch.setattr(install_mod, "SKILLS_LINK", tmp_path / "skills")
    monkeypatch.setattr(install_mod, "RECONCILE_BASELINE", tmp_path / "none.json")

    assert install(check=True) == 0


def test_install_check_returns_one_on_drift(tmp_path, monkeypatch, capsys):
    claude = tmp_path / "settings.json"
    codex = tmp_path / "codex.json"
    _write_settings(claude, with_hooks=False)
    _write_codex(codex)
    monkeypatch.setattr(install_mod, "CLAUDE_SETTINGS", claude)
    monkeypatch.setattr(install_mod, "CODEX_HOOKS", codex)
    monkeypatch.setattr(install_mod, "SKILLS_LINK", tmp_path / "skills")
    monkeypatch.setattr(install_mod, "RECONCILE_BASELINE", tmp_path / "none.json")

    code = install(check=True)
    out = capsys.readouterr().out
    assert code == 1
    payload = json.loads(out)  # structured diff printed, valid JSON
    assert payload["drift"] is True
    assert "items" in payload


# --------------------------------------------------------------------------- #
# CLI dispatch
# --------------------------------------------------------------------------- #


def test_main_check_and_bootstrap_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        main(["--check", "--bootstrap"])


def test_main_routes_check(monkeypatch):
    calls = []
    monkeypatch.setattr(install_mod, "install", lambda **kw: calls.append(kw) or 0)
    assert main(["--check"]) == 0
    assert calls == [{"check": True}]


def test_main_routes_bootstrap(monkeypatch):
    calls = []
    monkeypatch.setattr(install_mod, "bootstrap", lambda: calls.append("boot") or 0)
    assert main(["--bootstrap"]) == 0
    assert calls == ["boot"]


def test_drift_item_is_drift_property():
    assert DriftItem("x", "drift", True).is_drift is True
    assert DriftItem("x", "error", True).is_drift is True
    assert DriftItem("x", "drift", False).is_drift is False
    assert DriftItem("x", "unmanaged", False).is_drift is False
    assert DriftItem("x", "ok", True).is_drift is False


# --------------------------------------------------------------------------- #
# deploy: repo harness (ci/harness) -> live ~/.agents/harness
# --------------------------------------------------------------------------- #
#
# SAFETY: every deploy test passes an EXPLICIT source_dir/live_dir under tmp_path
# (or monkeypatches HERE/LIVE_HARNESS_DIR to tmp). No test ever touches the real
# ~/.agents tree.


def _make_source_tree(src):
    """A fake ci/harness source tree with real files + runtime junk to exclude."""
    src.mkdir(parents=True, exist_ok=True)
    (src / "modules.py").write_text("# modules\n", encoding="utf-8")
    (src / "installed.json").write_text("{}", encoding="utf-8")
    (src / "foo.bak").write_text("stale backup\n", encoding="utf-8")
    (src / "backups").mkdir()
    (src / "backups" / "x").write_text("old\n", encoding="utf-8")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "y.pyc").write_text("bytecode\n", encoding="utf-8")
    (src / "sub").mkdir()
    (src / "sub" / "a.py").write_text("# a\n", encoding="utf-8")
    return src


def test_deploy_copies_source_excluding_runtime_state(tmp_path):
    src = _make_source_tree(tmp_path / "source")
    live = tmp_path / "live"

    code = deploy(source_dir=src, live_dir=live)

    assert code == 0
    # real source files land
    assert (live / "modules.py").read_text(encoding="utf-8") == "# modules\n"
    assert (live / "sub" / "a.py").read_text(encoding="utf-8") == "# a\n"
    # runtime state is excluded
    assert not (live / "installed.json").exists()
    assert not (live / "backups").exists()
    assert not (live / "__pycache__").exists()
    assert not (live / "foo.bak").exists()


def test_deploy_backs_up_existing_live_tree(tmp_path, monkeypatch):
    src = _make_source_tree(tmp_path / "source")
    live = tmp_path / "live"
    backups = tmp_path / "backups"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", backups)
    # pre-populate live with a sentinel that the backup must capture
    live.mkdir(parents=True, exist_ok=True)
    (live / "sentinel.py").write_text("# sentinel\n", encoding="utf-8")

    code = deploy(source_dir=src, live_dir=live)

    assert code == 0
    copies = list(backups.rglob("sentinel.py"))
    assert len(copies) == 1
    assert copies[0].read_text(encoding="utf-8") == "# sentinel\n"
    # the backup lives under a deploy-<stamp>/harness/ prefix
    assert copies[0].parent.name == "harness"
    assert copies[0].parent.parent.name.startswith("deploy-")


def test_deploy_backup_excludes_runtime_state(tmp_path, monkeypatch):
    src = _make_source_tree(tmp_path / "source")
    live = tmp_path / "live"
    backups = tmp_path / "backups"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", backups)
    # pre-populate live with BOTH a real file and runtime junk
    live.mkdir(parents=True, exist_ok=True)
    (live / "keep.py").write_text("# keep\n", encoding="utf-8")
    (live / "installed.json").write_text("{}", encoding="utf-8")
    (live / "__pycache__").mkdir()
    (live / "__pycache__" / "z.pyc").write_text("bytecode\n", encoding="utf-8")

    deploy(source_dir=src, live_dir=live)

    assert list(backups.rglob("keep.py"))
    # runtime junk must not be backed up either
    assert not list(backups.rglob("installed.json"))
    assert not list(backups.rglob("*.pyc"))


def test_deploy_is_idempotent(tmp_path, monkeypatch):
    src = _make_source_tree(tmp_path / "source")
    live = tmp_path / "live"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    def _snapshot(root):
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    import io
    from contextlib import redirect_stdout

    buf1 = io.StringIO()
    with redirect_stdout(buf1):
        deploy(source_dir=src, live_dir=live)
    first_tree = _snapshot(live)
    first_copied = json.loads(buf1.getvalue())["copied"]

    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        deploy(source_dir=src, live_dir=live)
    second_tree = _snapshot(live)
    second_copied = json.loads(buf2.getvalue())["copied"]

    assert first_copied == second_copied
    assert first_tree == second_tree


def test_deploy_prints_copied_manifest(tmp_path, monkeypatch, capsys):
    src = _make_source_tree(tmp_path / "source")
    live = tmp_path / "live"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    deploy(source_dir=src, live_dir=live)

    payload = json.loads(capsys.readouterr().out)
    assert payload["deployed_to"] == str(live)
    assert payload["count"] == len(payload["copied"])
    assert "modules.py" in payload["copied"]
    # normpath means the nested file uses the OS separator; check by parts
    import os

    assert os.path.join("sub", "a.py") in payload["copied"]


def test_deploy_no_live_dir_skips_backup(tmp_path, monkeypatch):
    src = _make_source_tree(tmp_path / "source")
    live = tmp_path / "live"  # does not exist yet
    backups = tmp_path / "backups"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", backups)

    code = deploy(source_dir=src, live_dir=live)

    assert code == 0
    # tree materialized
    assert (live / "modules.py").exists()
    # no backup created (nothing was live)
    assert not backups.exists()


def test_main_deploy_subcommand(tmp_path, monkeypatch):
    src = _make_source_tree(tmp_path / "source")
    live = tmp_path / "live"
    monkeypatch.setattr(install_mod, "HERE", src)
    monkeypatch.setattr(install_mod, "LIVE_HARNESS_DIR", live)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = main(["--deploy"])

    assert code == 0
    assert (live / "modules.py").exists()
    assert (live / "sub" / "a.py").exists()
    assert not (live / "installed.json").exists()


def test_main_deploy_is_mutually_exclusive_with_check():
    with pytest.raises(SystemExit):
        main(["--deploy", "--check"])
