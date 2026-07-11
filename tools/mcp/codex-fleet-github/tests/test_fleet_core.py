#!/usr/bin/env python3
"""Unit tests for fleet_core (no live gh / no network -- injected fake runner)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pytest

import fleet_core as core


# --------------------------------------------------------------------------- #
# a fake `gh` runner that routes by subcommand and records every call
# --------------------------------------------------------------------------- #
class FakeGh:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []
        self.workflow_rc = 0
        self.workflow_err = "boom"
        self.run_list_json = "[]"
        self.api_text: str | None = None
        self.search_json = "[]"
        self.search_rc = 0

    def __call__(self, args, token=""):
        self.calls.append((list(args), token))
        head = args[:2]
        if head == ["workflow", "run"]:
            return (
                self.workflow_rc,
                "",
                "" if self.workflow_rc == 0 else self.workflow_err,
            )
        if head == ["run", "list"]:
            return (0, self.run_list_json, "")
        if args[:1] == ["api"]:
            if self.api_text is None:
                return (1, "", "Not Found")
            return (0, self.api_text, "")
        if head == ["search", "prs"]:
            return (self.search_rc, self.search_json, "")
        return (0, "", "")


def _fresh_run(url="https://github.com/o/r/actions/runs/9", run_id=9):
    now_iso = datetime.now(timezone.utc).isoformat()
    return json.dumps(
        [{"databaseId": run_id, "url": url, "status": "queued", "createdAt": now_iso}]
    )


_SAMPLE_TARGETS = """\
defaults: { model: gpt-5.6-sol, effort: max, max_changed_files: 40 }
targets:
  - repo: Prekzursil/Reframe
    enabled: true
    tasks: ["Documentation only: tidy the README, no code changes."]
    max_changed_files: 25
  - repo: Prekzursil/momentstudio
    enabled: false
    tasks: []
  - repo: Prekzursil/WebCoder
    enabled: true
    tasks: []
