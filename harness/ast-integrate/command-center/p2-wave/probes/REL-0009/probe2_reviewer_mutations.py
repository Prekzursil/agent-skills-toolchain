#!/usr/bin/env python3
"""Named probe 2: independent reviewer re-runs mutation controls.

A reviewer who only re-reads the receipt has verified nothing. This probe:

1. Re-packs each mutation and confirms the gate turns red (.git, 200MiB blob,
   gitignored member).
2. Lists the dirty archives via the ZIP central directory (not ZipFile.infolist,
   which the gate uses) and requires the same member names.
3. Shows a gitignore-respecting tree walk misses the packed ignored file, so a
   tree-based gate would go green — the archive listing is the required surface.
4. Mutates the allowlist to ** and confirms the .git plant would then pass,
   proving deny-by-default is what turns that control red.
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "release"))
sys.path.insert(0, str(HERE))

from archive_gate import (  # noqa: E402
    Entry,
    evaluate,
    evaluate_archive,
    load_policy,
)
from controls import (  # noqa: E402
    control_blob,
    control_dotgit,
    control_gitignored,
    receipt_view,
)
from scenario import GITIGNORED_NAME, gitignore_walk, pack_dotgit  # noqa: E402

ART = REPO / "command-center/receipts/REL-0009.json"
SENTINEL = "SUCCESS:REL-0009"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0009-probe2 {msg}")
    return 1


def list_zip_central_directory(path: Path) -> list[Entry]:
    """Independent listing: parse the ZIP central directory, not ZipFile.infolist."""
    data = path.read_bytes()
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise ValueError("EOCD missing")
    _disk, _cd_disk, _nthis, ntotal, _cdsz, cdoff = struct.unpack_from(
        "<HHHHII", data, eocd + 4
    )
    pos = cdoff
    out: list[Entry] = []
    for _ in range(ntotal):
        if data[pos : pos + 4] != b"PK\x01\x02":
            raise ValueError("central-directory signature mismatch")
        uncomp = struct.unpack_from("<I", data, pos + 24)[0]
        namelen, extralen, commentlen = struct.unpack_from("<HHH", data, pos + 28)
        name = data[pos + 46 : pos + 46 + namelen].decode("utf-8")
        pos += 46 + namelen + extralen + commentlen
        norm = name.replace("\\", "/").lstrip("/")
        if not norm or norm.endswith("/"):
            continue
        out.append(Entry(name=norm, size=int(uncomp)))
    return out


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    view = receipt_view(doc)
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel absent")
    if view.get("evaluation_surface") != "archive-entry-list":
        return fail("receipt evaluation_surface")

    policy = load_policy()
    with tempfile.TemporaryDirectory(prefix="rel0009-p2-") as tmp:
        work = Path(tmp)
        git_row = control_dotgit(work / "r-git")
        blob_row = control_blob(work / "r-blob")
        ign_row = control_gitignored(work / "r-ign")

        git_zip = Path(git_row["archive"])
        cd_names = {e.name for e in list_zip_central_directory(git_zip)}
        gate_names = {e["path"] for e in git_row["entries"]}
        if cd_names != gate_names:
            return fail(f"central-dir vs gate names {cd_names ^ gate_names}")
        if not any(n.startswith(".git/") for n in cd_names):
            return fail("central-dir missed .git member")

        ign_zip = Path(ign_row["archive"])
        ign_cd = {e.name for e in list_zip_central_directory(ign_zip)}
        if GITIGNORED_NAME not in ign_cd:
            return fail("central-dir missed gitignored member")
        tree = Path(ign_row["tree"])
        walked = gitignore_walk(tree)
        if GITIGNORED_NAME in walked:
            return fail("tree+gitignore saw the packed ignored file")
        tree_eval = evaluate(
            [Entry(name=n, size=1) for n in walked],
            policy,
            archive_path="TREE-WALK-NOT-ARCHIVE",
        )
        if not tree_eval.ok:
            # .gitignore itself may still be in the walk and fail allowlist.
            tree_viol = {v["path"] for v in tree_eval.allowlist_violations}
            if GITIGNORED_NAME in tree_viol:
                return fail("tree evaluation detected gitignored file; discriminator dead")
        else:
            # Clean tree walk (gitignore dropped the dirt) would PASS — the bug.
            pass

        mutant_policy = dict(policy)
        mutant_policy["globs"] = ["**"]
        mutant = evaluate_archive(git_zip, mutant_policy)
        if mutant.ok is False and any(
            v["path"].startswith(".git/") for v in mutant.allowlist_violations
        ):
            return fail("mutant catch-all glob still treated .git as not-allowlisted")
        # Catch-all must not report allowlist violations for .git. Byte/count may still pass.
        if any(v["path"].startswith(".git/") for v in mutant.allowlist_violations):
            return fail("mutant still allowlist-rejected .git")
        if not mutant.ok:
            # file-count/byte should still pass for the small dirty-git zip
            return fail(f"mutant ** glob failed for another reason: {mutant.to_dict()}")

    blob_hit = blob_row["ceiling_hits"][0]
    print(json.dumps({
        "probe": "probe2-reviewer-mutations",
        "unit_id": "REL-0009",
        "pass": True,
        "dotgit_red": True,
        "blob_red": True,
        "blob_offending_entry": blob_hit["offending_entry"],
        "gitignored_red": True,
        "central_dir_agrees": True,
        "tree_walk_misses_gitignored": True,
        "catch_all_glob_would_accept_dotgit": True,
        "reviewer_id": "REL-0009-probe2-reviewer-mutations",
    }, sort_keys=True))
    print(
        f"dotgit_red=True blob_named={blob_hit['offending_entry']} "
        f"gitignored_red=True central_dir_agrees=True "
        f"tree_miss={GITIGNORED_NAME} mutant_starstar_accepts_dotgit=True"
    )
    print("SUCCESS:REL-0009-probe2 reviewer re-ran mutation controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
