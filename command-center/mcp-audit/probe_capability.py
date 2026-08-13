#!/usr/bin/env python3
"""Real per-server MCP CAPABILITY probe -- the audit's missing producer.

The grounding lane measured four signals (config / host-health / session-namespace /
one real call) and found the fourth was never produced per-server.  This is that
producer, scoped to the audit: for each named server it performs a genuine MCP
handshake -- ``initialize`` -> ``notifications/initialized`` -> ``tools/list``
(paginated) -- against a freshly spawned stdio child, then reaps the child's whole
process tree.  It answers the question a health ping cannot: *does this server
actually advertise a working tool surface right now, and how big is it.*

WHY NOT A NEW PRIMITIVE.  ``tools/mcp/mcp-http-host/mcp_http_host.py::StdioChild``
already speaks this wire and is tested; this module imports it by path and adds only
what the audit needs (spec resolution, a tree-reaping terminate, RSS, redaction, a
both-states control, JSON output).  Nothing under ``tools/`` is modified.

SECURITY.  ``StdioChild`` spawns with ``stderr=subprocess.DEVNULL``, so no child
stderr is ever captured -- a server that dies complaining about a missing API key
cannot leak that key into this artifact.  The cost is diagnostic: ``last_error``
carries our own handshake exception (timeout / EOF / exit code), never the child's
message.  That trade is deliberate and is disclosed in the emitted JSON.
Env blocks are passed to the child (servers need them to start) but only variable
NAMES are ever recorded, and every emitted string is run through a redactor that
replaces any environment value of length >= 8 with ``<redacted:NAME>``.

NOT READ-ONLY.  This SPAWNS the servers it probes.  That is the point -- a config
read cannot tell you whether a server works -- but it is why the target list is an
explicit allowlist rather than "every row in the matrix".  ``claude mcp list``
spawning all 145 entries unasked is the failure mode this deliberately avoids.

Usage::

    python probe_capability.py --control            # both-states control only
    python probe_capability.py --mounted -o out.json
    python probe_capability.py --servers cloud-hub,searxng -o out.json
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[2]
HOST_DIR = REPO / "tools" / "mcp" / "mcp-http-host"
sys.path.insert(0, str(HOST_DIR))

from mcp_http_host import StdioChild  # noqa: E402  (path injection must precede)

HOME = pathlib.Path(os.path.expanduser("~"))
CLAUDE_JSON = HOME / ".claude.json"
MCP_JSON = HOME / ".mcp.json"

# Transcribed from the ``mcp__<server>__*`` tool namespaces injected into THIS
# session (2026-08-12).  The grounding lane transcribed the same 23 names from an
# independent session earlier the same day; the two agree exactly, which is a
# corroboration of the census, not a re-run of one probe.
MOUNTED = (
    "agent-mail",
    "angr",
    "basic-memory",
    "brightdata",
    "chrome-devtools",
    "claude-code-mcp",
    "cloud-hub",
    "codex",
    "context7",
    "deepwiki",
    "figma",
    "frida-mcp",
    "github",
    "huggingface",
    "paper-search",
    "playwright",
    "playwright-cdp",
    "playwright-extension",
    "qlty",
    "repomix",
    "scholarly-access",
    "search-hub",
    "searxng",
)

DEFAULT_TIMEOUT = 60.0
PROTOCOL_VERSION = "2025-06-18"

# Windows ``CreateProcess`` does NOT apply PATHEXT, so ``Popen(["npx", ...])`` raises
# FileNotFoundError even though ``npx.CMD`` is on PATH.  The first run of this sweep
# reported chrome-devtools / codex / all three playwright rails as broken for exactly
# that reason -- while ``codex`` had already been proven working by a real tool call.
# A self-contradicting output is a detector failure, not a finding.  Resolve the
# command through PATHEXT before spawning.  Toggleable so the SHIM control below can
# be shown to go red without it.
RESOLVE_SHIMS = True


def resolve_command(command: str) -> tuple[str, str]:
    """Return ``(argv0, how)``: PATHEXT-resolved executable and the method used."""
    if not RESOLVE_SHIMS:
        return command, "raw"
    found = shutil.which(command)
    if found and found != command:
        return found, "pathext"
    return command, "verbatim" if found else "unresolved"


# --------------------------------------------------------------------------- redaction
def build_redactor(extra: dict[str, str] | None = None) -> Any:
    """Return ``redact(text)`` replacing any env VALUE with ``<redacted:NAME>``.

    Longest-first so a value that contains another value is masked whole.  Only
    values of length >= 8 participate: shorter ones ("1", "true", "C:\\") are not
    credentials and masking them would shred ordinary diagnostics.
    """
    pairs: list[tuple[str, str]] = []
    for name, value in {**os.environ, **(extra or {})}.items():
        if isinstance(value, str) and len(value) >= 8:
            pairs.append((value, name))
    pairs.sort(key=lambda pv: -len(pv[0]))

    def redact(text: str) -> str:
        if not text:
            return text
        for value, name in pairs:
            if value in text:
                text = text.replace(value, f"<redacted:{name}>")
        return text

    return redact


# --------------------------------------------------------------------------- specs
def load_specs() -> dict[str, dict[str, Any]]:
    """Resolve ``name -> spec`` from the two files that DEFINE servers.

    ``~/.claude.json`` (``mcpServers``) and ``~/.mcp.json`` (``mcpServers``).  The
    other three scopes in mcpctl's model (settings.json ``deniedMcpServers``,
    settings.local.json approvals, ``.mcp-disabled-defaults.json``) only ENABLE or
    DISABLE names; they define no command, so they cannot be probed from.
    """
    specs: dict[str, dict[str, Any]] = {}
    for path, scope in ((CLAUDE_JSON, "claude-user"), (MCP_JSON, "mcp-json")):
        if not path.exists():
            continue
        try:
            blob = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        for name, raw in (blob.get("mcpServers") or {}).items():
            if not isinstance(raw, dict):
                continue
            specs.setdefault(
                name,
                {
                    "name": name,
                    "definition_scope": scope,
                    "source_file": str(path),
                    "transport": _transport(raw),
                    "command": raw.get("command"),
                    "args": list(raw.get("args") or []),
                    "url": raw.get("url"),
                    "env_names": sorted((raw.get("env") or {}).keys()),
                    "_env": dict(raw.get("env") or {}),
                },
            )
    return specs


def _transport(raw: dict[str, Any]) -> str:
    declared = (raw.get("type") or "").strip().lower()
    if declared in {"http", "sse", "streamable-http"}:
        return "http"
    if declared == "stdio":
        return "stdio"
    if raw.get("url"):
        return "http"
    if raw.get("command"):
        return "stdio"
    return "unknown"


# --------------------------------------------------------------------------- memory
class _PMCEX(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def process_memory(pid: int) -> dict[str, int] | None:
    """Working-set + commit for ONE pid (the direct child only, not its tree).

    A hub that lazily spawns backends (cloud-hub -> rclone rcd, search-hub ->
    per-provider children) charges most of its RAM to those children, so this is a
    FLOOR on the server's true footprint, never the total.  Stated here because a
    number without its scope is how a census gets misquoted.

    ``rss_bytes`` IS ``working_set_bytes``, emitted twice on purpose.  Round 1 claimed
    this producer emitted "exactly the four fields ``mcpctl.matrix.Row`` leaves null";
    a verifier REFUTED that -- mcpctl's fourth field is named ``rss_bytes`` and only
    three names matched, so the injected snapshot silently dropped memory.  Windows has
    no RSS counter; ``WorkingSetSize`` is its documented analogue (the same mapping
    psutil uses for ``Process.memory_info().rss`` on nt), so the value is right and only
    the NAME was missing.  The platform-specific name is kept alongside so the
    provenance of the number survives the alias.
    """
    if os.name != "nt":
        return None
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    handle = k32.OpenProcess(0x0400 | 0x0010, False, pid)  # QUERY_INFO | VM_READ
    if not handle:
        return None
    try:
        counters = _PMCEX()
        counters.cb = ctypes.sizeof(_PMCEX)
        ok = psapi.GetProcessMemoryInfo(
            ctypes.c_void_p(handle), ctypes.byref(counters), counters.cb
        )
        if not ok:
            return None
        return {
            "working_set_bytes": int(counters.WorkingSetSize),
            "rss_bytes": int(counters.WorkingSetSize),
            "commit_bytes": int(counters.PrivateUsage),
        }
    finally:
        k32.CloseHandle(ctypes.c_void_p(handle))


def reap_tree(pid: int) -> None:
    """Kill the child AND its descendants.

    ``StdioChild.terminate()`` signals only the direct child.  Half the fleet is
    launched as ``cmd /c npx ...``; terminating ``cmd.exe`` there orphans the node
    process, so a naive sweep would ADD to the very process-duplication problem the
    audit is measuring.  Called while the pid is provably still ours.
    """
    if os.name != "nt":
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        check=False,
    )


# --------------------------------------------------------------------------- probe
def probe(spec: dict[str, Any], timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """One full handshake against one stdio server.  Never raises."""
    redact = build_redactor(spec.get("_env"))
    row: dict[str, Any] = {
        "name": spec["name"],
        "definition_scope": spec.get("definition_scope"),
        "source_file": spec.get("source_file"),
        "transport": spec.get("transport"),
        "env_names": spec.get("env_names", []),
        "probe_method": "stdio-handshake",
        "command_resolution": None,
        "call_verified": False,
        "server_info": None,
        "tool_count": None,
        "tool_names": None,
        "name_bytes": None,
        "schema_bytes": None,
        "pid": None,
        "working_set_bytes": None,
        # mcpctl.matrix.Liveness reads this exact name; see process_memory().
        "rss_bytes": None,
        "commit_bytes": None,
        "elapsed_ms": None,
        "last_error": None,
    }
    if spec.get("transport") != "stdio" or not spec.get("command"):
        row["probe_method"] = "not-spawnable"
        row["last_error"] = f"transport={spec.get('transport')!r}: no stdio command"
        return row

    argv0, how = resolve_command(str(spec["command"]))
    row["command_resolution"] = how
    cmd = [argv0, *[str(a) for a in spec.get("args", [])]]
    child = StdioChild(cmd, env=spec.get("_env") or None)
    started = time.monotonic()
    pid: int | None = None
    try:
        init = child.request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-audit-capability", "version": "1"},
                },
            },
            timeout=timeout,
        )
        pid = child.pid
        row["pid"] = pid
        result = (init or {}).get("result") or {}
        row["server_info"] = result.get("serverInfo")
        child.request({"jsonrpc": "2.0", "method": "notifications/initialized"})

        names: list[str] = []
        schema_bytes = 0
        cursor: str | None = None
        for page in range(20):
            params = {"cursor": cursor} if cursor else {}
            resp = child.request(
                {
                    "jsonrpc": "2.0",
                    "id": 100 + page,
                    "method": "tools/list",
                    "params": params,
                },
                timeout=timeout,
            )
            body = (resp or {}).get("result") or {}
            for tool in body.get("tools") or []:
                if not isinstance(tool, dict):
                    continue
                names.append(str(tool.get("name")))
                # Byte size of the FULL tool declaration (name + description +
                # inputSchema) as the server sends it.  This is the eager-regime
                # context cost; the schemas themselves are deliberately NOT stored,
                # only measured, so the artifact stays small and carries no payload.
                schema_bytes += len(json.dumps(tool, separators=(",", ":")))
            cursor = body.get("nextCursor")
            if not cursor:
                break
        row["tool_count"] = len(names)
        row["tool_names"] = sorted(names)
        # Deferred regime injects names only (this session's regime), so name bytes
        # are the measured cost there; schema_bytes is the eager-regime cost.
        row["name_bytes"] = sum(len(n) for n in names)
        row["schema_bytes"] = schema_bytes
        row["call_verified"] = True
        if pid:
            row.update(process_memory(pid) or {})
    except Exception as exc:  # noqa: BLE001 -- a probe must never crash the sweep
        row["last_error"] = redact(f"{type(exc).__name__}: {exc}")
    finally:
        row["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        if pid:
            reap_tree(pid)
        child.terminate()
    return row


# --------------------------------------------------------------------------- control
def run_control() -> tuple[bool, list[dict[str, Any]]]:
    """BOTH-STATES control, fail-closed.

    Three states, chosen so a PASS can only mean one thing:

      GOOD      the committed ``_fake_mcp_server.py`` fixture -> MUST report
                ``call_verified`` and EXACTLY 1 tool (the fixture defines one).
      MISSING   a command that does not exist          -> MUST report failure.
      NOT-MCP   a real process that speaks no MCP      -> MUST report failure.
      SHIM      the same fixture behind a bare ``.cmd`` name on PATH -> MUST
                report 1 tool.  Regression control for the PATHEXT bug that made
                the first sweep call five working servers broken.

    NOT-MCP is the state that makes this a control rather than theatre.  Without
    it, a prober that merely checked ``Popen`` succeeded would pass GOOD and
    MISSING and be indistinguishable from one that performs the handshake -- the
    "control that cannot distinguish the two hypotheses" failure.  Requiring the
    exact tool count (not merely ``>0``) closes the other side: a prober that
    invented a surface could not land on 1.
    """
    fixture = HOST_DIR / "_fake_mcp_server.py"
    py = sys.executable
    # SHIM is a WINDOWS-ONLY state.  It regresses the defect that CreateProcess does not
    # apply PATHEXT, so a bare ``auditshim`` naming ``auditshim.cmd`` fails to launch.  POSIX
    # has no PATHEXT and no ``.cmd``: the defect cannot exist there, so the state is not
    # merely inconvenient, it is UNOBSERVABLE -- and a control that cannot fail is not a
    # control.  Measured on Ubuntu 24.04 before this branch existed: SHIM reported
    # ``FileNotFoundError: 'auditshim'`` and turned the whole gate red, which would have made
    # ``--control`` permanently red on ubuntu-latest.  It is therefore skipped on POSIX with
    # the reason recorded, and EXPECTED_STATES below makes an accidental skip loud instead of
    # silently shrinking the control to whatever happened to run.
    windows = os.name == "nt"
    shim_dir: pathlib.Path | None = None
    shim: pathlib.Path | None = None
    if windows:
        shim_dir = pathlib.Path(tempfile.mkdtemp(prefix="mcpaudit-shim-"))
        shim = shim_dir / "auditshim.cmd"
        shim.write_text(f'@echo off\r\n"{py}" "{fixture}" %*\r\n', encoding="ascii")
        os.environ["PATH"] = f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    cases = [
        (
            "GOOD",
            {
                "name": "_control_good",
                "transport": "stdio",
                "command": py,
                "args": [str(fixture)],
                "definition_scope": "control",
                "source_file": str(fixture),
                "env_names": [],
            },
        ),
        (
            "MISSING",
            {
                "name": "_control_missing",
                "transport": "stdio",
                "command": "definitely-not-a-real-binary-9f3a",
                "args": [],
                "definition_scope": "control",
                "source_file": "-",
                "env_names": [],
            },
        ),
        (
            "NOT-MCP",
            {
                "name": "_control_not_mcp",
                "transport": "stdio",
                "command": py,
                "args": ["-c", "import sys; sys.stdout.write('not json\\n')"],
                "definition_scope": "control",
                "source_file": "-",
                "env_names": [],
            },
        ),
    ]
    if windows:
        cases.append(
            (
                "SHIM",
                {
                    "name": "_control_shim",
                    "transport": "stdio",
                    "command": "auditshim",
                    "args": [],
                    "definition_scope": "control",
                    "source_file": str(shim),
                    "env_names": [],
                },
            )
        )
    rows: list[dict[str, Any]] = []
    ok = True
    for state, spec in cases:
        row = probe(spec, timeout=15.0)
        row["control_state"] = state
        if state in {"GOOD", "SHIM"}:
            passed = bool(row["call_verified"]) and row["tool_count"] == 1
        else:
            passed = not row["call_verified"] and bool(row["last_error"])
        row["control_passed"] = passed
        ok = ok and passed
        rows.append(row)
        print(
            f"  control {state:8} -> call_verified={row['call_verified']} "
            f"tools={row['tool_count']} passed={passed}"
        )
    if shim_dir is not None:
        shutil.rmtree(shim_dir, ignore_errors=True)
    # FLOOR.  Without this, dropping a case from ``cases`` -- or a future platform branch
    # that skips one by accident -- would leave the surviving states green and the control
    # would report success over a shrunken set.  The count is asserted, not assumed.
    expected_states = 4 if windows else 3
    if len(rows) != expected_states:
        print(
            f"  CONTROL FLOOR: executed {len(rows)} states, expected {expected_states} "
            f"on {'nt' if windows else 'posix'} (fail closed)"
        )
        ok = False
    if not windows:
        print(
            "  control SHIM     -> SKIPPED (posix: no PATHEXT, no .cmd; state unobservable)"
        )
    return ok, rows


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control", action="store_true", help="run the control only")
    ap.add_argument("--mounted", action="store_true", help="probe the 23 mounted")
    ap.add_argument("--servers", default="", help="comma-separated server names")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("-o", "--out", default="")
    args = ap.parse_args(argv)

    print("== both-states detector control ==")
    control_ok, control_rows = run_control()
    if not control_ok:
        print("FAILED:probe-capability control did not behave in BOTH states")
        return 1
    print("  control: PASS (good/shim=1 tool, missing=fail, not-mcp=fail)")
    if args.control:
        print("SUCCESS:probe-capability control-only")
        return 0

    targets = [s for s in args.servers.split(",") if s.strip()]
    if args.mounted:
        targets = list(MOUNTED)
    if not targets:
        print("FAILED:probe-capability no targets (pass --mounted or --servers)")
        return 1

    specs = load_specs()
    if not specs:
        print("FAILED:probe-capability resolved ZERO server specs (fail closed)")
        return 1

    print(f"\n== probing {len(targets)} server(s) of {len(specs)} defined ==")
    rows: list[dict[str, Any]] = []
    for name in targets:
        spec = specs.get(name)
        if spec is None:
            rows.append(
                {
                    "name": name,
                    "probe_method": "undefined",
                    "call_verified": False,
                    "last_error": "no spec in ~/.claude.json or ~/.mcp.json",
                }
            )
            print(f"  {name:24} UNDEFINED")
            continue
        row = probe(spec, timeout=args.timeout)
        rows.append(row)
        verdict = "PASS" if row["call_verified"] else "FAIL"
        print(
            f"  {name:24} {verdict:4} tools={row['tool_count']} "
            f"{row['elapsed_ms']}ms {row['last_error'] or ''}"
        )

    payload = {
        "probe": "mcp-capability",
        "generated_utc_date": "2026-08-12",
        "protocol_version": PROTOCOL_VERSION,
        "scope_note": (
            "Spawns each probed server, performs a real initialize+tools/list, "
            "then reaps its process tree. rss/commit are the DIRECT child only "
            "(a hub's lazily-spawned backends are not counted). No child stderr "
            "is captured (StdioChild uses DEVNULL), so last_error is our own "
            "handshake exception, never the server's message."
        ),
        "control": {"passed": control_ok, "rows": control_rows},
        "targets": targets,
        "rows": rows,
        "summary": {
            "probed": len(rows),
            "call_verified": sum(1 for r in rows if r.get("call_verified")),
            "failed": sum(1 for r in rows if not r.get("call_verified")),
            "total_tools": sum(r.get("tool_count") or 0 for r in rows),
        },
    }
    for row in rows:
        row.pop("_env", None)
    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nwrote {args.out}")
    verified = payload["summary"]["call_verified"]
    print(f"SUCCESS:probe-capability verified={verified}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