"""


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("good", ["o/r", "Prekzursil/Reframe", "a.b/c-d_e"])
def test_validate_repo_ok(good):
    assert core.validate_repo(good) == good


@pytest.mark.parametrize("bad", ["", "no-slash", "a/b/c", "-x/y", "a/..", "../y", 5])
def test_validate_repo_rejects(bad):
    with pytest.raises(core.FleetError):
        core.validate_repo(bad)


def test_validate_task_defaults_and_limits():
    assert core.validate_task("do it") == "do it"
    with pytest.raises(core.FleetError):
        core.validate_task("   ")
    with pytest.raises(core.FleetError):
        core.validate_task("a\x00b")
    with pytest.raises(core.FleetError):
        core.validate_task("x" * (core.MAX_TASK_LEN + 1))


def test_validate_model_default_and_reject():
    assert core.validate_model("") == core.DEFAULT_MODEL
    assert core.validate_model(None) == core.DEFAULT_MODEL
    assert core.validate_model("gpt-5.6-sol") == "gpt-5.6-sol"
    assert core.validate_model("o4_mini.hi") == "o4_mini.hi"
    with pytest.raises(core.FleetError):
        core.validate_model("bad slug!")


@pytest.mark.parametrize("bad", ["gpt:5", "gpt+5", ".hidden", "-lead", "a/b", "x y"])
def test_validate_model_tightened_rejects(bad):
    # tightened _MODEL_RE (^[A-Za-z0-9][A-Za-z0-9._-]*$): no ':' '+' '/' space,
    # and must start alphanumeric (parity with the runner's validate step)
    with pytest.raises(core.FleetError):
        core.validate_model(bad)


def test_validate_effort_allowlist():
    assert core.validate_effort("") == core.DEFAULT_EFFORT
    assert core.validate_effort("HIGH") == "high"
    with pytest.raises(core.FleetError):
        core.validate_effort("turbo")


def test_validate_max_changed_files():
    assert core.validate_max_changed_files(None) == core.DEFAULT_MAX_CHANGED_FILES
    assert core.validate_max_changed_files(0) == core.DEFAULT_MAX_CHANGED_FILES
    assert core.validate_max_changed_files("25") == 25
    with pytest.raises(core.FleetError):
        core.validate_max_changed_files(0.0 - 1)
    with pytest.raises(core.FleetError):
        core.validate_max_changed_files(5000)
    with pytest.raises(core.FleetError):
        core.validate_max_changed_files("abc")


def test_validate_base_branch():
    assert core.validate_base_branch("") == ""
    assert core.validate_base_branch("main") == "main"
    assert core.validate_base_branch("feat/x-1") == "feat/x-1"
    for bad in ["-x", "a..b", "has space", "bad~ref"]:
        with pytest.raises(core.FleetError):
            core.validate_base_branch(bad)


# --------------------------------------------------------------------------- #
# dispatch token (env priority + keyring fallback) -- never auth.json
# --------------------------------------------------------------------------- #
def test_dispatch_token_env_priority():
    env = {"CODEX_DISPATCH_PAT": "pat", "GH_TOKEN": "gh", "GITHUB_TOKEN": "gt"}
    assert core.dispatch_token(env) == "pat"
    assert core.dispatch_token({"GH_TOKEN": "gh"}) == "gh"
    assert core.dispatch_token({"GITHUB_TOKEN": "gt"}) == "gt"


def test_dispatch_token_keyring_fallback():
    seen = {}

    def fake_keyring(service, user):
        seen["args"] = (service, user)
        return "from-keyring"

    got = core.dispatch_token({}, keyring_lookup=fake_keyring)
    assert got == "from-keyring"
    assert seen["args"] == ("codex-fleet-github", "dispatch")


def test_dispatch_token_empty_when_nothing():
    assert core.dispatch_token({}, keyring_lookup=lambda *_: "") == ""


# --------------------------------------------------------------------------- #
# run_gh chokepoint: token via env, never argv; missing-binary handling
# --------------------------------------------------------------------------- #
def test_run_gh_injects_token_via_env(monkeypatch):
    # Use the Python interpreter as a stand-in for `gh`: it echoes GH_TOKEN.
    monkeypatch.setenv("CODEX_GH_BIN", sys.executable)
    code, out, _err = core.run_gh(
        ["-c", "import os;print(os.environ.get('GH_TOKEN',''))"], token="SEKRET"
    )
    assert code == 0
    assert out.strip() == "SEKRET"  # token reached the child ENV, not argv


def test_run_gh_missing_binary(monkeypatch):
    monkeypatch.setenv("CODEX_GH_BIN", "definitely-not-a-real-gh-binary-xyz")
    code, _out, err = core.run_gh(["--version"])
    assert code == 127
    assert "gh CLI not found" in err


# --------------------------------------------------------------------------- #
# build args + dispatch_one
# --------------------------------------------------------------------------- #
def test_build_dispatch_args_shape():
    args = core.build_dispatch_args("o/r", "t", "m", "max", 40)
    assert args[:5] == [
        "workflow",
        "run",
        "codex-runner.yml",
        "--repo",
        "Prekzursil/agent-skills-toolchain",
    ]
    assert "-f" in args and "target_repo=o/r" in args
    assert "task=t" in args and "model=m" in args and "effort=max" in args
    assert "max_changed_files=40" in args
    assert "base_branch=" not in " ".join(args)  # omitted when blank
    with_base = core.build_dispatch_args("o/r", "t", "m", "max", 40, "dev")
    assert "base_branch=dev" in with_base


def test_dispatch_one_success_resolves_run_url():
    fake = FakeGh()
    fake.run_list_json = _fresh_run()
    out = core.dispatch_one("o/r", "do it", token="t", runner=fake)
    assert out["ok"] is True
    assert out["repo"] == "o/r"
    assert out["model"] == core.DEFAULT_MODEL and out["effort"] == "max"
    assert out["run_url"].endswith("/runs/9")
    # first call is the dispatch, carrying the validated -f inputs
    disp_args = fake.calls[0][0]
    assert disp_args[:2] == ["workflow", "run"]
    assert "target_repo=o/r" in disp_args


def test_dispatch_one_failure_returns_error():
    fake = FakeGh()
    fake.workflow_rc = 1
    out = core.dispatch_one("o/r", "do it", token="t", runner=fake)
    assert out["ok"] is False
    assert "boom" in out["error"]
    # a failed dispatch must not go on to poll for a run
    assert all(c[0][:2] != ["run", "list"] for c in fake.calls)


def test_dispatch_one_invalid_repo_raises():
    with pytest.raises(core.FleetError):
        core.dispatch_one("bad repo", "t", token="t", runner=FakeGh())


def test_token_never_appears_on_argv():
    fake = FakeGh()
    fake.run_list_json = _fresh_run()
    core.dispatch_one("o/r", "do it", token="SUPERSECRET", runner=fake)
    for args, tok in fake.calls:
        assert "SUPERSECRET" not in " ".join(args)
        assert tok == "SUPERSECRET"  # travels only via the dedicated channel


# --------------------------------------------------------------------------- #
# run matching helpers
# --------------------------------------------------------------------------- #
def test_iso_to_epoch_and_newest_since():
    assert core._iso_to_epoch("nope") is None
    assert core._iso_to_epoch(None) is None
    now = datetime.now(timezone.utc)
    runs = [
        {"createdAt": "2000-01-01T00:00:00Z", "url": "old"},
        {"createdAt": now.isoformat(), "url": "new"},
    ]
    got = core._newest_since(runs, now.timestamp())
    assert got["url"] == "new"
    assert core._newest_since(runs[:1], now.timestamp()) is None


def test_find_recent_run_no_sleep_when_absent():
    fake = FakeGh()  # empty list
    got = core.find_recent_run(
        0.0, token="t", runner=fake, attempts=2, delay=0, sleep=lambda *_: None
    )
    assert got is None


# --------------------------------------------------------------------------- #
# targets parsing + resolution
# --------------------------------------------------------------------------- #
def test_parse_targets_and_enabled():
    pytest.importorskip("yaml")
    parsed = core.parse_targets(_SAMPLE_TARGETS)
    assert parsed["defaults"]["model"] == "gpt-5.6-sol"
    rows = core.enabled_targets(parsed)
    repos = [r["repo"] for r in rows]
    assert repos == ["Prekzursil/Reframe", "Prekzursil/WebCoder"]  # momentstudio off
    assert rows[0]["max_changed_files"] == 25


def test_parse_targets_rejects_non_mapping():
    pytest.importorskip("yaml")
    with pytest.raises(core.FleetError):
        core.parse_targets("- just\n- a list\n")


def test_resolve_repos_explicit_wins():
    rows, source, notes = core.resolve_fleet_repos(["a/b", "c/d"], token="t")
    assert [r["repo"] for r in rows] == ["a/b", "c/d"]
    assert source == "explicit" and notes == []


def test_resolve_repos_from_targets(monkeypatch):
    pytest.importorskip("yaml")
    fake = FakeGh()
    fake.api_text = _SAMPLE_TARGETS
    rows, source, _notes = core.resolve_fleet_repos(
        None, token="t", runner=fake, environ={}
    )
    assert source == "codex-targets.yml"
    assert [r["repo"] for r in rows] == ["Prekzursil/Reframe", "Prekzursil/WebCoder"]


def test_resolve_repos_local_file(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "codex-targets.yml"
    path.write_text(_SAMPLE_TARGETS, encoding="utf-8")
    env = {"CODEX_TARGETS_FILE": str(path)}
    rows, source, _notes = core.resolve_fleet_repos(None, token="t", environ=env)
    assert source == "codex-targets.yml"
    assert {r["repo"] for r in rows} == {"Prekzursil/Reframe", "Prekzursil/WebCoder"}


def test_resolve_repos_fail_closed_on_load_failure():
    # api_text None -> gh api fails -> no config, no opt-in -> RAISE (fail-closed)
    fake = FakeGh()
    with pytest.raises(core.FleetError) as exc:
        core.resolve_fleet_repos(None, token="t", runner=fake, environ={})
    msg = str(exc.value)
    assert "fail-closed" in msg
    assert "codex-targets.yml unavailable" in msg
    assert "CODEX_FLEET_ALLOW_FALLBACK" in msg


def test_resolve_repos_fail_closed_on_zero_enabled():
    pytest.importorskip("yaml")
    fake = FakeGh()
    # a well-formed targets file whose only entry is disabled -> zero enabled
    fake.api_text = "targets:\n  - repo: Prekzursil/momentstudio\n    enabled: false\n"
    with pytest.raises(core.FleetError) as exc:
        core.resolve_fleet_repos(None, token="t", runner=fake, environ={})
    assert "no enabled targets" in str(exc.value)


def test_resolve_repos_builtin_fallback_only_with_opt_in():
    fake = FakeGh()  # api_text None -> gh api fails
    rows, source, notes = core.resolve_fleet_repos(
        None, token="t", runner=fake, environ={"CODEX_FLEET_ALLOW_FALLBACK": "1"}
    )
    assert source == "builtin-fallback"
    repos = {r["repo"] for r in rows}
    # ONLY the 4 curated PUBLIC repos -- no private repos, no momentstudio
    assert repos == {
        "Prekzursil/Reframe",
        "Prekzursil/env-inspector",
        "Prekzursil/omniaudit-mcp",
        "Prekzursil/WebCoder",
    }
    assert "Prekzursil/agent-skills-toolchain" not in repos  # private stays off
    assert "Prekzursil/momentstudio" not in repos  # payment/auth stays off
    assert len(rows) == 4
    assert notes and "CODEX_FLEET_ALLOW_FALLBACK" in notes[0]


@pytest.mark.parametrize("flag", ["0", "false", "no", "", "  "])
def test_resolve_repos_opt_in_requires_truthy_flag(flag):
    fake = FakeGh()  # api fails
    with pytest.raises(core.FleetError):
        core.resolve_fleet_repos(
            None, token="t", runner=fake, environ={"CODEX_FLEET_ALLOW_FALLBACK": flag}
        )


# --------------------------------------------------------------------------- #
# status: runs + PRs
# --------------------------------------------------------------------------- #
def test_status_merges_runs_and_prs():
    fake = FakeGh()
    fake.run_list_json = json.dumps(
        [{"databaseId": 1, "url": "u", "status": "completed"}]
    )
    labelled = [
        {"url": "https://pr/1", "number": 1, "title": "Codex: automated change"}
    ]
    fake.search_json = json.dumps(labelled)
    out = core.status(5, token="t", runner=fake)
    assert out["ok"] is True
    assert out["recent_runs"][0]["databaseId"] == 1
    # two search passes (label + title) both return pr#1 -> de-duped to one
    assert len(out["open_prs"]) == 1
    assert out["open_prs"][0]["url"] == "https://pr/1"


def test_status_notes_run_failure():
    fake = FakeGh()

    def failing(args, token=""):
        if args[:2] == ["run", "list"]:
            return (1, "", "rate limited")
        return fake(args, token)

    out = core.status(5, token="t", runner=failing)
    assert out["recent_runs"] == []
    assert any("runs unavailable" in n for n in out["notes"])


def test_list_open_prs_dedupes_across_passes():
    fake = FakeGh()
    fake.search_json = json.dumps([{"url": "https://pr/7", "number": 7}])
    prs, notes = core.list_open_prs(token="t", runner=fake)
    assert len(prs) == 1 and notes == []


# --------------------------------------------------------------------------- #
# decomposition + orchestrate + sweep
# --------------------------------------------------------------------------- #
def test_decompose_plan_one_task_per_repo():
    items = core.decompose_plan("Add a LICENSE file", ["o/alpha", "o/beta"])
    assert [i["repo"] for i in items] == ["o/alpha", "o/beta"]
    assert "Add a LICENSE file" in items[0]["task"]
    assert "`alpha`" in items[0]["task"]  # scoped to the bare repo name


def test_orchestrate_no_dispatch_is_safe():
    out = core.orchestrate("Do X", ["o/a", "o/b"], token="t", runner=FakeGh())
    assert out["dispatched"] is False
    assert out["count"] == 2
    assert "dispatches" not in out  # nothing fired


def test_orchestrate_with_dispatch_fires_each():
    fake = FakeGh()
    fake.run_list_json = _fresh_run()
    out = core.orchestrate(
        "Do X", ["o/a", "o/b"], dispatch=True, token="t", runner=fake
    )
    assert out["dispatched"] is True
    assert out["dispatched_ok"] == 2
    workflow_runs = [c for c in fake.calls if c[0][:2] == ["workflow", "run"]]
    assert len(workflow_runs) == 2


def test_sweep_explicit_repos_dispatches_each():
    fake = FakeGh()
    out = core.sweep("tidy docs", ["o/a", "o/b"], token="t", runner=fake)
    assert out["repos_source"] == "explicit"
    assert out["requested"] == 2
    assert out["dispatched_ok"] == 2
    assert out["ok"] is True


def test_sweep_fail_closed_when_no_config_and_no_repos():
    # no explicit repos + unreachable codex-targets.yml + no opt-in -> RAISE,
    # NEVER a silent fan-out to a fallback fleet
    fake = FakeGh()  # api fails
    with pytest.raises(core.FleetError):
        core.sweep("tidy docs", None, token="t", runner=fake, environ={})
    # and crucially: nothing was dispatched
    assert all(c[0][:2] != ["workflow", "run"] for c in fake.calls)


def test_orchestrate_dispatch_fail_closed_when_no_config_and_no_repos():
    fake = FakeGh()  # api fails
    with pytest.raises(core.FleetError):
        core.orchestrate(
            "Do X", None, dispatch=True, token="t", runner=fake, environ={}
        )
    assert all(c[0][:2] != ["workflow", "run"] for c in fake.calls)


def test_sweep_applies_per_repo_max_changed_files(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "codex-targets.yml"
    path.write_text(_SAMPLE_TARGETS, encoding="utf-8")
    fake = FakeGh()
    out = core.sweep(
        "tidy",
        None,
        token="t",
        runner=fake,
        environ={"CODEX_TARGETS_FILE": str(path)},
    )
    assert out["repos_source"] == "codex-targets.yml"
    # Reframe overrides to 25; find its dispatch call and confirm the -f value
    reframe = [
        c
        for c in fake.calls
        if c[0][:2] == ["workflow", "run"] and "target_repo=Prekzursil/Reframe" in c[0]
    ]
    assert reframe and "max_changed_files=25" in reframe[0][0]


def test_default_fleet_catalogue_only_curated_public_enabled():
    fleet = core.default_fleet()
    assert len(fleet) == 26  # full owned-repo catalogue
    enabled = [r["repo"] for r in fleet if r["enabled"]]
    # ONLY the 4 curated public repos are enabled
    assert enabled == [
        "Prekzursil/Reframe",
        "Prekzursil/env-inspector",
        "Prekzursil/omniaudit-mcp",
        "Prekzursil/WebCoder",
    ]
    disabled = {r["repo"] for r in fleet if not r["enabled"]}
    assert len(disabled) == 22
    # private repos + payment/auth surface must be disabled
    assert "Prekzursil/agent-skills-toolchain" in disabled
    assert "Prekzursil/security-kb" in disabled
    assert "Prekzursil/momentstudio" in disabled
    assert "Prekzursil/quality-zero-platform" in disabled  # non-curated public


def test_default_fleet_enabled_and_disabled_are_disjoint():
    fleet = core.default_fleet()
    enabled = {r["repo"] for r in fleet if r["enabled"]}
    disabled = {r["repo"] for r in fleet if not r["enabled"]}
    assert enabled.isdisjoint(disabled)


def test_config_accessors_env_override(monkeypatch):
    monkeypatch.setenv("CODEX_RUNNER_REF", "feat/x")
    monkeypatch.setenv("CODEX_RUNNER_REPO", "Owner/runner")
    assert core.runner_ref() == "feat/x"
    assert core.runner_repo() == "Owner/runner"
    assert core.fleet_owner() == "Owner"
    assert "Owner/runner" in core.actions_url()
