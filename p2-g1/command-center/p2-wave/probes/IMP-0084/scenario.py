"""Shared both-states scenario for the IMP-0084 probes.

Builds a real on-disk install root, a deterministic lockfile over a
two-package index, and fetch factories for the two evidence states:
unmutated (must install) and mutated (must be refused pre-write).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace.lockfile import (  # noqa: E402
    ResolvedPackage,
    filesystem_census,
    generate_lockfile,
)

BLOBS = {
    "alpha": b"alpha-payload-v1",
    "beta": b"beta-payload-v1",
}


def build_index() -> list[ResolvedPackage]:
    return [
        ResolvedPackage(name, "1.0.0", "mem://" + name + "-1.0.0", blob)
        for name, blob in sorted(BLOBS.items())
    ]


def build_lockfile() -> bytes:
    return generate_lockfile(build_index())


def fetch_unmutated(url: str) -> bytes:
    name = url.split("/")[2].split("-")[0]
    return bytes(BLOBS[name])


def fetch_suffix_mutated(url: str) -> bytes:
    """Mutation class 1 (probe1): payload-suffix append."""
    name = url.split("/")[2].split("-")[0]
    return bytes(BLOBS[name]) + b"TAMPERED"


def fetch_xor_mutated(url: str) -> bytes:
    """Mutation class 2 (probe2, the reviewer's own): XOR of first byte."""
    name = url.split("/")[2].split("-")[0]
    blob = bytearray(BLOBS[name])
    blob[0] ^= 0x5A
    return bytes(blob)


def fresh_root() -> tuple[Path, bytes]:
    tmp = Path(tempfile.mkdtemp(prefix="imp0084-"))
    return tmp, build_lockfile()


__all__ = [
    "BLOBS",
    "build_index",
    "build_lockfile",
    "filesystem_census",
    "fetch_unmutated",
    "fetch_suffix_mutated",
    "fetch_xor_mutated",
    "fresh_root",
]
