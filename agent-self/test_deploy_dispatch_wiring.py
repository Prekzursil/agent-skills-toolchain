#!/usr/bin/env python3
r"""Tests for agent-self/deploy_dispatch_wiring.py — the WF-2 deploy vehicle.

Red-proofed by the three ``test_00_*`` cases: they run deliberately broken variants of the tool
and require the damage to show. A suite that stays green against a no-op deploy would be
measuring nothing (the both-states rule).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

THIS = Path(__file__).resolve().parent
TOOL = THIS / "deploy_dispatch_wiring.py"

_spec = importlib.util.spec_from_file_location("_ddw_under_test", TOOL)
ddw = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ddw)

MANIFEST_MATCHER = "Task|Write|Workflow|mcp__codex__codex|Bash|PowerShell"
DRIFTED_MATCHER = "Task|Bash|PowerShell|Edit|Write|mcp__basic-memory__.*"
FAKE_SECRET = "sk-test-NOT-A-REAL-KEY-0000"


def _cmd(root: Path, relpath: str) -> str:
    return f'python "{root.as_posix()}/hooks/{relpath}"'


def build_root(
    tmp_path: Path,
    *,
    matcher: str = DRIFTED_MATCHER,
    legacy_wired: bool = True,
    declare_successor: bool = True,
    dispatcher_groups: int = 1,
) -> Path:
    """A sandbox ~/.claude reproducing the measured live drift."""

    root = tmp_path / "claude"
    (root / "hooks" / "_dispatch").mkdir(parents=True)
    (root / "hooks" / "_dispatch" / "dispatch.py").write_text(
        "# stub\n", encoding="utf-8"
    )

    checks = [
        {"name": "dup-guard", "script": "dup-guard/guard.py", "matcher": "Write"},
        {
            "name": "codex-monitor-autolaunch",
            "script": "codex-monitor-autolaunch/check.py",
            "matcher": "Bash|PowerShell",
        },
    ]
    if declare_successor:
        checks.append(
            {
                "name": "monitor-autolaunch",
                "script": "monitor-autolaunch/check.py",
                "matcher": "Task|Workflow|mcp__codex__codex",
            }
        )
    manifest = {
        "hooks_root": (root / "hooks").as_posix(),
        "events": {
            "PreToolUse": {
                "settings_matcher": MANIFEST_MATCHER,
                "settings_timeout": 20,
                "checks": checks,
            },
            "SessionStart": {"checks": [{"name": "x", "script": "x/x.py"}]},
        },
    }
    (root / "hooks" / "_dispatch" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    pretool = []
    for _ in range(dispatcher_groups):
        pretool.append(
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": _cmd(root, "_dispatch/dispatch.py") + " pretooluse",
                        "timeout": 25,
                    }
                ],
            }
        )
    if legacy_wired:
        pretool.append(
            {
                "matcher": "Workflow",
                "hooks": [
                    {
                        "type": "command",
                        "command": _cmd(root, "workflow-monitor-autolaunch/check.py"),
                        "timeout": 6,
                    }
                ],
            }
        )
    # The substring-collision decoy: this path CONTAINS "monitor-autolaunch/check.py".
    pretool.append(
        {
            "matcher": "mcp__codex__codex",
            "hooks": [
                {
                    "type": "command",
                    "command": _cmd(root, "codex-monitor-autolaunch/check.py"),
                    "timeout": 6,
                }
            ],
        }
    )

    settings = {
        "model": "opus",
        "env": {"ANTHROPIC_API_KEY": FAKE_SECRET, "MCP_TIMEOUT": "60000"},
        "permissions": {"allow": ["Bash(ls:*)"], "defaultMode": "default"},
        "hooks": {
            "PreToolUse": pretool,
            "SessionEnd": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "python end.py"}],
                }
            ],
        },
    }
    (root / "settings.json").write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return root


def run_tool(root: Path, *args: str, tool: Path = TOOL) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(tool), "--claude-root", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def load(root: Path) -> dict:
    return json.loads((root / "settings.json").read_text(encoding="utf-8"))


def workflow_groups(settings: dict) -> list[dict]:
    import re

    out = []
    for group in settings["hooks"]["PreToolUse"]:
        matcher = group.get("matcher") or ""
        try:
            if re.fullmatch(matcher, "Workflow"):
                out.append(group)
        except re.error:
            continue
    return out


# --------------------------------------------------------------------------- core behaviour


def test_01_dispatcher_matcher_is_set_to_the_manifest_value(tmp_path):
    root = build_root(tmp_path)
    assert run_tool(root, "--apply", "--no-backup").returncode == 0
    assert load(root)["hooks"]["PreToolUse"][0]["matcher"] == MANIFEST_MATCHER


def test_02_superseded_legacy_group_is_removed(tmp_path):
    root = build_root(tmp_path)
    before = [
        g
        for g in load(root)["hooks"]["PreToolUse"]
        if "workflow-monitor-autolaunch" in json.dumps(g)
    ]
    assert len(before) == 1, "fixture must start with the legacy group wired"
    assert run_tool(root, "--apply", "--no-backup").returncode == 0
    after = [
        g
        for g in load(root)["hooks"]["PreToolUse"]
        if "workflow-monitor-autolaunch" in json.dumps(g)
    ]
    assert after == []


def test_03_exactly_one_workflow_route_and_it_is_the_dispatcher(tmp_path):
    """WF-2's LATENT TRAP: admitting Workflow while the legacy group survives = two launchers."""

    root = build_root(tmp_path)
    assert len(workflow_groups(load(root))) == 1, (
        "pre-state: only the legacy hook serves Workflow"
    )
    assert run_tool(root, "--apply", "--no-backup").returncode == 0
    groups = workflow_groups(load(root))
    assert len(groups) == 1
    assert "_dispatch/dispatch.py" in groups[0]["hooks"][0]["command"]


