"""Install-and-smoke journey shared with the canary rig: isolated HOME only."""
from __future__ import annotations

import os
import platform
import pwd
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import host as generic_host  # noqa: E402

OWNER_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
PLUGIN_GOOD = HERE / "fixtures" / "plugin"
PLUGIN_BROKEN = HERE / "fixtures" / "plugin-broken"

CLIENT_BINARIES = {
    "claude-code": ("claude", "claude-code"),
    "codex-cli": ("codex",),
    "antigravity": ("agy", "antigravity"),
    "generic-mcp": (),
}


class IsolationError(RuntimeError):
    pass


def host_os() -> str:
    sysname = platform.system().lower()
    if sysname == "linux":
        return "linux"
    if sysname == "darwin":
        return "macos"
    if sysname.startswith("win"):
        return "windows"
    return sysname


def uname_s() -> str:
    return " ".join(platform.uname())


def assert_isolated(isolated_home: Path) -> None:
    home = isolated_home.resolve()
    if home == OWNER_HOME:
        raise IsolationError(
            f"refusing smoke against owner home {OWNER_HOME}; "
            "canary journey requires a throwaway profile"
        )
    forbidden = [
        OWNER_HOME / ".claude",
        OWNER_HOME / ".codex",
        OWNER_HOME / ".agy",
        OWNER_HOME / ".cursor",
    ]
    for path in forbidden:
        try:
            home.relative_to(path)
            raise IsolationError(f"isolated home {home} sits inside {path}")
        except ValueError:
            pass


def locate_binary(names: tuple[str, ...]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def probe_version(binary: str) -> str:
    try:
        p = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"{binary}: {type(exc).__name__}: {exc}"
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    line = text.splitlines()[0] if text else f"{binary} --version empty"
    return line[:240]


def listing_would_pass(plugin_src: Path, isolated_home: Path) -> bool:
    dest = isolated_home / "opt" / "plugin"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(plugin_src, dest)
    return (dest / "plugin.json").is_file()


def run_journey(
    os_name: str,
    client_id: str,
    declared_version: str,
    isolated_home: Path,
    *,
    plugin_src: Path | None = None,
) -> dict[str, Any]:
    """Execute the identical install-and-smoke journey for one cell.

    Wrong OS or missing client -> status NOT-CHECKED with a named reason.
    Executed cells are PASS or FAIL and always carry the observed build string.
    """
    assert_isolated(isolated_home)
    plugin = plugin_src or PLUGIN_GOOD
    live_os = host_os()
    cell = {
        "os": os_name,
        "client": client_id,
        "declared_version": declared_version,
        "host_os_observed": live_os,
        "uname": uname_s(),
        "owner_home_refused": True,
        "acceptance_signal": "hook-side-effect-file-with-observed-build-string",
        "listing_disqualified": True,
    }
    if os_name != live_os:
        cell.update(
            {
                "status": "NOT-CHECKED",
                "reason": (
                    f"host_os={live_os} uname={uname_s()!r}; cell requires {os_name}; "
                    "no cross-OS runner is reachable on this worktree. "
                    f"Prerequisite: a {os_name} profile (or REL-0004 canary on that OS) "
                    "and the client binary for this cell."
                ),
            }
        )
        return cell

    binaries = CLIENT_BINARIES.get(client_id)
    if binaries is None:
        cell.update(
            {
                "status": "NOT-CHECKED",
                "reason": f"client {client_id!r} is not in the declared support contract",
            }
        )
        return cell

    if client_id != "generic-mcp":
        found = locate_binary(binaries)
        if not found:
            wanted = " or ".join(binaries)
            cell.update(
                {
                    "status": "NOT-CHECKED",
                    "reason": (
                        f"client binary not on PATH (looked for {wanted}); "
                        f"install step that would enable the probe: install {client_id} "
                        f"into an isolated HOME and re-run the install-and-smoke journey. "
                        f"host_os={live_os}."
                    ),
                }
            )
            return cell
        observed = probe_version(found)
        cell.update(
            {
                "status": "NOT-CHECKED",
                "observed_client_build_string": observed,
                "binary": found,
                "reason": (
                    f"binary present at {found} observed_build={observed!r} but this "
                    "unit has no isolated plugin-load adapter that can fire PreToolUse "
                    f"inside {client_id}; a directory listing is not acceptance. "
                    "Prerequisite: REL-0004 canary profile plus a client-native hook probe."
                ),
            }
        )
        return cell

    result = generic_host.smoke(plugin, isolated_home)
    listing = result["listing_ok"]
    cell.update(
        {
            "status": "PASS" if result["pass"] else "FAIL",
            "observed_client_build_string": result["observed_client_build_string"],
            "observed_from_hook": result.get("observed_from_hook"),
            "listing_ok": listing,
            "side_effect_present": result["side_effect_present"],
            "plugin_dest": result["plugin_dest"],
            "reason": (
                "hook side-effect observed"
                if result["pass"]
                else "hook did not write the required side-effect (runtime miss)"
            ),
        }
    )
    if listing and not result["pass"]:
        cell["listing_passes_while_runtime_fails"] = True
    return cell


def both_states(isolated_home: Path) -> dict[str, Any]:
    """Good plugin PASS, broken plugin FAIL; listing passes in both states."""
    good_home = isolated_home / "good"
    bad_home = isolated_home / "bad"
    good_home.mkdir(parents=True, exist_ok=True)
    bad_home.mkdir(parents=True, exist_ok=True)
    good = run_journey("linux", "generic-mcp", "1.0.0", good_home, plugin_src=PLUGIN_GOOD)
    bad = run_journey(
        "linux", "generic-mcp", "1.0.0", bad_home, plugin_src=PLUGIN_BROKEN
    )
    listing_good = listing_would_pass(PLUGIN_GOOD, isolated_home / "list-good")
    listing_bad = listing_would_pass(PLUGIN_BROKEN, isolated_home / "list-bad")
    return {
        "good_status": good.get("status"),
        "bad_status": bad.get("status"),
        "listing_good": listing_good,
        "listing_bad": listing_bad,
        "listing_passes_both_states": listing_good and listing_bad,
        "listing_passes_both_states": listing_good and listing_bad,
        "discriminates": good.get("status") == "PASS" and bad.get("status") == "FAIL",
        "good": good,
        "bad": bad,
    }


# Names used by emit/probes/matrix
IsolationError = IsolationError
OWNER_HOME = OWNER_HOME
assert_isolated = assert_isolated
both_states = both_states
