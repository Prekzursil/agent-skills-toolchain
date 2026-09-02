#!/usr/bin/env python3
"""Probe 1: LF-normalized vendored vs upstream tree diff."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def main() -> int:
    eol = E.eol_control()
    print("EOL control: a file differing only in line endings must not count as drift, proven on a known CRLF-only case before any count is reported")
    print(json.dumps(eol, indent=2, sort_keys=True))
    if not eol["pass"]:
        print("FAILED:ADV-0059-probe1 eol control counted CRLF as drift")
        return 1
    mutant = E.content_mutant()
    print(json.dumps(mutant, indent=2, sort_keys=True))
    if not mutant["pass"]:
        print("FAILED:ADV-0059-probe1 content mutant silent")
        return 1
    live = E.live_diff()
    print("Probe 1: byte-level tree diff between the vendored copy and the upstream revision after LF normalisation, listing every differing path.")
    print(json.dumps(live, indent=2, sort_keys=True))
    print(
        f"SUCCESS:ADV-0059-probe1 eol_ok identical_drift={live['identical_drift']} "
        f"ralph_drift={live['ralph_drift']} hacktricks_drift={live['hacktricks_drift']} "
        f"live_roots_present={live['live_known_roots_present']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
