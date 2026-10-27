"""Fixtures and live negative/positive controls for ARC-0020."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from client import PUBLIC_EXECUTE_PATHS, execute_cached
from verify import (
    OWNER_MAC_KEY,
    REFUSE_OVER_PERMISSION,
    REFUSE_PUBLIC_FALLBACK,
    REFUSE_REVOKED,
    REFUSE_SIGNATURE,
    REFUSE_STALE_CRL,
    REFUSE_TYPOSQUAT,
    REFUSE_WRONG_SOURCE,
    sign_package,
    verify_package,
)

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
NOW = 1_700_000_000
CRL_FETCHED = NOW - 60
UNSIGNED_REL = "command-center/p2-wave/probes/ARC-0020/fixtures/unsigned-skill.hello.json"


def base_lockfile(**over: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "allow_public_fallback": False,
        "allowlist_permissions": ["read", "search"],
        "crl_fetched_at": CRL_FETCHED,
        "crl_max_age_s": 3600,
        "packages": {
            "skill.hello": {
                "id": "skill.hello",
                "source_registry": "owner-private-index",
                "version": "1.0.0",
            }
        },
        "registry_id": "owner-private-index",
        "revoked": {},
    }
    doc.update(over)
    return doc


def base_package(**over: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "content": "skill hello body - not executed as code",
        "id": "skill.hello",
        "permissions": ["read"],
        "source_registry": "owner-private-index",
        "version": "1.0.0",
    }
    doc.update(over)
    return doc


def good_package() -> dict[str, Any]:
    return sign_package(base_package(), OWNER_MAC_KEY)


def unsigned_package() -> dict[str, Any]:
    pkg = dict(good_package())
    pkg.pop("signature", None)
    return pkg


def stripped_signature_package() -> dict[str, Any]:
    pkg = dict(good_package())
    pkg["signature"] = "hmac-sha256:" + ("00" * 32)
    return pkg


def ensure_fixtures() -> Path:
    FIX.mkdir(parents=True, exist_ok=True)
    path = FIX / "unsigned-skill.hello.json"
    path.write_text(
        json.dumps(unsigned_package(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (FIX / "good-skill.hello.json").write_text(
        json.dumps(good_package(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _run(pkg: dict[str, Any], lock: dict[str, Any], now: int = NOW) -> dict[str, Any]:
    return verify_package(pkg, lock, now=now, key=OWNER_MAC_KEY)


def run_negative_control() -> dict[str, Any]:
    ensure_fixtures()
    lock = base_lockfile()
    good = _run(good_package(), lock)
    unsigned = _run(unsigned_package(), lock)
    stripped = _run(stripped_signature_package(), lock)
    meta_ok_unsigned = (
        unsigned.get("allow") is not True
        and unsigned.get("reason") == REFUSE_SIGNATURE
        and unsigned.get("step") == "signature"
    )
    meta_ok_stripped = (
        stripped.get("allow") is not True
        and stripped.get("reason") == REFUSE_SIGNATURE
    )
    # Metadata-valid: unsigned package still has id/version/source/permissions.
    unsigned_keys = unsigned_package()
    metadata_fields_present = all(
        k in unsigned_keys for k in ("id", "version", "source_registry", "permissions")
    )
    cached = execute_cached(unsigned_package(), lock, now=NOW, key=OWNER_MAC_KEY)
    return {
        "metadata_fields_present_on_unsigned": metadata_fields_present,
        "metadata_ok_signature_ok_allowed": good.get("allow") is True,
        "metadata_ok_signature_bad_refused": meta_ok_unsigned and meta_ok_stripped,
        "unsigned_reason": unsigned.get("reason"),
        "stripped_reason": stripped.get("reason"),
        "good_reason": good.get("reason"),
        "cached_unsigned_executed": cached.get("executed") is True,
        "cached_unsigned_reason": (cached.get("decision") or {}).get("reason"),
        "silent_loss_file": UNSIGNED_REL,
    }


def run_class_controls() -> dict[str, Any]:
    lock = base_lockfile()
    typo = _run(sign_package(base_package(id="skill.helo")), lock)
    confused = _run(
        sign_package(base_package(source_registry="npmjs.org-public")),
        lock,
    )
    public_on = _run(good_package(), base_lockfile(allow_public_fallback=True))
    over = _run(sign_package(base_package(permissions=["read", "exec"])), lock)
    stale = _run(good_package(), lock, now=NOW + 10_000)
    revoked = _run(good_package(), base_lockfile(revoked={"skill.hello": NOW}))
    return {
        "typosquat_refused": typo.get("reason") == REFUSE_TYPOSQUAT,
        "wrong_source_refused": confused.get("reason") == REFUSE_WRONG_SOURCE,
        "public_fallback_refused": public_on.get("reason") == REFUSE_PUBLIC_FALLBACK,
        "over_permission_refused": over.get("reason") == REFUSE_OVER_PERMISSION,
        "stale_crl_refused": stale.get("reason") == REFUSE_STALE_CRL,
        "revoked_refused": revoked.get("reason") == REFUSE_REVOKED,
    }


def run_all_public_paths() -> dict[str, Any]:
    import client as C

    lock = base_lockfile()
    pkg = good_package()
    bad = unsigned_package()
    results = []
    for name in PUBLIC_EXECUTE_PATHS:
        fn = getattr(C, name)
        ok = fn(pkg, lock, now=NOW, key=OWNER_MAC_KEY)
        refuse = fn(bad, lock, now=NOW, key=OWNER_MAC_KEY)
        results.append(
            {
                "path": name,
                "good_executed": ok.get("executed") is True,
                "unsigned_executed": refuse.get("executed") is True,
                "unsigned_reason": (refuse.get("decision") or {}).get("reason"),
            }
        )
    return {
        "paths": results,
        "all_good_executed": all(r["good_executed"] for r in results),
        "all_unsigned_refused": all(
            (not r["unsigned_executed"]) and r["unsigned_reason"] == REFUSE_SIGNATURE
            for r in results
        ),
    }
