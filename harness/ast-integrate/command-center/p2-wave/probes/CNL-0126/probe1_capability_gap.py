#!/usr/bin/env python3
"""Probe 1: capability-gap fixture is LOUD and preserves the partial artifact.

Planted-bad = GAP_TOOL (and the other two closed gap types) -> DEGRADED + LOUD + bytes held.
Known-good = CAPABLE identical seat -> SUCCESS, no LOUD_DEGRADATION.
Discard mutant must fail the preservation check (detector is live).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402
import fixtures as F  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0126-cross-vendor-participant-adapter-boundary-and-loud-degrada.md"
)


def _run_gap(name: str, seat: dict, tmp: Path) -> dict:
    result = A.dispatch(F.SPEC, F.CAPABLE, seat, F.PARTIAL_WORK, tmp / name)
    loud = A.is_loud_gap(result)
    preserved = A.preservation_ok(result, F.PARTIAL_WORK)
    print(
        f"GAP {name}: verdict={result['verdict']} gaps={result['gaps']} "
        f"loud={loud} preserved={preserved} "
        f"sha256={(result.get('partial') or {}).get('sha256')}"
    )
    return {
        "name": name,
        "result": result,
        "loud": loud,
        "preserved": preserved,
        "gaps": list(result.get("gaps") or []),
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0126-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0126" not in text:
        print("FAILED:CNL-0126-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0126-probe1 self-declared {doc.get('state')}")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnl0126-p1-") as td:
        tmp = Path(td)
        capable = A.dispatch(
            F.SPEC, F.CAPABLE, F.CAPABLE, F.PARTIAL_WORK, tmp / "capable"
        )
        capable_loud = any(
            e.get("kind") == A.KIND_LOUD for e in (capable.get("audit") or [])
        )
        capable_preserved = A.preservation_ok(capable, F.PARTIAL_WORK)
        print(
            f"KNOWN-GOOD capable: verdict={capable['verdict']} "
            f"loud_degradation={capable_loud} preserved={capable_preserved} "
            f"gaps={capable.get('gaps')}"
        )
        if capable.get("verdict") != "SUCCESS" or capable_loud:
            print("FAILED:CNL-0126-probe1 known-good was not silent SUCCESS")
            return 1
        if not capable_preserved:
            print("FAILED:CNL-0126-probe1 known-good failed to keep the work bytes")
            return 1

        rows = []
        for name, seat in F.GAP_SEATS.items():
            row = _run_gap(name, seat, tmp)
            rows.append(row)
            if row["result"].get("verdict") != "DEGRADED":
                print(f"FAILED:CNL-0126-probe1 {name} was not DEGRADED")
                return 1
            if not row["loud"]:
                print(f"FAILED:CNL-0126-probe1 {name} was not LOUD")
                return 1
            if not row["preserved"]:
                print(f"FAILED:CNL-0126-probe1 {name} did not preserve partial")
                return 1
            if row["gaps"] != [name]:
                print(f"FAILED:CNL-0126-probe1 {name} gaps={row['gaps']}")
                return 1
            rec = row["result"].get("degradation") or {}
            if rec.get("interchangeability_claimed") is True:
                print(f"FAILED:CNL-0126-probe1 {name} claimed interchangeability")
                return 1
            if SPEC_MISSING := (rec.get("spec_cite") != A.SPEC_CITE):
                print(f"FAILED:CNL-0126-probe1 {name} spec cite missing {SPEC_MISSING}")
                return 1

        discard = A.mutant_discard(F.SPEC, F.GAP_TOOL)
        discard_ok = A.preservation_ok(discard, F.PARTIAL_WORK)
        print(
            f"NEGATIVE-CONTROL mutant_discard: preservation_ok={discard_ok} "
            f"verdict={discard.get('verdict')} "
            "(check FIRES on discarded partial; that is the state it rejects)"
        )
        if discard_ok:
            print("FAILED:CNL-0126-probe1 discard mutant was accepted")
            return 1

        index = A.lpi(
            [{"loud": r["loud"], "preserved": r["preserved"]} for r in rows],
            silent_sub=False,
        )
        print(f"LPI gap-fixtures={index} threshold=1.0")
        if index < 1.0:
            print("FAILED:CNL-0126-probe1 LPI below 1.0 on honest gap fixtures")
            return 1

        scores = doc.get("fixture_scores") or {}
        for name in F.GAP_SEATS:
            rec = scores.get(name) or {}
            if rec.get("gaps") != [name]:
                print(f"FAILED:CNL-0126-probe1 artifact gaps mismatch {name}={rec}")
                return 1
            if rec.get("loud") is not True or rec.get("preserved") is not True:
                print(f"FAILED:CNL-0126-probe1 artifact score not live {name}={rec}")
                return 1
            if rec.get("verdict") != "DEGRADED":
                print(f"FAILED:CNL-0126-probe1 artifact verdict {name}={rec}")
                return 1
        cap_rec = scores.get("capable") or {}
        if cap_rec.get("verdict") != "SUCCESS" or cap_rec.get("loud") is True:
            print(f"FAILED:CNL-0126-probe1 artifact capable row {cap_rec}")
            return 1

    print(
        "verbatim planted-bad: GAP tool_access DEGRADED LOUD preserved; "
        "verbatim known-good: capable SUCCESS no LOUD_DEGRADATION"
    )
    print("SUCCESS:CNL-0126-probe1 capability-gap loud preserve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
