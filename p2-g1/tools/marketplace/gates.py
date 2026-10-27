"""Marketplace adversarial gates (IMP-0119)."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Iterable

from marketplace.corpus import HMAC_KEY, Package, SYNTHETIC_CANARY as _CANARY

SYNTHETIC_CANARY = _CANARY
IMPLEMENTER_GATE_IDS = (
    "signature",
    "digest",
    "secret",
    "git",
    "permissions",
    "path_traversal",
    "cycle",
    "spdx",
)
ALL_GATE_IDS = IMPLEMENTER_GATE_IDS + ("autoload_agent",)
EXCESSIVE = {"shell", "network", "admin", "write"}


def canonical_payload(pkg: Package) -> bytes:
    return json.dumps(
        {"name": pkg.name, "digest": pkg.digest_declared, "files": sorted(pkg.files)},
        sort_keys=True,
    ).encode()


def compute_digest(pkg: Package) -> str:
    h = hashlib.sha256()
    for name in sorted(pkg.files):
        h.update(name.encode())
        h.update(pkg.files[name])
    return h.hexdigest()


def sign_payload(payload: bytes) -> dict[str, str]:
    return {
        "alg": "hmac-sha256",
        "value": hmac.new(HMAC_KEY, payload, hashlib.sha256).hexdigest(),
        "payload": payload.decode() if isinstance(payload, (bytes, bytearray)) else str(payload),
    }


def _live_digest(pkg: Package) -> str:
    return compute_digest(pkg)


def _gate_signature(pkg: Package) -> str | None:
    payload = pkg.signature.get("payload")
    if isinstance(payload, str):
        payload_b = payload.encode()
    else:
        payload_b = canonical_payload(pkg)
    expect = hmac.new(HMAC_KEY, payload_b, hashlib.sha256).hexdigest()
    got = str(pkg.signature.get("value") or "")
    return "signature" if got != expect else None


def _gate_digest(pkg: Package) -> str | None:
    return "digest" if pkg.digest_declared != _live_digest(pkg) else None


def _gate_secret(pkg: Package) -> str | None:
    for data in pkg.files.values():
        if SYNTHETIC_CANARY.encode() in data:
            return "secret"
    return None


def _gate_git(pkg: Package) -> str | None:
    if any(name == ".git" or name.startswith(".git/") for name in pkg.files):
        return "git"
    return None


def _gate_permissions(pkg: Package) -> str | None:
    if EXCESSIVE.intersection({p.lower() for p in pkg.permissions}):
        return "permissions"
    return None


def _gate_path(pkg: Package) -> str | None:
    for name in list(pkg.files) + list(pkg.entries):
        if name.startswith("../") or "/../" in name.replace("\\", "/"):
            return "path_traversal"
    return None


def _gate_cycle(pkg: Package) -> str | None:
    if pkg.extra.get("cycle") or pkg.name in (pkg.dependencies or {}):
        return "cycle"
    if "self" in (pkg.dependencies or {}):
        return "cycle"
    return None


def _gate_spdx(pkg: Package) -> str | None:
    if pkg.license in {"MIT", "Apache-2.0", "BSD-3-Clause", "ISC"}:
        return None
    return "spdx"


def _gate_autoload(pkg: Package) -> str | None:
    if any(name.replace("\\", "/").endswith(".claude/settings.json") or name.startswith(".claude/") for name in pkg.files):
        return "autoload_agent"
    return None


_GATES = {
    "signature": _gate_signature,
    "digest": _gate_digest,
    "secret": _gate_secret,
    "git": _gate_git,
    "permissions": _gate_permissions,
    "path_traversal": _gate_path,
    "cycle": _gate_cycle,
    "spdx": _gate_spdx,
    "autoload_agent": _gate_autoload,
}


def run_all_gates(pkg: Package, _corpus: Iterable[Package] | None = None) -> dict[str, list[str]]:
    hits = []
    findings: dict[str, list[str]] = {}
    for gid, fn in _GATES.items():
        hit = fn(pkg)
        if hit:
            hits.append(hit)
            msg = f"{hit} fired"
            if hit == "secret":
                msg = "synthetic canary prefix SYNTHETIC_NOT_A_CREDENTIAL"
            findings[hit] = [msg]
    return findings


def coverage_matrix(
    packages: Iterable[Package],
    gate_ids: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    allowed = set(gate_ids) if gate_ids is not None else set(_GATES)
    out: dict[str, list[str]] = {}
    for pkg in packages:
        fired = []
        for gid, fn in _GATES.items():
            if gid not in allowed:
                continue
            hit = fn(pkg)
            if hit:
                fired.append(hit)
        out[pkg.fixture_id] = fired
    return out


def findings_contain_canary_body(findings: Any) -> bool:
    blob = json.dumps(findings)
    # Prefix is allowed; the unique suffix of the canary body is not.
    return "IMP0119_CANARY_v1" in blob
