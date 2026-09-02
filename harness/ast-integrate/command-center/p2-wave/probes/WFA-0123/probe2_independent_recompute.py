#!/usr/bin/env python3
"""Probe 2: independent recompute from the stopping-condition text.

Imports qualify_b only (must not import qualify_a). Re-derives live and
planted counts and matches the artifact. Both-states: stripping the
fetched licence from a survivor must drop the qualified count.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import planted as P  # noqa: E402
import qualify_b as B  # noqa: E402

if "qualify_a" in sys.modules:
    print("FAILED:WFA-0123-probe2 imported qualify_a")
    raise SystemExit(1)

ART = REPO / "command-center/wfa/WFA-0123-candidate-floor-proof.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0123-probe2 {msg}")
    return 1


def main() -> int:
    P.assert_fixture_files(REPO)
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")

    live = C.load_live_registry(REPO)
    live_b = B.evaluate(live["records"], REPO)
    if live_b["qualified_count"] != int(doc["qualified_count"]):
        return fail(
            f"live qualified {live_b['qualified_count']} != artifact {doc['qualified_count']}"
        )
    if live_b["raw_count"] != int(doc["raw_count"]):
        return fail(f"live raw {live_b['raw_count']} != artifact {doc['raw_count']}")

    planted = P.planted_records()
    plant_b = B.evaluate(planted, REPO)
    rec_plant = (doc.get("both_states") or {}).get("planted_qualified")
    if plant_b["qualified_count"] != 2 or rec_plant != 2:
        return fail(
            f"planted qualified {plant_b['qualified_count']} artifact {rec_plant}"
        )
    ids = sorted(x["id"] for x in plant_b["qualified"])
    if ids != ["planted-alpha", "planted-beta"]:
        return fail(f"planted ids {ids}")

    stripped = copy.deepcopy(planted)
    for rec in stripped:
        if rec["id"] == "planted-alpha":
            rec["license_file"] = ""
            rec["provenance"] = (
                "command-center/p2-wave/probes/WFA-0123/fixtures/no-lic/SKILL.md"
            )
    dropped = B.evaluate(stripped, REPO)
    if dropped["qualified_count"] != 1:
        return fail(
            f"licence-strip both-states qualified={dropped['qualified_count']} want 1"
        )
    restored = B.evaluate(planted, REPO)
    if restored["qualified_count"] != 2:
        return fail("restored planted did not return to 2")

    if "qualify_a" in sys.modules:
        return fail("qualify_a leaked into this process")

    payload = {
        "probe": "probe2-independent-recompute",
        "unit_id": "WFA-0123",
        "live_qualified": live_b["qualified_count"],
        "artifact_qualified": doc["qualified_count"],
        "planted_qualified": plant_b["qualified_count"],
        "licence_strip_qualified": dropped["qualified_count"],
        "imported_qualify_a": False,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"live_q={live_b['qualified_count']} planted_q={plant_b['qualified_count']} "
        f"strip_q={dropped['qualified_count']}"
    )
    print(
        "SUCCESS:WFA-0123-probe2 independent recompute matches artifact; "
        "licence strip drops count"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
