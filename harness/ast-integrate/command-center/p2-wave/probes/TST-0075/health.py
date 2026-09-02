#!/usr/bin/env python3
"""Install health-check runner (SUT for TST-0075).

Each sub-check inspects mechanical evidence in an install tree. File
presence of a config is not a green verdict: runtime markers, nonce
match, write-fsync-readback, and content hashes are required.

Aggregate GREEN only when every registered sub-check ran and returned
SUCCESS. Unrun, FAILED, and BLOCKED all refuse GREEN.
"""
from __future__ import annotations

import hashlib
import json
import os
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

SUCCESS = "SUCCESS"
FAILED = "FAILED"
BLOCKED = "BLOCKED"
GREEN = "GREEN"
RED = "RED"
NOT_HEALTHY = "NOT-HEALTHY"

SUBCHECK_IDS = (
    "hooks_loaded",
    "skills_registered",
    "mcp_reachable",
    "router_responding",
    "ledger_writable",
    "cache_valid",
    "deploy_in_sync",
)
SUBCHECK_IDS = SUBCHECK_IDS


@dataclass
class CheckResult:
    id: str
    verdict: str
    evidence: str
    observed: dict = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _plugin(root: Path) -> dict[str, Any]:
    return _read_json(root / "plugin.json")


def check_hooks_loaded(root: Path) -> CheckResult:
    """A hook file on disk is not loaded. Require a runtime marker whose
    sentinel matches the hook body for every declared hook id."""
    plugin = _plugin(root)
    expected = list(plugin.get("hooks") or [])
    manifest_path = root / "hooks" / "manifest.json"
    if not manifest_path.is_file():
        return CheckResult(
            "hooks_loaded",
            FAILED,
            "hooks/manifest.json missing",
            {"expected": expected},
        )
    manifest = _read_json(manifest_path)
    listed = [h.get("id") for h in (manifest.get("hooks") or []) if isinstance(h, dict)]
    missing_decl = [i for i in expected if i not in listed]
    if missing_decl:
        return CheckResult(
            "hooks_loaded",
            FAILED,
            "plugin hook ids missing from hooks/manifest.json",
            {"missing_decl": missing_decl, "listed": listed},
        )
    loaded = []
    problems = []
    for hid in expected:
        body = root / "hooks" / f"{hid}.json"
        marker = root / "hooks" / "runtime" / f"{hid}.loaded.json"
        if not body.is_file():
            problems.append(f"hook-body-absent:{hid}")
            continue
        if not marker.is_file():
            problems.append(f"runtime-marker-absent:{hid}")
            continue
        hook = _read_json(body)
        mark = _read_json(marker)
        if mark.get("hook_id") != hid:
            problems.append(f"marker-id-mismatch:{hid}")
            continue
        if mark.get("sentinel") != hook.get("sentinel"):
            problems.append(f"sentinel-mismatch:{hid}")
            continue
        loaded.append(hid)
    if problems:
        return CheckResult(
            "hooks_loaded",
            FAILED,
            "declared hooks not loaded (runtime marker/sentinel)",
            {"loaded": loaded, "problems": problems, "expected": expected},
        )
    if not expected:
        return CheckResult(
            "hooks_loaded",
            FAILED,
            "plugin declares zero hooks; vacuous load is refused",
            {"expected": expected},
        )
    return CheckResult(
        "hooks_loaded",
        SUCCESS,
        "every declared hook has a matching runtime loaded marker",
        {"loaded": loaded},
    )


