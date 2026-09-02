#!/usr/bin/env python3
"""hygiene_doctor - read-only estate checks, and the one config rewrite that
removes an orphan class instead of reaping it.

    python hygiene_doctor.py [--root DIR] [--home DIR] [--json] [--digest FILE]
    python hygiene_doctor.py rewrite-mcp --config ~/.claude.json [--apply] ...

`doctor` answers the questions the supervisor cannot answer about itself or its
surroundings, without touching anything:

  heartbeat        is the supervisor running at all, how long ago, in which mode
                   (a dead watchdog and a quiet box look identical otherwise)
  runtime-version  are the installed agent CLIs past the releases that fixed
                   their own orphan bugs (Claude Code 2.1.153 for Windows MCP
                   servers surviving a VS Code close)
  wslconfig        are autoMemoryReclaim / sparseVhd under [experimental] - under
                   [wsl2] they are a silent no-op
  mcp-wrappers     which MCP servers are launched through npx / cmd /c / uvx, the
                   grandchild shape libuv hosts cannot tear down (queue Q2)

`rewrite-mcp` resolves those wrappers to the installed entrypoint so the server
becomes the host's DIRECT child (`node.exe <entry.js>`, or the uv tool's own
.exe). It is a dry run by default: it writes `<config>.rewritten.json` and a
diff, and only `--apply` touches the original, after a timestamped backup. JSON
configs only (Claude, Cursor); TOML (Codex, Grok) is scanned but not rewritten,
because rewriting TOML without losing comments needs a library this tool does
not ship - the scan prints the snippet to paste instead.

Every filesystem, command and clock access goes through a Probe so the logic is
fully testable off-Windows; RealProbe is the thin real one.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "process-hygiene-doctor-v1"
SEVERITIES = ("ok", "info", "warn", "action_required")
DIGEST_COOLDOWN_SECONDS = 12 * 3600

# Releases that fixed a runtime's OWN orphan / leak behaviour. Only versions that
# were verified against the vendor changelog are gated; everything else is an
# advisory, because a wrong version gate is worse than none.
KNOWN_FIXES: dict[str, dict[str, Any]] = {
    "claude": {
        "minimum": (2, 1, 153),
        "why": "2.1.153 fixed Claude Code processes not shutting down cleanly when "
        "VS Code closes on Windows (orphaned MCP servers); 2.1.212 fixed a SIGTERM "
        "mid-Bash orphaning the command's process tree",
        "remediation": "update Claude Code to >= 2.1.153 (ideally current); set "
        "DISABLE_AUTOUPDATER=1 in ~/.claude/settings.json env if the updater "
        "process is the leak you see",
    },
    "codex": {
        "minimum": None,
        "why": "Codex PR #19753 added process-group kill and an explicit MCP client "
        "shutdown after one long-lived daemon leaked 492 MCP children",
        "remediation": "confirm the installed build postdates PR #19753 (release "
        "notes); consider one pooled MCP gateway instead of per-session servers",
    },
}

WRAPPER_COMMANDS = {"npx", "npx.cmd", "cmd", "cmd.exe", "uvx", "uvx.exe"}
NPX_VALUE_FLAGS = {"-p", "--package", "-c", "--call"}


@dataclass
class Finding:
    id: str
    severity: str
    summary: str
    remediation: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "summary": self.summary,
            "remediation": self.remediation,
            "detail": self.detail,
        }


# ------------------------------------------------------------------ probes


class RealProbe:
    def exists(self, path) -> bool:
        return pathlib.Path(path).exists()

    def read_text(self, path) -> str:
        return pathlib.Path(path).read_text(encoding="utf-8-sig")

    def write_text(self, path, text: str) -> None:
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def glob(self, root, pattern: str):
        return sorted(pathlib.Path(root).glob(pattern))

    def run(self, args: list[str]) -> tuple[int, str]:
        try:
            completed = subprocess.run(
                args, capture_output=True, text=True, errors="replace", timeout=30
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return 127, ""
        return completed.returncode, (completed.stdout or "") + (completed.stderr or "")

    def now(self) -> int:
        return int(time.time())


def _posix(path) -> str:
    return pathlib.PurePath(str(path)).as_posix()


def default_paths(home: str) -> dict[str, str]:
    home = _posix(home)
    appdata = _posix(os.environ.get("APPDATA") or f"{home}/AppData/Roaming")
    local = _posix(os.environ.get("LOCALAPPDATA") or f"{home}/AppData/Local")
    return {
        "npx_cache": f"{local}/npm-cache/_npx",
        "npm_prefix": f"{appdata}/npm",
        "uv_tools": f"{appdata}/uv/tools",
    }


# ------------------------------------------------------------------ checks


def parse_version(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not match:
        return None
    return tuple(int(part) for part in match.groups() if part is not None)


def check_heartbeat(probe, root: str, interval_minutes: int) -> Finding:
    path = f"{_posix(root)}/state/heartbeat.json"
    if not probe.exists(path):
        return Finding(
            "heartbeat",
            "action_required",
            "the supervisor has never written a heartbeat: it is not running",
            "register it: pwsh -File install_task.ps1 (report-only first), then "
            "Start-ScheduledTask -TaskName ProcessHygiene",
        )
    try:
        beat = json.loads(probe.read_text(path))
        ts = int(beat["ts"])
    except (ValueError, KeyError, TypeError):
        return Finding(
            "heartbeat",
            "action_required",
            "heartbeat.json is unreadable; the last run did not complete its write",
            "read the ledger tail and Task Scheduler history for the failing run",
        )
    age_min = max(0.0, (probe.now() - ts) / 60.0)
    mode = "REPORT-ONLY" if not beat.get("apply") else "enforcing"
    detail = {
        "age_minutes": round(age_min, 1),
        "apply": bool(beat.get("apply")),
        "tier": beat.get("tier"),
    }
    if age_min > 3 * interval_minutes:
        return Finding(
            "heartbeat",
            "action_required",
            f"supervisor heartbeat is stale: last run {age_min:.0f} min ago "
            f"(cadence {interval_minutes} min, mode {mode})",
            "Get-ScheduledTask -TaskName ProcessHygiene | Get-ScheduledTaskInfo; "
            "if disabled or failing, re-run install_task.ps1 and read the ledger tail",
            detail,
        )
    return Finding(
        "heartbeat",
        "ok",
        f"supervisor ran {age_min:.0f} min ago in {mode} mode (tier {beat.get('tier')})",
        ""
        if beat.get("apply")
        else "after a clean dry-run week: pwsh -File install_task.ps1 -Apply",
        detail,
    )


def check_runtime_versions(probe) -> list[Finding]:
    findings = []
    for name, spec in KNOWN_FIXES.items():
        code, output = probe.run([name, "--version"])
        ident = f"runtime-version:{name}"
        if code != 0:
            findings.append(
                Finding(
                    ident,
                    "info",
                    f"{name} not found on PATH (or --version failed)",
                    "",
                    {"exit_code": code},
                )
            )
            continue
        version = parse_version(output)
        minimum = spec["minimum"]
        detail = {
            "installed": output.strip()[:80],
            "minimum": list(minimum) if minimum else None,
        }
        if minimum is None:
            findings.append(
                Finding(
                    ident,
                    "info",
                    f"{name} {output.strip()[:40]}: {spec['why']}",
                    spec["remediation"],
                    detail,
                )
            )
        elif version is None or version < minimum:
            findings.append(
                Finding(
                    ident,
                    "warn",
                    f"{name} {output.strip()[:40]} is below {'.'.join(map(str, minimum))}: {spec['why']}",
                    spec["remediation"],
                    detail,
                )
            )
        else:
            findings.append(
                Finding(
                    ident,
                    "ok",
                    f"{name} {'.'.join(map(str, version))} has the known orphan fixes",
                    "",
                    detail,
                )
            )
    return findings


def check_wslconfig(probe, home: str) -> Finding:
    path = f"{_posix(home)}/.wslconfig"
    if not probe.exists(path):
        return Finding(
            "wslconfig",
            "warn",
            "no .wslconfig: vmmemWSL may grow to 50% of RAM and never hands cache back",
            "copy wslconfig.example to %USERPROFILE%\\.wslconfig and run wsl --shutdown once",
        )
    section = ""
    placement: dict[str, tuple[str, str]] = {}
    for raw in probe.read_text(path).splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            placement[key.lower()] = (section, value)
    misplaced = [
        k
        for k in ("automemoryreclaim", "sparsevhd")
        if k in placement and placement[k][0] != "experimental"
    ]
    if misplaced:
        names = ", ".join(
            {"automemoryreclaim": "autoMemoryReclaim", "sparsevhd": "sparseVhd"}[k]
            for k in misplaced
        )
        return Finding(
            "wslconfig",
            "warn",
            f"{names} sit under [{placement[misplaced[0]][0] or 'no section'}] where WSL ignores them silently",
            "move them under an [experimental] section; memory/processors/swap/vmIdleTimeout stay under [wsl2]",
            {"placement": placement},
        )
    reclaim = placement.get("automemoryreclaim")
    if reclaim is None:
        return Finding(
            "wslconfig",
            "warn",
            ".wslconfig has no autoMemoryReclaim: the guest never returns page cache to Windows",
            "add [experimental]\\nautoMemoryReclaim=dropCache (wslconfig.example explains the trade)",
            {"placement": placement},
        )
    if reclaim[1].lower() == "gradual":
        return Finding(
            "wslconfig",
            "info",
            "autoMemoryReclaim=gradual reclaims slowly and stops short of an empty guest "
            "(a plausible cause of the measured 1.1 GB idle vmmem)",
            "prefer dropCache on a box that lives above 2x commit",
            {"placement": placement},
        )
    return Finding(
        "wslconfig",
        "ok",
        f"autoMemoryReclaim={reclaim[1]} under [experimental]",
        "",
        {"placement": placement},
    )


MCP_CONFIGS = (
    (".claude.json", "json", "mcpServers"),
    (".cursor/mcp.json", "json", "mcpServers"),
    (".codex/config.toml", "toml", "mcp_servers"),
    (".grok/config.toml", "toml", "mcp_servers"),
)


def _servers_in(text: str, kind: str, key: str) -> dict[str, Any]:
    data = json.loads(text) if kind == "json" else tomllib.loads(text)
    servers = data.get(key, {})
    return servers if isinstance(servers, dict) else {}


def _basename(command: str) -> str:
    return command.replace("\\", "/").rsplit("/", 1)[-1].lower()


def is_wrapper(command: str, args: list[str]) -> bool:
    base = _basename(command)
    if base in WRAPPER_COMMANDS:
        return True
    return base in ("uv", "uv.exe") and [a.lower() for a in args[:2]] == ["tool", "run"]


def check_mcp_wrappers(probe, home: str) -> Finding:
    home = _posix(home)
    servers_found = []
    errors = []
    scanned = []
    for rel, kind, key in MCP_CONFIGS:
        path = f"{home}/{rel}"
        if not probe.exists(path):
            continue
        scanned.append(path)
        try:
            servers = _servers_in(probe.read_text(path), kind, key)
        except (ValueError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path}: unreadable ({exc.__class__.__name__})")
            continue
        for name, spec in servers.items():
            if not isinstance(spec, dict) or "command" not in spec:
                continue
            args = [str(a) for a in spec.get("args", [])]
            if is_wrapper(str(spec["command"]), args):
                servers_found.append(
                    {
                        "file": path,
                        "server": name,
                        "command": spec["command"],
                        "args": args,
                        "kind": kind,
                    }
                )
    detail = {"servers": servers_found, "errors": errors, "scanned": scanned}
    if servers_found or errors:
        return Finding(
            "mcp-wrappers",
            "warn",
            f"{len(servers_found)} MCP server(s) launch through a wrapper (npx / cmd /c / uvx): "
            "the real server is a GRANDCHILD of its host and outlives it by design"
            + (f"; {len(errors)} config file(s) unreadable" if errors else ""),
            "python hygiene_doctor.py rewrite-mcp --config <file> (dry run writes "
            "<file>.rewritten.json + a diff; --apply after review). TOML configs: paste the "
            "resolved command/args shown by the dry run of an equivalent JSON entry",
            detail,
        )
    return Finding(
        "mcp-wrappers",
        "ok",
        f"no wrapper-launched MCP servers in {len(scanned)} config file(s)",
        "",
        detail,
    )


def run_checks(
    probe, *, root: str, home: str, interval_minutes: int = 5
) -> list[Finding]:
    findings = [check_heartbeat(probe, root, interval_minutes)]
    findings.extend(check_runtime_versions(probe))
    findings.append(check_wslconfig(probe, home))
    findings.append(check_mcp_wrappers(probe, home))
    return findings


# ------------------------------------------------------------- rewrite-mcp


def _strip_shell(command: str, args: list[str]) -> tuple[str, list[str], bool]:
    if (
        _basename(command) in ("cmd", "cmd.exe")
        and args
        and args[0].lower() in ("/c", "/k")
        and len(args) > 1
    ):
        return args[1], args[2:], True
    return command, args, False


def _split_npx(args: list[str]) -> tuple[str | None, list[str]]:
    """Return (package spec without version, remaining server args)."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in NPX_VALUE_FLAGS:
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        spec = arg
        # strip a trailing @version, keeping a leading @scope
        at = spec.rfind("@")
        if at > 0:
            spec = spec[:at]
        return spec, args[i + 1 :]
    return None, []


