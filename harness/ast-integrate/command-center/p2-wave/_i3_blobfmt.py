r"""CI-parity: are the files this lane COMMITTED ruff-clean as CI will see them?

A local ruff green proves nothing when the worktree is CRLF and the blob is LF -- ruff can format
the two forms differently, which is precisely how a "1 file already formatted" local green sat
against a CI "Would reformat" for the same commit.

Two things this gets right that the naive version does not:
  * blobs are read with `git ls-files -s` + `git cat-file -p`, never `git archive` (which returns
    the CRLF worktree bytes on Windows and would verify the wrong bytes);
  * the scratch tree is created INSIDE the repo so `ruff.toml` still applies. A bare temp dir falls
    back to ruff defaults (line-length 88 vs this project's setting) and manufactures a false red.

A mis-formatted control is planted in the same run, so silence on the real files means something.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUFF = ["uvx", "ruff@0.15.17"]

LANE_FILES = [
    "tools/measure-guard/unitgate.py",
    "tools/measure-guard/tests/test_unitgate.py",
    "command-center/ready_units.py",
    "command-center/p2-wave/_i1_dark_probe.py",
    "command-center/p2-wave/_i1_dark_probe2.py",
    "command-center/p2-wave/_i2_redproof.py",
    "command-center/p2-wave/_i3_blobfmt.py",
]

CONTROL = (
    "x = {  'deliberately' :'mis-formatted'  ,'so':'the silence means something'}\n"
)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)


def blob_bytes(rel: str) -> bytes | None:
    ls = run(["git", "ls-files", "-s", "--", rel]).stdout.split()
    if len(ls) < 2:
        return None
    proc = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", ls[1]], capture_output=True
    )
    return proc.stdout if proc.returncode == 0 else None


def main() -> int:
    scratch = REPO / "_i3_blobfmt_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    report: dict = {"files": [], "untracked": [], "crlf_total": 0}
    try:
        for rel in LANE_FILES:
            data = blob_bytes(rel)
            if data is None:
                report["untracked"].append(rel)
                continue
            dst = scratch / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            crlf = data.count(b"\r\n")
            report["crlf_total"] += crlf
            report["files"].append({"path": rel, "bytes": len(data), "crlf": crlf})

        (scratch / "_control_badly_formatted.py").write_text(CONTROL, encoding="utf-8")

        fmt = run([*RUFF, "format", "--check", str(scratch)])
        lint = run([*RUFF, "check", str(scratch)])
        would = [
            ln.split("Would reformat:", 1)[1].strip()
            for ln in fmt.stdout.splitlines()
            if "Would reformat:" in ln
        ]
        control_fired = any("_control_badly_formatted" in w for w in would)
        real_bad = [w for w in would if "_control_badly_formatted" not in w]
        report.update(
            {
                "control_fired": control_fired,
                "real_files_needing_reformat": real_bad,
                "lint_exit": lint.returncode,
                "lint_tail": lint.stdout.strip().splitlines()[-3:],
            }
        )
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)

    Path(__file__).with_suffix(".out.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        f"  blobs={len(report['files'])} untracked={report['untracked']} "
        f"CRLF-bytes={report['crlf_total']}"
    )
    print(
        f"  control planted and FIRED = {report['control_fired']}  "
        f"real files needing reformat = {len(report['real_files_needing_reformat'])}  "
        f"lint exit = {report['lint_exit']}"
    )

    if not report["control_fired"]:
        print(
            "FAILED:i3-blobfmt the mis-formatted control did NOT fire, so a clean reading on the "
            "real files would have measured nothing"
        )
        return 1
    if report["untracked"]:
        print(f"FAILED:i3-blobfmt not committed: {report['untracked']}")
        return 1
    if report["real_files_needing_reformat"] or report["lint_exit"] != 0:
        print("FAILED:i3-blobfmt the stored blobs are not CI-clean")
        return 1
    print(
        f"SUCCESS:i3-blobfmt {len(report['files'])} stored blobs, {report['crlf_total']} CRLF "
        "bytes, 0 needing reformat, 0 lint findings, control fired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
