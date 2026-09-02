#!/usr/bin/env python3
"""Named probe 1: capture, attribution, conservation, verbatim claim survival.

Signal 1 is in-count vs out-count at every pipeline stage.
Signal 2 is text-presence: each distinctive claim survives verbatim or by
resolvable id. Disagreement (counts match but claims summarised away) is FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.dissent import (  # noqa: E402
    AttributionError,
    DissentPipeline,
    from_kernel_events,
)
from scenario import (  # noqa: E402
    MAJORITY_CLAIM,
    TOKEN_ALPHA,
    TOKEN_BETA,
    TOKEN_GAMMA,
    kernel_events_for,
    majority,
    sibling_council,
    two_dissent_council,
    unanimous_council,
    unattributed_dissent_turn,
)

ART = REPO / "command-center/receipts/IMP-0312.json"
UNIT = "IMP-0312"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0312" not in text:
        return fail("sentinel absent")

    pipe = DissentPipeline()
    sibling = pipe.run(sibling_council(), majority=majority(), council_id="council-sibling")
    result = pipe.run(
        two_dissent_council(),
        majority=majority(),
        council_id="council-main",
        children=[sibling.artifact],
    )

    captured_claims = {d.claim for d in result.captured}
    if TOKEN_ALPHA not in captured_claims or TOKEN_BETA not in captured_claims:
        return fail(f"capture missed distinctive claims {sorted(captured_claims)}")
    if len(result.captured) != 2:
        return fail(f"capture count={len(result.captured)} want=2")
    if any(not d.participant_id or not d.turn_id for d in result.attributed):
        return fail("attribution left an unattributed dissent")

    for row in result.ledger:
        if not row.conserved:
            return fail(
                f"conservation broke at {row.stage} in={row.in_count} out={row.out_count} "
                f"lost={row.lost_ids} extra={row.extra_ids}"
            )
    for row in result.presence:
        if not row.ok:
            return fail(f"presence broke at {row.stage} {row.to_dict()}")

    blob = json.dumps(result.artifact, ensure_ascii=False)
    if TOKEN_ALPHA not in blob or TOKEN_BETA not in blob:
        return fail("synthesis summarised a distinctive claim into non-existence")
    if MAJORITY_CLAIM not in blob:
        return fail("majority claim missing; trace is broken rather than dissent-specific")

    if result.parent is None:
        return fail("parent aggregation missing")
    parent_blob = json.dumps(result.parent, ensure_ascii=False)
    if TOKEN_GAMMA not in parent_blob:
        return fail("parent aggregation dropped sibling dissent")
    parent_ids = set(result.parent["minority_report"]["dissent_ids"])
    child_ids = {d.id for d in result.attributed} | {d.id for d in sibling.attributed}
    if child_ids - parent_ids:
        return fail(f"parent missing ids {sorted(child_ids - parent_ids)}")

    uni = pipe.run(unanimous_council(), majority=majority(), council_id="council-unanimous")
    if uni.captured or uni.attributed:
        return fail(f"fabricated dissent on unanimous run n={len(uni.captured)}")
    if uni.artifact["minority_report"]["dissents"]:
        return fail("unanimous synthesis fabricated a minority report")
    if not all(r.conserved and r.in_count == 0 and r.out_count == 0 for r in uni.ledger if r.stage != "parent_aggregation"):
        return fail("unanimous conservation not 0==0")

    try:
        pipe.run(unattributed_dissent_turn(), majority=majority())
        return fail("unattributed dissent was silently accepted")
    except AttributionError as exc:
        attr_msg = str(exc)
        if "participant_id" not in attr_msg:
            return fail(f"attribution error did not name participant_id: {exc}")

    events = from_kernel_events(kernel_events_for(two_dissent_council()))
    via_kernel = pipe.run(events, majority=majority(), council_id="council-kernel")
    if {d.claim for d in via_kernel.captured} != captured_claims:
        return fail("kernel-event adapter lost a dissent")

    stages = [r.stage for r in result.ledger]
    print(
        json.dumps(
            {
                "probe": "probe1-conservation",
                "unit_id": UNIT,
                "pass": True,
                "captured": len(result.captured),
                "attributed": len(result.attributed),
                "stages": stages,
                "ledger": [r.to_dict() for r in result.ledger],
                "presence": [p.to_dict() for p in result.presence],
                "tokens_in_synthesis": {
                    "ALPHA": TOKEN_ALPHA in blob,
                    "BETA": TOKEN_BETA in blob,
                    "majority": MAJORITY_CLAIM in blob,
                },
                "parent_has_gamma": TOKEN_GAMMA in parent_blob,
                "unanimous_empty": True,
                "unattributed_refused": True,
                "kernel_adapter_ok": True,
            },
            indent=2,
        )
    )
    print("SUCCESS:IMP-0312-probe1 capture attribution conservation verbatim-or-id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