def _find_package_dir(probe, pkg: str, npx_cache: str, npm_prefix: str) -> str | None:
    for hit in probe.glob(npx_cache, f"*/node_modules/{pkg}/package.json"):
        return _posix(hit).rsplit("/package.json", 1)[0]
    candidate = f"{_posix(npm_prefix)}/node_modules/{pkg}/package.json"
    if probe.exists(candidate):
        return candidate.rsplit("/package.json", 1)[0]
    return None


def _entry_for(probe, pkg_dir: str, pkg: str) -> tuple[str | None, str]:
    meta = json.loads(probe.read_text(f"{pkg_dir}/package.json"))
    bin_field = meta.get("bin")
    rel: str | None = None
    if isinstance(bin_field, str):
        rel = bin_field
    elif isinstance(bin_field, dict) and bin_field:
        if len(bin_field) == 1:
            rel = next(iter(bin_field.values()))
        else:
            short = pkg.rsplit("/", 1)[-1]
            rel = bin_field.get(short) or bin_field.get(pkg)
            if rel is None:
                return (
                    None,
                    f"package.json bin has several entries {sorted(bin_field)} and none is named {short!r}",
                )
    elif isinstance(meta.get("main"), str):
        rel = meta["main"]
    if rel is None:
        return None, "package.json has neither bin nor main"
    return f"{pkg_dir}/{rel.lstrip('./')}", ""