def test_04_machine_local_state_survives(tmp_path):
    root = build_root(tmp_path)
    assert run_tool(root, "--apply", "--no-backup").returncode == 0
    after = load(root)
    assert after["env"]["ANTHROPIC_API_KEY"] == FAKE_SECRET
    assert after["env"]["MCP_TIMEOUT"] == "60000"
    assert after["model"] == "opus"
    assert after["permissions"] == {"allow": ["Bash(ls:*)"], "defaultMode": "default"}
    assert after["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == "python end.py"


def test_05_codex_group_survives_the_substring_collision(tmp_path):
    """``codex-monitor-autolaunch/check.py`` CONTAINS ``monitor-autolaunch/check.py``."""

    root = build_root(tmp_path)
    assert run_tool(root, "--apply", "--no-backup").returncode == 0
    survivors = [
        g
        for g in load(root)["hooks"]["PreToolUse"]
        if "codex-monitor-autolaunch" in json.dumps(g)
    ]
    assert len(survivors) == 1
    assert survivors[0]["matcher"] == "mcp__codex__codex"


def test_05b_a_wildcard_event_is_left_alone_in_either_spelling(tmp_path):
    """A declared ``"*"`` is satisfied by ``"*"`` or ``".*"``; rewriting one to the other is
    an out-of-scope edit. Measured on the live root before this guard existed: the tool planned
    ``SessionStart .* -> *``, wiring WF-2 never asked it to touch."""

    root = build_root(tmp_path)
    manifest_path = root / "hooks" / "_dispatch" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["events"]["SessionStart"]["settings_matcher"] = "*"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    settings = load(root)
    settings["hooks"]["SessionStart"] = [
        {
            "matcher": ".*",
            "hooks": [
                {
                    "type": "command",
                    "command": _cmd(root, "_dispatch/dispatch.py") + " sessionstart",
                }
            ],
        }
    ]
    (root / "settings.json").write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 0
    assert "SessionStart" not in result.stdout
    assert load(root)["hooks"]["SessionStart"][0]["matcher"] == ".*"
    assert ddw.matcher_satisfies(".*", "*") and ddw.matcher_satisfies("*", "*")
    assert not ddw.matcher_satisfies(".*", "Task|Workflow")


def test_06_references_matches_on_a_path_segment_boundary():
    assert ddw.references(
        'python "C:/x/hooks/monitor-autolaunch/check.py"', "monitor-autolaunch/check.py"
    )
    assert not ddw.references(
        'python "C:/x/hooks/codex-monitor-autolaunch/check.py"',
        "monitor-autolaunch/check.py",
    )
    assert ddw.references(
        'python "C:/x/hooks/codex-monitor-autolaunch/check.py"',
        "codex-monitor-autolaunch/check.py",
    )


def test_07_is_idempotent_and_byte_stable(tmp_path):
    root = build_root(tmp_path)
    assert run_tool(root, "--apply", "--no-backup").returncode == 0
    first = (root / "settings.json").read_bytes()
    second = run_tool(root, "--apply", "--no-backup")
    assert second.returncode == 0
    assert "already in sync (0 changes)" in second.stdout
    assert (root / "settings.json").read_bytes() == first


def test_08_dry_run_writes_nothing(tmp_path):
    root = build_root(tmp_path)
    before = (root / "settings.json").read_bytes()
    result = run_tool(root)
    assert result.returncode == 0
    assert "dry-run" in result.stdout
    assert (root / "settings.json").read_bytes() == before


def test_09_backup_holds_the_pre_change_bytes(tmp_path):
    root = build_root(tmp_path)
    before = (root / "settings.json").read_bytes()
    assert run_tool(root, "--apply").returncode == 0
    backups = list(root.glob("settings.json.bak-wiring-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == before


def test_10_no_temp_file_is_left_behind(tmp_path):
    root = build_root(tmp_path)
    assert run_tool(root, "--apply", "--no-backup").returncode == 0
    assert list(root.glob("*.deploy-tmp")) == []


# --------------------------------------------------------------------------- fail-closed


def test_11_refuses_when_the_successor_is_not_a_declared_check(tmp_path):
    root = build_root(tmp_path, declare_successor=False)
    before = (root / "settings.json").read_bytes()
    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 1
    assert "FAILED:deploy-dispatch-wiring" in result.stdout
    assert (root / "settings.json").read_bytes() == before


def test_12_refuses_when_the_dispatcher_group_is_not_unique(tmp_path):
    root = build_root(tmp_path, dispatcher_groups=2)
    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 1
    assert "exactly one local _dispatch group" in result.stdout


def test_13_refuses_when_a_required_file_is_missing(tmp_path):
    root = build_root(tmp_path)
    (root / "hooks" / "_dispatch" / "manifest.json").unlink()
    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 1
    assert "required file missing" in result.stdout


def test_14_refuses_on_unparseable_settings(tmp_path):
    root = build_root(tmp_path)
    (root / "settings.json").write_text("{not json", encoding="utf-8")
    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 1
    assert "unreadable JSON" in result.stdout


def test_15_refuses_a_manifest_that_declares_no_settings_matcher(tmp_path):
    root = build_root(tmp_path)
    manifest_path = root / "hooks" / "_dispatch" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["events"]["PreToolUse"]["settings_matcher"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 1
    assert "blind scan" in result.stdout


def test_16_already_correct_root_reports_in_sync(tmp_path):
    root = build_root(tmp_path, matcher=MANIFEST_MATCHER, legacy_wired=False)
    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 0
    assert "already in sync (0 changes)" in result.stdout


def test_17_never_prints_settings_content(tmp_path):
    root = build_root(tmp_path)
    for args in ((), ("--apply", "--no-backup")):
        result = run_tool(root, *args)
        assert FAKE_SECRET not in result.stdout
        assert FAKE_SECRET not in result.stderr


# --------------------------------------------------------------------------- red proof


#: Each entry is (anchor, replacement).  The anchor must appear EXACTLY once, so a refactor that
#: moves the mutated code fails loudly here instead of silently disarming the red proof.
MUTANTS = {
    # Drops the matcher rewrite -> tests 01 and 03 must redden.
    "noop-set-matcher": (
        "    out = json.loads(json.dumps(settings))\n    for change in changes:",
        "    out = json.loads(json.dumps(settings))\n    for change in []:",
    ),
    # Drops the legacy-group removal -> tests 02 and 03 must redden (the WF-2 double-open trap).
    "noop-drop-superseded": (
        '        key=lambda c: (c["event"], -c["index"]),\n    )\n    for change in drops:',
        '        key=lambda c: (c["event"], -c["index"]),\n    )\n    for change in []:',
    ),
    # Removes the path-segment guard -> test 06 must redden on the codex/monitor collision.
    "substring-match": (
        '        if idx == 0 or hay[idx - 1] == "/":\n            return True',
        "        if True:\n            return True",
    ),
}


def _mutate(name: str, tmp_path: Path) -> Path:
    old, new = MUTANTS[name]
    source = TOOL.read_text(encoding="utf-8")
    assert source.count(old) == 1, f"mutant {name!r} anchor did not match exactly once"
    mutant = tmp_path / f"mutant_{name.replace('-', '_')}.py"
    mutant.write_text(source.replace(old, new), encoding="utf-8")
    return mutant


@pytest.mark.parametrize("name", ("noop-set-matcher", "noop-drop-superseded"))
def test_00_apply_mutants_cannot_ship_a_half_deploy(name, tmp_path):
    """A half-applied deploy is the WF-2 trap, so ``verify()`` must abort rather than write it.

    Each mutant performs only ONE of the two required edits. Measured: the post-condition catches
    it, exits non-zero, and leaves settings.json byte-identical -- so the box is never left in the
    both-launchers-wired state. This also red-proofs tests 01-03: with ``verify()`` disarmed those
    assertions would be the only thing standing between the mutant and a shipped half-deploy.
    """

    root = build_root(tmp_path)
    before = (root / "settings.json").read_bytes()
    result = run_tool(root, "--apply", "--no-backup", tool=_mutate(name, tmp_path))

    assert result.returncode == 1, f"mutant {name!r} reported success for a half-deploy"
    assert "post-conditions fail" in result.stdout
    assert (root / "settings.json").read_bytes() == before, "a half-deploy reached disk"

    after = load(root)
    assert after["hooks"]["PreToolUse"][0]["matcher"] != MANIFEST_MATCHER or any(
        "workflow-monitor-autolaunch" in json.dumps(g)
        for g in after["hooks"]["PreToolUse"]
    ), f"mutant {name!r} still produced correct wiring; the assertions are inert"
    assert len(workflow_groups(after)) <= 1, "two Workflow launchers must never coexist"


def test_00_verify_rejects_a_hand_made_half_deploy(tmp_path):
    """Direct unit proof that ``verify()`` names BOTH halves of the WF-2 defect."""

    root = build_root(tmp_path)
    manifest = json.loads(
        (root / "hooks" / "_dispatch" / "manifest.json").read_text(encoding="utf-8")
    )
    half = load(root)
    half["hooks"]["PreToolUse"][0]["matcher"] = (
        MANIFEST_MATCHER  # matcher fixed, legacy kept
    )
    problems = ddw.verify(half, manifest, root)
    assert any("still wired standalone" in p for p in problems)

    other_half = load(root)  # legacy dropped, matcher left drifted
    other_half["hooks"]["PreToolUse"] = [
        g
        for g in other_half["hooks"]["PreToolUse"]
        if "workflow-monitor-autolaunch" not in json.dumps(g)
    ]
    problems = ddw.verify(other_half, manifest, root)
    assert any("does not mirror the manifest" in p for p in problems)

    assert (
        ddw.verify(
            ddw.apply_changes(load(root), ddw.plan(load(root), manifest, root)),
            manifest,
            root,
        )
        == []
    )


def test_00_substring_mutant_reintroduces_the_path_collision(tmp_path):
    """Without the segment guard, the legacy path is mistaken for its successor's path."""

    mutant_spec = importlib.util.spec_from_file_location(
        "_ddw_mutant", _mutate("substring-match", tmp_path)
    )
    mutant = importlib.util.module_from_spec(mutant_spec)
    assert mutant_spec.loader is not None
    mutant_spec.loader.exec_module(mutant)

    collision = (
        'python "C:/x/hooks/workflow-monitor-autolaunch/check.py"',
        "monitor-autolaunch/check.py",
    )
    assert mutant.references(*collision) is True, (
        "mutant failed to reproduce the collision"
    )
    assert ddw.references(*collision) is False, (
        "the shipped guard does not reject the collision"
    )


# --------------------------------------------------------------------------- #
# 2026-10-18 review thread: superseded guards must be removed on surgical deploy
# --------------------------------------------------------------------------- #

#: The six PreToolUse guards the 2026-10-17 blocking-mode wave consolidated as
#: exec-mode manifest checks. On an install deployed BEFORE that wave the
#: standalone groups are still wired; without their SUPERSEDED_STANDALONE
#: entries the deploy widens the dispatcher matcher but leaves every standalone
#: copy in place -> both run on every overlapping call.
CONSOLIDATED_GUARDS = (
    "no-force-push/hook.py",
    "test-tamper-guard/guard.py",
    "cmd-rewrite/inject-nopager.py",
    "ulysses/enforce.py",
    "loop-recovery/handler.py",
    "deny-credential-reads/deny.py",
)


def build_pre_wave_root(tmp_path: Path) -> Path:
    """A sandbox ~/.claude as an install deployed BEFORE the consolidation wave
    looked: dispatcher wired (drifted matcher), all six standalone guards still
    present, manifest already declaring their consolidated successors."""

    root = build_root(tmp_path)  # drifted matcher + wfmon legacy + decoy

    # Declare the six successors in the sandbox manifest (the deployed manifest
    # beside the dispatcher already carries them post-wave).
    manifest_path = root / "hooks" / "_dispatch" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["events"]["PreToolUse"]["checks"].extend(
        {"name": name, "script": script, "matcher": "Bash", "exec": True}
        for script in CONSOLIDATED_GUARDS
        for name in (script,)
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # The six standalone groups a pre-wave install still carries.
    settings_path = root / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    guard_matchers = {
        "no-force-push/hook.py": "Bash|PowerShell",
        "test-tamper-guard/guard.py": "Bash",
        "cmd-rewrite/inject-nopager.py": "Bash",
        "ulysses/enforce.py": "Bash|PowerShell|Edit|Write|MultiEdit",
        "loop-recovery/handler.py": "Bash",
        "deny-credential-reads/deny.py": "Read|Edit|MultiEdit|Grep|Bash|PowerShell",
    }
    for script, matcher in guard_matchers.items():
        settings["hooks"]["PreToolUse"].append(
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": _cmd(root, script),
                        "timeout": 20,
                    }
                ],
            }
        )
    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return root


def test_18_six_consolidated_guards_are_removed_on_apply(tmp_path):
    """P2 thread: --apply must retire the superseded standalone guards.

    Before the SUPERSEDED_STANDALONE extension, deploying onto a pre-wave
    install left the dispatcher copy AND every standalone guard wired: double
    scans per call and racing side effects on stateful hooks (loop-recovery).
    """
    root = build_pre_wave_root(tmp_path)

    before = json.dumps(load(root))
    for script in CONSOLIDATED_GUARDS:
        assert script in before, f"fixture must wire {script} standalone"
    assert load(root)["env"]["ANTHROPIC_API_KEY"] == FAKE_SECRET

    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "drop-superseded" in result.stdout

    after = load(root)
    for script in CONSOLIDATED_GUARDS:
        assert script not in json.dumps(after["hooks"]["PreToolUse"]), (
            f"superseded standalone {script} survived the deploy — it would "
            "double-run beside the dispatcher copy"
        )
    # Nothing else was harmed: machine-local state, the wfmon removal, the
    # codex decoy and the dispatcher group all behave exactly as before.
    assert after["env"]["ANTHROPIC_API_KEY"] == FAKE_SECRET
    assert after["model"] == "opus"
    wf = workflow_groups(after)
    assert len(wf) == 1 and "_dispatch/dispatch.py" in json.dumps(wf[0]), (
        "the only Workflow route left must be the dispatcher itself"
    )
    assert any(
        "codex-monitor-autolaunch/check.py" in json.dumps(g)
        for g in after["hooks"]["PreToolUse"]
    ), "the disjoint-route codex decoy must survive"
    assert any(
        "_dispatch/dispatch.py" in json.dumps(g)
        for g in after["hooks"]["PreToolUse"]
    ), "the dispatcher group itself must survive"

    # Idempotent: a second run is a clean no-op.
    again = run_tool(root, "--apply", "--no-backup")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "already in sync" in again.stdout


def test_18b_deploy_refuses_when_a_successor_is_undeclared(tmp_path):
    """Fail-closed control: the six new removals obey the same successor guard
    as the wfmon one — a manifest that does not declare the consolidated check
    must abort the deploy rather than retire the standalone copy blindly."""

    root = build_pre_wave_root(tmp_path)
    manifest_path = root / "hooks" / "_dispatch" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["events"]["PreToolUse"]["checks"] = [
        c for c in manifest["events"]["PreToolUse"]["checks"]
        if c.get("script") != "no-force-push/hook.py"
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    result = run_tool(root, "--apply", "--no-backup")
    assert result.returncode == 1, "an undeclared successor must refuse to deploy"
    assert "no-force-push/hook.py" in result.stdout
    # And nothing was written.
    assert "no-force-push/hook.py" in json.dumps(load(root)["hooks"]["PreToolUse"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
