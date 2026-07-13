"""Tests for the CAS-lite deploy mechanism (install.deploy).

SAFETY: every test passes an EXPLICIT source_dir/live_dir under tmp_path and
monkeypatches BACKUPS_DIR to tmp_path. No test ever touches the real ~/.agents
tree. (The HARNESS_LIVE_AGENTS_DIR env override is the alternative redirection
seam and is honored by _default_live; these tests use the direct live_dir arg.)

Covers the five load-bearing behaviors the owner specified: happy-path deploy,
CAS-abort-on-live-change, parity-mismatch-restore, lock-contention, and
receipt-emission -- plus stale-lock steal and target validation.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
from contextlib import redirect_stdout

import pytest

from harness import install as install_mod
from harness.install import deploy


def _src_tree(root, files: dict[str, str]):
    """Materialize a source tree {relpath: text} under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# 1. happy-path deploy
# --------------------------------------------------------------------------- #


def test_deploy_happy_path_writes_tree_and_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")
    src = _src_tree(tmp_path / "src", {"modules.py": "# m\n", "sub/a.py": "# a\n"})
    live = tmp_path / "live"  # does not exist yet

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deploy(source_dir=src, live_dir=live, target="harness")
    payload = json.loads(buf.getvalue())

    assert code == 0
    assert payload["status"] == "deployed"
    # backward-compatible manifest keys are preserved for existing consumers
    assert payload["deployed_to"] == str(live)
    assert payload["count"] == len(payload["copied"])
    assert "modules.py" in payload["copied"]
    assert os.path.join("sub", "a.py") in payload["copied"]

    # the managed tree landed byte-for-byte
    assert (live / "modules.py").read_text(encoding="utf-8") == "# m\n"
    assert (live / "sub" / "a.py").read_text(encoding="utf-8") == "# a\n"

    # RECEIPT: content-based per-file sha256 + datetime metadata
    receipt = json.loads((live / "installed.json").read_text(encoding="utf-8"))
    assert set(receipt) >= {
        "deployed_at", "source_commit", "target", "files", "backup_path"
    }
    assert receipt["target"] == "harness"
    assert receipt["backup_path"] is None  # nothing pre-existed -> no backup
    assert receipt["files"]["modules.py"] == _sha(live / "modules.py")
    assert receipt["files"][os.path.join("sub", "a.py")] == _sha(live / "sub" / "a.py")

    # the single-writer lock is always released
    assert not (live / install_mod.DEPLOY_LOCK_NAME).exists()


# --------------------------------------------------------------------------- #
# 2. CAS-abort-on-live-change
# --------------------------------------------------------------------------- #


