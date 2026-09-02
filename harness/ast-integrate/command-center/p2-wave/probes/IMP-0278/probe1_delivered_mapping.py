#!/usr/bin/env python3
"""Named probe 1: partition definition → delivered-context mapping.

Also runs the delivered-prompt leak scan (required zero hits) and the
detector control (scanner finds a token that WAS delivered) before
silence is trusted. Both checks operate on rendered prompt strings.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.integrity.partition import (  # noqa: E402
    detector_control,
    deliver_all,
    facts_visible,
    load_spec,
    partitions_differ,
    scan_delivered,
    scan_text,
    tokens_withheld,
)

FIXTURE = HERE / "fixtures" / "scenario.json"
MODULE = REPO / "tools" / "council" / "integrity" / "partition.py"

EXPECTED = {
    "alice": ["shared-charge", "alpha-private-source", "alpha-beta-joint"],
    "bob": ["shared-charge", "beta-private-source", "alpha-beta-joint"],
    "observer": ["shared-charge", "gamma-observer-note"],
}


def main() -> int:
    if not MODULE.is_file():
        print("FAILED:IMP-0278-probe1 partition.py missing")
        return 1
    spec = load_spec(FIXTURE)
    delivered = deliver_all(spec)

    mapping_ok = True
    mapping_rows = {}
    for seat_id, want_ids in EXPECTED.items():
        ctx = delivered[seat_id]
        got = list(ctx.fact_ids)
        vis = [f.fact_id for f in facts_visible(spec, seat_id)]
        row = {
            "partition_id": ctx.partition_id,
            "expected_fact_ids": want_ids,
            "delivered_fact_ids": got,
            "visible_table": vis,
            "prompt_chars": len(ctx.prompt),
        }
        if got != want_ids or vis != want_ids:
            mapping_ok = False
            row["ok"] = False
        else:
            # Tokens expected in this seat must appear in the prompt string.
            missing = [t for t in ctx.tokens if t not in ctx.prompt]
            extra_leak = [t for t in tokens_withheld(spec, seat_id) if t in ctx.prompt]
            row["missing_visible_tokens_in_prompt"] = missing
            row["withheld_tokens_in_prompt"] = extra_leak
            row["ok"] = not missing and not extra_leak
            if not row["ok"]:
                mapping_ok = False
        mapping_rows[seat_id] = row

    differ = partitions_differ(delivered)
    hits = scan_delivered(spec, delivered)

    # Detector control: alice's exclusive alpha token must be found in alice's
    # delivered prompt by the same scanner used for leak silence.
    alice_prompt = delivered["alice"].prompt
    alpha_token = "PTOK-ALPHA-imp0278-7f3a"
    control_found = detector_control(alice_prompt, alpha_token)
    control_scan = scan_text(alice_prompt, [alpha_token])

    # Shared token must be in every delivered prompt (positive presence).
    shared = "PTOK-SHARED-imp0278-c0a1"
    shared_all = all(shared in delivered[s].prompt for s in EXPECTED)

    payload = {
        "probe": "probe1-delivered-mapping",
        "unit_id": "IMP-0278",
        "module": "tools/council/integrity/partition.py",
        "fixture": "command-center/p2-wave/probes/IMP-0278/fixtures/scenario.json",
        "mapping": mapping_rows,
        "mapping_ok": mapping_ok,
        "partitions_differ": differ,
        "leak_hits": [
            {
                "seat_id": h.seat_id,
                "token": h.token,
                "fact_id": h.fact_id,
                "index": h.index,
            }
            for h in hits
        ],
        "leak_hit_count": len(hits),
        "detector_control_token": alpha_token,
        "detector_control_found": control_found,
        "detector_control_scan": control_scan,
        "shared_token_in_all_prompts": shared_all,
        "scan_target": "delivered_prompt_text",
        "not_a_config_read": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if not mapping_ok:
        print("FAILED:IMP-0278-probe1 mapping mismatch")
        return 1
    if not differ:
        print("FAILED:IMP-0278-probe1 delivered prompts do not differ")
        return 1
    if hits:
        print(f"FAILED:IMP-0278-probe1 leak scan fired n={len(hits)}")
        return 1
    if not control_found or control_scan != [alpha_token]:
        print("FAILED:IMP-0278-probe1 detector control did not find delivered token")
        return 1
    if not shared_all:
        print("FAILED:IMP-0278-probe1 shared token missing from a prompt")
        return 1
    print(
        "SUCCESS:IMP-0278-probe1 mapping+leak-scan-zero+detector-control "
        f"seats={len(EXPECTED)} leaks=0 detector_found={control_found}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
