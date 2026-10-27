#!/usr/bin/env python3
"""IMP-0035 probe1: classify_pair classes over planted CRLF/LF/CR/mixed fixtures.

Independent of the test script: recomputes raw and normalised digests itself and
checks the three-class contract plus the arithmetic identity (delta == newline
count) that fixture authors rely on.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.eol_hash import (  # noqa: E402
    CONTENT_DIVERGED,
    IDENTICAL,
    IDENTICAL_MODULO_EOL,
    bytes_for_hash,
    classify_pair,
    sha256_normalised,
    sha256_raw,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    lf = b"alpha\nbeta\ngamma\n"
    crlf = b"alpha\r\nbeta\r\ngamma\r\n"
    cr = b"alpha\rbeta\rgamma\r"
    mixed = b"alpha\r\nbeta\ngamma\r"
    changed = b"alpha\nbetaX\ngamma\n"

    raw_lf, raw_crlf = sha(lf), sha(crlf)
    norm_lf = sha(bytes_for_hash(lf))
    norm_crlf = sha(bytes_for_hash(crlf))
    delta = len(crlf) - len(lf)

    checks = {
        "raw_differ": raw_lf != raw_crlf,
        "norm_match": norm_lf == norm_crlf,
        "class_modulo": classify_pair(lf, crlf) == IDENTICAL_MODULO_EOL,
        "cr_norm_match": sha256_normalised(lf) == sha256_normalised(cr),
        "mixed_norm_match": sha256_normalised(lf) == sha256_normalised(mixed),
        "identical": classify_pair(lf, lf) == IDENTICAL,
        "changed_diverged": classify_pair(lf, changed) == CONTENT_DIVERGED,
        "arithmetic_identity": delta == lf.count(b"\n") == crlf.count(b"\r\n") == 3,
    }
    out = {
        "unit_id": "IMP-0035",
        "probe": "probe1-eol-classes",
        "raw_lf": raw_lf,
        "raw_crlf": raw_crlf,
        "norm_lf": norm_lf,
        "delta": delta,
        "newline_count": lf.count(b"\n"),
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    print(f"classes_pass={all(checks.values())} delta={delta} norm_match={checks['norm_match']}")
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        print(f"FAILED:IMP-0035-probe1 {failed}")
        return 1
    print("SUCCESS:IMP-0035-probe1 EOL class coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
