"""CI-equivalent ruff gate against the COMMITTED BLOBS, not the CRLF working tree.

windows-shell.md 8b: a local green on the working tree can disagree with CI, because git
stores LF and Windows checks out CRLF, and ruff makes different decisions on the two forms.
`git cat-file -p` returns the stored blob (0 CRLF, measured); `git archive` does NOT -- it
applies EOL conversion and hands back CRLF on Windows, which is the opposite of what is
wanted here.

Also stages the repo's ruff.toml at the temp root and MIRRORS each file's relative path, so
line-length and per-path settings resolve exactly as they do in CI. A bare temp dir would
fall back to ruff's default line-length 88 against this project's 120 and manufacture a
false red on clean files.

CONTROL: a deliberately mangled copy is added to the tree and the format check must FLAG IT.
If the control is not flagged, the checker is not looking at these files and its silence is
worthless -- the run fails closed rather than reporting a pass.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
RUFF = ["uvx", "ruff@0.15.17"]
CONTROL = "_zz_blobgate_control_mangled.py"
# Coverage floor: this lane committed 9 .py files across its two commits. A run that sees
# fewer is reading the wrong revisions and must fail rather than report a clean pass.
MIN_PY = 9
MANGLED = "def  f( a,b ):\n\n\n     return   a+b\nx=[1,\n 2 ,3]\n"


def blob(rev: str, path: str) -> bytes | None:
    p = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{rev}:{path}"],
        capture_output=True,
        timeout=60,
    )
    return p.stdout if p.returncode == 0 else None


def main() -> int:
    # PIN the revisions. Relative refs are wrong here: nine lanes commit to this same
    # branch, so HEAD~1 drifted onto a sibling lane's commit between writing this probe and
    # running it -- it enumerated 1 .py file instead of 9 and still reported SUCCESS,
    # because the mangled control proves the checker READS files, not that it read the
    # RIGHT ones. MIN_PY below is the coverage assertion that turns that into a red.
    revs = sys.argv[1:] or ["63ff313d", "03365d08"]
    paths: set[str] = set()
    for rev in revs:
        out = subprocess.run(
            ["git", "-C", str(REPO), "show", "--name-only", "--format=", rev],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout
        paths.update(p.strip() for p in out.splitlines() if p.strip().endswith(".py"))
    print(f"revs={revs}  .py paths enumerated={len(paths)}")
    if len(paths) < MIN_PY:
        print(
            f"FAILED:r2-blobgate only {len(paths)} .py paths from {revs}, expected at"
        )
        print(
            f"       least {MIN_PY} -- the wrong commits were read, so any pass below"
        )
        print("       would be measuring something other than this lane's work")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="r2blob_"))
    try:
        cfg = blob("HEAD", "ruff.toml")
        if cfg is None:
            print("FAILED:r2-blobgate no ruff.toml at HEAD -- CI config not reproduced")
            return 1
        (tmp / "ruff.toml").write_bytes(cfg)

        crlf = 0
        for rel in sorted(paths):
            data = blob("HEAD", rel)
            if data is None:
                continue
            crlf += data.count(b"\r\n")
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        (tmp / CONTROL).write_text(MANGLED, encoding="utf-8")

        chk = subprocess.run(
            [*RUFF, "check", "."],
            cwd=str(tmp),
            capture_output=True,
            text=True,
            timeout=900,
        )
        fmt = subprocess.run(
            [*RUFF, "format", "--check", "."],
            cwd=str(tmp),
            capture_output=True,
            text=True,
            timeout=900,
        )
        print(f"staged {len(paths)} .py blobs; CRLF bytes in blobs: {crlf} (must be 0)")
        print("--- ruff check ---")
        print((chk.stdout + chk.stderr).strip()[-1500:])
        print("--- ruff format --check ---")
        print((fmt.stdout + fmt.stderr).strip()[-1500:])

        control_seen = CONTROL in (fmt.stdout + fmt.stderr)
        if not control_seen:
            print(
                "FAILED:r2-blobgate the mangled CONTROL was not flagged -- the checker"
            )
            print(
                "       is not reading these files, so a pass here would mean nothing"
            )
            return 1
        if crlf:
            print("FAILED:r2-blobgate blobs carry CRLF -- wrong extraction route")
            return 1
        # The control is the only file allowed to be unformatted.
        bad_fmt = [
            ln
            for ln in (fmt.stdout + fmt.stderr).splitlines()
            if ln.startswith("Would reformat:") and CONTROL not in ln
        ]
        if chk.returncode != 0 or bad_fmt:
            for ln in bad_fmt:
                print(f"   {ln}")
            print("FAILED:r2-blobgate committed blobs are not CI-clean")
            return 1
        print("control flagged, every real blob clean")
        print("SUCCESS:r2-blobgate")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
