r"""windows-shell 8b: format-check the COMMITTED BLOBS, not the working tree.

A working-tree file here is whatever the author wrote; git stores a normalized blob; CI checks
out the blob. A local `ruff format --check` therefore measures the wrong bytes. This extracts the
committed blob of every file this lane touched, MIRRORS THE RELATIVE PATH and copies the ruff
config next to it (a bare temp dir has no pyproject.toml, so ruff would fall back to line-length
88 against this project's setting and manufacture a false red), and runs the pinned ruff there.

DETECTOR CONTROL, both states: one extracted file is deliberately mangled and the same command
must go RED on it. A format check that has only ever been seen passing proves nothing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUFF = ["uvx", "ruff@0.15.17"]
FILES = [
    "command-center/p2-next/rail_count_gate.py",
    "command-center/p2-next/vendor_satisfiability.py",
    "command-center/p2-next/_i1_eol_probe.py",
    "command-center/p2-next/_i2_numbers.py",
    "command-center/p2-next/_i3_redproof.py",
]
CONFIG = ["pyproject.toml", "ruff.toml", ".ruff.toml"]


def blob(rev: str, rel: str) -> bytes | None:
    p = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"], cwd=REPO, capture_output=True
    )
    return p.stdout if p.returncode == 0 else None


def ruff(args: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(
        RUFF + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    return p.returncode, (p.stdout + p.stderr).strip()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="p2next-blobcheck-"))
    try:
        cfgs = [c for c in CONFIG if (REPO / c).is_file()]
        for c in cfgs:
            shutil.copyfile(REPO / c, tmp / c)
        print(
            f"  ruff config carried into the temp tree: {cfgs or 'NONE (would be a false red)'}"
        )
        if not cfgs:
            print(
                "FAILED:blobcheck no ruff config found; the comparison would be meaningless"
            )
            return 1

        crlf_total = 0
        for rel in FILES:
            data = blob("HEAD", rel)
            if data is None:
                print(f"FAILED:blobcheck {rel} not committed at HEAD")
                return 1
            crlf_total += data.count(b"\r\n")
            dst = tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        print(
            f"  {len(FILES)} blobs extracted; CRLF bytes across all of them: {crlf_total}"
        )

        rc_fmt, out_fmt = ruff(["format", "--check", "."], tmp)
        rc_chk, out_chk = ruff(["check", "."], tmp)
        print(
            f"  blob format --check rc={rc_fmt}: {out_fmt.splitlines()[-1] if out_fmt else ''}"
        )
        print(
            f"  blob check        rc={rc_chk}: {out_chk.splitlines()[-1] if out_chk else ''}"
        )

        # both-states control
        victim = tmp / FILES[0]
        victim.write_bytes(b"x   =    1\ndef  f( a ,b ):\n  return  a+b\n")
        rc_bad, _ = ruff(["format", "--check", "."], tmp)
        print(
            f"  CONTROL mangled blob -> format --check rc={rc_bad} (must be non-zero)"
        )

        ok = rc_fmt == 0 and rc_chk == 0 and rc_bad != 0 and crlf_total == 0
        print(
            "SUCCESS:blobcheck the committed bytes are ruff-clean and the detector fires"
            if ok
            else f"FAILED:blobcheck fmt={rc_fmt} check={rc_chk} control={rc_bad} crlf={crlf_total}"
        )
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
