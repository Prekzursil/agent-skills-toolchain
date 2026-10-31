"""Single-defaulted-field deletion also trips the armed gate (IMP-0437).

Reviewer instrument: the sandbox fixture is hand-built here (not reused from
vfields_ci.mini_catalog), then mutations run through the same CI invocation.
Whole-defaults deletion and timeout_seconds-only deletion both fail armed;
both stay silent disarmed.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import vfields_ci as vc  # noqa: E402

DEFAULTS = {
    "assignment": {"model": "opus", "role": "implementer", "vendor": "anthropic"},
    "tool_permissions": ["Read", "Write"],
    "execution_substrate": "local-serialized",
    "timeout_seconds": 1800,
    "output_schema": "command-center/schema/receipt.schema.json",
    "evidence_requirement": "two mechanically independent signals",
    "tests_required": ["both-states control"],
    "reviewer_requirement": "independent reviewer",
    "retry_policy": "two strikes then pivot",
    "failure_classification": ["green-not-live"],
    "owner_approval_required": False,
}


def handbuilt_catalog(drop_defaults: bool = False,
                      drop_field: str | None = None) -> dict:
    defaults = None if drop_defaults else dict(DEFAULTS)
    if defaults is not None and drop_field:
        defaults.pop(drop_field, None)
    item = {
        "id": "R-Z07",
        "title": "reviewer hand-built completeness fixture",
        "phase": "0",
        "target": "arm V-FIELDS in CI",
        "inputs": ["fixture"],
        "dependencies": [],
        "completion_sentinel": "SUCCESS:R-Z07",
        "output_path": "command-center/receipts/R-Z07.json",
        "next_smallest_action": "run validate.py --require-complete",
        "status": "OPEN",
        "disposition": None,
        "program": "P2",
        "section": "OUTSTANDING",
    }
    doc = {"schema_version": 1, "owner_questions": [], "items": [item],
           "provenance": {}, "terminal_dispositions": {}}
    if defaults is not None:
        doc["defaults"] = defaults
    return doc


def main() -> int:
    results = {}
    with tempfile.TemporaryDirectory() as td:
        for label, kwargs in (
            ("intact", {}),
            ("whole_defaults_deleted", {"drop_defaults": True}),
            ("timeout_seconds_deleted", {"drop_field": "timeout_seconds"}),
        ):
            armed = vc.run_validate(
                vc.write_sandbox(Path(td) / ("armed-" + label),
                                 handbuilt_catalog(**kwargs)),
                flags=["--require-complete"])
            disarmed = vc.run_validate(
                vc.write_sandbox(Path(td) / ("disarmed-" + label),
                                 handbuilt_catalog(**kwargs)),
                flags=["--no-require-complete"])
            results[label] = {"armed_exit": armed["exit_code"],
                              "armed_vfields": armed["vfields"],
                              "disarmed_exit": disarmed["exit_code"]}

        assert results["intact"]["armed_exit"] == 0, results["intact"]
        for label in ("whole_defaults_deleted", "timeout_seconds_deleted"):
            assert results[label]["armed_exit"] != 0, label
            assert results[label]["armed_vfields"], label
            assert results[label]["disarmed_exit"] == 0, label + " disarmed control"

    print(json.dumps({
        "probe": "probe2-single-field-review",
        "unit_id": "IMP-0437",
        "fixture_builder": "hand-built (independent of probe1's mini_catalog)",
        "results": results,
        "sentinel": "SENTINEL:IMP-0437:FIELD-COMPLETENESS-ARMED",
    }, indent=2))
    print("SUCCESS:IMP-0437-probe2 single-field deletion trips the armed gate; "
          "disarmed stays silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
