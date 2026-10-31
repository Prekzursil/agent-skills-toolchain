#!/usr/bin/env python3
"""Named probe 2 (IMP-0002): independent third digest + blob-bytes + controls.

Signal 1: a fresh build in a fresh temp dir hashed three ways - inline
whole-read hashlib, inline chunked-stream hashlib, and pack.sha256_file
(the producer's own hasher). The two inline hashers never import pack.
Signal 2 (the unit's other required control): the CRLF worktree member is
packed with the LF git-blob bytes, not the worktree read.
Negative control: real mtimes behind a naive tar writer diverge (the detector
can see the failure mode it exists for).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
TESTS = TOOLS / "plugin" / "tests"
for _p in (TOOLS, TESTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from plugin.fixture_repo import create_pack_fixture  # noqa: E402
from test_pack_determinism import (  # noqa: E402
    test_real_mtimes_breaks_determinism,
)
from test_pack_uses_blob_bytes import (  # noqa: E402
    test_crlf_worktree_packed_with_lf_blob,
    test_source_uses_cat_file_not_worktree_read_of_payload,
)
from plugin.pack import pack_repository, sha256_file  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0002.json"
UNIT = "IMP-0002"


def _inline_whole(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inline_chunked(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        print(f"FAILED:{UNIT}-probe2 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="imp0002-third-") as tmp:
        root = Path(tmp)
        repo = create_pack_fixture(root)
        allow = root / "payload-allowlist.json"
        archive = root / "third.tar"
        pack_repository(repo, archive, allowlist_path=allow)
        h_whole = _inline_whole(archive)
        h_chunk = _inline_chunked(archive)
        h_producer = sha256_file(archive)
        third_equal = h_whole == h_chunk == h_producer

    crlf = test_crlf_worktree_packed_with_lf_blob()
    src_check = test_source_uses_cat_file_not_worktree_read_of_payload()
    negctl = test_real_mtimes_breaks_determinism()

    row = {
        "unit_id": UNIT,
        "probe": "probe2-independent-third-hash-and-blob",
        "third_digest_equal_all_three_hashers": third_equal,
        "crlf_packed_with_lf_blob": bool(crlf.get("ok")),
        "source_uses_cat_file": bool(src_check.get("ok")),
        "negative_control_diverged": bool(negctl.get("diverged")),
        "tests_recorded_in_receipt": [
            t.get("id") for t in (doc.get("tests") or []) if t.get("result") == "PASS"
        ],
    }
    print(json.dumps(row, indent=1))
    if not (third_equal and crlf.get("ok") and src_check.get("ok") and negctl.get("diverged")):
        print(f"FAILED:{UNIT}-probe2 a required signal or control failed")
        return 1
    print(f"SUCCESS:{UNIT}-probe2 independent third digest and controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
