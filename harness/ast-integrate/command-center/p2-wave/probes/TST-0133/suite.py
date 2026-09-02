"""Fixture suite standing in for B07 registry + package-download clients.

The catalog inputs (`tools/lib/net-allowlist.mjs`, `_USER-PROMPTS.md`) are
absent on this worktree. These tests are the measurable suite: two genuinely
hermetic cases, two undeclared network dependents (one planted URL fetch for
the detector control), and one test that already declares `network`.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from contract import DECLARED_ID, DOWNLOAD_ID, HERMETIC_IDS, PLANTED_ID

# Harness writes the live local HTTP fixture address before running tests.
TARGET: dict[str, object] = {"host": "127.0.0.1", "port": 0}


@dataclass(frozen=True)
class Case:
    id: str
    fn: Callable[[Path], str]
    network: bool
    role: str


def _url(path: str) -> str:
    return f"http://{TARGET['host']}:{int(TARGET['port'])}{path}"


def test_local_index_parse(cache: Path) -> str:
    idx = {"packages": [{"id": "hello-skill@1.0.0", "digest": "abc"}]}
    path = cache / "index.json"
    path.write_text(json.dumps(idx), encoding="utf-8")
    got = json.loads(path.read_text(encoding="utf-8"))
    if got["packages"][0]["id"] != "hello-skill@1.0.0":
        raise AssertionError("index roundtrip mismatch")
    return "pass"


def test_cached_blob_digest(cache: Path) -> str:
    blob = cache / "pkg.bin"
    blob.write_bytes(b"TST-0133-CACHED-BLOB\n")
    digest = hashlib.sha256(blob.read_bytes()).hexdigest()
    if len(digest) != 64:
        raise AssertionError("digest length")
    return f"pass:{digest[:12]}"


def test_planted_url_fetch(cache: Path) -> str:
    # Detector control: deliberately fetches a URL. Comment is not a declaration.
    _ = cache
    url = _url("/registry.json")
    with urllib.request.urlopen(url, timeout=3) as resp:
        body = resp.read()
    if b'"ok": true' not in body:
        raise AssertionError(f"unexpected registry body: {body!r}")
    return "pass"


def test_package_download_get(cache: Path) -> str:
    # Second undeclared network dependent (package-download client).
    # Uses urlopen so a split TCP segment cannot drop the `ok` body.
    _ = cache
    url = _url("/blob")
    with urllib.request.urlopen(url, timeout=3) as resp:
        data = resp.read()
    if b"ok" not in data:
        raise AssertionError("package download returned no fixture bytes")
    return "pass"


def test_declared_healthcheck(cache: Path) -> str:
    _ = cache
    with urllib.request.urlopen(_url("/health"), timeout=3) as resp:
        body = resp.read()
    if b"ok" not in body:
        raise AssertionError("healthcheck failed")
    return "pass"


def cases(extra_network: frozenset[str] | None = None) -> list[Case]:
    """Build the suite. `extra_network` is the remediation set (explicit declarations)."""
    declared = set(extra_network or ())
    rows = [
        Case(HERMETIC_IDS[0], test_local_index_parse, False, "hermetic"),
        Case(HERMETIC_IDS[1], test_cached_blob_digest, False, "hermetic"),
        Case(PLANTED_ID, test_planted_url_fetch, PLANTED_ID in declared, "planted-detector"),
        Case(DOWNLOAD_ID, test_package_download_get, DOWNLOAD_ID in declared, "undeclared-download"),
        Case(DECLARED_ID, test_declared_healthcheck, True, "declared-network"),
    ]
    return rows
