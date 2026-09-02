"""Tests for the shared-MCP-host supervisor decision logic.

Every rule here encodes a failure this estate has already paid for:

* ``test_wedge_*``      - the agent-mail supervisor killed near-ready children
  because it recycled on a single signal (health-poll failure). AND-gate it.
* ``test_orphan_*``     - a machine-wide reap once killed sibling sessions' MCP
  children. Reaping must be orphan-only and ownership-scoped.
* ``test_validate_*``   - 8765 (basic-memory) and 8812 (agent-mail) are LIVE
  ports; binding either would take down a working service.
"""

from __future__ import annotations

import json

import pytest

from fleet import (
    RESERVED_PORTS,
    HostSample,
    ServerSpec,
    find_orphans,
    main,
    parse_fleet,
    validate_fleet,
    wedge_verdict,
)

# --------------------------------------------------------------------- parse


def _fleet(**over):
    base = {
        "servers": [
            {
                "name": "search-hub",
                "port": 8901,
                "command": ["python", "hub.py"],
            }
        ]
    }
    base.update(over)
    return base


def test_parse_minimal_fleet_yields_one_spec():
    specs, errors = parse_fleet(_fleet())
    assert errors == []
    assert len(specs) == 1
    assert specs[0] == ServerSpec(
        name="search-hub",
        port=8901,
        command=("python", "hub.py"),
        health_path="/healthz",
        bind_host="127.0.0.1",
        enabled=True,
        startup_grace_sec=240,
    )


def test_parse_rejects_non_mapping():
    specs, errors = parse_fleet([])
    assert specs == []
    assert any("mapping" in e for e in errors)


def test_parse_reports_missing_name_and_port():
    specs, errors = parse_fleet({"servers": [{"command": ["x"]}]})
    assert specs == []
    assert any("name" in e for e in errors)


def test_parse_rejects_empty_command():
    _, errors = parse_fleet({"servers": [{"name": "a", "port": 8901, "command": []}]})
    assert any("command" in e for e in errors)


def test_parse_carries_disabled_flag():
    specs, errors = parse_fleet(
        {"servers": [{"name": "a", "port": 8901, "command": ["x"], "enabled": False}]}
    )
    assert errors == []
    assert specs[0].enabled is False


def test_parse_rejects_out_of_range_port():
    _, errors = parse_fleet(
        {"servers": [{"name": "a", "port": 99999, "command": ["x"]}]}
    )
    assert any("port" in e for e in errors)


# ------------------------------------------------------------------ validate


def test_validate_clean_fleet_has_no_errors():
    specs, _ = parse_fleet(_fleet())
    assert validate_fleet(specs) == []


def test_validate_rejects_duplicate_ports():
    specs, _ = parse_fleet(
        {
            "servers": [
                {"name": "a", "port": 8901, "command": ["x"]},
                {"name": "b", "port": 8901, "command": ["y"]},
            ]
        }
    )
    errors = validate_fleet(specs)
    assert any("8901" in e for e in errors)


def test_validate_rejects_duplicate_names():
    specs, _ = parse_fleet(
        {
            "servers": [
                {"name": "a", "port": 8901, "command": ["x"]},
                {"name": "a", "port": 8902, "command": ["y"]},
            ]
        }
    )
    assert any("duplicate server name" in e for e in validate_fleet(specs))


@pytest.mark.parametrize("port", sorted(RESERVED_PORTS))
def test_validate_rejects_live_reserved_ports(port):
    """8765 = basic-memory, 8812 = agent-mail. Both are LIVE services."""
    specs, _ = parse_fleet({"servers": [{"name": "a", "port": port, "command": ["x"]}]})
    errors = validate_fleet(specs)
    assert any(RESERVED_PORTS[port] in e for e in errors)


def test_validate_rejects_non_loopback_bind():
    specs, _ = parse_fleet(
        {
            "servers": [
                {"name": "a", "port": 8901, "command": ["x"], "bind_host": "0.0.0.0"}
            ]
        }
    )
    assert any("loopback" in e for e in validate_fleet(specs))


