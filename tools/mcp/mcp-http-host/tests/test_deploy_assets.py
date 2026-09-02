"""Pin the Windows deploy assets for the session-healing proxy.

``pwsh`` is not available on this runner, so these are static checks: the three
scripts exist, name the right ports / tasks / paths, mirror the daemon launcher's
hardening vocabulary, never touch the daemon, and keep the proxy's argv free of the
daemon's identity tokens. A brace / parenthesis balance heuristic catches the
typos a syntax check would.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
LAUNCHER = DEPLOY / "bm-session-proxy.ps1"
WATCHDOG = DEPLOY / "bm-session-proxy-watchdog.ps1"
REGISTER = DEPLOY / "Register-BmSessionProxyTasks.ps1"
README = DEPLOY / "README.md"
MOVER = DEPLOY / "move_daemon_port.py"
SCRIPTS = (LAUNCHER, WATCHDOG, REGISTER)
DAEMON_TOKENS = ("basic_memory", "basic-memory", "streamable-http")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def no_comments(text: str) -> str:
    """PowerShell source with block and line comments removed (strings kept)."""
    text = re.sub(r"<#.*?#>", "", text, flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        # a '#' inside a string literal is not a comment; strip only after the last quote
        cut = line
        if "#" in line:
            head, _, _ = line.rpartition("#")
            cut = (
                head if head.count("'") % 2 == 0 and head.count('"') % 2 == 0 else line
            )
        lines.append(cut)
    return "\n".join(lines)


def code_only(text: str) -> str:
    """``no_comments`` with string literals removed too, for the balance heuristic."""
    text = no_comments(text)
    text = re.sub(r"'[^'\n]*'", "''", text)
    return re.sub(r'"[^"\n]*"', '""', text)


def test_all_assets_are_present():
    for path in (*SCRIPTS, README, MOVER):
        assert path.is_file(), path


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_braces_and_parentheses_balance(path):
    code = code_only(read(path))
    assert code.count("{") == code.count("}"), path.name
    assert code.count("(") == code.count(")"), path.name


def test_launcher_owns_8765_and_forwards_to_8766():
    text = read(LAUNCHER)
    assert "$Port          = 8765" in text
    assert "$UpstreamPort  = 8766" in text
    assert "'--upstream', \"http://127.0.0.1:$UpstreamPort/mcp\"" in text
    assert "'--restart-log'" in text
    assert "Join-Path $AgentLogDir 'bm-session-proxy.jsonl'" in text
    assert (
        "basic-memory-supervisor.log" in text
    )  # restart visibility, the receipt's convention
    assert "bm_session_proxy.py" in text


def test_launcher_mirrors_the_daemon_launchers_hardening():
    text = read(LAUNCHER)
    for token in (
        "[System.IO.File]::Open($Lock, 'OpenOrCreate', 'ReadWrite', 'None')",  # start-lock
        "already in use - not starting a second",  # idempotent skip
        "Test-NetConnection -ComputerName 127.0.0.1 -Port $Port",  # bind wait
        "-RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog",  # per-launch logs
        "Select-Object -Skip $KeepLaunchLogs",  # pruned to the newest 8
        "Set-Content -Path $Marker",  # relaunch marker (re-stamped in the loop)
        "$proc.WaitForExit()",
        "did NOT bind in",
        "$lockStream.Close()",
    ):
        assert token in text, token
    assert (
        text.count("Set-Content -Path $Marker") >= 2
    )  # before AND during the bind wait


def test_proxy_scripts_never_touch_the_daemon_and_use_their_own_state_files():
    for path in SCRIPTS:
        text = read(path)
        code = no_comments(
            text
        )  # comments SAY what must never happen; code must not do it
        assert "Get-Process basic-memory" not in code, path.name
        assert "basic-memory*" not in code, path.name
        assert "bm-http-server" not in code, path.name
        assert "bm-relaunch.marker" not in code, path.name
        assert "BasicMemory-HTTP-MCP" not in code, path.name
        assert "*bm_session_proxy.py*" in text, (
            path.name
        )  # kill-stale scoped to the proxy
    assert "'bm-session-proxy.lock'" in read(LAUNCHER)
    assert "'bm-session-proxy-relaunch.marker'" in read(LAUNCHER)
    assert "'bm-session-proxy-relaunch.marker'" in read(WATCHDOG)


def test_the_launched_argv_carries_none_of_the_daemons_identity_tokens():
    text = read(LAUNCHER)
    argv_block = text[text.index("$argv = @(") : text.index("$proc = Start-Process")]
    defining = [
        line
        for line in text.splitlines()
        if re.match(r"^\$(Repo|Script|AgentLogDir|RestartLog)\s*=", line)
    ]
    assert len(defining) == 4
    for snippet in (argv_block, *defining):
        for token in DAEMON_TOKENS:
            assert token not in snippet.lower(), (token, snippet)
    # the launcher's OWN home is the daemon's folder (a pwsh path, not the python argv)
    assert "C:\\Users\\Prekzursil\\.basic-memory\\logs" in text


def test_watchdog_probes_healthz_and_force_recovers_only_the_proxy():
    text = read(WATCHDOG)
    assert '"http://127.0.0.1:$Port/healthz"' in text
    assert "$Task          = 'BasicMemory-SessionProxy'" in text
    assert "$ProbeTimeoutSec = 15" in text
    assert "$GraceSec        = 75" in text
    assert "bm-session-proxy-degraded.strike" in text  # two-strike rule
    assert "Test-Path $Strike" in text
    assert "$_.ProcessId -ne $PID" in text  # never kills itself
    assert "*bm-session-proxy.ps1*" in text  # a stuck launcher
    assert "schtasks /End /TN $Task" in text
    assert "Start-ScheduledTask -TaskName $Task" in text
    assert "upstream.state" in text  # logs the daemon's state, does not act on it
    assert "bm-watchdog.ps1" not in no_comments(text)


def test_registration_defines_both_tasks_like_the_daemons_pair():
    text = read(REGISTER)
    assert "[CmdletBinding(SupportsShouldProcess)]" in text
    assert "$ProxyTask    = 'BasicMemory-SessionProxy'" in text
    assert "$WatchdogTask = 'BasicMemory-SessionProxy-Watchdog'" in text
    assert "New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME" in text
    assert "-RepetitionInterval (New-TimeSpan -Minutes 5)" in text
    assert "-RepetitionInterval (New-TimeSpan -Minutes 3)" in text
    assert "-ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew" in text
    assert "-RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)" in text
    assert "-LogonType Interactive -RunLevel Limited" in text
    assert "Export-ScheduledTask -TaskName $Name" in text  # backup before replace
    assert "-WindowStyle Hidden -ExecutionPolicy Bypass -File" in text
    assert "if ($Uninstall)" in text
    assert text.index("$WatchdogTask, $ProxyTask") < text.index(
        "Unregister-ScheduledTask"
    )


def test_readme_carries_the_edits_staging_cutover_and_rollback():
    text = read(README)
    for needle in (
        'move_daemon_port.py" --apply',
        'move_daemon_port.py" --check',
        'move_daemon_port.py" --rollback',
        "'*basic-memory*8766*'",
        "--port 8767 --upstream http://127.0.0.1:8765/mcp",  # staging in front of the live daemon
        "critical.json",
        "restart-basic-memory.ps1",
        "memory-contract.md",
        "x_cursor",
        "## Rollback",
        "Stop-ScheduledTask 'BasicMemory-Watchdog'",
        "Start-ScheduledTask 'BasicMemory-SessionProxy'",
        "/healthz",
        "bm-session-proxy.jsonl",
    ):
        assert needle in text, needle
