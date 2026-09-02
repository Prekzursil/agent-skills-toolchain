#!/usr/bin/env python3
"""Probe 2: atomic tmp+rename publish hides the partial under SIGKILL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def main() -> int:
    # Detector control: the streaming writer MUST leave a readable partial,
    # otherwise the atomic claim is unfalsifiable.
    leaked = S.truncated_kill()
    hidden = S.atomic_kill()
    complete = S.complete_atomic()
    print(
        json.dumps(
            {
                "probe": "probe2-atomic-invisible",
                "unit_id": "TST-0088",
                "pass": True,
                "streaming_partial_visible": leaked["classification"]["exists"],
                "streaming_condition_id": leaked["classification"]["condition_id"],
                "atomic_destination_visible": hidden["destination_visible"],
                "atomic_published_partial": hidden["published_partial"],
                "atomic_tmp_exists": hidden["kill"]["tmp_exists"],
                "atomic_complete_verdict": complete["classification"]["verdict"],
                "signal": hidden["kill"]["signal"],
                "saw_ready": hidden["kill"]["saw_ready"],
            },
            sort_keys=True,
        )
    )
    print(
        f"streaming_partial_visible={leaked['classification']['exists']} "
        f"atomic_dest_visible={hidden['destination_visible']} "
        f"atomic_complete={complete['classification']['verdict']}"
    )
    if not leaked["classification"]["exists"]:
        print("FAILED:TST-0088-probe2 detector control: streaming kill left nothing")
        return 1
    if hidden["destination_visible"] or hidden["published_partial"]:
        print("FAILED:TST-0088-probe2 atomic kill exposed a destination partial")
        return 1
    if complete["classification"]["verdict"] != "SUCCESS":
        print("FAILED:TST-0088-probe2 uninterrupted atomic write was not SUCCESS")
        return 1
    print(
        "SUCCESS:TST-0088-probe2 atomic write prevents the partial from being visible at all"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
