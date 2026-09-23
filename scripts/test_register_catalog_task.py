"""Text contract for scripts/register-catalog-task.ps1 (D12 / WU-12 daily catalog sync).

The Scheduled Task is registered on the owner's Windows box; CI cannot register one. What
CI CAN hold fixed is the text the owner runs: the task name and cadence, the two fences
against overlapping runs (``-MultipleInstances IgnoreNew`` on the task and the
``Global\\AgentsCatalogSync`` mutex in the launched command), the 20-minute time limit,
``-StartWhenAvailable``, the RAM guard, the exact interpreter + script + ``--root`` it
launches, the ``-DryRun`` and ``-Unregister`` switches, and that the script it launches
exists in this repo. Every assertion below is something whose silent loss would leave the
owner registering a task that does the wrong thing at 03:30 with nobody watching.

When ``pwsh`` is on PATH the script is also parsed and dry-run for real (no ScheduledTasks
cmdlet is touched by ``-DryRun``, so this works on Linux too); otherwise those two tests skip.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SCRIPT = HERE / "register-catalog-task.ps1"
CATALOG_SYNC = REPO / "command-center" / "ssot" / "catalog_sync.py"
PWSH = shutil.which("pwsh")

SECRET_SHAPES = (
    r"sk-[A-Za-z0-9_-]{20,}",
    r"sk-or-v1-[A-Za-z0-9]{20,}",
    r"hf_[A-Za-z0-9]{20,}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"xox[abprs]-[A-Za-z0-9-]{10,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)bearer\s+[A-Za-z0-9._-]{20,}",
    r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    r"[A-Za-z0-9+/]{40,}={0,2}",
)


@pytest.fixture(scope="module")
def text() -> str:
    # .gitattributes checks *.ps1 out with CRLF; the contract is about content.
    return SCRIPT.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_script_exists_and_is_plain_ascii(text: str) -> None:
    assert SCRIPT.is_file()
    assert text.isascii(), (
        "Windows PowerShell 5.1 reads a BOM-less file as ANSI; stay ASCII"
    )


def test_task_identity_and_cadence(text: str) -> None:
    assert "'AgentsCatalogSync-Daily'" in text
    assert "[string]$At = '03:30'" in text
    assert "New-ScheduledTaskTrigger -Daily -At $At" in text


def test_two_fences_against_overlapping_runs(text: str) -> None:
    assert "-MultipleInstances IgnoreNew" in text
    assert "'Global\\AgentsCatalogSync'" in text
    assert "New-Object System.Threading.Mutex($false, $MutexName)" in text
    assert "$mutex.WaitOne(0)" in text
    assert "$mutex.ReleaseMutex()" in text
    assert "AbandonedMutexException" in text


def test_time_limit_start_when_available_and_ram_guard(text: str) -> None:
    assert "New-TimeSpan -Minutes 20" in text
    assert "-ExecutionTimeLimit $TimeLimit" in text
    assert "-StartWhenAvailable" in text
    assert "Get-Counter '\\Memory\\Available MBytes'" in text
    assert "[int]$MinFreeMB = 2048" in text
    assert "$freeMB -lt $MinFreeMB" in text


def test_launches_the_pinned_interpreter_script_and_root(text: str) -> None:
    assert "[string]$Python = 'C:\\Python314\\python.exe'" in text
    assert (
        "[string]$Toolchain = 'C:\\Users\\Prekzursil\\source\\agent-skills-toolchain'"
        in text
    )
    assert (
        "[string]$StateRoot = 'C:\\Users\\Prekzursil\\.agents\\state\\catalog'" in text
    )
    assert "Join-Path $Toolchain 'command-center\\ssot\\catalog_sync.py'" in text
    assert "--root" in text
    assert "Start-Process -FilePath $Python" in text
    assert "exit $proc.ExitCode" in text


def test_dry_run_and_unregister_switches(text: str) -> None:
    assert "[switch]$DryRun" in text
    assert "[switch]$Unregister" in text
    assert "[switch]$Run" in text
    assert "Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false" in text
    dry_run_block = text[text.index("if ($DryRun) {\n    Write-Info 'DRY RUN") :]
    dry_run_block = dry_run_block[: dry_run_block.index("\n}\n")]
    assert "Register-ScheduledTask" not in dry_run_block
    assert "return" in dry_run_block


def test_register_call_carries_settings_principal_and_force(text: str) -> None:
    register = text[text.index("Register-ScheduledTask -TaskName $TaskName") :]
    register = register[: register.index("| Out-Null")]
    for fragment in (
        "-Action $action",
        "-Trigger $trigger",
        "-Settings $settings",
        "-Principal $principal",
        "-Force",
    ):
        assert fragment in register
    assert "-RunLevel Limited" in text
    assert "-LogonType Interactive" in text


def test_task_action_points_at_the_executed_checkout_not_this_file(text: str) -> None:
    assert "Join-Path $Toolchain 'scripts\\register-catalog-task.ps1'" in text
    assert '-File "{0}" -Run' in text
    assert "-Execute (Resolve-Shell) -Argument $ActionArgument" in text
    assert "$PSCommandPath -ne $TaskScript" in text


def test_no_secret_shaped_strings(text: str) -> None:
    for shape in SECRET_SHAPES:
        assert re.search(shape, text) is None, f"secret-shaped text matches {shape!r}"
    assert "Authorization" not in text
    assert re.search(r"(?i)\$env:[A-Z_]*(TOKEN|KEY|SECRET)", text) is None


def test_the_launched_script_exists_in_the_repo() -> None:
    assert CATALOG_SYNC.is_file(), (
        f"{CATALOG_SYNC} must exist: the task launches it by path"
    )
    assert "def main(" in CATALOG_SYNC.read_text(encoding="utf-8")
    assert "--root" in CATALOG_SYNC.read_text(encoding="utf-8")


def _pwsh(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    assert PWSH is not None
    return subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.mark.skipif(PWSH is None, reason="pwsh not on PATH")
def test_script_parses_without_errors() -> None:
    probe = (
        "$t = $null; $e = $null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{SCRIPT.as_posix()}', [ref]$t, [ref]$e) | Out-Null; "
        "$e | ForEach-Object { $_.Message }; exit $e.Count"
    )
    result = _pwsh("-Command", probe)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(PWSH is None, reason="pwsh not on PATH")
def test_dry_run_prints_the_plan_and_registers_nothing(tmp_path: Path) -> None:
    result = _pwsh(
        "-File",
        str(SCRIPT),
        "-DryRun",
        "-Toolchain",
        str(REPO),
        "-StateRoot",
        str(tmp_path / "catalog"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout
    assert "DRY RUN - nothing is registered" in out
    assert "TaskName      : AgentsCatalogSync-Daily" in out
    assert "Trigger       : Daily at 03:30" in out
    assert "-MultipleInstances IgnoreNew" in out
    assert "New-TimeSpan -Minutes 20" in out
    assert "-StartWhenAvailable" in out
    assert "mutex Global\\AgentsCatalogSync" in out
    assert "Get-Counter '\\Memory\\Available MBytes' < 2048" in out
    assert "catalog_sync.py" in out
    assert "--root" in out
    assert "catalog_sync.py  exists=True" in out
    assert not (tmp_path / "catalog").exists()
