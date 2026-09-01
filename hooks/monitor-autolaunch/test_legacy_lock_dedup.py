import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

import pytest


HOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOK_DIR.parents[1]
MONITORCORE_ROOT = REPO_ROOT / "tools" / "monitorcore"
if str(MONITORCORE_ROOT) not in sys.path:
    sys.path.insert(0, str(MONITORCORE_ROOT))

SPEC = importlib.util.spec_from_file_location(
    "monitor_autolaunch_legacy_lock_dedup_check", HOOK_DIR / "check.py"
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


@pytest.fixture
def harness(tmp_path, monkeypatch, capsys):
    registry = tmp_path / "monitors.toml"
    registry.write_text(
        """[wfmon]
dir = "workflow-monitor"
entry = "workflow_monitor.py"
trigger_tool = "Workflow"

[codexmon]
dir = "workflow-monitor"
entry = "codex_monitor.py"
trigger_tool = "mcp__codex__codex"

[agentmon]
dir = "run-agent-monitor"
entry = "agentmon.py"
trigger_tool = "Task"
autolaunch = "remind"
""",
        encoding="utf-8",
    )
    skills_root = tmp_path / "skills"
    for relative in (
        "workflow-monitor/workflow_monitor.py",
        "workflow-monitor/codex_monitor.py",
        "run-agent-monitor/agentmon.py",
    ):
        entry = skills_root / relative
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# fixture\n", encoding="utf-8")

    from monitorcore import monitors

    launches = []
    monkeypatch.setenv("MONITORCORE_MONITORS_TOML", str(registry))
    monkeypatch.setattr(monitors, "default_skills_root", lambda: str(skills_root))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(
        check.subprocess, "Popen", lambda argv, **_kwargs: launches.append(argv)
    )

    def fire(tool, sid):
        monkeypatch.setattr(
            sys.stdin,
            "read",
            io.StringIO(json.dumps({"tool_name": tool, "session_id": sid})).read,
        )
        check.main()
        return capsys.readouterr().out

    return launches, fire


def test_01_positive_control_launches_and_claims_both_locks(tmp_path, harness):
    launches, fire = harness
    fire("Workflow", "positive")
    assert len(launches) == 1
    assert (tmp_path / "monitor-autolaunch-wfmon-positive.lock").exists()
    assert (tmp_path / "wfmon-autolaunch-positive.lock").exists()


def test_02_legacy_fired_first_stops_generalized(tmp_path, harness):
    launches, fire = harness
    (tmp_path / "wfmon-autolaunch-legacyfirst.lock").write_text("1", encoding="utf-8")
    output = fire("Workflow", "legacyfirst")
    assert len(launches) == 0
    assert "already opened this session" in output


def test_03_generalized_fired_first_claims_legacy_alias(tmp_path, harness):
    launches, fire = harness
    fire("Workflow", "generalfirst")
    assert len(launches) == 1
    assert (tmp_path / "wfmon-autolaunch-generalfirst.lock").exists()


def test_04_different_session_relaunches(harness):
    launches, fire = harness
    fire("Workflow", "sessionone")
    fire("Workflow", "sessiontwo")
    assert len(launches) == 2


def test_05_monitor_without_predecessor_has_no_alias(tmp_path, harness):
    launches, fire = harness
    fire("mcp__codex__codex", "codexsession")
    assert len(launches) == 1
    assert not (tmp_path / "codexmon-autolaunch-codexsession.lock").exists()


def test_06_remind_branch_emits_without_launch(harness):
    launches, fire = harness
    output = fire("Task", "agentsession")
    assert len(launches) == 0
    assert "run `mon agentmon`" in output


def test_07_reentrant_fire_launches_exactly_once(monkeypatch, harness):
    launches, fire = harness
    reentered = False
    sid = "oldrace"

    def popen(argv, **_kwargs):
        nonlocal reentered
        launches.append(argv)
        if not reentered:
            reentered = True
            fire("Workflow", sid)

    monkeypatch.setattr(check.subprocess, "Popen", popen)
    with monkeypatch.context() as old_ordering:
        old_ordering.setattr(check, "_claim_session", lambda _lock: None)
        fire("Workflow", sid)
    assert len(launches) == 2  # Both-states control: pre-fix ordering goes RED.

    launches.clear()
    reentered = False
    sid = "race"
    fire("Workflow", "race")
    assert len(launches) == 1


def test_08_claim_exists_before_launch(tmp_path, monkeypatch, harness):
    launches, fire = harness
    claim = tmp_path / "wfmon-autolaunch-beforelaunch.lock"

    def popen(argv, **_kwargs):
        assert claim.exists()
        launches.append(argv)

    monkeypatch.setattr(check.subprocess, "Popen", popen)
    fire("Workflow", "beforelaunch")
    assert len(launches) == 1


def test_09_claim_oserror_fails_open(monkeypatch, harness):
    launches, fire = harness
    monkeypatch.setattr(check, "_claim_session", lambda _lock: None)
    fire("Workflow", "denied")
    assert len(launches) == 1


def test_10_claim_alias_stale_lock_suppresses_launch(tmp_path, harness):
    launches, fire = harness
    claim = check._session_locks("wfmon", "claimstale")[-1]
    assert claim == tmp_path / "wfmon-autolaunch-claimstale.lock"
    claim.write_text("1", encoding="utf-8")
    output = fire("Workflow", "claimstale")
    assert len(launches) == 0
    assert "already opened this session" in output
