#!/usr/bin/env python3
"""Probe 2: title-token similarity; UNRESOLVED when no discriminating token."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:{E.UNIT}-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    planted = E.fixture_corpus()
    p2 = E.probe2_similarity(planted)
    ctrl = E.control_probe2(p2)
    if not ctrl["planted_ambiguous_unresolved"]:
        return fail("planted ambiguous reference was not UNRESOLVED", ctrl)
    if not ctrl["planted_unambiguous_one_binding"]:
        return fail("planted unambiguous reference did not bind uniquely", ctrl)
    if not ctrl["pass"]:
        return fail("title-similarity control failed", ctrl)
    payload = {
        "pass": True,
        "probe": "probe2-title-similarity",
        "unit_id": E.UNIT,
        "instrument": p2["instrument"],
        "independent": True,
        "reviewer_id": "ADV-0007-probe2-title-similarity",
        "unresolved_count": p2["unresolved_count"],
        "bound_count": p2["bound_count"],
        "control": {
            "id": ctrl["id"],
            "pass": True,
            "planted_ambiguous_unresolved": True,
            "planted_unambiguous_one_binding": True,
            "discriminating_fx16_bound": ctrl["discriminating_fx16_bound"],
            "ambiguous_refs": ctrl["ambiguous_refs"],
            "unambiguous_refs": ctrl["unambiguous_refs"],
        },
        "resolutions": p2["resolutions"],
    }
    print(json.dumps(payload, sort_keys=True))
    bound_paths = [
        (r.get("bound_to") or {}).get("path") for r in ctrl["unambiguous_refs"]
    ]
    print(
        f"unresolved={p2['unresolved_count']} bound={p2['bound_count']} "
        f"unambiguous_bound_to={bound_paths}"
    )
    print(
        f"SUCCESS:{E.UNIT}-probe2 title-similarity: planted ambiguous "
        f"{E.AMBIGUOUS_ID} UNRESOLVED; planted {E.UNAMBIGUOUS_ID} one binding"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
