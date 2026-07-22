#!/usr/bin/env python3
"""Register the linkedin MCP server on the surface Claude Code ACTUALLY reads.

WHY THIS SCRIPT EXISTS
----------------------
Claude Code resolves *user-scope* MCP servers from the root ``mcpServers`` object
of ``%USERPROFILE%\\.claude.json``. It does NOT resolve them from ``~/.mcp.json``
(that file is *project* scope and additionally requires per-project approval via
the project's ``enabledMcpjsonServers`` array -- which is empty here, so every
server declared only in ``~/.mcp.json`` is dark in a session).

Measured on 2026-07-20, three mechanically independent ways:
  1. 15 servers whose tools are live in a session (apify, basic-memory, github,
     gitlab, notion, qlty, searxng, ...) are declared ONLY in ``.claude.json``.
  2. ``claude mcp get <name>`` reports those as
     "Scope: User config (available in all your projects)".
  3. Of the 11 servers in ``~/.mcp.json``, the 7 declared ONLY there
     (angr, frida-mcp, ghidra-mcp, hexstrike-ai, ida-pro-mcp, playwright,
     schrodinger) expose ZERO tools in a session; the 4 that ARE live
     (cloud-hub, figma, search-hub, social-hub) are ALSO in user scope.

``.claude.json`` is rewritten every ~30s by any RUNNING Claude process, so a
hand-edit made while Claude is open is silently clobbered. Hence: this script
refuses to write unless every Claude process is closed, and it drives the
SUPPORTED ``claude mcp add`` CLI rather than hand-patching that file.

USAGE (PowerShell)
------------------
  # Read-only preflight -- safe to run any time, even with Claude open:
  C:\\Python314\\python.exe .\\tools\\mcp\\linkedin-mcp\\apply_linkedin_userscope.py --check

  # Do it for real -- CLOSE EVERY CLAUDE WINDOW FIRST:
  C:\\Python314\\python.exe .\\tools\\mcp\\linkedin-mcp\\apply_linkedin_userscope.py --apply

  # Register and leave it switched ON:
  ... apply_linkedin_userscope.py --apply --enable

  # Unregister completely (the guaranteed-off state):
  ... apply_linkedin_userscope.py --apply --remove

This script never reads, prints, or persists a token VALUE. It reports only
whether a credential env var is set and how long it is.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
CLAUDE_JSON = os.path.join(HOME, ".claude.json")
SERVER_NAME = "linkedin"
ROSTER = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "canonical-mcp-servers.json"
    )
)
CRED_VARS = (
    "LINKEDIN_ACCESS_TOKEN",
    "LINKEDIN_CLIENT_ID",
    "LINKEDIN_CLIENT_SECRET",
    "LINKEDIN_REDIRECT_URI",
)

OK, BAD = "  [ok]  ", "  [!!]  "


def fail(msg: str) -> None:
    print("\nFAILED: " + msg)
    sys.exit(1)


def claude_processes() -> list[str]:
    """Return names of running Claude processes (empty list == safe to write)."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq claude.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout
    except Exception:
        return ["<could not query tasklist>"]
    return [ln for ln in out.splitlines() if "claude" in ln.lower()]


def node_claude_processes() -> int:
    """Count node processes whose command line runs the Claude CLI."""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | "
        "Where-Object { $_.CommandLine -like '*claude*' } | Measure-Object | "
        "Select-Object -ExpandProperty Count"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=90,
        ).stdout.strip()
        return int(out or 0)
    except Exception:
        return -1


def load_roster_entry() -> dict:
    if not os.path.isfile(ROSTER):
        fail("canonical roster not found at " + ROSTER)
    with open(ROSTER, encoding="utf-8") as fh:
        servers = json.load(fh)["mcpServers"]
    if SERVER_NAME not in servers:
        fail("'%s' is not in the canonical roster %s" % (SERVER_NAME, ROSTER))
    return servers[SERVER_NAME]


def backup_claude_json() -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = "%s.bak-linkedin-%s" % (CLAUDE_JSON, stamp)
    shutil.copy2(CLAUDE_JSON, dest)
    if os.path.getsize(dest) == 0:
        fail("backup %s is EMPTY -- refusing to continue" % dest)
    print(OK + "backup written: %s (%d bytes)" % (dest, os.path.getsize(dest)))
    return dest


def set_disabled(disabled: bool) -> None:
    """Add/remove SERVER_NAME in the root disabledMcpServers array."""
    with open(CLAUDE_JSON, encoding="utf-8") as fh:
        data = json.load(fh)
    arr = data.get("disabledMcpServers")
    if not isinstance(arr, list):
        arr = []
    present = SERVER_NAME in arr
    if disabled and not present:
        arr.append(SERVER_NAME)
        arr.sort()
    elif not disabled and present:
        arr = [x for x in arr if x != SERVER_NAME]
    data["disabledMcpServers"] = arr
    tmp = CLAUDE_JSON + ".tmp-linkedin"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    json.load(open(tmp, encoding="utf-8"))  # parse-check before swapping in
    os.replace(tmp, CLAUDE_JSON)
    print(
        OK
        + "root disabledMcpServers now %s '%s' (%d entries)"
        % ("contains" if disabled else "excludes", SERVER_NAME, len(arr))
    )


