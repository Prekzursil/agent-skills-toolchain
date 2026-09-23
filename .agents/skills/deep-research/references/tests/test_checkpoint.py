"""Run-ledger + resume-from-checkpoint tests (Lens 12 find 1; tmp_path only)."""

import json

import pytest

from research_harness.checkpoint import (
    EVENT_CORRUPTION,
    EVENT_PLAN,
    EVENT_SUBQ_DONE,
    LedgerCorruption,
    append_event,
    ledger_path,
    load_ledger,
    open_run,
    plan_hash,
    record_partial_report,
    record_plan,
    record_subquestion_done,
    record_tool_output,
    resume,
    seal,
)

SUBQS = ["What is X?", "Who leads X?", "How big is the X market?"]
CAPS = ["web", "web", "synthesis"]


def test_plan_hash_normalizes_text_but_is_order_sensitive():
    base = plan_hash(SUBQS, CAPS)
    assert base == plan_hash(
        ["  what is x? ", "WHO leads X?", "how big is the x market?"], CAPS
    )
    assert base != plan_hash(list(reversed(SUBQS)), list(reversed(CAPS)))
    assert base != plan_hash(SUBQS, ["web", "web", "web"])
    assert base != plan_hash(SUBQS)  # capabilities are part of the plan identity
    assert len(base) == 64


def test_ledger_path_is_keyed_by_plan_hash(tmp_path):
    path = ledger_path(tmp_path, "abc123")
    assert path == tmp_path / "abc123.jsonl"


def test_append_and_load_roundtrip_preserves_order(tmp_path):
    path = ledger_path(tmp_path, plan_hash(SUBQS, CAPS))
    record_plan(path, plan_hash(SUBQS, CAPS), SUBQS, CAPS, ts="2026-09-02T07:00:00Z")
    record_subquestion_done(
        path,
        0,
        SUBQS[0],
        sources=("https://a.example/1",),
        grades=("[A.corrob x2.2026]",),
    )
    record_tool_output(path, 1, "exa.web_search_exa", "deadbeef", "raw payload text")
    record_partial_report(path, "# X: Research Report\npartial")
    ledger = load_ledger(path)
    assert [r["event"] for r in ledger.records] == [
        EVENT_PLAN,
        EVENT_SUBQ_DONE,
        "tool_output",
        "report_partial",
    ]
    assert ledger.corruption is None
    assert not ledger.sealed
    assert ledger.plan["subquestions"] == SUBQS
    assert ledger.answered_indexes == (0,)
    assert ledger.answered_subquestions == (SUBQS[0],)
    assert ledger.last_partial_report == "# X: Research Report\npartial"
    assert ledger.tool_outputs[0]["query_hash"] == "deadbeef"


def test_append_event_requires_an_event_name_and_writes_one_line(tmp_path):
    path = tmp_path / "l.jsonl"
    with pytest.raises(ValueError):
        append_event(path, {"no_event": 1})
    append_event(path, {"event": "plan", "text": "caf\u00e9"})
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert raw.count("\n") == 1
    assert json.loads(raw)["text"] == "caf\u00e9"


def test_resume_skips_answered_and_seeds_from_last_partial_report(tmp_path):
    phash = plan_hash(SUBQS, CAPS)
    path = ledger_path(tmp_path, phash)
    record_plan(path, phash, SUBQS, CAPS)
    record_subquestion_done(path, 0, SUBQS[0])
    record_partial_report(path, "draft-1")
    record_subquestion_done(path, 1, SUBQS[1], status="open")
    record_partial_report(path, "draft-2")
    state = resume(load_ledger(path), SUBQS)
    assert not state.fresh
    assert state.completed == (SUBQS[0],)
    assert state.pending == (SUBQS[1], SUBQS[2])  # "open" is NOT answered
    assert state.open_subquestions == (SUBQS[1],)
    assert state.seed_report == "draft-2"


def test_resume_matches_subquestions_by_normalized_text(tmp_path):
    phash = plan_hash(SUBQS, CAPS)
    path = ledger_path(tmp_path, phash)
    record_plan(path, phash, SUBQS, CAPS)
    record_subquestion_done(path, 0, "what is x?")
    state = resume(load_ledger(path), SUBQS)
    assert state.completed == (SUBQS[0],)


