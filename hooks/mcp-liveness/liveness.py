#!/usr/bin/env python3
r"""MCP-LIVENESS SELF-HEAL + ALERT — the keystone fix for the silent memory loss.

THE problem this solves: basic-memory's shared HTTP daemon (127.0.0.1:8765) can
die mid-session; the agent then keeps "saving" to a dead store and SILENTLY loses
hours of memory (the documented 4h loss). This hook makes the agent NEVER proceed
silently with a dead memory store:

  * SessionStart  -> always probe basic-memory (the resume-after-hours case).
  * PreToolUse    -> probe before basic-memory tool calls, THROTTLED ~60s so rapid
                     successive memory ops don't each re-probe.
  If a critical MCP is DOWN (or dead-but-listening — TCP up, MCP handshake fails):
    (a) attempt an AUTO-RESTART (basic-memory via restart-basic-memory.ps1, launched
        DETACHED so this hook never blocks), and
    (b) INJECT a LOUD additionalContext alert telling the agent memory is NOT being
        saved and to verify before relying on recall.

Liveness == a REAL MCP handshake (socket + JSON-RPC `initialize`), not just a port
being open — mirrors mcp_doctor's _mcp_handshake_ok so a dead-but-listening corpse
is caught. We deliberately do NOT call search_notes (it triggers a ~7s embed-model
load); `initialize` answers in well under a second.

BUT a handshake alone is monitoring the PROMISE, not the capability: an init-only
listener, or a DIFFERENT MCP server that grabbed :8765, answers `initialize` and is
then reported "up" while the memory tools do not exist. So the initialize RESULT is
also asserted to advertise a `tools` capability (`serves_tools`) — free, same
request, no extra round-trip and no embed-model load. That assertion is
one-directional: only a decoded result whose `capabilities` map lacks `tools`
demotes the verdict to dead-listening. An undecodable body or a streamable-http
session status (400/405/...) is INCONCLUSIVE and stays "up", so the added check can
never manufacture a false DOWN. Per-server opt-out: `"require_tools": false`.
NOT covered, and deliberately so: a write/read canary proving a DURABLE memory
transaction — that has a side effect on the vault on every session start, so it is
an owner decision, not a silent addition here.

re-harness RE daemons (IDA/Ghidra/...) are checked ONLY when registered in the
harness registry (so no noise when not doing RE) and are REPORT-ONLY (restart hint,
never auto-killed here).

DESIGN CONTRACT (AGENTS.md s6): FAIL-OPEN. Every path is wrapped; ANY error -> exit 0,
emit nothing. Inject-only (never blocks). Opt-out: MCP_LIVENESS=off or a .disabled file.

Usage (wired in settings.json):
  python liveness.py sessionstart   # SessionStart hook
  python liveness.py pretool        # PreToolUse(mcp__basic-memory__.*) hook
  python liveness.py probe          # CLI: print status JSON + SUCCESS/FAILED marker (testing)
  python liveness.py --mode all     # CLI: the report-only probe ladder L0-L5 (below)

THE PROBE LADDER (`--mode all`, D12 / WU-12) is NOT a hook: it never injects, never
restarts, never writes to either registry, and ignores the hook opt-out because it is
run on purpose (daily task or owner). Report-only: exit 0 whatever it finds; exit 2
only for misuse or a bug. Rungs, each `{status, items, duration_ms}`:

  L0 static     every ENABLED stdio server in .agents/agents.json: each arg under the
                owner-box toolchain prefix (plus the `--directory` operand and every
                .py/.js/.mjs/.ps1 arg) must exist under --root (the repo).
  L1 initialize the existing handshake probe (probe_critical) over critical.json plus
                every ENABLED loopback `http` MCP row in agents.json; hosted MCP rows are
                credentialed and owner-run, so they are not probed here.
  L2 tools/list `toolDigest` = sha256 over the sorted `name|description` lines, pinned
                in state/tool-digests.json; drift -> `changed` + `quarantine-candidate`.
                The pin only ever moves by a human edit (delete the row to re-pin).
  L3 /v1/models GET (or `health.path`) for every ENABLED loopback endpoint in
                .agents/models.json; hosted -> `skipped` `hosted:owner-run`.
  L4 one token  ONLY with --allow-inference, ONLY for a `declared` completions wire,
                never with a credential; the report never carries the prompt, a header
                or a response body.
  L5 mcp-scan   `mcp-scan --local-only --json` when mcp-scan (or uvx) is on PATH, else
                `skipped`.

Network goes through the module-level `http_get` / `http_post` so tests inject fakes.
`command-center/ssot/capability_score.py` folds the report into the score sidecar.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

THIS = Path(__file__).resolve().parent
CONFIG_PATH = THIS / "critical.json"
DISABLED = THIS / ".disabled"

# Per-session liveness state (throttle + alert dedup). Override for tests.
STATE_DIR = Path(
    os.environ.get(
        "MCP_LIVENESS_STATE_DIR",
        str(Path(os.environ.get("TEMP", "/tmp")) / "mcp-liveness"),
    )
)

# Streamable-HTTP handshake codes: the server IS serving MCP but wants a session /
# different content negotiation (NOT a generic 404/501 "nothing here"). Mirrors
# re-harness lib/mcp_doctor_core._mcp_handshake_ok.
_HANDSHAKE_CODES = {400, 405, 406, 409, 415, 426}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config() -> dict[str, Any]:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except Exception:
        # Hard-coded minimal fallback so the keystone still works if the JSON is gone.
        return {
            "throttle_seconds": 60,
            "handshake_timeout": 5.0,
            "tcp_timeout": 1.5,
            "critical": {
                "basic-memory": {
                    "url": "http://127.0.0.1:8765/mcp",
                    "host": "127.0.0.1",
                    "port": 8765,
                    "auto_restart": True,
                    "restart_helper": "restart-basic-memory.ps1",
                    "why": "semantic memory vault",
                }
            },
            "reharness": {
                "registry": "",
                "auto_restart": False,
                "restart_hint": "re_launch.py",
            },
        }


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------
def tcp_up(host: str, port: int, timeout: float) -> bool:
    """True iff a TCP connection to host:port is accepted within `timeout`."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def mcp_handshake(url: str, timeout: float) -> bool | None:
    """Does the endpoint complete a minimal MCP `initialize` handshake?

    Returns True  -> server answered MCP (JSON-RPC result/error, SSE, or a
                     streamable-http session-handshake status).
            False -> TCP answered but it is NOT MCP (dead-but-listening corpse).
            None  -> unreachable.
    """
    return handshake_detail(url, timeout)[0]


