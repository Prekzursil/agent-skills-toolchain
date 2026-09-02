#!/usr/bin/env python3
"""Probe 1: use-vs-mention control (1 real + 1 quoted => count 1 per class)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
from synthesis.digest_loss import (  # noqa: E402
    CLASSES,
    count_body,
    use_vs_mention_control,
)

FIXTURE = HERE / "fixtures" / "use_vs_mention.md"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0013-probe1 {msg}")
    return 1


def main() -> int:
    if not FIXTURE.is_file():
        return fail(f"missing {FIXTURE}")
    text = FIXTURE.read_text(encoding="utf-8")
    counted = count_body(text)
    control = use_vs_mention_control(text)
    print(
        json.dumps(
            {
                "probe": "probe1-use-vs-mention",
                "unit_id": "SYN-0013",
                "fixture": FIXTURE.relative_to(REPO).as_posix(),
                "use": counted["use"],
                "mention": counted["mention"],
                "control": control,
            },
            indent=1,
            sort_keys=True,
        )
    )
    if not control["pass"]:
        return fail(f"control {control['per_class']}")
    for cls in CLASSES:
        if counted["use"][cls] != 1 or counted["mention"][cls] != 1:
            return fail(f"{cls} use={counted['use'][cls]} mention={counted['mention'][cls]} want 1/1")
    print("SUCCESS:SYN-0013-probe1 use-vs-mention 1-real-1-quoted counts 1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
