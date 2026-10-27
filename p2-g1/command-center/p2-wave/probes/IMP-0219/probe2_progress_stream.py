"""IMP-0219 probe 2: a progress-stream body is never parsed as a result.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0219/probe2_progress_stream.py
Line/phrase progress and a JSON body carrying PROGRESS markers both expand to ZERO with the
severed-stream family reason; the fine cause stays progress-stream. A json-loads mutant
would expand the items list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))

from agentspec.fanout import ProducerRun, expand_dynamic_fanout  # noqa: E402
from agentspec.oracle import evaluate_producer  # noqa: E402


def main() -> int:
    line_progress = "started in the background as task-1"
    out = expand_dynamic_fanout(
        ProducerRun(exit_code=0, stdout=line_progress, receipt={"n": 7})
    )

    items = ["i%d" % i for i in range(5)]
    json_progress = json.dumps({"type": "PROGRESS", "items": items})
    fanout_json = expand_dynamic_fanout(
        ProducerRun(exit_code=0, stdout=json_progress, receipt={"n": 5})
    )
    oracle_json = evaluate_producer(
        ProducerRun(exit_code=0, stdout=json_progress, receipt={"n": 5})
    )

    # Counterfactual: a mutant that JSON-loads the progress body would expand to 5.
    mutant_cardinality = len(json.loads(json_progress).get("items") or [])

    doc = {
        "unit_id": "IMP-0219",
        "probe": "probe2-progress-stream",
        "line_progress": {
            "cardinality": out["cardinality"],
            "reason": out["reason"],
            "fine_reason": out.get("fine_reason"),
            "units_empty": not out.get("units"),
        },
        "json_progress": {
            "cardinality": fanout_json["cardinality"],
            "reason": fanout_json["reason"],
            "fine_reason": fanout_json.get("fine_reason"),
        },
        "oracle_json_progress": oracle_json,
        "mutant_parse_progress_cardinality": mutant_cardinality,
        "taxonomy_reason": out["reason"],
        "classified_as_progress": out["reason"] == "severed-stream"
        and out.get("fine_reason") == "progress-stream",
        "never_parsed_as_result": (
            out["cardinality"] == 0
            and not out.get("units")
            and fanout_json["cardinality"] == 0
        ),
    }
    doc["pass"] = (
        doc["never_parsed_as_result"]
        and out["reason"] == "severed-stream"
        and fanout_json["reason"] == "severed-stream"
        and oracle_json.get("ok") is False
        and oracle_json.get("reason") == "progress-stream"
        and mutant_cardinality == 5
    )
    out_path = Path(__file__).resolve().parent / "probe2-progress.raw.json"
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if doc["pass"]:
        print("SUCCESS:IMP-0219-probe2 progress-stream never parsed as result;"
              " taxonomy reason severed-stream")
        return 0
    print("FAILED:IMP-0219-probe2 progress-stream control failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