def test_validate_ignores_disabled_servers_for_port_clash():
    specs, _ = parse_fleet(
        {
            "servers": [
                {"name": "a", "port": 8901, "command": ["x"]},
                {"name": "b", "port": 8901, "command": ["y"], "enabled": False},
            ]
        }
    )
    assert validate_fleet(specs) == []


# --------------------------------------------------------------- wedge logic


def _sample(**over):
    base = {
        "cpu_seconds": 10.0,
        "requests_served": 5,
        "healthy": True,
        "uptime_sec": 600.0,
        "fail_streak": 0,
    }
    base.update(over)
    return HostSample(**base)


def test_wedge_healthy_when_health_probe_passes():
    assert wedge_verdict(_sample(), _sample(cpu_seconds=10.1)) == "HEALTHY"


def test_wedge_starting_inside_grace_never_recycles():
    """The measured agent-mail bug: a 90s grace killed children needing ~150s."""
    prev = _sample(healthy=False, uptime_sec=5.0, fail_streak=9)
    cur = _sample(healthy=False, uptime_sec=30.0, fail_streak=9)
    assert wedge_verdict(prev, cur, startup_grace_sec=240) == "STARTING"


def test_wedge_degraded_below_fail_streak_threshold():
    prev = _sample(healthy=False, fail_streak=1)
    cur = _sample(healthy=False, fail_streak=1, cpu_seconds=10.0)
    assert wedge_verdict(prev, cur, max_fail_streak=3) == "DEGRADED"


def test_wedge_busy_when_cpu_still_advancing():
    """Unhealthy + streak exceeded, but CPU is climbing: it is WORKING, not wedged.

    Single-signal verification: a failed health poll alone must never authorise
    a kill. This is the AND-gate that the agent-mail supervisor lacks.
    """
    prev = _sample(healthy=False, fail_streak=5, cpu_seconds=10.0)
    cur = _sample(healthy=False, fail_streak=5, cpu_seconds=25.0)
    assert wedge_verdict(prev, cur, max_fail_streak=3) == "BUSY"


def test_wedge_busy_when_requests_still_advancing():
    prev = _sample(healthy=False, fail_streak=5, cpu_seconds=10.0, requests_served=5)
    cur = _sample(healthy=False, fail_streak=5, cpu_seconds=10.0, requests_served=9)
    assert wedge_verdict(prev, cur, max_fail_streak=3) == "BUSY"


def test_wedge_wedged_only_when_all_three_signals_agree():
    prev = _sample(healthy=False, fail_streak=5, cpu_seconds=10.0, requests_served=5)
    cur = _sample(healthy=False, fail_streak=5, cpu_seconds=10.0, requests_served=5)
    assert wedge_verdict(prev, cur, max_fail_streak=3) == "WEDGED"


def test_wedge_tolerates_tiny_cpu_jitter_as_flat():
    prev = _sample(healthy=False, fail_streak=5, cpu_seconds=10.0)
    cur = _sample(healthy=False, fail_streak=5, cpu_seconds=10.0001)
    assert wedge_verdict(prev, cur, max_fail_streak=3) == "WEDGED"


def test_wedge_no_previous_sample_is_never_wedged():
    """One reading is not a trend. Never recycle on a single observation."""
    assert wedge_verdict(None, _sample(healthy=False, fail_streak=9)) == "DEGRADED"


# -------------------------------------------------------------------- orphans


def _proc(pid, ppid, cl):
    return {"pid": pid, "ppid": ppid, "cmdline": cl}


HOST_SIG = "mcp_http_host.py"


def test_find_orphans_returns_child_whose_parent_is_gone():
    procs = [_proc(100, 999, "python mcp_http_host.py --port 8901")]
    assert find_orphans(
        procs, supervisor_pid=1, tracked_pids={7}, signature=HOST_SIG
    ) == [100]


def test_find_orphans_never_reaps_a_tracked_child():
    procs = [_proc(100, 999, "python mcp_http_host.py --port 8901")]
    assert (
        find_orphans(procs, supervisor_pid=1, tracked_pids={100}, signature=HOST_SIG)
        == []
    )


