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

  4. ROUND-1 DEFECT, CONFIRMED BY THE VERIFIER AND FIXED HERE -- the SAME error a fourth
     time, now inside the correction for the first three. Round 1 shipped:

         return rc(["git", "merge-base", "--is-ancestor", root, "HEAD"], path) == 0

     `--is-ancestor` answers with THREE codes, not two: 0 = ancestor, 1 = genuinely not an
     ancestor, and 128 = `fatal: Not a valid commit name <sha>`, i.e. the root object is
     absent from this store so THE QUESTION COULD NOT BE ASKED. `== 0` folds 1 and 128 into
     one `False`, turning an error into a confident negative. MEASURED on this population
     (`rc128_redproof.py`, controlled on all three codes): 168 rc=0, 105 rc=1, **20 rc=128**
     -- and 105 + 20 = 125, exactly the "REJECTED (store held the object) : 125" round 1
     published. Every rc=128 row was a checkout whose identity was never determined.

     Round 1's own sibling file had already recorded this shape and its fix --
     salvage_atrisk.py:24-28, "`git log --not --remotes` returns EMPTY without a positive
     ref ... reachability_probe.py prints the query's return code so the silence cannot be
     mistaken for an answer again". This file printed no return code.

     REFUTED WORDING, kept rather than deleted: round 1 published "CORRECTED TOTAL 170" and
     "the real count is 170, not 25". 170 was measured over a population that had silently
     dropped the 20 undecidable rows; the corrected figure is in `identity-by-ancestry.json`
     under `corrected_total`, and the run log prints both.

     rc=128 has TWO causes and they land on opposite verdicts, so the shallow flag alone is
     not the fallback: (a) a SHALLOW clone of this repo -- `git clone --depth N` truncates
     history, so our root is legitimately absent; (b) an UNRELATED repo whose store never
     held our root at all. Measured: 20 rc=128 rows, 10 shallow, 4 with origin = this repo.

  5. MY OWN FIRST FIX WAS DEFECT 2 AGAIN, caught before shipping. The first resolution rule
     here was `origin_match OR census >= 0.5`, on the reasoning that an inclusive error only
     inflates a count while an exclusive one can drop a checkout holding the only copy of
     something. Running it printed 12 rows where the two signals DISAGREED -- and they were
     vendored third-party clones, exactly the failure this file's own defect 2 records:

         dsifry/metaswarm       census 95-96%   this repo VENDORS metaswarm
         Prekzursil/openmm-md-mcp   census 67%   this repo vendors its skill
         blader/humanizer           census 50%   likewise

     Folding those in would have published a count sourced from other people's repos. What
     caught it was PRINTING the disagreement instead of collapsing it. Measured on all 22
     residual rows, the census alone is wrong 8 times, every one in the inflating direction.
     `resolve_identity` therefore records the census and never lets it decide.

Residual cases ancestry cannot answer, handled explicitly rather than silently:
  * a 0-commit working copy (no HEAD) -- ancestry is undefined.
  * rc=128, the root object absent from the store.
    Both go through `resolve_identity`: origin naming this repo wins; origin naming another
    REMOTE is an authoritative negative; a LOCAL-path origin resolves transitively; and only
    where there is no origin at all does a root-marker test decide. Markers do NOT outrank
    origin -- measured, a genuine clone of this repo scores 3/10 markers while a vendored
    metaswarm clone scores 4/10, so markers cannot stand alone.
  * a checkout whose history was rewritten past the root -- flagged, not assumed.

