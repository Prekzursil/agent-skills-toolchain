#!/usr/bin/env python3
"""ADV-0069 measurement library: live BlobStore plus fixture mirror/bundle.

Does not implement IMP-0108/IMP-0109 production export/import. Those units
are absent on this tree; this module measures that absence and the live
content-addressed blob store (IMP-0121) that *does* exist.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MKT = REPO / "tools" / "marketplace"
if str(MKT) not in sys.path:
    sys.path.insert(0, str(MKT))

from blob_store import (  # noqa: E402
    BlobStore,
    CorruptedBlobError,
    digest_bytes,
    list_object_files,
)

PKG_NAME = "adv0069-fixture"
PKG_VERSION = "1.0.0"
PRISTINE_PAYLOAD = b"ADV-0069-pristine-package-payload-v1\nnot-executed\n"
_TAMPER = bytearray(PRISTINE_PAYLOAD)
_TAMPER[0] ^= 0x01
TAMPER_REPLACEMENT = bytes(_TAMPER)

PRODUCTION_CANDIDATES = (
    "tools/marketplace/tests/test_offline_export.py",
    "tools/marketplace/tests/test_offline_import.py",
    "tools/marketplace/tests/test_mirror_conflict.py",
    "tools/marketplace/schema/offline-bundle.schema.json",
    "tools/marketplace/offline.py",
    "tools/marketplace/bundle.py",
    "tools/marketplace/mirror.py",
    "tools/marketplace/export.py",
    "tools/marketplace/import_bundle.py",
)

SYMBOL_NEEDLES = (
    "import_bundle",
    "export_bundle",
    "verify_bundle",
    "offline_bundle",
    "offline export",
)

GATE_IDS = (
    "G01_source_exists",
    "G02_index_parses",
    "G03_package_named",
    "G04_version_named",
    "G05_digest_field_present",
    "G06_digest_sha256_hex",
    "G07_size_declared",
    "G08_blob_file_exists",
    "G09_size_matches",
    "G10_payload_recompute",
    "G11_blobstore_get",
    "G12_trust_anchor_named",
    "G13_no_exec_without_hash",
)

TRUST_ANCHOR_KIND = (
    "sha256 content-address of the package payload "
    "(tools/marketplace/blob_store.py BlobStore.get re-hashes on read)"
)
NOT_A_TRUST_ANCHOR = (
    "a digest or envelope hash computed by the same export process that "
    "could itself be tampered; a bundle that attests its own bytes is not integrity"
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def production_surfaces(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    named = {
        rel: (root / rel).is_file() for rel in PRODUCTION_CANDIDATES
    }
    hits: list[dict[str, str]] = []
    mkt = root / "tools" / "marketplace"
    if mkt.is_dir():
        for path in sorted(mkt.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".json", ".md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(root).as_posix()
            for needle in SYMBOL_NEEDLES:
                if needle in text:
                    hits.append({"path": rel, "needle": needle})
    blob = mkt / "blob_store.py"
    return {
        "named_files_present": named,
        "any_named_offline_or_mirror_module": any(named.values()),
        "symbol_hits": hits,
        "blob_store_present": blob.is_file(),
        "blob_store_path": "tools/marketplace/blob_store.py",
    }


def _gate(gid: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"id": gid, "result": "PASS" if ok else "FAIL", "detail": detail}


@dataclass
class InstallResult:
    channel: str
    state: str
    detected: bool
    declared_digest: str
    observed_digest: str
    blobstore_error: str | None
    gates: list[dict[str, Any]] = field(default_factory=list)
    trust_anchor: str = TRUST_ANCHOR_KIND

    @property
    def all_pass(self) -> bool:
        return bool(self.gates) and all(g["result"] == "PASS" for g in self.gates)

    def as_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "state": self.state,
            "detected": self.detected,
            "declared_digest": self.declared_digest,
            "observed_digest": self.observed_digest,
            "artifact_hash_evidence": {
                "declared_sha256": self.declared_digest,
                "observed_sha256": self.observed_digest,
                "mismatch": self.declared_digest != self.observed_digest,
            },
            "blobstore_error": self.blobstore_error,
            "all_thirteen_gates_pass": self.all_pass,
            "gates_passed": sum(1 for g in self.gates if g["result"] == "PASS"),
            "gates_total": len(self.gates),
            "gates": self.gates,
            "trust_anchor": self.trust_anchor,
        }


def build_pristine_mirror(root: Path) -> dict[str, Any]:
    store_root = root / "store"
    store = BlobStore(store_root)
    digest = store.put(PRISTINE_PAYLOAD, f"install:{PKG_NAME}@{PKG_VERSION}")
    index = {
        "kind": "adv0069-filesystem-mirror",
        "packages": {
            PKG_NAME: {
                "name": PKG_NAME,
                "version": PKG_VERSION,
                "digest": digest,
                "size": len(PRISTINE_PAYLOAD),
                "store": "store",
            }
        },
        "trust_anchor": TRUST_ANCHOR_KIND,
    }
    index_path = root / "index.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return {
        "root": str(root),
        "index_path": str(index_path),
        "store_root": str(store_root),
        "digest": digest,
        "size": len(PRISTINE_PAYLOAD),
        "payload_sha256": sha256_hex(PRISTINE_PAYLOAD),
    }


def tamper_mirror_payload(store_root: Path) -> dict[str, Any]:
    files = list_object_files(store_root)
    if len(files) != 1:
        raise RuntimeError(f"expected one object file, got {files}")
    before = files[0].read_bytes()
    files[0].write_bytes(TAMPER_REPLACEMENT)
    after = files[0].read_bytes()
    return {
        "object_path": files[0].as_posix(),
        "before_sha256": sha256_hex(before),
        "after_sha256": sha256_hex(after),
        "before_bytes": len(before),
        "after_bytes": len(after),
    }


def build_pristine_bundle(root: Path) -> dict[str, Any]:
    payloads = root / "payloads"
    payloads.mkdir(parents=True, exist_ok=True)
    rel = f"payloads/{PKG_NAME}-{PKG_VERSION}.bin"
    payload_path = root / rel
    payload_path.write_bytes(PRISTINE_PAYLOAD)
    digest = sha256_hex(PRISTINE_PAYLOAD)
    entries = [
        {
            "name": PKG_NAME,
            "version": PKG_VERSION,
            "digest": digest,
            "size": len(PRISTINE_PAYLOAD),
            "relpath": rel,
        }
    ]
    envelope = sha256_hex(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    manifest = {
        "kind": "offline-bundle",
        "schema_version": 1,
        "entries": entries,
        "envelope_sha256": envelope,
        "trust_anchor_claim": "envelope_sha256 over entries[] — NOT a payload trust anchor",
    }
    man_path = root / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "root": str(root),
        "manifest_path": str(man_path),
        "payload_path": str(payload_path),
        "digest": digest,
        "envelope_sha256": envelope,
        "manifest_keys": sorted(manifest.keys()),
        "entry_keys": sorted(entries[0].keys()),
        "has_digest_field": True,
    }


def tamper_bundle_payload(bundle_root: Path) -> dict[str, Any]:
    rel = f"payloads/{PKG_NAME}-{PKG_VERSION}.bin"
    path = bundle_root / rel
    before = path.read_bytes()
    path.write_bytes(TAMPER_REPLACEMENT)
    after = path.read_bytes()
    return {
        "payload_path": path.as_posix(),
        "before_sha256": sha256_hex(before),
        "after_sha256": sha256_hex(after),
    }


def _eval_common_gates(
    *,
    source_exists: bool,
    index_obj: Any,
    pkg: dict[str, Any] | None,
    blob_path: Path | None,
    declared_digest: str,
    observed: bytes | None,
    blobstore_ok: bool,
    blobstore_detail: str,
    trust_named: bool,
) -> list[dict[str, Any]]:
    digest_ok = (
        isinstance(declared_digest, str)
        and len(declared_digest) == 64
        and all(c in "0123456789abcdef" for c in declared_digest)
    )
    size = None if pkg is None else pkg.get("size")
    size_declared = isinstance(size, int) and size >= 0
    blob_exists = bool(blob_path and blob_path.is_file())
    observed_len = None if observed is None else len(observed)
    size_matches = (
        size_declared and observed is not None and observed_len == size
    )
    recomputed = sha256_hex(observed) if observed is not None else ""
    recompute_ok = bool(observed is not None and recomputed == declared_digest)
    return [
        _gate(GATE_IDS[0], source_exists, "source directory/index present"),
        _gate(GATE_IDS[1], isinstance(index_obj, dict), "index/manifest parsed as object"),
        _gate(GATE_IDS[2], bool(pkg and pkg.get("name")), "package name present"),
        _gate(GATE_IDS[3], bool(pkg and pkg.get("version")), "version present"),
        _gate(
            GATE_IDS[4],
            bool(pkg and (pkg.get("digest") or pkg.get("sha256"))),
            "digest field present",
        ),
        _gate(GATE_IDS[5], digest_ok, "digest is 64-char lowercase sha256 hex"),
        _gate(GATE_IDS[6], size_declared, "size declared as non-negative int"),
        _gate(GATE_IDS[7], blob_exists, "blob file exists"),
        _gate(GATE_IDS[8], size_matches, f"size matches observed={observed_len} declared={size}"),
        _gate(
            GATE_IDS[9],
            recompute_ok,
            f"recomputed={recomputed or 'none'} declared={declared_digest}",
        ),
        _gate(GATE_IDS[10], blobstore_ok, blobstore_detail),
        _gate(GATE_IDS[11], trust_named, TRUST_ANCHOR_KIND),
        _gate(GATE_IDS[12], True, "payload hashed only; never executed"),
    ]


def install_from_mirror(mirror_root: Path, state: str) -> InstallResult:
    index_path = mirror_root / "index.json"
    store_root = mirror_root / "store"
    source_exists = index_path.is_file() and store_root.is_dir()
    index_obj: Any = None
    if index_path.is_file():
        try:
            index_obj = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            index_obj = None
    pkg = None
    if isinstance(index_obj, dict):
        pkg = (index_obj.get("packages") or {}).get(PKG_NAME)
    declared = ""
    blob_path = None
    observed = None
    if isinstance(pkg, dict):
        declared = str(pkg.get("digest") or "")
        files = list_object_files(store_root)
        blob_path = files[0] if files else None
        if blob_path and blob_path.is_file():
            observed = blob_path.read_bytes()
    bs_ok = False
    bs_err = None
    bs_detail = "BlobStore.get not attempted"
    if declared:
        try:
            data = BlobStore(store_root).get(declared)
            bs_ok = sha256_hex(data) == declared
            bs_detail = f"BlobStore.get({declared[:12]}…) returned {len(data)} bytes"
        except CorruptedBlobError as exc:
            bs_ok = False
            bs_err = f"CorruptedBlobError digest={exc.digest} actual={exc.actual}"
            bs_detail = bs_err
        except Exception as exc:  # pragma: no cover - unexpected
            bs_ok = False
            bs_err = f"{type(exc).__name__}: {exc}"
            bs_detail = bs_err
    observed_digest = sha256_hex(observed) if observed is not None else ""
    gates = _eval_common_gates(
        source_exists=source_exists,
        index_obj=index_obj,
        pkg=pkg if isinstance(pkg, dict) else None,
        blob_path=blob_path,
        declared_digest=declared,
        observed=observed,
        blobstore_ok=bs_ok,
        blobstore_detail=bs_detail,
        trust_named=True,
    )
    mismatch = bool(declared and observed_digest and declared != observed_digest)
    detected = (not bs_ok) or mismatch
    return InstallResult(
        channel="filesystem-mirror+BlobStore",
        state=state,
        detected=detected if state == "tampered" else False,
        declared_digest=declared,
        observed_digest=observed_digest,
        blobstore_error=bs_err,
        gates=gates,
    )


def verify_bundle_envelope_only(bundle_root: Path, state: str) -> InstallResult:
    """Wrong-gate matcher: authenticates declared entry relationships, not payload bytes."""
    man_path = bundle_root / "manifest.json"
    source_exists = man_path.is_file()
    manifest: Any = None
    if man_path.is_file():
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
    pkg = None
    declared = ""
    blob_path = None
    observed = None
    envelope_ok = False
    if isinstance(manifest, dict):
        entries = manifest.get("entries") or []
        pkg = entries[0] if entries else None
        claimed = str(manifest.get("envelope_sha256") or "")
        recomputed_env = sha256_hex(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        envelope_ok = claimed == recomputed_env
    if isinstance(pkg, dict):
        declared = str(pkg.get("digest") or "")
        rel = str(pkg.get("relpath") or "")
        blob_path = bundle_root / rel if rel else None
        if blob_path and blob_path.is_file():
            observed = blob_path.read_bytes()
    observed_digest = sha256_hex(observed) if observed is not None else ""
    # Deliberately skip payload recompute and BlobStore.get — this is the wrong gate.
    gates = _eval_common_gates(
        source_exists=source_exists,
        index_obj=manifest,
        pkg=pkg if isinstance(pkg, dict) else None,
        blob_path=blob_path,
        declared_digest=declared,
        observed=observed,
        blobstore_ok=envelope_ok,
        blobstore_detail=(
            "WRONG-GATE: envelope_sha256 over entries[] only; payload not recomputed"
        ),
        trust_named=False,
    )
    # Force G10/G11/G12 to reflect envelope-only (do not use payload recompute as the gate).
    for g in gates:
        if g["id"] == GATE_IDS[9]:
            g["result"] = "PASS" if envelope_ok else "FAIL"
            g["detail"] = "wrong-gate treats envelope match as payload integrity"
        if g["id"] == GATE_IDS[10]:
            g["result"] = "PASS" if envelope_ok else "FAIL"
            g["detail"] = "wrong-gate: no BlobStore.get"
        if g["id"] == GATE_IDS[11]:
            g["result"] = "FAIL"
            g["detail"] = NOT_A_TRUST_ANCHOR
    detected = False  # envelope-only cannot see payload tamper when entries[] unchanged
    return InstallResult(
        channel="bundle-envelope-only",
        state=state,
        detected=detected,
        declared_digest=declared,
        observed_digest=observed_digest,
        blobstore_error=None,
        gates=gates,
        trust_anchor=NOT_A_TRUST_ANCHOR,
    )


def verify_bundle_recompute(bundle_root: Path, state: str) -> InstallResult:
    """Correct fixture importer: recompute payload sha256; optionally BlobStore.get."""
    man_path = bundle_root / "manifest.json"
    source_exists = man_path.is_file()
    manifest: Any = None
    if man_path.is_file():
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
    pkg = None
    declared = ""
    blob_path = None
    observed = None
    if isinstance(manifest, dict):
        entries = manifest.get("entries") or []
        pkg = entries[0] if entries else None
    if isinstance(pkg, dict):
        declared = str(pkg.get("digest") or "")
        rel = str(pkg.get("relpath") or "")
        blob_path = bundle_root / rel if rel else None
        if blob_path and blob_path.is_file():
            observed = blob_path.read_bytes()
    bs_ok = False
    bs_err = None
    bs_detail = "no production importer; fixture put+get through BlobStore"
    with tempfile.TemporaryDirectory(prefix="adv0069-bs-") as td:
        store = BlobStore(Path(td))
        if observed is not None:
            live = store.put(observed, f"import:{PKG_NAME}@{PKG_VERSION}")
            try:
                got = store.get(declared) if live == declared else store.get(live)
                bs_ok = live == declared and sha256_hex(got) == declared
                if live != declared:
                    bs_ok = False
                    bs_err = (
                        f"payload digest {live} != declared {declared}; "
                        "BlobStore addressed the actual bytes, not the envelope claim"
                    )
                    bs_detail = bs_err
                else:
                    bs_detail = f"fixture BlobStore.get matched declared {declared[:12]}…"
            except CorruptedBlobError as exc:
                bs_ok = False
                bs_err = f"CorruptedBlobError digest={exc.digest} actual={exc.actual}"
                bs_detail = bs_err
    observed_digest = sha256_hex(observed) if observed is not None else ""
    gates = _eval_common_gates(
        source_exists=source_exists,
        index_obj=manifest,
        pkg=pkg if isinstance(pkg, dict) else None,
        blob_path=blob_path,
        declared_digest=declared,
        observed=observed,
        blobstore_ok=bs_ok,
        blobstore_detail=bs_detail,
        trust_named=True,
    )
    mismatch = bool(declared and observed_digest and declared != observed_digest)
    detected = mismatch or (not bs_ok)
    return InstallResult(
        channel="bundle-payload-recompute+BlobStore",
        state=state,
        detected=detected if state == "tampered" else False,
        declared_digest=declared,
        observed_digest=observed_digest,
        blobstore_error=bs_err,
        gates=gates,
    )


def format_digest_fields(obj: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}"
            if str(key).lower() in {
                "digest",
                "sha256",
                "checksum",
                "envelope_sha256",
                "digest_algorithm",
            }:
                found.append(path)
            found.extend(format_digest_fields(val, path))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            found.extend(format_digest_fields(val, f"{prefix}[{i}]"))
    return found
