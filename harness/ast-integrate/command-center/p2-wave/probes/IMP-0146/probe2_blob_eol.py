#!/usr/bin/env python3
"""Named probe 2: CRLF working-tree copy and LF blob copy both round-trip.

Blob bytes are obtained with `git cat-file -p` (hash-object -w into an isolated
bare repo — no worktree add/commit). `git archive` is never invoked.

Both-states: a CRLF-only worktree copy still round-trips to the LF blob export;
a content mutation of the blob must not.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.canonical import (  # noqa: E402
    CanonicalError,
    export,
    import_workflow,
    read_blob_via_cat_file,
    round_trip_bytes,
)
from scenario import FIXTURES  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0146-probe2 {msg}")
    return 1


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_init_bare(git_dir: Path) -> None:
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    proc = subprocess.run(
        ["git", "init", "--bare", "--", str(git_dir)],
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            (proc.stderr or b"").decode("utf-8", "replace")[:400]
        )


def _hash_object(git_dir: Path, data: bytes) -> str:
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    proc = subprocess.run(
        ["git", "--git-dir", str(git_dir), "hash-object", "-w", "--stdin"],
        input=data,
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            (proc.stderr or b"").decode("utf-8", "replace")[:400]
        )
    sha = (proc.stdout or b"").decode("ascii").strip()
    if len(sha) != 40:
        raise RuntimeError(f"bad-blob-sha:{sha!r}")
    return sha


def main() -> int:
    wf = FIXTURES["all-kinds"]
    lf_export = export(wf)
    if b"\r" in lf_export:
        return _fail("canonical-export-has-cr")
    if b"\n" not in lf_export:
        return _fail("canonical-export-has-no-lf")

    with tempfile.TemporaryDirectory(prefix="imp0146-blob-") as tmp:
        git_dir = Path(tmp) / "blob.git"
        worktree = Path(tmp) / "worktree.json"
        _git_init_bare(git_dir)
        blob_sha = _hash_object(git_dir, lf_export)
        blob = read_blob_via_cat_file(git_dir=git_dir, objectish=blob_sha)
        if blob != lf_export:
            return _fail(
                f"cat-file-ne-export blob={len(blob)} export={len(lf_export)}"
            )

        crlf_copy = lf_export.replace(b"\n", b"\r\n")
        if crlf_copy == lf_export:
            return _fail("crlf-copy-identical-no-trap")
        if b"\r\n" not in crlf_copy:
            return _fail("crlf-copy-missing-crlf")
        worktree.write_bytes(crlf_copy)
        wt_bytes = worktree.read_bytes()
        if wt_bytes != crlf_copy:
            return _fail("worktree-write-mismatch")

        blob_rt = round_trip_bytes(blob)
        wt_rt = round_trip_bytes(wt_bytes)
        if blob_rt != lf_export:
            return _fail("blob-roundtrip-mismatch")
        if wt_rt != lf_export:
            return _fail("worktree-roundtrip-mismatch")
        if blob_rt != wt_rt:
            return _fail("blob-vs-worktree-roundtrip-disagree")

        # Raw hashes differ (the recorded EOL trap). Round-trip hashes match.
        if _sha(blob) == _sha(wt_bytes):
            return _fail("raw-sha-collision-eol-trap-not-visible")
        if _sha(blob_rt) != _sha(wt_rt):
            return _fail("roundtrip-sha-disagree")

        # Content mutation of the blob must not equal the original export.
        mutated = bytearray(blob)
        anchor = mutated.find(b"wf.all-kinds")
        if anchor < 0:
            return _fail("mutation-anchor-absent")
        mutated[anchor] = mutated[anchor] ^ 0x01
        mut_sha = _hash_object(git_dir, bytes(mutated))
        mut_blob = read_blob_via_cat_file(git_dir=git_dir, objectish=mut_sha)
        try:
            mut_rt = round_trip_bytes(mut_blob)
        except CanonicalError:
            mut_rt = b""
        if mut_rt == lf_export:
            return _fail("content-mutation-still-equals")

        # Confirm the blob helper refuses an archive-shaped objectish.
        archive_refused = False
        try:
            read_blob_via_cat_file(git_dir=git_dir, objectish="archive HEAD:x")
        except CanonicalError as exc:
            archive_refused = exc.code == "canonical-archive-forbidden"
        if not archive_refused:
            return _fail("archive-objectish-not-refused")

        imported_blob = import_workflow(blob)
        imported_wt = import_workflow(wt_bytes)
        if export(imported_blob) != export(imported_wt):
            return _fail("imported-objects-disagree")

        summary = {
            "probe": "probe2-blob-crlf",
            "unit_id": "IMP-0146",
            "blob_sha1": blob_sha,
            "blob_bytes": len(blob),
            "blob_crlf": blob.count(b"\r\n"),
            "worktree_bytes": len(wt_bytes),
            "worktree_crlf": wt_bytes.count(b"\r\n"),
            "raw_sha_differ": _sha(blob) != _sha(wt_bytes),
            "blob_roundtrip_equals_export": blob_rt == lf_export,
            "worktree_roundtrip_equals_export": wt_rt == lf_export,
            "content_mutation_equals": mut_rt == lf_export,
            "archive_forbidden": archive_refused,
            "method": "git cat-file -p (NOT git archive)",
            "pass": True,
        }
        print(json.dumps(summary, sort_keys=True))
        wt_crlf = wt_bytes.count(b"\r\n")
        print(
            f"blob={len(blob)}B/0CRLF worktree={len(wt_bytes)}B/"
            f"{wt_crlf}CRLF raw_sha_differ=True "
            f"both_roundtrip=True archive_forbidden={archive_refused}"
        )
        print(
            "SUCCESS:IMP-0146-probe2 CRLF worktree and LF blob both round-trip "
            "via git cat-file -p"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
