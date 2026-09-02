"""Fixture registry builder: IMP-0118's known-good marketplace registry (also RES-0060).

``build(root)`` materialises a self-contained registry under
``tools/marketplace/fixture/registry`` - ``index.json`` plus content-addressed
blobs - holding nine packages that together exercise every feature in
:data:`tools.marketplace.features.DECLARED_FEATURES`: all of them signed under the
documented non-credential fixture key, a ``hello-skill`` version pair, a
dependency edge (``dep-consumer`` -> ``hello-lib``), an SBOM, benchmark evidence
with reproduction fields, a deprecation with a successor pointer, and a
stable/canary channel-pin pair.  Everything is deterministic: fixed payload
bytes, canonical JSON manifests, HMAC signatures under a fixed key, packages
sorted by id, no timestamps, no absolute paths.  The index carries no
popularity, install or download keys (RES-0060 depends on that).

The two ``hello-skill`` payloads are byte-for-byte the original fixture bodies:
IMP-0118 probe 1 unlinks the 1.0.0 blob (``DANGLING_BLOB``) and patches the
phrase "Newer skill version" inside the 1.1.0 blob (``DIGEST_MISMATCH``).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.marketplace.crypto import ALGORITHM, FIXTURE_KEY_ID, sign_payload
from tools.marketplace.features import channel_of, split_package_id
from tools.marketplace.storage import digest_bytes, read_json, registry_dir

__all__ = [
    "FIXTURE_REGISTRY_ID",
    "INDEX_SCHEMA",
    "MANIFEST_SCHEMA",
    "PACKAGE_SPECS",
    "build",
    "load_payloads",
    "manifest_bytes",
    "payload_for",
]

INDEX_SCHEMA = "marketplace-index/v1"
FIXTURE_REGISTRY_ID = "reg:imp-0118-fixture"
MANIFEST_SCHEMA = "marketplace-package-manifest/v1"

#: What the fixture contains.  ``payload`` is a raw blob body; ``manifest`` is
#: rendered to canonical JSON by :func:`manifest_bytes`.  ``features`` are the
#: labels the index advertises - the coverage matrix re-derives them from the
#: structure and reports any disagreement, so keep the two in step.
PACKAGE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "hello-skill@1.0.0",
        "features": ("signed", "multi-version"),
        "payload": b"hello skill v1 payload\n",
    },
    {
        "id": "hello-skill@1.1.0",
        "features": ("signed", "multi-version"),
        "payload": b"Newer skill version payload\n",
    },
    {
        "id": "hello-lib@1.0.0",
        "features": ("signed",),
        "manifest": {
            "kind": "library",
            "description": "Leaf library that dep-consumer depends on.",
        },
    },
    {
        "id": "dep-consumer@1.0.0",
        "features": ("signed", "with-dependencies"),
        "dependencies": ("hello-lib@1.0.0",),
        "manifest": {
            "kind": "skill",
            "description": "Consumes hello-lib through a declared dependency edge.",
        },
    },
    {
        "id": "sbom-kit@1.0.0",
        "features": ("signed", "with-sbom"),
        "manifest": {
            "kind": "kit",
            "sbom": {
                "format": "cyclonedx-lite/1",
                "components": [
                    {
                        "name": "hello-lib",
                        "version": "1.0.0",
                        "purl": "pkg:fixture/hello-lib@1.0.0",
                    },
                    {
                        "name": "json-stdlib",
                        "version": "3.12",
                        "purl": "pkg:generic/python-json@3.12",
                    },
                ],
            },
        },
    },
    {
        "id": "bench-kit@1.0.0",
        "features": ("signed", "with-benchmark-evidence"),
        "manifest": {
            "kind": "kit",
            "benchmark": {
                "suite": "fixture-bench/v1",
                "metric": "latency_ms_p50",
                "value": 12.5,
                "unit": "ms",
                "reproduction": {
                    "command": "python3 -B tools/marketplace/tests/test_fixture_registry.py",
                    "seed": 7,
                    "runs": 3,
                    "environment": "hermetic-no-egress",
                },
            },
        },
    },
    {
        "id": "old-skill@0.9.0",
        "features": ("signed", "deprecated"),
        "manifest": {
            "kind": "skill",
            "deprecated": {
                "since": "1.0.0",
                "successor": "hello-skill@1.1.0",
                "reason": "renamed to hello-skill",
            },
        },
    },
    {
        "id": "stable-kit@1.0.0",
        "features": ("signed", "channel-pinned"),
        "manifest": {"kind": "kit", "channel_pin": "stable"},
    },
    {
        "id": "canary-kit@2.0.0-canary.1",
        "features": ("signed", "channel-pinned"),
        "manifest": {"kind": "kit", "channel_pin": "canary"},
    },
)


def manifest_bytes(package_id: str, fields: dict[str, Any], dependencies: tuple[str, ...] = ()) -> bytes:
    """Canonical JSON manifest body for ``package_id`` (sorted keys, 2-space indent, LF)."""
    name, version = split_package_id(package_id)
    doc: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "name": name,
        "version": version,
        "channel": channel_of(version),
    }
    if dependencies:
        doc["dependencies"] = [
            {"name": split_package_id(d)[0], "version": split_package_id(d)[1]} for d in dependencies
        ]
    for key, value in fields.items():
        if key in doc:
            raise ValueError(f"{package_id}: manifest field {key!r} is reserved")
        doc[key] = value
    return (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def payload_for(spec: dict[str, Any]) -> bytes:
    """The blob body of one :data:`PACKAGE_SPECS` entry."""
    if "payload" in spec:
        body = spec["payload"]
        if not isinstance(body, (bytes, bytearray)):
            raise TypeError(f"{spec.get('id')}: payload must be bytes")
        return bytes(body)
    manifest = spec.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError(f"{spec.get('id')}: needs either 'payload' or 'manifest'")
    return manifest_bytes(spec["id"], manifest, tuple(spec.get("dependencies", ())))


def _entry(spec: dict[str, Any], body: bytes, rel: str, known: set[str]) -> dict[str, Any]:
    pid = spec["id"]
    name, version = split_package_id(pid)
    dependencies: list[dict[str, str]] = []
    for dep in spec.get("dependencies", ()):
        if dep == pid or dep not in known:
            raise ValueError(f"{pid}: dependency {dep!r} is not another fixture package")
        dep_name, dep_version = split_package_id(dep)
        dependencies.append({"id": dep, "name": dep_name, "version": dep_version})
    manifest = spec.get("manifest") or {}
    return {
        "id": pid,
        "name": name,
        "version": version,
        "channel": channel_of(version),
        "blob": rel,
        "digest": digest_bytes(body),
        "bytes": len(body),
        "features": sorted(spec["features"]),
        "signature": sign_payload(body, key_id=FIXTURE_KEY_ID),
        "dependencies": dependencies,
        "sbom_present": "sbom" in manifest,
        "benchmark_present": "benchmark" in manifest,
        "deprecated": "deprecated" in manifest,
    }


def _materialise(reg: Path) -> dict[str, Any]:
    blobs = reg / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    known = {spec["id"] for spec in PACKAGE_SPECS}
    if len(known) != len(PACKAGE_SPECS):
        raise ValueError("PACKAGE_SPECS lists a package id twice")
    packages: list[dict[str, Any]] = []
    written: set[str] = set()
    for spec in PACKAGE_SPECS:
        body = payload_for(spec)
        digest = digest_bytes(body)
        rel = f"blobs/{digest}"
        (reg / rel).write_bytes(body)
        written.add(digest)
        packages.append(_entry(spec, body, rel, known))
    # A known-good registry has no stray blobs: drop leftovers from older builds.
    for stale in blobs.iterdir():
        if stale.is_file() and stale.name not in written:
            stale.unlink()
    packages.sort(key=lambda p: p["id"])
    index = {
        "schema": INDEX_SCHEMA,
        "registry_id": FIXTURE_REGISTRY_ID,
        "publisher_key": {"key_id": FIXTURE_KEY_ID, "algorithm": ALGORITHM},
        "packages": packages,
        "documented": [],
        "inferred": [],
    }
    (reg / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return index


def build(root: Path | str | None = None) -> dict[str, Any]:
    """Materialise the fixture registry and return its index.

    ``root`` may be the repo root (the registry lands at
    ``tools/marketplace/fixture/registry``), an explicit registry directory, or
    ``None`` for this package's own fixture directory.
    """
    path = Path(root) if root else Path(__file__).resolve().parent / "fixture" / "registry"
    if (path / "tools" / "marketplace").is_dir() or (path / "command-center").is_dir():
        reg = registry_dir(path)
    else:
        reg = path
    return _materialise(reg)


def load_payloads(repo: Path) -> dict[str, bytes]:
    """Blob bytes of every package in the on-disk registry index, keyed by package id."""
    root = registry_dir(Path(repo))
    index = read_json(root / "index.json")
    out: dict[str, bytes] = {}
    for pkg in index.get("packages") or []:
        out[pkg["id"]] = (root / pkg["blob"]).read_bytes()
    return out
