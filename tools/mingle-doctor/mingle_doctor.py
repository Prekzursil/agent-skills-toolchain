#!/usr/bin/env python3
"""mingle_doctor.py -- health + auto-heal for the Claude<->Codex mingle rails.

Runs five checks IN ORDER, printing a terminal-state marker per check
(SUCCESS:<id> / FAILED:<id> / WARN:<id>), auto-healing where it can:

  (a) codex-mcp        -- `claude mcp get codex` == Connected
  (b) codex-auth       -- ~/.codex/auth.json access-token JWT freshness (never prints token)
  (c) agent-mail       -- canonical port 8812 /health OK, else auto-start + re-check
  (d) port-agreement   -- agent-mail url in ~/.claude.json AND ~/.codex/config.toml
                          both present, agree, and == 8812 (catches the split-brain)
  (e) codex-roundtrip  -- trivial lean `codex exec` round-trip (90s cap)

Exit code == number of FAILED checks (WARN does not count).

Ground truth this is built against (Windows 11, 2026-07):
  * canonical agent-mail port = 8812 (8765=basic-memory LIVE, 8810 dead, 8811 stale)
  * agent-mail install: ~/.local/opt/mcp_agent_mail  (uv run python -m mcp_agent_mail.cli serve-http)
  * lean codex exec (mcp_servers={} + danger-full-access) returns ~30s; heavy MCP nesting hangs 600s
  * `codex auth status` is NOT a real subcommand -- freshness comes from auth.json JWT exp
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

HOME = Path(os.path.expanduser("~"))
CLAUDE_JSON = HOME / ".claude.json"
CODEX_CONFIG = HOME / ".codex" / "config.toml"
CODEX_AUTH = HOME / ".codex" / "auth.json"

AGENT_MAIL_HOST = "127.0.0.1"
CANONICAL_PORT = 8812
AGENT_MAIL_INSTALL = HOME / ".local" / "opt" / "mcp_agent_mail"

SCRIPT_DIR = Path(__file__).resolve().parent
SUPERVISOR_DIR = SCRIPT_DIR.parent / "supervisor"  # Component B lives here

_RESULTS: list[bool] = []  # True == pass/warn, False == fail (drives exit code)


def _exe(name: str) -> str:
    """Resolve a command through PATH/PATHEXT so Windows npm .cmd shims work under subprocess."""
    return shutil.which(name) or name


def emit(ok: bool, cid: str, msg: str, level: str = "") -> bool:
    """Print a terminal-state marker and record pass/fail for the exit code."""
    tag = level or ("SUCCESS" if ok else "FAILED")
    print(f"{tag}:{cid} {msg}")
    _RESULTS.append(ok)
    return ok


# --------------------------------------------------------------------------- #
# (a) codex MCP mount
# --------------------------------------------------------------------------- #
def check_codex_mcp() -> None:
    try:
        r = subprocess.run(
            [_exe("claude"), "mcp", "get", "codex"],
            capture_output=True, text=True, timeout=45,
        )
    except FileNotFoundError:
        emit(False, "codex-mcp", "'claude' CLI not on PATH -- cannot verify codex mount")
        return
    except Exception as e:  # noqa: BLE001
        emit(False, "codex-mcp", f"could not run 'claude mcp get codex': {e}")
        return

    out = f"{r.stdout or ''}\n{r.stderr or ''}".lower()
    if "connected" in out and "failed to connect" not in out:
        emit(True, "codex-mcp", "codex MCP mounted and Connected")
        return

    remount = ("remount: `claude mcp remove codex -s user` then "
               "`claude mcp add --scope user codex -- codex mcp-server`")
    emit(False, "codex-mcp",
         "codex MCP not Connected. Common cause: the [mcp_servers.github] `url` "
         "(url is not supported for stdio) breaks `codex mcp-server` config load -- "
         f"fix/disable that entry, then {remount}")


# --------------------------------------------------------------------------- #
# (b) codex auth freshness (JWT exp -- never prints the token)
# --------------------------------------------------------------------------- #
def _b64url_json(seg: str) -> dict:
    seg += "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg.encode("ascii")))


def check_codex_auth() -> None:
    if not CODEX_AUTH.exists():
        emit(False, "codex-auth", f"{CODEX_AUTH} not found -- run `codex login`")
        return
    try:
        data = json.loads(CODEX_AUTH.read_text(encoding="utf-8"))
        toks = data.get("tokens") or {}
        jwt = toks.get("access_token") or toks.get("id_token")
        if not jwt or jwt.count(".") < 2:
            emit(False, "codex-auth", "no JWT access_token in auth.json -- run `codex login`")
            return
        payload = _b64url_json(jwt.split(".")[1])
    except Exception as e:  # noqa: BLE001
        emit(False, "codex-auth", f"failed to parse auth.json: {e}")
        return

    exp = payload.get("exp")
    if not exp:
        emit(True, "codex-auth", "token present but has no 'exp' claim -- cannot assert expiry",
             level="WARN")
        return

    now = time.time()
    hrs = (exp - now) / 3600.0
    exp_utc = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
    if exp <= now:
        emit(False, "codex-auth", f"access token EXPIRED at {exp_utc} -- run `codex login`")
    elif hrs < 24:
        emit(True, "codex-auth",
             f"token valid but expires in {hrs:.1f}h ({exp_utc}) -- refresh soon", level="WARN")
    else:
        emit(True, "codex-auth", f"token valid, expires {exp_utc} ({hrs:.1f}h remaining)")


# --------------------------------------------------------------------------- #
# (c) agent-mail health + auto-heal
# --------------------------------------------------------------------------- #
def http_health(port: int, timeout: float = 4.0):
    url = f"http://{AGENT_MAIL_HOST}:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200, resp.status
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001  (connection refused, timeout, etc.)
        return False, type(e).__name__


def _launch_detached(cmd, cwd=None, shell=False) -> None:
    kwargs = dict(cwd=cwd, stdin=subprocess.DEVNULL,
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=shell)
    if os.name == "nt":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP -> survives this process exit
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)


def _find_supervisor():
    """Locate the Component-B supervisor. Returns (kind, spec) or None."""
    env = os.environ.get("MINGLE_SUPERVISOR_CMD")
    if env:
        return ("shell", env)
    if SUPERVISOR_DIR.is_dir():
        for name in ("mingle_supervisor.py", "supervisor.py",
                     "agent_mail_supervisor.py", "mingle-supervisor.py"):
            p = SUPERVISOR_DIR / name
            if p.exists():
                return ("python", str(p))
        for name in ("mingle_supervisor.ps1", "supervisor.ps1", "start.ps1"):
            p = SUPERVISOR_DIR / name
            if p.exists():
                return ("pwsh", str(p))
    return None


def _start_agent_mail():
    """Best-effort start. Prefer Component-B supervisor; fall back to direct uv start.
    Returns a human description of what was launched, or None if nothing could be run."""
    sup = _find_supervisor()
    if sup:
        kind, spec = sup
        if kind == "python":
            _launch_detached([sys.executable, spec, "start"])
        elif kind == "pwsh":
            _launch_detached([_exe("pwsh"), "-NoProfile", "-File", spec])
        else:  # shell
            _launch_detached(spec, shell=True)
        return f"supervisor ({spec})"

    # Fallback: direct ground-truth uv start (bind loopback only)
    if not AGENT_MAIL_INSTALL.is_dir():
        return None
    cmd = [_exe("uv"), "run", "python", "-m", "mcp_agent_mail.cli", "serve-http",
           "--host", AGENT_MAIL_HOST, "--port", str(CANONICAL_PORT)]
    try:
        _launch_detached(cmd, cwd=str(AGENT_MAIL_INSTALL))
    except FileNotFoundError:
        return None
    return f"direct uv serve-http --port {CANONICAL_PORT} in {AGENT_MAIL_INSTALL}"


def check_agent_mail(heal: bool = True) -> None:
    ok, code = http_health(CANONICAL_PORT)
    if ok:
        emit(True, "agent-mail", f"/health OK on {CANONICAL_PORT}")
        return
    if not heal:
        emit(False, "agent-mail", f"DOWN on {CANONICAL_PORT} ({code}); --no-heal set")
        return

    launched = _start_agent_mail()
    if launched is None:
        emit(False, "agent-mail",
             f"DOWN on {CANONICAL_PORT} ({code}); no Component-B supervisor found under "
             f"{SUPERVISOR_DIR} and no runnable install at {AGENT_MAIL_INSTALL} -- cannot auto-heal")
        return

    for _ in range(20):  # ~20s, under the 60s longrun threshold
        time.sleep(1)
        ok, code = http_health(CANONICAL_PORT)
        if ok:
            break
    if ok:
        emit(True, "agent-mail",
             f"was DOWN; auto-healed via {launched}; /health now OK on {CANONICAL_PORT}")
    else:
        emit(False, "agent-mail",
             f"DOWN on {CANONICAL_PORT}; attempted heal via {launched} but /health still failing ({code})")


# --------------------------------------------------------------------------- #
# (d) port agreement between the two configs
# --------------------------------------------------------------------------- #
def _port_of(url) -> int | None:
    if not url:
        return None
    m = re.search(r"://[^/]*?:(\d{2,5})", url) or re.search(r":(\d{2,5})", url)
    return int(m.group(1)) if m else None


def _find_agentmail_url(obj):
    """Recursively find an 'agent-mail'/'agent_mail' entry carrying a url (for .claude.json)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("agent-mail", "agent_mail", "agentmail") and isinstance(v, dict) and v.get("url"):
                return v["url"]
        for v in obj.values():
            found = _find_agentmail_url(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_agentmail_url(v)
            if found:
                return found
    return None


def _codex_agentmail_port():
    """Return (port|None, note) for the agent-mail mcp_server in codex config.toml."""
    if tomllib is None:
        return None, "tomllib unavailable"
    if not CODEX_CONFIG.exists():
        return None, f"{CODEX_CONFIG} missing"
    try:
        data = tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return None, f"parse error: {e}"
    servers = data.get("mcp_servers", {})
    for name in ("agent-mail", "agent_mail", "agentmail"):
        s = servers.get(name)
        if isinstance(s, dict):
            if s.get("url"):
                return _port_of(s["url"]), f"[mcp_servers.{name}].url"
            # scan url-in-args and env values for a host:port
            blob = " ".join(str(x) for x in (s.get("args") or [])) + " " + \
                   " ".join(str(v) for v in (s.get("env") or {}).values())
            p = _port_of(blob)
            if p:
                return p, f"[mcp_servers.{name}] args/env"
            return None, f"[mcp_servers.{name}] present but no port found"
    return None, "no [mcp_servers.agent-mail] section"


def check_port_agreement() -> None:
    # Claude side
    claude_port = None
    claude_note = ""
    try:
        cj = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
        url = _find_agentmail_url(cj)
        claude_port = _port_of(url)
        claude_note = url or "no agent-mail entry"
    except Exception as e:  # noqa: BLE001
        emit(False, "port-agreement", f"could not read {CLAUDE_JSON}: {e}")
        return

    # Codex side
    codex_port, codex_note = _codex_agentmail_port()

    problems = []
    if claude_port is None:
        problems.append(f".claude.json: no agent-mail port ({claude_note})")
    elif claude_port != CANONICAL_PORT:
        problems.append(f".claude.json agent-mail port={claude_port} != {CANONICAL_PORT} ({claude_note})")
    if codex_port is None:
        problems.append(f".codex/config.toml: {codex_note}")
    elif codex_port != CANONICAL_PORT:
        problems.append(f".codex/config.toml agent-mail port={codex_port} != {CANONICAL_PORT} ({codex_note})")
    if claude_port and codex_port and claude_port != codex_port:
        problems.append(f"SPLIT-BRAIN: claude={claude_port} vs codex={codex_port}")

    if problems:
        emit(False, "port-agreement", " | ".join(problems))
    else:
        emit(True, "port-agreement", f"both configs agree on canonical port {CANONICAL_PORT}")


# --------------------------------------------------------------------------- #
# (e) trivial lean codex round-trip
# --------------------------------------------------------------------------- #
def check_codex_roundtrip(timeout: int = 90) -> None:
    # Lean invocation: empty MCP fleet + danger-full-access (read-only/workspace-write
    # sandboxes are broken on Windows). Heavy nested MCPs are what cause the 600s hang.
    cmd = [_exe("codex"), "exec",
           "--skip-git-repo-check",  # doctor may run from a non-git dir (e.g. scratchpad)
           "-c", "mcp_servers={}",
           "-c", 'sandbox_mode="danger-full-access"',
           "say doctor-ok"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        emit(False, "codex-roundtrip",
             f"`codex exec` timed out (>{timeout}s) -- heavy MCP nesting? confirm the lean mount")
        return
    except FileNotFoundError:
        emit(False, "codex-roundtrip", "`codex` CLI not on PATH")
        return
    except Exception as e:  # noqa: BLE001
        emit(False, "codex-roundtrip", f"`codex exec` error: {e}")
        return

    if r.returncode == 0:
        tail = " ".join((r.stdout or "").split())[-140:]
        emit(True, "codex-roundtrip", f"`codex exec` OK (exit 0); tail: {tail!r}")
    else:
        err = " ".join((r.stderr or r.stdout or "").split())[-180:]
        emit(False, "codex-roundtrip", f"`codex exec` failed (exit {r.returncode}): {err}")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="mingle rails health + auto-heal")
    ap.add_argument("--no-heal", action="store_true",
                    help="diagnostics only; do not auto-start agent-mail")
    ap.add_argument("--roundtrip-timeout", type=int, default=90,
                    help="seconds for the codex exec round-trip (default 90)")
    args = ap.parse_args()

    print("== mingle_doctor ==  (canonical agent-mail port = %d)" % CANONICAL_PORT)
    check_codex_mcp()
    check_codex_auth()
    check_agent_mail(heal=not args.no_heal)
    check_port_agreement()
    check_codex_roundtrip(timeout=args.roundtrip_timeout)

    failed = _RESULTS.count(False)
    total = len(_RESULTS)
    print(f"\n{failed} FAILED / {total} checks. exit={failed}")
    return failed


if __name__ == "__main__":
    sys.exit(main())
