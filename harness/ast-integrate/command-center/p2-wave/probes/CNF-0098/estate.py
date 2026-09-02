#!/usr/bin/env python3
"""Live macOS-reachability signals for CNF-0098.

Signal A (method=command): Darwin userspace / kernel identity of THIS host,
plus a failed provisioning attempt (sw_vers, tart list).
Signal B (method=file-read): runner catalogue — CI workflows, ssh Host
entries, hypervisor CLIs on PATH, CI runner environment variables.

These are mechanically different: one executes Darwin-only binaries / uname;
the other inventories declared runners and provisioners without asking the
kernel its name as the sole oracle.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HYPERVISORS = ("tart", "anka", "limactl", "prlctl", "orb")
DARWIN_BINARIES = ("/usr/bin/sw_vers", "/usr/bin/xcrun", "/usr/bin/xattr")
SYSTEM_VERSION_PLIST = Path("/System/Library/CoreServices/SystemVersion.plist")


def fingerprint(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _run(argv: list[str], timeout: int = 8) -> dict:
    try:
        p = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "argv": argv,
            "exists": True,
            "exit_code": int(p.returncode),
            "stdout_head": (p.stdout or "")[:400],
            "stderr_head": (p.stderr or "")[:400],
        }
    except FileNotFoundError:
        return {
            "argv": argv,
            "exists": False,
            "exit_code": None,
            "stdout_head": "",
            "stderr_head": "FileNotFoundError",
        }
    except subprocess.TimeoutExpired:
        return {
            "argv": argv,
            "exists": True,
            "exit_code": 124,
            "stdout_head": "",
            "stderr_head": "TIMEOUT",
        }


def _ssh_hosts(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hosts: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0].lower() == "host":
            for token in parts[1:]:
                if token != "*":
                    hosts.append(token)
    return hosts


def _workflow_runs_on(repo: Path) -> list[str]:
    labels: list[str] = []
    wf_dir = repo / ".github" / "workflows"
    if not wf_dir.is_dir():
        return labels
    for path in sorted(wf_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".yml", ".yaml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in text.splitlines():
            stripped = raw.strip().lower()
            if "runs-on:" in stripped or "runs_on:" in stripped:
                labels.append(f"{path.relative_to(repo).as_posix()}:{stripped[:120]}")
    return labels


def signal_command() -> dict:
    """Signal A: execute Darwin-identity commands on this host."""
    if hasattr(os, "uname"):
        uname = os.uname()
    else:
        from collections import namedtuple as _namedtuple

        u = platform.uname()
        _U = _namedtuple("uname_result", "sysname nodename release version machine")
        uname = _U(u.system, u.node, u.release, u.version, u.machine)
    sw_vers = _run(["/usr/bin/sw_vers"])
    tart = _run(["tart", "list"])
    observations = {
        "sysname": uname.sysname,
        "machine": uname.machine,
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "sw_vers": sw_vers,
        "tart_list": tart,
        "system_version_plist_exists": SYSTEM_VERSION_PLIST.is_file(),
        "darwin_binaries_present": {
            p: Path(p).is_file() for p in DARWIN_BINARIES
        },
        "proc_version_exists": Path("/proc/version").is_file(),
    }
    this_host_darwin = (
        uname.sysname == "Darwin"
        or platform.system() == "Darwin"
        or bool(sw_vers.get("exists") and sw_vers.get("exit_code") == 0)
        or SYSTEM_VERSION_PLIST.is_file()
    )
    payload = {
        "id": "S1-command-darwin-identity-and-provision",
        "method": "command",
        "this_host_darwin": this_host_darwin,
        "macos_provisioned": this_host_darwin or (
            tart.get("exists") is True and tart.get("exit_code") == 0
        ),
        "observations": observations,
    }
    payload["fingerprint"] = fingerprint(
        {
            "this_host_darwin": payload["this_host_darwin"],
            "macos_provisioned": payload["macos_provisioned"],
            "sysname": uname.sysname,
            "sw_vers_exists": sw_vers.get("exists"),
            "tart_exists": tart.get("exists"),
            "plist": observations["system_version_plist_exists"],
        }
    )
    payload["observation"] = (
        f"sysname={uname.sysname} this_host_darwin={this_host_darwin} "
        f"sw_vers_exists={sw_vers.get('exists')} tart_exists={tart.get('exists')} "
        f"plist={observations['system_version_plist_exists']}"
    )
    return payload


def signal_catalogue(repo: Path | None = None) -> dict:
    """Signal B: inventory declared runners / provisioners (no uname oracle)."""
    repo = repo or REPO
    runs_on = _workflow_runs_on(repo)
    macos_ci = [
        row
        for row in runs_on
        if "macos" in row.lower() or "darwin" in row.lower()
    ]
    which_hv = {name: shutil.which(name) for name in HYPERVISORS}
    ssh_home = _ssh_hosts(Path.home() / ".ssh" / "config")
    ssh_etc = _ssh_hosts(Path("/etc/ssh/ssh_config"))
    ssh_macos = [
        h
        for h in (ssh_home + ssh_etc)
        if "mac" in h.lower() or "darwin" in h.lower()
    ]
    env = {
        "RUNNER_OS": os.environ.get("RUNNER_OS"),
        "RUNNER_NAME": os.environ.get("RUNNER_NAME"),
        "GITHUB_ACTIONS": os.environ.get("GITHUB_ACTIONS"),
        "CI": os.environ.get("CI"),
    }
    runner_os = (env["RUNNER_OS"] or "").lower()
    env_macos = runner_os in {"macos", "darwin"}
    workflows_dir = repo / ".github" / "workflows"
    payload_core = {
        "workflows_dir_exists": workflows_dir.is_dir(),
        "runs_on_lines": runs_on,
        "macos_ci_lines": macos_ci,
        "hypervisor_which": which_hv,
        "ssh_hosts_non_star": ssh_home + [h for h in ssh_etc if h not in ssh_home],
        "ssh_macos_named_hosts": ssh_macos,
        "env": env,
        "env_macos": env_macos,
    }
    macos_runner_present = bool(macos_ci or ssh_macos or env_macos or any(which_hv.values()))
    payload = {
        "id": "S2-file-read-runner-catalogue",
        "method": "file-read",
        "macos_runner_present": macos_runner_present,
        "observations": payload_core,
    }
    payload["fingerprint"] = fingerprint(
        {
            "workflows_dir_exists": payload_core["workflows_dir_exists"],
            "macos_ci_count": len(macos_ci),
            "ssh_macos": ssh_macos,
            "hypervisor_present": {k: bool(v) for k, v in which_hv.items()},
            "env_macos": env_macos,
        }
    )
    payload["observation"] = (
        f"workflows_dir={payload_core['workflows_dir_exists']} "
        f"macos_ci={len(macos_ci)} ssh_macos={ssh_macos} "
        f"hypervisors={[k for k, v in which_hv.items() if v]} "
        f"env_macos={env_macos}"
    )
    return payload


def macos_reachable(repo: Path | None = None) -> dict:
    s1 = signal_command()
    s2 = signal_catalogue(repo)
    # This host Darwin is sufficient to attempt install+health.
    # A catalogue-only macos runner without this-host Darwin is also sufficient
    # IF we could actually exec there; on this estate we cannot hop, so a
    # catalogue hit without a hop method stays unreachable-for-execution.
    hop = bool(
        s2["observations"]["hypervisor_which"].get("tart")
        or s2["observations"]["ssh_macos_named_hosts"]
    )
    reachable = bool(s1["this_host_darwin"] or (s2["macos_runner_present"] and hop))
    return {
        "reachable": reachable,
        "this_host_darwin": s1["this_host_darwin"],
        "catalogue_macos": s2["macos_runner_present"],
        "hop_available": hop,
        "signal_command": s1,
        "signal_catalogue": s2,
    }
