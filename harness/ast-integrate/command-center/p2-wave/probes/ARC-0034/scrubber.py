"""A5 harvest scrubber: fail-closed secret gate before a bundle leaves the box.

Detection is prefix + entropy body, PEM markers, and auth-filename membership.
Findings never include a secret body: only a zero-entropy prefix, suffix_len,
rule_id, path, and byte offset. A5-HARVEST-SCRUB-GATE is the contract name.

This gate is the A5 harvest control. The live marketplace scanner is
platform/marketplace/mkt/publish.py (SEC-1 PEM plus SEC-7 entropy).
tools/marketplace/secret_gate.py is not on this worktree.
"""
from __future__ import annotations

import math
import re
import tarfile
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

# Public type tokens. Showing one of these is not showing a secret.
ZERO_ENTROPY_PREFIXES: tuple[str, ...] = (
    "PLANTEDFAKE_",
    "sk-ant-",
    "sk-test-",
    "sk-live-",
    "ghp_",
    "gho_",
    "github_pat_",
    "AKIA",
    "ASIA",
    "xoxb-",
    "xoxp-",
    "AIza",
)

PEM_MARKERS: tuple[tuple[bytes, str], ...] = (
    (b"-----BEGIN PRIVATE KEY-----", "pem-private-key"),
    (b"-----BEGIN RSA PRIVATE KEY-----", "pem-rsa-private"),
    (b"-----BEGIN EC PRIVATE KEY-----", "pem-ec-private"),
    (b"-----BEGIN OPENSSH PRIVATE KEY-----", "openssh-private"),
    (b"-----BEGIN ENCRYPTED PRIVATE KEY-----", "pem-encrypted-private"),
)

AUTH_FILENAMES: frozenset[str] = frozenset(
    {
        ".env",
        ".netrc",
        "accounts.json",
        "credentials.json",
        "credentials",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "application_default_credentials.json",
        "gcloud.json",
    }
)

ARTIFACT_CLASSES: tuple[str, ...] = (
    "receipt-json",
    "transcript-log",
    "harvest-bundle",
)

MIN_BODY_LEN = 16
MIN_BODY_ENTROPY = 3.0
_PREFIX_ALT = "|".join(
    re.escape(p) for p in sorted(ZERO_ENTROPY_PREFIXES, key=len, reverse=True)
)
SECRET_BODY = re.compile(rf"({_PREFIX_ALT})([A-Za-z0-9/+=_\-]{{{MIN_BODY_LEN},}})")


@dataclass(frozen=True)
class Finding:
    path: str
    offset: int
    rule_id: str
    prefix: str
    suffix_len: int
    artifact_class: str


class HarvestSecretRefused(Exception):
    def __init__(self, findings: list[Finding]):
        self.findings = findings
        super().__init__(
            "A5-HARVEST-SCRUB-GATE: "
            + ", ".join(f"{f.rule_id}@{f.path}:{f.offset}" for f in findings)
        )


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    n = len(text)
    counts = Counter(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values() if c)


def matching_prefix(value: str) -> str | None:
    for prefix in ZERO_ENTROPY_PREFIXES:
        if value.startswith(prefix):
            return prefix
    return None


def redact(prefix: str, suffix_len: int) -> str:
    return f"{prefix}<redacted suffix_len={suffix_len}>"


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def scan_bytes(data: bytes, path: str, artifact_class: str) -> list[Finding]:
    found: list[Finding] = []
    text = _decode(data)
    for match in SECRET_BODY.finditer(text):
        body = match.group(2)
        if shannon_entropy(body) < MIN_BODY_ENTROPY:
            continue
        found.append(
            Finding(
                path=path,
                offset=match.start(),
                rule_id="prefix-entropy-body",
                prefix=match.group(1),
                suffix_len=len(body),
                artifact_class=artifact_class,
            )
        )
    for marker, rule_id in PEM_MARKERS:
        start = 0
        while True:
            idx = data.find(marker, start)
            if idx < 0:
                break
            found.append(
                Finding(
                    path=path,
                    offset=idx,
                    rule_id=rule_id,
                    prefix=marker[:8].decode("ascii", errors="replace"),
                    suffix_len=max(0, len(data) - idx - len(marker)),
                    artifact_class=artifact_class,
                )
            )
            start = idx + len(marker)
    found.sort(key=lambda f: (f.path, f.offset, f.rule_id))
    return found


def _basename(path: str) -> str:
    return Path(path.replace("\\", "/")).name


def scan_mapping(
    files: dict[str, bytes], artifact_class: str = "harvest-bundle"
) -> list[Finding]:
    out: list[Finding] = []
    for path in sorted(files):
        if _basename(path) in AUTH_FILENAMES:
            out.append(
                Finding(
                    path=path,
                    offset=0,
                    rule_id="auth-filename",
                    prefix=_basename(path),
                    suffix_len=len(files[path]),
                    artifact_class=artifact_class,
                )
            )
        out.extend(scan_bytes(files[path], path, artifact_class))
    out.sort(key=lambda f: (f.path, f.offset, f.rule_id))
    return out


def scan_tar_bytes(blob: bytes, path: str = "harvest.tar") -> list[Finding]:
    found: list[Finding] = []
    with tarfile.open(fileobj=BytesIO(blob), mode="r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            extracted = tar.extractfile(member)
            data = extracted.read() if extracted is not None else b""
            inner = f"{path}:{member.name}"
            if _basename(member.name) in AUTH_FILENAMES:
                found.append(
                    Finding(
                        path=inner,
                        offset=0,
                        rule_id="auth-filename",
                        prefix=_basename(member.name),
                        suffix_len=len(data),
                        artifact_class="harvest-bundle",
                    )
                )
            found.extend(scan_bytes(data, inner, "harvest-bundle"))
    found.sort(key=lambda f: (f.path, f.offset, f.rule_id))
    return found


def scan_artifact(data: bytes, path: str, artifact_class: str) -> list[Finding]:
    if artifact_class == "harvest-bundle":
        if data[:2] == b"PK" or data[:5] == b"<?xml":
            return scan_bytes(data, path, artifact_class)
        try:
            return scan_tar_bytes(data, path)
        except tarfile.TarError:
            return scan_bytes(data, path, artifact_class)
    return scan_bytes(data, path, artifact_class)


def assert_clean(files: dict[str, bytes], artifact_class: str = "harvest-bundle") -> None:
    findings = scan_mapping(files, artifact_class)
    if findings:
        raise HarvestSecretRefused(findings)


def report_contains_secret_body(report_text: str, secret_body: str) -> bool:
    if not secret_body:
        return False
    return secret_body in report_text


def findings_as_dicts(findings: Iterable[Finding]) -> list[dict]:
    rows = []
    for f in findings:
        rows.append(
            {
                "path": f.path,
                "offset": f.offset,
                "rule_id": f.rule_id,
                "prefix": f.prefix,
                "suffix_len": f.suffix_len,
                "artifact_class": f.artifact_class,
                "redacted": redact(f.prefix, f.suffix_len),
            }
        )
    return rows
