"""Decepticon terminal MCP server - dual-mode (kali container tmux / local sessions).

Same tool surface in both modes: create_session, session_list, command_exec,
kill_session, kill_server. kali mode uses tmux inside the `attacker` container;
local mode keeps per-session output buffers and executes via _exec.exec_command.
"""
from mcp.server.fastmcp import FastMCP
from typing_extensions import Annotated
from typing import List
from _exec import exec_command
import subprocess
import uuid
import time
import os
import threading

CONTAINER_NAME = os.environ.get("DECEPTICON_CONTAINER", "attacker")

mcp = FastMCP("terminal", port=3003)

# local-mode session buffers: session -> list of output chunks
_SESSIONS: dict = {}
_LOCK = threading.Lock()

_TMUX_TOOLS = ["bash", "-lc"]  # fallback if tmux binary is absent inside container


def _docker_ok() -> bool:
    try:
        probe = subprocess.run(
            ["docker", "ps", "--filter", f"name=^{CONTAINER_NAME}$", "--format", "{{.Names}}"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=15,
        )
        return probe.returncode == 0 and CONTAINER_NAME in probe.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def run(command: List[str]) -> subprocess.CompletedProcess:
    """docker exec helper (kali mode)"""
    return subprocess.run(
        ["docker", "exec", CONTAINER_NAME] + command,
        capture_output=True, text=True, encoding="utf-8", errors="ignore",
    )


def tmux_run(command: List[str]) -> subprocess.CompletedProcess:
    return run(["tmux"] + command)


@mcp.tool(description="Create new terminal sessions")
def create_session(
    session_names: Annotated[List[str], "Session names to create"]
) -> Annotated[List[str], "List of created session names"]:
    """New terminal sessions (tmux in kali mode; buffer sessions locally)"""
    if _docker_ok():
        created_sessions = []
        for session_name in session_names:
            result = tmux_run(["new-session", "-d", "-s", session_name])
            if result.returncode != 0:
                raise Exception(f"Failed to create session '{session_name}': {result.stderr}")
            created_sessions.append(session_name)
        return created_sessions
    with _LOCK:
        for session_name in session_names:
            _SESSIONS.setdefault(session_name, [])
    return list(session_names)


@mcp.tool(description="List all active sessions")
def session_list() -> Annotated[List[str], "List of session IDs"]:
    if _docker_ok():
        result = tmux_run(["list-sessions"])
        if result.returncode != 0:
            return []
        return [line.split(":")[0].strip() for line in result.stdout.strip().split("\n") if line.strip()]
    with _LOCK:
        return sorted(_SESSIONS.keys())


@mcp.tool(description="Execute command in session")
def command_exec(
    session_id: Annotated[str, "Session ID"],
    command: Annotated[str, "Command to execute"],
) -> Annotated[str, "Command output"]:
    """Execute a command in a session and return its output"""
    if _docker_ok():
        channel = f"done-{session_id}-{uuid.uuid4().hex[:8]}"
        timestamp = int(time.time())
        output_file = f"/tmp/cmd_output_{session_id}_{timestamp}.txt"
        status_file = f"/tmp/cmd_status_{session_id}_{timestamp}.txt"
        full_command = f"({command}) > {output_file} 2>&1; echo $? > {status_file}; tmux wait-for -S {channel}"
        result = tmux_run(["send-keys", "-t", session_id, full_command, "Enter"])
        if result.returncode != 0:
            raise Exception(f"Failed to execute command: {result.stderr}")
        wait_result = tmux_run(["wait-for", channel])
        if wait_result.returncode != 0:
            raise Exception(f"Command execution monitoring failed: {result.stderr}")
        time.sleep(0.1)
        try:
            status_result = run(["cat", status_file])
            if status_result.returncode != 0:
                raise Exception(f"Failed to read status file: {status_result.stderr}")
            try:
                exit_code = int(status_result.stdout.strip())
            except ValueError:
                raise Exception(f"Invalid exit code: '{status_result.stdout.strip()}'")
            output_result = run(["cat", output_file])
            if output_result.returncode != 0:
                raise Exception(f"Failed to read output file: {output_result.stderr}")
            output = output_result.stdout
            run(["rm", "-f", output_file, status_file])
            if exit_code != 0:
                raise Exception(f"Command failed with exit code {exit_code}: {output.strip()}")
            return output.strip()
        except Exception as exc:
            run(["rm", "-f", output_file, status_file])
            raise Exception(f"Failed to process command result: {str(exc)}") from exc
    # local mode
    with _LOCK:
        _SESSIONS.setdefault(session_id, [])
    mode, returncode, output = exec_command(command, timeout=900)
    with _LOCK:
        _SESSIONS[session_id].append(f"$ {command}\n{output}")
        if len(_SESSIONS[session_id]) > 100:
            del _SESSIONS[session_id][:-100]
    if returncode != 0 and not output.startswith("[-]"):
        raise Exception(f"Command failed with exit code {returncode} (mode {mode}): {output.strip()}")
    return output.strip()


@mcp.tool(description="Kill terminal sessions")
def kill_session(
    session_names: Annotated[List[str], "Session names to kill"]
) -> Annotated[List[str], "Results for each session"]:
    if _docker_ok():
        results = []
        for session_name in session_names:
            try:
                result = tmux_run(["kill-session", "-t", session_name])
                if result.returncode == 0:
                    results.append(f"Session {session_name} killed successfully")
                else:
                    results.append(f"Session {session_name} killed (with warning: {result.stderr})")
            except Exception as e:
                results.append(f"Failed to kill session {session_name}: {str(e)}")
        return results
    with _LOCK:
        for session_name in session_names:
            _SESSIONS.pop(session_name, None)
    return [f"Session {name} killed successfully" for name in session_names]


@mcp.tool(description="Kill server, Kill all session")
def kill_server() -> Annotated[str, "Result"]:
    if _docker_ok():
        try:
            tmux_run(["kill-server"])
            return "Server killed"
        except Exception as e:
            return f"Server killed (with warning: {str(e)})"
    with _LOCK:
        _SESSIONS.clear()
    return "Server killed (local sessions cleared)"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
