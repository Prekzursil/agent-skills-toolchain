#!/usr/bin/env python3
"""Named probe 2: byte-length delta equals line count (signal 2).

Independent of hashing: no sha256 is computed for the CRLF/LF identity.
The control is the arithmetic ``len(crlf) - len(lf) == lf.count(b'\\n') ==
crlf.count(b'\\r\\n')``. That identity holds only when the difference is
exactly one extra CR per newline.

Also the reviewer requirement: binary detection precedes normalisation.
A PNG whose signature contains CRLF must hash identically raw vs policy,
and a naive replace of the same bytes must NOT.
"""
from __future__ import annotations

import ast
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import eol_hash as H  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0035.json"
SRC = PLUGIN / "eol_hash.py"
LOGICAL = b"alpha\nbeta\ngamma\n"
SENTINEL = "SUCCESS:IMP-0035"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0035-probe2 {msg}")
    return 1


def _png_1x1() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00\xff\x00\x00"
    idat = chunk(b"IDAT", zlib.compress(raw, 9))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _binary_precedes_normalise(src: str) -> tuple[bool, str]:
    tree = ast.parse(src)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "bytes_for_hash":
            fn = node
            break
    if fn is None:
        return False, "bytes_for_hash missing"
    # First executable statement must be `if looks_binary(data): return data`.
    body = [s for s in fn.body if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)]
    # Keep docstrings skipped: first stmt after docstring.
    stmts = list(fn.body)
    if (
        stmts
        and isinstance(stmts[0], ast.Expr)
        and isinstance(stmts[0].value, ast.Constant)
    ):
        stmts = stmts[1:]
    if not stmts:
        return False, "empty body"
    first = stmts[0]
    if not isinstance(first, ast.If):
        return False, f"first stmt is {type(first).__name__}, want If looks_binary"
    test = first.test
    called = None
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name):
        called = test.func.id
    if called != "looks_binary":
        return False, f"first if tests {ast.dump(test)}, want looks_binary"
    if not first.body or not isinstance(first.body[0], ast.Return):
        return False, "looks_binary true-branch does not return"
    ret = first.body[0].value
    if not (isinstance(ret, ast.Name) and ret.id == "data"):
        return False, "true-branch does not return raw data"
    return True, "looks_binary then return data, else lf-normalise"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0035":
        return _fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        return _fail("sentinel-absent")

    lf = LOGICAL
    crlf = LOGICAL.replace(b"\n", b"\r\n")
    # Signal 2: no hashlib. Length delta, newline count, CRLF-pair count.
    delta = len(crlf) - len(lf)
    newline_count = lf.count(b"\n")
    crlf_pairs = crlf.count(b"\r\n")
    cr_bytes = crlf.count(b"\r")
    identity = delta == newline_count == crlf_pairs == cr_bytes

    png = _png_1x1()
    naive = png.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    png_raw = hashlib.sha256(png).hexdigest()
    png_policy = H.sha256_normalised(png)
    png_naive = hashlib.sha256(naive).hexdigest()
    png_passthrough = png_raw == png_policy
    naive_corrupts = png_naive != png_raw

    src = SRC.read_text(encoding="utf-8")
    order_ok, order_why = _binary_precedes_normalise(src)

    print(
        json.dumps(
            {
                "probe": "probe2-eol-arithmetic",
                "unit_id": "IMP-0035",
                "delta": delta,
                "newline_count": newline_count,
                "crlf_pairs": crlf_pairs,
                "cr_bytes": cr_bytes,
                "identity": identity,
                "png_passthrough": png_passthrough,
                "naive_corrupts_png": naive_corrupts,
                "binary_precedes_normalise": order_ok,
                "order_why": order_why,
            },
            indent=1,
            sort_keys=True,
        )
    )

    if not identity:
        return _fail(
            f"arithmetic identity failed delta={delta} newlines={newline_count} "
            f"crlf_pairs={crlf_pairs} cr={cr_bytes}"
        )
    if not png_passthrough:
        return _fail("PNG normalised hash differed from raw (binary was rewritten)")
    if not naive_corrupts:
        return _fail("PNG naive rewrite did not change bytes; control is inert")
    if not order_ok:
        return _fail(order_why)
    if not H.looks_binary(png):
        return _fail("looks_binary(PNG) is false")

    # Mixed-EOL is NOT claimed by this identity. A mixed file vs LF has
    # delta != newline count; if they were equal the control would not
    # discriminate CRLF-only from mixed, and would overclaim.
    mixed = b"alpha\r\nbeta\ngamma\n"
    mixed_delta = abs(len(mixed) - len(lf))
    if mixed_delta == newline_count:
        return _fail("mixed-EOL pair satisfied the CRLF identity; control is inert")

    print(
        f"delta={delta} newlines={newline_count} identity=True "
        f"png_passthrough=True naive_corrupts=True order_ok=True"
    )
    print("SUCCESS:IMP-0035-probe2 byte-delta-equals-line-count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