def handshake_detail(
    url: str, timeout: float
) -> tuple[bool | None, dict[str, Any] | None]:
    """`mcp_handshake` plus the decoded JSON-RPC object, for semantic checks.

    Returns ``(spoke_mcp, obj)`` where ``spoke_mcp`` is the tri-state above and
    ``obj`` is the parsed initialize response when one could be decoded, else None.
    A caller must treat ``obj is None`` as INCONCLUSIVE (see ``serves_tools``) —
    a streamable-http session handshake answers 400/405 with no body at all.
    """
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-liveness", "version": "1.0"},
            },
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- internal MCP liveness probe; URL from local config, not untrusted user data
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return (True, None) if exc.code in _HANDSHAKE_CODES else (False, None)
    except (urllib.error.URLError, OSError, socket.timeout):
        return None, None
    except Exception:
        # Malformed/non-HTTP response from a corpse on the port -> TCP is up but
        # this does not speak MCP. Caller (TCP already confirmed up) reads None as
        # dead-but-listening, which is the correct classification.
        return None, None
    # Parse application/json or SSE ("data: {json}")
    try:
        obj = None
        for line in body.splitlines():
            s = line.strip()
            if s.startswith("data:"):
                obj = json.loads(s[5:].strip())
                break
        if obj is None:
            obj = json.loads(body)
        spoke = isinstance(obj, dict) and ("result" in obj or "error" in obj)
        return spoke, (obj if isinstance(obj, dict) else None)
    except Exception:
        # Server answered with a body but it isn't JSON-RPC — still "spoke" over MCP.
        return True, None


def serves_tools(obj: Any, spec: dict[str, Any]) -> tuple[bool, str]:
    """Did the initialize RESULT prove this server actually exposes tools?

    "TCP is up and it answered initialize" does NOT establish that the endpoint is
    the tool-serving keystone: an init-only listener, or a DIFFERENT MCP server that
    grabbed the port, answers initialize happily and then has no tool surface at all
    — the false green this guard exists to kill.

    Only a POSITIVE contradiction demotes the verdict. An absent/undecodable body,
    or a result that carries no ``capabilities`` map, is INCONCLUSIVE and stays "up"
    so a streamable-http session handshake can never manufacture a false DOWN.

    Returns ``(ok, why_not)``.
    """
    if not spec.get("require_tools", True):
        return True, ""
    if not isinstance(obj, dict):
        return True, ""
    result = obj.get("result")
    if not isinstance(result, dict):
        return True, ""
    caps = result.get("capabilities")
    if not isinstance(caps, dict):
        return True, ""
    if "tools" in caps:
        return True, ""
    info = result.get("serverInfo")
    who = ""
    if isinstance(info, dict) and info.get("name"):
        who = f" (serverInfo.name={str(info['name'])!r})"
    return False, f"handshake advertises NO `tools` capability{who}"


def probe_critical(
    name: str, spec: dict[str, Any], cfg: dict[str, Any]
) -> dict[str, Any]:
    """Probe one critical server -> {name, state in up|down|dead-listening, ...}."""
    host = spec.get("host", "127.0.0.1")
    port = int(spec.get("port", 0))
    url = spec.get("url", "")
    tcp_t = float(cfg.get("tcp_timeout", 1.5))
    hs_t = float(cfg.get("handshake_timeout", 5.0))

    if not tcp_up(host, port, tcp_t):
        return {
            "name": name,
            "state": "down",
            "tcp": False,
            "mcp_ok": None,
            "url": url,
            "why": spec.get("why", ""),
        }
    hs, obj = handshake_detail(url, hs_t)
    tools_ok, mismatch = serves_tools(obj, spec) if hs else (False, "")
    state = "up" if (hs and tools_ok) else "dead-listening"
    return {
        "name": name,
        "state": state,
        "tcp": True,
        "mcp_ok": bool(hs),
        "tools_ok": bool(hs) and tools_ok,
        "mismatch": mismatch,
        "url": url,
        "why": spec.get("why", ""),
    }


