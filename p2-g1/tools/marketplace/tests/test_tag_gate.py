#!/usr/bin/env python3
"""Catalog tests for the marketplace tag gate."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from tag_gate import (  # noqa: E402
    load_plugin_keywords,
    validate_category,
    validate_free_tag,
)


def main() -> int:
    kws = load_plugin_keywords(REPO)
    near = validate_free_tag("reverse_engineering", kws)
    fresh = validate_free_tag("sbom-attestation", kws)
    over = validate_free_tag("x" * 64, kws)
    casing = validate_free_tag("Reverse-Engineering", kws)
    cat_ok = validate_category("security")
    cat_bad = validate_category("not-a-real-category")
    ok = (
        not near.accepted
        and near.reason == "near-duplicate"
        and fresh.accepted
        and not over.accepted
        and casing.accepted
        and cat_ok.accepted
        and not cat_bad.accepted
        and len(kws) == 7
    )
    if not ok:
        print("FAILED:test_tag_gate")
        return 1
    print("SUCCESS:test_tag_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
