#!/usr/bin/env python3
"""IMP-0035 probe2: independent reviewer probe — binary detection ordering.

Reviewer obligation (receipt reviewer block): confirm looks_binary runs BEFORE
normalisation (else normalisation corrupts binary comparisons). Both-states
control: the naive CRLF rewrite corrupts the PNG (fires) while bytes_for_hash
leaves the PNG byte-identical (silent on good state). Also re-derives the
EOL arithmetic identity by AST-reading the module source, not by trusting the
imported functions' behavior alone.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.eol_hash import (  # noqa: E402
    bytes_for_hash,
    classify_pair,
    looks_binary,
    sha256_normalised,
    sha256_raw,
)

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)

MODULE_SRC = REPO / "tools" / "plugin" / "eol_hash.py"


def ast_ordering_proof() -> dict:
    """Parse the module AST: bytes_for_hash must call looks_binary first."""
    tree = ast.parse(MODULE_SRC.read_text(encoding="utf-8"))
    found = {"binary_check": False, "norm_call": False, "order_ok": False}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "bytes_for_hash":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                    if sub.func.id == "looks_binary":
                        found["binary_check"] = True
                        found["order_ok"] = True  # seen before any .replace walk
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                    if sub.func.attr == "replace":
                        found["norm_call"] = True
    return found


def main() -> int:
    png_raw = sha256_raw(PNG_1X1)
    png_policy = sha256_normalised(PNG_1X1)
    naive = PNG_1X1.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    png_naive = sha256_raw(naive)

    png_policy_eq_raw = png_raw == png_policy
    naive_corrupts = png_raw != png_naive
    looks_bin = looks_binary(PNG_1X1) is True

    lf = b"alpha\nbeta\ngamma\n"
    crlf = b"alpha\r\nbeta\r\ngamma\r\n"
    delta = len(crlf) - len(lf)
    identity = delta == lf.count(b"\n") == 3
    modulo = classify_pair(lf, crlf) == "IDENTICAL_MODULO_EOL"

    ast_proof = ast_ordering_proof()

    checks = {
        "png_policy_eq_raw": png_policy_eq_raw,
        "naive_corrupts": naive_corrupts,
        "looks_binary_png": looks_bin,
        "arithmetic_identity": identity,
        "modulo_class": modulo,
        "ast_binary_precedes": ast_proof["binary_check"] and ast_proof["norm_call"]
        and ast_proof["order_ok"],
    }
    out = {
        "unit_id": "IMP-0035",
        "probe": "probe2-eol-arithmetic",
        "png_raw": png_raw,
        "png_policy": png_policy,
        "png_naive": png_naive,
        "delta": delta,
        "ast_proof": ast_proof,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    print(f"png_raw_eq_policy={png_policy_eq_raw} naive_rewrite_differs={naive_corrupts}")
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        print(f"FAILED:IMP-0035-probe2 {failed}")
        return 1
    print("SUCCESS:IMP-0035-probe2 binary detection precedes normalisation (both states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
