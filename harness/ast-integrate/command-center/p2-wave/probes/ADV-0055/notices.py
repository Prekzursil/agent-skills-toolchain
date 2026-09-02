"""Built-artifact notice checker for ADV-0055.

Probe 2 may only inspect archive members (zip/tar), never the source
repository tree. A decoy NOTICE in the probe fixtures directory must not
affect the verdict.
"""
from __future__ import annotations

import io
import re
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable

DECOY_CANARY = "DECOY-ADV-0055-SOURCE-NOTICE"

# Member-path evidence that a bundled crypto implementation is inside the
# built artifact (wheel, sdist, plugin zip) — not a source-tree grep.
BUNDLED_MEMBER_RE = re.compile(
    r"(?ix)"
    r"(cryptography/)|"
    r"(libcrypto)|"
    r"(libssl)|"
    r"(libsodium)|"
    r"(/openssl/)|"
    r"(\\openssl\\)|"
    r"(nacl/)|"
    r"(pycryptodome/)|"
    r"(Crypto/Cipher)"
)

OPENSSL_ATTR_RE = re.compile(
    r"(?is)(this product includes software developed by the openssl project)"
    r"|(openssl project for use in the openssl toolkit)"
    r"|(copyright .*openssl)"
    r"|(apache license.*openssl)"
)

EXPORT_NOTICE_RE = re.compile(
    r"(?is)\b(ECCN)\b"
    r"|(5D002|5D992)"
    r"|(export\s+control)"
    r"|(EAR\s+99)"
    r"|(this (product|software) includes cryptographic software)"
    r"|(BIS\s+notification)"
)

NOTICE_MEMBER_RE = re.compile(
    r"(?ix)(^|/)(NOTICE|NOTICE\.txt|EXPORT-CONTROL\.txt|EXPORT_CONTROL\.txt|"
    r"METADATA|LICENSE|LICENSE\.txt)$"
)


def _norm_member(name: str) -> str:
    return name.replace("\\", "/").lstrip("./")


def iter_archive_members(data: bytes, kind: str) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    if kind == "zip":
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = _norm_member(info.filename)
                out.append((name, zf.read(info)))
        return out
    if kind == "tar":
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                name = _norm_member(member.name)
                extracted = tf.extractfile(member)
                payload = extracted.read() if extracted is not None else b""
                out.append((name, payload))
        return out
    raise ValueError(f"unknown archive kind {kind}")


def member_is_bundled_crypto(name: str) -> bool:
    return bool(BUNDLED_MEMBER_RE.search(name.replace("\\", "/")))


def scan_bytes(payload: bytes) -> dict[str, bool]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("latin-1", errors="replace")
    return {
        "openssl_attribution": bool(OPENSSL_ATTR_RE.search(text)),
        "export_classification": bool(EXPORT_NOTICE_RE.search(text)),
        "decoy_canary": DECOY_CANARY in text,
    }


def inspect_archive(data: bytes, kind: str) -> dict:
    members = iter_archive_members(data, kind)
    names = [n for n, _ in members]
    bundled_members = [n for n in names if member_is_bundled_crypto(n)]
    notice_members = [n for n in names if NOTICE_MEMBER_RE.search(n.split("/")[-1]) or NOTICE_MEMBER_RE.search(n)]
    content = {"openssl_attribution": False, "export_classification": False, "decoy_canary": False}
    hits: list[dict] = []
    for name, payload in members:
        flags = scan_bytes(payload)
        if any(flags.values()):
            hits.append({"member": name, **flags})
        for k, v in flags.items():
            content[k] = content[k] or v
    has_bundled = bool(bundled_members)
    required = []
    if has_bundled:
        required = ["openssl_attribution", "export_classification"]
    missing = [r for r in required if not content.get(r)]
    fires = has_bundled and bool(missing)
    return {
        "kind": kind,
        "member_count": len(names),
        "members": names,
        "bundled_crypto_members": bundled_members,
        "notice_named_members": notice_members,
        "content_hits": hits,
        "openssl_attribution": content["openssl_attribution"],
        "export_classification": content["export_classification"],
        "decoy_canary": content["decoy_canary"],
        "has_bundled_crypto": has_bundled,
        "required_notices": required,
        "missing_notices": missing,
        "status": "FIRE" if fires else "SILENT",
    }


def build_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(files):
            zf.writestr(rel.replace("\\", "/"), files[rel])
    return buf.getvalue()


def payload_with_notices() -> dict[str, bytes]:
    return {
        "cryptography/hazmat/bindings/_openssl.so": b"fake-openssl-binding\n",
        "NOTICE": (
            "This product includes software developed by the OpenSSL Project\n"
            "for use in the OpenSSL Toolkit (https://www.openssl.org/).\n"
        ).encode("utf-8"),
        "EXPORT-CONTROL.txt": (
            "This software includes cryptographic software. ECCN 5D002 "
            "(mass-market encryption / ENC). Channel notice for the chosen "
            "release path. EAR 99 does not apply once OpenSSL is bundled.\n"
        ).encode("utf-8"),
        "METADATA": b"Name: acme-signer\nVersion: 1.0.0\n",
    }


def payload_without_notices() -> dict[str, bytes]:
    return {
        "cryptography/hazmat/bindings/_openssl.so": b"fake-openssl-binding\n",
        "METADATA": b"Name: acme-signer\nVersion: 1.0.0\n",
        "README.txt": b"acme-signer release bits without notices.\n",
    }


def payload_platform_hash_only() -> dict[str, bytes]:
    return {
        "plugin/payload.py": b"import hashlib\n\ndef sha256_hex(data):\n    return hashlib.sha256(data).hexdigest()\n",
        "METADATA": b"Name: plugin-packer\nVersion: 1.0.0\n",
    }


def reviewer_from_names(names: Iterable[str], has_bundled: bool) -> dict:
    """Independent of content regex: member basenames only."""
    bases = {n.replace("\\", "/").split("/")[-1] for n in names}
    has_notice = "NOTICE" in bases or "NOTICE.txt" in bases
    has_export = "EXPORT-CONTROL.txt" in bases or "EXPORT_CONTROL.txt" in bases
    missing = []
    if has_bundled:
        if not has_notice:
            missing.append("NOTICE-basename")
        if not has_export:
            missing.append("EXPORT-CONTROL-basename")
    return {
        "method": "archive-member-basenames-only",
        "has_notice_basename": has_notice,
        "has_export_basename": has_export,
        "missing": missing,
        "status": "FIRE" if missing else "SILENT",
    }


def inspect_path(path: Path) -> dict:
    data = path.read_bytes()
    name = path.name.lower()
    kind = "zip" if name.endswith(".zip") or name.endswith(".whl") else "tar"
    return inspect_archive(data, kind)
