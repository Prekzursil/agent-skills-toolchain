"""Tests for the process-hygiene decision engine.

Every rule here encodes a leak the 02.09.2026 04:50 EEST measurement found on the
owner's box (3.5 GB free, 67.7 GB committed against 31.6 GB physical):

* ``test_retired_*``   - a retired AgentBridge bridge-server crash-looping under
  three Grok sessions at 130-155 MB each.
* ``test_orphan_*``    - four node/python processes whose parent was gone, and
  two cursor-agent CLI sessions from 28-31 hours ago still holding 311 MB + 61 MB.
* ``test_rss_*``       - one cursor-agent session node.exe at 1.0 GB after 20 min.
* ``test_mcp_*``       - ~42 registered MCP servers duplicated per session.
* ``test_wsl_*``       - vmmemWSL at 1.1 GB with no workload inside.
* ``test_protected_*`` - auth2api (:8317, 105 h, orphan by design), the Basic
  Memory daemon and its watchdog must survive every rule.

Time model: ``NOW`` is the reference "now"; ``observe`` feeds ``rounds`` snapshots
ending exactly at ``NOW`` (5 minutes apart), so ``ago(seconds)`` gives a clean age
at the final evaluation.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

import hygiene

GIB = 1024**3
MIB = 1024**2
NOW = 5_000_000
STEP = 300
TOOL_ROOT = pathlib.Path(__file__).resolve().parents[1]
CURSOR_AGENT_EXE = "C:\\Users\\Prekzursil\\AppData\\Local\\cursor-agent\\versions\\2026.09.01\\node.exe"
NODE_EXE = "C:\\Program Files\\nodejs\\node.exe"
PY_EXE = "C:\\Python314\\python.exe"
PWSH_EXE = "C:\\Program Files\\PowerShell\\7\\pwsh.exe"
GROK_EXE = "C:\\Users\\Prekzursil\\.local\\bin\\grok.exe"
CLAUDE_EXE = "C:\\Users\\Prekzursil\\.local\\bin\\claude.exe"
CODEX_EXE = "C:\\Users\\Prekzursil\\.local\\bin\\codex.exe"
CURSOR_IDE_EXE = "C:\\Users\\Prekzursil\\AppData\\Local\\Programs\\cursor\\Cursor.exe"


WT_EXE = (
    "C:\\Program Files\\WindowsApps\\Microsoft.WindowsTerminal\\WindowsTerminal.exe"
)


def ago(seconds: int) -> int:
    return NOW - seconds


# --------------------------------------------------------------------- builders


def proc(
    pid: int,
    ppid: int,
    *,
    name: str = "node.exe",
    exe: str = NODE_EXE,
    cmd: str = "node server.js",
    created: int = ago(6 * 3600),
    cpu: float | None = 1.0,
    io: int | None = 10,
    ws: int = 100 * MIB,
    private: int = 100 * MIB,
) -> dict:
    return {
        "pid": pid,
        "ppid": ppid,
        "name": name,
        "executable": exe,
        "command_line": cmd,
        "created_unix": created,
        "cpu_seconds": cpu,
        "io_bytes": io,
        "working_set_bytes": ws,
        "private_bytes": private,
    }


def snap(
    procs: list[dict],
    *,
    taken: int = NOW,
    physical: int = 32 * GIB,
    free: int = 8 * GIB,
    commit: int = 20 * GIB,
    commit_limit: int = 64 * GIB,
    compressed: int | None = None,
    wsl_running: tuple[str, ...] = (),
    wsl_available: bool = True,
    listeners: dict[int, int] | None = None,
    supervisor_pids: tuple[int, ...] = (),
) -> dict:
    return {
        "schema": hygiene.SCHEMA_SNAPSHOT,
        "taken_unix": taken,
        "host": {
            "physical_bytes": physical,
            "free_bytes": free,
            "commit_total_bytes": commit,
            "commit_limit_bytes": commit_limit,
            "compressed_bytes": compressed,
        },
        "wsl": {"available": wsl_available, "running_distros": list(wsl_running)},
        "listeners": [
            {"port": port, "pid": pid} for port, pid in (listeners or {}).items()
        ],
        "supervisor_pids": list(supervisor_pids),
        "processes": procs,
    }


def policy(**changes) -> dict:
    payload = json.loads(
        (TOOL_ROOT / "policy.example.json").read_text(encoding="utf-8")
    )
    for dotted, value in changes.items():
        node = payload
        parts = dotted.split(".")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value
    return payload


def registry() -> dict:
    return {
        "mcp": {
            "policy": {
                "required": False,
                "startupTimeoutMs": 30_000,
                "toolTimeoutMs": 30_000,
                "healthProbe": {"kind": "mcp-tools-list", "timeoutMs": 30_000},
                "toolAllowlist": ["*"],
                "approvalMode": "native",
                "maxPrivateBytes": 512 * MIB,
            },
            "supervision": {
                "totalIdlePrivateBytes": 6 * GIB,
                "failureThreshold": 3,
                "failureWindowSeconds": 600,
                "quarantineScope": "session",
                "duplicatePolicy": "report-unless-exact-process-tree",
            },
            "servers": {
                "example": {
                    "enabled": True,
                    "targets": ["claude"],
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@example/mcp-server"],
                    "singletonKey": "example/server",
                    "requiredEnv": [],
                    "credentialNames": [],
                    "tags": ["approved", "stdio"],
                },
                "basic-memory": {
                    "enabled": True,
                    "targets": ["claude", "codex"],
                    "transport": "http",
                    "url": "http://127.0.0.1:8765/mcp",
                    "singletonKey": "basic-memory/http",
                    "processMatch": ["basic_memory", "streamable-http"],
                    "maxPrivateBytes": GIB,
                    "resourceException": (
                        "FastEmbed semantic index; measured warm singleton is ~843 MiB."
                    ),
                    "requiredEnv": [],
                    "credentialNames": [],
                    "tags": ["approved", "http", "local", "shared"],
                },
            },
        }
    }


def engine(pol: dict | None = None, state: dict | None = None) -> hygiene.Engine:
    return hygiene.Engine(
        hygiene.validate_policy(pol or policy()),
        state if state is not None else {},
        fleet=hygiene.load_fleet(hygiene.DEFAULT_FLEET_PATH),
        registry=registry(),
    )


def observe(
    eng: hygiene.Engine,
    procs: list[dict],
    rounds: int,
    *,
    end: int = NOW,
    reaper_available: bool = True,
    **snap_kwargs,
) -> hygiene.Plan:
    """Feed ``rounds`` snapshots 5 minutes apart, the last one exactly at ``end``."""
    plan = None
    for index in range(rounds):
        taken = end - (rounds - 1 - index) * STEP
        plan = eng.evaluate(
            hygiene.parse_snapshot(snap(procs, taken=taken, **snap_kwargs)),
            reaper_available=reaper_available,
        )
    assert plan is not None
    return plan


def terminal(pid: int = 9_999, created: int = ago(48 * 3600)) -> dict:
    """A present WindowsTerminal host (protected by name) for session-host shells."""
    return proc(
        pid, 1, name="WindowsTerminal.exe", exe=WT_EXE, cmd="wt", created=created
    )


def by_rule(plan: hygiene.Plan, rule: str) -> list[hygiene.Decision]:
    return [decision for decision in plan.decisions if decision.rule == rule]


def stops(plan: hygiene.Plan) -> list[hygiene.Decision]:
    return [decision for decision in plan.decisions if decision.action == "stop"]


def kill_pids(plan: hygiene.Plan) -> set[int]:
    return {member.pid for decision in stops(plan) for member in decision.tree}


# ---------------------------------------------------------------------- policy


def test_example_policy_validates_and_is_normalised():
    normalised = hygiene.validate_policy(policy())
    assert normalised["schema"] == hygiene.SCHEMA_POLICY
    assert normalised["runtimes"]["cursor-agent"]["orphanHandler"] == (
        "cursor-orphan-reaper"
    )
    assert normalised["pressure"]["elevated"]["free"] == 4 * GIB


def test_policy_rejects_unknown_top_level_key():
    bad = policy()
    bad["surprise"] = 1
    with pytest.raises(hygiene.PolicyError, match="unknown key"):
        hygiene.validate_policy(bad)


def test_policy_rejects_unknown_section_key():
    bad = policy()
    bad["wsl"]["typo"] = 1
    with pytest.raises(hygiene.PolicyError, match="wsl: unknown key"):
        hygiene.validate_policy(bad)


def test_policy_rejects_wrong_schema():
    with pytest.raises(hygiene.PolicyError, match="schema"):
        hygiene.validate_policy(policy(schema="nope"))


def test_policy_rejects_non_mapping():
    with pytest.raises(hygiene.PolicyError, match="mapping"):
        hygiene.validate_policy([])


def test_policy_rejects_inverted_tiers():
    bad = policy(**{"pressure.critical.freeBytesBelow": 5 * GIB})
    with pytest.raises(hygiene.PolicyError, match="critical"):
        hygiene.validate_policy(bad)


def test_policy_rejects_bad_regex():
    bad = policy(**{"runtimes.grok.executablePattern": "("})
    with pytest.raises(hygiene.PolicyError, match="regex"):
        hygiene.validate_policy(bad)


def test_policy_rejects_unknown_tier_name():
    bad = policy(**{"mcp.overBudget.minTier": "panic"})
    with pytest.raises(hygiene.PolicyError, match="tier"):
        hygiene.validate_policy(bad)


def test_policy_rejects_negative_numbers_and_wrong_types():
    with pytest.raises(hygiene.PolicyError, match="orphans.minAgeSeconds"):
        hygiene.validate_policy(policy(**{"orphans.minAgeSeconds": -1}))
    with pytest.raises(hygiene.PolicyError, match="protected.names"):
        hygiene.validate_policy(policy(**{"protected.names": "chrome.exe"}))
    with pytest.raises(hygiene.PolicyError, match="retired"):
        hygiene.validate_policy(policy(retired=[{"id": "x"}]))
    with pytest.raises(hygiene.PolicyError, match="retired"):
        hygiene.validate_policy(policy(retired=[{"id": "x", "matchAll": []}]))
    with pytest.raises(hygiene.PolicyError, match="retired"):
        hygiene.validate_policy(policy(retired=["agentbridge"]))
    with pytest.raises(hygiene.PolicyError, match="runtimes.grok"):
        hygiene.validate_policy(policy(**{"runtimes.grok": []}))
    with pytest.raises(hygiene.PolicyError, match="runtimes.grok"):
        bad = policy()
        bad["runtimes"]["grok"].pop("executablePattern")
        bad["runtimes"]["grok"].pop("commandLineTokens")
        hygiene.validate_policy(bad)
    with pytest.raises(hygiene.PolicyError, match="escalation"):
        hygiene.validate_policy(policy(**{"escalation.stopActiveAtCritical": "yes"}))
    with pytest.raises(hygiene.PolicyError, match="integration.powershell"):
        hygiene.validate_policy(policy(**{"integration.powershell": 3}))
    with pytest.raises(hygiene.PolicyError, match="pressure.deescalateObservations"):
        hygiene.validate_policy(policy(**{"pressure.deescalateObservations": 0}))
    with pytest.raises(hygiene.PolicyError, match="runtimes.grok.softPrivateBytes"):
        hygiene.validate_policy(
            policy(
                **{
                    "runtimes.grok.softPrivateBytes": 5 * GIB,
                    "runtimes.grok.hardPrivateBytes": 4 * GIB,
                }
            )
        )


def test_policy_rejects_more_bad_fields():
    with pytest.raises(hygiene.PolicyError, match="commitRatioAbove"):
        hygiene.validate_policy(policy(**{"pressure.elevated.commitRatioAbove": "x"}))
    with pytest.raises(hygiene.PolicyError, match="critical.commitRatioAbove"):
        hygiene.validate_policy(policy(**{"pressure.critical.commitRatioAbove": 1.0}))
    with pytest.raises(hygiene.PolicyError, match="idle.observations"):
        hygiene.validate_policy(policy(**{"idle.observations": 0}))
    with pytest.raises(hygiene.PolicyError, match="orphanHandler"):
        hygiene.validate_policy(policy(**{"runtimes.grok.orphanHandler": "bad"}))
    with pytest.raises(hygiene.PolicyError, match="retired.*id"):
        hygiene.validate_policy(policy(retired=[{"id": "", "matchAll": ["a"]}]))
    with pytest.raises(hygiene.PolicyError, match="retired must be a list"):
        hygiene.validate_policy(policy(retired=123))
    with pytest.raises(hygiene.PolicyError, match="wsl.idleShutdown.observations"):
        hygiene.validate_policy(policy(**{"wsl.idleShutdown.observations": 0}))


def test_policy_optional_sections_default_when_missing():
    minimal = policy()
    minimal.pop("retired")
    minimal.pop("escalation")
    minimal.pop("notify")
    normalised = hygiene.validate_policy(minimal)
    assert normalised["retired"] == []
    assert normalised["escalation"]["stopActiveAtCritical"] is False
    assert normalised["escalation"]["maxStopsPerRun"] == 3
    assert normalised["escalation"]["crashLoopKills"] == 2
    assert normalised["integration"]["politeStopSeconds"] == 0
    assert normalised["notify"]["digestCooldownSeconds"] == 43_200


@pytest.mark.parametrize(
    "section",
    [
        "pressure",
        "pressure.elevated",
        "pressure.critical",
        "idle",
        "protected",
        "browsers",
        "runtimes.grok",
        "orphans",
        "mcp",
        "mcp.sameOwnerDuplicate",
        "mcp.singletonDuplicate",
        "mcp.overBudget",
        "wsl",
        "wsl.idleShutdown",
        "escalation",
        "integration",
        "ledger",
        "notify",
    ],
)
def test_policy_rejects_unknown_keys_in_every_section(section):
    # Found by the prune lens: a typo such as `orphanHandlr` used to be accepted
    # silently and disabled reaper delegation. Every section is now closed.
    bad = policy(**{f"{section}.typo": 1})
    with pytest.raises(hygiene.PolicyError, match="unknown key"):
        hygiene.validate_policy(bad)


def test_policy_rejects_unknown_key_in_a_retired_entry():
    bad = policy(retired=[{"id": "x", "matchAll": ["a"], "typo": 1}])
    with pytest.raises(hygiene.PolicyError, match="unknown key"):
        hygiene.validate_policy(bad)


@pytest.mark.parametrize(
    "section", ["pressure", "idle", "protected", "runtimes", "mcp", "wsl"]
)
def test_policy_missing_required_section_is_a_policy_error_not_a_traceback(section):
    bad = policy()
    bad.pop(section)
    with pytest.raises(hygiene.PolicyError, match=section):
        hygiene.validate_policy(bad)


def test_policy_legacy_per_rule_graceful_and_interval_keys_are_rejected():
    for dotted in (
        "runtimes.grok.gracefulSeconds",
        "orphans.gracefulSeconds",
        "mcp.gracefulSeconds",
    ):
        with pytest.raises(hygiene.PolicyError, match="unknown key"):
            hygiene.validate_policy(policy(**{dotted: 5}))
    with pytest.raises(hygiene.PolicyError, match="unknown key"):
        hygiene.validate_policy(policy(intervalSeconds=300))


def test_policy_commit_headroom_and_budget_knobs_validate():
    normalised = hygiene.validate_policy(policy())
    assert normalised["pressure"]["critical"]["headroom"] == 3 * GIB
    assert normalised["pressure"]["elevated"]["headroom"] == 8 * GIB
    with pytest.raises(hygiene.PolicyError, match="commitHeadroomBelow"):
        hygiene.validate_policy(
            policy(**{"pressure.critical.commitHeadroomBelow": 9 * GIB})
        )
    with pytest.raises(hygiene.PolicyError, match="maxStopsPerRun"):
        hygiene.validate_policy(policy(**{"escalation.maxStopsPerRun": 0}))
    with pytest.raises(hygiene.PolicyError, match="resumeHint"):
        hygiene.validate_policy(policy(**{"runtimes.grok.resumeHint": 5}))
    with pytest.raises(hygiene.PolicyError, match="wsl.action"):
        hygiene.validate_policy(policy(**{"wsl.action": "nuke"}))


def test_load_policy_reads_file(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy()), encoding="utf-8")
    assert hygiene.load_policy(path)["schema"] == hygiene.SCHEMA_POLICY


# -------------------------------------------------------------------- snapshot


def test_snapshot_parses_and_indexes():
    snapshot = hygiene.parse_snapshot(
        snap([proc(10, 1), proc(11, 10)], listeners={8317: 10}, compressed=9 * GIB)
    )
    assert snapshot.by_pid[11].ppid == 10
    assert snapshot.listeners == {8317: 10}
    assert snapshot.compressed_bytes == 9 * GIB
    assert snapshot.children[10] == [11]


def test_snapshot_rejects_wrong_schema_and_missing_fields():
    with pytest.raises(hygiene.SnapshotError, match="schema"):
        hygiene.parse_snapshot({"schema": "x"})
    bad = snap([proc(10, 1)])
    del bad["host"]["free_bytes"]
    with pytest.raises(hygiene.SnapshotError, match="free_bytes"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    del bad["processes"][0]["created_unix"]
    with pytest.raises(hygiene.SnapshotError, match="created_unix"):
        hygiene.parse_snapshot(bad)
    with pytest.raises(hygiene.SnapshotError, match="mapping"):
        hygiene.parse_snapshot([])
    bad = snap([proc(10, 1)])
    bad["processes"] = {}
    with pytest.raises(hygiene.SnapshotError, match="processes"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["processes"] = ["nope"]
    with pytest.raises(hygiene.SnapshotError, match="processes"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["host"]["physical_bytes"] = 0
    with pytest.raises(hygiene.SnapshotError, match="physical_bytes"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["listeners"] = [{"port": "x"}]
    with pytest.raises(hygiene.SnapshotError, match="listeners"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["wsl"] = []
    with pytest.raises(hygiene.SnapshotError, match="wsl"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["processes"][0]["pid"] = "10"
    with pytest.raises(hygiene.SnapshotError, match="pid"):
        hygiene.parse_snapshot(bad)


def test_snapshot_rejects_duplicate_pid():
    with pytest.raises(hygiene.SnapshotError, match="duplicate pid"):
        hygiene.parse_snapshot(snap([proc(10, 1), proc(10, 2)]))


def test_snapshot_rejects_bad_wsl_and_supervisor_fields():
    bad = snap([proc(10, 1)])
    bad["wsl"] = {"available": "yes", "running_distros": []}
    with pytest.raises(hygiene.SnapshotError, match="available"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["wsl"] = {"available": True, "running_distros": [1]}
    with pytest.raises(hygiene.SnapshotError, match="running_distros"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["supervisor_pids"] = ["x"]
    with pytest.raises(hygiene.SnapshotError, match="supervisor_pids"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1, cpu=True)])
    with pytest.raises(hygiene.SnapshotError, match="cpu_seconds"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1, name=1)])
    with pytest.raises(hygiene.SnapshotError, match="name"):
        hygiene.parse_snapshot(bad)


def test_snapshot_tolerates_unknown_metrics_and_missing_optional_blocks():
    payload = snap([proc(10, 1, cpu=None, io=None)])
    del payload["listeners"]
    del payload["supervisor_pids"]
    del payload["host"]["compressed_bytes"]
    del payload["wsl"]
    snapshot = hygiene.parse_snapshot(payload)
    assert snapshot.by_pid[10].cpu_seconds is None
    assert snapshot.compressed_bytes is None
    assert snapshot.supervisor_pids == set()
    assert snapshot.wsl_available is False


def test_engine_refuses_replayed_snapshot():
    eng = engine()
    observe(eng, [proc(10, 1)], 1)
    with pytest.raises(hygiene.SnapshotError, match="after"):
        eng.evaluate(hygiene.parse_snapshot(snap([proc(10, 1)], taken=NOW)))


# ------------------------------------------------------------------------ tiers


def test_tier_normal_when_ram_and_commit_are_comfortable():
    plan = observe(engine(), [proc(10, 1)], 1)
    assert plan.tier == "normal"
    assert plan.raw_tier == "normal"


def test_tier_elevated_by_available_ram():
    plan = observe(engine(), [proc(10, 1)], 1, free=3 * GIB)
    assert plan.tier == "elevated"
    assert plan.metrics["pressure_legs"]["available"] == "elevated"


def test_commit_ratio_alone_can_drive_critical():
    """The ratio leg needs a case where it is the ONLY leg tripping.

    A small-RAM box with a huge pagefile: 30 GiB committed on 10 GiB of RAM is
    3.0x (over the 2.5x critical leg), while available RAM is fine and 70 GiB of
    commit headroom remains. Without this case the ratio leg would be covered only
    by scenarios that ALSO trip headroom, and could be deleted unnoticed.
    """
    plan = observe(
        engine(),
        [proc(10, 1)],
        1,
        free=8 * GIB,
        physical=10 * GIB,
        commit=30 * GIB,
        commit_limit=100 * GIB,
    )
    assert plan.tier == "critical"
    assert plan.metrics["commit_ratio"] == pytest.approx(3.0, abs=0.001)
    assert plan.metrics["pressure_legs"] == {
        "available": "normal",
        "ratio": "critical",
        "headroom": "normal",
    }
    assert plan.metrics["pressure_modes"] == ["commit-exhaustion"]


def test_the_measured_box_is_critical_by_headroom_not_ratio():
    # 67.7 GB committed on 31.6 GB RAM is 2.14x - BELOW the 2.5x critical leg. It
    # reads critical because only ~1 GB of commit headroom is left under the
    # default 64 GiB limit. Naming the right leg matters: a pagefile change moves
    # headroom and leaves the ratio roughly where it was.
    plan = observe(
        engine(),
        [proc(10, 1)],
        1,
        free=3 * GIB,
        physical=31_600_000_000,
        commit=67_700_000_000,
    )
    assert plan.tier == "critical"
    assert plan.metrics["commit_ratio"] == pytest.approx(2.142, abs=0.001)
    assert plan.metrics["pressure_legs"]["ratio"] == "elevated"
    assert plan.metrics["pressure_legs"]["headroom"] == "critical"


def test_tier_deescalation_needs_repeated_calm_readings():
    eng = engine()
    procs = [proc(10, 1)]
    plan = eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=1, free=1 * GIB)))
    assert plan.tier == "critical"
    calm = eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=2)))
    assert calm.raw_tier == "normal"
    assert calm.tier == "critical"
    calm = eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=3)))
    assert calm.tier == "normal"
    hot = eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=4, free=1 * GIB)))
    assert hot.tier == "critical"


def test_tier_hysteresis_streak_resets_when_pressure_returns():
    eng = engine()
    procs = [proc(10, 1)]
    eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=1, free=1 * GIB)))
    eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=2)))
    hot = eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=3, free=1 * GIB)))
    assert hot.tier == "critical"
    again = eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=4)))
    assert again.tier == "critical"


# -------------------------------------------------------------------- retired


def grok_with_bridge(*, bridge_pid: int = 300, grok_pid: int = 200) -> list[dict]:
    return [
        proc(grok_pid, 1, name="grok.exe", exe=GROK_EXE, cmd="grok", created=ago(2000)),
        proc(
            bridge_pid,
            grok_pid,
            cmd=(
                "node C:\\Users\\Prekzursil\\AppData\\Roaming\\npm\\node_modules\\"
                "@raysonmeng\\agentbridge\\dist\\bridge-server.js"
            ),
            created=ago(1000),
            private=150 * MIB,
        ),
    ]


def test_retired_component_is_stopped_on_first_sight_at_normal_tier():
    plan = observe(engine(), grok_with_bridge(), 1)
    retired = by_rule(plan, "retired")
    assert len(retired) == 1
    decision = retired[0]
    assert decision.action == "stop"
    assert decision.min_tier == "normal"
    assert [member.pid for member in decision.tree] == [300]
    assert decision.detail["id"] == "agentbridge"
    assert "config.toml" in decision.detail["remediation"]
    assert decision.detail["parent_chain"][0]["pid"] == 200
    assert decision.detail["parent_chain"][0]["name"] == "grok.exe"
    assert 200 not in kill_pids(plan)


def test_retired_requires_every_token():
    procs = [proc(300, 1, cmd="node bridge-server.js", created=ago(1000))]
    plan = observe(engine(), procs, 1)
    assert by_rule(plan, "retired") == []


def test_retired_tree_takes_descendants_but_never_a_protected_member():
    procs = grok_with_bridge() + [
        proc(301, 300, cmd="node helper.js", created=ago(900)),
        proc(
            302,
            300,
            cmd="node C:\\Users\\Prekzursil\\Cowork\\tools\\auth2api\\dist\\index.js",
            created=ago(800),
        ),
    ]
    plan = observe(engine(), procs, 1)
    assert [member.pid for member in by_rule(plan, "retired")[0].tree] == [301, 300]


# -------------------------------------------------------------------- orphans


def orphan_node(**over) -> dict:
    base = dict(
        pid=400, ppid=9_999, cmd="node C:\\x\\mcp\\index.js", created=ago(10 * 3600)
    )
    base.update(over)
    return proc(**base)


def test_orphan_needs_age_and_idle_confirmations():
    eng = engine()
    plan = observe(eng, [orphan_node()], 3)
    assert by_rule(plan, "orphan") == []
    plan = eng.evaluate(hygiene.parse_snapshot(snap([orphan_node()], taken=NOW + STEP)))
    decisions = by_rule(plan, "orphan")
    assert len(decisions) == 1
    assert decisions[0].action == "stop"
    assert decisions[0].min_tier == "normal"
    assert decisions[0].detail["idle_observations"] == 3


def test_orphan_too_young_is_not_a_candidate():
    eng = engine()
    young = orphan_node(created=ago(300))
    plan = observe(eng, [young], 4)
    assert by_rule(plan, "orphan") == []


def test_orphan_active_process_never_confirms():
    eng = engine()
    for index in range(5):
        busy = orphan_node(cpu=1.0 + index)
        plan = eng.evaluate(
            hygiene.parse_snapshot(snap([busy], taken=NOW + index * STEP))
        )
    assert by_rule(plan, "orphan") == []


def test_orphan_io_activity_resets_idle_streak():
    eng = engine()
    observe(eng, [orphan_node()], 3)
    plan = eng.evaluate(
        hygiene.parse_snapshot(snap([orphan_node(io=11)], taken=NOW + STEP))
    )
    assert by_rule(plan, "orphan") == []
    assert eng.state["observations"][f"400|{ago(10 * 3600)}"]["idle_streak"] == 0


def test_orphan_unknown_metrics_fail_closed():
    eng = engine()
    plan = observe(eng, [orphan_node(cpu=None)], 5)
    assert by_rule(plan, "orphan") == []


def test_orphan_with_live_parent_is_not_a_candidate():
    procs = [terminal(), orphan_node()]
    plan = observe(engine(), procs, 4)
    assert by_rule(plan, "orphan") == []


def test_orphan_stale_ppid_pointing_at_a_newer_process_counts_as_orphan():
    procs = [
        proc(9_999, 1, name="pwsh.exe", exe=PWSH_EXE, cmd="pwsh", created=ago(60)),
        orphan_node(),
    ]
    plan = observe(engine(), procs, 4)
    assert len(by_rule(plan, "orphan")) == 1


def test_orphan_scope_is_limited_to_named_binaries():
    procs = [orphan_node(name="foo.exe", exe="C:\\tools\\foo.exe", cmd="foo")]
    plan = observe(engine(), procs, 4)
    assert by_rule(plan, "orphan") == []


def test_orphan_that_owns_a_listening_port_is_a_daemon_not_a_leak():
    procs = [orphan_node(cmd="node C:\\somewhere\\dist\\index.js")]
    plan = observe(engine(), procs, 4, listeners={8317: 400})
    assert by_rule(plan, "orphan") == []
    assert by_rule(plan, "daemon")[0].action == "report"


def test_orphan_tree_kills_children_first_and_skips_predating_children():
    procs = [
        orphan_node(),
        proc(
            401,
            400,
            name="cmd.exe",
            exe="C:\\Windows\\System32\\cmd.exe",
            created=ago(10 * 3600 - 100),
        ),
        proc(402, 401, cmd="node child.js", created=ago(10 * 3600 - 200)),
        proc(403, 400, cmd="node stale-ppid.js", created=ago(11 * 3600)),
    ]
    plan = observe(engine(), procs, 4)
    tree = by_rule(plan, "orphan")[0].tree
    assert [member.pid for member in tree] == [402, 400]


def test_orphan_generic_rule_covers_python_and_shells():
    procs = [
        orphan_node(pid=500, name="python.exe", exe=PY_EXE, cmd="python server.py"),
        orphan_node(pid=501, name="pwsh.exe", exe=PWSH_EXE, cmd="pwsh -File hook.ps1"),
    ]
    plan = observe(engine(), procs, 4)
    assert {decision.root.pid for decision in by_rule(plan, "orphan")} == {500, 501}


# ------------------------------------------------------- cursor-agent delegation


def cursor_root(pid: int = 600, ppid: int = 9_999, **over) -> dict:
    base = dict(
        pid=pid,
        ppid=ppid,
        exe=CURSOR_AGENT_EXE,
        cmd="node cursor-agent",
        created=ago(30 * 3600),
        private=311 * MIB,
    )
    base.update(over)
    return proc(**base)


def test_cursor_agent_orphan_is_delegated_to_the_reaper_when_available():
    eng = engine()
    plan = observe(eng, [cursor_root()], 4, reaper_available=True)
    assert by_rule(plan, "orphan") == []
    assert plan.delegate_reaper is True
    delegated = by_rule(plan, "cursor-orphan-reaper")
    assert len(delegated) == 1
    assert delegated[0].action == "report"
    assert delegated[0].detail["delegated"] is True


def test_cursor_agent_orphan_falls_back_to_generic_rule_without_the_reaper():
    plan = observe(engine(), [cursor_root()], 4, reaper_available=False)
    assert plan.delegate_reaper is False
    assert [decision.root.pid for decision in by_rule(plan, "orphan")] == [600]


def test_reaper_is_not_invoked_when_no_cursor_agent_root_is_parentless():
    procs = [
        proc(
            9_999, 1, name="pwsh.exe", exe=PWSH_EXE, cmd="pwsh", created=ago(40 * 3600)
        ),
        cursor_root(),
    ]
    plan = observe(engine(), procs, 1)
    assert plan.delegate_reaper is False


# ------------------------------------------------------------- session age


def test_session_age_stops_idle_stale_cli_session():
    procs = [terminal(), cursor_root()]
    plan = observe(engine(), procs, 4)
    decisions = by_rule(plan, "session-age")
    assert len(decisions) == 1
    assert decisions[0].action == "stop"
    assert decisions[0].min_tier == "normal"
    assert decisions[0].detail["runtime"] == "cursor-agent"
    assert decisions[0].detail["age_seconds"] == 30 * 3600
    assert decisions[0].graceful_seconds == 0  # polite stop is off by default
    assert "agent --resume" in decisions[0].detail["resume_hint"]


def test_session_age_active_session_is_only_reported():
    eng = engine()
    for index in range(4):
        procs = [terminal(), cursor_root(cpu=1.0 + index)]
        plan = eng.evaluate(
            hygiene.parse_snapshot(snap(procs, taken=NOW + index * STEP))
        )
    decisions = by_rule(plan, "session-age")
    assert len(decisions) == 1
    assert decisions[0].action == "report"


def test_session_age_ide_owned_agent_is_never_stopped():
    procs = [
        proc(
            700,
            1,
            name="Cursor.exe",
            exe=CURSOR_IDE_EXE,
            cmd="Cursor",
            created=ago(40 * 3600),
        ),
        cursor_root(ppid=700),
    ]
    plan = observe(engine(), procs, 4)
    decisions = by_rule(plan, "session-age")
    assert len(decisions) == 1
    assert decisions[0].action == "report"
    assert decisions[0].detail["owned_by"] == "cursor.exe"


def test_session_age_runtime_owned_by_another_runtime_is_reported_not_stopped():
    procs = [
        proc(
            800,
            1,
            name="claude.exe",
            exe=CLAUDE_EXE,
            cmd="claude",
            created=ago(40 * 3600),
        ),
        proc(
            801,
            800,
            name="codex.exe",
            exe=CODEX_EXE,
            cmd="codex mcp-server",
            created=ago(3 * 86_400),
        ),
    ]
    plan = observe(engine(), procs, 4)
    codex = [d for d in by_rule(plan, "session-age") if d.root.pid == 801]
    assert codex[0].action == "report"
    assert codex[0].detail["owned_by"] == "claude-code"


def test_session_age_within_limit_produces_nothing():
    procs = [terminal(), cursor_root(created=ago(3600))]
    plan = observe(engine(), procs, 4)
    assert by_rule(plan, "session-age") == []


def test_orphan_rule_never_swallows_a_detached_shell_hosting_a_runtime():
    # A detached idle pwsh hosting a cursor-agent must NOT be reaped wholesale by
    # the generic orphan rule - the runtime child is session-age's job, and the
    # husk shell is only reaped once it is a childless leaf.
    procs = [
        proc(
            9_999, 1, name="pwsh.exe", exe=PWSH_EXE, cmd="pwsh", created=ago(40 * 3600)
        ),
        cursor_root(ppid=9_999),
    ]
    plan = observe(engine(), procs, 4, reaper_available=True)
    assert by_rule(plan, "orphan") == []
    assert 9_999 not in kill_pids(plan)


def test_runtime_matched_by_command_line_token():
    procs = [
        proc(
            900, 1, cmd="node C:\\x\\grok-cli\\dist\\index.js", created=ago(5 * 86_400)
        )
    ]
    plan = observe(engine(), procs, 4)
    decisions = by_rule(plan, "session-age")
    assert decisions[0].detail["runtime"] == "grok"


# ------------------------------------------------------------------- rss


def fat_cursor(private: int, **over) -> list[dict]:
    return [terminal(), cursor_root(created=ago(1200), private=private, **over)]


def test_rss_soft_ceiling_reports_at_normal_and_stops_idle_at_elevated():
    plan = observe(engine(), fat_cursor(2 * GIB), 4)
    soft = by_rule(plan, "rss-soft")
    assert len(soft) == 1
    assert soft[0].action == "stop"
    assert soft[0].min_tier == "elevated"
    assert soft[0].tree_private_bytes == 2 * GIB
    assert by_rule(plan, "rss-hard") == []


def test_rss_hard_ceiling_stops_idle_at_normal():
    plan = observe(engine(), fat_cursor(4 * GIB), 4)
    hard = by_rule(plan, "rss-hard")
    assert len(hard) == 1
    assert hard[0].action == "stop"
    assert hard[0].min_tier == "normal"
    assert by_rule(plan, "rss-soft") == []


def test_rss_hard_ceiling_active_session_is_reported_unless_critical_opt_in():
    eng = engine()
    for index in range(4):
        plan = eng.evaluate(
            hygiene.parse_snapshot(
                snap(fat_cursor(4 * GIB, cpu=1.0 + index), taken=NOW + index * STEP)
            )
        )
    assert by_rule(plan, "rss-hard")[0].action == "report"

    eng = engine(policy(**{"escalation.stopActiveAtCritical": True}))
    for index in range(4):
        plan = eng.evaluate(
            hygiene.parse_snapshot(
                snap(fat_cursor(4 * GIB, cpu=1.0 + index), taken=NOW + index * STEP)
            )
        )
    hard = by_rule(plan, "rss-hard")
    assert hard[0].action == "stop"
    assert hard[0].min_tier == "critical"


def test_rss_tree_sums_descendants():
    procs = fat_cursor(1 * GIB) + [
        proc(601, 600, cmd="node mcp-child.js", created=ago(1100), private=GIB)
    ]
    plan = observe(engine(), procs, 4)
    soft = by_rule(plan, "rss-soft")
    assert soft[0].tree_private_bytes == 2 * GIB
    assert [member.pid for member in soft[0].tree] == [601, 600]


# -------------------------------------------------------------------- mcp


def claude_with_example(owner_pid: int, root_pid: int, *, created: int) -> list[dict]:
    return [
        proc(root_pid, owner_pid, cmd="npx -y @example/mcp-server", created=created),
        proc(
            root_pid + 1,
            root_pid,
            cmd="node C:/npm/@example/mcp-server/index.js",
            created=created + 1,
        ),
    ]


def claude_owner(pid: int = 2, created: int = ago(40 * 3600)) -> dict:
    return proc(
        pid, 1, name="claude.exe", exe=CLAUDE_EXE, cmd="claude", created=created
    )


def test_mcp_same_owner_duplicate_stops_the_younger_idle_tree_at_elevated():
    procs = [claude_owner()]
    procs += claude_with_example(2, 10, created=ago(6000))
    procs += claude_with_example(2, 20, created=ago(5000))
    plan = observe(engine(), procs, 4)
    dup = by_rule(plan, "mcp-duplicate-same-owner")
    assert len(dup) == 1
    assert dup[0].action == "stop"
    assert dup[0].min_tier == "elevated"
    assert dup[0].root.pid == 20
    assert [member.pid for member in dup[0].tree] == [21, 20]
    assert dup[0].detail["server"] == "example"
    assert dup[0].detail["kept_root"] == 10
    assert plan.metrics["fleet"]["duplicateServers"] == ["example"]


def test_mcp_same_owner_duplicate_active_tree_is_reported():
    eng = engine()
    for index in range(4):
        procs = [claude_owner()]
        procs += claude_with_example(2, 10, created=ago(6000))
        younger = claude_with_example(2, 20, created=ago(5000))
        younger[1]["cpu_seconds"] = 1.0 + index
        procs += younger
        plan = eng.evaluate(
            hygiene.parse_snapshot(snap(procs, taken=NOW + index * STEP))
        )
    dup = by_rule(plan, "mcp-duplicate-same-owner")
    assert dup[0].action == "report"


def test_mcp_cross_owner_duplicate_is_reported_with_the_shared_host_doctrine():
    procs = [claude_owner(2), claude_owner(3, created=ago(39 * 3600))]
    procs += claude_with_example(2, 10, created=ago(6000))
    procs += claude_with_example(3, 20, created=ago(5000))
    plan = observe(engine(), procs, 4)
    assert by_rule(plan, "mcp-duplicate-same-owner") == []
    cross = by_rule(plan, "mcp-duplicate-cross-owner")
    assert len(cross) == 1
    assert cross[0].action == "report"
    assert "mcp-http-host" in cross[0].detail["proposal"]
    assert cross[0].detail["owners"] == ["claude-code:2", "claude-code:3"]


def basic_memory_proc(
    pid: int, ppid: int, *, created: int, private: int = 800 * MIB
) -> dict:
    return proc(
        pid,
        ppid,
        name="python.exe",
        exe=PY_EXE,
        cmd="python -m basic_memory mcp --transport streamable-http",
        created=created,
        private=private,
    )


def test_mcp_singleton_duplicate_daemon_not_owning_the_port_is_stopped_past_grace():
    procs = [
        basic_memory_proc(50, 9_999, created=ago(90_000)),
        basic_memory_proc(51, 9_998, created=ago(11_200), private=300 * MIB),
    ]
    plan = observe(engine(), procs, 4, listeners={8765: 50})
    single = by_rule(plan, "mcp-singleton-duplicate")
    assert len(single) == 1
    assert single[0].root.pid == 51
    assert single[0].action == "stop"
    assert single[0].min_tier == "elevated"
    assert single[0].detail["port_owner"] == 50
    assert 50 not in kill_pids(plan)
    assert by_rule(plan, "orphan") == []


def test_mcp_singleton_duplicate_inside_grace_or_without_port_owner_is_left_alone():
    procs = [
        basic_memory_proc(50, 9_999, created=ago(90_000)),
        basic_memory_proc(51, 9_998, created=ago(200)),
    ]
    plan = observe(engine(), procs, 1, listeners={8765: 50})
    assert by_rule(plan, "mcp-singleton-duplicate") == []
    plan = observe(engine(), procs, 1)
    single = by_rule(plan, "mcp-singleton-duplicate")
    assert [decision.action for decision in single] == ["report"]


def test_mcp_over_budget_instance_reports_then_stops_idle_at_critical():
    procs = [claude_owner()]
    procs += claude_with_example(2, 10, created=ago(6000))
    procs[1]["private_bytes"] = 700 * MIB
    plan = observe(engine(), procs, 4)
    over = by_rule(plan, "mcp-over-budget")
    assert len(over) == 1
    assert over[0].action == "stop"
    assert over[0].min_tier == "critical"
    assert over[0].detail["limit_bytes"] == 512 * MIB
    assert plan.metrics["fleet"]["overBudgetServers"] == ["example"]


def test_mcp_over_budget_active_instance_is_reported():
    eng = engine()
    for index in range(4):
        procs = [claude_owner()]
        procs += claude_with_example(2, 10, created=ago(6000))
        procs[1]["private_bytes"] = 700 * MIB
        procs[1]["cpu_seconds"] = 1.0 + index
        plan = eng.evaluate(
            hygiene.parse_snapshot(snap(procs, taken=NOW + index * STEP))
        )
    assert by_rule(plan, "mcp-over-budget")[0].action == "report"


def test_mcp_disabled_skips_every_mcp_rule():
    procs = [claude_owner()]
    procs += claude_with_example(2, 10, created=ago(6000))
    procs += claude_with_example(2, 20, created=ago(5000))
    plan = observe(engine(policy(**{"mcp.enabled": False})), procs, 4)
    assert not [d for d in plan.decisions if d.rule.startswith("mcp-")]
    assert "fleet" not in plan.metrics


def test_mcp_assigned_child_is_not_double_counted_as_a_generic_orphan():
    procs = [
        proc(10, 9_999, cmd="npx -y @example/mcp-server", created=ago(10 * 3600)),
        proc(
            11,
            10,
            cmd="node C:/npm/@example/mcp-server/index.js",
            created=ago(10 * 3600 - 1),
        ),
    ]
    plan = observe(engine(), procs, 4)
    orphan = by_rule(plan, "orphan")
    assert len(orphan) == 1
    assert orphan[0].detail["mcp_server"] == "example"
    assert [member.pid for member in orphan[0].tree] == [11, 10]


# --------------------------------------------------------------------- wsl


def vmmem(private: int = 1100 * MIB, **over) -> dict:
    base = dict(
        pid=77,
        ppid=4,
        name="vmmemWSL",
        exe="",
        cmd="",
        created=ago(50 * 3600),
        private=private,
        ws=private,
    )
    base.update(over)
    return proc(**base)


def test_wsl_report_above_threshold_and_idle_shutdown_at_elevated():
    eng = engine(
        policy(
            **{"wsl.reportPrivateBytesAbove": GIB, "wsl.idleShutdown.observations": 3}
        )
    )
    plan = observe(eng, [vmmem()], 4, wsl_running=("Ubuntu",), free=3 * GIB)
    report = by_rule(plan, "wsl-report")
    assert len(report) == 1
    assert report[0].action == "report"
    shutdown = by_rule(plan, "wsl-idle")
    assert len(shutdown) == 1
    assert shutdown[0].action == "wsl-shutdown"
    assert shutdown[0].min_tier == "elevated"
    assert plan.wsl_shutdown is True
    assert kill_pids(plan) == set()


def test_wsl_idle_shutdown_needs_the_configured_observations():
    eng = engine(policy(**{"wsl.idleShutdown.observations": 6}))
    plan = observe(eng, [vmmem()], 4, wsl_running=("Ubuntu",), free=3 * GIB)
    assert by_rule(plan, "wsl-idle") == []
    assert plan.wsl_shutdown is False


def test_wsl_busy_vm_or_unavailable_wsl_is_left_alone():
    eng = engine(policy(**{"wsl.idleShutdown.observations": 3}))
    for index in range(4):
        plan = eng.evaluate(
            hygiene.parse_snapshot(
                snap(
                    [vmmem(cpu=10.0 + index)],
                    taken=NOW + index * STEP,
                    wsl_running=("Ubuntu",),
                    free=3 * GIB,
                )
            )
        )
    assert by_rule(plan, "wsl-idle") == []
    eng = engine(policy(**{"wsl.idleShutdown.observations": 3}))
    plan = observe(
        eng, [vmmem()], 4, wsl_running=("Ubuntu",), free=3 * GIB, wsl_available=False
    )
    assert by_rule(plan, "wsl-idle") == []
    assert by_rule(plan, "wsl-report") == []


def test_wsl_without_running_distro_reports_the_vm_but_does_not_shut_down():
    eng = engine(policy(**{"wsl.idleShutdown.observations": 3}))
    plan = observe(eng, [vmmem(private=3 * GIB)], 4, free=3 * GIB)
    assert len(by_rule(plan, "wsl-report")) == 1
    assert by_rule(plan, "wsl-idle") == []


def test_wsl_small_vm_below_threshold_is_silent():
    plan = observe(engine(), [vmmem(private=200 * MIB)], 1, wsl_running=("Ubuntu",))
    assert by_rule(plan, "wsl-report") == []


# ----------------------------------------------------------------- browsers


def test_browser_aggregate_is_reported_never_stopped():
    procs = [
        proc(
            1000 + index,
            9_999,
            name="chrome.exe",
            exe="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            cmd="chrome --type=renderer",
            created=ago(2 * 3600),
            private=70 * MIB,
        )
        for index in range(70)
    ]
    plan = observe(engine(), procs, 4)
    report = by_rule(plan, "browser")
    assert len(report) == 1
    assert report[0].action == "report"
    assert report[0].detail["process_count"] == 70
    assert report[0].detail["private_bytes"] == 70 * 70 * MIB
    assert "Memory Saver" in report[0].detail["proposal"]
    assert kill_pids(plan) == set()


def test_browser_below_threshold_is_silent():
    procs = [
        proc(
            1000,
            1,
            name="msedge.exe",
            exe="C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            cmd="msedge",
            created=ago(2 * 3600),
            private=500 * MIB,
        )
    ]
    plan = observe(engine(), procs, 1)
    assert by_rule(plan, "browser") == []


# --------------------------------------------------------------- protected


@pytest.mark.parametrize(
    "row",
    [
        proc(
            400,
            9_999,
            cmd="node C:\\Users\\Prekzursil\\Cowork\\tools\\auth2api\\dist\\index.js",
            created=ago(105 * 3600),
        ),
        proc(
            400,
            9_999,
            name="pwsh.exe",
            exe=PWSH_EXE,
            cmd="pwsh -File C:\\Users\\Prekzursil\\.basic-memory\\bm-watchdog.ps1",
            created=ago(10 * 3600),
        ),
        proc(
            400,
            9_999,
            name="svchost.exe",
            exe="C:\\Windows\\System32\\svchost.exe",
            cmd="svchost -k netsvcs",
            created=ago(10 * 3600),
        ),
        proc(400, 9_999, name="node.exe", exe="", cmd="", created=ago(10 * 3600)),
        proc(
            400,
            9_999,
            name="python.exe",
            exe=PY_EXE,
            cmd="python C:\\x\\tools\\process-hygiene-supervisor\\hygiene.py run",
            created=ago(10 * 3600),
        ),
    ],
    ids=["auth2api", "bm-watchdog", "windows-binary", "no-executable", "self"],
)
def test_protected_processes_survive_the_orphan_rule(row):
    plan = observe(engine(), [row], 4)
    assert kill_pids(plan) == set()
    assert by_rule(plan, "orphan") == []


def test_supervisor_pids_from_the_snapshot_are_protected():
    row = orphan_node(cmd="node whatever.js")
    plan = observe(engine(), [row], 4, supervisor_pids=(400,))
    assert kill_pids(plan) == set()


def test_protected_process_reports_pressure_but_is_never_in_a_tree():
    procs = [
        terminal(),
        cursor_root(),
        proc(
            601,
            600,
            cmd="node C:\\Users\\Prekzursil\\Cowork\\tools\\auth2api\\dist\\index.js",
            created=ago(29 * 3600),
        ),
    ]
    plan = observe(engine(), procs, 4)
    decision = by_rule(plan, "session-age")[0]
    assert [member.pid for member in decision.tree] == [600]
    assert decision.detail["protected_members"] == [601]


# ------------------------------------------------------------- observations


def test_state_prunes_observations_of_departed_processes():
    eng = engine()
    observe(eng, [proc(10, 1), proc(11, 1)], 2)
    eng.evaluate(hygiene.parse_snapshot(snap([proc(10, 1)], taken=NOW + STEP)))
    assert set(eng.state["observations"]) == {f"10|{ago(6 * 3600)}"}


def test_state_records_run_metadata():
    eng = engine()
    plan = observe(eng, [proc(10, 1)], 1)
    assert eng.state["schema"] == hygiene.SCHEMA_STATE
    assert eng.state["last_run_unix"] == NOW
    assert eng.state["tier"]["current"] == plan.tier


def test_engine_rejects_foreign_state():
    with pytest.raises(hygiene.PolicyError, match="state"):
        engine(state={"schema": "something-else"})


def test_engine_requires_registry_when_mcp_is_enabled():
    with pytest.raises(hygiene.PolicyError, match="registry"):
        hygiene.Engine(
            hygiene.validate_policy(policy()),
            {},
            fleet=hygiene.load_fleet(hygiene.DEFAULT_FLEET_PATH),
            registry=None,
        )


def test_load_fleet_fails_closed_on_a_missing_module(tmp_path):
    with pytest.raises(hygiene.PolicyError, match="fleet supervisor"):
        hygiene.load_fleet(tmp_path / "missing.py")


# ------------------------------------------------------------------ ledger


def test_ledger_redacts_secrets_and_rotates(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = hygiene.Ledger(path, max_bytes=400)
    secret = "github_pat_" + "A" * 30
    row = hygiene.parse_snapshot(
        snap([proc(10, 1, cmd=f"node server --token={secret} --port 1")])
    ).by_pid[10]
    ledger.append(
        hygiene.record_for(
            row,
            rule="orphan",
            action="stop",
            tier="normal",
            result="ok",
            reason="test",
            run_id="r1",
            ts=1,
        )
    )
    text = path.read_text(encoding="utf-8")
    assert secret not in text
    assert "[REDACTED]" in text
    entry = json.loads(text.splitlines()[0])
    assert entry["schema"] == hygiene.SCHEMA_LEDGER
    assert entry["pid"] == 10
    assert len(entry["command_sha256"]) == 16
    for index in range(5):
        ledger.append({"schema": hygiene.SCHEMA_LEDGER, "n": index, "pad": "x" * 100})
    assert (tmp_path / "ledger.jsonl.1").exists()
    assert path.stat().st_size < 400


def test_ledger_redacts_flag_carried_secrets_without_a_known_prefix(tmp_path):
    # Found by the autoresearch mutation loop: the only redaction test used a
    # github_pat_ value that the literal-prefix regex ALSO catches, so breaking
    # the --flag=value redaction stayed green. A plain password must not leak.
    ledger = hygiene.Ledger(tmp_path / "l.jsonl", max_bytes=10_000)
    secret = "Zq9vT2hunter2ManyRandomChars"
    row = hygiene.parse_snapshot(
        snap(
            [
                proc(
                    10,
                    1,
                    cmd=f"python srv.py --password={secret} --api-key {secret}X --port 80",
                )
            ]
        )
    ).by_pid[10]
    ledger.append(
        hygiene.record_for(
            row,
            rule="orphan",
            action="report",
            tier="normal",
            result="dry-run",
            reason="",
            run_id="r",
            ts=1,
        )
    )
    text = (tmp_path / "l.jsonl").read_text(encoding="utf-8")
    assert secret not in text
    assert text.count("[REDACTED]") == 2
    assert "--port 80" in text


def test_ledger_truncates_long_command_lines(tmp_path):
    ledger = hygiene.Ledger(tmp_path / "l.jsonl", max_bytes=10_000)
    row = hygiene.parse_snapshot(snap([proc(10, 1, cmd="x" * 2000)])).by_pid[10]
    ledger.append(
        hygiene.record_for(
            row,
            rule="orphan",
            action="report",
            tier="normal",
            result="dry-run",
            reason="",
            run_id="r",
            ts=1,
        )
    )
    entry = json.loads((tmp_path / "l.jsonl").read_text(encoding="utf-8"))
    assert len(entry["command_line"]) == hygiene.COMMAND_LINE_MAX + len("...")


# --------------------------------------------------------------- apply_plan


class FakeActuator:
    def __init__(
        self, *, fail_pids: set[int] | None = None, reaper: dict | None = None
    ):
        self.stopped: list[tuple[list[int], int]] = []
        self.fail_pids = fail_pids or set()
        self.wsl_calls = 0
        self.reaper_calls: list[bool] = []
        self.reaper = reaper or {
            "status": "success",
            "candidates": 1,
            "confirmed": 0,
            "reaped": 0,
            "failed_survivors": [],
            "exit_code": 0,
        }

    def stop_tree(self, tree, *, graceful_seconds):
        self.stopped.append(([member.pid for member in tree], graceful_seconds))
        return [
            hygiene.StopResult(
                pid=member.pid,
                created_unix=member.created_unix,
                outcome="failed" if member.pid in self.fail_pids else "forced",
                detail="",
            )
            for member in tree
        ]

    def wsl_shutdown(self, *, distros=(), action="terminate"):
        self.wsl_calls += 1
        self.wsl_args = (list(distros), action)
        return hygiene.StopResult(
            pid=0, created_unix=0, outcome="ok", detail=f"wsl --{action}"
        )

    def run_reaper(self, *, apply):
        self.reaper_calls.append(apply)
        return dict(self.reaper)


def ledger_rows(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def mixed_plan(
    eng: hygiene.Engine | None = None, *, free: int = 3 * GIB
) -> hygiene.Plan:
    eng = eng or engine(policy(**{"wsl.idleShutdown.observations": 3}))
    procs = grok_with_bridge() + [orphan_node(), cursor_root(), vmmem()]
    return observe(eng, procs, 4, wsl_running=("Ubuntu",), free=free)


def test_apply_plan_report_only_touches_nothing_but_writes_the_ledger(tmp_path):
    plan = mixed_plan()
    actuator = FakeActuator()
    ledger = hygiene.Ledger(tmp_path / "ledger.jsonl")
    summary = hygiene.apply_plan(plan, actuator, ledger, apply=False, run_id="run-1")
    assert actuator.stopped == []
    assert actuator.wsl_calls == 0
    assert actuator.reaper_calls == []
    rows = ledger_rows(tmp_path / "ledger.jsonl")
    results = {row["result"] for row in rows if row["action"] == "stop"}
    assert results == {"dry-run"}
    assert rows[-1]["rule"] == "run"
    assert rows[-1]["detail"]["tier"] == "elevated"
    assert summary["stopped"] == 0
    assert summary["dry_run"] >= 2
    assert summary["failed"] == 0


def test_apply_plan_applies_only_decisions_at_or_below_the_current_tier(tmp_path):
    plan = mixed_plan(free=8 * GIB)
    assert plan.tier == "normal"
    actuator = FakeActuator()
    ledger = hygiene.Ledger(tmp_path / "ledger.jsonl")
    summary = hygiene.apply_plan(plan, actuator, ledger, apply=True, run_id="run-2")
    killed = {pid for pids, _ in actuator.stopped for pid in pids}
    assert killed == {300, 400}
    assert actuator.wsl_calls == 0
    assert actuator.reaper_calls == [True]
    rows = ledger_rows(tmp_path / "ledger.jsonl")
    deferred = [row for row in rows if row["result"] == "deferred"]
    assert {row["rule"] for row in deferred} == {"wsl-idle"}
    assert summary["stopped"] == 2
    assert summary["deferred"] == 1
    assert [
        row["rule"]
        for row in rows
        if row["rule"] == "cursor-orphan-reaper" and row["action"] == "delegate"
    ] == ["cursor-orphan-reaper"]


def test_apply_plan_at_elevated_tier_shuts_wsl_down_and_records_outcomes(tmp_path):
    plan = mixed_plan()
    assert plan.tier == "elevated"
    actuator = FakeActuator(fail_pids={400})
    ledger = hygiene.Ledger(tmp_path / "ledger.jsonl")
    summary = hygiene.apply_plan(plan, actuator, ledger, apply=True, run_id="run-3")
    assert actuator.wsl_calls == 1
    rows = ledger_rows(tmp_path / "ledger.jsonl")
    outcomes = {row["pid"]: row["result"] for row in rows if row["action"] == "stop"}
    assert outcomes[300] == "forced"
    assert outcomes[400] == "failed"
    assert summary["failed"] == 1
    assert summary["stopped"] == 1
    assert summary["exit_code"] == 2
    assert [row["result"] for row in rows if row["rule"] == "wsl-idle"] == ["ok"]


def test_apply_plan_records_reaper_failure_as_failed(tmp_path):
    plan = mixed_plan()
    actuator = FakeActuator(
        reaper={"status": "error", "exit_code": 1, "reason": "malformed state"}
    )
    ledger = hygiene.Ledger(tmp_path / "ledger.jsonl")
    summary = hygiene.apply_plan(plan, actuator, ledger, apply=True, run_id="run-4")
    reaper_rows = [
        row
        for row in ledger_rows(tmp_path / "ledger.jsonl")
        if row["rule"] == "cursor-orphan-reaper" and row["action"] == "delegate"
    ]
    assert reaper_rows[0]["result"] == "failed"
    assert summary["exit_code"] == 2


def test_apply_plan_skips_the_reaper_when_nothing_is_delegated(tmp_path):
    plan = observe(engine(), [proc(10, 1)], 1)
    actuator = FakeActuator()
    hygiene.apply_plan(
        plan, actuator, hygiene.Ledger(tmp_path / "l.jsonl"), apply=True, run_id="r"
    )
    assert actuator.reaper_calls == []


def test_apply_plan_uses_the_global_polite_stop_window(tmp_path):
    plan = observe(
        engine(policy(**{"integration.politeStopSeconds": 7})), grok_with_bridge(), 1
    )
    actuator = FakeActuator()
    hygiene.apply_plan(
        plan, actuator, hygiene.Ledger(tmp_path / "l.jsonl"), apply=True, run_id="r"
    )
    assert actuator.stopped == [([300], 7)]
    plan = observe(engine(), grok_with_bridge(), 1)
    actuator = FakeActuator()
    hygiene.apply_plan(
        plan, actuator, hygiene.Ledger(tmp_path / "l2.jsonl"), apply=True, run_id="r"
    )
    assert actuator.stopped == [([300], 0)]


# -------------------------------------------------------------------- cli


def write(path: pathlib.Path, payload) -> pathlib.Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def cli_files(
    tmp_path: pathlib.Path, procs: list[dict], **snap_kwargs
) -> dict[str, pathlib.Path]:
    return {
        "snapshot": write(tmp_path / "snapshot.json", snap(procs, **snap_kwargs)),
        "policy": write(tmp_path / "policy.json", policy()),
        "registry": write(tmp_path / "agents.json", registry()),
        "state": tmp_path / "state.json",
        "ledger": tmp_path / "ledger.jsonl",
    }


def run_cli(files: dict[str, pathlib.Path], *extra: str) -> int:
    return hygiene.main(
        [
            "run",
            "--snapshot",
            str(files["snapshot"]),
            "--policy",
            str(files["policy"]),
            "--registry",
            str(files["registry"]),
            "--state",
            str(files["state"]),
            "--ledger",
            str(files["ledger"]),
            "--reaper-available",
            "no",
            *extra,
        ]
    )


def test_cli_run_report_only_writes_state_and_ledger(tmp_path, capsys):
    files = cli_files(tmp_path, grok_with_bridge())
    assert run_cli(files) == 0
    out = capsys.readouterr().out
    assert "SUCCESS:process-hygiene" in out
    assert "apply=false" in out
    state = json.loads(files["state"].read_text(encoding="utf-8"))
    assert state["schema"] == hygiene.SCHEMA_STATE
    rows = ledger_rows(files["ledger"])
    assert any(row["rule"] == "retired" and row["result"] == "dry-run" for row in rows)


def test_cli_run_apply_uses_the_windows_actuator(tmp_path, capsys, monkeypatch):
    calls = {}

    def build(policy_obj, **kwargs):
        calls["policy"] = policy_obj
        calls["kwargs"] = kwargs
        return FakeActuator()

    monkeypatch.setattr(hygiene, "build_actuator", build)
    files = cli_files(tmp_path, grok_with_bridge())
    assert run_cli(files, "--apply") == 0
    assert calls["policy"]["schema"] == hygiene.SCHEMA_POLICY
    out = capsys.readouterr().out
    assert "apply=true" in out
    rows = ledger_rows(files["ledger"])
    assert any(row["rule"] == "retired" and row["result"] == "forced" for row in rows)


def test_cli_run_reports_failed_kills_with_exit_two(tmp_path, monkeypatch):
    monkeypatch.setattr(
        hygiene,
        "build_actuator",
        lambda policy_obj, **kwargs: FakeActuator(fail_pids={300}),
    )
    files = cli_files(tmp_path, grok_with_bridge())
    assert run_cli(files, "--apply") == 2


def test_cli_fails_closed_on_bad_policy(tmp_path, capsys):
    files = cli_files(tmp_path, [proc(10, 1)])
    write(files["policy"], {"schema": "wrong"})
    assert run_cli(files) == 1
    assert "FAILED:process-hygiene" in capsys.readouterr().out
    assert not files["ledger"].exists()


def test_cli_fails_closed_on_malformed_state(tmp_path, capsys):
    files = cli_files(tmp_path, [proc(10, 1)])
    files["state"].write_text("{not json", encoding="utf-8")
    assert run_cli(files) == 1
    assert "state" in capsys.readouterr().out


def test_cli_fails_closed_on_bad_snapshot_and_missing_registry(tmp_path, capsys):
    files = cli_files(tmp_path, [proc(10, 1)])
    write(files["snapshot"], {"schema": "x"})
    assert run_cli(files) == 1
    files = cli_files(tmp_path, [proc(10, 1)])
    files["registry"].unlink()
    assert run_cli(files) == 1
    assert "registry" in capsys.readouterr().out


def test_cli_second_run_reuses_state(tmp_path):
    files = cli_files(tmp_path, [orphan_node()])
    assert run_cli(files) == 0
    write(files["snapshot"], snap([orphan_node()], taken=NOW + STEP))
    assert run_cli(files) == 0
    state = json.loads(files["state"].read_text(encoding="utf-8"))
    assert state["observations"][f"400|{ago(10 * 3600)}"]["idle_streak"] == 1


def test_cli_reaper_available_auto_checks_the_path(tmp_path):
    files = cli_files(tmp_path, [cursor_root()])
    reaper = tmp_path / "reaper.ps1"
    reaper.write_text("exit 0", encoding="utf-8")
    write(files["policy"], policy(**{"integration.reaperPath": str(reaper)}))
    assert (
        hygiene.main(
            [
                "run",
                "--snapshot",
                str(files["snapshot"]),
                "--policy",
                str(files["policy"]),
                "--registry",
                str(files["registry"]),
                "--state",
                str(files["state"]),
                "--ledger",
                str(files["ledger"]),
            ]
        )
        == 0
    )
    rows = ledger_rows(files["ledger"])
    assert any(row["rule"] == "cursor-orphan-reaper" for row in rows)
    write(files["snapshot"], snap([cursor_root()], taken=NOW + STEP))
    write(
        files["policy"],
        policy(**{"integration.reaperPath": str(tmp_path / "gone.ps1")}),
    )
    assert run_cli(files) == 0


def test_cli_validate_commands(tmp_path, capsys):
    files = cli_files(tmp_path, [proc(10, 1)])
    assert hygiene.main(["validate-policy", "--policy", str(files["policy"])]) == 0
    assert "SUCCESS:process-hygiene-policy" in capsys.readouterr().out
    write(files["policy"], {"schema": "wrong"})
    assert hygiene.main(["validate-policy", "--policy", str(files["policy"])]) == 1
    assert "FAILED" in capsys.readouterr().out
    assert (
        hygiene.main(["validate-snapshot", "--snapshot", str(files["snapshot"])]) == 0
    )
    assert "SUCCESS:process-hygiene-snapshot" in capsys.readouterr().out
    write(files["snapshot"], {"schema": "x"})
    assert (
        hygiene.main(["validate-snapshot", "--snapshot", str(files["snapshot"])]) == 1
    )


def test_cli_explain_prints_decisions_without_writing_state(tmp_path, capsys):
    files = cli_files(tmp_path, grok_with_bridge())
    code = hygiene.main(
        [
            "explain",
            "--snapshot",
            str(files["snapshot"]),
            "--policy",
            str(files["policy"]),
            "--registry",
            str(files["registry"]),
            "--state",
            str(files["state"]),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tier"] == "normal"
    assert payload["decisions"][0]["rule"] == "retired"
    assert not files["state"].exists()


def test_cli_default_paths_resolve_inside_the_repo():
    assert hygiene.DEFAULT_FLEET_PATH.is_file()
    assert hygiene.DEFAULT_REGISTRY_PATH.is_file()
    assert hygiene.DEFAULT_POLICY_PATH.is_file()


def test_real_registry_validates_with_the_shipped_fleet_supervisor():
    fleet = hygiene.load_fleet(hygiene.DEFAULT_FLEET_PATH)
    config = json.loads(hygiene.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    fleet.control.validate_registry(config)


# ------------------------------------------------- research-driven guards


def test_metrics_separate_the_two_failure_modes_behind_one_tier():
    """`tier` is one ordinal scale over two failures with DIFFERENT remedies.

    Commit-limit exhaustion fails allocations (the mode that kills the Basic
    Memory daemon) and is relieved by reducing commit or a bigger pagefile.
    Working-set pressure means the touched set exceeds RAM: hard faults and a
    growing compression store, i.e. the freezes - and a pagefile does nothing for
    it. The tier gate stays one scale, but the ledger names which mode is live so
    the owner is not told "critical" without being told critical of what.
    """
    thrash = observe(
        engine(), [proc(10, 1)], 1, free=1 * GIB, commit=20 * GIB, commit_limit=80 * GIB
    )
    assert thrash.tier == "critical"
    assert thrash.metrics["pressure_modes"] == ["working-set"]
    assert thrash.metrics["pressure_legs"] == {
        "available": "critical",
        "ratio": "normal",
        "headroom": "normal",
    }

    starved = observe(
        engine(),
        [proc(10, 1)],
        1,
        free=20 * GIB,
        physical=31_600_000_000,
        commit=67_700_000_000,
        commit_limit=70_000_000_000,
    )
    assert starved.tier == "critical"
    assert starved.metrics["pressure_modes"] == ["commit-exhaustion"]

    both = observe(
        engine(),
        [proc(10, 1)],
        1,
        free=1 * GIB,
        physical=31_600_000_000,
        commit=67_700_000_000,
        commit_limit=70_000_000_000,
    )
    assert both.metrics["pressure_modes"] == ["commit-exhaustion", "working-set"]

    calm = observe(engine(), [proc(10, 1)], 1)
    assert calm.metrics["pressure_modes"] == []
    # An unknown commit limit cannot report a commit verdict it did not measure.
    unknown = observe(engine(), [proc(10, 1)], 1, commit_limit=0)
    assert unknown.metrics["pressure_legs"]["headroom"] == "unknown"


def test_digest_line_names_the_live_failure_mode():
    plan = observe(engine(), grok_with_bridge(), 1, free=1 * GIB)
    line = hygiene.digest_line(
        plan,
        {
            "stopped": 1,
            "failed": 0,
            "exit_code": 0,
            "run_id": "r",
            "rules": ["retired"],
        },
        {},
        apply=True,
        cooldown=100,
        stamp="s",
    )
    assert "tier=critical(working-set)" in line


def wrapper_tree(
    *, wrapper="cmd.exe", cmd="cmd /c npx -y @modelcontextprotocol/server-git"
):
    return [
        proc(
            700,
            1,
            name="Cursor.exe",
            exe=CURSOR_IDE_EXE,
            cmd="Cursor",
            created=ago(9000),
        ),
        proc(
            710,
            700,
            name=wrapper,
            exe=f"C:/Windows/System32/{wrapper}",
            cmd=cmd,
            created=ago(8000),
        ),
        proc(
            720,
            710,
            name="node.exe",
            exe="C:/Program Files/nodejs/node.exe",
            cmd="node C:/npm/server-git/dist/index.js",
            created=ago(7900),
        ),
    ]


def test_wrapper_chain_is_reported_once_per_wrapper_with_the_direct_exec_fix():
    """A wrapper chain is STRUCTURALLY orphan-prone, so it is worth naming early.

    libuv hosts (Cursor, the VS Code extension host) put their direct child in a
    job with KILL_ON_JOB_CLOSE *and* SILENT_BREAKAWAY_OK, so grandchildren are
    deliberately excluded from that job and outlive the host. With
    `cmd /c npx …` the real server is a grandchild; launched as `node.exe
    <entry.js>` it is the direct child and the OS reaps it with the host.
    """
    plan = observe(engine(), wrapper_tree(), 4)
    rows = by_rule(plan, "wrapper-chain")
    assert len(rows) == 1  # one row per wrapper root, not per descendant
    row = rows[0]
    assert row.action == "report"
    assert row.root.pid == 710
    assert row.detail["matched"] == "cmd /c"
    assert row.detail["server_pids"] == [720]
    assert "silent_breakaway" in row.detail["reason"]
    assert "node.exe" in row.detail["remediation"]
    assert kill_pids(plan) == set()


@pytest.mark.parametrize(
    "cmd,matched",
    [
        ("cmd /c npx -y some-server", "cmd /c"),
        ("C:/nodejs/npx.cmd server", "npx"),
        # the real Windows spelling of `npm exec` / `npx <pkg>`
        ("node C:/npm/node_modules/npm/bin/npm-cli.js exec server", "npm-cli.js exec"),
        ("node C:/npm/node_modules/npm/bin/npx-cli.js server", "npx"),
        ("uv tool run mcp-server-git", "uv tool run"),
        ("uvx mcp-server-git", "uvx"),
    ],
)
def test_every_default_wrapper_token_is_recognised(cmd, matched):
    plan = observe(engine(), wrapper_tree(wrapper="wrap.exe", cmd=cmd), 4)
    rows = by_rule(plan, "wrapper-chain")
    assert [row.detail["matched"] for row in rows] == [matched]


def test_wrapper_without_a_surviving_server_child_is_not_reported():
    # A wrapper whose server already exited is not a config defect to chase.
    procs = wrapper_tree()[:2]
    assert by_rule(observe(engine(), procs, 4), "wrapper-chain") == []
    # ...and a direct-exec server (no wrapper ancestry) is the GOOD shape.
    good = [
        proc(
            700,
            1,
            name="Cursor.exe",
            exe=CURSOR_IDE_EXE,
            cmd="Cursor",
            created=ago(9000),
        ),
        proc(
            720,
            700,
            name="node.exe",
            exe="C:/Program Files/nodejs/node.exe",
            cmd="node C:/npm/server-git/dist/index.js",
            created=ago(7900),
        ),
    ]
    assert by_rule(observe(engine(), good, 4), "wrapper-chain") == []


def test_wrapper_chain_reporting_can_be_disabled():
    plan = observe(engine(engine_policy_without_wrapper_tokens()), wrapper_tree(), 4)
    assert by_rule(plan, "wrapper-chain") == []


def engine_policy_without_wrapper_tokens():
    pol = policy()
    pol["wrapperChains"] = {"tokens": []}
    return pol


def test_tier_critical_is_driven_by_commit_headroom_not_ratio():
    # 67.7 GB committed on 31.6 GB physical is this box's chronic baseline
    # (2.14x); with 12 GB of headroom left it is elevated (by free RAM), not a
    # permanent emergency. Squeeze the commit LIMIT and the same box is critical.
    roomy = observe(
        engine(),
        [proc(10, 1)],
        1,
        free=5 * GIB,
        physical=31_600_000_000,
        commit=67_700_000_000,
        commit_limit=80_000_000_000,
    )
    assert roomy.tier == "elevated"
    assert roomy.metrics["commit_headroom_bytes"] == 80_000_000_000 - 67_700_000_000
    tight = observe(
        engine(),
        [proc(10, 1)],
        1,
        free=5 * GIB,
        physical=31_600_000_000,
        commit=67_700_000_000,
        commit_limit=70_000_000_000,
    )
    assert tight.tier == "critical"
    # A missing commit limit (0) disables the headroom leg rather than tripping it.
    unknown = observe(engine(), [proc(10, 1)], 1, commit_limit=0)
    assert unknown.tier == "normal"
    assert unknown.metrics["commit_headroom_bytes"] is None


def test_runtime_without_a_resume_hint_omits_the_field():
    pol = policy()
    pol["runtimes"]["grok"].pop("resumeHint")
    procs = [
        proc(
            900, 1, cmd="node C:\\x\\grok-cli\\dist\\index.js", created=ago(5 * 86_400)
        )
    ]
    plan = observe(engine(pol), procs, 4)
    assert "resume_hint" not in by_rule(plan, "session-age")[0].detail


def test_rss_hard_on_an_ide_owned_agent_is_reported_never_stopped():
    # Prune-lens finding: session-age respected IDE ownership but rss did not.
    procs = [
        proc(
            700,
            1,
            name="Cursor.exe",
            exe=CURSOR_IDE_EXE,
            cmd="Cursor",
            created=ago(40 * 3600),
        ),
        cursor_root(ppid=700, created=ago(1200), private=4 * GIB),
    ]
    plan = observe(engine(), procs, 4)
    hard = by_rule(plan, "rss-hard")
    assert len(hard) == 1
    assert hard[0].action == "report"
    assert hard[0].detail["owned_by"] == "cursor.exe"
    assert "resume_hint" in hard[0].detail
    assert kill_pids(plan) == set()


def snap_with_connections(procs, connections, **kw):
    payload = snap(procs, **kw)
    payload["connections"] = [
        {"pid": pid, "remote": remote} for pid, remote in connections
    ]
    return payload


def observe_connected(eng, procs, rounds, connections, *, end=NOW):
    plan = None
    for index in range(rounds):
        taken = end - (rounds - 1 - index) * STEP
        plan = eng.evaluate(
            hygiene.parse_snapshot(
                snap_with_connections(procs, connections, taken=taken)
            )
        )
    return plan


def test_network_veto_defers_an_idle_orphan_with_a_live_remote_socket_then_expires():
    eng = engine()
    remote = [(400, "52.10.20.30:443")]
    plan = observe_connected(eng, [orphan_node()], 4, remote)
    vetoed = by_rule(plan, "orphan")
    assert [d.action for d in vetoed] == ["report"]
    assert vetoed[0].detail["network_veto"] is True
    assert vetoed[0].detail["deferrals"] == 1
    for extra in (1, 2):
        plan = eng.evaluate(
            hygiene.parse_snapshot(
                snap_with_connections([orphan_node()], remote, taken=NOW + extra * STEP)
            )
        )
        assert [d.action for d in by_rule(plan, "orphan")] == ["report"]
    # networkVetoMaxCycles=3 exhausted: a half-open keep-alive cannot shield a leak.
    plan = eng.evaluate(
        hygiene.parse_snapshot(
            snap_with_connections([orphan_node()], remote, taken=NOW + 3 * STEP)
        )
    )
    assert [d.action for d in by_rule(plan, "orphan")] == ["stop"]


def test_network_veto_is_decided_once_per_tree_per_run_across_rules():
    """Found by the invariant fuzzer's follow-up probe.

    A parentless, stale cursor-agent with the reaper unavailable is examined by
    BOTH the orphan rule and the session-age rule. Each used to charge its own
    deferral, so a 3-cycle veto lasted 2 runs - and worse, in the run where the
    counter hit the cap the session rule STOPPED a tree the orphan rule had just
    reported as vetoed, inside one plan. The veto is now one verdict per tree per
    run, shared by every rule.
    """
    eng = engine()
    stale = cursor_root(created=ago(30 * 3600))  # parentless (ppid 9_999 absent)
    conns = [(600, "52.1.2.3:443")]
    key = hygiene._key(hygiene.parse_snapshot(snap([stale])).by_pid[600])
    seen = []
    for r in range(7):
        plan = eng.evaluate(
            hygiene.parse_snapshot(
                snap_with_connections([stale], conns, taken=NOW + r * STEP)
            ),
            reaper_available=False,
        )
        deferrals = eng.state["observations"][key]["network_deferrals"]
        actions = {(d.rule, d.action) for d in plan.decisions}
        seen.append((deferrals, actions))
        # never a stop and a veto report for the same tree in one plan
        assert not (
            any(a == "stop" for _, a in actions)
            and any(d.detail.get("network_veto") for d in plan.decisions)
        )
    deferral_track = [d for d, _ in seen]
    # idle is confirmed at round 3; then exactly one deferral per run for 3 runs
    assert deferral_track == [0, 0, 0, 1, 2, 3, 3]
    # the orphan rule runs first and claims the tree; exactly one stop, by one rule
    stops_at_6 = [rule for rule, action in seen[6][1] if action == "stop"]
    assert stops_at_6 == ["orphan"]
    assert all(a == "report" for _, a in seen[3][1] | seen[4][1] | seen[5][1])


def test_network_deferrals_reset_when_the_tree_shows_activity():
    eng = engine()
    remote = [(400, "52.1.2.3:443")]
    for r in range(5):  # 3 rounds to confirm idle, then 2 vetoes
        eng.evaluate(
            hygiene.parse_snapshot(
                snap_with_connections([orphan_node()], remote, taken=NOW + r * STEP)
            )
        )
    key = hygiene._key(hygiene.parse_snapshot(snap([orphan_node()])).by_pid[400])
    assert eng.state["observations"][key]["network_deferrals"] == 2
    # a burst of CPU: the tree is not idle, and it earns a fresh veto window
    busy = orphan_node(cpu=50.0)
    eng.evaluate(
        hygiene.parse_snapshot(
            snap_with_connections([busy], remote, taken=NOW + 5 * STEP)
        )
    )
    assert eng.state["observations"][key]["network_deferrals"] == 0
    for r in range(
        6, 9
    ):  # idle again: streak 1, 2, 3 - the third round is the first veto
        plan = eng.evaluate(
            hygiene.parse_snapshot(
                snap_with_connections([busy], remote, taken=NOW + r * STEP)
            )
        )
    assert eng.state["observations"][key]["network_deferrals"] == 1
    assert [d.action for d in by_rule(plan, "orphan")] == ["report"]


@pytest.mark.parametrize(
    "remote,loopback",
    [
        ("127.0.0.1:8765", True),
        ("127.9.9.9:1", True),
        ("[::1]:8812", True),
        ("::1:8812", True),  # the launcher's unbracketed v6 form
        ("::1", True),
        ("localhost:80", True),
        ("0.0.0.0:0", True),
        ("[fe80::1]:443", False),
        ("fe80::1:443", False),  # unbracketed v6 with port: NOT loopback
        ("2001:db8::1", False),
        ("52.1.2.3:443", False),
        ("10.0.0.7:11434", False),  # a LAN model server IS real work
    ],
)
def test_is_loopback_handles_v4_v6_bracketed_and_unbracketed(remote, loopback):
    # Get-NetTCPConnection hands the launcher a bare RemoteAddress; formatting it
    # as `addr:port` produces `::1:8812` for v6 loopback. That used to read as
    # a remote endpoint, so an IPv6-only local MCP client defeated the filter.
    assert hygiene._is_loopback(remote) is loopback


def test_network_veto_ignores_loopback_and_can_be_disabled():
    plan = observe_connected(
        engine(), [orphan_node()], 4, [(400, "127.0.0.1:8765"), (400, "[::1]:8812")]
    )
    assert [d.action for d in by_rule(plan, "orphan")] == ["stop"]
    eng = engine(policy(**{"idle.networkVeto": False}))
    plan = observe_connected(eng, [orphan_node()], 4, [(400, "52.10.20.30:443")])
    assert [d.action for d in by_rule(plan, "orphan")] == ["stop"]


def test_network_veto_applies_to_session_age_stops_too():
    eng = engine()
    procs = [terminal(), cursor_root()]
    plan = observe_connected(eng, procs, 4, [(600, "20.30.40.50:443")])
    decisions = by_rule(plan, "session-age")
    assert [d.action for d in decisions] == ["report"]
    assert decisions[0].detail["network_veto"] is True


def test_snapshot_connections_and_wsl_gate_fields_validate():
    payload = snap([proc(10, 1)])
    payload["connections"] = [
        {"pid": 10, "remote": "1.2.3.4:443"},
        {"pid": 10, "remote": "::1"},
    ]
    payload["wsl"] = {
        "available": True,
        "running_distros": ["Ubuntu"],
        "docker_desktop_running": True,
        "client_count": 2,
    }
    snapshot = hygiene.parse_snapshot(payload)
    assert snapshot.networked == {10}
    assert snapshot.docker_desktop_running is True
    assert snapshot.wsl_client_count == 2
    bad = snap([proc(10, 1)])
    bad["connections"] = [{"pid": 10, "remote": 5}]
    with pytest.raises(hygiene.SnapshotError, match="remote"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["wsl"] = {
        "available": True,
        "running_distros": [],
        "docker_desktop_running": "yes",
    }
    with pytest.raises(hygiene.SnapshotError, match="docker_desktop_running"):
        hygiene.parse_snapshot(bad)
    bad = snap([proc(10, 1)])
    bad["wsl"] = {"available": True, "running_distros": [], "client_count": -1}
    with pytest.raises(hygiene.SnapshotError, match="client_count"):
        hygiene.parse_snapshot(bad)
    assert hygiene._is_loopback("localhost:80") is True
    assert hygiene._is_loopback("fe80::1") is False


def wsl_engine():
    return engine(policy(**{"wsl.idleShutdown.observations": 3}))


def wsl_snapshot(taken, **wsl_fields):
    payload = snap([vmmem()], taken=taken, free=3 * GIB, wsl_running=("Ubuntu",))
    payload["wsl"].update(wsl_fields)
    return hygiene.parse_snapshot(payload)


def test_wsl_idle_shutdown_is_blocked_while_docker_desktop_or_a_client_is_alive():
    eng = wsl_engine()
    for index in range(4):
        plan = eng.evaluate(
            wsl_snapshot(NOW + index * STEP, docker_desktop_running=True)
        )
    blocked = by_rule(plan, "wsl-idle")
    assert [d.action for d in blocked] == ["report"]
    assert blocked[0].detail["blocked_by"] == "docker-desktop"
    assert plan.wsl_shutdown is False
    eng = wsl_engine()
    for index in range(4):
        plan = eng.evaluate(wsl_snapshot(NOW + index * STEP, client_count=2))
    assert by_rule(plan, "wsl-idle")[0].detail["blocked_by"] == "wsl.exe clients=2"


def test_wsl_docker_distros_are_excluded_and_the_action_is_per_distro_terminate():
    eng = wsl_engine()
    plan = observe(
        eng,
        [vmmem()],
        4,
        wsl_running=("docker-desktop", "docker-desktop-data"),
        free=3 * GIB,
    )
    assert by_rule(plan, "wsl-idle") == []
    eng = wsl_engine()
    plan = observe(
        eng, [vmmem()], 4, wsl_running=("docker-desktop", "Ubuntu"), free=3 * GIB
    )
    shutdown = by_rule(plan, "wsl-idle")[0]
    assert shutdown.action == "wsl-shutdown"
    assert shutdown.detail["distros"] == ["Ubuntu"]
    assert shutdown.detail["action"] == "terminate"


def test_apply_plan_passes_distros_and_action_to_the_actuator(tmp_path):
    plan = mixed_plan()
    actuator = FakeActuator()
    hygiene.apply_plan(
        plan, actuator, hygiene.Ledger(tmp_path / "l.jsonl"), apply=True, run_id="r"
    )
    assert actuator.wsl_args == (["Ubuntu"], "terminate")


def test_apply_plan_stop_budget_defers_the_rest_and_ledgers_it(tmp_path):
    plan = mixed_plan(free=8 * GIB)  # retired 300 + orphan 400 executable at normal
    actuator = FakeActuator()
    pol = hygiene.validate_policy(policy(**{"escalation.maxStopsPerRun": 1}))
    ledger = hygiene.Ledger(tmp_path / "l.jsonl")
    summary = hygiene.apply_plan(
        plan, actuator, ledger, apply=True, run_id="r", policy=pol, state={}
    )
    killed = {pid for pids, _ in actuator.stopped for pid in pids}
    assert killed == {300}  # retired outranks orphan; the orphan waits for the next run
    assert summary["stopped"] == 1
    assert summary["budget_deferred"] == 1
    rows = ledger_rows(tmp_path / "l.jsonl")
    assert [r["pid"] for r in rows if r["result"] == "deferred-budget"] == [400]


def test_apply_plan_crash_loop_breaker_stops_killing_a_respawning_component(tmp_path):
    pol = hygiene.validate_policy(policy())
    state: dict = {}
    for run in range(3):
        plan = observe(engine(), grok_with_bridge(), 1, end=NOW + run * STEP)
        actuator = FakeActuator()
        ledger = hygiene.Ledger(tmp_path / f"l{run}.jsonl")
        summary = hygiene.apply_plan(
            plan,
            actuator,
            ledger,
            apply=True,
            run_id=f"r{run}",
            policy=pol,
            state=state,
        )
        rows = ledger_rows(tmp_path / f"l{run}.jsonl")
        if run < 2:
            assert actuator.stopped == [([300], 0)]
            assert summary["crash_loop"] == 0
        else:
            # Third sighting inside 24 h: the spawner is the bug; report, do not kill.
            assert actuator.stopped == []
            assert summary["crash_loop"] == 1
            assert [r["result"] for r in rows if r["rule"] == "retired"] == [
                "crash-loop"
            ]
    assert len(next(iter(state["kills"].values()))) == 2


def test_apply_plan_prunes_kill_history_and_reported_keys_so_state_stays_bounded(
    tmp_path,
):
    """Both dicts lived in state forever: every command line ever stopped, and every
    (rule, pid, created) ever reported. On a box that churns PIDs that is a leak in
    the tool whose job is leaks. Entries older than their window are dropped."""
    pol = hygiene.validate_policy(
        policy(
            **{
                "escalation.crashLoopWindowSeconds": 1000,
                "ledger.reportKeepaliveSeconds": 1000,
            }
        )
    )
    state: dict = {
        "kills": {"stale-sha": [NOW - 5000], "fresh-sha": [NOW - 100]},
        "reported": {"rss-soft|1|1": NOW - 5000, "rss-soft|2|2": NOW - 100},
    }
    plan = observe(engine(), grok_with_bridge(), 1)
    hygiene.apply_plan(
        plan,
        FakeActuator(),
        hygiene.Ledger(tmp_path / "l.jsonl"),
        apply=True,
        run_id="r",
        policy=pol,
        state=state,
    )
    assert "stale-sha" not in state["kills"]
    assert "fresh-sha" in state["kills"]
    assert "rss-soft|1|1" not in state["reported"]
    assert "rss-soft|2|2" in state["reported"]


def test_summary_and_digest_name_only_rules_that_actually_stopped(tmp_path):
    """With a stop budget of 1, the orphan is deferred; the digest must not claim
    it was stopped just because its decision was executable at this tier."""
    plan = mixed_plan(free=8 * GIB)  # retired 300 and orphan 400 both executable
    pol = hygiene.validate_policy(policy(**{"escalation.maxStopsPerRun": 1}))
    summary = hygiene.apply_plan(
        plan,
        FakeActuator(),
        hygiene.Ledger(tmp_path / "l.jsonl"),
        apply=True,
        run_id="r",
        policy=pol,
        state={},
    )
    assert summary["rules"] == ["retired"]
    line = hygiene.digest_line(plan, summary, {}, apply=True, cooldown=100, stamp="s")
    assert "[retired]" in line
    assert "orphan" not in line


def test_apply_plan_crash_loop_window_expires(tmp_path):
    pol = hygiene.validate_policy(policy(**{"escalation.crashLoopWindowSeconds": 100}))
    state: dict = {}
    for run in range(3):
        plan = observe(engine(), grok_with_bridge(), 1, end=NOW + run * 1000)
        actuator = FakeActuator()
        hygiene.apply_plan(
            plan,
            actuator,
            hygiene.Ledger(tmp_path / f"l{run}.jsonl"),
            apply=True,
            run_id=f"r{run}",
            policy=pol,
            state=state,
        )
        assert actuator.stopped == [([300], 0)]


def test_apply_plan_dedupes_unchanged_report_rows_with_an_hourly_keepalive(tmp_path):
    pol = hygiene.validate_policy(policy())
    state: dict = {}
    eng = engine()
    ledger = hygiene.Ledger(tmp_path / "l.jsonl")
    procs = [terminal(), cursor_root(created=ago(1200), private=2 * GIB, cpu=1.0)]
    for run in range(4):
        # keep the session ACTIVE so rss-soft stays a report every run
        procs[1] = cursor_root(created=ago(1200), private=2 * GIB, cpu=1.0 + run)
        plan = eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=NOW + run * STEP)))
        hygiene.apply_plan(
            plan,
            FakeActuator(),
            ledger,
            apply=False,
            run_id=f"r{run}",
            policy=pol,
            state=state,
        )
    rows = [r for r in ledger_rows(tmp_path / "l.jsonl") if r["rule"] == "rss-soft"]
    assert len(rows) == 1  # first sight only within the keepalive window
    plan = eng.evaluate(hygiene.parse_snapshot(snap(procs, taken=NOW + 4000)))
    hygiene.apply_plan(
        plan,
        FakeActuator(),
        ledger,
        apply=False,
        run_id="late",
        policy=pol,
        state=state,
    )
    rows = [r for r in ledger_rows(tmp_path / "l.jsonl") if r["rule"] == "rss-soft"]
    assert len(rows) == 2  # keepalive after an hour


def test_ledger_rotates_through_n_generations(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = hygiene.Ledger(path, max_bytes=150, generations=3)
    for index in range(20):
        ledger.append({"schema": hygiene.SCHEMA_LEDGER, "n": index, "pad": "x" * 100})
    assert path.exists()
    assert (tmp_path / "ledger.jsonl.1").exists()
    assert (tmp_path / "ledger.jsonl.3").exists()
    assert not (tmp_path / "ledger.jsonl.4").exists()


def test_cli_run_writes_heartbeat_and_digest_only_on_new_kill_kinds(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        hygiene, "build_actuator", lambda policy_obj, **kwargs: FakeActuator()
    )
    files = cli_files(tmp_path, grok_with_bridge())
    digest = tmp_path / "BACKGROUND-DIGEST.md"
    heartbeat = tmp_path / "heartbeat.json"
    assert (
        run_cli(
            files, "--apply", "--digest", str(digest), "--heartbeat", str(heartbeat)
        )
        == 0
    )
    beat = json.loads(heartbeat.read_text(encoding="utf-8"))
    assert beat["schema"] == "process-hygiene-heartbeat-v1"
    assert beat["apply"] is True and beat["tier"] == "normal"
    lines = digest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "[process-hygiene] stopped 1 tree(s) [retired]" in lines[0]
    assert "| PROPOSE:" in lines[0]
    # Same kind again inside the cooldown: no second line (estate anti-spam).
    write(files["snapshot"], snap(grok_with_bridge(), taken=NOW + STEP))
    assert (
        run_cli(
            files, "--apply", "--digest", str(digest), "--heartbeat", str(heartbeat)
        )
        == 0
    )
    assert len(digest.read_text(encoding="utf-8").splitlines()) == 1


def test_digest_line_satisfies_the_estate_background_digest_contract():
    """The digest line is useless if the SessionStart reader does not recognise it.

    hooks/background-digest/reader.py surfaces only lines matching its entry regex
    and ranks UPPERCASE urgency tokens first, so both are asserted against the
    REAL reader rather than a copy of its patterns. Skipped (not failed) if the
    hook tree is absent, so this can never break the gate on a partial checkout.
    """
    reader_path = (
        pathlib.Path(__file__).resolve().parents[3]
        / "hooks/background-digest/reader.py"
    )
    if not reader_path.exists():  # pragma: no cover - full checkout in CI
        pytest.skip("background-digest hook not present in this checkout")
    spec = importlib.util.spec_from_file_location("bg_digest_reader", reader_path)
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)

    plan = observe(engine(), grok_with_bridge(), 1)
    stamp = "2026-09-02 04:50:00"
    ok = hygiene.digest_line(
        plan,
        {
            "stopped": 1,
            "failed": 0,
            "exit_code": 0,
            "run_id": "r1",
            "rules": ["retired"],
        },
        {},
        apply=True,
        cooldown=100,
        stamp=stamp,
    )
    failing = hygiene.digest_line(
        plan,
        {
            "stopped": 0,
            "failed": 1,
            "exit_code": 2,
            "run_id": "r2",
            "rules": ["retired"],
        },
        {},
        apply=True,
        cooldown=100,
        stamp=stamp,
    )
    assert reader._is_entry(ok), "reader would not surface the digest line at all"
    assert reader._is_entry(failing)
    # A failure must outrank routine chatter; a mere critical TIER reading must not
    # (that is why the tier is written lowercase).
    assert reader._priority(failing) == 0
    assert reader._priority(ok) == 1
    message, surfaced = reader.build_message(["# header", "", ok, failing])
    assert surfaced == [ok, failing]
    assert message.splitlines()[1] == failing  # urgent card first
    assert "PROPOSE:" in message


def test_digest_line_rules():
    state: dict = {}
    plan = observe(engine(), grok_with_bridge(), 1)
    ok = {
        "stopped": 1,
        "failed": 0,
        "exit_code": 0,
        "run_id": "r",
        "rules": ["retired"],
    }
    assert (
        hygiene.digest_line(plan, ok, state, apply=False, cooldown=100, stamp="s")
        is None
    )
    line = hygiene.digest_line(plan, ok, state, apply=True, cooldown=100, stamp="s")
    assert line.startswith("[s] [process-hygiene] stopped 1 tree(s) [retired]")
    assert (
        hygiene.digest_line(plan, ok, state, apply=True, cooldown=100, stamp="s")
        is None
    )
    failing = {
        "stopped": 0,
        "failed": 1,
        "exit_code": 2,
        "run_id": "r",
        "rules": ["retired"],
    }
    line = hygiene.digest_line(
        plan, failing, state, apply=True, cooldown=100, stamp="s"
    )
    assert line.startswith("[s] [process-hygiene] ACTION_REQUIRED:")
    # Cooldown elapsed: the signature resets and the same kind is reported again.
    later = observe(engine(), grok_with_bridge(), 1, end=NOW + 1000)
    assert (
        hygiene.digest_line(later, ok, state, apply=True, cooldown=100, stamp="s")
        is not None
    )
    calm = observe(engine(), [proc(10, 1)], 1, end=NOW + 2000)
    nothing = {"stopped": 0, "failed": 0, "exit_code": 0, "run_id": "r", "rules": []}
    assert (
        hygiene.digest_line(calm, nothing, {}, apply=True, cooldown=100, stamp="s")
        is None
    )
    hot = observe(engine(), [proc(10, 1)], 1, end=NOW + 3000, free=1 * GIB)
    line = hygiene.digest_line(hot, nothing, {}, apply=True, cooldown=100, stamp="s")
    assert "tier=critical" in line


# ------------------------------------------------------- coverage corners


def mcp_disabled_engine_without_registry() -> hygiene.Engine:
    return hygiene.Engine(
        hygiene.validate_policy(policy(**{"mcp.enabled": False})),
        {},
        fleet=hygiene.load_fleet(hygiene.DEFAULT_FLEET_PATH),
        registry=None,
    )


def test_mcp_disabled_without_a_registry_still_reaps_generic_orphans():
    eng = mcp_disabled_engine_without_registry()
    plan = observe(eng, [orphan_node()], 4)
    orphan = by_rule(plan, "orphan")
    assert len(orphan) == 1
    assert "mcp_server" not in orphan[0].detail
    assert "fleet" not in plan.metrics


def test_cursor_agent_without_an_orphan_handler_is_not_delegated():
    pol = policy()
    pol["runtimes"]["cursor-agent"]["orphanHandler"] = None
    plan = observe(engine(pol), [cursor_root()], 4, reaper_available=True)
    assert plan.delegate_reaper is False
    assert [decision.root.pid for decision in by_rule(plan, "orphan")] == [600]


def test_retired_match_that_is_protected_is_left_alone():
    procs = grok_with_bridge()
    plan = observe(engine(), procs, 1, supervisor_pids=(300,))
    assert by_rule(plan, "retired") == []
    assert kill_pids(plan) == set()


def test_retired_nested_match_is_claimed_only_once():
    bridge_cmd = (
        "node C:\\Users\\Prekzursil\\AppData\\Roaming\\npm\\node_modules\\"
        "@raysonmeng\\agentbridge\\dist\\bridge-server.js"
    )
    procs = [
        proc(200, 1, name="grok.exe", exe=GROK_EXE, cmd="grok", created=ago(2000)),
        proc(300, 200, cmd=bridge_cmd, created=ago(1000)),
        proc(301, 300, cmd=bridge_cmd + " --worker", created=ago(900)),
    ]
    plan = observe(engine(), procs, 1)
    retired = by_rule(plan, "retired")
    assert len(retired) == 1
    assert [member.pid for member in retired[0].tree] == [301, 300]


def test_kill_tree_excludes_a_name_protected_child():
    procs = [
        orphan_node(),
        proc(
            401,
            400,
            name="cursor.exe",
            exe=CURSOR_IDE_EXE,
            cmd="Cursor --renderer",
            created=ago(10 * 3600 - 100),
        ),
    ]
    plan = observe(engine(), procs, 4)
    orphan = by_rule(plan, "orphan")[0]
    assert [member.pid for member in orphan.tree] == [400]
    assert orphan.detail["protected_members"] == [401]


def test_descendants_terminates_on_a_pid_cycle():
    # A PID-reuse artifact can make two rows point at each other; the walk must
    # not recurse forever and must still reap the parentless root.
    procs = [
        proc(410, 411, cmd="node a.js", created=ago(10 * 3600)),
        proc(411, 410, cmd="node b.js", created=ago(9 * 3600)),
    ]
    plan = observe(engine(), procs, 4)
    orphan = by_rule(plan, "orphan")
    assert {member.pid for decision in orphan for member in decision.tree} <= {410, 411}


def test_session_age_on_a_protected_root_emits_no_stop():
    procs = [terminal(), cursor_root()]
    plan = observe(engine(), procs, 4, supervisor_pids=(600,))
    assert by_rule(plan, "session-age") == []
    assert 600 not in kill_pids(plan)


def test_mcp_single_singleton_instance_is_not_flagged():
    procs = [basic_memory_proc(50, 9_999, created=ago(90_000))]
    plan = observe(engine(), procs, 4, listeners={8765: 50})
    assert by_rule(plan, "mcp-singleton-duplicate") == []


def test_mcp_singleton_duplicate_skips_a_protected_member(tmp_path):
    procs = [
        basic_memory_proc(50, 9_999, created=ago(90_000)),
        basic_memory_proc(51, 9_998, created=ago(11_200)),
    ]
    plan = observe(engine(), procs, 4, listeners={8765: 50}, supervisor_pids=(51,))
    assert by_rule(plan, "mcp-singleton-duplicate") == []


def test_port_helpers_cover_their_branches():
    snapshot = hygiene.parse_snapshot(
        snap([proc(10, 1), proc(11, 1)], listeners={8000: 11, 8765: 10})
    )
    assert hygiene._port_owned_by(10, snapshot) == 8765
    assert hygiene._port_owned_by(999, snapshot) is None
    assert hygiene._port_of({}) is None
    assert hygiene._port_of({"url": 123}) is None
    assert hygiene._port_of({"url": "http://127.0.0.1/mcp"}) is None
    assert hygiene._port_of({"url": "http://127.0.0.1:8765/mcp"}) == 8765


def test_apply_plan_records_a_failed_wsl_shutdown(tmp_path):
    class WslFail(FakeActuator):
        def wsl_shutdown(self, *, distros=(), action="terminate"):
            self.wsl_calls += 1
            return hygiene.StopResult(
                pid=0, created_unix=0, outcome="failed", detail=""
            )

    plan = mixed_plan()
    ledger = hygiene.Ledger(tmp_path / "ledger.jsonl")
    summary = hygiene.apply_plan(plan, WslFail(), ledger, apply=True, run_id="wsl")
    assert summary["exit_code"] == 2
    assert [
        row["result"]
        for row in ledger_rows(tmp_path / "ledger.jsonl")
        if row["rule"] == "wsl-idle"
    ] == ["failed"]


def test_cli_run_with_mcp_disabled_needs_no_registry(tmp_path, capsys):
    files = cli_files(tmp_path, [orphan_node()])
    write(files["policy"], policy(**{"mcp.enabled": False}))
    files["registry"].unlink()
    assert run_cli(files) == 0
    assert "SUCCESS:process-hygiene" in capsys.readouterr().out


def test_cli_reaper_available_yes_forces_delegation(tmp_path, capsys):
    files = cli_files(tmp_path, [cursor_root()])
    assert (
        hygiene.main(
            [
                "run",
                "--snapshot",
                str(files["snapshot"]),
                "--policy",
                str(files["policy"]),
                "--registry",
                str(files["registry"]),
                "--state",
                str(files["state"]),
                "--ledger",
                str(files["ledger"]),
                "--reaper-available",
                "yes",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "delegate_reaper=true" in out
