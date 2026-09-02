#!/usr/bin/env python3
"""Probe 1: rebuild the attested package twice and compare hashes.

On mismatch, diff member lists then differing members. Also the source-mutant
negative control (comparator must go red) and the identical-environment control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from probe_common import run_rebuild_compare  # noqa: E402


def main() -> int:
    result = run_rebuild_compare()
    print(json.dumps(result, sort_keys=True, indent=2))
    if not result.get("identical_environment_rebuilds_match"):
        print("FAILED:ADV-0062-probe1 identical-environment rebuilds diverged")
        return 1
    if not result.get("attested_rebuild_byte_identical"):
        print("FAILED:ADV-0062-probe1 attested rebuild was not byte-identical")
        return 1
    if not result.get("comparator_fires_on_source_mutant"):
        print("FAILED:ADV-0062-probe1 comparator silent on source mutant")
        return 1
    if not result.get("silent_on_good_identical_rebuild"):
        print("FAILED:ADV-0062-probe1 comparator fired on good identical rebuild")
        return 1
    print(
        "SUCCESS:ADV-0062-probe1 identical rebuilds match; "
        "source mutant turns the comparator red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
