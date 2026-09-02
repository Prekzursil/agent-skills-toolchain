"""Two-signal load detector vs naive config-only walker."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

# Distinctive argv token for the process-table reviewer control. Must not
# collide with cursor-agent binary paths so a remesure sandbox that cannot
# see the outer session still has a live /proc row to re-enumerate.
PROC_REVIEW_TOKEN = "ADV0139_PROC_REVIEW"


def iter_proc_cmdlines() -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return rows
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        cmd = raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
        if cmd:
            rows.append((int(entry.name), cmd))
    return rows


def proc_cwd(pid: int) -> str:
    try:
        return str(Path(f"/proc/{pid}/cwd").resolve())
    except OSError:
        return ""


def is_agent_binary_cmd(cmd: str) -> bool:
    """True when argv0 is the cursor-agent CLI or its node runtime.

    Prompt text on the live agent often quotes this unit's probe paths;
    substring matching those paths would hide the real agent.
    """
    if not cmd or PROC_REVIEW_TOKEN in cmd or "ADV0139_LOADED_BEACON" in cmd:
        return False
    first = cmd.split()[0]
    if first.endswith("/agent") or first == "agent":
        return True
    if first.endswith("/node") and "cursor-agent" in cmd:
        return True
    return False


def proc_on_workspace(pid: int, cmd: str, ws: str | None = None) -> bool:
    """Workspace affinity from argv *or* cwd (cmdline is often truncated)."""
    ws = ws or str(C.REPO)
    if ws in cmd:
        return True
    cwd = proc_cwd(pid)
    if not cwd:
        return False
    return cwd == ws or cwd.startswith(ws + os.sep)


def workspace_agent_rows(
    rows: list[tuple[int, str]] | None = None,
) -> list[dict]:
    rows = rows if rows is not None else iter_proc_cmdlines()
    out: list[dict] = []
    for pid, cmd in rows:
        if not is_agent_binary_cmd(cmd):
            continue
        out.append(
            {
                "pid": pid,
                "has_workspace": proc_on_workspace(pid, cmd),
                "cwd": proc_cwd(pid),
            }
        )
    return out


@contextmanager
def proc_table_control() -> Iterator[tuple[str, int]]:
    """Spawn a live /proc row this probe must re-find (settings-file independent)."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import sys,time;"
                f"sys.argv[0]={PROC_REVIEW_TOKEN!r};"
                "print('proc-review-up', flush=True);"
                "time.sleep(90)"
            ),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=str(C.REPO),
    )
    try:
        deadline = time.time() + 2.0
        while time.time() < deadline:
            rows = iter_proc_cmdlines()
            if any(
                pid == child.pid and PROC_REVIEW_TOKEN in cmd for pid, cmd in rows
            ):
                break
            time.sleep(0.05)
        yield PROC_REVIEW_TOKEN, child.pid
    finally:
        child.kill()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.terminate()


def process_has(token: str, rows: list[tuple[int, str]] | None = None) -> tuple[bool, str]:
    rows = rows if rows is not None else iter_proc_cmdlines()
    hits = [(pid, cmd) for pid, cmd in rows if token in cmd]
    if not hits:
        return False, f"no process cmdline contains {token}"
    pid, cmd = hits[0]
    return True, f"pid={pid} cmdline_has={token}"


