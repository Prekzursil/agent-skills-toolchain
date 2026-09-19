#!/usr/bin/env python3
"""AUD-0061 named probe 2: measured RAM / commit-charge cost of MCP process
multiplication on THIS Linux Cursor Cloud host.

Honest platform scope up front: the catalog's evidence_requirement asks for
"the system commit charge and pagefile usage" -- that is Windows terminology
(Committed_AS / PageFile on a Windows host). THIS probe runs on a Linux pod.
Linux has no PageFile/commit-charge concept identical to Windows; the
closest real, measured, kernel-reported analog is /proc/meminfo's
Committed_AS (the sum of all virtual memory the kernel has promised to back,
across every process) and CommitLimit (the point past which further
overcommit is refused absent swap). This probe reports THOSE real numbers
and does not invent a Windows-shaped metric this host cannot produce.

Real, measured steps (no simulation):
  1. Read /proc/meminfo host-wide (MemTotal, MemAvailable, Committed_AS,
     CommitLimit, SwapTotal) -- ACTUAL values on this host right now.
  2. Re-run the probe1 census logic to get the actual live process set,
     the exec-daemon's measured RSS/VSZ, and how many of the 3 configured
     MCP servers are ACTUALLY live right now (measured: currently 0).
  3. Spawn ONE real, local, network-free `node -e` idle child process and
     measure its ACTUAL RSS/VSZ after a settle delay -- a real subprocess
     execution, not a guess -- as a representative same-runtime proxy for
     the Node-based configured servers (Context-mode runs `node`;
     Chrome-devtools runs `npx` which itself execs node). This is
     explicitly a PROXY measurement of "one idle Node interpreter", NOT a
     claim about the actual chrome-devtools-mcp or Context-mode packages,
     which are not installed/resolvable on this host right now (no
     CLAUDE_PLUGIN_ROOT env var, no start.mjs found on disk -- verified
     below) and were not fetched over the network to keep this probe
     side-effect-free.
  4. Compute an EXPLICITLY LABELED extrapolation (not a measurement) for
     what N concurrent sessions x the 3 configured servers would cost,
     using the measured node-proxy RSS for the one server we could measure
     and disclosing the other two servers' real RSS as NOT-CHECKED.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _proc_census as C  # noqa: E402


def read_meminfo() -> dict[str, int]:
    wanted = {
        "MemTotal": "mem_total_kb",
        "MemFree": "mem_free_kb",
        "MemAvailable": "mem_available_kb",
        "Committed_AS": "committed_as_kb",
        "CommitLimit": "commit_limit_kb",
        "SwapTotal": "swap_total_kb",
        "SwapFree": "swap_free_kb",
    }
    out: dict[str, int] = {}
    text = Path("/proc/meminfo").read_text(encoding="ascii", errors="replace")
    for line in text.splitlines():
        key = line.split(":", 1)[0]
        if key in wanted:
            val = int(line.split()[1])
            out[wanted[key]] = val
    return out


def measure_idle_node_proxy(settle_seconds: float = 0.35) -> dict[str, object]:
    """Spawn a real, local, network-free idle node child (busy for
    `settle_seconds` via a synchronous sleep loop so we can sample it while
    alive), measure its ACTUAL /proc/<pid>/status RSS/VSZ, then let it exit.
    Returns measured=False with a reason if node is unavailable or the
    process cannot be sampled before it exits -- never a fabricated number.
    """
    node_bin = None
    for candidate in ("/exec-daemon/node", "node"):
        try:
            subprocess.run(
                [candidate, "--version"], capture_output=True, timeout=5, check=True
            )
            node_bin = candidate
            break
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            continue
    if node_bin is None:
        return {
            "measured": False,
            "reason": "no node binary found on PATH or at /exec-daemon/node",
        }

    script = f"setTimeout(() => process.exit(0), {int(settle_seconds * 1000) + 500});"
    try:
        proc = subprocess.Popen([node_bin, "-e", script])
    except OSError as exc:
        return {
            "measured": False,
            "reason": f"spawn failed: {type(exc).__name__}: {exc}",
        }

    time.sleep(settle_seconds)
    mem = C.read_status_mem(proc.pid)
    stat = C.read_stat_fields(proc.pid)
    alive = stat is not None
    try:
        proc.wait(timeout=5)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        exit_code = proc.returncode

    if not alive or mem["vmrss_kb"] == 0:
        return {
            "measured": False,
            "reason": "child exited or was unsampleable before the settle delay elapsed",
            "node_bin": node_bin,
            "exit_code": exit_code,
        }
    return {
        "measured": True,
        "node_bin": node_bin,
        "pid": proc.pid,
        "vmrss_kb": mem["vmrss_kb"],
        "vmsize_kb": mem["vmsize_kb"],
        "settle_seconds": settle_seconds,
        "exit_code": exit_code,
    }


def check_plugin_root_resolvable() -> dict[str, object]:
    env_val = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    resolved = bool(env_val) and Path(env_val, "start.mjs").is_file()
    return {
        "claude_plugin_root_env_set": bool(env_val),
        "claude_plugin_root_env_value": env_val,
        "start_mjs_exists_on_disk": resolved,
    }


def main() -> int:
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    own_ticks = C.own_creation_ticks()

    meminfo = read_meminfo()

    raw_rows = C.scan_raw()
    kept, excluded = C.apply_self_exclusion(raw_rows, own_ticks)
    total_rss_kb = sum(r["vmrss_kb"] for r in kept)
    total_vsz_kb = sum(r["vmsize_kb"] for r in kept)

    md = C.find_exec_daemon_mcp_config(kept) or C.find_exec_daemon_mcp_config(raw_rows)
    configured_servers = md["mcp_servers_config"] if md else {}
    configured_server_count = len(configured_servers)

    mcp_live = []
    for name, sdef in configured_servers.items():
        for row in kept:
            if C.server_match(row, name, sdef):
                mcp_live.append(
                    {
                        "server_name": name,
                        "pid": row["pid"],
                        "vmrss_kb": row["vmrss_kb"],
                    }
                )
    mcp_live_total_rss_kb = sum(m["vmrss_kb"] for m in mcp_live)

    plugin_root_check = check_plugin_root_resolvable()
    proxy = measure_idle_node_proxy()

    node_backed_server_count = sum(
        1
        for sdef in configured_servers.values()
        if sdef.get("command") in ("node", "npx")
    )
    non_node_server_count = configured_server_count - node_backed_server_count

    exec_daemon_rss_kb = md["exec_daemon_vmrss_kb"] if md else 0
    if proxy.get("measured"):
        extrapolated_single_session_measured_component_kb = exec_daemon_rss_kb + (
            int(proxy["vmrss_kb"]) * node_backed_server_count
        )
    else:
        extrapolated_single_session_measured_component_kb = exec_daemon_rss_kb

    catalog_incident_sessions = 23
    extrapolated_n_sessions_kb = (
        extrapolated_single_session_measured_component_kb * catalog_incident_sessions
        if proxy.get("measured")
        else None
    )

    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    doc = {
        "probe": "AUD-0061-probe2-memory-cost",
        "started_at": started,
        "ended_at": ended,
        "platform_scope_note": (
            "Linux host: no Windows-shaped commit-charge/pagefile metric "
            "exists here. committed_as_kb/commit_limit_kb below are "
            "/proc/meminfo's real Linux analog (total virtual memory the "
            "kernel has promised to back vs. the point past which further "
            "overcommit is refused absent swap); vmrss_kb/vmsize_kb are the "
            "measured RSS/VSZ this catalog item asks for as the fallback "
            "when Windows commit-charge is unavailable."
        ),
        "host_meminfo": meminfo,
        "self_pid": os.getpid(),
        "self_starttime_ticks": own_ticks,
        "raw_process_count": len(raw_rows),
        "self_excluded_count": len(excluded),
        "final_process_count": len(kept),
        "total_rss_kb_all_processes": total_rss_kb,
        "total_vsz_kb_all_processes": total_vsz_kb,
        "exec_daemon_found": md is not None,
        "exec_daemon_rss_kb": exec_daemon_rss_kb,
        "exec_daemon_vsz_kb": md["exec_daemon_vmsize_kb"] if md else 0,
        "mcp_configured_server_count": configured_server_count,
        "mcp_live_process_count": len(mcp_live),
        "mcp_live_total_rss_kb": mcp_live_total_rss_kb,
        "node_backed_configured_server_count": node_backed_server_count,
        "non_node_configured_server_count": non_node_server_count,
        "context_mode_plugin_root_check": plugin_root_check,
        "idle_node_proxy_measurement": proxy,
        "extrapolation": {
            "method": (
                "MEASURED exec_daemon_rss_kb + (MEASURED idle-node-proxy "
                "vmrss_kb x count of configured servers whose declared "
                "command is node/npx). The uvx-launched Browser-use "
                "server's RSS was NOT measured (no network package fetch "
                "attempted) and is NOT included -- this extrapolation is a "
                "documented UNDER-estimate, not a full accounting."
            ),
            "single_session_kb": extrapolated_single_session_measured_component_kb,
            "catalog_incident_session_count_input": catalog_incident_sessions,
            "extrapolated_n_sessions_kb": extrapolated_n_sessions_kb,
            "extrapolated_n_sessions_exceeds_host_mem_total": (
                bool(
                    extrapolated_n_sessions_kb is not None
                    and extrapolated_n_sessions_kb > meminfo.get("mem_total_kb", 0)
                )
            ),
        },
        "ok": True,
    }
    print(json.dumps(doc, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
