#!/usr/bin/env python3
"""Probe 1: each UNVERIFIED/residual flag plus adjacent sentence and experiment."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

UNIT = "AUD-0073"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, sort_keys=True, default=str)[:4000])
    return 1


def main() -> int:
    doc = E.scan()
    flags = doc["flags"]
    missing_adj = [
        f["id"] for f in flags if not str(f.get("adjacent_sentence") or "").strip()
    ]
    missing_exp = []
    for f in flags:
        exp = f.get("experiment") or {}
        if not (
            str(exp.get("command") or "").strip()
            and str(exp.get("expected_observation") or "").strip()
            and str(exp.get("discriminating_outcome") or "").strip()
        ):
            missing_exp.append(f["id"])
    generated = [
        f["id"]
        for f in flags
        if (f.get("experiment") or {}).get("kind") == "minimal-generated"
        and not f.get("has_named_runnable_experiment")
    ]
    payload = {
        "probe": "probe1-unverified-and-experiments",
        "unit_id": UNIT,
        "n_flags": doc["n_flags"],
        "n_with_named_runnable_experiment": doc["n_with_named_runnable_experiment"],
        "n_without_named_runnable_experiment": doc[
            "n_without_named_runnable_experiment"
        ],
        "n_minimal_generated": len(generated),
        "upstream_aud_0068_present": doc["upstream_aud_0068"]["present"],
        "control_inline": len(doc["controls"]["inline"]),
        "control_trailing": len(doc["controls"]["trailing"]),
        "missing_adjacent": missing_adj[:8],
        "missing_experiment": missing_exp[:8],
        "kinds": {},
    }
    kinds: dict[str, int] = {}
    for f in flags:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    payload["kinds"] = kinds
    print(json.dumps(payload, indent=1, sort_keys=True))
    if doc["n_flags"] < 2:
        return fail("extracted fewer than 2 flags; meter is dark", payload)
    if missing_adj:
        return fail("flag missing adjacent sentence", payload)
    if missing_exp:
        return fail("flag missing named or minimal experiment", payload)
    if not doc["controls"]["inline"] or not doc["controls"]["trailing"]:
        return fail("planted inline/trailing controls not extracted", payload)
    if doc["upstream_aud_0068"]["present"]:
        # Live tree currently lacks AUD-0068; if it appears, still fine.
        pass
    else:
        # Honest: we must not pretend canonical records exist.
        if doc["n_flags"] < 1:
            return fail("AUD-0068 absent and live scan found nothing", payload)
    if len(generated) != doc["n_without_named_runnable_experiment"]:
        return fail(
            "every flag without a runnable named experiment must get a minimal one",
            payload,
        )
    print(
        f"extracted={doc['n_flags']} named={doc['n_with_named_runnable_experiment']} "
        f"generated={len(generated)} aud0068={doc['upstream_aud_0068']['present']}"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 each UNVERIFIED/residual has adjacent sentence "
        "and a named or minimal experiment"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
