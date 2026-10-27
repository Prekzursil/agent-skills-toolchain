"""IMP-0219 probe 1: exit-0 with a missing producer receipt expands to ZERO + severed-stream.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0219/probe1_exit0_missing_receipt.py
Both-states: the healthy twin receipt expands to 7; a mutant trusting exit_code==0 alone
would expand to 1. Production must call the oracle and gate on it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))

from agentspec.fanout import ProducerRun, expand_dynamic_fanout  # noqa: E402


def mutant_trust_exit_code(run: ProducerRun) -> dict:
    """Defect twin: exit 0 alone expands. The detector must discriminate."""
    if run.exit_code == 0:
        return {"cardinality": 1, "reason": "trusted-exit-zero", "units": ["u0"]}
    return {"cardinality": 0, "reason": "failed", "units": []}


def main() -> int:
    bad = expand_dynamic_fanout(ProducerRun(exit_code=0, stdout="ok", receipt=None))
    good = expand_dynamic_fanout(
        ProducerRun(
            exit_code=0,
            stdout="ok",
            receipt={"n": 7, "units": [{"id": "u%d" % i} for i in range(7)]},
        )
    )
    mutant = mutant_trust_exit_code(
        ProducerRun(exit_code=0, stdout="ok", receipt=None)
    )
    oracle_obj = bad.get("oracle") or {}
    doc = {
        "unit_id": "IMP-0219",
        "probe": "probe1-exit0-missing-receipt",
        "bad": {
            "cardinality": bad["cardinality"],
            "reason": bad["reason"],
            "fine_reason": bad.get("fine_reason"),
            "oracle_ok": oracle_obj.get("ok"),
            "oracle_reason": oracle_obj.get("reason"),
        },
        "good_cardinality": good["cardinality"],
        "good_reason": good["reason"],
        "expand_calls_oracle": "oracle" in bad,
        "mutant_trusts_exit_0": mutant["cardinality"] == 1,
        "mutant_trust_exit_code_cardinality": mutant["cardinality"],
    }
    doc["pass"] = (
        bad["cardinality"] == 0
        and bad["reason"] == "severed-stream"
        and good["cardinality"] == 7
        and "oracle" in bad
        and mutant["cardinality"] == 1
        and oracle_obj.get("ok") is False
    )
    out = Path(__file__).resolve().parent / "probe1-exit0-missing.raw.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if doc["pass"]:
        print("SUCCESS:IMP-0219-probe1 exit-0 missing receipt expands to zero +"
              " severed-stream")
        return 0
    print("FAILED:IMP-0219-probe1 both-states control failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
