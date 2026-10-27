#!/usr/bin/env python3
"""_r4_blobgate.py -- run CI's ruff gate against the bytes this commit will SHIP.

A Windows working tree is CRLF; git stores LF; CI checks out LF. A local green measured on
the worktree is measured on the wrong bytes (windows-shell 8b). `git show :<path>` and
`git cat-file -p` both emit the stored blob; `git archive` re-applies EOL conversion on
Windows and hands back CRLF, so it is not used.

The committed `ruff.toml` is staged into the temp root as well, and each file is placed at
its REAL relative path -- without both, ruff falls back to its own defaults (line-length 88
against the project's setting) and manufactures a false red on clean files.

BOTH-STATES CONTROLS. A green run only counts if the same invocation can go red, so before
reporting, this adds (a) a badly formatted file and requires `format --check` to flag it and
(b) a file with an unused import and requires `check` to flag it, then removes both and
re-runs. If either control stays green the gate is not measuring anything and no verdict is
published.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUFF = ["uvx", "ruff@0.15.17"]

PATHS = [
    "ruff.toml",
    "command-center/hook-audit/check_citations.py",
    "command-center/hook-audit/test_citation_gate.py",
    "command-center/hook-audit/_r4_wire_exit.py",
    "command-center/hook-audit/_r4_budget_ceiling.py",
    "command-center/hook-audit/_r4_githygiene_range.py",
    "command-center/hook-audit/_r4_table_scan.py",
    "command-center/hook-audit/_r4_blobgate.py",
]

MANGLED = "def  f( a ,b ):\n\n\n    return (   a+b )\n"
UNUSED = "import os\n\n\ndef g() -> int:\n    return 1\n"


def blob(rel: str) -> bytes | None:
    p = subprocess.run(
        ["git", "show", f":{rel}"], cwd=str(REPO), capture_output=True, timeout=60
    )
    return p.stdout if p.returncode == 0 else None


def ruff(root: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(
        [*RUFF, *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    out: dict = {"probe": "_r4_blobgate.py", "files": {}}
    tmp = Path(tempfile.mkdtemp(prefix="r4blob_"))
    try:
        crlf_total = 0
        for rel in PATHS:
            data = blob(rel)
            if data is None:
                print(f"FAILED:r4-blobgate {rel} is not in the index -- stage it first")
                return 1
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            n_crlf = data.count(b"\r\n")
            crlf_total += n_crlf
            out["files"][rel] = {"bytes": len(data), "crlf": n_crlf}
        out["crlf_in_blobs"] = crlf_total

        # --- controls: prove this invocation can go red, in both gates.
        (tmp / "_ctl_mangled.py").write_text(MANGLED, encoding="utf-8")
        rc_fmt_hot, o_fmt_hot = ruff(tmp, "format", "--check", ".")
        (tmp / "_ctl_mangled.py").unlink()
        (tmp / "_ctl_unused.py").write_text(UNUSED, encoding="utf-8")
        rc_chk_hot, o_chk_hot = ruff(tmp, "check", ".")
        (tmp / "_ctl_unused.py").unlink()
        out["control_format_goes_red"] = rc_fmt_hot != 0 and "_ctl_mangled" in o_fmt_hot
        out["control_check_goes_red"] = rc_chk_hot != 0 and "_ctl_unused" in o_chk_hot
        if not (out["control_format_goes_red"] and out["control_check_goes_red"]):
            out["verdict"] = "DETECTOR-UNPROVEN"
            print(json.dumps(out, indent=1))
            print(
                "FAILED:r4-blobgate a control stayed green; no lint verdict published"
            )
            return 1

        # --- the real arms, on the blobs alone.
        rc_chk, o_chk = ruff(tmp, "check", ".")
        rc_fmt, o_fmt = ruff(tmp, "format", "--check", ".")
        out["ruff_check_rc"] = rc_chk
        out["ruff_check_tail"] = (
            o_chk.strip().splitlines()[-1][:200] if o_chk.strip() else ""
        )
        out["ruff_format_rc"] = rc_fmt
        out["ruff_format_tail"] = (
            o_fmt.strip().splitlines()[-1][:200] if o_fmt.strip() else ""
        )
        out["verdict"] = "GREEN" if rc_chk == 0 and rc_fmt == 0 else "RED"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    (HERE / "R4-BLOBGATE.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    if out["verdict"] != "GREEN":
        print("FAILED:r4-blobgate ruff is RED on the committed blobs")
        return 1
    print("SUCCESS:r4-blobgate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
