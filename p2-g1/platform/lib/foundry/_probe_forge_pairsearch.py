"""Search the real blueprint corpus for pairs the forge CERTIFIES and pairs it REJECTS.

This is the forge's own both-states control. A gate that only ever rejects is as useless as one
that only ever accepts, so this probe measures BOTH populations over real inputs and reports the
counts plus one worked example of each. It calls the shipped ``fuse_and_certify`` - no separate
scoring path, so a pass here is a pass of the real gate.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foundry import bench, forge, registry  # noqa: E402


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 26
    strategy = sys.argv[2] if len(sys.argv) > 2 else "best-of-breed"
    cands = [c for c in registry.load_dsl_candidates() if c.dsl_doc]
    cands.sort(key=lambda c: c.id)
    cands = cands[:limit]
    cases = list(bench.DEFAULT_CASES)

    verdicts: Counter = Counter()
    certified: list[dict] = []
    rejected_reasons: Counter = Counter()
    stage_only_rejections: list[dict] = []
    errors: list[str] = []

    for i, a in enumerate(cands):
        for b in cands[i + 1 :]:
            try:
                out = forge.fuse_and_certify(
                    a.dsl_doc, b.dsl_doc, strategy=strategy, cases=cases
                )
            except Exception as exc:  # noqa: BLE001 - a crash is a finding, not a pass
                errors.append(f"{a.id} + {b.id}: {type(exc).__name__}: {exc}")
                continue
            cert = out["certification"]
            verdicts[cert["verdict"]] += 1
            if cert["accepted"]:
                certified.append(
                    {
                        "base": out["base"],
                        "donor": out["donor"],
                        "improvements": cert["axis_improvements_over_best_source"],
                        "cost_delta_stage_count": cert["cost_delta_vs_largest_source"][
                            "stage_count"
                        ],
                        "roundtrip": out["decomposition"]["roundtrip"]["verdict"],
                    }
                )
            else:
                for r in cert["reasons"]:
                    rejected_reasons[r.split(":")[0].split(" on ")[0][:60]] += 1
                if (
                    any("no-axis-improved" in r for r in cert["reasons"])
                    and cert["cost_delta_vs_largest_source"]["stage_count"] > 0
                ):
                    stage_only_rejections.append(
                        {
                            "base": out["base"],
                            "donor": out["donor"],
                            "extra_stages": cert["cost_delta_vs_largest_source"][
                                "stage_count"
                            ],
                        }
                    )

    certified.sort(
        key=lambda r: (-sum(r["improvements"].values()), r["base"], r["donor"])
    )
    out = {
        "strategy": strategy,
        "candidates_considered": len(cands),
        "pairs_evaluated": sum(verdicts.values()),
        "verdicts": dict(verdicts),
        "crashes": errors[:5],
        "crash_count": len(errors),
        "certified_count": len(certified),
        "best_certified": certified[:5],
        "rejection_reason_histogram": dict(rejected_reasons.most_common(10)),
        "bigger_but_no_better_rejections": len(stage_only_rejections),
        "bigger_but_no_better_examples": stage_only_rejections[:5],
        "both_states_control": {
            "gate_can_accept": bool(certified),
            "gate_can_reject": verdicts.get("REJECTED", 0) > 0,
            "verdict": (
                "PASS - the gate fires in both directions over real inputs"
                if certified and verdicts.get("REJECTED", 0) > 0
                else "FAIL - a gate that only ever returns one verdict measures nothing"
            ),
        },
    }
    print(json.dumps(out, indent=2))
    ok = bool(certified) and verdicts.get("REJECTED", 0) > 0 and not errors
    print(f"{'SUCCESS' if ok else 'FAILED'}:forge-pairsearch")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
