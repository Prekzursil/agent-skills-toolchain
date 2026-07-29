#!/usr/bin/env python3
"""Mutation probe for test_reap.py -- the both-states check on the SUITE.

A green suite is not evidence that the suite protects anything
(rules/common/single-signal-verification.md:44). This script reverts five
load-bearing decisions in reap.py one at a time and requires the suite to go RED
for each. A mutation that SURVIVES is a hole in the tests and fails this gate.

Stdlib-only, own ``__main__``: run it directly, there is no repo-wide pytest
autodiscovery here.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (label, needle, replacement) -- each replacement is the pre-fix behaviour that
# the corresponding test was written to forbid.
MUTATIONS: list[tuple[str, str, str]] = [
    (
        "age-gate becomes OR (one signal can authorise a delete)",
        "return (now_ms - name_ms) >= min_age_ms and (now_ms - mtime_ms) >= min_age_ms",
        "return (now_ms - name_ms) >= min_age_ms or (now_ms - mtime_ms) >= min_age_ms",
    ),
    (
        # NOTE: the leading ``^`` is deliberately NOT mutated here -- STAGING_RE is
        # applied with ``re.match``, which anchors at position 0 anyway, so removing
        # ``^`` changes nothing and a "surviving" mutation there would be a broken
        # probe rather than a test hole. The trailing ``$`` is the load-bearing one:
        # without it ``temp_git_..._aaaaaa.clone.bak`` would be reaped.
        "staging regex loses its end anchor",
        r'(?P<clone>\.clone)?$"',
        r'(?P<clone>\.clone)?"',
    ),
    (
        "candidate scan stops checking that the entry is a directory",
        "        if not entry.is_dir(follow_symlinks=False):\n            continue",
        "        if False:  # noqa: SIM108\n            continue",
    ),
    (
        "root validation becomes a no-op (any path is deletable)",
        '        raise ValueError(f"refusing to scan {root}: not a .../plugins/cache path")',
        "        pass  # noqa: PIE790",
    ),
    (
        "dry-run deletes anyway",
        "    if apply:\n        for candidate in candidates:",
        "    if True:\n        for candidate in candidates:",
    ),
]


def run_suite(workdir: Path) -> bool:
    """Return True if the suite passes in ``workdir``."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test_reap.py",
            "-q",
            "-x",
            "-p",
            "no:cacheprovider",
        ],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    source = (HERE / "reap.py").read_text(encoding="utf-8")
    suite = (HERE / "test_reap.py").read_text(encoding="utf-8")
    killed = 0
    with tempfile.TemporaryDirectory() as raw:
        workdir = Path(raw)
        (workdir / "test_reap.py").write_text(suite, encoding="utf-8")
        (workdir / "reap.py").write_text(source, encoding="utf-8")
        if not run_suite(workdir):
            print("FAILED:reap-mutations baseline suite is RED before any mutation")
            return 1
        for label, needle, replacement in MUTATIONS:
            if needle not in source:
                print(f"FAILED:reap-mutations anchor not found -- {label}")
                return 1
            (workdir / "reap.py").write_text(
                source.replace(needle, replacement, 1), encoding="utf-8"
            )
            if run_suite(workdir):
                print(f"FAILED:reap-mutations SURVIVED -- {label}")
                return 1
            killed += 1
            print(f"killed: {label}")
        (workdir / "reap.py").write_text(source, encoding="utf-8")
    print(f"SUCCESS:reap-mutations {killed}/{len(MUTATIONS)} mutations killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
