#!/usr/bin/env python3
"""Probe 1: git object recovery of a deleted blob; never-committed is not fabricated.

Both-states: a blob deleted from HEAD but still in objects must recover with
content hash + ref/reflog. A path that was never stored must miss, not invent
bytes. Production git writes are refused.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import planted as P  # noqa: E402

ART = E.REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0022-probe1 {msg}")
    return 1


def main() -> int:
    try:
        E.git_ro(E.REPO, "gc")
        return fail("git gc was not refused")
    except E.GitWriteRefused:
        print("git_gc_refused=True")
    try:
        E.git_ro(E.REPO, "add", "x")
        return fail("git add was not refused")
    except E.GitWriteRefused:
        print("git_add_refused=True")
    try:
        E.git_ro(E.REPO, "hash-object", "-w", "--stdin")
        return fail("hash-object -w was not refused")
    except E.GitWriteRefused:
        print("hash_object_w_refused=True")

    with tempfile.TemporaryDirectory(prefix="wfa0022-p1-") as raw:
        fx = P.build(Path(raw))
        repo = fx["git_repo"]
        rec = E.recover_path(repo, fx["abandoned_path"])
        if not rec.ok:
            return fail(f"abandoned blob not recovered: {rec}")
        if rec.sha256 != fx["abandoned_sha256"]:
            return fail(f"hash mismatch git={rec.sha256} want={fx['abandoned_sha256']}")
        if not rec.blob_id:
            return fail("blob_id missing")
        if not rec.ref:
            return fail("ref/reflog missing")
        if rec.content != P.ABANDONED_BODY and E.lf(rec.content or b"") != E.lf(
            P.ABANDONED_BODY
        ):
            return fail("recovered bytes do not match planted abandoned body")

        keep = E.recover_path(repo, fx["keep_path"])
        if not keep.ok or keep.sha256 != fx["keep_sha256"]:
            return fail("keep.yml on HEAD not recovered")

        never = E.recover_path(repo, fx["never_committed"])
        if never.ok:
            return fail("never-committed path fabricated")
        if not never.surface_available:
            return fail("fixture git surface should be available")

        lost = E.recover_path(repo, fx["lost_path"])
        if lost.ok:
            return fail("lost-unique path was stored in git (plant setup broken)")

        summary = {
            "probe": "probe1-git-recovery",
            "abandoned_ok": rec.ok,
            "abandoned_sha256": rec.sha256,
            "abandoned_blob_id": rec.blob_id,
            "abandoned_ref": rec.ref,
            "keep_ok": keep.ok,
            "never_fabricated": False,
            "lost_in_git": lost.ok,
            "pass": True,
            "unit_id": E.UNIT,
        }
        print(json.dumps(summary, sort_keys=True))
        print(
            f"recovered blob={rec.blob_id} sha256={rec.sha256} ref={rec.ref!r}"
        )

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if E.SENTINEL not in text:
            return fail("sentinel absent from artifact")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"artifact self-declared {st}")
        ctrl = ((doc.get("controls") or {}).get("planted") or {})
        ab = ctrl.get("abandoned") or {}
        if not (ab.get("git_recovery") or {}).get("ok"):
            return fail("artifact planted control missing git recovery")
        if ab.get("classification") != E.PRESERVED:
            return fail("artifact abandoned plant is not PRESERVED")

    print("SUCCESS:WFA-0022-probe1 git recovery both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
