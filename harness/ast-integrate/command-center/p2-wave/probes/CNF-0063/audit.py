#!/usr/bin/env python3
"""Load the CNF-0063 sample, re-measure live legs, classify via origin tracing."""
from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CLAIMS_PATH = HERE / "fixtures" / "claims.json"

from lineage import classify_sample  # noqa: E402

DIGEST_BYTES = b"CNF-0063"
EXPECTED_DIGEST = "fb9dd65151c3e73a574956b8a4c8eeea7b71289aa9b51d3342f946cb759c3dce"
CATALOG_PATH_CLAIM = "command-center/confirmation/CNF-0063-source-corroboration.json"
DRAFT7 = "http://json-schema.org/draft-07/schema#"
DRAFT202012 = "https://json-schema.org/draft/2020-12/schema"
ARCH_CLASS = '"x-artifact-class": "architecture-review"'
RFC_EXCERPT = HERE / "fixtures" / "rfc6234-excerpt.txt"
RFC_MARKERS = (
    "adapted by the authors from FIPS 180-2",
    "taken from [SHS]",
    "SHA-256 algorithms produce 224-bit and 256-bit",
    "[SHS]",
    "(FIPS) 180-3",
)


def load_raw() -> dict[str, Any]:
    return json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))


def hashlib_digest() -> str:
    return hashlib.sha256(DIGEST_BYTES).hexdigest()


def coreutils_digest() -> str:
    p = subprocess.run(
        ["sha256sum"],
        input=DIGEST_BYTES,
        capture_output=True,
        check=True,
    )
    return p.stdout.decode("ascii").split()[0]


def live_checks(raw: dict[str, Any]) -> dict[str, Any]:
    catalog = (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    schema_text = (REPO / "command-center" / "schema" / "architecture-review.schema.json").read_text(
        encoding="utf-8"
    )
    excerpt = RFC_EXCERPT.read_text(encoding="utf-8")
    excerpt_flat = " ".join(excerpt.split())
    h = hashlib_digest()
    c = coreutils_digest()
    missing_rfc = [m for m in RFC_MARKERS if m not in excerpt_flat]
    return {
        "catalog_declares_output_path": CATALOG_PATH_CLAIM in catalog and '"id": "CNF-0063"' in catalog,
        "draft7_uri_in_architecture_review_schema": DRAFT7 in schema_text,
        "draft202012_uri_in_architecture_review_schema": DRAFT202012 in schema_text,
        "architecture_review_is_generated_shim": "GENERATED SHIM" in schema_text and ARCH_CLASS in schema_text,
        "hashlib_digest": h,
        "coreutils_digest": c,
        "digests_agree": h == c == EXPECTED_DIGEST,
        "rfc_excerpt_markers_present": missing_rfc == [],
        "rfc_excerpt_missing": missing_rfc,
        "rfc_excerpt_sha256": hashlib.sha256(RFC_EXCERPT.read_bytes()).hexdigest(),
        "rfc_excerpt_bytes": RFC_EXCERPT.stat().st_size,
    }


def require_live(checks: dict[str, Any]) -> None:
    if not checks["catalog_declares_output_path"]:
        raise SystemExit("FAILED:CNF-0063 live catalog path claim not found")
    if not checks["draft202012_uri_in_architecture_review_schema"]:
        raise SystemExit("FAILED:CNF-0063 live draft/2020-12 URI not found in architecture-review shim")
    if not checks["architecture_review_is_generated_shim"]:
        raise SystemExit("FAILED:CNF-0063 architecture-review schema is not a generated shim")
    if checks["draft7_uri_in_architecture_review_schema"]:
        raise SystemExit(
            "FAILED:CNF-0063 architecture-review still carries draft-07 URI; "
            "C-SCHEMA-SHIM would be the wrong claim"
        )
    if not checks["digests_agree"]:
        raise SystemExit(
            "FAILED:CNF-0063 digest disagreement "
            f"hashlib={checks['hashlib_digest']} coreutils={checks['coreutils_digest']}"
        )
    if not checks["rfc_excerpt_markers_present"]:
        raise SystemExit(f"FAILED:CNF-0063 RFC excerpt missing {checks['rfc_excerpt_missing']}")


def audit() -> dict[str, Any]:
    raw = load_raw()
    checks = live_checks(raw)
    require_live(checks)
    classified = classify_sample(deepcopy(raw["claims"]))
    classified["live_checks"] = checks
    classified["frame_note"] = raw.get("frame_note")
    classified["seed"] = raw.get("seed")
    classified["ids"] = [c["id"] for c in raw["claims"]]
    return classified
