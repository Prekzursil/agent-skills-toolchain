#!/usr/bin/env python
"""Read-only measurement of success.json: is the suggested-vs-used signal readable?

Prints counts only (never a key dump). Exists because the router's `boost()` is
alpha * used/(suggested+2): if `used` is 0 for every key the signal is DEAD, and a large
accumulated `suggested` permanently flattens the ratio even after `used` starts arriving.

Usage:  python measure_success.py [path-to-success.json]
"""

import json
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent


def main(argv=None):
    argv = argv or sys.argv[1:]
    path = Path(argv[0]) if argv else THIS / "success.json"
    if not path.exists():
        print(f"FAILED:measure-success no such file {path}")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:measure-success unparseable ({type(exc).__name__})")
        return 1
    if not isinstance(data, dict) or not data:
        print("FAILED:measure-success empty or not a mapping (fail closed)")
        return 1

    keys = len(data)
    sug = sum(int((v or {}).get("suggested", 0)) for v in data.values())
    used = sum(int((v or {}).get("used", 0)) for v in data.values())
    with_used = sum(1 for v in data.values() if int((v or {}).get("used", 0)) > 0)
    max_sug = max(int((v or {}).get("suggested", 0)) for v in data.values())

    print(f"keys={keys} suggested_total={sug} used_total={used} keys_with_used={with_used} max_suggested={max_sug}")
    if sug == 0 and used == 0:
        # Distinct from DEAD: a freshly reset store has nothing to read YET, which is correct
        # rather than broken. Without this branch a legitimate reset reads as a failure.
        print("SIGNAL=FRESH (counters reset; no suggestion recorded yet -- re-read after a session)")
    elif used == 0:
        print("SIGNAL=DEAD  (used==0 for every key -> boost() returns 0.0 everywhere)")
    else:
        print(f"SIGNAL=LIVE  (ratio used/suggested = {used / max(sug, 1):.4f})")
    print("SUCCESS:measure-success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
