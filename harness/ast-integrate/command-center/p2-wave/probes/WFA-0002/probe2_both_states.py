#!/usr/bin/env python3
"""Probe 2: both-states — re-inject one known-bad ref and the closure checker fails.

Mechanically independent of probe1: does not import probe1, does not read
probe1 return codes. Recomputes closure from fixtures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from closure import (  # noqa: E402
    KNOWN_BAD_REINJECT,
    apply_fix,
    check_closure,
    classify_all,
    re_inject_known_bad,
)
from estate import evidence_b, load_head_index, pair_ab, scan_filesystem  # noqa: E402
from fixtures import ESTATE, HEAD_INDEX_PATH, materialize  # noqa: E402

UNIT = "WFA-0002"
ART = REPO / "command-center" / "wfa" / "WFA-0002-provenance-closure.json"
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    planted = materialize()
    refs = planted["refs"]
    graph = planted["graph"]
    registry = planted["registry"]
    hits_a = scan_filesystem([ESTATE])
    hits_b = evidence_b(refs, load_head_index(HEAD_INDEX_PATH), repo=None)
    rows = pair_ab(refs, hits_a, hits_b)
    classifications = classify_all(rows)
    fixed = apply_fix(graph, registry, classifications)
    good = check_closure(fixed["graph"], fixed["registry"])

    if good["provenance_edges_unresolved"] != 0 or good["provenance_resolution_rate"] != 1.0:
        return fail(f"good-state-not-closed {good}")

    bad_graph = re_inject_known_bad(fixed["graph"], KNOWN_BAD_REINJECT)
    bad = check_closure(bad_graph, fixed["registry"])
    if bad["provenance_edges_unresolved"] < 1:
        return fail("re-inject-did-not-open-an-unresolved-edge")
    if bad["provenance_resolution_rate"] >= 1.0:
        return fail("re-inject-still-rate-1")
    if KNOWN_BAD_REINJECT not in bad["unresolved_refs"]:
        return fail(f"known-bad-missing {bad['unresolved_refs']}")
    if good["provenance_edges_unresolved"] >= bad["provenance_edges_unresolved"]:
        return fail("bad-state-must-have-more-unresolved-than-good")

    # Honest checker is silent on the closed graph and fires on the reinject.
    both = {
        "good_silent": good["rate_is_one"] is True,
        "bad_fires": bad["rate_is_one"] is False,
        "reinject_ref": KNOWN_BAD_REINJECT,
        "good_unresolved": good["provenance_edges_unresolved"],
        "bad_unresolved": bad["provenance_edges_unresolved"],
        "independent_of_probe1": True,
    }
    if not (both["good_silent"] and both["bad_fires"]):
        return fail(f"both-states {both}")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in BLOCKED:
            return fail(f"self-declared:{st}")
        if "SUCCESS:WFA-0002" not in text:
            return fail("sentinel-absent")
        recorded = doc.get("negative_controls") or []
        ids = {c.get("id") for c in recorded if isinstance(c, dict)}
        if "re-inject-known-bad-ref" not in ids:
            return fail("artifact-missing-reinject-control")

    payload = {
        "ok": True,
        "probe": "probe2-both-states",
        "unit_id": UNIT,
        "both_states": both,
        "independent_of_recomposition": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "good_silent=True bad_fires=True "
        f"good_unresolved={good['provenance_edges_unresolved']} "
        f"bad_unresolved={bad['provenance_edges_unresolved']}"
    )
    print(
        "SUCCESS:WFA-0002-probe2 both-states: closed graph silent; "
        "re-injected known-bad ref fails the closure checker"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