def parse_mcp_servers(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(doc, dict):
        return {}
    servers = doc.get("mcpServers") or doc.get("mcp") or {}
    if not isinstance(servers, dict):
        return {}
    return {str(k): v for k, v in servers.items() if isinstance(v, dict)}


def valid_scope_mcp(workspace: Path) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for rel in ("mcp.json", ".mcp.json", ".cursor/mcp.json"):
        merged.update(parse_mcp_servers(workspace / rel))
    return merged


def naive_all_mcp_names(root: Path) -> set[str]:
    names: set[str] = set()
    for path in root.rglob("mcp.json"):
        names.update(parse_mcp_servers(path).keys())
    for path in root.rglob(".mcp.json"):
        names.update(parse_mcp_servers(path).keys())
    return names


def server_enabled(spec: dict) -> bool:
    if spec.get("disabled") is True:
        return False
    if spec.get("enabled") is False:
        return False
    return True


def two_signal_mcp(
    name: str,
    workspace: Path,
    beacon_token: str | None,
    rows: list[tuple[int, str]] | None = None,
) -> dict:
    cfg = valid_scope_mcp(workspace)
    in_cfg = name in cfg
    enabled = in_cfg and server_enabled(cfg[name])
    token = beacon_token or name
    proc_hit, proc_sum = process_has(token, rows)
    signals = [
        {
            "kind": "config",
            "observed": bool(enabled),
            "summary": (
                f"workspace={workspace} name={name} in_valid_scope={in_cfg} "
                f"enabled={enabled}"
            ),
        },
        {
            "kind": "process",
            "observed": proc_hit,
            "summary": proc_sum,
        },
    ]
    if enabled and proc_hit:
        verdict = "LOADED"
    elif (not enabled) and (not proc_hit):
        verdict = "NOT-LOADED"
    else:
        verdict = "UNKNOWN-CAPABILITY"
    return {
        "name": name,
        "verdict": verdict,
        "load_signals": signals,
        "config_enabled": enabled,
        "process_observed": proc_hit,
    }


def naive_verdict(name: str, names: set[str]) -> str:
    return "LOADED" if name in names else "NOT-LOADED"


def run_fixture_control() -> dict:
    """Known-loaded beacon vs known-disabled / wrong-scope shadow."""
    ws = C.FIXTURE_WS
    tree = ws.parent
    naive_names = naive_all_mcp_names(tree)
    rows_before = iter_proc_cmdlines()
    # Spawn a live beacon whose argv token is not a path substring of ADV-0139.
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import sys,time;"
                f"sys.argv[0]={C.BEACON!r};"
                "print('beacon-up', flush=True);"
                "time.sleep(90)"
            ),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        time.sleep(0.15)
        rows = iter_proc_cmdlines()
        live = two_signal_mcp("adv0139-live", ws, C.BEACON, rows)
        disabled = two_signal_mcp("adv0139-disabled", ws, "ADV0139_DISABLED_BEACON", rows)
        shadow = two_signal_mcp("adv0139-shadow", ws, "ADV0139_SHADOW_BEACON", rows)
        naive_live = naive_verdict("adv0139-live", naive_names)
        naive_disabled = naive_verdict("adv0139-disabled", naive_names)
        naive_shadow = naive_verdict("adv0139-shadow", naive_names)
        # Naive treats disabled and wrong-scope-enabled as loaded because both
        # names appear in some mcp.json. Two-signal must not.
        naive_collapsed = naive_live == naive_disabled == "LOADED"
        separated = live["verdict"] == "LOADED" and disabled["verdict"] == "NOT-LOADED"
        shadow_not_loaded = shadow["verdict"] == "NOT-LOADED"
        naive_shadow_false_load = naive_shadow == "LOADED"
        return {
            "known_loaded": {"name": "adv0139-live", "verdict": live["verdict"]},
            "known_disabled": {
                "name": "adv0139-disabled",
                "verdict": disabled["verdict"],
            },
            "wrong_scope": {
                "name": "adv0139-shadow",
                "verdict": shadow["verdict"],
                "naive_verdict": naive_shadow,
            },
            "live": live,
            "disabled": disabled,
            "shadow": shadow,
            "naive": {
                "names": sorted(naive_names),
                "adv0139-live": naive_live,
                "adv0139-disabled": naive_disabled,
                "adv0139-shadow": naive_shadow,
            },
            "naive_collapsed": naive_collapsed and naive_shadow_false_load,
            "two_signal_separated": separated and shadow_not_loaded,
            "beacon_pid": child.pid,
            "proc_count_before": len(rows_before),
            "proc_count_during": len(rows),
        }
    finally:
        child.kill()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.terminate()
