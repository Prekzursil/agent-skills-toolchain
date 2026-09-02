#!/usr/bin/env python3
"""Named probe 2: without-dissenter fabrication control + synthesis differential.

Mechanically different from probe 1: sha256 inequality of the two synthesis
texts, plus a fabrication detector on the no-dissenter run. Does not score
verbatim substring location.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import fabrication_verdict, syntheses_differ  # noqa: E402
from fixtures import INJECTED_POSITION  # noqa: E402
from synthesis import with_dissenter, without_dissenter  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0088-dissent-survival.json"
UNIT = "CNF-0088"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live_without = without_dissenter("preserve")
    live_with = with_dissenter("preserve")
    if not live_without.get("completed") or not live_with.get("completed"):
        return fail("a live run did not complete")

    fab = fabrication_verdict(live_without)
    if not fab["pass"]:
        return fail("without-dissenter fabricated a minority report", fab)
    if INJECTED_POSITION in live_without["synthesis_text"]:
        return fail("injected position leaked into the no-dissenter run")
    if "## Minority report" in live_without["synthesis_text"]:
        return fail("minority report heading fabricated")

    diff = syntheses_differ(live_with, live_without)
    if not diff["runs_differ"] or not diff["recommendations_differ"]:
        return fail("syntheses did not differ as designed", diff)

    planted = fabrication_verdict(without_dissenter("fabricate"))
    if planted["pass"] or not planted["fabricated"]:
        return fail("fabricate control silent", planted)
    if planted.get("classification") != "fabricated-dissent":
        return fail("fabricate not classified", planted)

    runs = {r.get("id"): r for r in (doc.get("runs") or []) if isinstance(r, dict)}
    art_with = runs.get("with-dissenter")
    art_without = runs.get("without-dissenter")
    if not art_with or not art_without:
        return fail("artifact missing a required run")
    if not art_with.get("completed") or not art_without.get("completed"):
        return fail("artifact run not completed")
    if art_with.get("synthesis_text") != live_with["synthesis_text"]:
        return fail("artifact with-dissenter != live")
    if art_without.get("synthesis_text") != live_without["synthesis_text"]:
        return fail("artifact without-dissenter != live")

    cmp_ = doc.get("comparison") or {}
    if cmp_.get("runs_differ") is not True:
        return fail("artifact comparison.runs_differ is not true")
    if cmp_.get("with_sha256") != diff["with_sha256"]:
        return fail("artifact with_sha256 mismatch")
    if cmp_.get("without_sha256") != diff["without_sha256"]:
        return fail("artifact without_sha256 mismatch")
    if cmp_.get("with_sha256") == cmp_.get("without_sha256"):
        return fail("sha256s collided")

    out = {
        "probe": "probe2-without-dissenter",
        "unit_id": UNIT,
        "pass": True,
        "without_completed": True,
        "with_completed": True,
        "fabricated_minority_report": False,
        "runs_differ": True,
        "recommendations_differ": True,
        "with_sha256": diff["with_sha256"],
        "without_sha256": diff["without_sha256"],
        "fabricate_control_fired": True,
        "artifact_matches_live": True,
    }
    (HERE / "probe2-without-dissenter.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0088-probe2 without-dissenter control and differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
