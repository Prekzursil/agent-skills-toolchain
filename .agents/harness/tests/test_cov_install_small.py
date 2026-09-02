"""Branch-coverage completion for the small harness install/support modules.

Every test here documents CURRENT behavior of an already-shipped code path and
asserts a REAL observable result (a returned value, a written file, a DriftItem
status/detail, a redacted string, a raised error). No source is changed.

Cross-platform by construction: no real OS symlink is ever created (symlink
OBSERVATION is monkeypatched instead, since Windows needs privilege), platform
gates are monkeypatched so both arcs run on any host, and every path assertion
compares ``Path`` objects (never a hardcoded separator). Deterministic: no
network, no real sleeps, no reliance on ``git`` being installed.

Targets (uncovered lines/arcs the enshrined suite left open):
  models.py       78, 87-95            (HookResult.failed_open / to_dict)
  redaction.py    55, 62-65            (max_chars truncation / _to_text)
  registration.py 147                  (unsupported provider guard)
  storage.py      19-20                (atomic_write_text unlink-OSError swallow)
  install.py      129,191,194,196,     (_read_object, _norm_path prefixes,
                  219->221,221->223,    _structured_diff empty arcs,
                  315-316,334,489,584,  skills-symlink error/ok, codex backup,
                  605-606,615-618,      _managed_files, _default_source/_live,
                  653-654,676-677,680,  lock-release + _source_commit,
                  803->805              parity-mismatch on a brand-new target)

SKIPPED (documented, not covered here): install.py lines 59-62 are the
``if __package__ in {None, ""}`` dual-import (script-vs-package) fallback, and
line 887 is the ``if __name__ == "__main__": raise SystemExit(main())`` module
main-guard -- neither is reachable when the module is imported as a package.
"""

from __future__ import annotations

import io
import json
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from harness import install as I
from harness import models, redaction, registration, storage


@pytest.fixture(autouse=True)
def _isolate_state_root(tmp_path, monkeypatch):
    """Never let a harness state-root default resolve to the real home dir."""
    monkeypatch.setenv("AGENT_HARNESS_STATE_ROOT", str(tmp_path / "state"))


# --------------------------------------------------------------------------- #
# models.HookResult -- failed_open (78) + to_dict (87-95)
# --------------------------------------------------------------------------- #


def test_hookresult_failed_open_has_lowercased_failure_status():
    result = models.HookResult.failed_open("SessionStart")

    assert result.status == "FAILED:hook-sessionstart"
    assert result.action == "allow"
    assert result.reason_code == "internal_error"
    assert result.additional_context == []
    assert result.continuation is None


def test_hookresult_to_dict_omits_continuation_when_none_and_copies_context():
    result = models.HookResult.success(
        action="inject", reason_code="drift", additional_context=["a", "b"]
    )

    payload = result.to_dict()

    assert payload == {
        "status": "SUCCESS:hook",
        "action": "inject",
        "reason_code": "drift",
        "additional_context": ["a", "b"],
    }
    assert "continuation" not in payload
    # the emitted list is a defensive copy -- mutating it must not touch the result
    payload["additional_context"].append("leak")
    assert result.additional_context == ["a", "b"]


def test_hookresult_to_dict_includes_continuation_when_set():
    result = models.HookResult.success(continuation="resume-from-here")

    payload = result.to_dict()

    assert payload["continuation"] == "resume-from-here"
    assert payload["action"] == "allow"
    assert payload["status"] == "SUCCESS:hook"


# --------------------------------------------------------------------------- #
# redaction -- max_chars truncation (55) + _to_text non-str paths (62-65)
# --------------------------------------------------------------------------- #


def test_redact_text_truncates_when_longer_than_max_chars():
    out = redaction.redact_text("x" * 200, max_chars=40)

    # keeps max_chars-16 body chars, then the marker on its own line
    assert out == "x" * 24 + "\n[TRUNCATED]"
    assert out.endswith("\n[TRUNCATED]")
    assert len(out) < 200


def test_contains_secret_serializes_non_str_value_via_json():
    # a non-str value is routed through _to_text -> json.dumps (the happy path)
    assert redaction.contains_secret(["prefix", "AKIAIOSFODNN7EXAMPLE"]) is True
    assert redaction.contains_secret({"note": "nothing sensitive here"}) is False


def test_contains_secret_falls_back_to_repr_when_json_dumps_raises():
    # mixed-type dict keys make json.dumps(sort_keys=True) raise a TypeError, so
    # _to_text falls back to repr(value); the secret in that repr is still found.
    unsortable = {1: "int-key", "AKIAIOSFODNN7EXAMPLE": 2}

    assert redaction.contains_secret(unsortable) is True


# --------------------------------------------------------------------------- #
# registration -- unsupported provider guard (147)
# --------------------------------------------------------------------------- #


def test_build_hooks_rejects_unsupported_provider():
    with pytest.raises(ValueError, match="unsupported provider: gemini"):
        registration.build_hooks("gemini")


