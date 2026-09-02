#!/usr/bin/env python3
"""Probe 2: negative control + independent resolution API.

Measuring the short alias must be shown to admit an over-limit write.
The production writer records the resolved length; GNU ``readlink -f``
(and a second /bin/bash invocation) must agree. pwsh7 is probed and
named as MISSING on this Linux box rather than substituted.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def pwsh_probe() -> dict:
    exe = shutil.which("pwsh")
    if not exe:
        return {
            "present": False,
            "divergence": None,
            "note": (
                "pwsh7 is MISSING on this Linux worktree; the catalog "
                "second-shell reviewer is /bin/bash (Git Bash analog). "
                "powershell was not substituted."
            ),
        }
    return {"present": True, "path": exe, "divergence": None}


def main() -> int:
    row = S.run_negative_alias()
    pwsh = pwsh_probe()
    bash_vs_readlink = row["bash_resolved"] == row["independent_readlink_f"]
    summary = {
        "probe": "probe2-negative-alias",
        "unit_id": "TST-0202",
        "pass": row["pass"] and bash_vs_readlink,
        "alias_admits_over_limit_write": row["alias_admits_over_limit_write"],
        "production_refused": row["production_refused"],
        "lengths_agree": row["lengths_agree"],
        "writer_measured_length": row["writer_measured_length"],
        "independent_length": row["independent_length"],
        "bash_length": row["bash_length"],
        "independent_api": "readlink -f (GNU coreutils, not pathlib.Path.resolve)",
        "second_shell": "/bin/bash",
        "bash_agrees_with_readlink": bash_vs_readlink,
        "pwsh": pwsh,
        "alias_length": row["over"]["alias_length"],
        "resolved_length": row["over"]["resolved_length"],
        "budget": row["over"]["budget"],
        "defect_measured_length": row["defect"]["measured_length"],
        "defect_measure": row["defect"]["measure"],
    }
    print(json.dumps(summary, sort_keys=True))
    if not row["pass"] or not bash_vs_readlink:
        print("FAILED:TST-0202-probe2 negative alias or independent resolve")
        return 1
    print("SUCCESS:TST-0202-probe2 alias-defect admits over-limit write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
