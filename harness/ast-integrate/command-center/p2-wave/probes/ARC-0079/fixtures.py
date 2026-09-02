#!/usr/bin/env python3
"""Fixtures for ARC-0079: published, deprecated, revoked, deleted, negative."""
from __future__ import annotations

import copy
import hashlib
from typing import Any


def _sha(label: str) -> str:
    return hashlib.sha256(f"arc-0079:{label}".encode("utf-8")).hexdigest()


def _base_version(label: str, version: str) -> dict[str, Any]:
    digest = _sha(f"{label}:{version}:artifact")
    return {
        "version": version,
        "channels": ["stable"],
        "lifecycle": "published",
        "presence": "retained",
        "dependencies": [
            {
                "package_id": "example-publisher/core-lib",
                "constraint": ">=1.0.0 <2.0.0",
                "optional": False,
            }
        ],
        "compatibility": {
            "platforms": ["linux", "darwin"],
            "client": {"id": "claude-code", "min_version": "1.0.0"},
        },
        "permissions": [
            {"id": "fs.read", "required": True, "scope": "workspace"}
        ],
        "provenance": {
            "artifact_sha256": digest,
            "source_uri": f"https://example.invalid/src/{label}",
            "builder_id": "arc-0079-fixture-builder",
            "built_at": "2026-08-01T00:00:00Z",
            "git_commit": "a" * 40,
            "tree_hash": _sha(f"{label}:{version}:tree"),
        },
        "signature": {
            "algorithm": "ed25519",
            "key_id": "key-" + _sha(f"{label}:key")[:16],
            "signature_uri": f"https://example.invalid/sig/{label}/{version}",
            "digest_sha256": digest,
        },
        "sbom": {
            "media_type": "application/spdx+json",
            "uri": f"https://example.invalid/sbom/{label}/{version}.spdx.json",
            "digest_sha256": _sha(f"{label}:{version}:sbom"),
        },
        "license": {
            "spdx_id": "Apache-2.0",
            "uri": "https://spdx.org/licenses/Apache-2.0.html",
        },
        "vulnerability": {"status": "none_known", "advisory_ids": []},
        "quality": {
            "score": 82,
            "method": "conformance-suite-v1",
            "evidence_uri": f"https://example.invalid/quality/{label}",
        },
    }


def _pkg(namespace: str, name: str, versions: list[dict]) -> dict[str, Any]:
    return {
        "package_id": f"{namespace}/{name}",
        "namespace": namespace,
        "name": name,
        "versions": versions,
    }


def published() -> dict[str, Any]:
    return _pkg("example-publisher", "fixture-normal", [_base_version("normal", "1.2.0")])


def deprecated() -> dict[str, Any]:
    ver = _base_version("deprecated", "1.0.0")
    ver["lifecycle"] = "deprecated"
    ver["deprecation"] = {
        "message": "Use fixture-normal >=1.2.0; this channel is frozen.",
        "deprecated_at": "2026-08-10T00:00:00Z",
        "successor": "example-publisher/fixture-normal",
    }
    ver["quality"]["score"] = 61
    return _pkg("example-publisher", "fixture-deprecated", [ver])


def revoked() -> dict[str, Any]:
    ver = _base_version("revoked", "1.0.0")
    ver["lifecycle"] = "revoked"
    ver["presence"] = "retained"
    ver["vulnerability"] = {
        "status": "advisory_open",
        "advisory_ids": ["OSV-ARC-0079-1"],
    }
    ver["revocation"] = {
        "reason": "compromised-signing-key",
        "effective_at": "2026-08-20T12:00:00Z",
        "signed_list_ref": "revocation-list/2026-08-20#fixture-revoked@1.0.0",
        "issuer": "owner",
        "client_action": "refuse-install-and-surface-on-refresh",
    }
    return _pkg("example-publisher", "fixture-revoked", [ver])


def deleted() -> dict[str, Any]:
    """Tombstone: expressible, and not a revocation."""
    ver = _base_version("deleted", "0.9.0")
    ver["lifecycle"] = "deleted"
    ver["presence"] = "tombstone"
    ver["tombstone"] = {
        "deleted_at": "2026-08-18T00:00:00Z",
        "reason": "yanked-from-distribution-not-a-security-revocation",
    }
    return _pkg("example-publisher", "fixture-deleted", [ver])


def missing_provenance() -> dict[str, Any]:
    entry = published()
    del entry["versions"][0]["provenance"]
    return entry


def missing_artifact_sha256() -> dict[str, Any]:
    entry = published()
    del entry["versions"][0]["provenance"]["artifact_sha256"]
    return entry


def revoked_without_revocation_object() -> dict[str, Any]:
    entry = revoked()
    del entry["versions"][0]["revocation"]
    return entry


def revoked_as_deleted_confusion() -> dict[str, Any]:
    """Illegal: revocation object on a deleted tombstone."""
    entry = deleted()
    entry["versions"][0]["revocation"] = copy.deepcopy(revoked()["versions"][0]["revocation"])
    return entry


FIXTURES = {
    "published": published,
    "deprecated": deprecated,
    "revoked": revoked,
    "deleted": deleted,
    "missing_provenance": missing_provenance,
    "missing_artifact_sha256": missing_artifact_sha256,
    "revoked_without_revocation_object": revoked_without_revocation_object,
    "revoked_as_deleted_confusion": revoked_as_deleted_confusion,
}
