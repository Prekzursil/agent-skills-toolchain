#!/usr/bin/env python3
"""IMP-0002 probe1: two consecutive deterministic builds → equal sha256."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import pack as pack_mod  # noqa: E402

PROBE = Path(__file__).resolve().parent
WORK = PROBE / "work" / "probe1"
OUT1 = WORK / "build1.zip"
OUT2 = WORK / "build2.zip"


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "NAMED PROBE 1: TWO CONSECUTIVE BUILDS SAME WORKTREE",
        "PROBE-1-BEGIN:IMP-0002",
        f"repo={REPO}",
        "prefix=tools/plugin",
        "use_real_mtimes=false",
    ]
    r1 = pack_mod.pack(
        repo=REPO,
        rev="HEAD",
        allowlist=REPO / "tools/plugin/payload-allowlist.json",
        out=OUT1,
        prefix="tools/plugin",
        use_real_mtimes=False,
    )
    r2 = pack_mod.pack(
        repo=REPO,
        rev="HEAD",
        allowlist=REPO / "tools/plugin/payload-allowlist.json",
        out=OUT2,
        prefix="tools/plugin",
        use_real_mtimes=False,
    )
    h1 = hashlib.sha256(OUT1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(OUT2.read_bytes()).hexdigest()
    equal = h1 == h2 == r1.sha256 == r2.sha256
    meas = {
        "build1_sha256": h1,
        "build2_sha256": h2,
        "pack_result1": r1.as_dict(),
        "pack_result2": r2.as_dict(),
        "equal": equal,
        "member_count": len(r1.members),
        "members": r1.members,
    }
    (PROBE / "probe1-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines.extend(
        [
            f"build1_sha256={h1}",
            f"build2_sha256={h2}",
            f"equal={equal}",
            f"member_count={len(r1.members)}",
            f"members={json.dumps(r1.members)}",
            "PROBE-1-COMPLETE:IMP-0002",
            "SUCCESS:IMP-0002-probe1" if equal else "FAILED:IMP-0002-probe1",
        ]
    )
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe1-two-builds.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
