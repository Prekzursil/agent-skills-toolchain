#!/usr/bin/env python3
"""IMP-0044 probe1: same-run both-states control.

Signal 1: the deliberately useless always-OK probe is marked UNTRUSTWORTHY.
Signal 2: the genuine content-marker probe is marked TRUSTED - in the SAME
run, so the harness is proven against both states at once.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.both_states_harness import (  # noqa: E402
    TRUSTED,
    UNTRUSTWORTHY,
    same_run_catalog_evidence,
)


def main() -> int:
    ev = same_run_catalog_evidence()
    by_id = ev.by_id()
    useless = by_id["always-ok"]
    genuine = by_id["content-marker"]
    checks = {
        "same_run": bool(ev.same_run),
        "useless_untrustworthy": useless.trust == UNTRUSTWORTHY,
        "useless_not_skipped": not useless.skipped,
        "genuine_trusted": genuine.trust == TRUSTED,
        "counts_pair": ev.trusted_count == 1 and ev.untrustworthy_count == 1,
    }
    out = {
        "probe": "probe1-same-run",
        "unit_id": "IMP-0044",
        "checks": checks,
        "rows": {
            "always-ok": {"trust": useless.trust, "reason": useless.reason,
                          "skipped": useless.skipped},
            "content-marker": {"trust": genuine.trust, "reason": genuine.reason,
                               "skipped": genuine.skipped},
        },
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    print(f"always_ok_flagged={checks['useless_untrustworthy']} "
          f"genuine_trusted={checks['genuine_trusted']} same_run={checks['same_run']}")
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        print(f"FAILED:IMP-0044-probe1 {failed}")
        return 1
    print("SUCCESS:IMP-0044-probe1 same-run: useless probe flagged, genuine probe trusted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
