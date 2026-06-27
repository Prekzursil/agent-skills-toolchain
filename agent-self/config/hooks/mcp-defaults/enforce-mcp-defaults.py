"""
SessionStart hook: enforce default disabled MCP servers for every project.

Reads ~/.claude/.mcp-disabled-defaults.json for the canonical list,
then patches the current project's entry in ~/.claude.json if it's
missing any of those servers in its disabledMcpServers array.

Exit 0 = success (no blocking). Prints a message if it patched anything.
"""

import json
import os
import sys

if os.name == "nt":
    import msvcrt
else:
    import fcntl

HOME = os.path.expanduser("~")
DEFAULTS_FILE = os.path.join(HOME, ".claude", ".mcp-disabled-defaults.json")
CLAUDE_JSON = os.path.join(HOME, ".claude.json")


def load_defaults():
    if not os.path.exists(DEFAULTS_FILE):
        return []
    with open(DEFAULTS_FILE, "r") as f:
        data = json.load(f)
    return data.get("disabledMcpServers", [])


def get_current_project():
    """Best-effort: CWD is the project key Claude Code uses."""
    cwd = os.getcwd().replace("\\", "/")
    return cwd


def patch_project(defaults):
    if not os.path.exists(CLAUDE_JSON):
        return False

    with open(CLAUDE_JSON, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return False

    project_key = get_current_project()
    projects = data.get("projects", {})

    # Try both forward-slash and backslash variants
    entry = projects.get(project_key)
    if entry is None:
        alt_key = project_key.replace("/", "\\")
        entry = projects.get(alt_key)
        if entry is None:
            # Project not yet in .claude.json — will be created on first use
            # Create a minimal entry with our defaults
            projects[project_key] = {"disabledMcpServers": defaults}
            data["projects"] = projects
            _write_claude_json(data)
            return True

    current = set(entry.get("disabledMcpServers", []))
    desired = set(defaults)
    missing = desired - current

    if not missing:
        return False

    # Merge: keep any extra user-disabled servers, add missing defaults
    merged = sorted(current | desired)
    entry["disabledMcpServers"] = merged
    _write_claude_json(data)
    return True


def _write_claude_json(data):
    # Atomic-ish write with file locking (cross-platform)
    tmp = CLAUDE_JSON + ".tmp"
    with open(tmp, "w") as f:
        if os.name == "nt":
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(data, f, indent=2)
        if os.name == "nt":
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    os.replace(tmp, CLAUDE_JSON)


def main():
    defaults = load_defaults()
    if not defaults:
        # No defaults file — nothing to enforce
        sys.exit(0)

    try:
        changed = patch_project(defaults)
        if changed:
            print(
                f"[mcp-defaults] Patched disabledMcpServers for {get_current_project()} ({len(defaults)} servers disabled)"
            )
    except Exception as e:
        # Never block session start — just warn
        print(f"[mcp-defaults] Warning: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
