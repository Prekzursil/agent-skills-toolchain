"""Round 8 both-states control: mutate a REAL command doc, run the SHIPPED gate.

The round-8 arm ships five in-suite controls, but every one of them feeds the
predicate a string it built itself. That is not enough: round 7's first arm
passed its own in-suite controls and was still INERT, because the expectation
moved with the artifact. The only reading that settles it is the SHIPPED test,
run by pytest, against BYTES ON DISK.

    H1  the gate reads the command-doc corpus
        -> appending a fenced invocation of a script that exists nowhere
           makes pytest go RED
    H2  the gate reads something else, or short-circuits
        -> pytest stays GREEN on a genuinely broken tree

CONTROLS
    C1  fixed state must be GREEN first. Red-in-both-states measures nothing.
    C2  the injected token must not resolve, asserted before the mutation.
    C3  sha256 restore check, plus a scratch copy taken before any write.

The doc is read and written with ``newline=""`` so a CRLF working tree is not
rewritten to LF -- that would turn a 3-line append into a whole-file diff.
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

#: A top-level published command doc, so the mutation lands in the real corpus.
TARGET = "commands/prime.md"

INJECTED = "scripts/zzz-round8-bothstates-not-real.js"

GATE = (
    "ci/tests/test_command_doc_promises.py"
    "::test_no_command_doc_adds_a_new_invocation_of_a_missing_script"
)


def _read(rel: str) -> str:
    return io.open(REPO_ROOT / rel, encoding="utf-8", newline="").read()


def _write(rel: str, text: str) -> None:
    with io.open(REPO_ROOT / rel, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()[:16]


def _run_gate() -> int:
    return subprocess.run(
        [sys.executable, "-m", "pytest", GATE, "-q", "-p", "no:cacheprovider"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).returncode


def main() -> int:
    if not (REPO_ROOT / TARGET).is_file():
        print(f"FAILED:docs-r8-bothstates target missing {TARGET}")
        return 1
    if (REPO_ROOT / INJECTED).exists():
        print(f"FAILED:docs-r8-bothstates C2 {INJECTED} unexpectedly exists")
        return 1

    before = _digest(TARGET)
    scratch = Path(tempfile.mkdtemp(prefix="r8-bothstates-"))
    shutil.copy2(REPO_ROOT / TARGET, scratch / "orig")

    fixed_rc = _run_gate()
    if fixed_rc != 0:
        print(f"FAILED:docs-r8-bothstates C1 fixed state is not green (rc={fixed_rc})")
        return 1

    original = _read(TARGET)
    eol = "\r\n" if "\r\n" in original else "\n"
    try:
        _write(
            TARGET, original + eol.join(["", "```bash", f"node {INJECTED}", "```", ""])
        )
        broken_rc = _run_gate()
    finally:
        _write(TARGET, original)
        if _digest(TARGET) != before:
            _write(
                TARGET, io.open(scratch / "orig", encoding="utf-8", newline="").read()
            )

    restored = _digest(TARGET) == before
    ok = fixed_rc == 0 and broken_rc != 0 and restored
    print(
        f"{'SUCCESS' if ok else 'FAILED'}:docs-r8-bothstates "
        f"fixed_rc={fixed_rc} broken_rc={broken_rc} arms_differ={fixed_rc != broken_rc} "
        f"target={TARGET} eol={'CRLF' if eol == chr(13) + chr(10) else 'LF'} "
        f"restored={restored}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
