#!/usr/bin/env python3
"""Probe 2: independent reviewer — a repairing parser must fail this unit's contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    ArtifactParseCache,
    LenientParseCache,
    truncated_contract_holds,
)


def main() -> int:
    strict = truncated_contract_holds(ArtifactParseCache())
    mutant = truncated_contract_holds(LenientParseCache())
    # The catalog negative control: a lenient parser that repairs truncated
    # JSON must fail this test. Strict must still pass.
    ok = (
        strict["pass"] is True
        and mutant["pass"] is False
        and mutant["cached"] is True
        and mutant["parsed"] is True
        and mutant["consumer_holds"] is True
        and strict["cached"] is False
        and strict["byte_offset"] is not None
        and int(strict["byte_offset"]) >= 0
    )
    payload = {
        "ok": bool(ok),
        "probe": "probe2-lenient-repair-mutant-must-fail-this-test",
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0144-probe2-lenient-mutant",
            "verdict": "PASS" if ok else "FAIL",
        },
        "strict": strict,
        "mutant": mutant,
        "unit_id": "TST-0144",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print(
            "FAILED:TST-0144-probe2 lenient repair mutant must fail the truncated-JSON cache contract"
        )
        return 1
    print(
        "SUCCESS:TST-0144-probe2 strict cache-miss byte_offset="
        f"{strict['byte_offset']}; lenient mutant cached={mutant['cached']} "
        "so this test fails the repairing parser"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
