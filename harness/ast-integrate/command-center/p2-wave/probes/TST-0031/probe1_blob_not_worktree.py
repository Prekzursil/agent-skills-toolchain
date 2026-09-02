#!/usr/bin/env python3
"""Probe 1: gate hashes/formats BLOB bytes, not worktree or git-archive bytes.

Catalog tests: test_gate_reads_blob_bytes_not_worktree_bytes
Evidence: three-route table + LF-normalisation identity on this box.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import blob_gate as G  # noqa: E402
from harness_load import load_both_states  # noqa: E402

UNIT = "TST-0031"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    bs = load_both_states()
    with tempfile.TemporaryDirectory(prefix="tst0031-p1-") as td:
        root = Path(td)
        good = G.init_repo(root / "good")
        lf = b"line-one\nline-two\n" * 40
        G.commit_bytes(good, "sample.txt", lf, "lf-blob")
        G.commit_bytes(
            good,
            ".gitattributes",
            b"sample.txt text eol=crlf\n",
            "archive-export-crlf",
        )
        crlf_wt = lf.replace(b"\n", b"\r\n")
        (good / "sample.txt").write_bytes(crlf_wt)

        gate = G.evaluate(good, "HEAD", "sample.txt")
        blob = G.read_blob(good, "HEAD", "sample.txt")
        show = G.read_show(good, "HEAD", "sample.txt")
        arch = G.read_archive(good, "HEAD", "sample.txt")
        wt = G.worktree_bytes(good, "sample.txt")
        table = G.three_route(good, "HEAD", "sample.txt")

        print(json.dumps({"three_route": table, "gate": gate}, sort_keys=True))

        if blob != lf:
            return fail(f"cat-file did not return LF blob: {blob[:40]!r}")
        if show != blob:
            return fail("git show disagreed with git cat-file")
        if wt != crlf_wt:
            return fail("worktree was not the planted CRLF bytes")
        if gate["blob_sha256"] != sha(lf):
            return fail("gate hashed something other than the LF blob")
        if gate["blob_sha256"] == sha(crlf_wt):
            return fail("gate hash collided with CRLF worktree (read worktree?)")
        if gate["worktree_sha256"] != sha(crlf_wt):
            return fail("recorded worktree hash is wrong")
        if gate["hash_matches_worktree"]:
            return fail("gate claimed blob hash equals worktree hash")
        if not gate["format_ok"] or gate["verdict"] != "PASS":
            return fail("LF blob should format-PASS")
        if G.format_ok_text_blob(crlf_wt):
            return fail("format check on worktree CRLF should fail; control broken")
        if arch == blob:
            return fail("git archive equalled blob; eol=crlf fixture did not convert")
        if arch.count(b"\r\n") < 1:
            return fail("git archive produced no CRLF on eol=crlf fixture")
        if not table["archive_differs_from_blob"]:
            return fail("three-route did not record archive≠blob")
        if not table["cat_file_equals_show"]:
            return fail("cat-file !== show")
        if not table["identical_after_lf_normalisation"]:
            return fail("LF-normalisation identity failed")
        if table["recipe_used_by_gate"] != G.AUTHORITATIVE_RECIPE:
            return fail("gate recipe drifted")

        def format_fires(state: dict) -> bool:
            result = G.evaluate(Path(state["repo"]), "HEAD", state["path"])
            return not result["format_ok"]

        broken = G.init_repo(root / "broken")
        crlf_blob = lf.replace(b"\n", b"\r\n")
        G.commit_bytes(broken, "sample.txt", crlf_blob, "crlf-as-blob")
        (broken / "sample.txt").write_bytes(lf)

        rec = bs.control(
            format_fires,
            {"repo": str(good), "path": "sample.txt"},
            {"repo": str(broken), "path": "sample.txt"},
            check_id="test_gate_reads_blob_bytes_not_worktree_bytes",
            description=(
                "Format/hash gate is silent on an LF blob with a dirty CRLF "
                "worktree, and fires when the committed blob itself is CRLF."
            ),
        )
        if rec.verdict != bs.VALID:
            return fail(f"both-states rejected: {rec.to_dict()}")
        print(f"both_states verdict={rec.verdict} good={rec.good_outcome} broken={rec.broken_outcome}")

        broken_gate = G.evaluate(broken, "HEAD", "sample.txt")
        if broken_gate["format_ok"] or broken_gate["verdict"] != "FAIL":
            return fail("CRLF blob must format-FAIL")
        if broken_gate["blob_sha256"] != sha(crlf_blob):
            return fail("broken-state gate did not hash the CRLF blob")
        if broken_gate["blob_sha256"] == sha(lf):
            return fail("broken-state gate hashed the LF worktree")

    print("SUCCESS:TST-0031-probe1 blob gate reads cat-file bytes not worktree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
