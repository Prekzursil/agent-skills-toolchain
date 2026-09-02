#!/usr/bin/env python3
"""Named probe 1: raw sha256 differs, normalised sha256 matches (signal 1).

Mechanically a hashlib comparison of a CRLF/LF pair of the same logical
file, plus the library's classify_pair. Probe 2 does not hash; it checks
the arithmetic identity. Disagreement between the two readings is a fail,
not a picked winner.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import eol_hash as H  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0035.json"
LOGICAL = b"alpha\nbeta\ngamma\n"
SENTINEL = "SUCCESS:IMP-0035"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0035-probe1 {msg}")
    return 1


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
    raw_lf = hashlib.sha256(lf).hexdigest()
    raw_crlf = hashlib.sha256(crlf).hexdigest()
    # Signal 1 uses hashlib on the library's bytes_for_hash output, not a
    # second copy of sha256_normalised, so a broken wrapper cannot hide.
    norm_lf = hashlib.sha256(H.bytes_for_hash(lf)).hexdigest()
    norm_crlf = hashlib.sha256(H.bytes_for_hash(crlf)).hexdigest()
    cls = H.classify_pair(lf, crlf)

    print(
        json.dumps(
            {
                "probe": "probe1-raw-vs-normalised",
                "unit_id": "IMP-0035",
                "raw_sha256_differ": raw_lf != raw_crlf,
                "normalised_sha256_match": norm_lf == norm_crlf,
                "raw_lf": raw_lf,
                "raw_crlf": raw_crlf,
                "norm": norm_lf,
                "class": cls,
                "lf_bytes": len(lf),
                "crlf_bytes": len(crlf),
            },
            indent=1,
            sort_keys=True,
        )
    )

    if raw_lf == raw_crlf:
        return _fail("raw hashes matched; fixture is not a CRLF/LF pair")
    if norm_lf != norm_crlf:
        return _fail("normalised hashes diverged on EOL-only pair")
    if cls != H.IDENTICAL_MODULO_EOL:
        return _fail(f"class={cls}")

    changed = b"alpha\nbeta\ngammaX\n"
    if hashlib.sha256(H.bytes_for_hash(lf)).hexdigest() == hashlib.sha256(
        H.bytes_for_hash(changed)
    ).hexdigest():
        return _fail("negative control: one-character change was masked")
    if H.classify_pair(lf, changed) != H.DIVERGED:
        return _fail("negative control: content change not DIVERGED")

    print("raw_differ=True normalised_match=True class=IDENTICAL-MODULO-EOL")
    print("SUCCESS:IMP-0035-probe1 raw-vs-normalised sha256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
