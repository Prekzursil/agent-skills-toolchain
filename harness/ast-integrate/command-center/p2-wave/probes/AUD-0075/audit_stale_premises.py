#!/usr/bin/env python3
"""AUD-0075 CLI retained from the harvest-era harness name.

Subcommands: emit, probe1, probe2, controls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import emit as EM  # noqa: E402
import probe1_remeasure as P1  # noqa: E402
import probe2_origin_audit as P2  # noqa: E402


def main() -> int:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "emit").strip()
    if cmd in {"emit", "implement"}:
        return EM.main()
    if cmd in {"probe1", "remeasure"}:
        return P1.main()
    if cmd in {"probe2", "origin"}:
        return P2.main()
    if cmd in {"controls"}:
        report = E.fingerprint_controls()
        print(json.dumps(report, indent=2, sort_keys=True))
        ok = all(
            [
                report["same_fingerprint_rejected"],
                report["distinct_fingerprint_accepted"],
                report["missing_source_is_rejected"],
                report["ready_comparator_silent_on_good"],
                report["ready_comparator_fires_on_bad"],
            ]
        )
        print("SUCCESS:AUD-0075-controls" if ok else "FAILED:AUD-0075-controls")
        return 0 if ok else 1
    print(f"FAILED:AUD-0075 unknown subcommand {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