# --------------------------------------------------------------------------- #
# storage -- atomic_write_text swallows a cleanup unlink OSError (19-20)
# --------------------------------------------------------------------------- #


def test_atomic_write_text_swallows_unlink_oserror(tmp_path, monkeypatch):
    target = tmp_path / "out.txt"

    def raising_unlink(self, *args, **kwargs):
        raise OSError("cleanup unlink refused")

    monkeypatch.setattr(Path, "unlink", raising_unlink)

    # the temp cleanup unlink raises, but the payload was already atomically moved
    storage.atomic_write_text(target, "payload-123")

    assert target.read_text(encoding="utf-8") == "payload-123"


# --------------------------------------------------------------------------- #
# install._read_object -- non-object JSON rejection (129)
# --------------------------------------------------------------------------- #


def test_read_object_rejects_non_dict_json(tmp_path):
    path = tmp_path / "arr.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with pytest.raises(ValueError, match="expected JSON object"):
        I._read_object(path)


# --------------------------------------------------------------------------- #
# install._norm_path -- empty (191) + extended-length prefix stripping (194/196)
# --------------------------------------------------------------------------- #


def test_norm_path_empty_and_none_return_empty_string():
    assert I._norm_path("") == ""
    assert I._norm_path(None) == ""


def test_norm_path_strips_unc_extended_length_prefix():
    # \\?\UNC\server\share\skills normalizes equal to \\server\share\skills
    unc = "\\\\?\\UNC\\server\\share\\skills"
    plain = "\\\\server\\share\\skills"

    assert I._norm_path(unc) == I._norm_path(plain)


def test_norm_path_strips_plain_extended_length_prefix():
    # \\?\C:\dir\skills normalizes equal to C:\dir\skills
    prefixed = "\\\\?\\C:\\dir\\skills"
    plain = "C:\\dir\\skills"

    assert I._norm_path(prefixed) == I._norm_path(plain)


# --------------------------------------------------------------------------- #
# install._structured_diff -- the empty-bucket skip arcs (219->221, 221->223)
# --------------------------------------------------------------------------- #


def test_structured_diff_reports_only_removed_when_nothing_added():
    # added bucket empty -> skip past it to the removed bucket
    assert I._structured_diff({"a": 1, "b": 2}, {"a": 1}) == {"removed": ["b"]}


def test_structured_diff_reports_only_added_when_nothing_removed():
    # removed bucket empty -> skip past it to the changed bucket
    assert I._structured_diff({"a": 1}, {"a": 1, "b": 2}) == {"added": ["b"]}


# --------------------------------------------------------------------------- #
# install._reconcile_skills_symlink -- OSError (315-316) + pinned-ok (334)
# --------------------------------------------------------------------------- #


def test_reconcile_skills_symlink_reports_error_on_oserror(tmp_path, monkeypatch):
    def raising_observe(_link):
        raise OSError("readlink failed")

    monkeypatch.setattr(I, "_observe_symlink", raising_observe)
    baseline = {"skills_symlink": {"target": str(tmp_path / "expected")}}

    item = I._reconcile_skills_symlink(tmp_path / "skills", baseline)

    assert item.status == "error"
    assert item.managed is True
    assert item.detail == {"message": "OSError"}
    assert item.is_drift is True


def test_reconcile_skills_symlink_ok_when_pinned_without_target_and_is_symlink(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        I,
        "_observe_symlink",
        lambda _link: {"is_symlink": True, "target": str(tmp_path / "daily")},
    )
    # pinned (managed) but no target -> the only requirement is that it BE a symlink
    baseline = {"skills_symlink": {}}

    item = I._reconcile_skills_symlink(tmp_path / "skills", baseline)

    assert item.status == "ok"
    assert item.managed is True
    assert item.detail == {}
    assert item.is_drift is False


# --------------------------------------------------------------------------- #
# install.install -- backs up a PRE-EXISTING codex hooks file (489)
# --------------------------------------------------------------------------- #


def test_install_backs_up_existing_codex_hooks(tmp_path, monkeypatch):
    claude = tmp_path / "claude" / "settings.json"
    codex = tmp_path / "codex" / "hooks.json"
    backups = tmp_path / "backups"
    manifest = tmp_path / "installed.json"
    claude.parent.mkdir(parents=True, exist_ok=True)
    claude.write_text(
        json.dumps({"model": "opus", "hooks": {"stale": []}}), encoding="utf-8"
    )
    codex.parent.mkdir(parents=True, exist_ok=True)
    codex.write_text(json.dumps({"hooks": {"old": []}}), encoding="utf-8")

    monkeypatch.setattr(I, "CLAUDE_SETTINGS", claude)
    monkeypatch.setattr(I, "CODEX_HOOKS", codex)
    monkeypatch.setattr(I, "BACKUPS_DIR", backups)
    monkeypatch.setattr(I, "INSTALLED_MANIFEST", manifest)

    assert I.install(check=False) == 0

    # the pre-existing codex hooks were snapshotted into the timestamped backup
    codex_backups = list(backups.rglob("codex-hooks.json"))
    assert len(codex_backups) == 1
    assert json.loads(codex_backups[0].read_text(encoding="utf-8")) == {
        "hooks": {"old": []}
    }


