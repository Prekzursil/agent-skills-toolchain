"""INTEGRATE / step I4 -- wire the gate into CI, byte-safely.

.github/workflows/no-runtime-junk.yml is 100% CRLF (121/121). Writing it back through a
text-mode round trip would either flip it to LF or reflow the whole file, turning a 12-line
addition into a whole-file diff -- a failure this repo has already paid for three times in
one night. So the patch is applied to BYTES with an explicit b"\\r\\n", and asserted:

  * the pre-existing bytes are an exact PREFIX of the result (nothing rewritten),
  * CRLF count rises by exactly the number of lines added,
  * no bare-LF line is introduced.

WHY THIS FILE AND NOT quality.yml. .quality/charter_check.sh enforces a CLOSED gate set:
every `gate-<slug>` marker in quality.yml must map back to a slug in .quality/charter.yml
and vice versa. Adding a step there would either break that reverse check or require
expanding the declared 7-gate charter -- a governance change, not an integration. This repo
already puts a gate outside the closed set in exactly this file (`gate-no-runtime-junk` is
not a charter slug), so that is the precedented home. It is also thematically the mirror of
what is already there: no-runtime-junk fails when git TRACKS a file it must not; this fails
when a committed document PROMISES a file git does not track.

SHARED FILE. This is a sibling-visible edit and it is declared as one. Verified `git status
--porcelain .github/` is empty immediately before writing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
WF = ROOT / ".github/workflows/no-runtime-junk.yml"

ANCHOR = b'print("OK: crcp reports deny-by-default holds (6 denied, 2 admitted).")\r\n'

STEP = [
    "      # A committed document may not publish a command that a clone cannot run. The SLOP",
    "      # lane found 45 probe scripts named by committed artifacts while .gitignore kept every",
    "      # one untracked -- the citation resolved on the author's disk and resolved to nothing",
    "      # for everyone else. It carried those 45; nothing stopped the 46th, and there already",
    "      # is one. This gate extracts every `python <path>` invocation from the tracked .md",
    "      # under command-center/ and docs/ and requires <path> to be TRACKED.",
    "      #",
    "      # --self-test runs FIRST and on purpose: it proves the gate can still go RED (synthetic",
    "      # known-bad flagged, known-good clean) before its silence is allowed to mean anything.",
    "      # A gate that has never failed is indistinguishable from a no-op, and this repo has",
    "      # shipped that exact shape. Red-proof, in a fresh LF clone with the pre-existing CI",
    "      # measured blind to the same injected defect:",
    "      # command-center/slop-report/_i3_integration_redproof.out.json",
    "      - name: gate-published-commands (no doc may publish a command a clone cannot run)",
    "        run: |",
    "          python command-center/slop-report/check_published_commands.py --self-test",
    "          python command-center/slop-report/check_published_commands.py",
]


def main() -> int:
    dirty = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", ".github/"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        print(f"FAILED:i4 .github/ is dirty -- a sibling may be mid-edit:\n{dirty}")
        return 1

    original = WF.read_bytes()
    if ANCHOR not in original:
        print("FAILED:i4 anchor line not found -- the workflow changed under me")
        return 1
    if b"gate-published-commands" in original:
        print("FAILED:i4 already wired; refusing to double-append")
        return 1

    addition = b"".join(line.encode("utf-8") + b"\r\n" for line in STEP)
    patched = original + addition

    checks = {
        "original_is_exact_prefix": patched[: len(original)] == original,
        "crlf_grew_by_added_lines": patched.count(b"\r\n")
        == original.count(b"\r\n") + len(STEP),
        "no_bare_lf_introduced": patched.count(b"\n") == patched.count(b"\r\n"),
        "step_present": b"gate-published-commands" in patched,
    }
    for k, v in checks.items():
        print(f"   {'ok  ' if v else 'FAIL'} {k}")
    if not all(checks.values()):
        print("FAILED:i4 byte-safety checks did not hold; nothing written")
        return 1

    WF.write_bytes(patched)
    after = WF.read_bytes()
    print(
        f"\nwrote {WF}  bytes {len(original)} -> {len(after)}  "
        f"CRLF {original.count(b'\r\n')} -> {after.count(b'\r\n')}"
    )
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "diff",
            "--numstat",
            "--",
            ".github/workflows/no-runtime-junk.yml",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    print(f"git numstat: {diff}")
    if not diff.startswith(f"{len(STEP)}\t0\t"):
        print(
            f"FAILED:i4 numstat is not +{len(STEP)}/-0 -- the diff is wider than the addition"
        )
        return 1
    print("SUCCESS:i4 wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
