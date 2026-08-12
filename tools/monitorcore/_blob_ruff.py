"""Run the CI format/lint gate against the COMMITTED LF BLOBS, not the CRLF worktree.

windows-shell 8b, ledger-proven: `ruff format --check` can decide differently on the LF blob
than on the CRLF worktree, so a local green can be measured against bytes CI never checks out.
`_blob_parity.py` already established the blobs here are LF while 15 worktree files are CRLF, so
the worktree run does NOT transfer. This extracts the blobs and re-runs the gate on them.

Two traps this avoids, both previously measured:
  * a bare temp dir has no ruff.toml, so ruff falls back to line-length 88 against the project's
    real config and manufactures a FALSE red. The repo's ruff.toml is copied in first.
  * relative paths matter (ruff.toml carries extend-exclude globs), so each blob is written at
    its ORIGINAL repo-relative path inside the temp root.
And a MANGLED CONTROL proves the gate can still fail in that temp tree; without it a green is
indistinguishable from ruff having discovered no files at all.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUFF = ["uvx", "ruff@0.15.17"]


def blob(rev: str, path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{rev}:{path}"], capture_output=True
    )
    return proc.stdout if proc.returncode == 0 else None


def changed(rev: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(REPO), "show", "--pretty=", "--name-only", "-z", rev]
    )
    return [p for p in out.decode("utf-8", "replace").split("\0") if p.endswith(".py")]


def ruff(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [*RUFF, *args], cwd=cwd, capture_output=True, text=True, shell=False
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    paths = changed(rev)
    if not paths:
        print("FAILED:blob-ruff no .py files in the commit (fail closed)")
        return 1

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shutil.copy2(REPO / "ruff.toml", root / "ruff.toml")
        written = 0
        for path in paths:
            data = blob(rev, path)
            if data is None:
                print(f"FAILED:blob-ruff cannot read blob {path}")
                return 1
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            written += 1
        crlf = sum(1 for p in paths if b"\r\n" in (root / p).read_bytes())
        print(f"extracted {written} blob(s), CRLF among them: {crlf}")

        fmt_code, fmt_out = ruff(["format", "--check", "."], root)
        chk_code, chk_out = ruff(["check", "."], root)
        print(
            f"[blob] format --check exit={fmt_code}  {fmt_out.splitlines()[-1] if fmt_out else ''}"
        )
        print(
            f"[blob] check        exit={chk_code}  {chk_out.splitlines()[-1] if chk_out else ''}"
        )

        # Control: deliberately mis-format one extracted blob; the gate MUST go red.
        victim = root / paths[0]
        original = victim.read_bytes()
        victim.write_bytes(
            original.replace(b"from __future__", b"x   =   1\nfrom __future__", 1)
        )
        ctl_code, _ = ruff(["format", "--check", "."], root)
        victim.write_bytes(original)
        print(
            f"control (mis-formatted blob) format --check exit={ctl_code} (must be non-zero)"
        )

        if ctl_code == 0:
            print(
                "FAILED:blob-ruff the control did not fire -- the gate measures nothing"
            )
            return 1
        if fmt_code or chk_code:
            print("FAILED:blob-ruff the committed blobs do not pass the CI gate")
            return 1

    print(
        f"SUCCESS:blob-ruff {written} committed blob(s) pass ruff check + format --check"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
