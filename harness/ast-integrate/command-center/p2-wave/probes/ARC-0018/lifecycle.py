#!/usr/bin/env python3
"""Single-owner PR-ONLY lockfile-pinned package lifecycle walker.

Walks install / update / rollback / uninstall against an in-memory estate.
Marketplace machines can be toggled off without inventing a public registry.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

OPS = ("install", "update", "rollback", "uninstall")

NAMED_MARKETPLACE = (
    "publisher_identity",
    "signing",
    "sbom",
    "advisories",
    "moderation",
    "governance",
    "dispute_process",
)

LIFECYCLE_CORE = (
    "package_unit",
    "local_index",
    "lockfile_pin",
    "digest_verify",
    "op.install",
    "op.update",
    "op.rollback",
    "op.uninstall",
)

OWNER_KEY = b"single-owner-local-key"
PKG_ID = "pkg.owner.skill"


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sign(blob: bytes) -> str:
    return hashlib.sha256(OWNER_KEY + blob).hexdigest()


def _record(version: str, body: str) -> dict[str, Any]:
    blob = body.encode("utf-8")
    return {
        "id": PKG_ID,
        "version": version,
        "bytes": blob,
        "sha256": sha256_bytes(blob),
        "publisher": "owner",
        "signature": sign(blob),
        "sbom": {"files": ["SKILL.md"], "produced_by": "owner"},
        "moderation": "owner-self",
        "tos_accepted": True,
    }


V1 = _record("1.0.0", "skill-body-v1\n")
V2 = _record("2.0.0", "skill-body-v2\n")
OWNER_NOTE = b"owner-authored note that uninstall must preserve\n"

ITEM_SPEC: dict[str, dict[str, Any]] = {
    "publisher_identity": {
        "name": "publisher identity",
        "group": "marketplace",
        "second_party_required": True,
        "purpose": (
            "Namespace/account identity so consumers can distinguish publishers. "
            "Unreachable when the only publisher and the only consumer are the owner."
        ),
    },
    "signing": {
        "name": "signing",
        "group": "marketplace",
        "second_party_required": False,
        "purpose": (
            "Cryptographic signatures beyond the lockfile sha256 pin. Reachable "
            "locally with an owner key; not required for the four lifecycle ops."
        ),
        "adjacent_property": "tamper-evidence if the tree is copied off the owner's disk",
    },
    "sbom": {
        "name": "SBOM",
        "group": "marketplace",
        "second_party_required": True,
        "purpose": (
            "Published bill-of-materials for other consumers to audit a third-party "
            "package. Unreachable: there is no other consumer."
        ),
    },
    "advisories": {
        "name": "advisories",
        "group": "marketplace",
        "second_party_required": True,
        "purpose": (
            "Security-advisory feed over third-party packages. Unreachable: this "
            "estate does not consume a second publisher's packages."
        ),
    },
    "moderation": {
        "name": "moderation",
        "group": "marketplace",
        "second_party_required": True,
        "purpose": (
            "Review of packages submitted by other publishers. Unreachable with "
            "no second publisher."
        ),
    },
    "governance": {
        "name": "governance",
        "group": "marketplace",
        "second_party_required": True,
        "purpose": (
            "Community rules, TOS, and policy for a multi-party marketplace. "
            "Unreachable under PR-ONLY with a single owner."
        ),
    },
    "dispute_process": {
        "name": "dispute process",
        "group": "marketplace",
        "second_party_required": True,
        "purpose": (
            "Takedown / ownership dispute machinery. Unreachable: there is no "
            "third party to dispute with."
        ),
    },
    "package_unit": {
        "name": "versioned package unit",
        "group": "lifecycle",
        "second_party_required": False,
        "purpose": "A versioned payload with a stable id. Install has nothing to place without it.",
    },
    "local_index": {
        "name": "local index",
        "group": "lifecycle",
        "second_party_required": False,
        "purpose": "Directory of available versions. Install cannot resolve a package without it.",
    },
    "lockfile_pin": {
        "name": "lockfile pin",
        "group": "lifecycle",
        "second_party_required": False,
        "purpose": "Records current and previous (id, version, sha256). Rollback has no target without it.",
    },
    "digest_verify": {
        "name": "digest verify",
        "group": "lifecycle",
        "second_party_required": False,
        "purpose": "Refuse install/update when payload sha256 disagrees with the pin/index.",
    },
    "op.install": {
        "name": "install operation",
        "group": "lifecycle",
        "second_party_required": False,
        "purpose": "Places a package into the prefix and writes the lockfile pin.",
    },
    "op.update": {
        "name": "update operation",
        "group": "lifecycle",
        "second_party_required": False,
        "purpose": "Replaces the installed version and pushes the previous pin onto history.",
    },
    "op.rollback": {
        "name": "rollback operation",
        "group": "lifecycle",
        "second_party_required": False,
        "purpose": "Restores the previous lockfile pin and prefix bytes.",
    },
    "op.uninstall": {
        "name": "uninstall operation",
        "group": "lifecycle",
        "second_party_required": False,
        "purpose": "Removes the package from the prefix and must preserve owner data.",
    },
}


def all_features() -> frozenset[str]:
    return frozenset(NAMED_MARKETPLACE + LIFECYCLE_CORE)


def minimal_subset() -> frozenset[str]:
    return frozenset(LIFECYCLE_CORE)


def new_estate(enabled: frozenset[str] | set[str]) -> dict[str, Any]:
    return {
        "enabled": frozenset(enabled),
        "index": {"1.0.0": deepcopy(V1), "2.0.0": deepcopy(V2)},
        "prefix": {},
        "lock": {"current": None, "history": []},
        "owner_data": {PKG_ID: OWNER_NOTE},
    }


def _gate(estate: dict[str, Any], rec: dict[str, Any]) -> str | None:
    enabled = estate["enabled"]
    if "publisher_identity" in enabled and rec.get("publisher") != "owner":
        return "publisher-identity"
    if "signing" in enabled:
        expected = sign(rec["bytes"])
        if rec.get("signature") != expected:
            return "signing"
    if "sbom" in enabled and not rec.get("sbom"):
        return "sbom"
    if "advisories" in enabled:
        pass
    if "moderation" in enabled and rec.get("moderation") not in {"approved", "owner-self"}:
        return "moderation"
    if "governance" in enabled and not rec.get("tos_accepted"):
        return "governance"
    if "dispute_process" in enabled:
        pass
    return None


def _pin(rec: dict[str, Any]) -> dict[str, str]:
    return {"id": rec["id"], "version": rec["version"], "sha256": rec["sha256"]}


def _fail(op: str, reason: str, *, postcondition: bool = False) -> dict[str, Any]:
    return {
        "op": op,
        "ok": False,
        "blocked": not postcondition,
        "postcondition_failed": postcondition,
        "reason": reason,
    }


def _ok(op: str) -> dict[str, Any]:
    return {
        "op": op,
        "ok": True,
        "blocked": False,
        "postcondition_failed": False,
        "reason": "",
    }


def run_op(
    estate: dict[str, Any],
    op: str,
    *,
    version: str | None = None,
    swap_bytes: bool = False,
) -> dict[str, Any]:
    enabled = estate["enabled"]
    if op not in OPS:
        return _fail(op, "unknown-op")
    feat = f"op.{op}"
    if feat not in enabled:
        return _fail(op, feat)

    if op == "install":
        if "package_unit" not in enabled:
            return _fail(op, "package_unit")
        if "local_index" not in enabled:
            return _fail(op, "local_index")
        ver = version or "1.0.0"
        rec = estate["index"].get(ver)
        if rec is None:
            return _fail(op, "not-in-index")
        gate = _gate(estate, rec)
        if gate:
            return _fail(op, gate)
        blob = rec["bytes"]
        if swap_bytes:
            blob = b"SWAPPED-" + blob
        actual = sha256_bytes(blob)
        if "digest_verify" in enabled and actual != rec["sha256"]:
            return _fail(op, "digest-mismatch")
        estate["prefix"][rec["id"]] = blob
        if "lockfile_pin" in enabled:
            cur = estate["lock"]["current"]
            if cur:
                estate["lock"]["history"].append(cur)
            estate["lock"]["current"] = _pin(rec)
        if sha256_bytes(estate["prefix"][rec["id"]]) != rec["sha256"]:
            return _fail(op, "prefix-digest-mismatch", postcondition=True)
        return _ok(op)

    if op == "update":
        if "package_unit" not in enabled:
            return _fail(op, "package_unit")
        if "local_index" not in enabled:
            return _fail(op, "local_index")
        ver = version or "2.0.0"
        rec = estate["index"].get(ver)
        if rec is None:
            return _fail(op, "not-in-index")
        gate = _gate(estate, rec)
        if gate:
            return _fail(op, gate)
        blob = rec["bytes"]
        if swap_bytes:
            blob = b"SWAPPED-" + blob
        actual = sha256_bytes(blob)
        if "digest_verify" in enabled and actual != rec["sha256"]:
            return _fail(op, "digest-mismatch")
        estate["prefix"][rec["id"]] = blob
        if "lockfile_pin" in enabled:
            cur = estate["lock"]["current"]
            if cur:
                estate["lock"]["history"].append(cur)
            estate["lock"]["current"] = _pin(rec)
        if sha256_bytes(estate["prefix"][rec["id"]]) != rec["sha256"]:
            return _fail(op, "prefix-digest-mismatch", postcondition=True)
        return _ok(op)

    if op == "rollback":
        if "lockfile_pin" not in enabled:
            return _fail(op, "lockfile_pin")
        hist = estate["lock"]["history"]
        if not hist:
            return _fail(op, "empty-history")
        prev = hist.pop()
        rec = estate["index"].get(prev["version"])
        if rec is None or rec["sha256"] != prev["sha256"]:
            return _fail(op, "history-not-in-index")
        estate["prefix"][prev["id"]] = rec["bytes"]
        estate["lock"]["current"] = dict(prev)
        if estate["prefix"].get(prev["id"]) != rec["bytes"]:
            return _fail(op, "rollback-bytes-mismatch", postcondition=True)
        return _ok(op)

    # uninstall
    if "lockfile_pin" in enabled:
        cur = estate["lock"]["current"]
        pid = cur["id"] if cur else PKG_ID
    else:
        pid = PKG_ID
    estate["prefix"].pop(pid, None)
    estate["lock"]["current"] = None
    estate["lock"]["history"] = []
    if pid not in estate["owner_data"]:
        return _fail(op, "owner-data-lost", postcondition=True)
    if pid in estate["prefix"]:
        return _fail(op, "package-still-present", postcondition=True)
    return _ok(op)


def walk_four(
    enabled: frozenset[str] | set[str],
    *,
    swap_on_install: bool = False,
) -> list[dict[str, Any]]:
    estate = new_estate(enabled)
    results = [
        run_op(estate, "install", version="1.0.0", swap_bytes=swap_on_install),
        run_op(estate, "update", version="2.0.0"),
        run_op(estate, "rollback"),
        run_op(estate, "uninstall"),
    ]
    results[-1]["owner_data_preserved"] = PKG_ID in estate["owner_data"]
    return results


def broken_ops_if_absent(item: str) -> list[str]:
    """Ops that fail (blocked or postcondition) when item is removed from the full set."""
    enabled = set(all_features())
    if item not in enabled:
        raise KeyError(item)
    enabled.remove(item)
    broken: list[str] = []
    if item == "digest_verify":
        results = walk_four(enabled, swap_on_install=True)
    else:
        results = walk_four(enabled)
    for row in results:
        if not row["ok"]:
            broken.append(row["op"])
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for op in broken:
        if op not in seen:
            seen.add(op)
            out.append(op)
    return out
