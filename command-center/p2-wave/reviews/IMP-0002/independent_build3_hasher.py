#!/usr/bin/env python3
"""Independent Build-3 hasher for IMP-0002 adversarial review.

Reimplements the spirit of probe2 (other cwd + TMPDIR + clock offset) without
reading probe measurement/raw outputs. Hashes the zip with this script only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from shutil import which


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True, help="clean second checkout")
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--out-dir", type=Path, required=True, help="review artifact dir")
    ap.add_argument("--clock-offset-seconds", type=int, default=7200)
    args = ap.parse_args()

    repo = args.repo.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    pack_py = repo / "tools" / "plugin" / "pack.py"
    allowlist = repo / "tools" / "plugin" / "payload-allowlist.json"

    lines = [
        "INDEPENDENT BUILD 3: OTHER CWD + TMPDIR + CLOCK OFFSET",
        "REVIEWER-BUILD3-BEGIN:IMP-0002",
        f"repo={repo}",
        f"rev={args.rev}",
        "prefix=tools/plugin",
        "use_real_mtimes=false",
        f"clock_offset_seconds={args.clock_offset_seconds}",
        "hasher=independent_build3_hasher.py",
    ]

    with tempfile.TemporaryDirectory(prefix="imp0002-review-b3-") as td:
        td_path = Path(td)
        zip_path = td_path / "build3.zip"
        env = os.environ.copy()
        tmp = td_path / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        env["TMPDIR"] = str(tmp)
        env["TEMP"] = str(tmp)
        env["TMP"] = str(tmp)
        lines.append(f"tmpdir={env['TMPDIR']}")
        lines.append(f"cwd={td_path}")

        cmd = [
            sys.executable,
            "-B",
            str(pack_py),
            "--repo",
            str(repo),
            "--rev",
            args.rev,
            "--allowlist",
            str(allowlist),
            "--prefix",
            "tools/plugin",
            "--out",
            str(zip_path),
            "--json",
        ]
        faketime = which("faketime")
        if faketime:
            cmd = [faketime, f"+{args.clock_offset_seconds}s", *cmd]
            lines.append(f"faketime={faketime}")
        else:
            time.sleep(1.05)
            lines.append("faketime=absent; slept_1s_plus")

        proc = subprocess.run(
            cmd,
            cwd=str(td_path),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines.append(f"pack_exit={proc.returncode}")
        lines.append(f"pack_stdout={proc.stdout.strip()}")
        lines.append(f"pack_stderr={proc.stderr.strip()}")
        if proc.returncode != 0 or not zip_path.is_file():
            raw = "\n".join(lines) + "\nFAILED:reviewer-build3\n"
            (out_dir / "build3.raw.txt").write_text(raw, encoding="utf-8")
            print(raw, end="")
            return 1

        # Hash ONLY in this script (independent of pack.py --json field trust).
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        dest = out_dir / "build3.zip"
        dest.write_bytes(zip_path.read_bytes())
        meas = {
            "build3_sha256": digest,
            "size_bytes": dest.stat().st_size,
            "tmpdir": env["TMPDIR"],
            "cwd": str(td_path),
            "clock_offset_seconds": args.clock_offset_seconds,
            "faketime": bool(faketime),
            "repo": str(repo),
            "rev_resolved": subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", args.rev],
                text=True,
            ).strip(),
        }
        (out_dir / "build3-measurement.json").write_text(
            json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        lines.extend(
            [
                f"build3_sha256={digest}",
                f"size_bytes={meas['size_bytes']}",
                "REVIEWER-BUILD3-COMPLETE:IMP-0002",
                "SUCCESS:reviewer-build3",
            ]
        )
        raw = "\n".join(lines) + "\n"
        (out_dir / "build3.raw.txt").write_text(raw, encoding="utf-8")
        print(raw, end="")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