def test_deploy_cas_aborts_when_live_changes_since_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")
    src = _src_tree(tmp_path / "src", {"a.py": "candidate\n"})
    live = tmp_path / "live"
    live.mkdir()
    (live / "a.py").write_text("live-at-plan\n", encoding="utf-8")
    plan_hash = _sha(live / "a.py")  # the hash PLAN will capture (real on-disk bytes)

    # A concurrent writer mutates the live file AFTER PLAN captured its hash.
    # The pre-write CAS re-hash must detect the drift and abort the whole deploy.
    def mutate() -> None:
        (live / "a.py").write_text("MUTATED-since-plan\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deploy(source_dir=src, live_dir=live, _after_stage=mutate)
    payload = json.loads(buf.getvalue())

    assert code == 1
    assert payload["reason"] == "cas_conflict"
    assert payload["file"] == "a.py"
    # reported hashes are content-based: expected = plan-time, actual = the change
    assert payload["expected_hash"] == plan_hash
    assert payload["actual_hash"] == _sha(live / "a.py")  # post-mutation bytes
    assert payload["expected_hash"] != payload["actual_hash"]

    # ABORT WITHOUT WRITING: the candidate never landed; the live file is left
    # exactly as the concurrent writer left it (no partial overwrite).
    assert (live / "a.py").read_text(encoding="utf-8") == "MUTATED-since-plan\n"
    assert not (live / "installed.json").exists()  # no receipt on failure
    assert not (live / install_mod.DEPLOY_LOCK_NAME).exists()  # lock released


# --------------------------------------------------------------------------- #
# 3. parity-mismatch-restore (fail-CLOSED on integrity)
# --------------------------------------------------------------------------- #


def test_deploy_parity_mismatch_restores_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")
    src = _src_tree(tmp_path / "src", {"a.py": "candidate\n"})
    live = tmp_path / "live"
    live.mkdir()
    (live / "a.py").write_text("known-good\n", encoding="utf-8")  # last-known-good

    # After the atomic WRITE lands the candidate, something corrupts the live
    # file so it no longer matches the candidate hash -> parity must fail-closed.
    def corrupt() -> None:
        (live / "a.py").write_text("CORRUPTED\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deploy(source_dir=src, live_dir=live, _after_write=corrupt)
    payload = json.loads(buf.getvalue())

    assert code == 1
    assert payload["reason"] == "parity_mismatch"
    assert payload["mismatches"] == ["a.py"]
    assert payload["restored_from"] is not None

    # fail-CLOSED: live is RESTORED to the pre-deploy last-known-good -- NOT left
    # corrupted, and NOT the unverifiable candidate.
    assert (live / "a.py").read_text(encoding="utf-8") == "known-good\n"
    assert not (live / "installed.json").exists()  # no success receipt
    assert not (live / install_mod.DEPLOY_LOCK_NAME).exists()


# --------------------------------------------------------------------------- #
# 4. lock-contention (+ stale-lock steal)
# --------------------------------------------------------------------------- #


def test_deploy_refuses_when_lock_held(tmp_path, monkeypatch):
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")
    src = _src_tree(tmp_path / "src", {"a.py": "v1\n"})
    live = tmp_path / "live"
    live.mkdir()
    # a FRESH lock held by another (fake) live writer
    held = {"pid": 999999, "timestamp": time.time(), "iso": "held"}
    (live / install_mod.DEPLOY_LOCK_NAME).write_text(json.dumps(held), encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deploy(source_dir=src, live_dir=live)
    payload = json.loads(buf.getvalue())

    assert code == 1
    assert payload["reason"] == "lock_contention"
    assert payload["held_by"]["pid"] == 999999

    # refused: nothing deployed, and the holder's lock is UNTOUCHED (not stolen,
    # not released by our finally -- we never acquired it).
    assert not (live / "a.py").exists()
    assert not (live / "installed.json").exists()
    lock = json.loads((live / install_mod.DEPLOY_LOCK_NAME).read_text(encoding="utf-8"))
    assert lock["pid"] == 999999


def test_deploy_steals_stale_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")
    src = _src_tree(tmp_path / "src", {"a.py": "v1\n"})
    live = tmp_path / "live"
    live.mkdir()
    # a STALE lock (timestamp far in the past) left by a crashed writer
    stale = {"pid": 4242, "timestamp": time.time() - 10_000}
    (live / install_mod.DEPLOY_LOCK_NAME).write_text(json.dumps(stale), encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deploy(source_dir=src, live_dir=live, lock_stale_seconds=600)

    assert code == 0
    assert (live / "a.py").read_text(encoding="utf-8") == "v1\n"
    # the stale lock was stolen for the deploy, then released at the end
    assert not (live / install_mod.DEPLOY_LOCK_NAME).exists()


# --------------------------------------------------------------------------- #
# 5. receipt-emission (write/extend + content-based hashes)
# --------------------------------------------------------------------------- #


def test_deploy_receipt_records_hashes_and_extends_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")
    src = _src_tree(tmp_path / "src", {"modules.py": "# m\n", "sub/a.py": "# a\n"})
    live = tmp_path / "live"
    live.mkdir()
    # a pre-existing receipt with an owner key that write/EXTEND must PRESERVE
    (live / "installed.json").write_text(
        json.dumps({"custom": "keep-me"}), encoding="utf-8"
    )

    code = deploy(source_dir=src, live_dir=live, target="harness")

    assert code == 0
    receipt = json.loads((live / "installed.json").read_text(encoding="utf-8"))
    assert receipt["target"] == "harness"
    assert "deployed_at" in receipt
    assert "source_commit" in receipt  # a bare tmp dir has no HEAD -> None, not a crash
    assert receipt["source_commit"] is None
    assert receipt["backup_path"] is not None  # live pre-existed -> backed up

    # per-file sha256 is CONTENT-based: it matches the deployed bytes exactly
    assert receipt["files"]["modules.py"] == _sha(live / "modules.py")
    assert receipt["files"][os.path.join("sub", "a.py")] == _sha(live / "sub" / "a.py")

    # write/EXTEND: the pre-existing owner key survives the receipt refresh
    assert receipt["custom"] == "keep-me"


# --------------------------------------------------------------------------- #
# 6. receipt provenance: caller-supplied source_commit wins
# --------------------------------------------------------------------------- #


def test_deploy_receipt_records_caller_supplied_source_commit(tmp_path, monkeypatch):
    # PROVENANCE: a caller-supplied source_commit (e.g. the runner's
    # `git rev-parse HEAD`) is recorded verbatim, taking precedence over the
    # source tree's own HEAD -- so the receipt is auditable even when deploying
    # from a non-git archive (where _source_commit would yield None).
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")
    src = _src_tree(tmp_path / "src", {"modules.py": "# m\n"})
    live = tmp_path / "live"

    code = deploy(
        source_dir=src,
        live_dir=live,
        target="harness",
        source_commit="deadbeefcafe1234567890abcdef000000000000",
    )

    assert code == 0
    receipt = json.loads((live / "installed.json").read_text(encoding="utf-8"))
    assert receipt["source_commit"] == "deadbeefcafe1234567890abcdef000000000000"


# --------------------------------------------------------------------------- #
# target validation (one target per call)
# --------------------------------------------------------------------------- #


def test_deploy_rejects_unknown_target(tmp_path):
    with pytest.raises(ValueError):
        deploy(source_dir=tmp_path / "src", live_dir=tmp_path / "live", target="bogus")
