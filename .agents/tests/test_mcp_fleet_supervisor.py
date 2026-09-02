from __future__ import annotations

import importlib.util
import pathlib
import sys


SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "mcp_fleet_supervisor", SCRIPTS / "mcp_fleet_supervisor.py"
)
assert SPEC is not None and SPEC.loader is not None
fleet = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fleet
SPEC.loader.exec_module(fleet)


def config(max_private: int = 512 * 1024 * 1024) -> dict:
    return {
        "mcp": {
            "policy": {
                "required": False,
                "startupTimeoutMs": 30_000,
                "toolTimeoutMs": 30_000,
                "healthProbe": {"kind": "mcp-tools-list", "timeoutMs": 30_000},
                "toolAllowlist": ["*"],
                "approvalMode": "native",
                "maxPrivateBytes": max_private,
            },
            "supervision": {
                "totalIdlePrivateBytes": 6 * 1024 * 1024 * 1024,
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
                }
            },
        }
    }


def process(pid: int, parent: int, command: str, private: int) -> fleet.ProcessRecord:
    return fleet.ProcessRecord(pid, parent, "C:/node.exe", command, private)


def test_duplicate_roots_and_resource_limit_are_degraded() -> None:
    processes = [
        fleet.ProcessRecord(2, 1, "C:/claude.exe", "claude", 1),
        process(10, 2, "node C:/npm/@example/mcp-server/index.js", 600_000_000),
        process(11, 2, "node C:/npm/@example/mcp-server/index.js", 350_000_000),
    ]

    report = fleet.evaluate_fleet(config(), processes, set())

    assert report["status"] == "degraded"
    assert report["duplicateServers"] == ["example"]
    assert report["overBudgetServers"] == ["example"]
    assert report["servers"]["example"]["terminationEligible"] is False


def test_parent_child_tree_is_one_singleton_root() -> None:
    processes = [
        fleet.ProcessRecord(2, 1, "C:/claude.exe", "claude", 1),
        process(10, 2, "npx -y @example/mcp-server", 10_000_000),
        process(11, 10, "node C:/npm/@example/mcp-server/index.js", 20_000_000),
    ]

    report = fleet.evaluate_fleet(config(), processes, set())

    assert report["status"] == "healthy"
    assert report["servers"]["example"]["rootCount"] == 1
    assert report["servers"]["example"]["privateBytes"] == 30_000_000


def test_three_failures_in_ten_minutes_quarantine_only_that_session() -> None:
    state: dict = {}
    for moment in (100.0, 200.0, 300.0):
        state, quarantined = fleet.update_quarantine_state(
            state,
            session_id="session-a",
            failures=["example"],
            now=moment,
            threshold=3,
            window_seconds=600,
        )
    assert quarantined == {"example"}

    fresh, quarantined = fleet.update_quarantine_state(
        state,
        session_id="session-b",
        failures=[],
        now=301.0,
        threshold=3,
        window_seconds=600,
    )
    assert quarantined == set()
    assert fresh["sessionId"] == "session-b"


def test_fleet_total_above_the_idle_ceiling_is_degraded() -> None:
    """The 6 GiB ceiling is a FLEET budget, not a per-session one.

    Measured from the committed live capture
    ``reconcile-flags/import-2026-08-28/live-only-flagged/reports/mcp-fleet-status.json``:
    ``totalPrivateBytes`` 13.6 GiB against a 6 GiB ``totalIdlePrivateBytes``, with
    ``maxSessionPrivateBytes`` only 2.4 GiB — and ``status: healthy``. Seven
    sessions each individually under budget summed to more than double the fleet
    ceiling and nothing reported it, which is exactly the per-session stdio
    multiplication the estate measured as its commit-exhaustion driver.
    """
    per_session = 500 * 1024 * 1024  # under the 512 MiB per-instance cap
    sessions = 16  # 16 x 500 MiB = 8000 MiB, over the 6 GiB fleet ceiling
    processes: list[fleet.ProcessRecord] = []
    for index in range(sessions):
        client = 100 + index * 10
        processes.append(fleet.ProcessRecord(client, 1, "C:/claude.exe", "claude", 1))
        processes.append(
            process(client + 1, client, "npx -y @example/mcp-server", per_session)
        )

    report = fleet.evaluate_fleet(config(), processes, set())

    assert report["totalPrivateBytes"] == sessions * per_session
    assert report["totalPrivateBytes"] > 6 * 1024**3
    assert report["maxSessionPrivateBytes"] == per_session
    assert report["sessionCount"] == sessions
    assert report["sessionsOverBudget"] == 0, "no single session breaches the ceiling"
    assert report["overBudgetServers"] == [], "no single instance breaches its own cap"
    assert report["duplicateServers"] == [], "one root per session is not duplication"
    assert report["totalOverBudget"] is True
    assert report["status"] == "degraded"


def test_fleet_total_under_the_idle_ceiling_stays_healthy() -> None:
    processes = [
        fleet.ProcessRecord(100, 1, "C:/claude.exe", "claude", 1),
        process(101, 100, "npx -y @example/mcp-server", 500 * 1024 * 1024),
    ]

    report = fleet.evaluate_fleet(config(), processes, set())

    assert report["totalPrivateBytes"] == 500 * 1024 * 1024
    assert report["totalOverBudget"] is False
    assert report["status"] == "healthy"


def test_secret_bearing_argument_is_counted_but_never_returned() -> None:
    secret = "github_pat_" + "A" * 30
    processes = [process(10, 1, f"node @example/mcp-server --token={secret}", 1)]

    report = fleet.evaluate_fleet(config(), processes, set())

    assert report["secretArgumentProcessCount"] == 1
    assert secret not in str(report)
