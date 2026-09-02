#!/usr/bin/env python3
"""Named probe 2: independent e2e trace + named bypass attempts (evidence B).

Does not import campaign.py. Walks unmutated hop outputs, then plants
empty-string, whitespace, missing-key, and side-channel-list bypasses at
certification. Mention-in-notes must stay silent.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from carry import ANCHOR_KEY, HOPS, LICENCE_KEY, SEED_A  # noqa: E402
from gates import inspect  # noqa: E402
from pipeline import run_to  # noqa: E402
from trace import walk_unmutated  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0122-probe2 {msg}")
    return 1


def main() -> int:
    walked = walk_unmutated()
    print(
        json.dumps(
            {
                "case": "unmutated-e2e",
                "intact": walked["intact"],
                "uncovered_hops": walked["uncovered_hops"],
                "final_anchor": walked["final_anchor"],
                "final_licence_class": walked["final_licence_class"],
                "final_source_anchors": walked["final_source_anchors"],
                "final_licence_lineage": walked["final_licence_lineage"],
            },
            sort_keys=True,
        )
    )
    if not walked["intact"]:
        return _fail(f"unmutated path uncovered hops={walked['uncovered_hops']}")
    if walked["final_kind"] != "certified-workflow":
        return _fail(f"final kind {walked['final_kind']}")
    if SEED_A[ANCHOR_KEY] not in walked["final_source_anchors"]:
        return _fail("seed A provenance_anchor missing from final source_anchors")
    if walked["final_licence_class"] != "GPL-3.0":
        return _fail(
            f"final licence_class={walked['final_licence_class']!r} "
            "(most-restrictive-wins should be GPL-3.0)"
        )
    fired_on_clean = [r for r in walked["hops"] if r["gate_fired"]]
    if fired_on_clean:
        return _fail(f"gate fired on unmutated path: {fired_on_clean}")
    if [r["hop"] for r in walked["hops"]] != list(HOPS):
        return _fail("e2e hop list does not match catalog hops")

    cert = run_to("certification")
    mention = inspect("certification", cert)
    if mention["fired"]:
        return _fail("notes mention of empty licence_class tripped the gate")

    bypasses = []
    # empty-string ≡ missing
    empty = copy.deepcopy(cert)
    empty[ANCHOR_KEY] = ""
    v_empty = inspect("certification", empty)
    bypasses.append(("empty-string-anchor", v_empty["fired"], v_empty["gate_id"]))
    if not v_empty["fired"] or ANCHOR_KEY not in v_empty["lost_fields"]:
        return _fail("empty-string anchor bypass survived")

    missing = copy.deepcopy(cert)
    missing.pop(ANCHOR_KEY, None)
    v_missing = inspect("certification", missing)
    bypasses.append(("missing-anchor", v_missing["fired"], v_missing["gate_id"]))
    if not v_missing["fired"]:
        return _fail("missing-key anchor bypass survived")
    if v_empty["gate_id"] != v_missing["gate_id"]:
        return _fail("empty-string and missing fired different gates")

    # whitespace-only is the naive `if not value` bypass
    ws = copy.deepcopy(cert)
    ws[ANCHOR_KEY] = "   "
    v_ws = inspect("certification", ws)
    bypasses.append(("whitespace-anchor", v_ws["fired"], v_ws["gate_id"]))
    if not v_ws["fired"]:
        return _fail("whitespace-only anchor bypass survived")

    empty_lic = copy.deepcopy(cert)
    empty_lic[LICENCE_KEY] = ""
    v_lic = inspect("certification", empty_lic)
    bypasses.append(("empty-string-licence", v_lic["fired"], v_lic["gate_id"]))
    if not v_lic["fired"] or LICENCE_KEY not in v_lic["lost_fields"]:
        return _fail("empty-string licence bypass survived")

    # side-channel list must not substitute for a lost primary field
    side = copy.deepcopy(cert)
    side.pop(ANCHOR_KEY, None)
    side["source_anchors"] = [SEED_A[ANCHOR_KEY]]
    v_side = inspect("certification", side)
    bypasses.append(("side-channel-source_anchors", v_side["fired"], v_side["gate_id"]))
    if not v_side["fired"]:
        return _fail("source_anchors side-channel bypass survived")

    print(json.dumps({"bypasses": bypasses, "all_caught": True}, sort_keys=True))
    print("SUCCESS:WFA-0122-probe2 e2e intact and named bypasses caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