Read-only.
"""

from __future__ import annotations

import hashlib
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


def ancestry(path: str, root: str) -> tuple[str, int | None]:
    """Classify a checkout against a root commit, WITHOUT discarding the return code.

    Returns (verdict, rc) where verdict is one of:
        "no-head"      the checkout has 0 commits; ancestry is undefined
        "ancestor"     rc=0, HEAD descends from `root`
        "not-ancestor" rc=1, git looked and the answer is genuinely no
        "undecidable"  any other rc (128 in practice): `root` is not an object in this
                       store, so git could not evaluate the question at all

    The third and fourth cases are DIFFERENT ANSWERS and round 1 returned `False` for both.
    See defect 4 in the module docstring.
    """
    if not out(["git", "rev-parse", "HEAD"], path):
        return "no-head", None
    code = rc(["git", "merge-base", "--is-ancestor", root, "HEAD"], path)
    return {0: "ancestor", 1: "not-ancestor"}.get(code, "undecidable"), code


def descends(path: str, root: str) -> bool | None:
    """Back-compat wrapper for the CONTROL block: True / False / None.

    Kept deliberately narrow. It is only sound where the root object is known to be in the
    store -- which is true of the two hand-picked control checkouts and is NOT true of the
    population, so the sweep below calls `ancestry()` directly.
    """
    verdict, _ = ancestry(path, root)
    return {"ancestor": True, "not-ancestor": False}.get(verdict)


# Long-lived top-level entries of THIS repo. Used only where ancestry cannot run AND there
# is no origin to appeal to. Deliberately NOT weighted toward recent additions: a 5-entry
# set built from REPO-TOPOLOGY.md/docs/ssot scored genuine-but-old checkouts at 1-2/5.
MARKERS = (
    "REPO-TOPOLOGY.md",
    "AGENTS.md",
    "command-center",
    "ci/tests",
    "docs/ssot",
    "skills",
    "hooks",
    "tools",
    ".github",
    "ruff.toml",
)
# Set BY THE BOTH-STATES CONTROL in rc128_resolve_probe.py, not by fitting these rows: at
# MARKER_MIN=3 that control FAILED because the known-vendored metaswarm clone scores 4/10.
# The threshold must sit above the measured negative (4) and below the lowest true positive
# among the rows this test decides (6).
MARKER_MIN = 5


def markers(path: str) -> int:
    return sum(1 for m in MARKERS if (Path(path) / m).exists())


def resolve_identity(path: str, census_ratio: float) -> dict:
    """Decide "is this a checkout of THIS repo" where ancestry could not.

    Rule, chosen from measurement (`rc128_resolve_probe.py`), not from first principles:

      origin names this repo        -> checkout
      origin names a LOCAL path     -> resolve transitively through that checkout's origin
      origin names another REMOTE   -> NOT ours. AUTHORITATIVE, because the blob census is
                                       demonstrably misled here: this repo vendors metaswarm,
                                       so `dsifry/metaswarm` clones score 95-96%.
      origin absent                 -> root-marker test, the only signal left.

    Why origin outranks the markers rather than the other way round: measured, a genuine
    clone of this repo (`work/agent-skills-toolchain-re`, origin = this repo) scores 3/10
    markers while a vendored metaswarm clone scores 4/10. Markers cannot stand alone.

    The census is recorded but never decides. On the 20 rows this ran over it would have
    been wrong 9 times, every one in the inflating direction.
    """
    origin = out(["git", "remote", "get-url", "origin"], path)
    m = markers(path)
    if not origin:
        kind, verdict = "absent", m >= MARKER_MIN
    elif "agent-skills-toolchain" in origin:
        kind, verdict = "this-repo", True
    elif origin.startswith(("http", "git@", "ssh:")):
        kind, verdict = "other-remote", False
    else:
        up = (
            out(["git", "remote", "get-url", "origin"], origin)
            if Path(origin).exists()
            else ""
        )
        verdict = "agent-skills-toolchain" in up or "agent-skills-toolchain" in origin
        kind = f"local->{'ours' if verdict else 'other'}"
    return {
        "origin_url": origin,
        "origin_kind": kind,
        "markers": m,
        "census_ratio": census_ratio,
        "census_would_say": census_ratio >= 0.5,
        "census_disagrees": bool(verdict) != (census_ratio >= 0.5),
        "is_checkout": bool(verdict),
    }


def tree_census(path: str, reach: set[str], cap: int = 400) -> dict:
    """What fraction of this working tree's blobs are reachable in canonical?

    Content-based, so it works where ancestry cannot: a 0-commit copy, or a shallow clone
    whose history was truncated past our root. Hashes raw AND LF-normalised bytes -- the
    working tree is CRLF on this box while git stores LF, and a raw-only comparison scored
    0% on a file that was genuinely present (the control that caught it is in
    salvage_atrisk.py).
    """
    hit = tot = 0
    for dirpath, dirnames, filenames in os.walk(path):
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
            if _blob_sha(b) in reach or _blob_sha(b.replace(b"\r\n", b"\n")) in reach:
                hit += 1
            if tot >= cap:
                break
        if tot >= cap:
            break
    ratio = (hit / tot) if tot else 0.0
    return {"sampled": tot, "in_canonical": hit, "ratio": round(ratio, 3)}


def _blob_sha(b: bytes) -> str:
    # sha1 is not a choice here: a git blob id IS sha1("blob <len>\0" + content), so this
    # reproduces git's own object id rather than securing anything. `usedforsecurity=False`
    # is the remedy quality.opengrep.python-weak-hash-md5-sha1 names for exactly this case.
    #
    # PROVEN before editing, because a changed digest would silently break every identity
    # comparison built on this: identical hexdigest with and without the flag across 5 probes
    # (empty, short, newline-terminated, 4 KB, all 256 byte values); a control showing
    # sha1 != md5 so the equality is a reading and not a tautology; and `git hash-object
    # --stdin` agreeing with BOTH forms on the same input.
    h = hashlib.sha1(b"blob %d\0" % len(b), usedforsecurity=False)
    h.update(b)
    return h.hexdigest()


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

    confirmed, rejected, no_head, undecidable = [], [], [], []
    rc_hist: dict[str, int] = {}
    for r in distinct:
        verdict, code = ancestry(r["path"], ROOT_COMMIT)
        r["ancestry"] = verdict
        r["ancestry_rc"] = code
        rc_hist[str(code)] = rc_hist.get(str(code), 0) + 1
        {
            "ancestor": confirmed,
            "not-ancestor": rejected,
            "no-head": no_head,
            "undecidable": undecidable,
        }[verdict].append(r)

    # Print the RETURN-CODE histogram, not just the verdicts. Round 1 printed only the
    # verdicts and that is precisely how 20 unanswerable rows hid inside a "rejected" count.
    print(f"  rc histogram                        : {rc_hist}")
    print(f"  ANCESTRY-CONFIRMED (rc=0)           : {len(confirmed)}")
    print(f"  REJECTED, git answered no (rc=1)    : {len(rejected)}")
    print(f"  UNDECIDABLE, root absent (rc=128)   : {len(undecidable)}")
    print(f"  no HEAD (0-commit working copies)   : {len(no_head)}")

    reach = {
        ln.split(" ", 1)[0].strip()
        for ln in out(["git", "rev-list", "--objects", "--all"], CANONICAL).splitlines()
        if len(ln.split(" ", 1)[0].strip()) == 40
    }
    if len(reach) < 1000:
        # Fail CLOSED: an empty reachable set would score every census 0% and read as
        # "all unrelated" -- a broken reader reporting a clean answer.
        print(
            f"FAILED:identity-ancestry reachable set implausibly small ({len(reach)})"
        )
        return 3

    # CONTROL for the census reader, on two checkouts of KNOWN kind. It must score a real
    # checkout of this repo high and an unrelated repo low; if it cannot separate those it
    # cannot be trusted to resolve the undecidable rows either.
    census_ctl = {
        "known_toolchain": tree_census(
            "C:/Users/Prekzursil/source/ast-integrate", reach, cap=120
        ),
        "known_unrelated": tree_census(known_reframe, reach, cap=120),
    }
    census_ctl["discriminates"] = (
        census_ctl["known_toolchain"]["ratio"]
        >= 0.5
        > census_ctl["known_unrelated"]["ratio"]
    )
    print(
        f"\nCONTROL census toolchain : {census_ctl['known_toolchain']['ratio']:.0%}\n"
        f"CONTROL census unrelated : {census_ctl['known_unrelated']['ratio']:.0%}\n"
        f"discriminates: {census_ctl['discriminates']}"
    )
    if not census_ctl["discriminates"]:
        print("FAILED:identity-ancestry census control did not discriminate")
        return 3

    # Both residual groups -- 0-commit copies and rc=128 rows -- go through ONE resolver,
    # so a reader does not have to hold two different rules in mind. The census is measured
    # for every row and printed, but `resolve_identity` never lets it decide.
    print(f"\nresolving {len(undecidable)} undecidable + {len(no_head)} no-HEAD rows:")
    print(f"    {'kind':<14}{'mark':<6}{'census':<8}{'shallow':<9}verdict / path")
    for r in undecidable + no_head:
        r["tree_census"] = tree_census(r["path"], reach)
        r["is_shallow"] = (
            out(["git", "rev-parse", "--is-shallow-repository"], r["path"]) == "true"
        )
        r.update(resolve_identity(r["path"], r["tree_census"]["ratio"]))
        print(
            f"    {r['origin_kind']:<14}{r['markers']}/{len(MARKERS):<4}"
            f"{r['census_ratio']:<8.0%}{str(r['is_shallow']):<9}"
            f"{'CHECKOUT' if r['is_checkout'] else 'not-ours':<10}{r['path'][:46]}"
        )

    census_yes_rows = [r for r in no_head if r["is_checkout"]]
    undecidable_yes = [r for r in undecidable if r["is_checkout"]]
    disagreements = [r for r in undecidable + no_head if r["census_disagrees"]]
    total = len(confirmed) + len(census_yes_rows) + len(undecidable_yes)

    by_name = len([r for r in distinct if r["sig_name"]])
    print(f"\n{'=' * 66}")
    print(f"  ancestry-confirmed checkouts        : {len(confirmed)}")
    print(f"  0-commit working copies confirmed   : {len(census_yes_rows)}")
    print(f"  rc=128 rows resolved as checkouts   : {len(undecidable_yes)}")
    print(f"  CORRECTED TOTAL                     : {total}")
    print(
        f"  round 1 published (rc=128 dropped)  : {len(confirmed) + len(census_yes_rows)}"
    )
    print(f"  the OLD name-based test reports     : {by_name}")
    print("  inventory's published figure        : 25")
    if disagreements:
        print(
            f"  !! the blob census alone would have been WRONG on {len(disagreements)} of "
            f"{len(undecidable) + len(no_head)} residual rows"
        )

    report = {
        "control": ctl,
        "census_control": census_ctl,
        "distinct_candidates": len(distinct),
        "rc_histogram": rc_hist,
        "ancestry_confirmed": len(confirmed),
        "rejected_git_answered_no": len(rejected),
        "undecidable_root_absent": len(undecidable),
        "no_head": len(no_head),
        "census_confirmed": [r["path"] for r in census_yes_rows],
        "residual_rows": [
            {
                "path": r["path"],
                "ancestry": r["ancestry"],
                "is_shallow": r["is_shallow"],
                "origin_kind": r["origin_kind"],
                "origin_url": r["origin_url"],
                "markers": f"{r['markers']}/{len(MARKERS)}",
                "census_ratio": r["census_ratio"],
                "census_would_say": r["census_would_say"],
                "census_disagrees": r["census_disagrees"],
                "is_checkout": r["is_checkout"],
            }
            for r in undecidable + no_head
        ],
        "census_alone_would_be_wrong_on": len(disagreements),
        "undecidable_resolved_as_checkouts": [r["path"] for r in undecidable_yes],
        "corrected_total": total,
        "round1_published_total": len(confirmed) + len(census_yes_rows),
        "old_name_test_total": by_name,
        # `confirmed_paths` keeps its round-1 meaning (ancestry rc=0 only) so an existing
        # reader is not silently handed a wider set; the union any classifier should
        # actually consume is `all_checkout_paths`.
        "confirmed_paths": sorted(r["path"] for r in confirmed),
        "all_checkout_paths": sorted(
            [r["path"] for r in confirmed]
            + [r["path"] for r in census_yes_rows]
            + [r["path"] for r in undecidable_yes]
        ),
        "rejected_examples": [
            {"path": r["path"], "origin": r["origin"]} for r in rejected[:15]
        ],
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")
    print(
        f"SUCCESS:identity-ancestry total={total} rc128_recovered={len(undecidable_yes)} "
        f"old_test={by_name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
