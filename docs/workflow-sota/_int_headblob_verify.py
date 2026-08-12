#!/usr/bin/env python3
"""End-to-end: does the COMMITTED tree carry the wiring, or only my working copy?

CI checks out blobs, not the working tree.  This rebuilds the files the wiring check
reads from ``git cat-file -p HEAD:<path>`` (never ``git archive``, which re-applies EOL
conversion on Windows) and runs the SAME test file against them.

Control: the same HEAD mirror with the step excised must go RED.  Without that, a mirror
that is green for an unrelated reason proves nothing.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_REL = "ci/tests/test_wf_timeout_ci_wiring.py"
FILES = [
    TEST_REL,
    "ci/tests/conftest.py",
    "ci/tests/dual_write_fixtures.py",
    ".github/workflows/quality.yml",
    ".github/workflows/skill-dual-write.yml",
    "tools/wf-timeout/wf_gate.py",
    "tools/wf-timeout/h6_extract.py",
    "tools/wf-timeout/h6_harness.mjs",
    "tools/wf-timeout/test_h6_timeout.py",
    "skills/workflow-authoring/templates/h6-timeout-heartbeat.md",
]
BLOCK_START = "      # tools/wf-timeout -- design item H6"
BLOCK_END = "      # ================================ VENDORED TOOL TREES"


def head_blob(rel: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-p", f"HEAD:{rel}"],
        capture_output=True,
        check=True,
    ).stdout


def build(dest: Path, excise: bool) -> int:
    crlf = 0
    for rel in FILES:
        data = head_blob(rel)
        crlf += data.count(b"\r\n")
        if excise and rel.endswith("quality.yml"):
            text = data.decode("utf-8")
            data = (
                text[: text.index(BLOCK_START)] + text[text.index(BLOCK_END) :]
            ).encode("utf-8")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return crlf


def run(dest: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_REL, "-q", "-p", "no:cacheprovider"],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    tail = [ln for ln in proc.stdout.splitlines() if ln.strip()][-1:]
    return proc.returncode, (tail[0] if tail else "<no output>")


def main() -> int:
    results = {}
    for name, excise, want_pass in (
        ("HEAD", False, True),
        ("HEAD-excised", True, False),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            crlf = build(dest, excise)
            rc, tail = run(dest)
            ok = (rc == 0) == want_pass
            results[name] = ok
            print(
                f"  {name:<13} crlf={crlf} rc={rc} -> "
                f"{'PASS' if rc == 0 else 'FAIL'} (want {'PASS' if want_pass else 'FAIL'}) [{tail}]"
            )
    if all(results.values()):
        print(
            "SUCCESS:headblob committed blobs carry the wiring; control fires without it"
        )
        return 0
    print("FAILED:headblob see above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
