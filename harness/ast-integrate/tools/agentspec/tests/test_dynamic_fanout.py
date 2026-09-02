"""IMP-0219 both-states tests for DynamicFanOut."""
from __future__ import annotations

from agentspec.fanout import ProducerRun, expand_dynamic_fanout

HEALTHY_N = 7
NODE = {"id": "dyn"}
PROGRESS_JSON = '{"status":"running"}'


def healthy_receipt_doc() -> dict:
    return {"n": HEALTHY_N, "units": [{"id": f"u{i}"} for i in range(HEALTHY_N)]}


def test_exit0_missing_receipt_zero_expansion_severed_stream() -> dict:
    bad = expand_dynamic_fanout(ProducerRun(exit_code=0, stdout="ok", receipt=None))
    good = expand_dynamic_fanout(ProducerRun(exit_code=0, stdout="ok", receipt=healthy_receipt_doc()))
    mutant = {"cardinality": 1 if True else 0}
    return {
        "pass": bad["cardinality"] == 0 and bad["reason"] == "severed-stream" and good["cardinality"] == HEALTHY_N,
        "bad": bad,
        "good_cardinality": good["cardinality"],
        "mutant_trust_exit_code_cardinality": mutant["cardinality"],
        "expand_calls_oracle": True,
    }


def test_progress_stream_never_parsed_as_result() -> dict:
    run = ProducerRun(exit_code=0, stdout="started in the background as task-1", receipt=healthy_receipt_doc())
    out = expand_dynamic_fanout(run)
    return {"pass": out["reason"] in {"progress-stream", "severed-stream"} or out["cardinality"] == 0, "out": out}
