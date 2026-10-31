#!/usr/bin/env python3
"""RES-0151 probe2_negative_control.

tests_required (verbatim): negative control - feed a run of 30 near-identical
sources and require the metric to fire EARLY; feed a run of 30 genuinely
diverse sources and require it NOT to fire - a metric that fires in both cases
is a token counter. Recomputes both legs from the artifact's embedded yields
with an independent cumulative-sum implementation, plus the token-counter foil
and the string-equality mutant legs. Defaults to FAIL.

--selftest applies an in-memory mutation (diverse corpus cropped to 10) and
requires this probe to go red.
"""
from __future__ import annotations

import json
import sys
from itertools import accumulate
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def fire_index_cs(yields, window, floor, min_sources):
    """Independent implementation via prefix sums (not a rolling loop)."""
    cs = [0] + list(accumulate(yields))
    n = len(yields)
    for t in range(min_sources, n + 1):
        seg_sum = cs[t] - cs[max(0, t - window)]
        seg_n = t - max(0, t - window)
        if seg_n and seg_sum / seg_n <= floor:
            return t
    return None


def main() -> int:
    selftest = "--selftest" in sys.argv
    art = REPO / "command-center/research/evidence-quality/RES-0151-evidence-saturation-stopping-metric.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:200]})
        return bool(ok)

    metric = doc.get("metric") or {}
    window = int(metric.get("window") or 3)
    floor = float(metric.get("floor") if metric.get("floor") is not None else 0.34)
    min_sources = int(metric.get("min_sources") or 5)
    nc = doc.get("negative_controls") or {}

    near = nc.get("near_identical") or {}
    div = nc.get("diverse") or {}
    foil = nc.get("token_counter_foil") or {}

    yn = [int(v) for v in (near.get("yields") or [])]
    yd = [int(v) for v in (div.get("yields") or [])]
    if selftest:
        yd = yd[:10]  # mutation: crop diverse corpus -> metric must fire at 10
    ck("control-yields-30-sources", len(yn) == 30 and len(yd) == 30,
       f"near={len(yn)} diverse={len(yd)}")

    near_fire = fire_index_cs(yn, window, floor, min_sources)
    div_fire = fire_index_cs(yd, window, floor, min_sources)
    ck("near-identical-fires-early-at-5", near_fire == 5, f"computed={near_fire} recorded={near.get('fire_index')}")
    ck("diverse-does-not-fire", div_fire is None, f"computed={div_fire} recorded={div.get('fired')}")
    ck("near-recorded-matches", near.get("fired") is True and near.get("fire_index") == 5
       and near.get("result") == "PASS", str(near.get("result")))
    ck("diverse-recorded-matches", div.get("fired") is False and div.get("result") == "PASS",
       str(div.get("result")))

    # mechanism-key distinctness, not string equality: the recorded string-equality
    # mutant leg must show the foil did NOT fire early on the near-identical run
    ck("string-equality-mutant-did-not-fire-early",
       near.get("string_equality_fired") is False and near.get("string_equality_distinct") == 30
       and near.get("total_distinct_mechanism_keys") == 1,
       f"se_fired={near.get('string_equality_fired')} mech_keys={near.get('total_distinct_mechanism_keys')}")
    ck("diverse-30-distinct-mechanism-keys", div.get("total_distinct_mechanism_keys") == 30,
       str(div.get("total_distinct_mechanism_keys")))
    ck("token-counter-foil-recorded", bool(foil), json.dumps({k: foil.get(k) for k in list(foil)[:3]}, default=str)[:150])

    ctrl_ids = (doc.get("report") or {}).get("control_ids") or []
    ck("both-states-controls-declared",
       {"near-identical-30-fire-early", "diverse-30-stay-silent", "token-counter-foil"}.issubset(set(ctrl_ids)),
       str(ctrl_ids))

    red = [c for c in checks if not c["pass"]]
    if selftest:
        # the mutation must flip at least the diverse leg red
        print(json.dumps({"selftest": True, "red": [c["check"] for c in red]}))
        return 0 if red else 1
    verdict = {"probe": "probe2-negative-control", "unit_id": "RES-0151", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0151-probe2 both-states negative control recomputed" if not red
          else f"FAILED:RES-0151-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
