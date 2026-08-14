"""Round 8: settle round 7's residual #5 by mutating the anchor, not stripping it.

THE CLAIM UNDER TEST
--------------------
``docs/_LANE-DOCS-BUILD-R7.md`` §6 residual 5 states:

    "The gate proves an anchor is PRESENT, not CORRECT. A future edit could
     replace ``67137879`` with a different valid-looking SHA and the arm would
     stay green."

Round 7's own in-suite control only ever STRIPS an anchor (``source.replace(sha, "")``).
Stripping and replacing are different mutations and a gate can plausibly catch one
and miss the other, so the residual was never actually measured -- it was inferred.

TWO HYPOTHESES, DIFFERENT PREDICTIONS (this is what makes it a control and not
an invocation):

    H1  the arm asserts the EXACT expected SHA from a non-carrier module
        -> replacing 67137879 with 0badc0de makes the expectation MISSING
        -> pytest goes RED
    H2  the arm asserts only that "some anchor-shaped token" survives
        -> a different valid-looking SHA satisfies it
        -> pytest stays GREEN   (this is what residual #5 asserts)

A run that cannot tell these apart is worthless, so the script refuses to report
unless C1 and C2 below both hold.

CONTROLS
--------
C1  precondition: the SHA must be present in the region BEFORE the mutation.
    Without it, "the gate fired" could just mean the file was already broken.
C2  fixed-state arm: the SHIPPED test must be GREEN on untouched bytes. A gate
    that is red in both states measures nothing.
C3  integrity: every carrier is snapshotted to a scratch copy before any write,
    restored in a ``finally``, and verified by sha256 against the pre-run digest.

Bytes are read and written with ``newline=""`` so a CRLF working tree is not
silently rewritten to LF (that turns a 1-token change into a whole-file diff).
"""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CARRIERS = (
    "ci/tests/test_command_doc_promises.py",
    "docs/_LANE-DOCS-BUILD-R5.md",
)
ANCHORS = ("67137879", "5d573583")

#: Valid-looking but wrong. Exactly the mutation residual #5 says goes undetected.
DECOY = "0badc0de"

SHIPPED_TEST = "ci/tests/test_command_doc_promises.py::test_round5_counts_keep_their_commit_anchors"


def _read(rel: str) -> str:
    return io.open(REPO_ROOT / rel, encoding="utf-8", newline="").read()


def _write(rel: str, text: str) -> None:
    with io.open(REPO_ROOT / rel, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()[:16]


def _run_shipped_test() -> int:
    """Run the SHIPPED gate, not a re-implementation of it."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", SHIPPED_TEST, "-q", "-p", "no:cacheprovider"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode


def _region_contains(rel: str, sha: str) -> bool:
    """Use the SHIPPED region extractor so C1 asks the same question the gate does."""
    sys.path.insert(0, str(REPO_ROOT / "ci" / "tests"))
    import test_command_doc_promises as gate  # noqa: PLC0415

    return sha in gate._count_region(rel, _read(rel))


def main() -> int:
    before = {rel: _digest(rel) for rel in CARRIERS}
    scratch = Path(tempfile.mkdtemp(prefix="r8-anchor-"))
    for rel in CARRIERS:
        shutil.copy2(REPO_ROOT / rel, scratch / Path(rel).name)

    results: list[tuple[str, str, int, bool]] = []
    fixed_rc = -1
    try:
        # C2 -- the fixed state must be green, or a red reading means nothing.
        fixed_rc = _run_shipped_test()
        if fixed_rc != 0:
            print(f"FAILED:docs-r8-anchor C2 fixed-state is NOT green (rc={fixed_rc})")
            return 1

        for rel in CARRIERS:
            original = _read(rel)
            for sha in ANCHORS:
                # C1 -- the mutation must actually change the region under test.
                pre = _region_contains(rel, sha)
                if not pre:
                    print(f"FAILED:docs-r8-anchor C1 {sha} absent from {rel} region")
                    return 1
                try:
                    _write(rel, original.replace(sha, DECOY))
                    rc = _run_shipped_test()
                finally:
                    _write(rel, original)
                results.append((rel, sha, rc, pre))
    finally:
        for rel in CARRIERS:
            if _digest(rel) != before[rel]:
                _write(
                    rel,
                    io.open(
                        scratch / Path(rel).name, encoding="utf-8", newline=""
                    ).read(),
                )

    # C3 -- integrity.
    restored = all(_digest(rel) == before[rel] for rel in CARRIERS)

    fired = sum(1 for _, _, rc, _ in results if rc != 0)
    total = len(results)

    for rel, sha, rc, _ in results:
        print(
            f"  {rel:<44} {sha} -> {DECOY}  pytest rc={rc}  "
            f"{'FIRES' if rc else 'GREEN'}"
        )

    verdict = (
        "H1-exact-sha"
        if fired == total
        else ("H2-shape-only" if fired == 0 else "MIXED")
    )
    ok = restored and fired == total
    print(
        f"{'SUCCESS' if ok else 'FAILED'}:docs-r8-anchor "
        f"fixed_state_rc={fixed_rc} mutations={total} fired={fired} "
        f"verdict={verdict} restored={restored}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
