#!/usr/bin/env python3
"""Pinned fixture advisory scanner for REL-0014.

Exit-code contract (the estate measured the opposite and it was a defect):
  0   tool ran, no findings          -> PASS
  1   tool ran, findings present     -> FAIL
  127 command not found / tooling    -> NOT-CHECKED
  other non-zero tooling             -> NOT-CHECKED

Exit 127 must never be read as a clean scan.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SCANNER_NAME = "rel-0014-advisory-scanner"
SCANNER_PIN = "rel-0014-advisory-scanner@1.0.0"
SCANNER_BACKEND = "fixture-advisory-mirror"


def lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(lf_bytes(data)).hexdigest()


def classify_exit(exit_code: int) -> str:
    """Honest classifier. Tooling failures are NOT-CHECKED, never PASS."""
    if exit_code == 0:
        return "PASS"
    if exit_code == 1:
        return "FAIL"
    return "NOT-CHECKED"


def classify_exit_buggy_127_as_clean(exit_code: int) -> str:
    """Measured estate defect: command-not-found (127) was read as a clean scan."""
    if exit_code in (0, 127):
        return "PASS"
    if exit_code == 1:
        return "FAIL"
    return "NOT-CHECKED"


def version_tuple(version: str) -> tuple[int, ...]:
    core = version.split("-", 1)[0].split("+", 1)[0]
    parts: list[int] = []
    for piece in core.split("."):
        digits = ""
        for ch in piece:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def version_cmp(a: str, b: str) -> int:
    ta, tb = version_tuple(a), version_tuple(b)
    n = max(len(ta), len(tb))
    ta = ta + (0,) * (n - len(ta))
    tb = tb + (0,) * (n - len(tb))
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def is_affected(version: str, advisory: dict[str, Any]) -> bool:
    listed = advisory.get("affected_versions") or []
    if version in listed:
        return True
    introduced = str(advisory.get("introduced") or "0.0.0")
    fixed = advisory.get("fixed")
    if not fixed:
        return False
    ge_intro = version_cmp(version, introduced) >= 0
    lt_fixed = version_cmp(version, str(fixed)) < 0
    return ge_intro and lt_fixed


@dataclass
class ScanResult:
    exit_code: int
    classification: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    artifact_sha256: str = ""
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "classification": self.classification,
            "findings": list(self.findings),
            "artifact_sha256": self.artifact_sha256,
            "error": self.error,
        }


def parse_lockfile(artifact_bytes: bytes) -> dict[str, Any]:
    return json.loads(lf_bytes(artifact_bytes).decode("utf-8"))


def match_advisories(
    lockfile: dict[str, Any], advisories: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    packages = lockfile.get("packages") or {}
    findings: list[dict[str, Any]] = []
    for name, meta in packages.items():
        if not isinstance(meta, dict):
            continue
        version = str(meta.get("version") or "")
        ecosystem = str(meta.get("ecosystem") or "")
        if not version:
            continue
        for adv in advisories:
            if str(adv.get("package") or "") != name:
                continue
            adv_eco = str(adv.get("ecosystem") or "")
            if adv_eco and ecosystem and adv_eco != ecosystem:
                continue
            if not is_affected(version, adv):
                continue
            findings.append(
                {
                    "id": adv["id"],
                    "package": name,
                    "version": version,
                    "severity": adv.get("severity"),
                    "summary": adv.get("summary"),
                    "fixed": adv.get("fixed"),
                }
            )
    findings.sort(key=lambda row: (row["package"], row["id"]))
    return findings


def scan_artifact(
    artifact_bytes: bytes,
    expected_sha256: str,
    advisories: list[dict[str, Any]],
    *,
    missing_tool: bool = False,
) -> ScanResult:
    """Scan exact artifact bytes. Hash mismatch refuses rather than scanning the wrong object."""
    actual = sha256_bytes(artifact_bytes)
    if missing_tool:
        return ScanResult(
            exit_code=127,
            classification=classify_exit(127),
            findings=[],
            artifact_sha256=actual,
            error="scanner-not-installed",
        )
    if actual != expected_sha256:
        return ScanResult(
            exit_code=2,
            classification=classify_exit(2),
            findings=[],
            artifact_sha256=actual,
            error="artifact-hash-mismatch",
        )
    try:
        lockfile = parse_lockfile(artifact_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return ScanResult(
            exit_code=2,
            classification=classify_exit(2),
            findings=[],
            artifact_sha256=actual,
            error=f"lockfile-unparseable:{type(exc).__name__}",
        )
    findings = match_advisories(lockfile, advisories)
    if findings:
        code = 1
    else:
        code = 0
    return ScanResult(
        exit_code=code,
        classification=classify_exit(code),
        findings=findings,
        artifact_sha256=actual,
    )