def probe_reharness(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Probe re-harness RE daemons ONLY if registered (registry tools non-empty).

    Report-only: returns the list of registered-but-down daemons (never restarted
    here — RE daemons are heavy/context-specific; we just surface a hint).
    """
    rh = cfg.get("reharness") or {}
    reg_path = rh.get("registry") or ""
    if not reg_path:
        return []
    try:
        reg = json.loads(Path(reg_path).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    tools = (reg or {}).get("tools") or {}
    if not tools:
        return []  # nothing registered -> not doing RE -> silent
    down: list[dict[str, Any]] = []
    tcp_t = float(cfg.get("tcp_timeout", 1.5))
    for tool, info in tools.items():
        try:
            port = int((info or {}).get("port") or 0)
        except Exception:
            port = 0
        if not port:
            continue
        if not tcp_up("127.0.0.1", port, tcp_t):
            down.append({"name": f"re:{tool}", "port": port, "state": "down"})
    return down


# ---------------------------------------------------------------------------
# State (throttle + alert dedup), per session
# ---------------------------------------------------------------------------
def _state_file(sid: str) -> Path:
    safe = (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in str(sid))[:80]
        or "default"
    )
    return STATE_DIR / f"{safe}.json"


def load_state(sid: str) -> dict[str, Any]:
    try:
        return json.loads(_state_file(sid).read_text(encoding="utf-8"))
    except Exception:
        return {
            "last_check": 0.0,
            "last_state": "unknown",
            "alerted_down": False,
            "restart_attempted": False,
        }


def save_state(sid: str, st: dict[str, Any]) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_file(sid).write_text(json.dumps(st), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Restart (detached — never blocks the hook)
# ---------------------------------------------------------------------------
def attempt_restart(spec: dict[str, Any], dead_listening: bool) -> bool:
    """Launch the basic-memory restart helper DETACHED. Returns True if launched."""
    helper = spec.get("restart_helper")
    if not helper:
        return False
    ps1 = THIS / helper
    if not ps1.exists():
        return False
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)]
    if dead_listening:
        args += ["-KillCorpse"]
    try:
        flags = 0
        if os.name == "nt":
            # NOTE: do NOT add DETACHED_PROCESS here — on Windows it prevents the
            # powershell child from actually executing (verified: marker never
            # written). CREATE_NEW_PROCESS_GROUP keeps the child alive after this
            # short-lived hook exits; CREATE_NO_WINDOW hides the console flash.
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200) | getattr(
                subprocess, "CREATE_NO_WINDOW", 0x08000000
            )
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Alert formatting
# ---------------------------------------------------------------------------
def format_alert(
    down: list[dict[str, Any]], reharness_down: list[dict[str, Any]], restarted: bool
) -> str:
    parts: list[str] = []
    for d in down:
        if d["name"] == "basic-memory":
            if d["state"] == "down":
                verb = "DOWN"
            elif d.get("mismatch"):
                # Handshake succeeded but the endpoint has no tool surface: the
                # false-green case. Name it, or the operator hunts a crash that
                # never happened.
                verb = f"WRONG SERVER on the port - {d['mismatch']}"
            else:
                verb = "DEAD-but-LISTENING (corpse on the port)"
            parts.append(
                f"WARNING: basic-memory {verb} - memory is NOT being saved and "
                f"recall is UNRELIABLE. "
                + (
                    "Auto-restart attempted - VERIFY (call a basic-memory tool) before "
                    "relying on recall, and re-save anything important. "
                    if restarted
                    else "Auto-restart could NOT be launched - start it manually: "
                    "Start-ScheduledTask -TaskName BasicMemory-HTTP-MCP. "
                )
            )
        else:
            parts.append(f"WARNING: critical MCP '{d['name']}' is {d['state']}.")
    if reharness_down:
        names = ", ".join(f"{r['name']}(:{r['port']})" for r in reharness_down)
        parts.append(
            f"RE daemon(s) registered but DOWN: {names}. "
            f"Restart via re_launch.py before relying on RE MCP calls."
        )
    return "[mcp-liveness] " + " ".join(parts)


def emit(event_name: str, msg: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": msg,
                }
            }
        )
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(mode: str, data: dict[str, Any]) -> int:
    cfg = load_config()
    sid = str(data.get("session_id") or "default")
    now = time.time()
    st = load_state(sid)
    throttle = float(cfg.get("throttle_seconds", 60))

    # PreToolUse fast-path: if we very recently saw the keystone UP, skip the probe.
    if mode == "pretool":
        if (
            now - float(st.get("last_check", 0)) < throttle
            and st.get("last_state") == "up"
        ):
            return 0

    critical = cfg.get("critical") or {}
    results = [probe_critical(name, spec, cfg) for name, spec in critical.items()]
    down = [r for r in results if r["state"] != "up"]
    reharness_down = probe_reharness(cfg)

    if not down and not reharness_down:
        save_state(
            sid,
            {
                "last_check": now,
                "last_state": "up",
                "alerted_down": False,
                "restart_attempted": False,
            },
        )
        return 0  # healthy -> silent

    # Something critical is down. Auto-restart (once per down-episode) + alert.
    restarted = bool(st.get("restart_attempted"))
    if not st.get("restart_attempted"):
        for r in down:
            spec = critical.get(r["name"], {})
            if spec.get("auto_restart"):
                if attempt_restart(
                    spec, dead_listening=(r["state"] == "dead-listening")
                ):
                    restarted = True
        st["restart_attempted"] = True

    # SessionStart always alerts when down (the resume-after-hours case is critical);
    # PreToolUse alerts once per down-episode (no nagging on every memory call).
    should_alert = (mode == "sessionstart") or (not st.get("alerted_down"))
    event = "SessionStart" if mode == "sessionstart" else "PreToolUse"
    if should_alert and down:
        emit(event, format_alert(down, reharness_down, restarted))
        st["alerted_down"] = True
    elif should_alert and reharness_down and mode == "sessionstart":
        emit(event, format_alert([], reharness_down, False))

    st.update({"last_check": now, "last_state": down[0]["state"] if down else "up"})
    save_state(sid, st)
    return 0


# ---------------------------------------------------------------------------
# --mode all: the probe ladder L0-L5 (report-only)
# ---------------------------------------------------------------------------
REPO_ROOT = THIS.parents[1]
DEFAULT_AGENTS_CONFIG = REPO_ROOT / ".agents" / "agents.json"
DEFAULT_MODELS_REGISTRY = REPO_ROOT / ".agents" / "models.json"
DEFAULT_DIGESTS = REPO_ROOT / "state" / "tool-digests.json"
TOOLCHAIN_PREFIX = "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\"
SCRIPT_SUFFIXES = (".py", ".js", ".mjs", ".ps1")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
RUNGS = ("L0", "L1", "L2", "L3", "L4", "L5")
DIGESTS_SCHEMA_VERSION = 1
DEFAULT_HEALTH_TIMEOUT = 5.0
DEFAULT_INFERENCE_TIMEOUT = 60.0
SCAN_TIMEOUT_SECONDS = 180.0
MAX_BODY_BYTES = 4 * 1024 * 1024
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
TRANSPORT_ERRORS = (OSError, http.client.HTTPException, ValueError)

Json = dict[str, Any]
HttpResponse = tuple[int, dict[str, str], bytes]
RungResult = tuple[str, list[Json]]


# ---- transport (module-level so tests inject fakes) ------------------------
def _http_send(req: urllib.request.Request, timeout: float) -> HttpResponse:
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- probe ladder; URLs come from the two committed registries and are loopback-only for anything that sends a body
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read(MAX_BODY_BYTES)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read(MAX_BODY_BYTES)


def http_get(url: str, timeout: float) -> HttpResponse:
    """GET -> ``(status, headers, body)``; HTTP errors are a status, transport
    failures raise one of ``TRANSPORT_ERRORS``."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    return _http_send(req, timeout)


def http_post(
    url: str, body: bytes, headers: Mapping[str, str], timeout: float
) -> HttpResponse:
    """POST ``body`` -> ``(status, headers, body)``; same contract as ``http_get``."""
    req = urllib.request.Request(url, data=body, method="POST", headers=dict(headers))
    return _http_send(req, timeout)


def run_command(command: Sequence[str], timeout: float) -> tuple[int, str]:
    """``(returncode, stdout)`` of a finished child; injectable for tests."""
    proc = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout


def which(name: str) -> str | None:
    return shutil.which(name)


# ---- small utilities --------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _elapsed_ms(started: float) -> int:
    return int(round((time.monotonic() - started) * 1000))


def _load_json_object(path: Path) -> Json | None:
    """The JSON object at ``path``, or None when absent, unreadable or not an object."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Same shape as ``mcp_control_plane.atomic_write_json``: temp file beside the
    target, fsync, ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> Json:
    return value if isinstance(value, dict) else {}


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _is_loopback(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    try:
        return urlparse(url).hostname in LOOPBACK_HOSTS
    except ValueError:
        return False


def _is_2xx(status: int) -> bool:
    return 200 <= status < 300


def _decode_jsonrpc(body: bytes) -> Json | None:
    """The first JSON-RPC object in a JSON or SSE (``data:`` lines) body."""
    text = body.decode("utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        try:
            obj = json.loads(stripped[5:].strip())
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _lattice_state(value: Any) -> str:
    """``native`` / ``probed`` / ``declared`` / ``emulated`` / ``absent`` from a
    models.json lattice value (a string or a ``{"state": "probed", ...}`` object)."""
    if isinstance(value, dict):
        return str(value.get("state") or "absent")
    return str(value) if isinstance(value, str) else "absent"


def _rpc(method: str, request_id: int | None, params: Json | None = None) -> bytes:
    message: Json = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        message["id"] = request_id
    if params is not None:
        message["params"] = params
    return json.dumps(message).encode("utf-8")


# ---- L0: static paths -----------------------------------------------------
def map_toolchain_path(arg: str, prefix: str, root: Path) -> Path | None:
    """The path under ``root`` that an owner-box ``arg`` under ``prefix`` maps to;
    None when ``arg`` is not under the prefix (Windows paths compare case-blind)."""
    normalised = arg.replace("/", "\\")
    wanted = prefix.replace("/", "\\")
    if not normalised.lower().startswith(wanted.lower()):
        return None
    remainder = normalised[len(wanted) :]
    return root.joinpath(*[part for part in remainder.split("\\") if part])


def _static_candidates(spec: Mapping[str, Any]) -> list[tuple[str, str]]:
    """``(value, kind)`` for the command and every arg; ``kind`` is ``command``,
    ``--directory`` (the operand), ``script`` (.py/.js/.mjs/.ps1) or ``arg``."""
    candidates: list[tuple[str, str]] = []
    command = spec.get("command")
    if isinstance(command, str):
        candidates.append((command, "command"))
    previous = ""
    for arg in _as_list(spec.get("args")):
        if not isinstance(arg, str):
            continue
        if previous == "--directory":
            kind = "--directory"
        elif arg.lower().endswith(SCRIPT_SUFFIXES):
            kind = "script"
        else:
            kind = "arg"
        candidates.append((arg, kind))
        previous = arg
    return candidates


def static_path_items(
    servers: Mapping[str, Any], prefix: str, root: Path
) -> list[Json]:
    """One item per checkable arg of every ENABLED stdio server.

    ``ok`` / ``missing`` when the arg maps under ``root``; ``unmapped`` when a
    ``--directory`` operand or a script arg lives outside the toolchain prefix (it
    cannot be checked from the repo, and saying so beats silence).
    """
    items: list[Json] = []
    for name, spec in servers.items():
        if not isinstance(spec, dict):
            continue
        if not spec.get("enabled") or spec.get("transport") != "stdio":
            continue
        for value, kind in _static_candidates(spec):
            mapped = map_toolchain_path(value, prefix, root)
            if mapped is None:
                if kind in ("--directory", "script"):
                    items.append(
                        {
                            "server": name,
                            "arg": value,
                            "kind": kind,
                            "status": "unmapped",
                        }
                    )
                continue
            items.append(
                {
                    "server": name,
                    "arg": value,
                    "kind": kind,
                    "path": mapped.relative_to(root).as_posix(),
                    "status": "ok" if mapped.exists() else "missing",
                }
            )
    return items


def rung_static(
    servers: Mapping[str, Any] | None, prefix: str, root: Path
) -> RungResult:
    if servers is None:
        return "error", [{"reason": "agents config unreadable"}]
    items = static_path_items(servers, prefix, root)
    status = "missing" if any(i["status"] == "missing" for i in items) else "ok"
    return status, items


# ---- L1: initialize (the existing probe, widened to every loopback MCP row) ---
def l1_targets(cfg: Mapping[str, Any], servers: Mapping[str, Any]) -> dict[str, Json]:
    """critical.json rows plus every ENABLED loopback ``http`` MCP row of agents.json
    (hosted MCP rows need credentials and are owner-run, so they are left out)."""
    targets: dict[str, Json] = {
        str(name): dict(spec)
        for name, spec in _as_dict(cfg.get("critical")).items()
        if isinstance(spec, dict)
    }
    for name, spec in servers.items():
        if not isinstance(spec, dict) or name in targets:
            continue
        if not spec.get("enabled") or spec.get("transport") != "http":
            continue
        url = spec.get("url")
        if not _is_loopback(url):
            continue
        parsed = urlparse(url)
        targets[str(name)] = {
            "url": url,
            "host": parsed.hostname,
            "port": parsed.port or (443 if parsed.scheme == "https" else 80),
            "why": str(spec.get("description") or ""),
        }
    return targets


def rung_initialize(cfg: Mapping[str, Any], servers: Mapping[str, Any]) -> RungResult:
    items: list[Json] = []
    for name, spec in l1_targets(cfg, servers).items():
        started = time.monotonic()
        item = probe_critical(name, spec, dict(cfg))
        item["latency_ms"] = _elapsed_ms(started)
        items.append(item)
    status = "down" if any(i["state"] != "up" for i in items) else "ok"
    return status, items


# ---- L2: tools/list digest pin ----------------------------------------------
def tools_list(url: str, timeout: float) -> list[Json] | None:
    """``result.tools`` of a fresh ``initialize`` -> ``tools/list`` exchange, or
    None when the server did not return a tool list (transport errors propagate)."""
    headers: dict[str, str] = dict(MCP_HEADERS)
    init_params: Json = {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-liveness", "version": "1.0"},
    }
    _status, init_headers, _body = http_post(
        url, _rpc("initialize", 1, init_params), headers, timeout
    )
    session = _header(init_headers, "Mcp-Session-Id")
    if session:
        headers["Mcp-Session-Id"] = session
    http_post(url, _rpc("notifications/initialized", None), headers, timeout)
    _status, _headers, body = http_post(
        url, _rpc("tools/list", 2, {}), headers, timeout
    )
    obj = _decode_jsonrpc(body)
    tools = _as_dict(obj).get("result")
    tools = _as_dict(tools).get("tools")
    if not isinstance(tools, list):
        return None
    return [tool for tool in tools if isinstance(tool, dict)]


def tool_digest(tools: Iterable[Mapping[str, Any]]) -> str:
    """sha256 over the sorted ``name|description`` lines."""
    lines = sorted(
        f"{tool.get('name', '')}|{tool.get('description', '')}" for tool in tools
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def load_digests(path: Path) -> Json | None:
    """The pin file's ``servers`` map; an empty map when the file does not exist;
    None when it exists but is not a valid pin file (never overwritten then)."""
    if not path.exists():
        return {}
    payload = _load_json_object(path)
    servers = payload.get("servers") if payload else None
    return servers if isinstance(servers, dict) else None


def rung_digests(
    l1_items: Iterable[Mapping[str, Any]], digests_path: Path, timeout: float, now: str
) -> RungResult:
    pins = load_digests(digests_path)
    if pins is None:
        return "error", [{"reason": f"digest pin file is not valid: {digests_path}"}]
    items: list[Json] = []
    new_pins: Json = {}
    for probe in l1_items:
        name = str(probe.get("name"))
        if probe.get("state") != "up":
            items.append(
                {"server": name, "status": "none", "reason": f"L1:{probe.get('state')}"}
            )
            continue
        try:
            tools = tools_list(str(probe.get("url")), timeout)
        except TRANSPORT_ERRORS as exc:
            tools = None
            reason = f"{type(exc).__name__}: {exc}"
        else:
            reason = "no tools/list result"
        if tools is None:
            items.append({"server": name, "status": "unavailable", "reason": reason})
            continue
        digest = tool_digest(tools)
        item: Json = {"server": name, "toolDigest": digest, "tools": len(tools)}
        pin = _as_dict(pins.get(name))
        if not pin:
            item["status"] = "pinned"
            item["pinned_at"] = now
            new_pins[name] = {
                "toolDigest": digest,
                "tools": len(tools),
                "pinned_at": now,
            }
        elif pin.get("toolDigest") == digest:
            item["status"] = "unchanged"
            item["pinned_at"] = pin.get("pinned_at")
        else:
            item.update(
                {
                    "status": "changed",
                    "verdict": "quarantine-candidate",
                    "pinned_digest": pin.get("toolDigest"),
                    "pinned_at": pin.get("pinned_at"),
                    "reviewed": bool(pin.get("reviewed")),
                }
            )
        items.append(item)
    if new_pins:
        _atomic_write_json(
            digests_path,
            {
                "schemaVersion": DIGESTS_SCHEMA_VERSION,
                "updated_at": now,
                "servers": dict(sorted({**pins, **new_pins}.items())),
            },
        )
    status = "changed" if any(i["status"] == "changed" for i in items) else "ok"
    return status, items


# ---- L3: /v1/models ---------------------------------------------------------
def health_url(base_url: str, health: Mapping[str, Any]) -> str:
    """``health.path`` on the endpoint's origin when the health kind is ``http``,
    else the OpenAI ``/models`` list under ``baseUrl``."""
    path = health.get("path")
    if health.get("kind") == "http" and isinstance(path, str) and path:
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    return base_url.rstrip("/") + "/models"


def model_ids(body: bytes) -> list[str]:
    """Sorted ``data[].id`` of an OpenAI-shape models list; empty for any other body."""
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    return sorted(
        str(entry["id"])
        for entry in _as_list(_as_dict(payload).get("data"))
        if isinstance(entry, dict) and "id" in entry
    )


def registry_models(registry: Mapping[str, Any], endpoint_id: str) -> list[str]:
    """``remoteId`` of every ENABLED model row on ``endpoint_id``, sorted."""
    return sorted(
        str(model.get("remoteId") or model_id)
        for model_id, model in _as_dict(registry.get("models")).items()
        if isinstance(model, dict)
        and model.get("enabled")
        and model.get("endpoint") == endpoint_id
    )


def endpoint_claims(endpoint: Mapping[str, Any]) -> list[str]:
    """Every ``wire`` / ``features`` name the registry claims (state not absent)."""
    claims = {
        str(name)
        for block in ("wire", "features")
        for name, value in _as_dict(endpoint.get(block)).items()
        if _lattice_state(value) != "absent"
    }
    return sorted(claims)


def _timeout_seconds(block: Mapping[str, Any], default: float) -> float:
    value = block.get("timeoutMs")
    if isinstance(value, (int, float)) and value > 0:
        return float(value) / 1000.0
    return default


def rung_models(registry: Mapping[str, Any] | None) -> RungResult:
    if registry is None:
        return "error", [{"reason": "models registry unreadable"}]
    items: list[Json] = []
    for endpoint_id, endpoint in _as_dict(registry.get("endpoints")).items():
        if not isinstance(endpoint, dict):
            continue
        base_url = endpoint.get("baseUrl")
        item: Json = {"endpoint": str(endpoint_id), "url": base_url}
        if not endpoint.get("enabled"):
            items.append({**item, "status": "skipped", "reason": "disabled"})
            continue
        if not _is_loopback(base_url):
            items.append({**item, "status": "skipped", "reason": "hosted:owner-run"})
            continue
        health = _as_dict(endpoint.get("health"))
        url = health_url(str(base_url), health)
        item.update(
            {
                "url": url,
                "registry_models": registry_models(registry, str(endpoint_id)),
                "claims": endpoint_claims(endpoint),
            }
        )
        started = time.monotonic()
        try:
            status, _headers, body = http_get(
                url, _timeout_seconds(health, DEFAULT_HEALTH_TIMEOUT)
            )
        except TRANSPORT_ERRORS as exc:
            item.update(
                {
                    "status": "down",
                    "latency_ms": _elapsed_ms(started),
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            items.append(item)
            continue
        item.update(
            {
                "status": "up" if _is_2xx(status) else "down",
                "http_status": status,
                "latency_ms": _elapsed_ms(started),
                "models": model_ids(body) if _is_2xx(status) else [],
            }
        )
        items.append(item)
    probed = [i for i in items if i["status"] != "skipped"]
    status = "down" if any(i["status"] == "down" for i in probed) else "ok"
    return status, items


# ---- L4: one token, gated ----------------------------------------------------
def rung_inference(
    registry: Mapping[str, Any] | None,
    l3_items: Iterable[Mapping[str, Any]],
    *,
    allow_inference: bool,
) -> RungResult:
    """One ``max_tokens: 1`` chat completion per ENABLED loopback endpoint whose
    ``wire.completions`` is still only ``declared`` -- and only behind the flag.
    No credential is ever attached (an endpoint with ``auth`` is owner-run) and the
    item carries neither the prompt nor a header nor the response body."""
    if registry is None:
        return "error", [{"reason": "models registry unreadable"}]
    probes = {str(i.get("endpoint")): i for i in l3_items}
    timeout = _timeout_seconds(
        _as_dict(registry.get("policy")), DEFAULT_INFERENCE_TIMEOUT
    )
    items: list[Json] = []
    for endpoint_id, endpoint in _as_dict(registry.get("endpoints")).items():
        if not isinstance(endpoint, dict):
            continue
        item: Json = {"endpoint": str(endpoint_id), "wire": "completions"}
        wire_state = _lattice_state(_as_dict(endpoint.get("wire")).get("completions"))
        probe = _as_dict(probes.get(str(endpoint_id)))
        skip = None
        if not endpoint.get("enabled"):
            skip = "disabled"
        elif not _is_loopback(endpoint.get("baseUrl")):
            skip = "hosted:owner-run"
        elif not allow_inference:
            skip = "flag:--allow-inference"
        elif endpoint.get("auth") is not None:
            skip = "auth:owner-run"
        elif wire_state != "declared":
            skip = f"wire:completions={wire_state}"
        elif probe.get("status") != "up":
            skip = f"L3:{probe.get('status') or 'absent'}"
        candidates = [
            *_as_list(probe.get("models")),
            *_as_list(probe.get("registry_models")),
        ]
        if skip is None and not candidates:
            skip = "no-model"
        if skip is not None:
            items.append({**item, "status": "skipped", "reason": skip})
            continue
        model = str(candidates[0])
        url = str(endpoint["baseUrl"]).rstrip("/") + "/chat/completions"
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }
        ).encode("utf-8")
        item.update({"model": model, "url": url})
        started = time.monotonic()
        try:
            status, _headers, _body = http_post(
                url, payload, {"Content-Type": "application/json"}, timeout
            )
        except TRANSPORT_ERRORS as exc:
            item.update(
                {
                    "status": "error",
                    "latency_ms": _elapsed_ms(started),
                    "observed": {"completions": False},
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            items.append(item)
            continue
        item.update(
            {
                "status": "ok" if _is_2xx(status) else "error",
                "http_status": status,
                "latency_ms": _elapsed_ms(started),
                "observed": {"completions": _is_2xx(status)},
            }
        )
        items.append(item)
    ran = [i for i in items if i["status"] != "skipped"]
    if not ran:
        return "skipped", items
    status = "error" if any(i["status"] == "error" for i in ran) else "ok"
    return status, items


# ---- L5: mcp-scan -------------------------------------------------------------
def scan_command() -> list[str] | None:
    if which("mcp-scan"):
        return ["mcp-scan", "--local-only", "--json"]
    if which("uvx"):
        return ["uvx", "mcp-scan", "--local-only", "--json"]
    return None


def scan_items(payload: Mapping[str, Any]) -> list[Json]:
    """One item per scanned config file: server count, issue count and the names
    of the servers an issue's ``reference`` points at."""
    items: list[Json] = []
    for path, entry in payload.items():
        if not isinstance(entry, dict):
            continue
        servers = [s for s in _as_list(entry.get("servers")) if isinstance(s, dict)]
        names = [str(s.get("name") or f"#{i}") for i, s in enumerate(servers)]
        issues = [i for i in _as_list(entry.get("issues")) if isinstance(i, dict)]
        flagged: set[str] = set()
        for issue in issues:
            reference = _as_list(issue.get("reference"))
            index = reference[0] if reference else None
            if isinstance(index, int) and 0 <= index < len(names):
                flagged.add(names[index])
        items.append(
            {
                "path": str(path),
                "servers": len(servers),
                "issues": len(issues),
                "flagged": sorted(flagged),
            }
        )
    return items


def rung_scan(timeout: float) -> RungResult:
    command = scan_command()
    if command is None:
        return "skipped", [{"reason": "neither mcp-scan nor uvx is on PATH"}]
    try:
        returncode, stdout = run_command(command, timeout)
    except subprocess.TimeoutExpired:
        return "error", [{"command": command, "reason": f"timeout after {timeout}s"}]
    except OSError as exc:
        return "error", [{"command": command, "reason": f"{type(exc).__name__}: {exc}"}]
    try:
        payload = json.loads(stdout)
    except ValueError:
        reason = f"exit {returncode}: output is not JSON"
        return "error", [{"command": command, "reason": reason}]
    if not isinstance(payload, dict):
        return "error", [{"command": command, "reason": "unrecognised mcp-scan output"}]
    items = scan_items(payload)
    status = "findings" if any(i["issues"] for i in items) else "clean"
    return status, [{"command": command}, *items]


# ---- orchestration ----------------------------------------------------------
def _timed(fn: Callable[[], RungResult]) -> Json:
    started = time.monotonic()
    status, items = fn()
    return {"status": status, "items": items, "duration_ms": _elapsed_ms(started)}


def run_ladder(
    *,
    root: Path,
    agents_config: Path,
    registry_path: Path,
    digests_path: Path,
    prefix: str = TOOLCHAIN_PREFIX,
    allow_inference: bool = False,
    scan_timeout: float = SCAN_TIMEOUT_SECONDS,
    now: str | None = None,
) -> Json:
    """The whole ladder as one report: ``{mode, generated_at, rungs, duration_ms}``."""
    started = time.monotonic()
    now = now or utc_now_iso()
    cfg = load_config()
    agents = _load_json_object(agents_config)
    servers = _as_dict(_as_dict(agents.get("mcp")).get("servers")) if agents else {}
    registry = _load_json_object(registry_path)
    timeout = float(cfg.get("handshake_timeout", 5.0))

    rungs: dict[str, Json] = {}
    rungs["L0"] = _timed(
        lambda: rung_static(None if agents is None else servers, prefix, root)
    )
    rungs["L1"] = _timed(lambda: rung_initialize(cfg, servers))
    rungs["L2"] = _timed(
        lambda: rung_digests(rungs["L1"]["items"], digests_path, timeout, now)
    )
    rungs["L3"] = _timed(lambda: rung_models(registry))
    rungs["L4"] = _timed(
        lambda: rung_inference(
            registry, rungs["L3"]["items"], allow_inference=allow_inference
        )
    )
    rungs["L5"] = _timed(lambda: rung_scan(scan_timeout))
    return {
        "mode": "all",
        "generated_at": now,
        "root": str(root),
        "allow_inference": allow_inference,
        "rungs": rungs,
        "duration_ms": _elapsed_ms(started),
    }


def _ladder_marker(report: Mapping[str, Any]) -> str:
    rungs = _as_dict(report.get("rungs"))
    parts = [f"{rung}={_as_dict(rungs.get(rung)).get('status')}" for rung in RUNGS]
    return f"SUCCESS:liveness-all {' '.join(parts)} duration_ms={report['duration_ms']}"


def _split_mode(argv: Sequence[str]) -> tuple[str, list[str]]:
    """``(mode, rest)`` from ``liveness.py <mode>``, ``--mode <mode>`` or ``--mode=<mode>``."""
    args = list(argv)
    if not args:
        return "sessionstart", []
    if args[0] == "--mode":
        return (args[1].lower() if len(args) > 1 else ""), args[2:]
    if args[0].startswith("--mode="):
        return args[0][len("--mode=") :].lower(), args[1:]
    return args[0].lower(), args[1:]


def main_all(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="liveness.py --mode all",
        description="Report-only probe ladder L0-L5 over the two registries.",
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repo root for L0")
    parser.add_argument("--agents-config", type=Path, default=DEFAULT_AGENTS_CONFIG)
    parser.add_argument("--registry", type=Path, default=DEFAULT_MODELS_REGISTRY)
    parser.add_argument("--digests", type=Path, default=DEFAULT_DIGESTS)
    parser.add_argument("--prefix", default=TOOLCHAIN_PREFIX, help="owner-box prefix")
    parser.add_argument(
        "--allow-inference", action="store_true", help="enable the L4 one-token probe"
    )
    parser.add_argument("--scan-timeout", type=float, default=SCAN_TIMEOUT_SECONDS)
    parser.add_argument("--out", type=Path, default=None, help="write the report here")
    args = parser.parse_args(list(argv))
    try:
        report = run_ladder(
            root=args.root,
            agents_config=args.agents_config,
            registry_path=args.registry,
            digests_path=args.digests,
            prefix=args.prefix,
            allow_inference=args.allow_inference,
            scan_timeout=args.scan_timeout,
        )
        if args.out is not None:
            _atomic_write_json(args.out, report)
        else:
            print(json.dumps(report, indent=2))
    except Exception as exc:
        print(f"FAILED:liveness-all {type(exc).__name__}: {exc}")
        return 2
    print(_ladder_marker(report))
    return 0


def main(argv: Sequence[str]) -> int:
    mode, rest = _split_mode(argv)
    if mode == "all":
        return main_all(rest)
    try:
        if DISABLED.exists() or os.environ.get("MCP_LIVENESS", "").lower() in (
            "off",
            "0",
            "false",
        ):
            return 0

        if mode == "probe":
            # CLI test mode: print status + terminal-state marker, no restart/alert.
            cfg = load_config()
            results = [
                probe_critical(n, s, cfg)
                for n, s in (cfg.get("critical") or {}).items()
            ]
            rh = probe_reharness(cfg)
            down = [r for r in results if r["state"] != "up"]
            report = {"critical": results, "reharness_down": rh}
            marker = (
                "SUCCESS:liveness all critical MCPs up"
                if not down
                else f"FAILED:liveness {len(down)} critical down: "
                + ",".join(f"{r['name']}={r['state']}" for r in down)
            )
            print(json.dumps(report, indent=2))
            print(marker)
            return 1 if down else 0

        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            data = {}
        return run(mode, data)
    except Exception:
        return 0  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
