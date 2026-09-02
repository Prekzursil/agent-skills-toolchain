#!/usr/bin/env python3
"""Secret-free artifact bundles.

A bundle is secret-free iff none of the scanned members contain private-key
PEM markers, AWS-style access-key prefixes, or Authorization Bearer tokens.
Findings never echo the secret body past a short prefix.
"""
from __future__ import annotations

import re
from typing import Mapping

PEM_MARKERS = (
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN PRIVATE KEY-----",
)
AKIA_RE = re.compile(rb"AKIA[0-9A-Z]{16}")
BEARER_RE = re.compile(rb"Authorization:\s*Bearer\s+\S+", re.I)


def scan_member(name: str, raw: bytes) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for marker in PEM_MARKERS:
        if marker in raw:
            hits.append({"member": name, "class": "pem-private-key", "prefix": marker[:12].decode("ascii")})
            break
    if AKIA_RE.search(raw):
        hits.append({"member": name, "class": "aws-access-key-prefix", "prefix": "AKIA"})
    if BEARER_RE.search(raw):
        hits.append({"member": name, "class": "bearer-token", "prefix": "Bearer"})
    return hits


def scan_bundle(members: Mapping[str, bytes]) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    for name in sorted(members):
        findings.extend(scan_member(name, members[name]))
    return {
        "secret_free": len(findings) == 0,
        "findings": findings,
        "members": sorted(members),
    }
