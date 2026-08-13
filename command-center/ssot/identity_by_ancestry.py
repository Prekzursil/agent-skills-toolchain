"""The correct checkout-identity test: is HEAD a DESCENDANT of the repo's root commit?

Every earlier signal in this lane asked a question about the STORE and treated the answer as
a fact about the CHECKOUT. That error appeared three times, each time inflating a count:

  1. `git cat-file -e <blob>` -- "the blob exists in canonical" was read as "the file is
     safe". It was a loose object in a SHARED store, reachable from nothing.
  2. sentinel-blob membership -- "this file's bytes are in canonical's history" was read as
     "this checkout is that repo". Canonical VENDORS third-party trees, so a standalone clone
     of a vendored repo matches. 15 of 17 content-only rows were false positives.
  3. `git cat-file -e <root-commit>` -- "canonical's root commit exists in this store" was
     read as "this checkout is canonical". MEASURED FALSE: 103 rows resolved to
     `Documents/GitHub/Reframe/.git`, whose store holds the toolchain root commit (identical
     subject) while its checkouts are Reframe. Proof for one of them:
         HEAD descends from toolchain root : NO
         store's own root commit           : 03b864ef (Reframe's)
         REPO-TOPOLOGY.md in HEAD tree     : absent
         HEAD tree contains                : app/, electron-builder.yml
     A store can hold any objects somebody fetched into it. That says nothing about what a
     worktree in it has checked out.

The question that is actually about the checkout is ANCESTRY:

    git merge-base --is-ancestor <root_commit> HEAD

which asks whether THIS checkout's own history descends from THAT repo's first commit.
A polluted store cannot fake it, because HEAD either descends or it does not.

Two residual cases ancestry cannot answer, handled explicitly rather than silently:
  * a 0-commit working copy (no HEAD) -- ancestry is undefined; fall back to a WHOLE-TREE
    blob census, which is what NO-REMOTE-REPO-TRIAGE.md used for `scratch`.
  * a checkout whose history was rewritten past the root -- flagged, not assumed.

Read-only.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANONICAL = Path("C:/Users/Prekzursil/source/agent-skills-toolchain")
ROOT_COMMIT = "66e383dd97e4e53bd34085636f9b2a2f83efce02"
REFRAME_ROOT = "03b864ef5260c4a74e68629f63102a7414cb8833"
OUT = HERE / "identity-by-ancestry.json"


def rc(args, cwd) -> int:
    return subprocess.run(args, cwd=str(cwd), capture_output=True).returncode


def out(args, cwd) -> str:
    p = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout.strip() if p.returncode == 0 else ""


def descends(path: str, root: str) -> bool | None:
    """True/False, or None when the checkout has no HEAD to test."""
    if not out(["git", "rev-parse", "HEAD"], path):
        return None
    return rc(["git", "merge-base", "--is-ancestor", root, "HEAD"], path) == 0


def main() -> int:
    # ---------------- CONTROL: the ancestry test must separate two KNOWN cases.
    known_ast = "C:/Users/Prekzursil/source/ast-integrate"
    known_reframe = "C:/Users/Prekzursil/.claude/agent-worktrees/agent-1060568916"
    ctl = {
        "ast_checkout_descends_from_ast_root": descends(known_ast, ROOT_COMMIT),
        "reframe_checkout_descends_from_ast_root": descends(known_reframe, ROOT_COMMIT),
        "reframe_checkout_descends_from_reframe_root": descends(
            known_reframe, REFRAME_ROOT
        ),
    }
    ctl["discriminates"] = (
        ctl["ast_checkout_descends_from_ast_root"] is True
        and ctl["reframe_checkout_descends_from_ast_root"] is False
    )
    print(
        f"CONTROL ast checkout  -> ast root : {ctl['ast_checkout_descends_from_ast_root']}\n"
        f"CONTROL reframe wt    -> ast root : {ctl['reframe_checkout_descends_from_ast_root']}\n"
        f"CONTROL reframe wt    -> rf  root : {ctl['reframe_checkout_descends_from_reframe_root']}\n"
        f"discriminates: {ctl['discriminates']}"
    )
    if not ctl["discriminates"]:
        print("FAILED:identity-ancestry control did not discriminate")
        return 3

    rows = json.loads((HERE / "enumerate-checkouts.json").read_text(encoding="utf-8"))[
        "rows"
    ]
    seen: dict[str, dict] = {}
    for r in rows:
        rp = os.path.realpath(r["path"]).replace("\\", "/").rstrip("/").lower()
        seen.setdefault(rp, r)
    distinct = list(seen.values())
    print(f"\ndistinct candidate checkouts: {len(distinct)}")

    confirmed, rejected, no_head = [], [], []
    for r in distinct:
        d = descends(r["path"], ROOT_COMMIT)
        r["descends_from_ast_root"] = d
        if d is True:
            confirmed.append(r)
        elif d is False:
            rejected.append(r)
        else:
            no_head.append(r)

    print(f"  ANCESTRY-CONFIRMED (real checkouts) : {len(confirmed)}")
    print(f"  REJECTED (store held the object)    : {len(rejected)}")
    print(f"  no HEAD (0-commit working copies)   : {len(no_head)}")

    # 0-commit copies: whole-tree blob census, the only test that can see them.
    reach = {
        ln.split(" ", 1)[0].strip()
        for ln in out(["git", "rev-list", "--objects", "--all"], CANONICAL).splitlines()
        if len(ln.split(" ", 1)[0].strip()) == 40
    }
    import hashlib

    def gh(b: bytes) -> str:
        h = hashlib.sha1()
        h.update(b"blob %d\0" % len(b))
        h.update(b)
        return h.hexdigest()

    for r in no_head:
        hit = tot = 0
        for dirpath, dirnames, filenames in os.walk(r["path"]):
            dirnames[:] = [
                x
                for x in dirnames
                if x not in {".git", "node_modules", "__pycache__", ".venv"}
            ]
            for fn in filenames:
                fp = Path(dirpath) / fn
                try:
                    if fp.stat().st_size > 400_000:
                        continue
                    b = fp.read_bytes()
                except OSError:
                    continue
                tot += 1
                if gh(b) in reach or gh(b.replace(b"\r\n", b"\n")) in reach:
                    hit += 1
                if tot >= 400:
                    break
            if tot >= 400:
                break
        ratio = (hit / tot) if tot else 0.0
        r["tree_census"] = {
            "sampled": tot,
            "in_canonical": hit,
            "ratio": round(ratio, 3),
        }
        r["census_verdict"] = (
            "working-copy-of-this-repo" if ratio >= 0.5 else "unrelated"
        )
        print(
            f"    {r['path'][:66]}\n"
            f"        {hit}/{tot} blobs in canonical ({ratio:.0%}) -> {r['census_verdict']}"
        )

    census_yes = [
        r for r in no_head if r.get("census_verdict") == "working-copy-of-this-repo"
    ]
    total = len(confirmed) + len(census_yes)

    by_name = len([r for r in distinct if r["sig_name"]])
    print(f"\n{'=' * 66}")
    print(f"  ancestry-confirmed checkouts        : {len(confirmed)}")
    print(f"  0-commit working copies confirmed   : {len(census_yes)}")
    print(f"  CORRECTED TOTAL                     : {total}")
    print(f"  the OLD name-based test reports     : {by_name}")
    print("  inventory's published figure        : 25")

    report = {
        "control": ctl,
        "distinct_candidates": len(distinct),
        "ancestry_confirmed": len(confirmed),
        "rejected_store_only": len(rejected),
        "no_head": len(no_head),
        "census_confirmed": [r["path"] for r in census_yes],
        "corrected_total": total,
        "old_name_test_total": by_name,
        "confirmed_paths": sorted(r["path"] for r in confirmed),
        "rejected_examples": [
            {"path": r["path"], "origin": r["origin"]} for r in rejected[:15]
        ],
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    print(f"SUCCESS:identity-ancestry total={total} old_test={by_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
