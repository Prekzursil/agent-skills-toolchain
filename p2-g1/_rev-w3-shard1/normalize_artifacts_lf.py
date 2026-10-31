#!/usr/bin/env python3
"""Normalize ADV-0038 + ADV-0090 artifacts to LF on disk (content-invariant).

The unit contract hashes CRLF-to-LF normalized; the program's completion gate
c3 hashes RAW bytes. For a CRLF-on-disk artifact the two instruments disagree
forever unless the disk form IS the canonical LF form. This script makes disk
== canonical: it rewrites the artifacts' CRLF to LF, verifying BEFORE and AFTER
that (1) the normalized sha256 is UNCHANGED, (2) json.loads content is
UNCHANGED, (3) the file is pure LF afterwards. Any mismatch aborts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")

TARGETS = {
    "ADV-0038": ("e18cdc21d53121501fd62d37bb920946442e4fff17771eb61263aa2b64013f05", 31457),
    "ADV-0090": ("ef5e26333446d9063ed983575999c08da2054e16597fa4f5197929a2407d73f2", 31785),
}


def main() -> int:
    ok = True
    for uid, (expect_sha, expect_norm_len) in TARGETS.items():
        p = list((REPO / "command-center/adversarial").glob(uid + "-*.json"))[0]
        raw = p.read_bytes()
        pre_norm_sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        pre_doc = json.loads(raw.decode("utf-8"))
        if pre_norm_sha != expect_sha:
            print("ABORT", uid, "normalized sha changed before write:", pre_norm_sha)
            ok = False
            continue
        lf = raw.replace(b"\r\n", b"\n")
        post_norm_sha = hashlib.sha256(lf.replace(b"\r\n", b"\n")).hexdigest()
        post_doc = json.loads(lf.decode("utf-8"))
        if post_norm_sha != expect_sha or post_doc != pre_doc or b"\r" in lf:
            print("ABORT", uid, "post-write verification failed")
            ok = False
            continue
        p.write_bytes(lf)
        check = p.read_bytes()
        final = hashlib.sha256(check.replace(b"\r\n", b"\n")).hexdigest()
        same = (final == expect_sha and len(check) == expect_norm_len
                and b"\r" not in check and json.loads(check.decode("utf-8")) == pre_doc)
        print("NORMALIZED" if same else "FAILED", uid,
              "| raw bytes now:", len(check), "| sha:", final[:16], "| pure-LF:", b"\r" not in check)
        ok = ok and same
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
