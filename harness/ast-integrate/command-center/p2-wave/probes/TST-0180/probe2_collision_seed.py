#!/usr/bin/env python3
"""Probe 2: regression seed — case-insensitive parser collision is detected.

Two independent signals:
  (a) validator verdict REJECT naming both keys
  (b) case-folded key-set size compared against the raw key-set size
Also: emitter refuses to produce the colliding document.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.case_collision import (  # noqa: E402
    CaseCollisionError,
    casefold_last_wins,
    emit_document,
    independent_signal,
    iter_document_keysets,
    validate_document,
)

SEED = (HERE / "fixtures" / "collision_top.json").read_text(encoding="utf-8")
CLEAN = (HERE / "fixtures" / "clean_plugin.json").read_text(encoding="utf-8")


def main() -> int:
    keysets = iter_document_keysets(SEED)
    sig = independent_signal(keysets)
    verdict = validate_document(SEED)
    lost = casefold_last_wins(SEED)

    emitter_refused = False
    emitter_message = ""
    try:
        emit_document({"Name": "demo-plugin", "name": "other", "version": "1.0.0"})
    except CaseCollisionError as exc:
        emitter_refused = True
        emitter_message = str(exc)

    emitted_clean = emit_document(
        {"name": "demo-plugin", "version": "1.0.0", "description": "ok"}
    )
    clean_roundtrip = validate_document(emitted_clean)

    top = next(ks for ks in keysets if ks.path == "$")
    case_sensitive_would_miss = (
        top.unique_raw_size == 3 and top.casefolded_size == 2
    )

    ok = (
        verdict.accepted is False
        and "case-collision" in verdict.reason
        and "Name" in verdict.reason
        and "name" in verdict.reason
        and sig["any_case_collision"] is True
        and sig["sizes_differ"] is True
        and sig["worst_raw_keyset_size"] == 3
        and sig["worst_casefolded_keyset_size"] == 2
        and emitter_refused
        and "emitter-refused" in emitter_message
        and clean_roundtrip.accepted
        and set(lost.keys()) == {"name", "version"}
        and lost["name"] == "other"
        and case_sensitive_would_miss
        and validate_document(CLEAN).accepted
    )
    payload = {
        "pass": bool(ok),
        "probe": "probe2-collision-seed",
        "unit_id": "TST-0180",
        "signal_a_validator": {
            "accepted": verdict.accepted,
            "reason": verdict.reason,
            "verdict": "REJECT" if not verdict.accepted else "ACCEPT",
        },
        "signal_b_keyset_sizes": sig,
        "emitter_refused": emitter_refused,
        "emitter_message": emitter_message,
        "clean_emitter_accepted": clean_roundtrip.accepted,
        "naive_last_wins": {"keys": sorted(lost.keys()), "name": lost.get("name")},
        "case_sensitive_uniqueness_misses": case_sensitive_would_miss,
        "regression_seed": "FC-11309/11310 case-insensitive parser collision",
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print("FAILED:TST-0180-probe2 collision seed not detected with two signals")
        return 1
    print(
        "SUCCESS:TST-0180-probe2 validator REJECT + raw_keyset_size "
        f"{sig['worst_raw_keyset_size']} vs casefolded "
        f"{sig['worst_casefolded_keyset_size']}; emitter refused"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