# --------------------------------------------------------------------------- #
# install._managed_files -- missing root short-circuit (584)
# --------------------------------------------------------------------------- #


def test_managed_files_returns_empty_for_missing_root(tmp_path):
    assert I._managed_files(tmp_path / "does-not-exist") == {}


# --------------------------------------------------------------------------- #
# install._default_source -- non-harness targets (605-606)
# --------------------------------------------------------------------------- #


def test_default_source_for_skills_and_hooks_targets():
    assert I._default_source("skills").name == "skills"
    assert I._default_source("hooks").name == "hooks"


# --------------------------------------------------------------------------- #
# install._default_live -- skills/hooks targets + env overrides (615-618)
# --------------------------------------------------------------------------- #


def test_default_live_skills_honors_agents_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_LIVE_AGENTS_DIR", str(tmp_path / "agents"))

    assert I._default_live("skills") == tmp_path / "agents" / "skills"


def test_default_live_skills_falls_back_to_home_agents_without_env(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("HARNESS_LIVE_AGENTS_DIR", raising=False)
    monkeypatch.setattr(I, "HOME", tmp_path / "home")

    assert I._default_live("skills") == tmp_path / "home" / ".agents" / "skills"


def test_default_live_hooks_honors_hooks_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_LIVE_HOOKS_DIR", str(tmp_path / "myhooks"))

    assert I._default_live("hooks") == tmp_path / "myhooks"


def test_default_live_hooks_falls_back_to_claude_hooks_without_env(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("HARNESS_LIVE_HOOKS_DIR", raising=False)
    monkeypatch.setattr(I, "HOME", tmp_path / "home")

    assert I._default_live("hooks") == tmp_path / "home" / ".claude" / "hooks"


# --------------------------------------------------------------------------- #
# install._release_deploy_lock -- swallows an OSError on unlink (653-654)
# --------------------------------------------------------------------------- #


def test_release_deploy_lock_swallows_oserror(tmp_path, monkeypatch):
    lock = tmp_path / ".deploy.lock"
    lock.write_text("{}", encoding="utf-8")

    def raising_unlink(self, *args, **kwargs):
        raise OSError("cannot remove lock")

    monkeypatch.setattr(Path, "unlink", raising_unlink)

    # must not raise even though the unlink failed (finally-safe release)
    I._release_deploy_lock(lock)

    assert lock.exists()  # unlink was refused -> file remains, no crash


# --------------------------------------------------------------------------- #
# install._source_commit -- OSError (676-677) + success/blank (678->680, 680)
# --------------------------------------------------------------------------- #


def test_source_commit_returns_none_when_git_invocation_raises(tmp_path, monkeypatch):
    def raising_run(*args, **kwargs):
        raise OSError("git executable not found")

    monkeypatch.setattr(I.subprocess, "run", raising_run)

    assert I._source_commit(tmp_path) is None


def test_source_commit_returns_stripped_hash_on_success(tmp_path, monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="deadbeefcafe\n", stderr=""
        )

    monkeypatch.setattr(I.subprocess, "run", fake_run)

    assert I._source_commit(tmp_path) == "deadbeefcafe"


def test_source_commit_returns_none_when_stdout_is_blank(tmp_path, monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="   \n", stderr=""
        )

    monkeypatch.setattr(I.subprocess, "run", fake_run)

    assert I._source_commit(tmp_path) is None


# --------------------------------------------------------------------------- #
# install.deploy -- parity mismatch on a BRAND-NEW target (backup is None) 803->805
# --------------------------------------------------------------------------- #


def test_deploy_parity_mismatch_on_new_target_fails_without_restore(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(I, "BACKUPS_DIR", tmp_path / "backups")
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("candidate\n", encoding="utf-8")
    live = tmp_path / "live"  # does NOT pre-exist -> no last-known-good backup

    def corrupt():
        (live / "a.py").write_text("CORRUPTED\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = I.deploy(source_dir=src, live_dir=live, _after_write=corrupt)
    payload = json.loads(buf.getvalue())

    assert code == 1
    assert payload["status"] == "failed"
    assert payload["reason"] == "parity_mismatch"
    assert payload["mismatches"] == ["a.py"]
    # brand-new target -> backup was None -> nothing to restore from
    assert payload["restored_from"] is None
    # the corrupted file is left as-is (no backup existed to roll back to)
    assert (live / "a.py").read_text(encoding="utf-8") == "CORRUPTED\n"
    assert not (live / I.DEPLOY_LOCK_NAME).exists()
