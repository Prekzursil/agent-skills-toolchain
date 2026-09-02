#!/usr/bin/env python3
"""Named probe 2: unquoted control fires; quoted state is silent (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from fixtures import BREAKOUT, benign_imports, hostile_imports  # noqa: E402
from import_quarantine import (  # noqa: E402
    CANARY,
    HOSTILE_INSTRUCTION,
    data_spans,
    hits_as_dicts,
    payload_bytes,
    render_prompt,
    splice_unquoted,
    unquoted_hits,
    utf8,
)


def main() -> int:
    quoted = render_prompt(hostile_imports(include_breakout=True))
    quoted_hits = unquoted_hits(quoted.raw)

    unquoted_blob = splice_unquoted(
        render_prompt(benign_imports()).raw, utf8("\n" + HOSTILE_INSTRUCTION + "\n")
    )
    unquoted = unquoted_hits(unquoted_blob)

    benign = render_prompt(benign_imports())
    benign_hits = unquoted_hits(benign.raw)

    mkt = next(
        s
        for s in data_spans(quoted.raw)
        if s.source_id == "marketplace/pkg.catalog-class"
    )
    mkt_payload = payload_bytes(quoted.raw, mkt.source_id)
    breakout_held = utf8(BREAKOUT) in mkt_payload
    forged_absent = all(s.source_id != "forged" for s in data_spans(quoted.raw))

    fired_on_unquoted = len(unquoted) > 0 and any(h.channel == "directive" for h in unquoted)
    silent_on_quoted = len(quoted_hits) == 0
    silent_on_benign = len(benign_hits) == 0

    ok = (
        fired_on_unquoted
        and silent_on_quoted
        and silent_on_benign
        and breakout_held
        and forged_absent
        and utf8(CANARY) in mkt_payload
    )
    report = {
        "probe": "probe2-unquoted-control",
        "unit_id": "IMP-0169",
        "pass": ok,
        "fired_on_unquoted": fired_on_unquoted,
        "silent_on_quoted": silent_on_quoted,
        "silent_on_benign": silent_on_benign,
        "unquoted_hit_count": len(unquoted),
        "quoted_unquoted_hit_count": len(quoted_hits),
        "benign_unquoted_hit_count": len(benign_hits),
        "unquoted_hits": hits_as_dicts(unquoted),
        "breakout_held_inside_marketplace_payload": breakout_held,
        "forged_source_id_not_parsed_as_region": forged_absent,
        "data_region_ids": [s.source_id for s in data_spans(quoted.raw)],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0169-probe2 both-states unquoted control")
        return 1
    print("SUCCESS:IMP-0169-probe2 unquoted payload caught; quoted silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