def rewrite_mcp(
    probe,
    config_path: str,
    *,
    npx_cache: str,
    npm_prefix: str,
    uv_tools: str,
    node: str = "node",
) -> dict[str, Any]:
    original_text = probe.read_text(config_path)
    data = json.loads(original_text)
    rewritten = json.loads(original_text)
    changed: list[str] = []
    unresolved: list[dict[str, str]] = []
    servers = rewritten.get("mcpServers")
    if isinstance(servers, dict):
        for name, spec in servers.items():
            if not isinstance(spec, dict) or "command" not in spec:
                continue
            command, args, shell_stripped = _strip_shell(
                str(spec["command"]), [str(a) for a in spec.get("args", [])]
            )
            base = _basename(command)
            if base in ("npx", "npx.cmd"):
                pkg, rest = _split_npx(args)
                pkg_dir = (
                    _find_package_dir(probe, pkg, npx_cache, npm_prefix)
                    if pkg
                    else None
                )
                if pkg is None or pkg_dir is None:
                    unresolved.append(
                        {
                            "server": name,
                            "hint": f"package {pkg!r} is not installed under {npx_cache} or {npm_prefix}; "
                            f"run `npx -y {pkg}` once (or `npm i -g {pkg}`) so there is an entrypoint to point at",
                        }
                    )
                    continue
                entry, why = _entry_for(probe, pkg_dir, pkg)
                if entry is None:
                    unresolved.append(
                        {
                            "server": name,
                            "hint": f"{pkg}: {why}; set command/args by hand",
                        }
                    )
                    continue
                spec["command"], spec["args"] = node, [entry, *rest]
                changed.append(name)
            elif base in ("uvx", "uvx.exe") or (
                base in ("uv", "uv.exe")
                and [a.lower() for a in args[:2]] == ["tool", "run"]
            ):
                tool_args = args if base.startswith("uvx") else args[2:]
                pkg = next((a for a in tool_args if not a.startswith("-")), None)
                rest = [a for a in tool_args if a != pkg]
                exe = f"{_posix(uv_tools)}/{pkg}/Scripts/{pkg}.exe" if pkg else None
                if exe is None or not probe.exists(exe):
                    unresolved.append(
                        {
                            "server": name,
                            "hint": f"uv tool {pkg!r} is not installed; `uv tool install {pkg}` then rerun",
                        }
                    )
                    continue
                spec["command"], spec["args"] = exe, rest
                changed.append(name)
            elif shell_stripped:
                spec["command"], spec["args"] = command, args
                changed.append(name)
    new_text = json.dumps(rewritten, indent=2) + "\n"
    # Both sides re-serialised the same way, so the diff shows only real changes
    # (never the original file's indentation or trailing-newline habits).
    diff = "".join(
        difflib.unified_diff(
            (json.dumps(data, indent=2) + "\n").splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=config_path,
            tofile=f"{config_path} (rewritten)",
        )
    )
    return {
        "rewritten": rewritten,
        "changed": sorted(changed),
        "unresolved": unresolved,
        "diff": diff,
        "text": new_text,
    }