def check_skills_registered(root: Path) -> CheckResult:
    plugin = _plugin(root)
    expected = list(plugin.get("skills") or [])
    registry_path = root / "skills" / "registry.json"
    if not registry_path.is_file():
        return CheckResult(
            "skills_registered",
            FAILED,
            "skills/registry.json missing",
            {"expected": expected},
        )
    registry = _read_json(registry_path)
    listed = [
        s.get("id") for s in (registry.get("skills") or []) if isinstance(s, dict)
    ]
    missing_decl = [i for i in expected if i not in listed]
    if missing_decl:
        return CheckResult(
            "skills_registered",
            FAILED,
            "plugin skill ids missing from skills/registry.json",
            {"missing_decl": missing_decl},
        )
    registered = []
    problems = []
    for sid in expected:
        skill_md = root / "skills" / sid / "SKILL.md"
        marker = root / "skills" / "runtime" / f"{sid}.registered.json"
        if not skill_md.is_file() or skill_md.stat().st_size <= 0:
            problems.append(f"skill-md-absent:{sid}")
            continue
        if not marker.is_file():
            problems.append(f"runtime-marker-absent:{sid}")
            continue
        mark = _read_json(marker)
        if mark.get("skill_id") != sid:
            problems.append(f"marker-id-mismatch:{sid}")
            continue
        if mark.get("body_sha256") != _sha256_file(skill_md):
            problems.append(f"body-hash-mismatch:{sid}")
            continue
        registered.append(sid)
    if problems:
        return CheckResult(
            "skills_registered",
            FAILED,
            "declared skills not registered (runtime marker/hash)",
            {"registered": registered, "problems": problems},
        )
    if not expected:
        return CheckResult(
            "skills_registered",
            FAILED,
            "plugin declares zero skills; vacuous register is refused",
            {},
        )
    return CheckResult(
        "skills_registered",
        SUCCESS,
        "every declared skill has a matching runtime registration marker",
        {"registered": registered},
    )


def check_mcp_reachable(root: Path) -> CheckResult:
    plugin = _plugin(root)
    expected = list(plugin.get("mcp_servers") or [])
    servers_path = root / "mcp" / "servers.json"
    if not servers_path.is_file():
        return CheckResult(
            "mcp_reachable",
            FAILED,
            "mcp/servers.json missing",
            {"expected": expected},
        )
    servers = _read_json(servers_path)
    by_id = {
        s.get("id"): s
        for s in (servers.get("servers") or [])
        if isinstance(s, dict) and s.get("id")
    }
    reached = []
    problems = []
    for sid in expected:
        spec = by_id.get(sid)
        if not spec:
            problems.append(f"server-undeclared:{sid}")
            continue
        pong_path = root / "mcp" / "runtime" / f"{sid}.pong.json"
        if not pong_path.is_file():
            problems.append(f"pong-absent:{sid}")
            continue
        pong = _read_json(pong_path)
        if pong.get("server_id") != sid:
            problems.append(f"pong-id-mismatch:{sid}")
            continue
        if pong.get("nonce") != spec.get("nonce"):
            problems.append(f"nonce-mismatch:{sid}")
            continue
        if pong.get("ok") is not True:
            problems.append(f"pong-not-ok:{sid}")
            continue
        reached.append(sid)
    if problems:
        return CheckResult(
            "mcp_reachable",
            FAILED,
            "MCP config present but reachability pong missing or stale",
            {"reached": reached, "problems": problems},
        )
    if not expected:
        return CheckResult(
            "mcp_reachable",
            FAILED,
            "plugin declares zero MCP servers; vacuous reachability refused",
            {},
        )
    return CheckResult(
        "mcp_reachable",
        SUCCESS,
        "every declared MCP server has a nonce-matching pong",
        {"reached": reached},
    )


