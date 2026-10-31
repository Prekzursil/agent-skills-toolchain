#!/usr/bin/env python3
r"""_r3_blobgate.py -- lint the bytes this commit will SHIP, not the CRLF working tree.

Round 2's blob gate defaulted to `HEAD~1 HEAD` and, with nine lanes committing to this
branch, drifted onto a sibling's commit: it staged ONE .py blob, found it clean, saw its
mangled control correctly flagged, and printed SUCCESS. The control was sound and proved
the wrong thing.

This one reads the INDEX (`git show :<path>`) for an explicit list of paths -- the same
bytes `git commit` is about to write -- so there is no revision to get wrong, and it fails
closed below a minimum count. It also plants a deliberately mangled control file and
requires ruff to flag exactly that file, so a silent pass cannot be mistaken for a clean
one.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUFF = "ruff@0.15.17"
MIN_PY = 5

MANGLED = "import os,sys\ndef  f( a ):\n  return    os.path.join(a,sys.argv[0])\n"


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )


def main() -> int:
    paths = [p.strip() for p in sys.argv[1:] if p.strip()]
    if not paths:
        print("FAILED:r3-blobgate no paths given -- refusing to lint nothing")
        return 1
    stage = Path(tempfile.mkdtemp(prefix="r3-blobgate-"))
    try:
        n_py = crlf = 0
        for rel in paths:
            p = sh("git", "show", f":{rel}", cwd=REPO)
            if p.returncode != 0:
                print(
                    f"FAILED:r3-blobgate {rel} is not in the index: {p.stderr.strip()[:120]}"
                )
                return 1
            raw = p.stdout
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            # newline="" so nothing re-inserts CRLF on the way back out to disk
            with dst.open("w", encoding="utf-8", newline="") as fh:
                fh.write(raw)
            if rel.endswith(".py"):
                n_py += 1
                crlf += dst.read_bytes().count(b"\r\n")
        for cfg in ("ruff.toml", "pyproject.toml", ".ruff.toml"):
            src = REPO / cfg
            if src.is_file():
                shutil.copy2(src, stage / cfg)
        if n_py < MIN_PY:
            print(
                f"FAILED:r3-blobgate only {n_py} .py blobs staged, expected >= {MIN_PY}"
            )
            return 1

        control = stage / "command-center" / "hook-audit" / "_zz_control_mangled.py"
        control.parent.mkdir(parents=True, exist_ok=True)
        control.write_text(MANGLED, encoding="utf-8", newline="")

        chk = sh("uvx", RUFF, "check", ".", cwd=stage)
        fmt = sh("uvx", RUFF, "format", "--check", ".", cwd=stage)
        out = chk.stdout + chk.stderr + fmt.stdout + fmt.stderr
        control_flagged = "_zz_control_mangled" in out
        real = [
            ln
            for ln in out.splitlines()
            if ("_zz_control_mangled" not in ln)
            and (
                "Would reformat" in ln or "-->" in ln or ln.strip().startswith("error")
            )
        ]
        print(
            f"py blobs {n_py} | CRLF bytes in blobs {crlf} | control flagged {control_flagged}"
        )
        for ln in real[:20]:
            print("  !!", ln)
        if crlf:
            print("FAILED:r3-blobgate the index holds CRLF -- CI checks out LF")
            return 1
        if not control_flagged:
            print(
                "FAILED:r3-blobgate the mangled control was NOT flagged -- ruff did not run"
            )
            return 1
        if real:
            print(
                f"FAILED:r3-blobgate {len(real)} real finding(s) on the shipped blobs"
            )
            return 1
        print("SUCCESS:r3-blobgate")
        return 0
    finally:
        shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
