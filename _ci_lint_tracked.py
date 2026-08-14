"""`ruff check` scoped to TRACKED files -- the surface CI actually lints.

WHY NOT JUST `ruff check .`. Ruff respects .gitignore, so ignored files are already skipped,
but this working tree carries 300+ untracked-and-NOT-ignored lane-scratch probes (`_h*.py`,
`_zz*.py`) that a fresh CI checkout never contains. Measured 2026-08-14: `ruff check .`
reported 4 fixable violations and every one lived in untracked scratch -- zero on the tracked
surface. Reporting that as "CI would be red" is a scope error, not a finding.

Format is NOT checked here: `command-center/hook-audit/_b9_format_tracked.py` already does it
against the stored blobs (the correct bytes under core.autocrlf=true), and a second
implementation would be a competing source of truth.

CONTROLS, printed every run and failing closed. A zero on either side means the instrument
broke rather than the repo being clean, which is the failure mode that makes a green
meaningless: an empty file list lints clean forever.

Terminal: SUCCESS:lint-tracked / FAILED:lint-tracked <n>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent


def main() -> int:
    tracked = [
        p for p in subprocess.check_output(
            ["git", "ls-files", "*.py"], cwd=REPO, text=True
        ).splitlines() if p.strip()
    ]
    print(f"CONTROL tracked *.py files = {len(tracked)}")
    if not tracked:
        print("FAILED:lint-tracked control is zero -- git ls-files returned nothing")
        return 2

    # ruff takes the paths on argv; chunk so a long list cannot hit the Windows
    # 32,767-char command-line cap (the documented `os error 206` shape).
    violations: list[str] = []
    CHUNK = 400
    for i in range(0, len(tracked), CHUNK):
        batch = tracked[i:i + CHUNK]
        p = subprocess.run(
            # --force-exclude IS LOAD-BEARING. Ruff applies `extend-exclude` during file
            # DISCOVERY, so a path named explicitly on argv is linted even when the config
            # excludes it. Without this flag the first run of this tool reported 90
            # violations on the tracked surface while `ruff check .` reported 0 -- a
            # self-contradiction, and the tool was the one that was wrong. The 90 were
            # deliberate control fixtures under p2-wave/probes/*/control/ (one is a
            # 700-char undefined name) that ruff.toml:22 excludes on purpose.
            ["ruff", "check", "--force-exclude", "--output-format=concise", *batch],
            cwd=REPO, capture_output=True, text=True,
        )
        violations += [
            ln for ln in p.stdout.splitlines()
            if ln[:1] not in ("", "[") and ":" in ln and not ln.startswith(("Found", "warning", "All checks"))
        ]

    # Both-states control: a file with a guaranteed violation MUST be reported. A linter
    # that is silent on known-bad input is not measuring the good state either.
    probe = REPO / "_zz_lint_control.py"
    probe.write_text("import os\n", encoding="utf-8")  # F401 unused-import
    try:
        c = subprocess.run(
            ["ruff", "check", "--output-format=concise", "--select", "F401", str(probe)],
            cwd=REPO, capture_output=True, text=True,
        )
        fires = "F401" in c.stdout
    finally:
        probe.unlink(missing_ok=True)
    print(f"CONTROL linter fires on known-bad input = {fires}")
    if not fires:
        print("FAILED:lint-tracked linter did not flag a known violation -- verdict withheld")
        return 2

    print(f"\n== tracked files with lint violations: {len(violations)}")
    for v in violations[:40]:
        print(f"   {v}")

    print("SUCCESS:lint-tracked 0 violations on the tracked surface" if not violations
          else f"FAILED:lint-tracked {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
