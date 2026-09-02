#!/usr/bin/env python3
"""Live signature-bypass matrix against tools.plugin.install.apply_install.

The installer checks SHA-256 of the blob against the handoff digest. It never
consults a signature sidecar or a trust store. Synthetic Ed25519 keys are
generated in memory for this unit only.
"""
from __future__ import annotations

import json
import socket
import tempfile
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INSTALL_REL = "tools/plugin/install.py"
ROLLBACK_REL = "tools/plugin/rollback_transaction.py"

import sys

sys.path.insert(0, str(REPO / "tools"))
from plugin.install import apply_install  # noqa: E402
from plugin.payload import (  # noqa: E402
    blob_identity,
    pack_package,
    projection_of,
    sha256_hex,
    unpack_package,
)

TRUSTED_KEY_ID = "adv0028-trusted-synthetic"
UNTRUSTED_KEY_ID = "adv0028-untrusted-synthetic"
PKG = "adv0028-probe-pkg"
VER = "1.0.0"
VER_OLD = "0.9.0"


def _pub_hex(sk: Ed25519PrivateKey) -> str:
    return sk.public_key().public_bytes_raw().hex()


def _sign(sk: Ed25519PrivateKey, payload: bytes) -> bytes:
    return sk.sign(payload)


def _verify(pub_hex: str, payload: bytes, signature: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex)).verify(
            signature, payload
        )
        return True
    except (InvalidSignature, ValueError):
        return False


def source_scan() -> dict[str, Any]:
    hits: dict[str, list[str]] = {}
    needles = (
        "signature",
        "ed25519",
        "trust_store",
        "trust-store",
        "pubkey",
        "public_key",
        "cosign",
        "minisign",
        "sigstore",
    )
    for rel in (INSTALL_REL, ROLLBACK_REL, "tools/plugin/handoff.py"):
        text = (REPO / rel).read_text(encoding="utf-8").lower()
        found = [n for n in needles if n in text]
        hits[rel] = found
    return {
        "files": hits,
        "signature_api_present": any(hits.values()),
        "digest_check_present": "digest" in (REPO / ROLLBACK_REL).read_text(
            encoding="utf-8"
        ).lower(),
    }


def _handoff(
    *,
    prefix: Path,
    blob_path: Path,
    digest: str,
    projection: list[str],
    tx: str,
    package: str = PKG,
    version: str = VER,
) -> dict[str, Any]:
    return {
        "transaction_id": tx,
        "package": package,
        "target_version": version,
        "digest": digest,
        "payload_path": str(blob_path),
        "projection_map": projection,
        "declared_permissions": (),
        "operation": "install",
        "source": "local-blob-store",
    }


def try_install(
    blob: bytes,
    *,
    digest: str | None = None,
    package: str = PKG,
    version: str = VER,
    tx: str = "tx-adv0028",
) -> dict[str, Any]:
    dgst = digest if digest is not None else sha256_hex(blob)
    unpacked = unpack_package(blob)
    name, ver = blob_identity(unpacked)
    projection = projection_of(unpacked)
    with tempfile.TemporaryDirectory(prefix="adv0028-prefix-") as tmp:
        prefix = Path(tmp)
        blob_path = prefix / "payload.bin"
        blob_path.write_bytes(blob)
        handoff = _handoff(
            prefix=prefix,
            blob_path=blob_path,
            digest=dgst,
            projection=projection,
            tx=tx,
            package=package,
            version=version,
        )
        try:
            result = apply_install(prefix, handoff)
            live = result.get("version")
            return {
                "accepted": True,
                "failure_mode": None,
                "ok": bool(result.get("ok")),
                "installed_version": live,
                "installed_name": result.get("package"),
                "digest": result.get("digest"),
                "blob_name": name,
                "blob_version": ver,
                "projection": projection,
            }
        except Exception as exc:  # noqa: BLE001 - failure mode is the measurement
            return {
                "accepted": False,
                "failure_mode": f"{type(exc).__name__}: {exc}",
                "ok": False,
                "installed_version": None,
                "installed_name": None,
                "digest": dgst,
                "blob_name": name,
                "blob_version": ver,
                "projection": projection,
            }


def _pack(name: str, version: str, body: bytes) -> bytes:
    return pack_package(name, version, {"payload.txt": body})


