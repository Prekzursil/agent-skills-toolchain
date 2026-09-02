"""Isolated ARTIFACT-MANIFEST trees for both-states probes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from digest import digest_bytes, digest_file


def write_payload(path: Path, size: int, tag: bytes = b"ARC-0084") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = tag + b"\n" + (b"x" * max(0, size - len(tag) - 1))
    if len(body) < size:
        body += b"x" * (size - len(body))
    path.write_bytes(body[:size])


def manifest_doc(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": "ARC-0084-artifact-envelope",
        "derivation": "probe-fixture",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": sum(1 for row in rows if row.get("present") is True),
        "artifacts": rows,
    }


def registration_row(
    *,
    rel: str,
    sha: str,
    size: int,
    producing_unit: str,
    present: bool = True,
    manifest_path: str = "ARTIFACT-MANIFEST.json",
) -> dict[str, Any]:
    return {
        "manifest_path": manifest_path,
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": present,
        "producing_unit": producing_unit,
        "role": "primary",
        "artifact_id": f"{producing_unit}:primary",
    }


def make_envelope(
    *,
    rel: str,
    sha: str,
    size: int,
    producing_unit: str = "ARC-0084",
    artifact_class: str = "receipt",
    schema_reference: str = "https://json-schema.org/draft/2020-12/schema",
    sentinel: str = "SUCCESS:ARC-0084-FIXTURE",
    retention_class: str = "session",
    manifest_path: str = "ARTIFACT-MANIFEST.json",
    present: bool = True,
) -> dict[str, Any]:
    return {
        "artifact_id": f"{producing_unit}:primary",
        "producing_unit": producing_unit,
        "path": rel,
        "artifact_class": artifact_class,
        "content_hash": {"alg": "sha256", "hex": sha},
        "byte_size": size,
        "schema_reference": schema_reference,
        "sentinel": sentinel,
        "evidence_anchors": [
            {
                "path": manifest_path,
                "claim": "registration is read from on-disk ARTIFACT-MANIFEST.json",
            }
        ],
        "retention_class": retention_class,
        "manifest_registration": registration_row(
            rel=rel,
            sha=sha,
            size=size,
            producing_unit=producing_unit,
            present=present,
            manifest_path=manifest_path,
        ),
    }


def install(
    root: Path,
    *,
    rel: str = "out/payload.json",
    size: int = 2048,
    register: bool = True,
    artifact_class: str = "receipt",
) -> dict[str, Any]:
    payload = root / rel
    write_payload(payload, size)
    sha, live = digest_file(payload)
    if live != size:
        # digest_file counts LF-normalized length; payload has no CRLF.
        pass
    man_rel = "ARTIFACT-MANIFEST.json"
    rows = []
    if register:
        rows.append(
            registration_row(
                rel=rel,
                sha=sha,
                size=live,
                producing_unit="ARC-0084",
                present=True,
                manifest_path=man_rel,
            )
        )
    (root / man_rel).write_text(
        json.dumps(manifest_doc(rows), indent=2) + "\n", encoding="utf-8"
    )
    env = make_envelope(
        rel=rel,
        sha=sha,
        size=live,
        artifact_class=artifact_class,
        manifest_path=man_rel,
        present=True,
    )
    env["_live_sha"] = sha
    env["_live_bytes"] = live
    return env
