#!/usr/bin/env python3
"""Probe 1: unresolvable forecast REJECTED; resolvable twin ADMITTED (both-states).

The two twins share the same statement. A gate that consulted prose would
not discriminate. Rejected candidates must not enter ForecastLibrary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

import fixtures as F  # noqa: E402
from analysis.forecast_gate import (  # noqa: E402
    ADMIT_RESOLVABLE,
    REJECT_MISSING_CRITERION,
    REJECT_MISSING_RESOLUTION_DATE,
    REJECT_PROSE_CRITERION,
    REJECT_UNBOUNDED_HORIZON,
    ForecastLibrary,
    emission_fingerprint,
    emit,
)
from analysis.library import build_library  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0253.json"
UNIT = "IMP-0253"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    lib = ForecastLibrary()
    d_bad = lib.try_admit(F.UNRESOLVABLE_NO_DATE)
    d_good = lib.try_admit(F.RESOLVABLE)
    d_prose = emit(F.UNRESOLVABLE_PROSE)
    d_never = emit(F.UNRESOLVABLE_UNBOUNDED)
    d_nocrit = emit(F.UNRESOLVABLE_NO_CRIT)
    d_swap = emit(F.PROSE_STATEMENT_SWAP)

    print(
        json.dumps(
            {
                "unresolvable_no_date": d_bad.to_dict(),
                "resolvable": d_good.to_dict(),
                "prose_criterion": d_prose.to_dict(),
                "unbounded": d_never.to_dict(),
                "missing_criterion": d_nocrit.to_dict(),
                "library_ids": list(lib.admitted_ids()),
            },
            sort_keys=True,
        )
    )

    if d_bad.admitted:
        return fail("unresolvable (no date) was admitted")
    if d_bad.reason != REJECT_MISSING_RESOLUTION_DATE:
        return fail(f"no-date reason={d_bad.reason}")
    if d_bad.executable:
        return fail("unresolvable marked executable")
    if d_bad.statement_consulted:
        return fail("gate consulted statement on reject")
    if lib.contains(F.UNRESOLVABLE_NO_DATE.forecast_id):
        return fail("rejected forecast entered the library")

    if not d_good.admitted:
        return fail("resolvable forecast was rejected")
    if d_good.reason != ADMIT_RESOLVABLE:
        return fail(f"resolvable reason={d_good.reason}")
    if not d_good.executable:
        return fail("resolvable not marked executable")
    if d_good.resolution_date != "2027-03-01":
        return fail(f"resolution_date={d_good.resolution_date}")
    if not lib.contains(F.RESOLVABLE.forecast_id):
        return fail("admitted forecast missing from library")
    if d_good.statement_consulted:
        return fail("gate consulted statement on admit")

    if emission_fingerprint(d_swap) != emission_fingerprint(d_good):
        return fail("statement swap mutated the admission fingerprint")

    if d_prose.admitted:
        return fail("prose criterion was admitted")
    if d_prose.reason != REJECT_PROSE_CRITERION:
        return fail(f"prose reason={d_prose.reason}")
    if d_never.admitted or d_never.reason != REJECT_UNBOUNDED_HORIZON:
        return fail(f"unbounded reason={d_never.reason} admitted={d_never.admitted}")
    if d_nocrit.admitted or d_nocrit.reason != REJECT_MISSING_CRITERION:
        return fail(f"no-crit reason={d_nocrit.reason} admitted={d_nocrit.admitted}")

    alib, rows = build_library()
    if alib.ids() != (
        "bp.morphological-analysis",
        "bp.simulation-counterfactual",
        "bp.forecasting",
        "bp.expert-elicitation",
    ):
        return fail(f"library ids={alib.ids()}")
    if any(not r.get("ok") for r in rows):
        return fail(f"blueprint contract failed {rows}")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0253" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    recorded = (doc.get("forecast_gate") or {}).get("unresolvable_no_date") or {}
    if recorded.get("reason") != REJECT_MISSING_RESOLUTION_DATE:
        return fail("receipt did not record no-date reject")
    if recorded.get("admitted") is not False:
        return fail("receipt did not record unresolvable admitted=false")
    rec_good = (doc.get("forecast_gate") or {}).get("resolvable") or {}
    if rec_good.get("admitted") is not True:
        return fail("receipt did not record resolvable admit")
    if rec_good.get("reason") != ADMIT_RESOLVABLE:
        return fail("receipt resolvable reason drift")

    print(
        "unresolvable_rejected=True resolvable_admitted=True "
        f"library={list(lib.admitted_ids())} prose_rejected=True"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 unresolvable rejected; resolvable admitted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
