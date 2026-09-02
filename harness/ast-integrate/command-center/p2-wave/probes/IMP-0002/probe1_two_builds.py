#!/usr/bin/env python3
"""Named probe 1: two consecutive packs of the same revision are byte-identical.

Catalog evidence signal (1): sha256 of two consecutive builds from a clean
worktree compared in the same run. Worktree mtimes, umask, TZ, and
SOURCE_DATE_EPOCH are perturbed between builds and must not leak.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.fixture_repo import create_pack_fixture  # noqa: E402
from plugin.pack import pack_repository, sha256_file  # noqa: E402
from plugin.tests.test_pack_determinism import (  # noqa: E402
    test_real_mtimes_breaks_determinism,
    test_two_builds_identical,
)

RECEIPT = REPO / "command-center/receipts/IMP-0002.json"
SENTINEL = "SUCCESS:IMP-0002"


def _check_receipt() -> None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0002-probe1 receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0002-probe1 sentinel absent")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0002-probe1 self-declared:{state}")


def main() -> int:
    _check_receipt()
    unit = test_two_builds_identical()
    neg = test_real_mtimes_breaks_determinism()

    with tempfile.TemporaryDirectory(prefix="imp0002-p1-") as tmp:
        root = Path(tmp)
        repo = create_pack_fixture(root, crlf_worktree=True)
        allow = root / "payload-allowlist.json"
        a = root / "build1.tar.gz"
        b = root / "build2.tar.gz"
        r1 = pack_repository(repo, a, allowlist_path=allow)
        for path in repo.rglob("*"):
            if path.is_file():
                os.utime(path, (1_111_111_111, 1_111_111_111))
        old = os.umask(0o077)
        try:
            os.environ["TZ"] = "Pacific/Kiritimati"
            os.environ["SOURCE_DATE_EPOCH"] = "0"
            r2 = pack_repository(repo, b, allowlist_path=allow)
        finally:
            os.umask(old)
        h1, h2 = sha256_file(a), sha256_file(b)
        if h1 != h2 or h1 != r1.sha256 or r1.sha256 != r2.sha256:
            print(f"FAILED:IMP-0002-probe1 digests diverged {h1} {h2}")
            return 1
        if not r1.members:
            print("FAILED:IMP-0002-probe1 empty archive")
            return 1

    summary = {
        "pass": True,
        "probe": "probe1-two-builds",
        "unit_id": "IMP-0002",
        "sha256": h1,
        "members": list(r1.members),
        "member_count": len(r1.members),
        "bytes": r1.size,
        "negative_control_diverged": bool(neg.get("diverged")),
        "unit_test_sha256": unit["sha256"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(f"two_builds sha256={h1} members={len(r1.members)} negative_diverged={neg['diverged']}")
    print("SUCCESS:IMP-0002-probe1 two consecutive builds byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
