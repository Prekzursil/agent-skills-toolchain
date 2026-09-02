#!/usr/bin/env python3
"""RES-0037 measurement library: process-table vs handle-count, self-exclusion."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
STDIO_SCRIPT = HERE / "fixtures" / "stdio_standin.py"
HTTP_SCRIPT = HERE / "fixtures" / "http_standin.py"

# Exact argv tokens. They must NOT appear on the probe's own command line.
TOKEN_STDIO = "RES0037_STDIO_STANDIN"
TOKEN_HTTP = "RES0037_HTTP_STANDIN"
DECOY_TOKEN = "RES0037_DECOY_NOT_A_SERVER"

N_SESSIONS = 3
N_STDIO_SERVERS = 2
RECORDED_SESSIONS = 23
RECORDED_SERVERS = 65
RECORDED_CLAIMED_PROCESSES = 2037

PROBE_SCRIPT_MARKERS = (
    "probe1_self_exclusion_delta.py",
    "probe2_handle_count.py",
    "emit.py",
)


def read_cmdline(pid: int) -> list[str] | None:
    path = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None
    if not raw:
        return None
    parts = [p.decode("utf-8", "replace") for p in raw.split(b"\x00") if p]
    return parts or None


def iter_proc_argv() -> list[dict]:
    rows: list[dict] = []
    proc = Path("/proc")
    try:
        names = list(proc.iterdir())
    except OSError:
        return rows
    for entry in names:
        name = entry.name
        if not name.isdigit():
            continue
        pid = int(name)
        argv = read_cmdline(pid)
        if argv is None:
            continue
        rows.append(
            {
                "pid": pid,
                "argv": argv,
                "cmdline": " ".join(argv),
            }
        )
    return rows


def python_script_arg(argv: list[str]) -> str | None:
    """The script the interpreter is running: first argv element ending in .py."""
    for arg in argv:
        if arg.endswith(".py"):
            return arg
    return None


def is_this_probe_argv(argv: list[str]) -> bool:
    script = python_script_arg(argv)
    if not script:
        return False
    return Path(script).name in PROBE_SCRIPT_MARKERS


def naive_substring_pids(needle: str, rows: list[dict] | None = None) -> list[int]:
    """Bad matcher: substring anywhere in the joined command line, including self."""
    if rows is None:
        rows = iter_proc_argv()
    hits = []
    for row in rows:
        if needle in row["cmdline"]:
            hits.append(int(row["pid"]))
    return sorted(hits)


def token_exact_pids(
    token: str,
    rows: list[dict] | None = None,
    exclude_probe_scripts: bool = True,
) -> list[int]:
    """Good matcher: token must be a distinct argv element. Probe scripts excluded."""
    if rows is None:
        rows = iter_proc_argv()
    hits = []
    self_pid = os.getpid()
    for row in rows:
        pid = int(row["pid"])
        if pid == self_pid:
            continue
        argv = row["argv"]
        if token not in argv:
            continue
        if exclude_probe_scripts and is_this_probe_argv(argv):
            continue
        hits.append(pid)
    return sorted(hits)


def kill_pids(pids: list[int], timeout: float = 2.0) -> None:
    self_pid = os.getpid()
    for pid in pids:
        if pid in (0, 1, self_pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            continue
    deadline = time.time() + timeout
    remaining = set(pids)
    while remaining and time.time() < deadline:
        still = set()
        for pid in remaining:
            if Path("/proc", str(pid)).exists():
                still.add(pid)
        remaining = still
        if remaining:
            time.sleep(0.05)
    for pid in remaining:
        if pid in (0, 1, self_pid):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def reap_orphans() -> dict:
    before = token_exact_pids(TOKEN_STDIO) + token_exact_pids(TOKEN_HTTP)
    decoy = token_exact_pids(DECOY_TOKEN)
    kill_pids(sorted(set(before + decoy)))
    time.sleep(0.05)
    after = token_exact_pids(TOKEN_STDIO) + token_exact_pids(TOKEN_HTTP)
    return {"killed": sorted(set(before + decoy)), "remaining": after}


def _spawn(script: Path, token: str, extra: list[str]) -> subprocess.Popen:
    cmd = [sys.executable, "-B", str(script), token, *extra]
    return subprocess.Popen(
        cmd,
        cwd=str(REPO),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def wait_pid_token(pid: int, token: str, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        argv = read_cmdline(pid)
        if argv and token in argv:
            return True
        if not Path("/proc", str(pid)).exists():
            return False
        time.sleep(0.02)
    return False


def spawn_stdio(session_id: str, server_id: str) -> subprocess.Popen:
    proc = _spawn(STDIO_SCRIPT, TOKEN_STDIO, [session_id, server_id])
    if not wait_pid_token(proc.pid, TOKEN_STDIO):
        proc.kill()
        raise RuntimeError(f"stdio stand-in pid={proc.pid} never showed token")
    return proc


def spawn_http(label: str) -> tuple[subprocess.Popen, int | None]:
    proc = _spawn(HTTP_SCRIPT, TOKEN_HTTP, [label])
    if not wait_pid_token(proc.pid, TOKEN_HTTP):
        proc.kill()
        raise RuntimeError(f"http stand-in pid={proc.pid} never showed token")
    port = None
    deadline = time.time() + 5.0
    buf = ""
    socks: list[int] = []
    while time.time() < deadline:
        socks = listen_inodes(proc.pid)
        if socks:
            break
        time.sleep(0.02)
    if not socks:
        proc.kill()
        raise RuntimeError(f"http stand-in pid={proc.pid} never opened a LISTEN socket")
    if proc.stdout is not None:
        # Non-blocking first-line read if the child already wrote PORT=.
        try:
            os.set_blocking(proc.stdout.fileno(), False)
            chunk = proc.stdout.read() or ""
            buf += chunk
            for line in buf.splitlines():
                if line.startswith("PORT="):
                    port = int(line.split("=", 1)[1])
                    break
        except (OSError, ValueError):
            port = None
    return proc, port


def fd_entries(pid: int) -> list[str]:
    fd_dir = Path("/proc") / str(pid) / "fd"
    names: list[str] = []
    try:
        for entry in fd_dir.iterdir():
            try:
                names.append(os.readlink(entry))
            except OSError:
                names.append(f"unreadable:{entry.name}")
    except (FileNotFoundError, PermissionError, OSError):
        return []
    return names


def fd_count(pid: int) -> int:
    return len(fd_entries(pid))


def _parse_proc_net_listen_inodes(table: Path) -> set[int]:
    inodes: set[int] = set()
    try:
        text = table.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return inodes
    lines = text.splitlines()
    if len(lines) < 2:
        return inodes
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        # st is hex; 0A = LISTEN
        if parts[3].lower() != "0a":
            continue
        try:
            inodes.add(int(parts[9]))
        except ValueError:
            continue
    return inodes


def listen_inodes(pid: int) -> list[int]:
    listen = set()
    listen |= _parse_proc_net_listen_inodes(Path("/proc/net/tcp"))
    listen |= _parse_proc_net_listen_inodes(Path("/proc/net/tcp6"))
    found: list[int] = []
    for target in fd_entries(pid):
        if not target.startswith("socket:"):
            continue
        try:
            inode = int(target.split("[", 1)[1].rstrip("]"))
        except (IndexError, ValueError):
            continue
        if inode in listen:
            found.append(inode)
    return found


def ps_token_pids(token: str) -> list[int]:
    """Independent process-table rail: /bin/ps, not a Python /proc walk."""
    proc = subprocess.run(
        ["/bin/ps", "-eo", "pid=,args="],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ps failed rc={proc.returncode} err={proc.stderr[-400:]}")
    hits: list[int] = []
    self_pid = os.getpid()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid == self_pid:
            continue
        args = parts[1]
        argv = args.split()
        if token not in argv:
            continue
        if is_this_probe_argv(argv):
            continue
        hits.append(pid)
    return sorted(hits)


def expr_product(a: int, b: int) -> int:
    """Independent arithmetic rail: POSIX expr, not Python multiplication."""
    proc = subprocess.run(
        ["expr", str(a), "*", str(b)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode not in (0, 1) or not proc.stdout.strip().isdigit():
        raise RuntimeError(
            f"expr failed rc={proc.returncode} out={proc.stdout!r} err={proc.stderr!r}"
        )
    return int(proc.stdout.strip())


def fleet_snapshot() -> dict:
    """Live MCP-ish fleet on this box, with a matcher that does not scan -c blobs."""
    rows = iter_proc_argv()
    naive_mcp = naive_substring_pids("mcp", rows)
    exact: list[dict] = []
    for row in rows:
        argv = row["argv"]
        if not argv:
            continue
        if is_this_probe_argv(argv):
            continue
        if TOKEN_STDIO in argv or TOKEN_HTTP in argv or DECOY_TOKEN in argv:
            continue
        short = [a for a in argv if len(a) < 240]
        bases = [Path(a).name for a in short]
        hit = False
        reason = ""
        if any(b in {"mcp", "mcp.exe"} for b in bases):
            hit = True
            reason = "argv-basename-mcp"
        elif any(a.startswith("@modelcontextprotocol/") for a in short):
            hit = True
            reason = "argv-modelcontextprotocol-package"
        elif any("mcp-server" in a and len(a) < 240 for a in short):
            hit = True
            reason = "argv-mcp-server"
        if hit:
            exact.append(
                {
                    "pid": row["pid"],
                    "reason": reason,
                    "argv_head": argv[:6],
                }
            )
    home = Path.home()
    configs = {}
    for rel in (".mcp.json", ".claude.json", ".claude/settings.json"):
        path = home / rel
        configs[str(path)] = {
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
    repo_mcp = REPO / ".mcp.json"
    configs[str(repo_mcp)] = {
        "exists": repo_mcp.is_file(),
        "bytes": repo_mcp.stat().st_size if repo_mcp.is_file() else 0,
    }
    return {
        "proc_rows": len(rows),
        "naive_substring_mcp_pids": naive_mcp,
        "naive_substring_mcp_count": len(naive_mcp),
        "argv_exact_mcp_rows": exact,
        "argv_exact_mcp_count": len(exact),
        "configs": configs,
        "self_pid": os.getpid(),
        "self_in_naive_mcp": os.getpid() in naive_mcp,
    }


class ChildSet:
    def __init__(self) -> None:
        self.procs: list[subprocess.Popen] = []

    def add(self, proc: subprocess.Popen) -> subprocess.Popen:
        self.procs.append(proc)
        return proc

    def pids(self) -> list[int]:
        return [p.pid for p in self.procs if p.pid]

    def kill(self) -> None:
        kill_pids(self.pids())
        for p in self.procs:
            try:
                p.wait(timeout=1)
            except Exception:
                pass
        self.procs.clear()


def start_stop_delta() -> dict:
    reap_orphans()
    rows0 = iter_proc_argv()
    baseline = token_exact_pids(TOKEN_STDIO, rows0)
    naive_self = os.getpid() in naive_substring_pids("RES-0037", rows0)
    actual_self = os.getpid() in token_exact_pids(TOKEN_STDIO, rows0)
    self_argv = read_cmdline(os.getpid()) or sys.argv
    children = ChildSet()
    try:
        child = children.add(spawn_stdio("delta-session", "delta-server"))
        time.sleep(0.05)
        rows1 = iter_proc_argv()
        after_start = token_exact_pids(TOKEN_STDIO, rows1)
        naive_after = naive_substring_pids("RES-0037", rows1)
        child_argv = read_cmdline(child.pid) or []
        probe_in_child = is_this_probe_argv(child_argv)
        token_in_self = TOKEN_STDIO in (self_argv or [])
        expected_delta = 1
        observed_delta = len(after_start) - len(baseline)
        children.kill()
        time.sleep(0.08)
        rows2 = iter_proc_argv()
        after_stop = token_exact_pids(TOKEN_STDIO, rows2)
        stop_delta = len(after_stop) - len(baseline)
        return {
            "self_pid": os.getpid(),
            "self_argv": self_argv,
            "token": TOKEN_STDIO,
            "naive_pattern": "RES-0037",
            "naive_matcher_includes_probe": naive_self,
            "actual_matcher_includes_probe_before": actual_self,
            "actual_matcher_includes_probe_after_start": os.getpid()
            in token_exact_pids(TOKEN_STDIO, rows1),
            "token_present_on_probe_argv": token_in_self,
            "child_pid": child.pid,
            "child_argv": child_argv,
            "child_cmdline_is_probe_script": probe_in_child,
            "child_in_actual": child.pid in after_start,
            "child_in_naive_RES-0037": child.pid in naive_after,
            "baseline_count": len(baseline),
            "after_start_count": len(after_start),
            "after_stop_count": len(after_stop),
            "expected_start_delta": expected_delta,
            "observed_start_delta": observed_delta,
            "expected_stop_delta": 0,
            "observed_stop_delta": stop_delta,
            "pass": (
                naive_self is True
                and actual_self is False
                and token_in_self is False
                and probe_in_child is False
                and child.pid in after_start
                and observed_delta == expected_delta
                and stop_delta == 0
                and os.getpid() not in after_start
            ),
        }
    finally:
        children.kill()


def per_transport_counts() -> dict:
    reap_orphans()
    children = ChildSet()
    try:
        stdio_meta = []
        for s in range(N_SESSIONS):
            for srv in range(N_STDIO_SERVERS):
                proc = children.add(spawn_stdio(f"sess-{s}", f"srv-{srv}"))
                stdio_meta.append(
                    {"pid": proc.pid, "session": s, "server": srv, "fd": fd_count(proc.pid)}
                )
        http_proc, http_port = spawn_http("shared")
        children.add(http_proc)
        time.sleep(0.1)
        stdio_pids_procfs = token_exact_pids(TOKEN_STDIO)
        http_pids_procfs = token_exact_pids(TOKEN_HTTP)
        stdio_pids_ps = ps_token_pids(TOKEN_STDIO)
        http_pids_ps = ps_token_pids(TOKEN_HTTP)
        http_listen = listen_inodes(http_proc.pid)
        stdio_listen = []
        for row in stdio_meta:
            stdio_listen.extend(listen_inodes(row["pid"]))
        stdio_handles = {str(row["pid"]): fd_count(row["pid"]) for row in stdio_meta}
        http_handles = fd_count(http_proc.pid)
        expected_stdio = N_SESSIONS * N_STDIO_SERVERS
        expected_http = 1
        python_product = N_SESSIONS * N_STDIO_SERVERS
        expr_n = expr_product(N_SESSIONS, N_STDIO_SERVERS)
        rec_python = RECORDED_SESSIONS * RECORDED_SERVERS
        rec_expr = expr_product(RECORDED_SESSIONS, RECORDED_SERVERS)
        return {
            "sessions": N_SESSIONS,
            "stdio_servers_per_session": N_STDIO_SERVERS,
            "expected_stdio_processes": expected_stdio,
            "expected_http_processes": expected_http,
            "stdio_process_table": len(stdio_pids_procfs),
            "http_process_table": len(http_pids_procfs),
            "stdio_ps": len(stdio_pids_ps),
            "http_ps": len(http_pids_ps),
            "stdio_pids_procfs": stdio_pids_procfs,
            "http_pids_procfs": http_pids_procfs,
            "stdio_pids_ps": stdio_pids_ps,
            "http_pids_ps": http_pids_ps,
            "stdio_handle_counts": stdio_handles,
            "http_handle_count": http_handles,
            "http_listen_inodes": http_listen,
            "stdio_listen_inodes": stdio_listen,
            "http_port": http_port,
            "processes_per_stdio_server_per_session": (
                len(stdio_pids_procfs) / expected_stdio if expected_stdio else None
            ),
            "additional_http_processes_per_extra_session": 0,
            "python_sessions_times_servers": python_product,
            "expr_sessions_times_servers": expr_n,
            "recorded_sessions": RECORDED_SESSIONS,
            "recorded_servers": RECORDED_SERVERS,
            "recorded_claimed_processes": RECORDED_CLAIMED_PROCESSES,
            "recorded_python_product": rec_python,
            "recorded_expr_product": rec_expr,
            "recorded_equation_holds": rec_python == RECORDED_CLAIMED_PROCESSES,
            "pass": (
                len(stdio_pids_procfs) == expected_stdio
                and len(http_pids_procfs) == expected_http
                and stdio_pids_procfs == stdio_pids_ps
                and http_pids_procfs == http_pids_ps
                and python_product == expr_n == expected_stdio
                and rec_python == rec_expr
                and rec_python != RECORDED_CLAIMED_PROCESSES
                and len(http_listen) >= 1
                and len(stdio_listen) == 0
                and all(v >= 1 for v in stdio_handles.values())
                and http_handles >= 1
            ),
        }
    finally:
        children.kill()


def self_exclusion_with_decoy() -> dict:
    reap_orphans()
    children = ChildSet()
    try:
        decoy = children.add(_spawn(STDIO_SCRIPT, DECOY_TOKEN, ["probe1_self_exclusion_delta.py"]))
        if not wait_pid_token(decoy.pid, DECOY_TOKEN):
            raise RuntimeError("decoy never appeared")
        rows = iter_proc_argv()
        naive = naive_substring_pids("probe1_self_exclusion_delta.py", rows)
        actual_stdio = token_exact_pids(TOKEN_STDIO, rows)
        actual_decoy = token_exact_pids(DECOY_TOKEN, rows)
        return {
            "self_pid": os.getpid(),
            "decoy_pid": decoy.pid,
            "naive_probe1_name_hits": naive,
            "naive_includes_self": os.getpid() in naive,
            "naive_includes_decoy": decoy.pid in naive,
            "stdio_token_hits": actual_stdio,
            "decoy_token_hits": actual_decoy,
            "stdio_token_ignores_decoy": decoy.pid not in actual_stdio,
            "pass": (
                os.getpid() in naive
                and decoy.pid in naive
                and decoy.pid in actual_decoy
                and decoy.pid not in actual_stdio
                and os.getpid() not in actual_stdio
                and os.getpid() not in actual_decoy
            ),
        }
    finally:
        children.kill()
