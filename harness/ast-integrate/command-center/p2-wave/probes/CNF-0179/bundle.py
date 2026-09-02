"""Build a published-shape tarball, CycloneDX SBOM, and in-toto provenance.

Signing uses an ephemeral fixture RSA key destroyed after use. That key is not
an API key and is never printed.
"""
from __future__ import annotations

import gzip
import io
import json
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from tools import (
    destroy_private,
    generate_keypair,
    public_fingerprint,
    sha256_bytes,
    sign_file,
)

PKG = "cnf-0179-demo-1.0.0"
PATH_PROP = "cnf0179:path"
VENDOR_HELPER_PURL = "pkg:generic/vendor-helper@1.2.3"
PHANTOM_PURL = "pkg:generic/ghost-lib@0.0.1"

# Payload files that constitute the published artifact contents.
PAYLOAD: list[tuple[str, str, str, str]] = [
    # rel, purl, name, body
    (
        "manifest.json",
        "pkg:generic/cnf-0179-demo@1.0.0",
        "cnf-0179-demo",
        json.dumps(
            {
                "name": "cnf-0179-demo",
                "version": "1.0.0",
                "kind": "published-shape-fixture",
                "note": "CNF-0179 independent-tooling harness bundle; not a production marketplace release",
            },
            indent=2,
        )
        + "\n",
    ),
    (
        "lib/declared-lib.txt",
        "pkg:generic/declared-lib@2.0.0",
        "declared-lib",
        "declared-lib 2.0.0\ncontrol component listed in the SBOM\n",
    ),
    (
        "vendor/helper.py",
        VENDOR_HELPER_PURL,
        "vendor-helper",
        '"""Vendored helper present in the artifact."""\nVERSION = "1.2.3"\n',
    ),
    (
        "bin/tool.sh",
        "pkg:generic/bundled-tool@9.1.0",
        "bundled-tool",
        "#!/bin/sh\necho cnf-0179-bundled-tool 9.1.0\n",
    ),
    (
        "docs/NOTES.md",
        "pkg:generic/runtime-notes@0.4.0",
        "runtime-notes",
        "# runtime notes\nNo credentials. Fixture documentation only.\n",
    ),
    (
        "LICENSE",
        "pkg:generic/cnf-0179-demo-license@1.0.0",
        "cnf-0179-demo-license",
        "MIT-SHAPE FIXTURE LICENSE TEXT. Not a secret.\n",
    ),
]


def _tarinfo(name: str, size: int, mode: int = 0o644) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = 0
    info.mode = mode
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def build_tarball() -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tf:
        for rel, _purl, _name, body in PAYLOAD:
            data = body.encode("utf-8")
            arc = f"{PKG}/{rel}"
            mode = 0o755 if rel.startswith("bin/") else 0o644
            tf.addfile(_tarinfo(arc, len(data), mode), io.BytesIO(data))
    uncompressed = raw.getvalue()
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0, compresslevel=9) as gzf:
        gzf.write(uncompressed)
    return gz.getvalue()


def component_rows() -> list[dict]:
    rows = []
    for rel, purl, name, body in PAYLOAD:
        digest = sha256_bytes(body.encode("utf-8"))
        version = purl.rsplit("@", 1)[-1]
        rows.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": purl,
                "hashes": [{"alg": "SHA-256", "content": digest}],
                "properties": [{"name": PATH_PROP, "value": f"{PKG}/{rel}"}],
            }
        )
    return rows


def make_sbom() -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:00000000-0000-4000-a000-000000000179",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "cnf-0179-demo",
                "version": "1.0.0",
                "purl": "pkg:generic/cnf-0179-demo@1.0.0",
            }
        },
        "components": component_rows(),
    }


def make_provenance(artifact_name: str, artifact_sha256: str) -> dict:
    now = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc).isoformat()
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": artifact_name, "digest": {"sha256": artifact_sha256}}
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://cnf-0179.local/fixture-publish@v1",
                "externalParameters": {
                    "package": "cnf-0179-demo",
                    "version": "1.0.0",
                },
            },
            "runDetails": {
                "builder": {"id": "https://cnf-0179.local/fixture-builder"},
                "metadata": {"startedOn": now, "finishedOn": now},
            },
        },
    }


def write_json(path: Path, doc: dict) -> None:
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def publish(dest: Path) -> dict:
    """Write artifact, SBOM, provenance, signatures, and public key. No private key left."""
    dest.mkdir(parents=True, exist_ok=True)
    artifact = dest / "cnf-0179-published.tar.gz"
    sbom_path = dest / "sbom.cdx.json"
    prov_path = dest / "provenance.intoto.json"
    art_sig = dest / "cnf-0179-published.tar.gz.sig"
    prov_sig = dest / "provenance.intoto.json.sig"
    pubkey = dest / "pubkey.pem"

    tarball = build_tarball()
    artifact.write_bytes(tarball)
    art_sha = sha256_bytes(tarball)
    write_json(sbom_path, make_sbom())
    write_json(prov_path, make_provenance(artifact.name, art_sha))

    with tempfile.TemporaryDirectory(prefix="cnf0179-key-") as tmp:
        work = Path(tmp)
        private, public = generate_keypair(work)
        try:
            pubkey.write_bytes(public.read_bytes())
            sign_file(private, artifact, art_sig)
            sign_file(private, prov_path, prov_sig)
            fp = public_fingerprint(public)
        finally:
            destroy_private(private)

    leftover = dest / "fixture-only-private.pem"
    if leftover.exists():
        destroy_private(leftover)
        raise RuntimeError("private key leaked into published dir")

    return {
        "dir": dest.as_posix(),
        "artifact": artifact.name,
        "artifact_sha256": art_sha,
        "artifact_bytes": len(tarball),
        "sbom": sbom_path.name,
        "provenance": prov_path.name,
        "artifact_sig": art_sig.name,
        "provenance_sig": prov_sig.name,
        "pubkey": pubkey.name,
        "pubkey_sha256": fp,
        "component_count": len(PAYLOAD),
        "vendor_helper_purl": VENDOR_HELPER_PURL,
        "phantom_purl": PHANTOM_PURL,
    }
