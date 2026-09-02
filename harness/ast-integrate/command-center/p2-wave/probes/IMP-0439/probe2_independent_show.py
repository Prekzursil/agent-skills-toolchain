#!/usr/bin/env python3
"""Named probe 2: independent git-show re-derive + REACH-6 both-states.

Different instrument from probe 1: this probe re-derives two blob digests with
`git show` (not `git cat-file`), then drives validate() on a CRLF snapshot
(must be silent) and a content-mutated snapshot (must fire). Starts from the
tests, not the author summary.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import blob  # noqa: E402
import validate as val  # noqa: E402


def fail(msg: str, extra: object = None) -> int:
    print(f"FAILED:IMP-0439-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:8000])
    return 1


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mini_catalog(digest: str) -> dict:
    return {
        "schema_version": 1,
        "provenance": {
            "register": "command-center/sources/REGISTER.md",
            "register_sha256": digest,
        },
        "items": [
            {
                "id": "R-A01",
                "title": "fixture",
                "status": "OPEN",
                "program": "A-toolchain",
                "next_smallest_action": "do the thing",
                "dependencies": [],
            }
        ],
        "defaults": {},
        "owner_questions": [],
    }


def _reach6_digest(violations: list) -> list:
    return [
        v
        for v in violations
        if v["check"] == "REACH-6" and "sha256" in v["detail"]
    ]


def main() -> int:
    src = Path(blob.__file__).read_text(encoding="utf-8")
    if "cat-file" not in src:
        return fail("blob.py no longer calls git cat-file")
    if '", "archive"' in src or "', 'archive'" in src:
        return fail("blob.py invokes git archive")

    with tempfile.TemporaryDirectory(prefix="imp0439-p2-") as tmp:
        tmp_path = Path(tmp)
        repo = blob.init_manifest_fixture(tmp_path)
        sample_a = "command-center/PROGRAM-CHARTER.md"
        sample_b = "command-center/WORK-UNIT-CATALOG.json"
        show_a = blob.sha256_hex(blob.show_bytes(repo, sample_a))
        show_b = blob.sha256_hex(blob.show_bytes(repo, sample_b))
        cat_a = blob.sha256_hex(blob.blob_bytes(repo, sample_a))
        cat_b = blob.sha256_hex(blob.blob_bytes(repo, sample_b))
        if show_a != cat_a or show_b != cat_b:
            return fail(
                "git show != git cat-file",
                {
                    sample_a: {"show": show_a, "cat-file": cat_a},
                    sample_b: {"show": show_b, "cat-file": cat_b},
                },
            )

        blob.materialise_crlf_worktree(repo, [sample_a])
        via_helper = blob.sha256_hex(
            blob.provenance_bytes(repo / sample_a, repo=repo)
        )
        if via_helper != cat_a:
            return fail(
                "provenance_bytes after CRLF != blob",
                {"via_helper": via_helper, "blob": cat_a},
            )
        wt = blob.sha256_hex(blob.working_tree_bytes(repo / sample_a))
        if wt == cat_a:
            return fail("working-tree hash matched blob after CRLF; control is dead")

        lf = b"# register\nline two\n"
        crlf_path = tmp_path / "REGISTER.md"
        crlf_path.write_bytes(lf.replace(b"\n", b"\r\n"))
        catalog = _mini_catalog(_sha(lf))
        silent, _ = val.validate(catalog, register_path=crlf_path)
        if _reach6_digest(silent):
            return fail("REACH-6 fired on CRLF-only snapshot", silent)

        tampered = tmp_path / "TAMPERED.md"
        tampered.write_bytes(lf + b"mutated\n")
        fired, _ = val.validate(catalog, register_path=tampered)
        if not _reach6_digest(fired):
            return fail("REACH-6 silent on content mutation", fired)

    payload = {
        "pass": True,
        "probe": "probe2-independent-show-and-reach6",
        "unit_id": "IMP-0439",
        "reviewer_id": "IMP-0439-probe2-independent-show",
        "starts_from": "tests (blob parity + REACH-6 both-states), not author summary",
        "independent_git_show_matches_cat_file": True,
        "samples": {
            sample_a: {"git_show": show_a, "git_cat_file": cat_a},
            sample_b: {"git_show": show_b, "git_cat_file": cat_b},
        },
        "both_states": {
            "silent_on_crlf_only": True,
            "fires_on_content_change": True,
            "working_tree_differs_from_blob_after_crlf": True,
        },
    }
    print(json.dumps(payload, indent=2))
    print(
        "git_show_matches=True crlf_silent=True content_fires=True "
        f"samples=[{sample_a}, {sample_b}]"
    )
    print("SUCCESS:IMP-0439-probe2 independent-show REACH-6 both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
