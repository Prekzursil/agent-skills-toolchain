"""Are the 4 ci/tests failures MINE, or pre-existing on this box?

Two hypotheses, and a control that can tell them apart:
  H1  this lane's change broke them   -> they pass at HEAD (which carries none of my files)
  H2  they are pre-existing           -> they fail at HEAD too

The clone is made from HEAD, so it contains NONE of this lane's uncommitted files. Running the
same four node ids there is mechanically independent of my working tree.

Run:  python command-center/p2-next/_l2_pre_existing_control.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

NODE_IDS = [
    "ci/tests/test_check_skill_dual_write.py::test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct",
    "tools/d001-dual-write/tests/test_d001_apply.py::test_project_keeps_distinct_invalid_utf8_path_bytes",
    "tools/d001-dual-write/tests/test_d001_apply.py::test_verifier_refuses_an_executable_mode_regression",
    "tools/d001-dual-write/tests/test_d001_apply.py::test_atomic_ref_create_refuses_a_branch_created_after_precheck",
]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="p2next-l2-"))
    clone = tmp / "clone"
    try:
        r = subprocess.run(
            ["git", "clone", "--no-hardlinks", "-q", str(REPO), str(clone)],
            cwd=tmp,
            capture_output=True,
        )
        if r.returncode != 0:
            print(f"FAILED:l2-control clone rc={r.returncode}")
            return 2
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=clone,
            capture_output=True,
            text=True,
        ).stdout.strip()

        # CONTROL that the clone is really a NO-LANE-FILES state: my wiring test must be ABSENT
        # there. Without this, a clone that somehow carried my files would make H2 unfalsifiable.
        mine = clone / "ci" / "tests" / "test_p2next_tree_survey_wiring.py"
        print(
            f"clone HEAD={head}  my wiring test present in clone: {mine.is_file()} (want False)"
        )
        if mine.is_file():
            print(
                "FAILED:l2-control the clone carries lane files; it cannot separate H1 from H2"
            )
            return 2

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *NODE_IDS, "-q"],
            cwd=clone,
            capture_output=True,
            timeout=1800,
        )
        out = proc.stdout.decode("utf-8", "replace")
        summary = [ln for ln in out.splitlines() if "passed" in ln or "failed" in ln]
        print(f"pytest at HEAD rc={proc.returncode}")
        for ln in summary[-3:]:
            print(f"  {ln}")

        (REPO / "command-center/p2-next/L2-PREEXISTING-CONTROL.json").write_text(
            json.dumps(
                {
                    "clone_head": head,
                    "node_ids": NODE_IDS,
                    "rc_at_head": proc.returncode,
                    "summary": summary[-3:],
                },
                indent=2,
            ),
            encoding="utf-8",
            newline="\n",
        )
        if proc.returncode != 0:
            print(
                "SUCCESS:l2-control H2 CONFIRMED -- these 4 fail at HEAD, which carries none of "
                "this lane's files, so they are pre-existing and not introduced here"
            )
            return 0
        print(
            "FAILED:l2-control H1 -- they PASS at HEAD, so this lane's change is implicated"
        )
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
