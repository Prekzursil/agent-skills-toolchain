#!/usr/bin/env python3
"""Named probe 1: fake server 429 + Retry-After; inter-arrival matches policy.

Signal (1) of IMP-0122. Client-side intent is not evidence — the fake
server records arrival times on a shared clock.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _lib import SENTINEL, TOOLS  # noqa: E402

sys.path.insert(0, str(TOOLS))
from marketplace.rate_limit_client import (  # noqa: E402
    measure_retry_after_honoured,
    measure_storm_is_named,
)


def main() -> int:
    retry = measure_retry_after_honoured(retry_after_s=1.5, seed=7)
    storm = measure_storm_is_named()
    print(
        json.dumps(
            {
                "probe": "probe1-retry-after",
                "unit_id": "IMP-0122",
                "retry": retry,
                "storm": storm,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    if not retry["honoured"] or not retry["within_jitter_cap"]:
        print("FAILED:IMP-0122-probe1 Retry-After not honoured on the server clock")
        return 1
    if retry["attempts"] != 2 or retry["status"] != 200:
        print("FAILED:IMP-0122-probe1 unexpected retry shape")
        return 1
    if not storm["not_a_cascade"] or storm["condition"] != "429-storm":
        print("FAILED:IMP-0122-probe1 429 storm was not a named condition")
        return 1
    print(
        f"gap={retry['gap']:.6f}s retry_after={retry['retry_after_s']} "
        f"honoured={retry['honoured']} storm={storm['condition']} "
        f"cancelled={storm['cancelled_remaining']} hits={storm['server_hits']}"
    )
    print(f"{SENTINEL}-probe1 Retry-After honoured; 429-storm is named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
