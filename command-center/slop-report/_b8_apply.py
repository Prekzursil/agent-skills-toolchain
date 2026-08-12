"""BUILD R1 -- apply the bucket-(b) fix: negate the 45 cited probes, exclude them from ruff.

Byte-exact, LF-preserving (both files are LF; reading/writing without newline="" would
re-insert CRLF and turn a 2-hunk change into a whole-file diff -- that has bitten three times
in this program). Idempotent: re-running makes no second insertion.
"""

import json
import os
import sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
GITIGNORE = os.path.join(ROOT, ".gitignore")
RUFFTOML = os.path.join(ROOT, "ruff.toml")
ANCHOR = "!platform/lib/_gen_schema_substrate.py\n"
MARK = "# EXCEPTION 2, same shape and the same evidence"

GI_COMMENT = """
# EXCEPTION 2, same shape and the same evidence standard as the generator above.
# `command-center/_*.py` (line 76) ignores 123 of 123 root-level probe scripts and 0 are
# tracked, so 1,269,072 B of them exist only on one disk. Measured: 45 of those 123 are NAMED
# INSIDE COMMITTED ARTIFACTS (one `git grep -F` over HEAD blobs; detector controlled both ways
# -- it finds 248 citers for the known-referenced `_gen_schema_substrate.py` and 0 for a
# nonexistent name). On a fresh clone every one of those 45 citations dangles: the artifact
# names a probe the clone does not contain, so its evidence cannot be re-run or even read.
# That contradicts line 70's own header, "the probe SCRIPTS are kept as provenance".
#
# Precedent, not a new policy: commit `d53485ce` ("chore: commit six root-level probes a
# TRACKED audit cites but a clone lacks") already did exactly this once at repo root.
# Only the 45 CITED scripts are negated. The other 78 stay ignored -- absence of a citation is
# not evidence of worthlessness, so they are left alone rather than proposed for deletion.
#
# They are committed BYTE-UNCHANGED and excluded in ruff.toml instead of being reformatted.
# Reason, stated because the safe-looking choice is the wrong one: committing these 45 with no
# ruff exclusion turns `gate-lint-format` RED -- measured in a fresh LF clone of HEAD, 29 files
# would be reformatted and `ruff check` finds 9 errors, versus 0 and 0 with the exclusion.
# Reformatting them was considered and REJECTED: the digest-lock detector that would have
# proven it safe FAILED its own positive control (the known provenance-locked
# `casualty/probes/adv0022_probe2.py` did not match the digests published near its name), so
# "no receipt depends on these bytes" is UNVERIFIED, not established. Settling experiment:
# locate the casualty sha256 manifest and re-run the matcher against it; until then the
# byte-preserving route is the one that cannot destroy evidence.
"""

RT_COMMENT = """    # Cited-but-ignored root probe scripts, committed byte-unchanged by the SLOP lane.
    # 45 of the 123 `command-center/_*.py` are named inside committed artifacts, so a clone
    # needs them or those citations dangle (see the .gitignore EXCEPTION 2 block). They are
    # evidence, not source: they were written once to answer one question. Same trade-off
    # already settled above for `command-center/casualty/probes` -- there is no per-file escape
    # from `ruff format` that does not itself change the bytes, and a digest-lock check on
    # these files failed its positive control, so the bytes are preserved rather than
    # reformatted on an unproven assumption. Measured: with this line the gate is green
    # (0 reformat, 0 lint); without it, 29 reformat + 9 lint errors.
    "command-center/_*.py",
"""


def read(p):
    with open(p, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(s)


def main():
    cited = json.load(
        open(
            os.path.join(ROOT, "command-center/slop-report/_b1_cited_probes.out.json"),
            encoding="utf-8",
        )
    )["cited_names"]
    assert len(cited) == 45, len(cited)

    gi = read(GITIGNORE)
    assert "\r\n" not in gi, "gitignore is not LF -- refusing to rewrite"
    if MARK in gi:
        print("gitignore: already patched, skipping")
    else:
        assert gi.count(ANCHOR) == 1, f"anchor count {gi.count(ANCHOR)}"
        block = GI_COMMENT + "".join(f"!command-center/{n}\n" for n in cited)
        gi = gi.replace(ANCHOR, ANCHOR + block, 1)
        write(GITIGNORE, gi)
        print(
            f"gitignore: inserted {len(cited)} negations after the generator exception"
        )

    rt = read(RUFFTOML)
    # ruff.toml is CRLF in this worktree while .gitignore is LF, so the inserted block must
    # adopt the HOST FILE's ending. Writing LF into a CRLF file makes every later line read as
    # changed and turns a 1-hunk edit into a whole-file diff.
    eol = "\r\n" if rt.count("\r\n") > rt.count("\n") // 2 else "\n"
    if '"command-center/_*.py",' in rt:
        print("ruff.toml: already patched, skipping")
    else:
        anchor = f"extend-exclude = [{eol}"
        assert rt.count(anchor) == 1, f"anchor count {rt.count(anchor)} for eol={eol!r}"
        block = RT_COMMENT.replace("\n", eol) if eol != "\n" else RT_COMMENT
        rt = rt.replace(anchor, anchor + block, 1)
        write(RUFFTOML, rt)
        print(f"ruff.toml: added command-center/_*.py to extend-exclude (eol={eol!r})")

    print("\nnow verifying ignore status flipped for the 45 and NOT for the other 78")
    return 0


if __name__ == "__main__":
    sys.exit(main())