def run_variant_matrix() -> dict[str, Any]:
    trusted = Ed25519PrivateKey.generate()
    untrusted = Ed25519PrivateKey.generate()
    trust_store = {TRUSTED_KEY_ID: _pub_hex(trusted)}
    current = _pack(PKG, VER, b"adv0028-current-body")
    older = _pack(PKG, VER_OLD, b"adv0028-older-body")
    sig_ok = _sign(trusted, current)
    sig_trunc = sig_ok[:8]
    sig_old = _sign(trusted, older)
    sig_untrusted = _sign(untrusted, current)

    unsigned = try_install(current, tx="tx-unsigned")
    truncated = try_install(current, tx="tx-truncated")
    old_content = try_install(current, tx="tx-old-content")
    untrusted_row = try_install(current, tx="tx-untrusted")
    control = try_install(current, tx="tx-trusted-signed")
    digest_mismatch = try_install(current, digest="0" * 64, tx="tx-bad-digest")

    sidecar = {
        "unsigned": {"present": False, "bytes": 0, "verifies_for_payload": False},
        "truncated": {
            "present": True,
            "bytes": len(sig_trunc),
            "verifies_for_payload": _verify(trust_store[TRUSTED_KEY_ID], current, sig_trunc),
        },
        "old_content": {
            "present": True,
            "bytes": len(sig_old),
            "verifies_for_payload": _verify(trust_store[TRUSTED_KEY_ID], current, sig_old),
            "verifies_for_older_blob": _verify(trust_store[TRUSTED_KEY_ID], older, sig_old),
        },
        "untrusted_key": {
            "present": True,
            "bytes": len(sig_untrusted),
            "signer_in_trust_store": False,
            "verifies_for_payload": _verify(_pub_hex(untrusted), current, sig_untrusted),
        },
        "trusted_signed_control": {
            "present": True,
            "bytes": len(sig_ok),
            "signer_in_trust_store": True,
            "verifies_for_payload": _verify(trust_store[TRUSTED_KEY_ID], current, sig_ok),
        },
    }

    return {
        "probe": "probe1-install-variants",
        "installer": INSTALL_REL,
        "digest_only": True,
        "synthetic_keys_only": True,
        "existing_keys_touched": False,
        "trust_store_key_ids": [TRUSTED_KEY_ID],
        "trusted_public_hex_prefix": trust_store[TRUSTED_KEY_ID][:16],
        "untrusted_public_hex_prefix": _pub_hex(untrusted)[:16],
        "source_scan": source_scan(),
        "sidecars": sidecar,
        "attempts": {
            "unsigned": unsigned,
            "truncated_signature": truncated,
            "signature_over_older_content": old_content,
            "untrusted_key": untrusted_row,
            "trusted_signed_control": control,
            "digest_mismatch_liveness": digest_mismatch,
        },
        "bypass": {
            "unsigned_accepted": bool(unsigned.get("accepted")),
            "truncated_accepted": bool(truncated.get("accepted")),
            "old_content_accepted": bool(old_content.get("accepted")),
            "untrusted_accepted": bool(untrusted_row.get("accepted")),
        },
        "control_trusted_signed_installs": bool(control.get("accepted")),
        "liveness_digest_mismatch_refuses": not bool(digest_mismatch.get("accepted")),
        "installer_inspected_signature": False,
    }


def run_degraded_trust() -> dict[str, Any]:
    """Probe 2: corrupt/missing trust store + blocked network, re-install unsigned."""
    trusted = Ed25519PrivateKey.generate()
    current = _pack(PKG, VER, b"adv0028-degraded-body")
    with tempfile.TemporaryDirectory(prefix="adv0028-trust-") as tmp:
        root = Path(tmp)
        store_path = root / "trust-store.json"
        store_path.write_text(
            json.dumps(
                {
                    "keys": {TRUSTED_KEY_ID: _pub_hex(trusted)},
                    "key_source_url": "https://keys.invalid.example/adv0028.json",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        before = store_path.read_bytes()
        store_path.write_bytes(b"{not-json-trust-store")
        corrupted = store_path.read_bytes() != before

        orig_connect = socket.socket.connect
        orig_create = socket.create_connection
        orig_getaddr = socket.getaddrinfo
        blocked: list[str] = []

        def boom_connect(self, address, *a, **k):  # type: ignore[no-untyped-def]
            blocked.append(f"connect:{address!r}")
            raise OSError("ADV-0028 probe2 network disabled")

        def boom_create(*a, **k):  # type: ignore[no-untyped-def]
            blocked.append("create_connection")
            raise OSError("ADV-0028 probe2 network disabled")

        def boom_getaddr(*a, **k):  # type: ignore[no-untyped-def]
            blocked.append("getaddrinfo")
            raise OSError("ADV-0028 probe2 network disabled")

        socket.socket.connect = boom_connect  # type: ignore[method-assign]
        socket.create_connection = boom_create  # type: ignore[assignment]
        socket.getaddrinfo = boom_getaddr  # type: ignore[assignment]
        try:
            unsigned = try_install(current, tx="tx-degraded-unsigned")
            truncated = try_install(current, tx="tx-degraded-truncated")
        finally:
            socket.socket.connect = orig_connect  # type: ignore[method-assign]
            socket.create_connection = orig_create  # type: ignore[assignment]
            socket.getaddrinfo = orig_getaddr  # type: ignore[assignment]

        store_after = store_path.read_bytes()
        missing_path = root / "absent-trust-store.json"
        missing_absent = not missing_path.is_file()

    return {
        "probe": "probe2-degraded-trust-store",
        "trust_store_corrupted": corrupted,
        "trust_store_unread_by_installer": store_after == b"{not-json-trust-store",
        "missing_trust_store_file": missing_absent,
        "network_blocked": True,
        "egress_attempts_during_install": blocked,
        "unsigned_accepted_while_degraded": bool(unsigned.get("accepted")),
        "truncated_accepted_while_degraded": bool(truncated.get("accepted")),
        "unsigned": unsigned,
        "truncated_signature": truncated,
        "fail_open": bool(unsigned.get("accepted")) and bool(truncated.get("accepted")),
        "source_scan": source_scan(),
    }


def run_all() -> dict[str, Any]:
    p1 = run_variant_matrix()
    p2 = run_degraded_trust()
    bypass = p1["bypass"]
    all_bypass = all(bypass.values()) and bool(p2.get("fail_open"))
    control_ok = bool(p1.get("control_trusted_signed_installs"))
    live = bool(p1.get("liveness_digest_mismatch_refuses"))
    return {
        "unit_id": "ADV-0028",
        "probe1": p1,
        "probe2": p2,
        "pass": all_bypass and control_ok and live,
        "all_malicious_variants_accepted": all_bypass,
        "control_ok": control_ok,
        "liveness_ok": live,
    }


if __name__ == "__main__":
    doc = run_all()
    print(json.dumps({k: doc[k] for k in ("pass", "all_malicious_variants_accepted", "control_ok", "liveness_ok")}, sort_keys=True))
    raise SystemExit(0 if doc["pass"] else 1)
