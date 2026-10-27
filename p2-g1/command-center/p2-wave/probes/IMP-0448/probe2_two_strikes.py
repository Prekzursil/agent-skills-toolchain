"""Two-strikes pivot + text-blindness controls (IMP-0448)."""
from __future__ import annotations

import ast
import json
import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import retry_engine as re  # noqa: E402


def main() -> int:
    policy = re.parse_retry_policy("max 3 attempts, backoff 30s/120s; "
                                   "two strikes then pivot")
    fp = "transient-fp-same"

    # same fingerprint: PIVOT fires at strike two, never a third attempt
    d2 = re.decide([re.TypedFailure("severed-stream", fp),
                    re.TypedFailure("severed-stream", fp)], policy)
    assert d2.action == "PIVOT" and d2.reason == re.REASON_PIVOT, d2
    assert d2.required_fix == re.PIVOT_REQUIRED_FIX, d2.required_fix

    # distinct fingerprints reach the cap with plain RETRY until n == cap
    seq = [re.TypedFailure("severed-stream", "fp-%d" % i) for i in range(3)]
    d3 = re.decide(seq, policy)
    assert d3.action == "STOP" and d3.reason == re.REASON_CAP, d3

    # same fingerprint thrice: still PIVOT at strike two (decide sees >= 2)
    d4 = re.decide([re.TypedFailure("severed-stream", fp),
                    re.TypedFailure("severed-stream", fp),
                    re.TypedFailure("severed-stream", fp)], policy)
    assert d4.action == "PIVOT" and d4.same_fingerprint_count >= 2, d4

    # text-mutant control: identical decoy TEXT, different CLASS diverges
    decoy = re.class_overrides_decoy_text()
    assert decoy["diverged"] is True, decoy

    # AST control: decide() never reads raw message/text fields
    tree = ast.parse(inspect.getsource(re.decide))
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not (names & {"message", "text", "raw", "stderr"}), names

    print(json.dumps({
        "probe": "probe2-two-strikes",
        "unit_id": "IMP-0448",
        "pivot_at_strike_two": True,
        "pivot_required_fix": d2.required_fix,
        "distinct_fingerprints_reach_cap": d3.reason,
        "thrice_same_still_pivot": d4.same_fingerprint_count >= 2,
        "class_overrides_decoy_text": True,
        "decide_ast_has_no_text_fields": True,
        "sentinel": "SENTINEL:IMP-0448:RETRY-CLASS-DRIVEN",
    }, indent=2))
    print("SUCCESS:IMP-0448-probe2 PIVOT at strike two; class overrides decoy text")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