def report_credentials() -> None:
    print(
        "\nCredential environment (names + lengths only -- values are never read or printed):"
    )
    for var in CRED_VARS:
        val = os.environ.get(var)
        state = ("set, length %d" % len(val)) if val else "NOT set"
        print("    %-26s %s" % (var, state))
    if not os.environ.get("LINKEDIN_ACCESS_TOKEN"):
        print(
            "    -> every tool will return a clean 'LINKEDIN_ACCESS_TOKEN is not set'"
            " error until you set it. See SETUP.md step 7."
        )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Register linkedin MCP at Claude user scope."
    )
    ap.add_argument(
        "--apply", action="store_true", help="actually write (needs Claude closed)"
    )
    ap.add_argument(
        "--check", action="store_true", help="read-only preflight (default)"
    )
    ap.add_argument(
        "--enable", action="store_true", help="leave the server switched ON"
    )
    ap.add_argument("--remove", action="store_true", help="unregister the server")
    args = ap.parse_args()
    do_write = args.apply and not args.check

    print("=" * 72)
    print("linkedin MCP -- user-scope registration")
    print("  target surface : %s  (root 'mcpServers')" % CLAUDE_JSON)
    print(
        "  mode           : %s"
        % ("APPLY (writes)" if do_write else "CHECK (read-only)")
    )
    print("=" * 72)

    # ---- 1. paths -------------------------------------------------------
    print("\n1. Paths")
    if not os.path.isfile(CLAUDE_JSON):
        fail("%s does not exist" % CLAUDE_JSON)
    print(OK + "%s exists (%d bytes)" % (CLAUDE_JSON, os.path.getsize(CLAUDE_JSON)))
    entry = load_roster_entry()
    print(OK + "roster entry found in %s" % ROSTER)
    cmd, cargs = entry["command"], entry.get("args", [])
    for label, path in [("command", cmd)] + [
        ("args[%d]" % i, a) for i, a in enumerate(cargs)
    ]:
        if os.path.isfile(path):
            print(OK + "%-9s %s" % (label, path))
        else:
            print(BAD + "%-9s %s  <-- MISSING" % (label, path))
            fail("%s does not exist; fix the roster before applying" % path)
    if shutil.which("claude") is None:
        fail("the 'claude' CLI is not on PATH")
    print(OK + "claude CLI on PATH: %s" % shutil.which("claude"))

    # ---- 2. running-Claude guard ---------------------------------------
    print(
        "\n2. Running-Claude guard (.claude.json is rewritten every ~30s by a live session)"
    )
    procs, nodes = claude_processes(), node_claude_processes()
    print("    claude.exe processes : %d" % len(procs))
    print("    node.exe running CLI : %s" % (nodes if nodes >= 0 else "unknown"))
    busy = bool(procs) or nodes > 0
    if busy:
        print(BAD + "Claude appears to be RUNNING -- any write would be clobbered.")
        if do_write:
            fail("close every Claude window/session, then re-run with --apply")
    else:
        print(OK + "no Claude process detected -- safe to write")

    # ---- 3. current state ----------------------------------------------
    print("\n3. Current state")
    with open(CLAUDE_JSON, encoding="utf-8") as fh:
        data = json.load(fh)
    servers = data.get("mcpServers", {})
    disabled = data.get("disabledMcpServers", []) or []
    print("    user-scope servers registered : %d" % len(servers))
    print(
        "    '%s' registered              : %s" % (SERVER_NAME, SERVER_NAME in servers)
    )
    print(
        "    '%s' in disabledMcpServers   : %s" % (SERVER_NAME, SERVER_NAME in disabled)
    )

    # ---- 4. plan / execute ---------------------------------------------
    print("\n4. %s" % ("Executing" if do_write else "Would execute"))
    add_cmd = ["claude", "mcp", "add", SERVER_NAME, "--scope", "user"]
    for var in CRED_VARS:
        add_cmd += ["-e", "%s=${%s}" % (var, var)]
    add_cmd += ["--", cmd] + list(cargs)
    rm_cmd = ["claude", "mcp", "remove", SERVER_NAME, "-s", "user"]

    if args.remove:
        print("    " + " ".join(rm_cmd))
        if do_write:
            backup_claude_json()
            subprocess.run(rm_cmd, timeout=180)
            print(OK + "removed -- this is the guaranteed-OFF state")
        print("\n%s" % ("DONE" if do_write else "CHECK PASSED (nothing written)"))
        return 0

    print("    %s" % " ".join(rm_cmd) + "      # idempotent cleanup, ok if it errors")
    print("    %s" % " ".join(add_cmd))
    print(
        "    then %s '%s' %s root disabledMcpServers"
        % (
            "remove" if args.enable else "add",
            SERVER_NAME,
            "from" if args.enable else "to",
        )
    )

    if do_write:
        backup_claude_json()
        subprocess.run(rm_cmd, capture_output=True, timeout=180)
        res = subprocess.run(add_cmd, capture_output=True, text=True, timeout=180)
        print("    claude mcp add exit=%d" % res.returncode)
        if res.stdout.strip():
            print("    " + res.stdout.strip().splitlines()[0])
        if res.returncode != 0:
            print(res.stderr.strip()[:500])
            fail("claude mcp add failed -- restore the backup printed above")
        set_disabled(disabled=not args.enable)

        # ---- 5. verify --------------------------------------------------
        print("\n5. Verify")
        with open(CLAUDE_JSON, encoding="utf-8") as fh:
            after = json.load(fh)
        if SERVER_NAME not in after.get("mcpServers", {}):
            fail("'%s' is STILL not in root mcpServers after the add" % SERVER_NAME)
        print(OK + "'%s' present in root mcpServers of %s" % (SERVER_NAME, CLAUDE_JSON))
        got = subprocess.run(
            ["claude", "mcp", "get", SERVER_NAME],
            capture_output=True,
            text=True,
            timeout=180,
        )
        for line in got.stdout.splitlines()[:5]:
            print("    | " + line)

    report_credentials()
    print(
        "\n"
        + (
            "DONE -- start Claude Code and call linkedin_auth_status."
            if do_write
            else "CHECK PASSED (nothing written)."
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