def test_find_orphans_never_reaps_a_live_siblings_child():
    """The measured regression: a machine-wide reap killed other sessions' MCPs.

    pid 100's parent (500) is ALIVE and is not this supervisor, so 100 belongs to
    somebody else. It must survive.
    """
    procs = [
        _proc(100, 500, "python mcp_http_host.py --port 8901"),
        _proc(500, 1, "claude.exe"),
    ]
    assert (
        find_orphans(procs, supervisor_pid=1, tracked_pids=set(), signature=HOST_SIG)
        == []
    )


def test_find_orphans_reaps_our_own_untracked_leftover():
    """Parent IS this supervisor but the pid is not tracked: a stale leftover."""
    procs = [_proc(100, 42, "python mcp_http_host.py --port 8901")]
    assert find_orphans(
        procs, supervisor_pid=42, tracked_pids=set(), signature=HOST_SIG
    ) == [100]


def test_find_orphans_ignores_non_matching_signature():
    procs = [_proc(100, 999, "python some_other_server.py")]
    assert (
        find_orphans(procs, supervisor_pid=1, tracked_pids=set(), signature=HOST_SIG)
        == []
    )


def test_find_orphans_requires_a_signature():
    """An empty signature would match every process on the box - refuse it."""
    procs = [_proc(100, 999, "python mcp_http_host.py")]
    with pytest.raises(ValueError):
        find_orphans(procs, supervisor_pid=1, tracked_pids=set(), signature="")


def test_find_orphans_is_case_insensitive_on_windows_paths():
    procs = [
        _proc(100, 999, r"C:\Python314\python.exe C:\x\MCP_HTTP_HOST.PY --port 8901")
    ]
    assert find_orphans(
        procs, supervisor_pid=1, tracked_pids=set(), signature=HOST_SIG
    ) == [100]


def test_find_orphans_skips_self():
    procs = [_proc(42, 999, "python mcp_http_host.py")]
    assert (
        find_orphans(procs, supervisor_pid=42, tracked_pids=set(), signature=HOST_SIG)
        == []
    )


def test_find_orphans_returns_sorted_unique_pids():
    procs = [
        _proc(300, 999, "python mcp_http_host.py --port 8903"),
        _proc(100, 999, "python mcp_http_host.py --port 8901"),
    ]
    assert find_orphans(
        procs, supervisor_pid=1, tracked_pids=set(), signature=HOST_SIG
    ) == [
        100,
        300,
    ]


# ------------------------------------------------- remaining parse branches


def test_parse_rejects_non_mapping_entry():
    _, errors = parse_fleet({"servers": ["not-a-mapping"]})
    assert any("must be a mapping" in e for e in errors)


def test_parse_rejects_servers_not_a_list():
    _, errors = parse_fleet({"servers": {"name": "a"}})
    assert any("must be a list" in e for e in errors)


def test_parse_rejects_blank_name():
    _, errors = parse_fleet({"servers": [{"name": "   ", "port": 8901}]})
    assert any("name" in e for e in errors)


def test_parse_rejects_boolean_port():
    """`True` is an int subclass in Python - it must not slip through as a port."""
    _, errors = parse_fleet(
        {"servers": [{"name": "a", "port": True, "command": ["x"]}]}
    )
    assert any("integer" in e for e in errors)


def test_parse_rejects_port_below_1024():
    _, errors = parse_fleet({"servers": [{"name": "a", "port": 80, "command": ["x"]}]})
    assert any("1024" in e for e in errors)


def test_parse_rejects_command_not_a_list():
    _, errors = parse_fleet({"servers": [{"name": "a", "port": 8901, "command": "x"}]})
    assert any("non-empty list" in e for e in errors)


def test_parse_rejects_non_string_command_entries():
    _, errors = parse_fleet(
        {"servers": [{"name": "a", "port": 8901, "command": ["ok", 7]}]}
    )
    assert any("must be strings" in e for e in errors)


def test_parse_honours_custom_grace_and_health_path():
    specs, errors = parse_fleet(
        {
            "servers": [
                {
                    "name": "a",
                    "port": 8901,
                    "command": ["x"],
                    "health_path": "/alive",
                    "startup_grace_sec": 30,
                }
            ]
        }
    )
    assert errors == []
    assert specs[0].health_path == "/alive"
    assert specs[0].startup_grace_sec == 30


