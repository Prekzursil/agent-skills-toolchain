r"""CI-PARITY: run the pinned linters over the STORED BLOBS, not the working tree.

WHY THE WORKING TREE IS THE WRONG BYTES. This repo has core.autocrlf=true, so a tracked file
can sit CRLF on disk while its blob is LF, and CI checks out the LF form. ruff has been
measured making DIFFERENT decisions on the two: "1 file already formatted" locally against
"Would reformat" in CI, for the same commit. A local green measured against the wrong bytes
verifies nothing.

TWO THINGS THIS GETS RIGHT that a naive blob check gets wrong:

  * `git cat-file -p`, never `git archive`. Measured on this estate: `git archive` applies
    export-time EOL conversion and hands back CRLF on Windows -- 3,837 bytes with 100 CRLF
    against 3,737 with zero from cat-file, for one file. A rule that tells you to verify
    against the wrong bytes manufactures confidence in exactly the check meant to catch this.
  * The CONFIG travels with the blobs. A bare temp dir has no ruff.toml, so ruff falls back to
    its default line-length 88 while this repo sets its own -- producing a FALSE red on clean
    files. ruff.toml is extracted to the mirror root and the relative paths are preserved so
    its excludes still resolve.

CONTROL (runs first; the result is not printed unless it fires): a deliberately mangled copy
of one file must make `format --check` complain. A formatter that is silent on mangled input
is not measuring the good state either.

usage: python command-center/casualty/verify_ci_parity.py [path ...]   (default: this lane)
Terminal: SUCCESS:ci-parity / FAILED:ci-parity <reason>
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(os.environ.get("CASUALTY_REPO") or Path(__file__).resolve().parents[2])
RUFF = ["uvx", "ruff@0.15.17"]
CONFIG_FILES = ("ruff.toml", "pyproject.toml", ".gitattributes")

DEFAULT_TARGETS = (
    "command-center/casualty/casualty_guard.py",
    "command-center/casualty/integration_redproof.py",
    "command-center/casualty/verify_ci_parity.py",
    "command-center/casualty/tests/conftest.py",
    "command-center/casualty/tests/test_casualty_guard.py",
    "command-center/casualty/census_v2.py",
    "command-center/casualty/liveness_v2.py",
    "command-center/casualty/recover_failed_agents_v2.py",
    "command-center/casualty/verify_blob_parity.py",
    "tools/measure-guard/suitefloor.py",
)


def _run(argv: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True, check=False
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _materialise(targets: list[str], dest: Path) -> tuple[list[str], int]:
    """Write each tracked path's COMMITTED blob into dest, preserving the relative path."""
    written: list[str] = []
    crlf = 0
    for rel in targets:
        proc = subprocess.run(
            ["git", "cat-file", "-p", f"HEAD:{rel}"],
            cwd=str(REPO),
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(proc.stdout)
        crlf += proc.stdout.count(b"\r\n")
        written.append(rel)
    for name in CONFIG_FILES:
        src = REPO / name
        if src.is_file():
            shutil.copy2(src, dest / name)
    return written, crlf


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets = argv or list(DEFAULT_TARGETS)
    tmp = Path(tempfile.mkdtemp(prefix="casualty_ci_parity_"))
    try:
        mirror = tmp / "blobs"
        mirror.mkdir()
        written, crlf = _materialise(targets, mirror)
        if not written:
            print(
                "FAILED:ci-parity materialised ZERO blobs -- an empty walk is a path bug, "
                "not a pass (are these paths tracked at HEAD?)"
            )
            return 1

        # CONTROL FIRST. Mangle a copy and require the formatter to complain about it; if it
        # does not, the tool is not running and its silence on the real files means nothing.
        ctrl = tmp / "control"
        ctrl.mkdir()
        for name in CONFIG_FILES:
            if (REPO / name).is_file():
                shutil.copy2(REPO / name, ctrl / name)
        (ctrl / "mangled.py").write_text("x   =    1\ndef  f( a,b ):\n  return  a+b\n")
        crc, cout = _run([*RUFF, "format", "--check", "mangled.py"], ctrl)
        if crc == 0:
            print(
                "FAILED:ci-parity the CONTROL did not fire -- ruff reported mangled input as "
                f"formatted, so its verdict on the real blobs is meaningless. output: {cout}"
            )
            return 1

        rc_check, out_check = _run([*RUFF, "check", *written], mirror)
        rc_fmt, out_fmt = _run([*RUFF, "format", "--check", *written], mirror)

        print(f"  control  : ruff format --check on mangled input -> rc {crc} (FIRES)")
        print(
            f"  blobs    : {len(written)} materialised via `git cat-file -p`, CRLF bytes {crlf}"
        )
        print(f"  config   : {[n for n in CONFIG_FILES if (mirror / n).is_file()]}")
        print(
            f"  check    : rc {rc_check}  {out_check.splitlines()[-1] if out_check else ''}"
        )
        print(
            f"  format   : rc {rc_fmt}  {out_fmt.splitlines()[-1] if out_fmt else ''}"
        )

        if rc_check or rc_fmt:
            print(f"FAILED:ci-parity check_rc={rc_check} format_rc={rc_fmt}")
            print(out_check)
            print(out_fmt)
            return 1
        print(
            f"SUCCESS:ci-parity {len(written)} committed blob(s) clean under the pinned ruff"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
