#!/usr/bin/env python3
"""Probe 2: each consumer parser's resolution is measured, not assumed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "lib"))
sys.path.insert(0, str(REPO / "tools" / "plugin" / "tests"))

from plugin.duplicate_key_matrix import (  # noqa: E402
    assert_table_is_a_measurement,
    measure_matrix,
)
from test_duplicate_keys import (  # noqa: E402
    test_each_consumer_parser_behaviour_is_recorded_not_assumed,
)


def main() -> int:
    result = test_each_consumer_parser_behaviour_is_recorded_not_assumed()
    table = measure_matrix()
    check = assert_table_is_a_measurement(table)
    live = [r for r in table["parsers"] if r.get("live") is True]
    resolutions = sorted({r["resolution"] for r in live})
    if len(resolutions) < 2:
        print("FAILED:TST-0054-probe2 assumed a single resolution")
        return 1
    payload = {
        "probe": "probe2-consumer-behaviours-recorded",
        "unit_id": "TST-0054",
        "pass": True,
        "fixture": table["fixture"],
        "independent_pairs_hook": table["independent_pairs_hook"],
        "duplicate_name_occurrence_count": table["duplicate_name_occurrence_count"],
        "resolutions_observed": resolutions,
        "last_wins_parsers": table["last_wins_parsers"],
        "error_parsers": table["error_parsers"],
        "first_wins_parsers": table["first_wins_parsers"],
        "naive_json_loads_hides_duplicate": table["naive_json_loads_hides_duplicate"],
        "pipeline_json_loads_caller_count": check["pipeline_json_loads_caller_count"],
        "stdlib_resolution": result["stdlib"]["resolution"],
        "strict_resolution": result["strict"]["resolution"],
        "assumed": False,
        "measured_live": True,
        "parsers": table["parsers"],
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print("SUCCESS:TST-0054-probe2 consumer behaviours recorded not assumed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