def test_sealed_ledger_means_a_fresh_run(tmp_path):
    phash = plan_hash(SUBQS, CAPS)
    path = ledger_path(tmp_path, phash)
    record_plan(path, phash, SUBQS, CAPS)
    record_subquestion_done(path, 0, SUBQS[0])
    seal(path, "complete")
    ledger = load_ledger(path)
    assert ledger.sealed
    assert ledger.final_status == "complete"
    state = resume(ledger, SUBQS)
    assert state.fresh
    assert state.pending == tuple(SUBQS)
    assert state.completed == ()


def test_missing_ledger_is_an_empty_fresh_run(tmp_path):
    ledger = load_ledger(tmp_path / "nope.jsonl")
    assert ledger.records == ()
    state = resume(ledger, SUBQS)
    assert state.fresh
    assert state.pending == tuple(SUBQS)


def test_corrupt_line_fails_closed_truncating_to_last_good_record(tmp_path):
    phash = plan_hash(SUBQS, CAPS)
    path = ledger_path(tmp_path, phash)
    record_plan(path, phash, SUBQS, CAPS)
    record_subquestion_done(path, 0, SUBQS[0])
    good_size = path.stat().st_size
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"event": "subq_done", "index": 1, "subquest\n')  # torn write
        fh.write(
            json.dumps({"event": "subq_done", "index": 2, "subquestion": SUBQS[2]})
        )
        fh.write("\n")

    ledger = load_ledger(path)

    # Everything after the corrupt line is dropped, even the well-formed record.
    assert ledger.answered_indexes == (0,)
    assert ledger.corruption is not None
    assert ledger.corruption.dropped_lines == 2
    assert ledger.corruption.truncated_at == good_size
    # The file itself was truncated to the last good record + a corruption record.
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[-1])["event"] == EVENT_CORRUPTION
    assert json.loads(lines[-1])["dropped_lines"] == 2
    assert path.read_text(encoding="utf-8")[:good_size] == "".join(
        line + "\n" for line in lines[:2]
    )
    # Reloading the repaired ledger is clean and keeps the corruption on record.
    again = load_ledger(path)
    assert again.corruption is None
    assert any(r["event"] == EVENT_CORRUPTION for r in again.records)


def test_trailing_line_without_newline_is_treated_as_torn(tmp_path):
    path = tmp_path / "l.jsonl"
    append_event(path, {"event": "plan"})
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"event": "subq_done", "index": 0}')  # killed before the newline
    ledger = load_ledger(path)
    assert ledger.corruption is not None
    assert ledger.corruption.dropped_lines == 1
    assert [r["event"] for r in ledger.records] == ["plan", EVENT_CORRUPTION]


def test_non_object_or_eventless_json_line_is_corrupt(tmp_path):
    path = tmp_path / "l.jsonl"
    append_event(path, {"event": "plan"})
    with path.open("a", encoding="utf-8") as fh:
        fh.write('["not", "an", "object"]\n')
    ledger = load_ledger(path)
    assert ledger.corruption is not None
    assert ledger.corruption.dropped_lines == 1


def test_repair_false_raises_instead_of_truncating(tmp_path):
    path = tmp_path / "l.jsonl"
    append_event(path, {"event": "plan"})
    with path.open("a", encoding="utf-8") as fh:
        fh.write("garbage\n")
    with pytest.raises(LedgerCorruption):
        load_ledger(path, repair=False)
    assert path.read_text(encoding="utf-8").endswith("garbage\n")  # untouched


def test_open_run_creates_the_plan_record_once_and_resumes(tmp_path):
    ledger, state = open_run(tmp_path, SUBQS, CAPS)
    assert ledger.plan is not None
    assert state.fresh
    assert state.pending == tuple(SUBQS)
    record_subquestion_done(ledger.path, 0, SUBQS[0])

    ledger2, state2 = open_run(tmp_path, SUBQS, CAPS)
    assert sum(1 for r in ledger2.records if r["event"] == EVENT_PLAN) == 1
    assert not state2.fresh
    assert state2.pending == (SUBQS[1], SUBQS[2])


def test_open_run_after_seal_starts_a_new_ledger_file(tmp_path):
    ledger, _ = open_run(tmp_path, SUBQS, CAPS)
    seal(ledger.path, "partial:budget")
    ledger2, state2 = open_run(tmp_path, SUBQS, CAPS)
    assert ledger2.path != ledger.path
    assert state2.fresh
    assert ledger.path.exists()  # the sealed run is kept as an audit trail
