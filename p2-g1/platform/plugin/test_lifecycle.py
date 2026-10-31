"""Tests for the journal, the two-directional drift classifier, and the lifecycle commands.

The DIVERGED case gets its own test because it is the one that six independent agents got wrong on
338 real files, with 100% of the errors pointing at data loss. A classifier that only reads one
direction cannot produce it, so a test that never constructs it proves nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from plugin import deploy as deploy_mod
from plugin import journal as journal_mod
from plugin import lifecycle
from plugin.build import build
from plugin.errors import PluginError
from plugin.journal import Prefix, PrefixLock, Transaction
from plugin.manifest import MANIFEST_RELPATH, load as load_manifest

# --------------------------------------------------------------------------- journal


def test_transaction_commits_and_records_steps(tmp_path: Path) -> None:
    prefix = Prefix(tmp_path)
    prefix.ensure()
    with Transaction(prefix, "demo") as txn:
        txn.add("touch", {"path": "x"}, None)
    events = [r["event"] for r in journal_mod.read_journal(prefix)]
    assert events == ["open", "step", "commit"]
    assert journal_mod.open_transactions(prefix) == []


def test_transaction_replays_inverses_in_reverse_order(tmp_path: Path) -> None:
    prefix = Prefix(tmp_path)
    prefix.ensure()
    order: list[str] = []
    with pytest.raises(RuntimeError):
        with Transaction(prefix, "demo") as txn:
            txn.add("one", {}, lambda: order.append("undo-one"))
            txn.add("two", {}, lambda: order.append("undo-two"))
            raise RuntimeError("boom")
    assert order == ["undo-two", "undo-one"]
    last = journal_mod.read_journal(prefix)[-1]
    assert last["event"] == "abort" and last["steps_undone"] == 2


def test_crash_recovery_removes_staged_and_created_dirs(tmp_path: Path) -> None:
    prefix = Prefix(tmp_path)
    prefix.ensure()
    staged = prefix.staging / "abc"
    staged.mkdir(parents=True)
    (staged / "f").write_text("x", encoding="utf-8")
    # Simulate a kill: open + step recorded, no commit/abort.
    txn = Transaction(prefix, "install")
    txn.__enter__()
    txn.add("stage", {"staged_dir": str(staged)}, None)
    assert journal_mod.open_transactions(prefix) == [txn.txn_id]
    got = journal_mod.recover(prefix)
    assert got["clean"] is False and str(staged) in got["removed"]
    assert not staged.exists()
    assert journal_mod.open_transactions(prefix) == []


def test_recovery_never_deletes_outside_the_prefix(tmp_path: Path) -> None:
    prefix = Prefix(tmp_path / "prefix")
    prefix.ensure()
    outsider = tmp_path / "outside"
    outsider.mkdir()
    (outsider / "precious.txt").write_text("keep me", encoding="utf-8")
    txn = Transaction(prefix, "install")
    txn.__enter__()
    txn.add("stage", {"staged_dir": str(outsider)}, None)
    journal_mod.recover(prefix)
    assert (outsider / "precious.txt").exists(), (
        "recovery deleted a path outside the prefix"
    )


def test_prefix_lock_is_exclusive(tmp_path: Path) -> None:
    prefix = Prefix(tmp_path)
    prefix.ensure()
    with PrefixLock(prefix, op="install"):
        with pytest.raises(PluginError) as exc:
            with PrefixLock(prefix, op="update"):
                pass
        assert exc.value.code == "E_LOCK"
    assert not prefix.lock.exists(), "the lock was not released"


def test_stale_lock_is_taken_over(tmp_path: Path) -> None:
    prefix = Prefix(tmp_path)
    prefix.ensure()
    prefix.lock.write_text("dead holder\n", encoding="utf-8")
    with PrefixLock(prefix, op="install", stale_after=0.0):
        assert prefix.lock.exists()


# --------------------------------------------------------------------------- drift classes


@pytest.fixture
def installed(tmp_path: Path, repo_root: Path) -> tuple[Prefix, Path, Path]:
    """A real installed prefix with a real deployed live tree."""
    result, _ = build(repo_root, tmp_path / "dist")
    prefix = Prefix(tmp_path / "prefix")
    res = lifecycle.install(
        result.archive, prefix, live_root=tmp_path / "prefix" / "live"
    )
    assert res.ok
    vroot = prefix.version_dir(str(res.version))
    return prefix, vroot, tmp_path / "prefix" / "live"


def _classify(prefix: Prefix, vroot: Path, live: Path) -> dict[str, str]:
    manifest = load_manifest(vroot / MANIFEST_RELPATH)
    prov = deploy_mod.Provenance.load(prefix.state / deploy_mod.PROVENANCE_NAME)
    return {
        e.live_path: e.classification
        for e in deploy_mod.classify(manifest, vroot, live, prov)
    }


def test_fresh_install_is_all_unchanged(installed) -> None:
    prefix, vroot, live = installed
    got = _classify(prefix, vroot, live)
    assert set(got.values()) == {"unchanged"}, got


def test_live_edit_alone_is_live_only(installed) -> None:
    prefix, vroot, live = installed
    target = live / "commands" / "astplugin.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nlocal\n", encoding="utf-8", newline="\n"
    )
    assert _classify(prefix, vroot, live)["commands/astplugin.md"] == "live_only"


def test_source_edit_alone_is_upstream_only(installed) -> None:
    prefix, vroot, live = installed
    src = vroot / "commands" / "astplugin.md"
    src.write_text(
        src.read_text(encoding="utf-8") + "\nupstream\n", encoding="utf-8", newline="\n"
    )
    assert _classify(prefix, vroot, live)["commands/astplugin.md"] == "upstream_only"


def test_both_sides_unique_is_diverged(installed) -> None:
    """The case a one-directional classifier CANNOT see. 31 of 31 agent errors were this shape."""
    prefix, vroot, live = installed
    rel = "commands/astplugin.md"
    (live / "commands" / "astplugin.md").write_text(
        (live / "commands" / "astplugin.md").read_text(encoding="utf-8")
        + "\nlocal-only\n",
        encoding="utf-8",
        newline="\n",
    )
    (vroot / "commands" / "astplugin.md").write_text(
        (vroot / "commands" / "astplugin.md").read_text(encoding="utf-8")
        + "\nupstream-only\n",
        encoding="utf-8",
        newline="\n",
    )
    got = _classify(prefix, vroot, live)
    assert got[rel] == "diverged", got


def test_both_sides_converging_to_same_content_is_unchanged(installed) -> None:
    prefix, vroot, live = installed
    suffix = "\nsame edit both sides\n"
    for base in (live / "commands", vroot / "commands"):
        p = base / "astplugin.md"
        p.write_text(
            p.read_text(encoding="utf-8") + suffix, encoding="utf-8", newline="\n"
        )
    assert _classify(prefix, vroot, live)["commands/astplugin.md"] == "unchanged"


def test_missing_live_file_is_live_absent(installed) -> None:
    prefix, vroot, live = installed
    (live / "hooks" / "plugin_health.py").unlink()
    assert _classify(prefix, vroot, live)["hooks/plugin_health.py"] == "live_absent"


def test_live_file_with_no_provenance_is_untracked(installed) -> None:
    prefix, vroot, live = installed
    prov_path = prefix.state / deploy_mod.PROVENANCE_NAME
    doc = json.loads(prov_path.read_text(encoding="utf-8"))
    doc["records"] = []
    doc["record_count"] = 0
    prov_path.write_text(json.dumps(doc), encoding="utf-8", newline="\n")
    target = live / "commands" / "astplugin.md"
    target.write_text("totally different\n", encoding="utf-8", newline="\n")
    assert _classify(prefix, vroot, live)["commands/astplugin.md"] == "untracked_live"


def test_crlf_live_copy_is_not_reported_as_drift(installed) -> None:
    prefix, vroot, live = installed
    target = live / "commands" / "astplugin.md"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    assert _classify(prefix, vroot, live)["commands/astplugin.md"] == "unchanged", (
        "a CRLF checkout was reported as drift; the hash is not EOL-normalised"
    )


def test_drift_document_enumerates_all_six_classes(installed) -> None:
    prefix, vroot, live = installed
    manifest = load_manifest(vroot / MANIFEST_RELPATH)
    prov = deploy_mod.Provenance.load(prefix.state / deploy_mod.PROVENANCE_NAME)
    doc = deploy_mod.drift_document(deploy_mod.classify(manifest, vroot, live, prov))
    assert set(doc["counts"]) == set(
        deploy_mod.CLASS_UNCHANGED
        and {  # type: ignore[arg-type]
            "unchanged",
            "upstream_only",
            "live_only",
            "diverged",
            "live_absent",
            "untracked_live",
        }
    )
    assert doc["bidirectional"] is True


def test_sync_refuses_to_resolve_divergence(installed) -> None:
    prefix, vroot, live = installed
    manifest = load_manifest(vroot / MANIFEST_RELPATH)
    live_file = live / "commands" / "astplugin.md"
    src_file = vroot / "commands" / "astplugin.md"
    live_body = live_file.read_text(encoding="utf-8") + "\nlocal-only\n"
    live_file.write_text(live_body, encoding="utf-8", newline="\n")
    src_file.write_text(
        src_file.read_text(encoding="utf-8") + "\nupstream-only\n",
        encoding="utf-8",
        newline="\n",
    )
    res = deploy_mod.sync(manifest, vroot, live, prefix)
    assert res.needs_decision == ["commands/astplugin.md"]
    assert live_file.read_text(encoding="utf-8") == live_body, (
        "sync overwrote a diverged file"
    )
    packet = deploy_mod.divergence_decisions(res.entries)
    assert packet["auto_resolved"] is False
    assert packet["decisions"][0]["chosen"] is None  # type: ignore[index]


def test_repair_never_touches_live_unique_content(installed) -> None:
    prefix, vroot, live = installed
    manifest = load_manifest(vroot / MANIFEST_RELPATH)
    edited = live / "commands" / "astplugin.md"
    body = edited.read_text(encoding="utf-8") + "\nmine\n"
    edited.write_text(body, encoding="utf-8", newline="\n")
    victim = live / "hooks" / "plugin_health.py"
    victim.unlink()
    res = deploy_mod.repair(manifest, vroot, live, prefix)
    assert "hooks/plugin_health.py" in res.written
    assert edited.read_text(encoding="utf-8") == body
    assert res.kept == ["commands/astplugin.md"]


def test_three_way_merge_merges_disjoint_hunks_and_refuses_overlap() -> None:
    base = "a\nb\nc\nd\ne\n"
    merged, conflicts = deploy_mod.three_way_merge(
        base, "A\nb\nc\nd\ne\n", "a\nb\nc\nd\nE\n"
    )
    assert conflicts == [] and merged == "A\nb\nc\nd\nE\n"
    merged2, conflicts2 = deploy_mod.three_way_merge(
        base, "a\nB1\nc\nd\ne\n", "a\nB2\nc\nd\ne\n"
    )
    assert merged2 is None and conflicts2, "overlapping hunks were silently merged"


def test_projection_map_carries_per_os_argv(installed) -> None:
    prefix, vroot, live = installed
    manifest = load_manifest(vroot / MANIFEST_RELPATH)
    doc = deploy_mod.projection_map(manifest, vroot, live)
    assert {t["target"] for t in doc["targets"]} == {"commands", "hooks"}  # type: ignore[index]
    for ep in doc["entrypoints"]:  # type: ignore[union-attr]
        assert set(ep["launch"]) == {"windows", "macos", "linux"}
        assert all(isinstance(v, list) and v for v in ep["launch"].values())


# --------------------------------------------------------------------------- lifecycle


def test_install_is_idempotently_refused_for_the_same_version(
    installed, tmp_path: Path, repo_root: Path
) -> None:
    prefix, _, live = installed
    result, _ = build(repo_root, tmp_path / "dist2")
    with pytest.raises(PluginError) as exc:
        lifecycle.install(result.archive, prefix, live_root=live)
    assert exc.value.code == "E_TXN" and "already installed" in exc.value.detail


def test_update_refuses_a_non_advance(
    installed, tmp_path: Path, repo_root: Path
) -> None:
    prefix, _, live = installed
    result, _ = build(repo_root, tmp_path / "dist-same", version="1.0.0")
    with pytest.raises(PluginError) as exc:
        lifecycle.update(result.archive, prefix, live_root=live)
    assert "not an advance" in exc.value.detail


def test_update_then_rollback_round_trips(
    installed, tmp_path: Path, repo_root: Path
) -> None:
    prefix, _, live = installed
    newer, _ = build(repo_root, tmp_path / "dist-new", version="1.0.1")
    up = lifecycle.update(newer.archive, prefix, live_root=live)
    assert (up.previous_version, up.version) == ("1.0.0", "1.0.1")
    live_before = {p.name for p in live.rglob("*") if p.is_file()}
    rb = lifecycle.rollback(prefix, live_root=live)
    assert rb.version == "1.0.0"
    assert {p.name for p in live.rglob("*") if p.is_file()} == live_before
    assert rb.detail["live_files_removed"] == []
    assert sorted(rb.detail["versions_retained"]) == ["1.0.0", "1.0.1"]  # type: ignore[arg-type]


def test_rollback_without_a_previous_version_is_refused(installed) -> None:
    prefix, _, live = installed
    with pytest.raises(PluginError) as exc:
        lifecycle.rollback(prefix, live_root=live)
    assert "no recorded previous version" in exc.value.detail


def test_uninstall_requires_an_explicit_user_data_decision(installed) -> None:
    prefix, _, live = installed
    with pytest.raises(PluginError) as exc:
        lifecycle.uninstall(prefix, live_root=live, user_data=None)
    assert (
        exc.value.code == "E_USAGE"
        and "explicit user-data decision" in exc.value.detail
    )


def test_uninstall_retains_user_data_and_user_edited_files(installed) -> None:
    prefix, _, live = installed
    prefix.userdata.mkdir(parents=True, exist_ok=True)
    note = prefix.userdata / "notes.txt"
    note.write_text("owner notes\n", encoding="utf-8", newline="\n")
    edited = live / "commands" / "astplugin.md"
    edited.write_text("hand written\n", encoding="utf-8", newline="\n")
    res = lifecycle.uninstall(prefix, live_root=live, user_data="retain")
    assert note.exists(), "retained user data was deleted"
    assert edited.exists(), "a user-edited deployed file was deleted"
    assert res.detail["kept_live_edited"] == ["commands/astplugin.md"]
    assert not prefix.installed.exists()
    assert not prefix.version_dir("1.0.0").exists()


def test_uninstall_purge_removes_user_data_only_when_asked(installed) -> None:
    prefix, _, live = installed
    prefix.userdata.mkdir(parents=True, exist_ok=True)
    (prefix.userdata / "notes.txt").write_text("x\n", encoding="utf-8", newline="\n")
    lifecycle.uninstall(prefix, live_root=live, user_data="purge")
    assert not prefix.userdata.exists()


def test_failed_install_leaves_no_partial_state(
    tmp_path: Path, repo_root: Path
) -> None:
    """Corrupt the archive AFTER its inventory was computed, then prove the prefix is untouched."""
    import zipfile

    result, _ = build(repo_root, tmp_path / "dist")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(result.archive) as zin:
        members = {
            i.filename: zin.read(i.filename) for i in zin.infolist() if not i.is_dir()
        }
    members["README.md"] += b"\ntampered\n"
    with zipfile.ZipFile(bad, "w") as zout:
        for name in sorted(members):
            zout.writestr(name, members[name])

    prefix = Prefix(tmp_path / "prefix")
    with pytest.raises(PluginError) as exc:
        lifecycle.install(bad, prefix, live_root=tmp_path / "prefix" / "live")
    assert exc.value.code == "E_CONFORM"

    residue = lifecycle.prefix_residue(prefix)
    assert residue["versions"] == []
    assert residue["staged_dirs"] == []
    assert residue["installed_json_exists"] is False
    assert residue["lock_held"] is False
    assert residue["live_files"] == []
    assert (
        json.loads(prefix.journal.read_text(encoding="utf-8").splitlines()[-1])["event"]
        == "abort"
    )

    # BOTH-STATES CONTROL: the same prefix must accept the INTACT package. Without this,
    # "nothing partial remains" is indistinguishable from "the prefix is unusable".
    ok = lifecycle.install(
        result.archive, prefix, live_root=tmp_path / "prefix" / "live"
    )
    assert ok.ok and prefix.version_dir("1.0.0").exists()


def test_install_negotiation_rejects_an_old_client(
    tmp_path: Path, repo_root: Path
) -> None:
    result, _ = build(repo_root, tmp_path / "dist")
    prefix = Prefix(tmp_path / "prefix")
    with pytest.raises(PluginError) as exc:
        lifecycle.install(result.archive, prefix, client_version="0.0.1")
    assert exc.value.code == "E_COMPAT"
    assert lifecycle.prefix_residue(prefix)["versions"] == []


def test_dry_run_install_writes_nothing(tmp_path: Path, repo_root: Path) -> None:
    result, _ = build(repo_root, tmp_path / "dist")
    prefix = Prefix(tmp_path / "prefix")
    res = lifecycle.install(result.archive, prefix, dry_run=True)
    assert res.ok and res.detail["dry_run"] is True
    assert lifecycle.prefix_residue(prefix)["versions"] == []
    assert not prefix.installed.exists()


def test_preflight_rejects_an_unwritable_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = Prefix(tmp_path / "prefix")

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("read-only filesystem")

    monkeypatch.setattr("plugin.lifecycle.atomic_write_bytes", boom)
    with pytest.raises(PluginError) as exc:
        lifecycle.preflight(prefix, op="install")
    assert exc.value.code == "E_PREFLIGHT"
