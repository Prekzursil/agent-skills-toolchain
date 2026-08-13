#!/usr/bin/env python3
"""Tests for hook_predeploy_gate.

Every case here exists because the gate got that specific thing WRONG at least once while it was
being built, or because a sibling probe in this audit did. They are regression tests for measured
defects, not coverage decoration:

  * `manifest_checks` reading the event DICT instead of its `checks` list -- the false parity that
    survived four successive probes and reported "3 modules" for every event on both sides.
  * wiredness taken from the manifest alone, which scored both blocking security hooks as unwired.
  * wiredness taken as the UNION of both trees, which made the gate assert "the live harness runs
    this file" about a repo-declared, undeployed script.
  * a regex containing `\\s` classified as a lost PATH -- a label the reader can see is wrong.
  * the gate reporting clean when it cannot read the live tree at all.

Run: python -m pytest command-center/hook-audit/test_hook_predeploy_gate.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hook_predeploy_gate as gate  # noqa: E402


# --------------------------------------------------------------- direction classification


@pytest.mark.parametrize(
    ("repo", "live", "expected"),
    [
        ("def f():\n    return 1\n", "def f():\n    return 1\n", "EQUAL"),
        (
            "def f():\n    pass\ndef g():\n    pass\n",
            "def f():\n    pass\n",
            "REPO-AHEAD",
        ),
        (
            "def f():\n    pass\n",
            "def f():\n    pass\ndef g():\n    pass\n",
            "LIVE-AHEAD",
        ),
        (
            "def f():\n    pass\ndef g():\n    pass\n",
            "def f():\n    pass\ndef h():\n    pass\n",
            "DIVERGED",
        ),
    ],
)
def test_direction_arms(repo: str, live: str, expected: str) -> None:
    assert gate.classify_direction(repo, live) == expected


def test_crlf_alone_is_not_drift() -> None:
    """windows-shell 8b. Counting CRLF as drift manufactures a flood of false findings."""
    body = "def f():\n    return 1\n"
    assert gate.classify_direction(body, body.replace("\n", "\r\n")) == "EQUAL"


def test_trailing_whitespace_is_not_drift() -> None:
    """The behaviour `rstrip` alone carries.

    CRLF is defended twice -- the `\\r\\n` replace AND the rstrip -- so removing either one on
    its own is an EQUIVALENT mutant and a CRLF test can never distinguish them. Trailing
    whitespace is the case only rstrip handles, and a formatter stripping it must not register
    as a behaviour fork.
    """
    assert gate.classify_direction("x = 1\n", "x = 1   \n") == "EQUAL"


def test_comment_only_change_is_not_drift() -> None:
    assert gate.classify_direction("# a\nx = 1\n", "# b\nx = 1\n") == "EQUAL"


def test_indentation_change_is_drift() -> None:
    """A block moved under an `if` changes behaviour, so indentation must NOT normalise away."""
    assert gate.classify_direction("x = 1\n", "if q:\n    x = 1\n") == "DIVERGED"


# --------------------------------------------------------------- literal classification


@pytest.mark.parametrize(
    ("literal", "prefix"),
    [
        ("HOOK_DISPATCH_WALL_CAP", "ENV:"),
        (".claude/hooks/_dispatch", "PATH:"),
        (r"(?:def|class)\s+([A-Za-z_]\w{2,})", "RE:"),
        (r"^\d{4}-\d{2}-\d{2}$", "RE:"),
        ("x" * 45, "MSG:"),
    ],
)
def test_literal_classification(literal: str, prefix: str) -> None:
    assert gate.classify_literal(literal).startswith(prefix)


def test_regex_is_never_labelled_path() -> None:
    """The measured false label: `\\s` is a backslash, so a naive path test claimed a PATH."""
    assert not gate.classify_literal(r"(?:a|b)\s+c").startswith("PATH:")


def test_short_noise_literal_is_dropped() -> None:
    assert gate.classify_literal("ok") == ""


# --------------------------------------------------------------- capability markers


def test_marker_loss_is_detected() -> None:
    live = 'import os\nX = os.environ.get("KEEP_ME")\n'
    assert "ENV:KEEP_ME" in (gate.markers(live) - gate.markers("import os\n"))


def test_marker_survives_extraction_into_a_helper() -> None:
    """Markers must answer "would this capability disappear", not "were the bytes reformatted"."""
    inline = 'import os\nif os.environ.get("KILL_SWITCH"):\n    pass\n'
    refactored = 'import os\ndef off():\n    return os.environ.get("KILL_SWITCH")\nif off():\n    pass\n'
    assert not (gate.markers(inline) - gate.markers(refactored))


def test_exit2_sites_are_counted() -> None:
    assert "EXIT2:2" in gate.markers("def a():\n    return 2\ndef b():\n    return 2\n")
    assert "EXIT2:0" in gate.markers("def a():\n    return 0\n")


def test_unparseable_source_is_flagged_not_silently_empty() -> None:
    assert gate.markers("def (:\n") == {"UNPARSEABLE"}


# --------------------------------------------------------------- manifest reader


def _manifest(checks: list[dict]) -> dict:
    return {
        "events": {
            "Stop": {"settings_matcher": ".*", "settings_timeout": 35, "checks": checks}
        }
    }


def test_manifest_reader_reads_checks_not_the_event_dict_keys() -> None:
    """THE trap. events[ev] is a dict of 3 keys; len() on it reports 3 for any fleet size."""
    doc = _manifest([{"name": f"c{i}", "script": f"c{i}.py"} for i in range(5)])
    assert len(gate.manifest_checks(doc, "Stop")) == 5
    assert set(gate.manifest_checks(doc, "Stop")) == {"c0", "c1", "c2", "c3", "c4"}


def test_manifest_reader_tolerates_a_flat_list_shape() -> None:
    doc = {"events": {"Stop": [{"name": "c0", "script": "c0.py"}]}}
    assert set(gate.manifest_checks(doc, "Stop")) == {"c0"}


def test_manifest_reader_returns_empty_for_an_unknown_event() -> None:
    assert gate.manifest_checks(_manifest([]), "SessionStart") == {}


# --------------------------------------------------------------- settings reader


def test_command_script_returns_the_hooks_relative_path() -> None:
    cmd = 'python "C:\\Users\\x\\.claude\\hooks\\no-force-push\\hook.py"'
    assert gate._command_script(cmd) == "no-force-push/hook.py"


def test_command_script_never_leaks_an_env_prefix() -> None:
    """A command line can carry a token in an env prefix; only the script path may be printed."""
    cmd = 'SECRET_TOKEN=abc123 python "/home/u/.claude/hooks/a/b.py"'
    out = gate._command_script(cmd)
    assert out == "a/b.py"
    assert "abc123" not in out and "SECRET_TOKEN" not in out


def test_command_script_fallback_also_never_leaks() -> None:
    """The no-recognised-extension branch.

    The first version of the leak test used a command ENDING in `.py`, so it returned from the
    loop and never reached the fallback -- a mutation that made the fallback return the whole
    command line survived the suite. The dangerous path was the untested one.
    """
    out = gate._command_script("SECRET_TOKEN=abc123 node --experimental runner")
    assert out == "runner"
    assert "abc123" not in out and "SECRET_TOKEN" not in out


def test_settings_reader_touches_only_the_hooks_subtree(tmp_path: Path) -> None:
    """Regression guard: the live settings.json holds real credentials."""
    doc = {
        "apiKeyHelper": "TOP_SECRET_VALUE",
        "env": {"ANTHROPIC_API_KEY": "REDACTED-PLACEHOLDER-NOT-A-KEY"},
        "hooks": {
            "Stop": [
                {
                    "matcher": ".*",
                    "hooks": [{"command": 'python "/h/hooks/a/b.py"', "timeout": 5}],
                }
            ]
        },
    }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    parsed = gate.settings_hooks(path)
    blob = json.dumps(parsed)
    assert "TOP_SECRET_VALUE" not in blob
    assert "REDACTED-PLACEHOLDER-NOT-A-KEY" not in blob
    assert parsed["Stop"][0]["script"] == "a/b.py"


def test_settings_reader_returns_empty_for_a_missing_file(tmp_path: Path) -> None:
    assert gate.settings_hooks(tmp_path / "nope.json") == {}


# --------------------------------------------------------------- L1 `if` lint


def test_if_lint_fires_on_a_non_tool_event() -> None:
    report = gate.Report()
    gate.lint_if_on_non_tool_event(
        report, {"s": {"Stop": [{"if": "Edit(*.ts)", "script": "x.py"}]}}
    )
    assert len(report.hazards()) == 1
    assert "never evaluated" in report.hazards()[0].detail


def test_if_lint_is_silent_on_a_tool_event() -> None:
    report = gate.Report()
    gate.lint_if_on_non_tool_event(
        report, {"s": {"PreToolUse": [{"if": "Edit(*.ts)", "script": "x.py"}]}}
    )
    assert report.hazards() == []


def test_if_lint_is_silent_when_no_entry_uses_if() -> None:
    report = gate.Report()
    gate.lint_if_on_non_tool_event(report, {"s": {"Stop": [{"script": "x.py"}]}})
    assert report.findings == []


# --------------------------------------------------------------- severity ladder


@pytest.mark.parametrize(
    ("rel", "wired", "expected"),
    [
        ("no-force-push/hook.py", True, "HAZARD"),
        ("some-hook/check.py", False, "WARN"),
        ("some-hook/test_check.py", False, "INFO"),
        ("recall-gate/state/tree_index.json", False, "INFO"),
    ],
)
def test_body_severity_ladder(rel: str, wired: bool, expected: str) -> None:
    assert gate._body_severity(rel, wired)[0] == expected


def test_a_wired_json_is_still_a_hazard() -> None:
    """Wiredness outranks the file-type demotion; the manifest itself is wired JSON."""
    assert gate._body_severity("_dispatch/manifest.json", True)[0] == "HAZARD"


# --------------------------------------------------------------- axis P (broken promises)

_DOC = "the ghost-hook writes ~/.claude/ghost/index.ndjson"


def _promise(wired: set[str], age: float | None, text: str = _DOC) -> gate.Report:
    report = gate.Report()
    gate.axis_promises(
        report,
        {"d.md": text},
        wired,
        {"ghost-hook"},
        age_fn=lambda _root: age,
        stale_hours=168.0,
    )
    return report


def test_promise_fires_when_the_artifact_is_stale() -> None:
    assert len(_promise(set(), 700.0).hazards()) == 1


def test_promise_fires_when_the_artifact_is_absent() -> None:
    assert len(_promise(set(), None).hazards()) == 1


def test_promise_is_silent_when_the_artifact_is_fresh() -> None:
    """Regression guard for a false positive this axis actually produced.

    `commands/sentinel.md` names `event-ledger`; no script under `hooks/event-ledger/` is wired
    in either live registry; and `~/.claude/event-ledger/` was 0.6 h fresh, because something
    wired under a different directory name writes it. The config signal ALONE must never raise
    a hazard.
    """
    assert _promise(set(), 0.6).hazards() == []


def test_promise_is_silent_when_the_producer_is_wired() -> None:
    assert _promise({"ghost-hook/hook.py"}, 700.0).hazards() == []


def test_promise_is_silent_on_a_bare_mention() -> None:
    """use-vs-mention: naming a hook is not a dependency on it."""
    assert (
        _promise(set(), 700.0, "see also the ghost-hook, unrelated here").hazards()
        == []
    )


def test_promise_is_silent_with_no_artifact_path() -> None:
    assert _promise(set(), 700.0, "the ghost-hook is great").hazards() == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("read ~/.claude/checkpoints/<id>/index.ndjson now", {"checkpoints"}),
        (r"see .claude\plans\active.md", {"plans"}),
        ("~/.claude/settings.json holds it", {"settings.json"}),
        ("no path here at all", set()),
    ],
)
def test_artifact_roots(text: str, expected: set) -> None:
    assert gate.artifact_roots(text) == expected


def test_age_of_a_file_artifact_is_measured_not_reported_absent(
    tmp_path, monkeypatch
) -> None:
    """The measured bug: walking a FILE yields nothing, so it read as "produces nothing".

    That claim was falsifiable by looking -- `~/.claude/settings.json` plainly exists -- and a
    finding the reader can disprove discredits the true ones printed beside it.
    """
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gate, "LIVE_ROOT", tmp_path)
    age = gate._newest_age_hours("settings.json")
    assert age is not None and age < 1.0


def test_age_of_an_absent_artifact_is_none(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gate, "LIVE_ROOT", tmp_path)
    assert gate._newest_age_hours("nothing-here") is None


def test_age_of_an_empty_directory_is_none(tmp_path, monkeypatch) -> None:
    (tmp_path / "empty").mkdir()
    monkeypatch.setattr(gate, "LIVE_ROOT", tmp_path)
    assert gate._newest_age_hours("empty") is None


# --------------------------------------------------------------- wiredness


def _write_manifest(path: Path, scripts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "events": {
                    "PreToolUse": {
                        "settings_timeout": 20,
                        "checks": [{"name": s, "script": s} for s in scripts],
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def test_wiredness_is_the_live_side_only(tmp_path, monkeypatch) -> None:
    """A repo-declared, undeployed script is NOT wired.

    The measured defect: taking the union of both trees made the gate assert "the live harness
    runs this file" about `mcp-liveness/liveness.py`, which is declared in the repo manifest and
    deployed nowhere. The hazard is "a deploy destroys behaviour that runs today", so the
    denominator is what runs today.
    """
    live_manifest = tmp_path / "live" / "hooks" / "_dispatch" / "manifest.json"
    repo_manifest = tmp_path / "repo" / "hooks" / "_dispatch" / "manifest.json"
    _write_manifest(live_manifest, ["deployed/check.py"])
    _write_manifest(repo_manifest, ["deployed/check.py", "undeployed/check.py"])
    monkeypatch.setattr(gate, "LIVE_MANIFEST", live_manifest)
    monkeypatch.setattr(gate, "REPO_MANIFEST", repo_manifest)
    monkeypatch.setattr(gate, "LIVE_SETTINGS", tmp_path / "none.json")
    monkeypatch.setattr(gate, "REPO_SETTINGS", tmp_path / "none.json")

    wired = gate.wired_live(gate.Report())
    assert "deployed/check.py" in wired
    assert "undeployed/check.py" not in wired


def test_wiredness_includes_hooks_registered_only_in_settings(
    tmp_path, monkeypatch
) -> None:
    """Both blocking security hooks reach the harness this way, not via the manifest."""
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {"command": 'python "/h/hooks/no-force-push/hook.py"'}
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "LIVE_MANIFEST", tmp_path / "absent.json")
    monkeypatch.setattr(gate, "REPO_MANIFEST", tmp_path / "absent.json")
    monkeypatch.setattr(gate, "LIVE_SETTINGS", settings)
    monkeypatch.setattr(gate, "REPO_SETTINGS", tmp_path / "none.json")

    assert "no-force-push/hook.py" in gate.wired_live(gate.Report())


# --------------------------------------------------------------- fail-closed behaviour


def test_gate_fails_closed_when_the_live_tree_is_unreadable(
    tmp_path, monkeypatch, capsys
) -> None:
    """A gate that reports clean because it could not measure is worse than no gate.

    ci-hygiene 1: any empty walk returns non-zero, never "nothing found -> pass".
    """
    monkeypatch.setattr(gate, "LIVE_HOOKS", tmp_path / "hooks")
    monkeypatch.setattr(
        gate, "LIVE_MANIFEST", tmp_path / "hooks" / "_dispatch" / "manifest.json"
    )
    monkeypatch.setattr(gate, "LIVE_SETTINGS", tmp_path / "settings.json")
    rc = gate.main(["--quiet"])
    out = capsys.readouterr().out
    assert rc == 2, "an unreadable live tree must fail closed, not report clean"
    assert "FAILED:hook-predeploy-gate" in out
    # Name the control that must have fired. Asserting only that the control's NAME appears is
    # what let a mutation making C9 unfalsifiable survive: the name prints either way, and a
    # different control was carrying the exit code.
    assert "C9_manifest_reader_plausible=FAIL" in out
    assert (
        "C9_manifest_reader_plausible" in out.split("controls:")[1].split("stats:")[0]
    )


def test_controls_are_reported_on_every_run(capsys) -> None:
    report = gate.Report()
    report.stats["live_manifest_checks"] = 25
    report.stats["live_settings_events"] = 20
    report.stats["repo_settings_events"] = 19
    gate.run_controls(report)
    assert all(report.controls.values()), report.controls
    assert len(report.controls) >= 10


def test_report_emits_a_terminal_state_marker(capsys) -> None:
    """AGENTS.md 4: terminal-state output, never open-ended prose."""
    gate.main(["--quiet"])
    out = capsys.readouterr().out
    assert ("SUCCESS:hook-predeploy-gate" in out) or (
        "FAILED:hook-predeploy-gate" in out
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
