"""Tests for the Program E Step 2 driver, `e2e/run_runnability.py`.

This driver had NO test on either side of the reconcile, which is how two contracts silently
drifted apart:

  * the gaps file NAME and SHAPE that `e2e/run_fanout.py` reads back, and
  * the R1 invariant that the runnability unit is submitted with NO github write token.

Both are pinned below. The R1 test is written so it FIRES on the known-broken state (a driver
that passes `extra_env={"GITHUB_TOKEN": ...}`) rather than merely passing on the fixed one — a
probe that is quiet in both states measures nothing.

The driver is importable at all only because it wraps its work in `main(argv)`; the earlier
module-level form submitted a billable Databricks job as an import side effect.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
DRIVER = SCRIPTS / "e2e" / "run_runnability.py"


def _load():
    """Import e2e/run_runnability.py by path (e2e/ is a script dir, not a package)."""
    spec = importlib.util.spec_from_file_location("_run_runnability_under_test", DRIVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub(mod, monkeypatch, tmp_path, ok=True, gaps=(), text="artifact body"):
    """Point the driver's output at tmp_path and record the run_E call it makes."""
    calls = []

    def fake_runnability(*args, **kwargs):
        calls.append((args, kwargs))
        return ok, list(gaps), text

    monkeypatch.setattr(mod.run_E, "runnability", fake_runnability)
    monkeypatch.setattr(mod, "__file__", str(tmp_path / "run_runnability.py"))
    return calls


def test_missing_args_is_usage_error(capsys):
    mod = _load()
    assert mod.main([]) == 2
    assert mod.main(["only-repo"]) == 2
    err = capsys.readouterr().err
    assert "usage: run_runnability.py <repo> <clone_url>" in err


def test_no_hardcoded_repo_default(monkeypatch, tmp_path):
    """A billable submit must never happen on a defaulted repo/url."""
    mod = _load()
    calls = _stub(mod, monkeypatch, tmp_path)
    assert mod.main([]) == 2
    assert calls == [], "argv-less invocation must not reach run_E.runnability"


def test_success_writes_run_fanout_contract(monkeypatch, tmp_path, capsys):
    """Name and shape must match what e2e/run_fanout.py reads: _E_<repo>_gaps.json -> dict."""
    mod = _load()
    _stub(mod, monkeypatch, tmp_path, ok=True, gaps=["src/a.py", "src/b.py"])
    rc = mod.main(["env-inspector", "https://example.invalid/env-inspector"])
    assert rc == 0
    out = tmp_path / "_E_env-inspector_gaps.json"
    assert out.exists(), (
        f"expected {out.name}; run_fanout.py defaults to that exact name"
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    # run_fanout.py does `.get("gaps", [])` -- a bare list here would raise AttributeError.
    assert payload == {
        "repo": "env-inspector",
        "ok": True,
        "gaps": ["src/a.py", "src/b.py"],
    }
    outp = capsys.readouterr().out
    assert "RUNNABILITY env-inspector ok=True gaps=2" in outp
    assert "SUCCESS: runnability env-inspector -> 2 uncovered-file gap(s)" in outp
    assert "  gap: src/a.py" in outp and "  gap: src/b.py" in outp


def test_clone_url_is_forwarded(monkeypatch, tmp_path):
    mod = _load()
    calls = _stub(mod, monkeypatch, tmp_path)
    assert mod.main(["repo-x", "https://example.invalid/repo-x"]) == 0
    (args, _kwargs) = calls[0]
    assert args[:2] == ("repo-x", "https://example.invalid/repo-x")


def test_r1_no_github_token_is_passed(monkeypatch, tmp_path):
    """R1: the node clones READ-ONLY and only commits LOCALLY, so no write token is provisioned.

    Both-states note: revert the driver to `run_E.runnability(repo, url,
    extra_env={"GITHUB_TOKEN": TOKEN_REF})` and this test fails -- it discriminates.
    """
    mod = _load()
    calls = _stub(mod, monkeypatch, tmp_path)
    assert mod.main(["repo-x", "https://example.invalid/repo-x"]) == 0
    (args, kwargs) = calls[0]
    assert "extra_env" not in kwargs, "no env may be injected into the runnability unit"
    blob = repr(args) + repr(kwargs)
    assert "GITHUB_TOKEN" not in blob
    assert "github_token" not in blob
    assert not hasattr(mod, "TOKEN_REF"), (
        "the write-token reference must stay deleted (R1)"
    )


def test_failure_returns_1_and_still_persists_verdict(monkeypatch, tmp_path, capsys):
    mod = _load()
    _stub(mod, monkeypatch, tmp_path, ok=False, gaps=(), text="")
    rc = mod.main(["repo-x", "https://example.invalid/repo-x"])
    assert rc == 1
    payload = json.loads((tmp_path / "_E_repo-x_gaps.json").read_text(encoding="utf-8"))
    assert payload == {"repo": "repo-x", "ok": False, "gaps": []}
    outp = capsys.readouterr().out
    assert "RUNNABILITY repo-x ok=False gaps=0" in outp
    assert "FAILED: runnability preflight for repo-x did not reach DONE" in outp
    # The artifact echo must survive onto the failure path: a non-DONE verdict carries no gaps,
    # so the node's stdout is the only diagnostic there is.
    assert f"=== artifact (first {mod.ARTIFACT_PREVIEW_CHARS} chars) ===" in outp
    assert "(empty)" in outp


def test_artifact_preview_is_truncated(monkeypatch, tmp_path, capsys):
    mod = _load()
    long_text = "x" * (mod.ARTIFACT_PREVIEW_CHARS + 500)
    _stub(mod, monkeypatch, tmp_path, ok=True, gaps=(), text=long_text)
    assert mod.main(["repo-x", "https://example.invalid/repo-x"]) == 0
    outp = capsys.readouterr().out
    assert "x" * mod.ARTIFACT_PREVIEW_CHARS in outp
    assert "x" * (mod.ARTIFACT_PREVIEW_CHARS + 1) not in outp


def test_argv_defaults_to_sys_argv(monkeypatch, tmp_path):
    mod = _load()
    _stub(mod, monkeypatch, tmp_path, ok=True, gaps=["g"])
    monkeypatch.setattr(
        sys, "argv", ["run_runnability.py", "repo-y", "https://example.invalid/repo-y"]
    )
    assert mod.main() == 0
    assert (tmp_path / "_E_repo-y_gaps.json").exists()
