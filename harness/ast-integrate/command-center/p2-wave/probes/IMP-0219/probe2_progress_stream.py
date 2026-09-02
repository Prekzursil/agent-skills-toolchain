#!/usr/bin/env python3
"""IMP-0219 probe 2: a progress-stream body is never parsed as a result.

Asserts the taxonomy reason string severed-stream. A mutant that JSON-loads the
progress body would expand to 5 units; production expands to 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))

from test_dynamic_fanout import (  # noqa: E402
    test_progress_stream_never_parsed_as_result,
)


def main() -> int:
    result = test_progress_stream_never_parsed_as_result()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["pass"]:
        print("FAILED:IMP-0219-probe2 progress-stream parsed as result")
        return 1
    if result["taxonomy_reason"] != "severed-stream":
        print("FAILED:IMP-0219-probe2 taxonomy reason")
        return 1
    if result["mutant_parse_progress_cardinality"] != 5:
        print("FAILED:IMP-0219-probe2 mutant did not discriminate")
        return 1
    print("SUCCESS:IMP-0219-probe2 progress-stream never parsed as result")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
