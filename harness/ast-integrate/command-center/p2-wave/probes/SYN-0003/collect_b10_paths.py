#!/usr/bin/env python3
"""Discriminating collector: empty adversarial/ vs ADV probe trees."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADV = REPO / "command-center/adversarial"
PROBES = REPO / "command-center/p2-wave/probes"


def main() -> int:
    adv_files = (
        [p.relative_to(REPO).as_posix() for p in ADV.rglob("*") if p.is_file()]
        if ADV.is_dir()
        else []
    )
    dirs = [p.name for p in PROBES.glob("ADV-*") if p.is_dir()] if PROBES.is_dir() else []
    returns = (
        [p.parent.name for p in PROBES.glob("ADV-*/SUBAGENT-RETURN.json")]
        if PROBES.is_dir()
        else []
    )
    print(
        json.dumps(
            {
                "collector": "b10-paths",
                "adversarial_present": ADV.is_dir(),
                "adversarial_file_count": len(adv_files),
                "adv_probe_dirs": len(dirs),
                "adv_subagent_returns": len(returns),
                "verdict": (
                    "path-convention-gap"
                    if dirs and not adv_files
                    else ("missing-b10-labor" if not dirs and not adv_files else "landed")
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