def check_router_responding(root: Path) -> CheckResult:
    listen_path = root / "router" / "listen.json"
    pong_path = root / "router" / "runtime" / "pong.json"
    if not listen_path.is_file():
        return CheckResult(
            "router_responding",
            FAILED,
            "router/listen.json missing",
            {},
        )
    listen = _read_json(listen_path)
    if not pong_path.is_file():
        return CheckResult(
            "router_responding",
            FAILED,
            "router listen config present but runtime pong absent",
            {"endpoint": listen.get("endpoint")},
        )
    pong = _read_json(pong_path)
    if pong.get("nonce") != listen.get("nonce"):
        return CheckResult(
            "router_responding",
            FAILED,
            "router pong nonce does not match listen nonce (stale/unrelated)",
            {
                "listen_nonce": listen.get("nonce"),
                "pong_nonce": pong.get("nonce"),
            },
        )
    if pong.get("ok") is not True:
        return CheckResult(
            "router_responding",
            FAILED,
            "router pong ok is not true",
            {"pong": pong},
        )
    return CheckResult(
        "router_responding",
        SUCCESS,
        "router runtime pong matches listen nonce",
        {"endpoint": listen.get("endpoint")},
    )


def check_ledger_writable(root: Path) -> CheckResult:
    ledger = root / "ledger"
    if not ledger.exists():
        return CheckResult("ledger_writable", FAILED, "ledger path missing", {})
    if not ledger.is_dir():
        return CheckResult(
            "ledger_writable",
            FAILED,
            "ledger path exists but is not a directory",
            {"kind": "file" if ledger.is_file() else "other"},
        )
    probe = ledger / f".health-write-{os.getpid()}-{id(ledger)}"
    payload = b"TST-0075-ledger-probe\n"
    try:
        fd = os.open(str(probe), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        got = probe.read_bytes()
        if got != payload:
            return CheckResult(
                "ledger_writable",
                FAILED,
                "ledger write readback mismatch",
                {"wrote": len(payload), "read": len(got)},
            )
        return CheckResult(
            "ledger_writable",
            SUCCESS,
            "ledger accepted write+fsync+readback",
            {"bytes": len(payload)},
        )
    except OSError as exc:
        return CheckResult(
            "ledger_writable",
            FAILED,
            f"ledger write failed: {type(exc).__name__}: {exc}",
            {"errno": getattr(exc, "errno", None)},
        )
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def check_cache_valid(root: Path) -> CheckResult:
    index_path = root / "cache" / "index.json"
    if not index_path.is_file():
        return CheckResult("cache_valid", FAILED, "cache/index.json missing", {})
    index = _read_json(index_path)
    files = index.get("files") or {}
    if not isinstance(files, dict) or len(files) < 1:
        return CheckResult(
            "cache_valid",
            FAILED,
            "cache index is empty; vacuous validity refused",
            {},
        )
    mismatches = []
    missing = []
    checked = 0
    for rel, expected_hash in files.items():
        path = root / str(rel)
        if not path.is_file():
            missing.append(rel)
            continue
        live = _sha256_file(path)
        checked += 1
        if live != expected_hash:
            mismatches.append({"path": rel, "index": expected_hash, "live": live})
    if missing or mismatches:
        return CheckResult(
            "cache_valid",
            FAILED,
            "cache index does not match live file bytes",
            {"missing": missing, "mismatches": mismatches, "checked": checked},
        )
    return CheckResult(
        "cache_valid",
        SUCCESS,
        "every cache index hash matches live file bytes",
        {"checked": checked},
    )


def check_deploy_in_sync(root: Path) -> CheckResult:
    plugin = _plugin(root)
    installed_path = root / "deploy" / "installed-version.json"
    manifest_path = root / "deploy" / "manifest.json"
    if not installed_path.is_file():
        return CheckResult(
            "deploy_in_sync",
            FAILED,
            "deploy/installed-version.json missing",
            {"plugin_version": plugin.get("version")},
        )
    installed = _read_json(installed_path)
    if installed.get("version") != plugin.get("version"):
        return CheckResult(
            "deploy_in_sync",
            FAILED,
            "plugin.json version disagrees with deploy/installed-version.json",
            {
                "plugin_version": plugin.get("version"),
                "installed_version": installed.get("version"),
            },
        )
    if not manifest_path.is_file():
        return CheckResult(
            "deploy_in_sync",
            FAILED,
            "deploy/manifest.json missing",
            {},
        )
    manifest = _read_json(manifest_path)
    files = manifest.get("files") or {}
    if not isinstance(files, dict) or len(files) < 1:
        return CheckResult(
            "deploy_in_sync",
            FAILED,
            "deploy manifest is empty; vacuous sync refused",
            {},
        )
    mismatches = []
    missing = []
    for rel, expected_hash in files.items():
        path = root / str(rel)
        if not path.is_file():
            missing.append(rel)
            continue
        live = _sha256_file(path)
        if live != expected_hash:
            mismatches.append({"path": rel, "manifest": expected_hash, "live": live})
    if missing or mismatches:
        return CheckResult(
            "deploy_in_sync",
            FAILED,
            "deploy manifest hashes do not match live files",
            {"missing": missing, "mismatches": mismatches},
        )
    return CheckResult(
        "deploy_in_sync",
        SUCCESS,
        "installed version matches plugin.json and deploy hashes match",
        {"version": plugin.get("version"), "files": len(files)},
    )


CHECKS: dict[str, Callable[[Path], CheckResult]] = {
    "hooks_loaded": check_hooks_loaded,
    "skills_registered": check_skills_registered,
    "mcp_reachable": check_mcp_reachable,
    "router_responding": check_router_responding,
    "ledger_writable": check_ledger_writable,
    "cache_valid": check_cache_valid,
    "deploy_in_sync": check_deploy_in_sync,
}


def safe_run(check_id: str, fn: Callable[[Path], CheckResult], root: Path) -> CheckResult:
    try:
        result = fn(root)
    except Exception as exc:  # noqa: BLE001 — must not swallow into GREEN
        return CheckResult(
            check_id,
            FAILED,
            f"check raised {type(exc).__name__}: {exc}",
            {"traceback": traceback.format_exc()[-1500:]},
        )
    if result.verdict not in {SUCCESS, FAILED, BLOCKED}:
        return CheckResult(
            check_id,
            FAILED,
            f"illegal verdict {result.verdict!r} coerced to FAILED",
            {"illegal": result.verdict},
        )
    return result


def aggregate(
    results: dict[str, CheckResult],
    expected_ids: tuple[str, ...] = SUBCHECK_IDS,
) -> str:
    missing = [i for i in expected_ids if i not in results]
    if missing:
        return RED
    for cid in expected_ids:
        verdict = results[cid].verdict
        if verdict == BLOCKED:
            return NOT_HEALTHY
        if verdict != SUCCESS:
            return RED
    extra_blocked = [
        cid
        for cid, row in results.items()
        if cid not in expected_ids and row.verdict == BLOCKED
    ]
    if extra_blocked:
        return NOT_HEALTHY
    return GREEN


def run_health(
    root: Path,
    expected_ids: tuple[str, ...] = SUBCHECK_IDS,
) -> dict[str, Any]:
    results: dict[str, CheckResult] = {}
    for cid in expected_ids:
        results[cid] = safe_run(cid, CHECKS[cid], Path(root))
    agg = aggregate(results, expected_ids)
    return {
        "root": str(root),
        "aggregate": agg,
        "green": agg == GREEN,
        "subchecks": {cid: results[cid].as_dict() for cid in expected_ids},
        "expected_ids": list(expected_ids),
    }


def always_ok(_root: Path) -> CheckResult:
    """Deliberately inert check: SUCCESS on every tree. Harness must reject."""
    return CheckResult(
        "always_ok",
        SUCCESS,
        "always returns SUCCESS regardless of install state",
        {"inert": True},
    )


def always_failed(_root: Path) -> CheckResult:
    return CheckResult(
        "always_failed",
        FAILED,
        "always returns FAILED regardless of install state",
        {"inert": True},
    )


def blocked_probe(_root: Path) -> CheckResult:
    return CheckResult(
        "blocked_probe",
        BLOCKED,
        "probe could not run (injected BLOCKED control)",
        {},
    )
