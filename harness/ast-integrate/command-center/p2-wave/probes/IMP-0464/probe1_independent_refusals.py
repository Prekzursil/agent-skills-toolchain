#!/usr/bin/env python3
"""Named probe 1: planted .git, 200 MiB file, and credential each fail alone.

Clean tree is the positive control and must pack. A refusal of one plant must
not depend on the other plants being present.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from package_gate.content_gate import (  # noqa: E402
    OVERSIZE_BYTES,
    SYNTHETIC_CREDENTIAL,
    evaluate,
    plant_credential,
    plant_git,
    plant_oversize,
    write_clean_tree,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0464-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0464-p1-") as raw:
        base = Path(raw)

        clean = base / "clean"
        write_clean_tree(clean)
        clean_tar = base / "clean.tgz"
        clean_res = evaluate(clean, pack_to=clean_tar)
        if not clean_res.ok:
            return fail(f"clean tree refused: {clean_res.reasons}")
        if not clean_tar.is_file() or not clean_res.packed_file_count:
            return fail("clean tree did not pack")
        if any(n != 0 for n in clean_res.pattern_match_counts.values()):
            return fail(f"clean tree matched exclusions: {clean_res.pattern_match_counts}")

        git_root = base / "git"
        write_clean_tree(git_root)
        plant_git(git_root)
        git_tar = base / "git.tgz"
        git_res = evaluate(git_root, pack_to=git_tar)
        if git_res.ok or git_tar.exists():
            return fail("planted .git was packed")
        if "git-dir-shipped" not in git_res.reasons:
            return fail(f"git plant reasons={git_res.reasons}")
        if git_res.pattern_match_counts.get("oversize-file") or git_res.pattern_match_counts.get(
            "credential-env"
        ):
            return fail("git plant was not independent")

        big = base / "big"
        write_clean_tree(big)
        planted = plant_oversize(big)
        if planted.stat().st_size != OVERSIZE_BYTES:
            return fail(f"oversize plant size={planted.stat().st_size}")
        big_tar = base / "big.tgz"
        big_res = evaluate(big, pack_to=big_tar)
        if big_res.ok or big_tar.exists():
            return fail("planted 200 MiB file was packed")
        if "oversize-artifact" not in big_res.reasons:
            return fail(f"oversize plant reasons={big_res.reasons}")
        if "size-ceiling-exceeded" not in big_res.reasons:
            return fail("200 MiB plant did not exceed the size ceiling")
        if big_res.pattern_match_counts.get("git-dir") or big_res.pattern_match_counts.get(
            "credential-env"
        ):
            return fail("oversize plant was not independent")

        cred = base / "cred"
        write_clean_tree(cred)
        plant_credential(cred)
        cred_tar = base / "cred.tgz"
        cred_res = evaluate(cred, pack_to=cred_tar)
        if cred_res.ok or cred_tar.exists():
            return fail("planted credential was packed")
        if "credential-in-package" not in cred_res.reasons:
            return fail(f"credential plant reasons={cred_res.reasons}")
        if cred_res.pattern_match_counts.get("git-dir") or cred_res.pattern_match_counts.get(
            "oversize-file"
        ):
            return fail("credential plant was not independent")
        dumped = json.dumps(cred_res.as_dict())
        if SYNTHETIC_CREDENTIAL in dumped:
            return fail("credential value leaked into gate result")

        payload = {
            "probe": "probe1-independent-refusals",
            "unit_id": "IMP-0464",
            "clean": {
                "ok": clean_res.ok,
                "packed_file_count": clean_res.packed_file_count,
                "packed_bytes": clean_res.packed_bytes,
                "total_bytes": clean_res.total_bytes,
                "file_list": clean_res.packed_members,
            },
            "git": {
                "ok": git_res.ok,
                "reasons": git_res.reasons,
                "match_count": git_res.pattern_match_counts["git-dir"],
            },
            "oversize": {
                "ok": big_res.ok,
                "reasons": big_res.reasons,
                "planted_bytes": OVERSIZE_BYTES,
                "total_bytes": big_res.total_bytes,
            },
            "credential": {
                "ok": cred_res.ok,
                "reasons": cred_res.reasons,
                "hit_paths": [h["relpath"] for h in cred_res.hits],
            },
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "clean_ok=True git_refused=True oversize_refused=True "
            "credential_refused=True independent=True"
        )
        print("SUCCESS:IMP-0464-probe1 planted .git, 200MiB, credential each fail independently")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
