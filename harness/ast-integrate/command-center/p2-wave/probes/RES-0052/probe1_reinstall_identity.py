#!/usr/bin/env python3
"""Probe 1: two installs match; git archive differs from git cat-file.

Known-good fixture: two dest trees, per-file blob hashes equal.
Known-broken route: git archive bytes are not the blob (CRLF).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/research/RES-0052.json"
SENTINEL = (
    "SUCCESS:RES-0052 in the receipt AND two installs whose per-file blob "
    "hashes match exactly, plus a demonstrated mismatch on mutation"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0052-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("research artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")

    report = S.run_suite()
    ident = report["identity"]
    crlf = report["crlf_control"]
    print(
        "trees_identical="
        f"{ident['trees_identical']} "
        "per_file_match="
        f"{ident['per_file_blob_hashes_match']} "
        "file_count="
        f"{ident['file_count']}"
    )
    print(
        "archive_differs="
        f"{crlf['archive_differs_on_any_file']} "
        "archive_crlf="
        f"{crlf['any_archive_has_crlf']} "
        "blob_crlf="
        f"{crlf['any_blob_has_crlf']} "
        "cat_equals_show="
        f"{crlf['cat_file_equals_show_all']}"
    )
    for path, digest in ident["hashes_a"].items():
        print(f"file {path} sha256={digest} identical={ident['hashes_a'][path]==ident['hashes_b'].get(path)}")
    if not ident["per_file_blob_hashes_match"]:
        return fail("two installs did not match per-file blob hashes")
    if not crlf["archive_differs_on_any_file"]:
        return fail("git archive did not differ from git cat-file")
    if not crlf["any_archive_has_crlf"]:
        return fail("git archive emitted no CRLF; CRLF control is silent")
    if crlf["any_blob_has_crlf"]:
        return fail("blob unexpectedly contains CRLF")
    if not crlf["cat_file_equals_show_all"]:
        return fail("git show disagreed with git cat-file")
    if not report["ok"]:
        return fail("suite ok=false")
    print("SUCCESS:RES-0052-probe1 two-install identity and archive-vs-cat-file CRLF control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
