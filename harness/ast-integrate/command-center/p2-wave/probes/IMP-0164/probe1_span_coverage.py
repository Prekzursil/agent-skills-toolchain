#!/usr/bin/env python3
"""Named probe 1 (IMP-0164): span coverage == 1.0, computed over the whole set.

Good state: every extracted stage on the control (and the two other adapter
shapes) has a resolvable source span; coverage is anchored/extracted.
Bad state: the same control with the critic span stripped; coverage < 1.0
and ok is false. Honest-null (no declared stages) is not an inferred pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def main() -> int:
    reports = S.extract_all()
    control = reports["control"]
    codex = reports["codex"]
    dag = reports["dag"]
    empty = reports["empty"]
    unanchored = reports["unanchored"]
    unmapped = reports["unmapped"]

    def coverage(rep: dict) -> float:
        return float(rep["span_coverage"])

    print(
        f"control extracted={control['extracted_count']} "
        f"anchored={control['anchored_count']} "
        f"coverage={coverage(control)}"
    )
    print(
        f"codex extracted={codex['extracted_count']} "
        f"anchored={codex['anchored_count']} coverage={coverage(codex)}"
    )
    print(
        f"dag extracted={dag['extracted_count']} "
        f"anchored={dag['anchored_count']} coverage={coverage(dag)}"
    )
    print(
        f"empty honest_null={empty['honest_null']} stages={empty['stages']!r}"
    )
    print(
        f"unanchored coverage={coverage(unanchored)} "
        f"ok={unanchored['ok']} ids={unanchored['unanchored_ids']}"
    )
    print(
        f"unmapped kind={unmapped['stages'][0]['kind'] if unmapped['stages'] else None}"
    )

    if coverage(control) != 1.0 or not control["ok"]:
        print("FAILED:IMP-0164-probe1 control span coverage is not 1.0")
        return 1
    if control["extracted_count"] != 3:
        print(f"FAILED:IMP-0164-probe1 control extracted={control['extracted_count']}")
        return 1
    if coverage(codex) != 1.0 or not codex["ok"]:
        print("FAILED:IMP-0164-probe1 codex span coverage is not 1.0")
        return 1
    if coverage(dag) != 1.0 or not dag["ok"]:
        print("FAILED:IMP-0164-probe1 dag span coverage is not 1.0")
        return 1
    if not empty["honest_null"] or empty["stages"] is not None:
        print("FAILED:IMP-0164-probe1 empty source inferred stages (want HONEST-NULL)")
        return 1
    if unanchored["ok"] or coverage(unanchored) >= 1.0:
        print("FAILED:IMP-0164-probe1 unanchored plant did not drop coverage")
        return 1
    if "critic" not in unanchored["unanchored_ids"]:
        print("FAILED:IMP-0164-probe1 critic was not the unanchored id")
        return 1
    if unmapped["stages"][0]["kind"] != "UNKNOWN":
        print("FAILED:IMP-0164-probe1 unmapped native kind was snapped, not UNKNOWN")
        return 1

    # Coverage is a ratio, not a hardcoded 1. Mutating the plant must change it.
    expected_plant = unanchored["anchored_count"] / unanchored["extracted_count"]
    if unanchored["span_coverage"] != expected_plant:
        print("FAILED:IMP-0164-probe1 coverage was not computed as anchored/extracted")
        return 1
    if expected_plant != 2 / 3:
        print(f"FAILED:IMP-0164-probe1 planted coverage {expected_plant} want 2/3")
        return 1

    doc = {
        "probe": "probe1-span-coverage",
        "unit_id": "IMP-0164",
        "pass": True,
        "computed_not_sampled": True,
        "control_coverage": coverage(control),
        "codex_coverage": coverage(codex),
        "dag_coverage": coverage(dag),
        "planted_coverage": coverage(unanchored),
        "planted_formula": expected_plant,
        "honest_null": empty["honest_null"],
        "unmapped_kind": unmapped["stages"][0]["kind"],
        "both_states": True,
        "fired_on_bad_state": (not unanchored["ok"]) and coverage(unanchored) < 1.0,
        "silent_on_good_state": control["ok"] and coverage(control) == 1.0,
    }
    (HERE / "probe1-span-coverage.raw.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "SUCCESS:IMP-0164-probe1 span coverage == 1.0 computed; "
        "unanchored plant coverage=2/3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
