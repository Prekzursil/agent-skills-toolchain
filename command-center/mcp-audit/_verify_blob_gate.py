"""Verify the COMMITTED BLOBS pass the pinned ruff gate, not the working tree.

windows-shell rule 8b: a local green measured on CRLF working-tree bytes can disagree
with CI, which checks out the stored blob. `git show <rev>:<path>` returns the blob
(git archive does NOT -- it re-applies EOL conversion on Windows).

The config must travel too: a bare temp dir has no ruff.toml, so ruff would fall back to
its own defaults and the verdict would answer a different question than CI's.

Includes a MANGLED both-states control: a deliberately mis-formatted copy of one blob
must be FLAGGED, otherwise a clean report proves only that ruff ran.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate")
REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
RUFF = ["uvx", "ruff@0.15.17"]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def blob(path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{REV}:{path}"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout


def ruff(sub: list[str], target: pathlib.Path, cwd: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run(
        [*RUFF, *sub, str(target)], cwd=cwd, capture_output=True, text=True
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    files = [
        p
        for p in git("show", "--name-only", "--format=", REV).split("\n")
        if p.strip().endswith(".py")
    ]
    if not files:
        print("FAILED:blob-gate no .py files in the commit (fail closed)")
        return 1

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="blobgate-"))
    try:
        # Config from HEAD -- that is what CI reads.
        (tmp / "ruff.toml").write_bytes(
            subprocess.run(
                ["git", "show", "HEAD:ruff.toml"],
                cwd=REPO,
                capture_output=True,
                check=True,
            ).stdout
        )
        crlf = 0
        for rel in files:
            data = blob(rel)
            crlf += data.count(b"\r\n")
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        target = tmp / "command-center" / "mcp-audit"
        print(f"extracted {len(files)} blobs from {REV}; CRLF bytes in blobs: {crlf}")

        rc_check, out_check = ruff(["check"], target, tmp)
        rc_fmt, out_fmt = ruff(["format", "--check"], target, tmp)
        print(f"blob ruff check        rc={rc_check}  {out_check.splitlines()[-1:]}")
        print(f"blob ruff format-check rc={rc_fmt}  {out_fmt.splitlines()[-1:]}")

        # ---- MANGLED CONTROL: the gate must FIRE on deliberately bad formatting.
        ctl = tmp / "control"
        ctl.mkdir()
        # The mangle must not depend on the file's CONTENT.  Two earlier versions did and
        # both misreported: a hardcoded filename crashed on a commit that lacked it, and a
        # search-and-replace on `import argparse` silently no-op'd on a file without it, so
        # the control read as "did not fire" when nothing had been mangled at all.
        # APPENDING is content-independent, always syntactically valid (unlike prepending,
        # which breaks `from __future__` and makes ruff exit 2 = error, not 1 = would-
        # reformat), and always mis-formatted because of the doubled spaces.
        candidates = sorted(target.glob("*.py"))
        if not candidates:
            print("FAILED:blob-gate no extracted .py to mangle (fail closed)")
            return 1
        src = candidates[0]
        (ctl / "mangled.py").write_bytes(src.read_bytes() + b"\n\nx  =  1\n")
        shutil.copy(tmp / "ruff.toml", ctl / "ruff.toml")
        rc_ctl, out_ctl = ruff(["format", "--check"], ctl / "mangled.py", ctl)
        # rc must be exactly 1 (would reformat). rc=2 means ruff ERRORED, which would also
        # be "non-zero" and would let a broken control masquerade as a firing one.
        fired = rc_ctl == 1
        print(f"MANGLED control fires: {fired} (rc={rc_ctl}, want 1) -- must be True")
        if not fired:
            print(f"  control output: {out_ctl.splitlines()[-2:]}")

        ok = rc_check == 0 and rc_fmt == 0 and fired and crlf == 0
        print(
            "SUCCESS:blob-gate blobs pass both ruff gates, control fired, 0 CRLF"
            if ok
            else f"FAILED:blob-gate check={rc_check} fmt={rc_fmt} control_fired={fired} crlf={crlf}"
        )
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