# ---------------------------------------------------------------------- CLI


def _digest_line(probe, root: str, digest_path: str, findings: list[Finding]) -> None:
    urgent = [f for f in findings if f.severity == "action_required"]
    if not urgent:
        return
    signature = "|".join(sorted(f.id for f in urgent))
    marker = f"{_posix(root)}/state/doctor-digest.json"
    now = probe.now()
    if probe.exists(marker):
        try:
            last = json.loads(probe.read_text(marker))
            if (
                last.get("signature") == signature
                and now - int(last.get("ts", 0)) < DIGEST_COOLDOWN_SECONDS
            ):
                return
        except (ValueError, TypeError):
            pass
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now))
    summary = "; ".join(f.summary for f in urgent)
    line = f"[{stamp}] [process-hygiene-doctor] ACTION_REQUIRED: {summary} | PROPOSE: {urgent[0].remediation}"
    existing = probe.read_text(digest_path) if probe.exists(digest_path) else ""
    probe.write_text(digest_path, existing + line + "\n")
    probe.write_text(marker, json.dumps({"signature": signature, "ts": now}))


def _cmd_doctor(argv: list[str], probe) -> int:
    parser = argparse.ArgumentParser(prog="hygiene_doctor.py")
    parser.add_argument(
        "--root", default=str(pathlib.Path.home() / ".agent-guard" / "process-hygiene")
    )
    parser.add_argument("--home", default=str(pathlib.Path.home()))
    parser.add_argument("--interval-minutes", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--digest",
        default=None,
        help="append one ACTION_REQUIRED line here (12 h cooldown)",
    )
    args = parser.parse_args(argv)
    findings = run_checks(
        probe, root=args.root, home=args.home, interval_minutes=args.interval_minutes
    )
    if args.digest:
        _digest_line(probe, args.root, args.digest, findings)
    urgent = sum(1 for f in findings if f.severity == "action_required")
    if args.json:
        print(
            json.dumps(
                {"schema": SCHEMA, "findings": [f.to_dict() for f in findings]},
                indent=2,
            )
        )
    else:
        for finding in findings:
            print(f"[{finding.severity}] {finding.id}: {finding.summary}")
            if finding.remediation and finding.severity != "ok":
                print(f"         -> {finding.remediation}")
        status = "FAILED" if urgent else "SUCCESS"
        print(
            f"{status}:process-hygiene-doctor findings={len(findings)} action_required={urgent}"
        )
    return 1 if urgent else 0


