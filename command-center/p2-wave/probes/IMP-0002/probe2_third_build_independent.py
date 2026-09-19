#!/usr/bin/env python3
"""IMP-0002 probe2 (SEPARATE SCRIPT): third build in other cwd + TMPDIR + clock offset.

Does not import probe1. Hashes independently and compares to probe1 measurement.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
PACK_PY = REPO / "tools" / "plugin" / "pack.py"
MEAS1 = PROBE / "probe1-measurement.json"


def main() -> int:
    if not MEAS1.is_file():
        print("FAILED:IMP-0002-probe2 missing probe1-measurement.json", file=sys.stderr)
        return 2
    prior = json.loads(MEAS1.read_text(encoding="utf-8"))
    expected = prior["build1_sha256"]

    lines = [
        "NAMED PROBE 2: THIRD BUILD OTHER CWD + TMPDIR + CLOCK OFFSET",
        "PROBE-2-BEGIN:IMP-0002",
        "script=probe2_third_build_independent.py",
        "imports_probe1=false",
        f"expected_from_probe1={expected}",
    ]

    with tempfile.TemporaryDirectory(prefix="imp0002-probe2-") as td:
        td_path = Path(td)
        out = td_path / "build3.zip"
        env = os.environ.copy()
        env["TMPDIR"] = str(td_path / "tmp")
        env["TEMP"] = env["TMPDIR"]
        env["TMP"] = env["TMPDIR"]
        Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
        # Shift perceived clock for child via libfaketime if present; else sleep +
        # document offset. We still change cwd and TMPDIR (required independence).
        clock_offset_seconds = 3600
        lines.append(f"clock_offset_seconds={clock_offset_seconds}")
        lines.append(f"tmpdir={env['TMPDIR']}")
        lines.append(f"cwd={td_path}")

        # Prefer faketime when available so ZipInfo would diverge if mtimes leaked.
        faketime = None
        for cand in ("faketime", "/usr/bin/faketime"):
            if (
                Path(cand if cand.startswith("/") else "").exists()
                or cand == "faketime"
            ):
                from shutil import which

                faketime = which("faketime")
                break

        cmd = [
            sys.executable,
            "-B",
            str(PACK_PY),
            "--repo",
            str(REPO),
            "--rev",
            "HEAD",
            "--allowlist",
            str(REPO / "tools/plugin/payload-allowlist.json"),
            "--prefix",
            "tools/plugin",
            "--out",
            str(out),
            "--json",
        ]
        if faketime:
            cmd = [faketime, f"+{clock_offset_seconds}s", *cmd]
            lines.append(f"faketime={faketime}")
        else:
            # No faketime: still change environment; sleep past second boundary.
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
        if proc.returncode != 0 or not out.is_file():
            raw = "\n".join(lines) + "\nFAILED:IMP-0002-probe2\n"
            (PROBE / "probe2-third-build.raw.txt").write_text(raw, encoding="utf-8")
            print(raw, end="")
            return 1

        h3 = hashlib.sha256(out.read_bytes()).hexdigest()
        # Copy artifact into probe tree for receipt anchors.
        dest = PROBE / "work" / "probe2" / "build3.zip"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(out.read_bytes())
        equal = h3 == expected
        meas = {
            "build3_sha256": h3,
            "expected_build1_sha256": expected,
            "equal_to_probe1": equal,
            "tmpdir": env["TMPDIR"],
            "cwd": str(td_path),
            "clock_offset_seconds": clock_offset_seconds,
            "faketime": bool(faketime),
        }
        (PROBE / "probe2-measurement.json").write_text(
            json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        lines.extend(
            [
                f"build3_sha256={h3}",
                f"equal_to_probe1={equal}",
                "PROBE-2-COMPLETE:IMP-0002",
                "SUCCESS:IMP-0002-probe2" if equal else "FAILED:IMP-0002-probe2",
            ]
        )
        raw = "\n".join(lines) + "\n"
        (PROBE / "probe2-third-build.raw.txt").write_text(raw, encoding="utf-8")
        print(raw, end="")
        return 0 if equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
