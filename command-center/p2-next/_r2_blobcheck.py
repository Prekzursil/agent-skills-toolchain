"""ROUND-2: lint the COMMITTED BLOBS at a REV, not the worktree and not the index.

PRIOR ART, NOT DUPLICATED BLINDLY: `docs/rule-audit/_r2_blobcheck.py` (a sibling lane) already does
this for the *staged* index -- `git cat-file -p :<path>` over `git diff --cached`. It is the better
tool at a pre-commit boundary and I did not edit it (other lane's file). It cannot serve here for
one mechanical reason: this lane's round-2 work is already COMMITTED, so `--cached` is empty and
that script correctly fails closed with "no staged .py files". This variant differs in exactly one
respect -- it reads `HEAD:<path>` for an explicit file list. Same rule, same control shape.

windows-shell rule 8b: a Windows worktree file is CRLF, git stores LF, CI checks out LF, and ruff
can format the two differently -- so a local green measured against the wrong bytes verifies
nothing. `git cat-file -p` returns the stored blob (LF); `git archive` is the one that re-inserts
CRLF on Windows. MIRROR THE RELATIVE PATH and carry the ruff config -- without it ruff defaults to
line-length 88 instead of this repo's setting and manufactures a false CI-red on clean files.

CONTROL: a deliberately mangled copy of one blob must be REPORTED by the same invocation. A
formatter check that cannot go red is not a check.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FILES = [
    "command-center/p2-next/vendor_satisfiability.py",
    "command-center/p2-next/split_review_gate.py",
    "command-center/p2-next/_b20_final_verify.py",
    "command-center/p2-next/_r2_bld0023.py",
    "command-center/p2-next/_r2_control_b20.py",
    "command-center/p2-next/_r2_control_stability.py",
    "command-center/p2-next/_r2_probe_ruled.py",
    "command-center/p2-next/_r2_probe_splitgate.py",
    "command-center/p2-next/_r2_reconcile.py",
    "command-center/p2-next/_r2_tagcensus.py",
]
RUFF = ["uvx", "ruff@0.15.17"]


def cat(rev: str, rel: str) -> bytes:
    r = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"], cwd=REPO, capture_output=True
    )
    if r.returncode != 0:
        raise SystemExit(f"FAILED:blobcheck cannot read {rev}:{rel}")
    return r.stdout


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    for cfg in ("pyproject.toml", "ruff.toml", ".ruff.toml"):
        if (REPO / cfg).is_file():
            shutil.copy2(REPO / cfg, root / cfg)
            print(f"  carried config: {cfg}")
    crlf = 0
    for rel in FILES:
        data = cat("HEAD", rel)
        crlf += data.count(b"\r\n")
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
    print(f"  extracted {len(FILES)} blobs; CRLF sequences across all of them: {crlf}")

    fmt = subprocess.run(
        [*RUFF, "format", "--check", "."], cwd=root, capture_output=True, text=True
    )
    chk = subprocess.run(
        [*RUFF, "check", "."], cwd=root, capture_output=True, text=True
    )
    print(
        f"  BLOB ruff format --check rc={fmt.returncode} :: {fmt.stdout.strip().splitlines()[-1:]}"
    )
    print(
        f"  BLOB ruff check        rc={chk.returncode} :: {chk.stdout.strip().splitlines()[-1:]}"
    )

    # ---- CONTROL: mangle one extracted blob; the same command must now go red ----
    victim = root / FILES[0]
    src = victim.read_text(encoding="utf-8")
    victim.write_text(
        src.replace("import argparse", "import   argparse", 1), encoding="utf-8"
    )
    ctl = subprocess.run(
        [*RUFF, "format", "--check", "."], cwd=root, capture_output=True, text=True
    )
    fired = ctl.returncode != 0 and "vendor_satisfiability" in ctl.stdout
    print(f"  CONTROL mangled blob -> rc={ctl.returncode} fires={fired}")

ok = fmt.returncode == 0 and chk.returncode == 0 and fired and crlf == 0
print("SUCCESS:r2-blobcheck" if ok else "FAILED:r2-blobcheck")
sys.exit(0 if ok else 1)