def _cmd_rewrite(argv: list[str], probe) -> int:
    parser = argparse.ArgumentParser(prog="hygiene_doctor.py rewrite-mcp")
    parser.add_argument("--config", required=True)
    defaults = default_paths(str(pathlib.Path.home()))
    parser.add_argument("--npx-cache", default=defaults["npx_cache"])
    parser.add_argument("--npm-prefix", default=defaults["npm_prefix"])
    parser.add_argument("--uv-tools", default=defaults["uv_tools"])
    parser.add_argument(
        "--node",
        default="node",
        help="node executable to launch entrypoints with (full path recommended)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the config in place after a timestamped backup",
    )
    args = parser.parse_args(argv)
    config = _posix(args.config)
    if not config.lower().endswith(".json"):
        print(
            "FAILED:rewrite-mcp only rewrites JSON configs; for TOML paste the resolved entry by hand"
        )
        return 2
    if not probe.exists(config):
        print(f"FAILED:rewrite-mcp config not found: {config}")
        return 2
    result = rewrite_mcp(
        probe,
        config,
        npx_cache=args.npx_cache,
        npm_prefix=args.npm_prefix,
        uv_tools=args.uv_tools,
        node=args.node,
    )
    print(result["diff"] or "(no changes)")
    print("changed: " + (", ".join(result["changed"]) or "none"))
    print(
        "unresolved: "
        + (", ".join(u["server"] for u in result["unresolved"]) or "none")
    )
    for item in result["unresolved"]:
        print(f"  - {item['server']}: {item['hint']}")
    if args.apply and result["changed"]:
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(probe.now()))
        backup = f"{config}.BEFORE-{stamp}.json"
        probe.write_text(backup, probe.read_text(config))
        probe.write_text(config, result["text"])
        print(f"applied; backup at {backup}")
    else:
        sidecar = f"{config}.rewritten.json"
        probe.write_text(sidecar, result["text"])
        print(f"dry run; rewritten config at {sidecar} (use --apply to write in place)")
    return 1 if result["unresolved"] else 0


def main(argv: list[str] | None = None, probe=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    probe = probe or RealProbe()
    if argv and argv[0] == "rewrite-mcp":
        return _cmd_rewrite(argv[1:], probe)
    return _cmd_doctor(argv, probe)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
