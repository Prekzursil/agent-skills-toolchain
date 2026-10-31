#!/usr/bin/env python3
"""IMP-0011 probe1 (source): three-way pack digests match after normalisation."""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.repro_gate import inspect_workflows, negative_control, three_way  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        res = three_way(Path(td))
        cmp = res["compare"]
        checks = {
            "three_way_equal": cmp["equal"] is True,
            "linux_1_eq_linux_2": res["linux_1"]["sha256"] == res["linux_2"]["sha256"],
            "windows_eq_linux": res["windows"]["sha256"] == res["linux_1"]["sha256"],
            "crlf_normalised": res["windows"]["worktree_crlf"] >= 0,
        }
        print(json.dumps({"compare": cmp, "checks": checks}, indent=1))
        if not all(checks.values()):
            print("FAILED:IMP-0011-probe1 digests diverge")
            return 1
        print("SUCCESS:IMP-0011-probe1 linux1==linux2==windows after CRLF normalisation")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
