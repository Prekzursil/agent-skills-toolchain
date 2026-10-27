"""IMP-0194 tests: trace replay parity + gap-derived typed cover.

Run all:      python -B tools/workflow_foundry/tests/test_from_trace_and_gap.py
Run one:      python -B tools/workflow_foundry/tests/test_from_trace_and_gap.py::test_name
Exit 0 iff every selected test passes.
"""
from __future__ import annotations

import sys
from pathlib import Path

W = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(W / "tools"))

from workflow_foundry.sample import OMITTED_GAP, SAMPLE_INPUTS, SAMPLE_STEPS  # noqa: E402
from workflow_foundry.replay_log import record_adhoc  # noqa: E402
from workflow_foundry.generate import from_trace, from_gap, as_candidate  # noqa: E402
from workflow_foundry.replay import replay_workflow, outcomes_equal  # noqa: E402
from workflow_foundry.gap_finder import find_gaps, covering_stubs, load_taxonomy, parse_taxonomy  # noqa: E402


def _fixture():
    log = record_adhoc(SAMPLE_INPUTS, SAMPLE_STEPS, trace_id="imp0194-adhoc")
    wf = from_trace(log)
    return log, wf


def test_trace_replay_matches_adhoc():
    log, wf = _fixture()
    same = replay_workflow(wf, SAMPLE_INPUTS)
    assert outcomes_equal(same["outcome"], log["outcome"])


def test_mutated_inputs_diverge():
    log, wf = _fixture()
    mut = replay_workflow(wf, dict(SAMPLE_INPUTS, b="w0rld"))
    assert not outcomes_equal(mut["outcome"], log["outcome"])


def test_dropped_stage_diverge():
    log, wf = _fixture()
    ablated = {"id": wf["id"] + "-ablated", "stages": wf["stages"][:-1]}
    drop = replay_workflow(ablated, SAMPLE_INPUTS)
    assert not outcomes_equal(drop["outcome"], log["outcome"])


def test_results_not_copied_into_workflow():
    log, wf = _fixture()
    blob = repr(wf)
    for event in log["events"]:
        assert repr(event["result"]) not in blob, "result string leaked into workflow"


def test_gap_closed_only_by_typed_cover():
    tax = load_taxonomy()
    lib = covering_stubs(tax, omit=[OMITTED_GAP])
    assert OMITTED_GAP in find_gaps(tax, lib)["gaps"]
    cand = as_candidate(from_gap(OMITTED_GAP, tax))
    assert OMITTED_GAP not in find_gaps(tax, lib + [cand])["gaps"]
    prose = {"id": "prose", "category": OMITTED_GAP.split(":")[0], "covers": []}
    assert OMITTED_GAP in find_gaps(tax, lib + [prose])["gaps"]
    wrong = {"id": "wrong", "category": "replay", "covers": [OMITTED_GAP]}
    assert OMITTED_GAP in find_gaps(tax, lib + [wrong])["gaps"]


def test_taxonomy_size_is_parsed_not_hardcoded():
    tax = load_taxonomy()
    spec_text = Path(tax.source_path).read_text(encoding="utf-8")
    shorter = parse_taxonomy(spec_text.replace("- token-budget\n", "", 1))
    assert shorter.size == tax.size - 1
    finder_src = (W / "tools" / "workflow_foundry" / "gap_finder.py").read_text(encoding="utf-8")
    assert str(tax.size) not in finder_src, "finder hardcodes the taxonomy size"


TESTS = [test_trace_replay_matches_adhoc, test_mutated_inputs_diverge,
         test_dropped_stage_diverge, test_results_not_copied_into_workflow,
         test_gap_closed_only_by_typed_cover, test_taxonomy_size_is_parsed_not_hardcoded]


def main(argv: list) -> int:
    selected = [t for t in TESTS
                if not argv or any(t.__name__ in a for a in argv)]
    if not selected:
        print("no test matched", argv)
        return 2
    failed = 0
    for t in selected:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    if failed == 0:
        print("SUCCESS:IMP-0194-tests")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
