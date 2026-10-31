"""INTEGRATE round 2 -- apply the two edits, on BYTES, with line endings pinned.

Why a script and not an editor: `_r6_transcript.py` is pure LF (0 CRLF) and
`.github/workflows/no-runtime-junk.yml` is 100% CRLF (138/138). A text-mode write on
Windows re-inserts CRLF and turns a 3-line change into a whole-file diff -- measured three
times in this program already. Every write below is `newline=""` on text read and explicit
bytes on the workflow, and each edit asserts its anchor is UNIQUE before touching anything.

The workflow is a SIBLING-VISIBLE file. `git status --porcelain -- .github/` was empty
immediately before this ran, and the assertions below require the original bytes to remain
an exact PREFIX of the result, so this can only append.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = subprocess.run(
    ["git", "-C", HERE, "rev-parse", "--show-toplevel"],
    capture_output=True,
    text=True,
).stdout.strip() or os.path.abspath(os.path.join(HERE, "..", ".."))

GATE = os.path.join(REPO, "command-center/slop-report/_r6_transcript.py")
WF = os.path.join(REPO, ".github/workflows/no-runtime-junk.yml")

OLD_FLAG = '    committed = "--committed" in sys.argv\n'
NEW_FLAG = """    # INTEGRATE round 2: flags are VALIDATED, and a worktree run can decline to write.
    # Measured live this round, not hypothesised: `_r6_transcript.py --help` was silently
    # accepted as "no flags", ran the DEFAULT worktree mode, and OVERWROTE the tracked
    # receipt `_r6_transcript.out.json`. Two consequences, both fixed here. (1) A typo'd
    # flag silently answers a different question than the one asked -- unknown flags now
    # fail closed with rc 2. (2) The one command an author is told to run BEFORE committing
    # a doc punished them for running it, because the pre-commit check must read the
    # WORKING TREE (the doc is not committed yet) and that is the mode that writes.
    # `--no-write` gives that check without mutating a tracked file.
    argv = sys.argv[1:]
    unknown = [a for a in argv if a not in ("--committed", "--no-write")]
    if unknown:
        print("FAILED:r6-transcript unknown flag(s): " + " ".join(unknown))
        print("usage: _r6_transcript.py [--committed] [--no-write]")
        return 2
    committed = "--committed" in argv
    # Default (no flags) still writes, so the run meant to refresh the receipt still does.
    no_write = committed or "--no-write" in argv
"""

OLD_WRITE = "    if not committed:\n"
NEW_WRITE = "    if not no_write:\n"

STEP = """      # A committed SLOP report may not publish a number its own committed receipt
      # refutes. Round 6 of this lane found two such lines BY HAND in SLOP-BUILD-R5.md: a
      # histogram published `d-zero=18` against a receipt saying 23, whose parts summed to
      # 300 against the 305 asserted in the same sentence. Nothing mechanical was checking
      # any of it, and every adversarial finding against this lane across seven rounds was
      # the same shape -- the receipt was right and the SENTENCE was wider than it.
      #
      # `--committed` reads the docs AND the receipts from HEAD blobs, which is the question
      # a CLONE asks. The default worktree mode answers only "clean on this disk" -- the
      # false negative round 7 measured in BOTH directions on a genuinely divergent key
      # (`n_before`, worktree 73 against committed 1). It writes no receipt, so the step
      # cannot dirty the tree it is checking.
      #
      # There is no separate --self-test here, on purpose: the T1/T5 both-states fixtures
      # live INSIDE the gate, run on every invocation and gate its exit code, so a silent
      # result is impossible without them having fired first. A gate that has never failed
      # is indistinguishable from a no-op, and this repo has shipped that exact shape.
      # Red-proof, executed in a fresh LF clone with the pre-existing CI measured BLIND to
      # the same injected defect:
      # command-center/slop-report/_i9_claims_redproof.out.json
      - name: gate-published-claims (no report may publish a number its receipt refutes)
        run: |
          python command-center/slop-report/_r6_transcript.py --committed
"""


def patch_gate() -> dict:
    with open(GATE, encoding="utf-8", newline="") as fh:
        text = fh.read()
    before = len(text)
    assert "\r\n" not in text, "gate was LF; refusing to touch a file whose EOL changed"
    for anchor in (OLD_FLAG, OLD_WRITE):
        n = text.count(anchor)
        assert n == 1, f"anchor is not unique (count={n}): {anchor!r}"
    text = text.replace(OLD_FLAG, NEW_FLAG).replace(OLD_WRITE, NEW_WRITE)
    with open(GATE, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return {
        "file": "_r6_transcript.py",
        "bytes_before": before,
        "bytes_after": len(text),
    }


def patch_workflow() -> dict:
    with open(WF, "rb") as fh:
        raw = fh.read()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n")
    assert crlf == lf, f"workflow is not uniformly CRLF ({crlf} of {lf})"
    assert b"gate-published-claims" not in raw, (
        "step already present -- refusing to double"
    )
    assert raw.endswith(b"\n"), "workflow does not end in a newline"
    add = STEP.replace("\n", "\r\n").encode("utf-8")
    out = raw + add
    assert out.startswith(raw), "original bytes are not a prefix -- refusing"
    with open(WF, "wb") as fh:
        fh.write(out)
    with open(WF, "rb") as fh:
        chk = fh.read()
    return {
        "file": "no-runtime-junk.yml",
        "bytes_before": len(raw),
        "bytes_after": len(chk),
        "crlf_before": crlf,
        "crlf_after": chk.count(b"\r\n"),
        "bare_lf_after": chk.count(b"\n") - chk.count(b"\r\n"),
        "prefix_preserved": chk.startswith(raw),
    }


def main() -> int:
    dirty = subprocess.run(
        ["git", "-C", REPO, "status", "--porcelain", "--", ".github/"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    res = {"repo": REPO, "github_dirty_before": dirty}
    assert dirty == "", f"a sibling is mid-edit under .github/: {dirty!r}"
    res["gate"] = patch_gate()
    res["workflow"] = patch_workflow()
    res["numstat"] = subprocess.run(
        ["git", "-C", REPO, "diff", "--numstat"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    print(json.dumps(res, indent=1, sort_keys=True))
    print("SUCCESS:i9-apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
