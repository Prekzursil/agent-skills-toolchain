#!/usr/bin/env python3
"""SessionStart hook: fast MCP + CLI tool preflight.

EXISTENCE-CHECK ONLY — verifies each stdio MCP server's interpreter/command
EXISTS on disk or on PATH, and that a configurable set of project CLIs are
reachable.  No server spawns, no pings, no auth checks (those stay in
/external-tools-health).

Emits ONE digest to stdout only when something is missing.  Silent on all-OK.
Fail-open by contract (AGENTS.md s6): ANY error exits 0, emits nothing.

Opt-out:
  - Create  C:/Users/Prekzursil/.claude/hooks/tool-preflight/.disabled
  - Or set  PREFLIGHT=off  in env
"""

import json
import os
import shutil
import sys

# ---------------------------------------------------------------------------
# Configuration — edit this list to match the CLIs you want on PATH
# ---------------------------------------------------------------------------
PROJECT_CLIS = [
    "qlty",
    "shellcheck",
    "pydocstyle",
    "semgrep",
    "lizard",
    "ruff",
    "bandit",
    "trivy",
    "gitleaks",
    "gh",
    "rg",
]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HOME = os.path.expanduser("~")
MCP_JSON = os.path.join(HOME, ".mcp.json")
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DISABLED_SENTINEL = os.path.join(THIS_DIR, ".disabled")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cmd_exists(command: str) -> bool:
    """Return True if `command` resolves — absolute path exists OR is on PATH."""
    if os.path.isabs(command):
        return os.path.isfile(command)
    return shutil.which(command) is not None


def _check_mcp_servers(servers: dict) -> list[str]:
    """Return list of human-readable issue strings for dead/missing server commands."""
    issues = []
    for name, cfg in servers.items():
        # Skip URL-based (remote) servers — nothing to check locally
        if "url" in cfg:
            continue
        command = cfg.get("command")
        if not command:
            continue  # Unusual; skip rather than false-positive

        args = cfg.get("args", [])

        # Special case: `cmd /c npx -y <pkg>` or `cmd /c node ...` style
        # The real interpreter is embedded in args after /c — check `cmd` is
        # present (always true on Windows) and that the first meaningful arg
        # binary is on PATH.
        if command.lower() in ("cmd", "cmd.exe"):
            # Find what follows /c; the first real program in args
            try:
                c_idx = next(
                    i for i, a in enumerate(args)
                    if a.lower() in ("/c", "/k")
                )
                delegate = args[c_idx + 1] if c_idx + 1 < len(args) else None
            except StopIteration:
                delegate = None

            if delegate:
                if not _cmd_exists(delegate):
                    issues.append(
                        f"- MCP '{name}': delegate command missing ({delegate!r}) "
                        f"→ install {delegate} or fix PATH"
                    )
            # cmd.exe itself is always present on Windows; no further check
            continue

        # Direct executable (absolute venv path, uvx, node, gh-cli-mcp, etc.)
        if not _cmd_exists(command):
            if os.path.isabs(command):
                hint = "venv broken / rebuild it"
            else:
                hint = f"install {command} or fix PATH"
            issues.append(
                f"- MCP '{name}': interpreter missing ({command!r}) → {hint}"
            )

    return issues


def _check_clis(cli_list: list[str]) -> list[str]:
    """Return issue strings for any CLI not found on PATH."""
    return [
        f"- CLI '{cli}': not on PATH → install or add to PATH"
        for cli in cli_list
        if not shutil.which(cli)
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # Opt-out checks
    if os.path.exists(DISABLED_SENTINEL):
        sys.exit(0)
    if os.environ.get("PREFLIGHT", "").lower() in ("off", "0", "false"):
        sys.exit(0)

    # Read and discard stdin (SessionStart sends a JSON payload we don't need)
    try:
        sys.stdin.read()
    except Exception:
        pass

    # Load ~/.mcp.json
    mcp_issues: list[str] = []
    if os.path.isfile(MCP_JSON):
        try:
            with open(MCP_JSON, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            servers = data.get("mcpServers", {})
            mcp_issues = _check_mcp_servers(servers)
        except Exception:
            pass  # Fail-open: malformed JSON → skip

    cli_issues = _check_clis(PROJECT_CLIS)

    all_issues = mcp_issues + cli_issues
    if not all_issues:
        sys.exit(0)

    n = len(all_issues)
    print(f"## Tool preflight — {n} issue(s):")
    for line in all_issues:
        print(line)
    print(
        "\n_Run `/external-tools-health` for deep ping/auth checks. "
        "This preflight is existence-only._"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-open: never let preflight break session start
        pass
    sys.exit(0)
