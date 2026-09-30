"""Dual-mode command execution for Decepticon MCP tool servers.

Full capability in both modes:
- kali mode: a running docker engine with the `attacker` container -> the
  command runs inside the container (`docker exec`, full kali toolset).
- local mode: otherwise -> the command runs on this host through Git Bash's
  `sh -c` (POSIX syntax preserved) so nothing is un-wired when Docker is
  unavailable.

Override knobs:
- DECEPTICON_CONTAINER  container name (default: attacker)
- DECEPTICON_SHELL      absolute shell used in local mode (default: Git Bash sh)
- DECEPTICON_FORCE      "kali" | "local"  to pin a mode (default: auto)
"""
from __future__ import annotations

import os
import shutil
import subprocess

CONTAINER_NAME = os.environ.get("DECEPTICON_CONTAINER", "attacker")


def _local_shell() -> list[str]:
    override = os.environ.get("DECEPTICON_SHELL")
    if override:
        return [override, "-c"]
    candidates = [
        r"C:\Program Files\Git\bin\sh.exe",
        r"C:\Program Files\Git\usr\bin\sh.exe",
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return [cand, "-c"]
    which = shutil.which("sh")
    if which:
        return [which, "-c"]
    return ["powershell", "-NoProfile", "-Command"]


def _attacker_container_running() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        probe = subprocess.run(
            [docker, "ps", "--filter", f"name=^{CONTAINER_NAME}$",
             "--format", "{{.Names}}"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0 and CONTAINER_NAME in probe.stdout


def resolve_mode() -> str:
    forced = os.environ.get("DECEPTICON_FORCE", "").strip().lower()
    if forced in ("kali", "local"):
        return forced
    return "kali" if _attacker_container_running() else "local"


def exec_command(command: str, timeout: int = 600) -> tuple[str, int, str]:
    """Run `command` in the resolved mode. Returns (mode, returncode, output).

    Output convention matches the original servers: stderr on failure, stdout
    on success; callers format their own '[-] ...' error strings.
    """
    mode = resolve_mode()
    if mode == "kali":
        result = subprocess.run(
            ["docker", "exec", CONTAINER_NAME, "sh", "-c", command],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=timeout,
        )
    else:
        try:
            result = subprocess.run(
                _local_shell() + [command],
                capture_output=True, text=True, encoding="utf-8", errors="ignore",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return mode, 124, f"[-] Command timed out after {timeout}s"
        except FileNotFoundError as exc:
            return mode, 127, f"[-] Local shell not found: {exc}"
    output = result.stdout or ""
    if result.returncode != 0 and result.stderr.strip():
        output = f"[-] Command execution error: {result.stderr.strip()}\n{output}".strip()
    return mode, result.returncode, output.strip()
