"""IMP-0219 both-states tests for DynamicFanOut.

Each test returns a dict a probe prints and asserts on. The MUTANTS are real
alternative expanders written here, so every test measures discrimination
between the production oracle-gated path and a known-bad shortcut rather than
asserting a constant.
"""
from __future__ import annotations

import json
from typing import Any

from agentspec.fanout import ProducerRun, expand_dynamic_fanout
from agentspec.oracle import TAXONOMY_SEVERED_STREAM

HEALTHY_N = 7
PROGRESS_N = 5
NODE = {"id": "dyn"}
PROGRESS_TEXT = "started in the background as task-1"


def healthy_receipt_doc() -> dict:
    return {"n": HEALTHY_N, "units": [{"id": f"u{i}"} for i in range(HEALTHY_N)]}


def progress_stream_doc() -> dict:
    """A progress payload that happens to be valid JSON and to carry a unit list."""
    return {
        "kind": "PROGRESS",
        "state": "RUNNING",
        "status": PROGRESS_TEXT,
        "n": PROGRESS_N,
        "units": [{"id": f"p{i}"} for i in range(PROGRESS_N)],
    }


def mutant_trust_exit_code(run: ProducerRun) -> dict[str, Any]:
    """Known-bad expander: exit 0 IS success; a producer with no receipt still counts as one unit."""
    if run.exit_code != 0:
        return {"cardinality": 0, "units": []}
    units = list((run.receipt or {}).get("units") or [])
    if not units:
        units = [{"id": "producer-exit-0"}]
    return {"cardinality": len(units), "units": units}


def mutant_parse_progress_as_result(run: ProducerRun) -> dict[str, Any]:
    """Known-bad expander: JSON-load whatever the producer printed and count its units."""
    try:
        doc = json.loads(run.stdout or "")
    except ValueError:
        doc = None
    units = list(doc.get("units") or []) if isinstance(doc, dict) else []
    return {"cardinality": len(units), "units": units}


def test_exit0_missing_receipt_zero_expansion_severed_stream() -> dict:
    bad_run = ProducerRun(exit_code=0, stdout="ok", receipt=None)
    good_run = ProducerRun(exit_code=0, stdout="ok", receipt=healthy_receipt_doc())
    bad = expand_dynamic_fanout(bad_run, node=NODE)
    good = expand_dynamic_fanout(good_run, node=NODE)
    mutant = mutant_trust_exit_code(bad_run)
    expand_calls_oracle = (
        isinstance(bad.get("oracle"), dict)
        and bad["oracle"].get("ok") is False
        and bad["oracle"].get("reason") == TAXONOMY_SEVERED_STREAM
        and isinstance(good.get("oracle"), dict)
        and good["oracle"].get("ok") is True
    )
    ok = (
        bad["cardinality"] == 0
        and bad["reason"] == TAXONOMY_SEVERED_STREAM
        and bad.get("taxonomy") == TAXONOMY_SEVERED_STREAM
        and good["cardinality"] == HEALTHY_N
        and good["reason"] == "ok"
        and mutant["cardinality"] > 0
        and expand_calls_oracle
    )
    return {
        "pass": ok,
        "bad": bad,
        "good_cardinality": good["cardinality"],
        "mutant_trust_exit_code_cardinality": mutant["cardinality"],
        "expand_calls_oracle": expand_calls_oracle,
    }


def test_progress_stream_never_parsed_as_result() -> dict:
    doc = progress_stream_doc()
    body = json.dumps(doc, sort_keys=True)
    json_run = ProducerRun(exit_code=0, stdout=body, receipt=doc)
    text_run = ProducerRun(exit_code=0, stdout=PROGRESS_TEXT, receipt=None)
    out = expand_dynamic_fanout(json_run, node=NODE)
    text_out = expand_dynamic_fanout(text_run, node=NODE)
    mutant = mutant_parse_progress_as_result(json_run)
    ok = (
        out["cardinality"] == 0
        and out["reason"] == "progress-stream"
        and out.get("taxonomy") == TAXONOMY_SEVERED_STREAM
        and text_out["cardinality"] == 0
        and text_out.get("taxonomy") == TAXONOMY_SEVERED_STREAM
        and mutant["cardinality"] == PROGRESS_N
    )
    return {
        "pass": ok,
        "out": out,
        "text_progress_out": text_out,
        "taxonomy_reason": out.get("taxonomy"),
        "fine_reason": out["reason"],
        "mutant_parse_progress_cardinality": mutant["cardinality"],
    }
