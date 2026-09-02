#!/usr/bin/env python3
"""Named probe 2: third pack in a different cwd/TMPDIR/clock, hashed separately.

Catalog evidence signal (2): a THIRD build in a different working directory
with a different TMPDIR and a shifted clock offset, hashed by hash_archive.py
(does not import pack.py). Equality across the three digests, or FAILED.

Also: CRLF worktree packed with LF blob; pack.py source uses git cat-file.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.fixture_repo import (  # noqa: E402
    BLOB_LF,
    CRLF_REL,
    WORKTREE_CRLF,
    create_pack_fixture,
)
from plugin.pack import git_cat_file_blob, git_ls_tree, pack_repository, sha256_file  # noqa: E402
from plugin.tests.test_pack_uses_blob_bytes import (  # noqa: E402
    test_crlf_worktree_packed_with_lf_blob,
    test_source_uses_cat_file_not_worktree_read_of_payload,
)

RECEIPT = REPO / "command-center/receipts/IMP-0002.json"
SENTINEL = "SUCCESS:IMP-0002"
HASHER = Path(__file__).resolve().parent / "hash_archive.py"


def _check_receipt() -> None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0002-probe2 receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0002-probe2 sentinel absent")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0002-probe2 self-declared:{state}")


def _independent_hash(archive: Path, *, cwd: Path, tmpdir: Path, tz: str) -> str:
    env = os.environ.copy()
    env["TZ"] = tz
    env["TMPDIR"] = str(tmpdir)
    env["TMP"] = str(tmpdir)
    env["TEMP"] = str(tmpdir)
    env["SOURCE_DATE_EPOCH"] = "946684800"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(HASHER), str(archive)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"FAILED:IMP-0002-probe2 hasher rc={proc.returncode} {proc.stderr[-800:]}")
    digest = (proc.stdout or "").strip().splitlines()[-1].strip()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit(f"FAILED:IMP-0002-probe2 hasher output {digest!r}")
    return digest


def main() -> int:
    _check_receipt()
    test_source_uses_cat_file_not_worktree_read_of_payload()
    blob_info = test_crlf_worktree_packed_with_lf_blob()

    with tempfile.TemporaryDirectory(prefix="imp0002-p2-") as tmp:
        base = Path(tmp)
        # Build 1+2 in dir A (same as probe1 recipe).
        a_root = base / "cwd-a"
        a_root.mkdir()
        repo_a = create_pack_fixture(a_root, crlf_worktree=True)
        allow_a = a_root / "payload-allowlist.json"
        out1 = a_root / "b1.tar.gz"
        out2 = a_root / "b2.tar.gz"
        r1 = pack_repository(repo_a, out1, allowlist_path=allow_a)
        r2 = pack_repository(repo_a, out2, allowlist_path=allow_a)
        h1, h2 = sha256_file(out1), sha256_file(out2)
        if h1 != h2:
            print(f"FAILED:IMP-0002-probe2 builds 1/2 diverged {h1} {h2}")
            return 1

        # Build 3: different worktree, TMPDIR, TZ, SOURCE_DATE_EPOCH, utimed files.
        b_root = base / "cwd-b"
        b_tmp = base / "tmp-b"
        b_root.mkdir()
        b_tmp.mkdir()
        repo_b = create_pack_fixture(b_root, crlf_worktree=True)
        allow_b = b_root / "payload-allowlist.json"
        for path in repo_b.rglob("*"):
            if path.is_file():
                os.utime(path, (946_684_800, 946_684_800))
        out3 = b_root / "b3.tar.gz"
        old_tz = os.environ.get("TZ")
        old_tmp = os.environ.get("TMPDIR")
        old_cwd = Path.cwd()
        try:
            os.environ["TZ"] = "America/Adak"
            os.environ["TMPDIR"] = str(b_tmp)
            os.environ["SOURCE_DATE_EPOCH"] = "946684800"
            os.chdir(b_root)
            r3 = pack_repository(repo_b, out3, allowlist_path=allow_b)
        finally:
            os.chdir(old_cwd)
            if old_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old_tz
            if old_tmp is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = old_tmp
        h3_pack = sha256_file(out3)
        h3_ind = _independent_hash(out3, cwd=b_root, tmpdir=b_tmp, tz="Pacific/Honolulu")
        if h3_pack != h1 or h3_ind != h1 or r3.sha256 != h1:
            print(
                f"FAILED:IMP-0002-probe2 third digest mismatch "
                f"h1={h1} h3_pack={h3_pack} h3_ind={h3_ind} r3={r3.sha256}"
            )
            return 1
        if r3.members != r1.members:
            print("FAILED:IMP-0002-probe2 member list drifted")
            return 1

        worktree = (repo_b / CRLF_REL).read_bytes()
        entries = {e.path: e for e in git_ls_tree(repo_b, "HEAD")}
        blob = git_cat_file_blob(repo_b, entries[CRLF_REL].sha)
        if worktree != WORKTREE_CRLF or blob != BLOB_LF:
            print("FAILED:IMP-0002-probe2 CRLF fixture drift")
            return 1

    summary = {
        "pass": True,
        "probe": "probe2-third-build-independent-hash",
        "unit_id": "IMP-0002",
        "sha256": h1,
        "build1": h1,
        "build2": h2,
        "build3_pack": h3_pack,
        "build3_independent_hasher": h3_ind,
        "equal_across_three": True,
        "hasher": "command-center/p2-wave/probes/IMP-0002/hash_archive.py",
        "isolation": {
            "cwd": "cwd-b",
            "TMPDIR": "tmp-b",
            "TZ": "America/Adak",
            "SOURCE_DATE_EPOCH": "946684800",
            "worktree_utime": 946684800,
        },
        "crlf": blob_info,
        "byte_source": "git cat-file -p <rev>:<path>",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"three_builds sha256={h1} independent_hasher={h3_ind} "
        f"crlf_packed_equals_blob={blob_info['packed_equals_blob']}"
    )
    print("SUCCESS:IMP-0002-probe2 third build independent hash matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
