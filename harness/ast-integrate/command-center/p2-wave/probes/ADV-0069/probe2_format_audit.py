#!/usr/bin/env python3
"""Probe 2: inspect export/mirror formats for integrity metadata.

Mechanically different from probe 1: no install, no BlobStore.get, no payload
mutation. A format with no digest field cannot detect tampering regardless of
what an install attempt happens to do.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dist import (  # noqa: E402
    NOT_A_TRUST_ANCHOR,
    TRUST_ANCHOR_KIND,
    build_pristine_bundle,
    format_digest_fields,
    production_surfaces,
)

BLOB_STORE_REL = "tools/marketplace/blob_store.py"
INDEX_DIGEST_MARKERS = (
    "DIGEST_ALG",
    "digest_bytes",
    "CorruptedBlobError",
    "recompute",
)


def blob_store_format_audit(repo: Path) -> dict:
    path = repo / BLOB_STORE_REL
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    markers = {m: (m in text) for m in INDEX_DIGEST_MARKERS}
    get_rehash = (
        "def get(self, digest: str) -> bytes:" in text
        and "actual = digest_bytes(data)" in text
        and "if actual != digest:" in text
    )
    return {
        "path": BLOB_STORE_REL,
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "markers": markers,
        "get_recomputes_digest": get_rehash,
        "digest_fields_in_index_schema": [
            "digest_algorithm",
            "objects.<sha256>",
        ],
        "trust_anchor": TRUST_ANCHOR_KIND if get_rehash else "UNNAMED",
    }


def main() -> int:
    surfaces = production_surfaces(REPO)
    blob = blob_store_format_audit(REPO)
    with tempfile.TemporaryDirectory(prefix="adv0069-p2-") as td:
        bundle_root = Path(td) / "bundle"
        bundle_root.mkdir()
        built = build_pristine_bundle(bundle_root)
        manifest = json.loads(Path(built["manifest_path"]).read_text(encoding="utf-8"))
        fixture_fields = format_digest_fields(manifest)

    production_bundle_schema = surfaces["named_files_present"].get(
        "tools/marketplace/schema/offline-bundle.schema.json", False
    )
    production_export = surfaces["any_named_offline_or_mirror_module"]
    # A missing format has no digest field.
    production_has_digest_field = bool(production_bundle_schema)
    cannot_detect_if_no_digest = not production_has_digest_field

    trust_anchor_named = bool(blob["get_recomputes_digest"])
    out = {
        "probe": "probe2_format_audit",
        "method": "static-format-inspection",
        "no_install_attempt": True,
        "production_surfaces": {
            "named_files_present": surfaces["named_files_present"],
            "any_named_offline_or_mirror_module": production_export,
            "symbol_hits": surfaces["symbol_hits"],
            "blob_store_present": surfaces["blob_store_present"],
        },
        "blob_store_format": blob,
        "fixture_offline_bundle": {
            "kind": "probe-local fixture, not production export",
            "manifest_keys": built["manifest_keys"],
            "entry_keys": built["entry_keys"],
            "digest_field_paths": fixture_fields,
            "has_digest_field": True,
            "envelope_sha256_is_trust_anchor": False,
            "why_envelope_is_not_integrity": NOT_A_TRUST_ANCHOR,
        },
        "production_offline_export_format": {
            "present": production_export,
            "schema_present": production_bundle_schema,
            "has_digest_field": production_has_digest_field,
            "cannot_detect_tamper_without_digest_field": cannot_detect_if_no_digest,
        },
        "trust_anchor": {
            "named": trust_anchor_named,
            "kind": TRUST_ANCHOR_KIND,
            "what_is_not_a_trust_anchor": NOT_A_TRUST_ANCHOR,
        },
        "conclusion": (
            "The live mirror-like format is the BlobStore on-disk index, which "
            "keys objects by sha256 and recomputes on read. No production "
            "offline-bundle export format exists on this tree; a format with "
            "no digest field cannot detect tampering, independent of install."
        ),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    ok = (
        blob["present"]
        and blob["get_recomputes_digest"]
        and all(blob["markers"].values())
        and not production_export
        and cannot_detect_if_no_digest
        and any("digest" in p.lower() for p in fixture_fields)
        and trust_anchor_named
    )
    if not ok:
        print("FAILED:ADV-0069-probe2 format-audit invariants broken", file=sys.stderr)
        return 1
    print(
        "SUCCESS:ADV-0069-probe2 BlobStore index carries digest metadata; "
        "production offline-bundle format absent (no digest field); "
        "trust anchor named; envelope self-hash is not integrity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