# ------------------------------------------------------------------- the CLI


def _write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_cli_validate_accepts_a_clean_manifest(tmp_path, capsys):
    manifest = _write(tmp_path, "fleet.json", _fleet())
    assert main(["validate", "--manifest", manifest]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_cli_validate_rejects_a_reserved_port(tmp_path, capsys):
    manifest = _write(
        tmp_path,
        "fleet.json",
        {"servers": [{"name": "a", "port": 8812, "command": ["x"]}]},
    )
    assert main(["validate", "--manifest", manifest]) == 1
    assert "mcp_agent_mail" in capsys.readouterr().out


def test_cli_validate_rejects_a_malformed_manifest(tmp_path, capsys):
    manifest = _write(tmp_path, "fleet.json", {"servers": [{"name": "a"}]})
    assert main(["validate", "--manifest", manifest]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_plan_emits_health_urls_for_enabled_servers_only(tmp_path, capsys):
    manifest = _write(
        tmp_path,
        "fleet.json",
        {
            "servers": [
                {"name": "a", "port": 8901, "command": ["x"]},
                {"name": "b", "port": 8902, "command": ["y"], "enabled": False},
            ]
        },
    )
    assert main(["plan", "--manifest", manifest]) == 0
    plan = json.loads(capsys.readouterr().out)["plan"]
    assert [p["name"] for p in plan] == ["a"]
    assert plan[0]["health_url"] == "http://127.0.0.1:8901/healthz"


def test_cli_plan_refuses_an_invalid_manifest(tmp_path, capsys):
    manifest = _write(
        tmp_path,
        "fleet.json",
        {"servers": [{"name": "a", "port": 8765, "command": ["x"]}]},
    )
    assert main(["plan", "--manifest", manifest]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_verdict_reports_wedged_and_sets_recycle(tmp_path, capsys):
    flat = {
        "cpu_seconds": 10.0,
        "requests_served": 5,
        "healthy": False,
        "uptime_sec": 900.0,
        "fail_streak": 5,
    }
    state = _write(tmp_path, "state.json", {"previous": flat, "current": flat})
    assert main(["verdict", "--state", state]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "WEDGED"
    assert out["recycle"] is True


def test_cli_verdict_without_previous_sample_never_recycles(tmp_path, capsys):
    state = _write(
        tmp_path,
        "state.json",
        {
            "current": {
                "cpu_seconds": 1.0,
                "requests_served": 0,
                "healthy": False,
                "uptime_sec": 900.0,
                "fail_streak": 9,
            }
        },
    )
    assert main(["verdict", "--state", state]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "DEGRADED"
    assert out["recycle"] is False


def test_cli_orphans_lists_reapable_pids(tmp_path, capsys):
    payload = {
        "supervisor_pid": 42,
        "tracked_pids": [7],
        "signature": "mcp_http_host.py",
        "procs": [{"pid": 100, "ppid": 999, "cmdline": "python mcp_http_host.py"}],
    }
    assert main(["orphans", "--input", _write(tmp_path, "o.json", payload)]) == 0
    assert json.loads(capsys.readouterr().out)["orphans"] == [100]


def test_cli_orphans_refuses_an_empty_signature(tmp_path, capsys):
    payload = {"supervisor_pid": 42, "signature": "", "procs": []}
    assert main(["orphans", "--input", _write(tmp_path, "o.json", payload)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_reads_a_bom_prefixed_file(tmp_path, capsys):
    """Windows PowerShell 5.1 `Set-Content -Encoding utf8` emits a UTF-8 BOM.

    The supervisor is launched via `powershell.exe` (5.1, not pwsh 7), so every
    JSON hand-off it writes is BOM-prefixed. Plain utf-8 `json.load` raises
    `Unexpected UTF-8 BOM` on those files - measured, and it broke the reap step
    end-to-end before this was fixed.
    """
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(_fleet()).encode("utf-8"))
    assert main(["validate", "--manifest", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
