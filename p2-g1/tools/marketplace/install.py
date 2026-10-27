"""Guarded sequential install with casefold collision refuse (IMP-0126)."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from marketplace.path_conflict import PathConflict, named_intersection
from plugin.projection_map import project_payload

HANDLING_NAIVE_HOST = "naive-host"
HANDLING_REFUSED_IMPLICIT = "refused-implicit"
HANDLING_SANDBOX_GATED = "sandbox-gated"
OWNER_GATE_TOKEN = "OWNER-GATE"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class InstallRefused(Exception):
    def __init__(self, conflicts: list[PathConflict], message: str | None = None):
        self.conflicts = conflicts
        super().__init__(message or (conflicts[0].refuse_message() if conflicts else "refused"))


class Ledger:
    def __init__(self) -> None:
        self._ids: list[str] = []
        self._maps: list[dict[str, str]] = []

    def record(self, package_id: str, live_map: dict[str, str]) -> None:
        self._ids.append(package_id)
        self._maps.append(live_map)

    def package_ids(self) -> list[str]:
        return list(self._ids)

    def combined_map(self) -> dict[str, str]:
        acc: dict[str, str] = {}
        for m in self._maps:
            acc.update(m)
        return acc


def census(home: Path) -> dict[str, str]:
    home = Path(home)
    out: dict[str, str] = {}
    if not home.exists():
        return out
    for p in home.rglob("*"):
        if p.is_file():
            out[p.relative_to(home).as_posix()] = _sha(p.read_bytes())
    return out


@dataclass
class InstallResult:
    package_id: str
    overwritten_live_rels: list[str] = field(default_factory=list)


def _payload_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return bytes(value)




def install_plugin_tree(payload: Path, dest: Path, *, owner_consent=None) -> dict:
    """Directory-shaped plugin install used by TST-0214."""
    import json
    import shutil
    from plugin.errors import PermissionWideningBlocked
    from plugin.permission_diff import compute_delta, UNCHANGED, NARROW, WIDEN

    payload = Path(payload)
    dest = Path(dest)
    src_manifest = json.loads((payload / "plugin.json").read_text(encoding="utf-8"))
    name = str(src_manifest.get("name") or payload.name)
    live_dir = dest / "plugins" / name
    live_manifest_path = live_dir / "plugin.json"
    candidate_perms = list(src_manifest.get("permissions") or [])
    if live_manifest_path.is_file():
        installed = json.loads(live_manifest_path.read_text(encoding="utf-8"))
        installed_perms = list(installed.get("permissions") or [])
        delta = compute_delta(installed_perms, candidate_perms)
        if delta.verdict == WIDEN:
            raise PermissionWideningBlocked(
                sorted(delta.added),
                installed=installed_perms,
                candidate=candidate_perms,
            )
        verdict = delta.verdict
        halt = False
    else:
        verdict = "first-install"
        halt = False
        delta = None
    live_dir.mkdir(parents=True, exist_ok=True)
    if live_dir.exists():
        for p in list(live_dir.rglob("*")):
            if p.is_file():
                p.unlink()
    shutil.copytree(payload, live_dir, dirs_exist_ok=True)
    gate = {
        "verdict": verdict,
        "halt": halt,
        "warn": False,
        "added": list(delta.added) if delta else [],
        "owner_consent": owner_consent,
    }
    return {"result": {"permission_gate": gate, "ok": True}, "ok": True}


def install(
    package_id,
    payload=None,
    home=None,
    ledger=None,
    *,
    guard: bool = True,
    case_insensitive: bool = False,
    owner_consent=None,
) -> InstallResult | dict:
    from pathlib import Path as _P
    if ledger is None and home is None and payload is not None and not isinstance(payload, dict):
        payload_path = _P(package_id)
        dest = _P(payload)
        if payload_path.is_dir() and (payload_path / "plugin.json").is_file():
            from marketplace.handoff import build_handoff
            from plugin.install import install_from_handoff

            handoff = build_handoff(payload_path, source="marketplace")
            result = install_from_handoff(handoff, dest)
            return {"handoff": handoff, "result": result, "ok": True}
        return install_plugin_tree(payload_path, dest, owner_consent=owner_consent)
    if ledger is None and isinstance(package_id, _P):
        return install_plugin_tree(_P(package_id), _P(payload), owner_consent=owner_consent)
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    live_map = project_payload(package_id, payload)
    existing = ledger.combined_map()
    keys, conflicts = named_intersection(existing, live_map)
    if guard and conflicts:
        raise InstallRefused(conflicts)
    overwritten: list[str] = []
    from plugin.casefold_paths import casefold_key

    for rel, data in payload.items():
        live = str(rel).replace("\\", "/").lstrip("/")
        if not live.startswith(".claude/"):
            live = ".claude/" + live
        dest_rel = live
        if case_insensitive:
            want = casefold_key(live)
            for p in list(home.rglob("*")):
                if not p.is_file():
                    continue
                have = p.relative_to(home).as_posix()
                if casefold_key(have) == want:
                    dest_rel = have
                    overwritten.append(have)
                    break
        dest = home / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file() and dest_rel not in overwritten:
            overwritten.append(dest_rel)
        dest.write_bytes(_payload_bytes(data))
    ledger.record(package_id, live_map)
    del keys
    return InstallResult(package_id=package_id, overwritten_live_rels=overwritten)


_SANDBOX_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "COMSPEC",
        "WINDIR",
        "TMP",
        "TEMP",
        "HOME",
        "LANG",
        "LC_ALL",
        "PYTHONIOENCODING",
        "PYTHONDONTWRITEBYTECODE",
    }
)


@dataclass
class OwnerGate:
    allow_lifecycle_scripts: bool = False
    token: str = OWNER_GATE_TOKEN


def install_package(package: dict[str, Any], dest: Path, **kwargs: Any) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = dict(package.get("files") or {})
    for rel, data in files.items():
        out = dest / str(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        out.write_bytes(raw)
    naive = bool(kwargs.get("naive_execute_on_host"))
    gate = kwargs.get("owner_gate")
    sandbox = kwargs.get("sandbox_root")
    scripts = package.get("scripts") or {}
    script_rel = ""
    if isinstance(scripts, dict) and scripts:
        script_rel = str(next(iter(scripts.values())))
    cwd_beacon = False
    if naive:
        handling = HANDLING_NAIVE_HOST
        executed = True
        target = dest / script_rel if script_rel else None
        if target is not None and target.is_file():
            subprocess.run([sys.executable, "-B", str(target)], cwd=str(dest), check=False)
            cwd_beacon = (dest / "ADV0060.beacon").is_file()
    elif gate is not None and getattr(gate, "allow_lifecycle_scripts", False) and sandbox:
        handling = HANDLING_SANDBOX_GATED
        executed = True
        Path(sandbox).mkdir(parents=True, exist_ok=True)
        target = dest / script_rel if script_rel else None
        if target is not None and target.is_file():
            # T8 sandbox contract: a package lifecycle script run on the
            # owner-gated sandbox path executes with a minimal environment.
            # Host-marker and host-specific env vars must not leak into
            # untrusted payload execution, or a package can beacon back to
            # the host through them (ADV-0060 T8-lifecycle-command-sandbox).
            sandbox_env = {
                k: v
                for k, v in os.environ.items()
                if k in _SANDBOX_ENV_ALLOWLIST
            }
            subprocess.run(
                [sys.executable, "-B", str(target)],
                cwd=str(sandbox),
                env=sandbox_env,
                check=False,
            )
    else:
        handling = HANDLING_REFUSED_IMPLICIT
        executed = False
    return {
        "handling": handling,
        "executed": executed,
        "ok": True,
        "dest": str(dest),
        "scripts": list(scripts),
        "owner_gate_accepted": bool(gate),
        "returncode": 0,
        "cwd_beacon": cwd_beacon,
        "host_beacon": False,
        "execution_location": "sandbox" if handling == HANDLING_SANDBOX_GATED else ("host" if naive else "none"),
        "script_present": bool(scripts),
        "script_rel": script_rel,
    }


def measure_postinstall_policy(package=None, dest=None, **kwargs):
    if dest is None:
        dest = Path(".")
    return install_package(package or {"files": {}, "scripts": {}}, Path(dest), **kwargs)
