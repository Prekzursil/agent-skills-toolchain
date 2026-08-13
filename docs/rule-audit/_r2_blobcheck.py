"""Check the STAGED blobs the way CI sees them, not the CRLF working tree.

windows-shell.md 8b: a Windows working tree is CRLF, git stores LF, CI checks out LF, and ruff
can decide differently on the two forms -- so a local green measured against the wrong bytes
verifies nothing. `git cat-file -p :<path>` returns the stored blob (0 CRLF, measured); the
config must travel too, or a bare temp dir defaults to line-length 88 against this repo's
ruff.toml and manufactures a false CI-red.

CONTROL: one extracted file is deliberately mangled and re-checked; if ruff does not go red on
the mangled copy, the checker is inert and its green means nothing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUFF = ["uvx", "ruff@0.15.17"]


def staged_python() -> list[str]:
    out = subprocess.run(
        [
            "git",
            "-C",
            str(REPO),
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACM",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [p for p in out.split("\n") if p.strip().endswith(".py")]


def main() -> int:
    paths = staged_python()
    if not paths:
        print(
            "FAILED:r2_blobcheck no staged .py files -- nothing measured, fail closed"
        )
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copy2(REPO / "ruff.toml", root / "ruff.toml")
        crlf = 0
        for rel in paths:
            blob = subprocess.run(
                ["git", "-C", str(REPO), "cat-file", "-p", f":{rel}"],
                capture_output=True,
                check=True,
            ).stdout
            crlf += blob.count(b"\r\n")
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)

        print(f"staged .py blobs extracted: {len(paths)}   CRLF pairs in blobs: {crlf}")
        checks = {
            "ruff check": subprocess.run(
                [*RUFF, "check", "."], cwd=root, capture_output=True, text=True
            ),
            "ruff format --check": subprocess.run(
                [*RUFF, "format", "--check", "."],
                cwd=root,
                capture_output=True,
                text=True,
            ),
        }
        for name, proc in checks.items():
            print(
                f"  {name}: rc={proc.returncode}  {proc.stdout.strip().splitlines()[-1:]}"
            )

        # CONTROL: mangle one file; the format gate MUST go red or this checker is inert.
        victim = root / paths[0]
        victim.write_text(
            victim.read_text(encoding="utf-8") + "\n\n\n\nx    =    1\n",
            encoding="utf-8",
        )
        control = subprocess.run(
            [*RUFF, "format", "--check", "."], cwd=root, capture_output=True, text=True
        )
        print(
            f"  CONTROL (mangled {paths[0]}): rc={control.returncode} (must be non-zero)"
        )

    ok = (
        all(p.returncode == 0 for p in checks.values())
        and control.returncode != 0
        and crlf == 0
    )
    print("")
    if ok:
        print(
            f"SUCCESS:r2_blobcheck {len(paths)} staged blob(s) clean at LF, control fires"
        )
        return 0
    print("FAILED:r2_blobcheck staged blobs would not pass CI, or the control is inert")
    return 1


if __name__ == "__main__":
    sys.exit(main())
