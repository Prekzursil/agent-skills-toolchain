from harness import poll
from harness.contract import Unit
U = Unit(id="u1", lane="coverage", prompt="p", artifact="/dbfs/r/u1.md")
FIELDS = "file: src/a.py\nuncovered_before: [1]\ntests_added: 1\nsuite_status: green\ncoverage_after: 90\nbranch_pushed: agent/E-x\n"
def art(tmp, body): p = tmp/"u1.md"; p.write_text(body, encoding="utf-8"); return p

def test_done_needs_terminal_AND_gate_AND_schema(tmp_path):
    assert poll.classify("TERMINATED", U, art(tmp_path, FIELDS + "x"*1100 + "\nUNIT-COMPLETE: u1\n")) == "DONE"
def test_job_success_no_artifact_is_FAILED(tmp_path):
    assert poll.classify("TERMINATED", U, None) == "FAILED"
def test_nonzero_exit_valid_artifact_is_DONE(tmp_path):
    assert poll.classify("INTERNAL_ERROR", U, art(tmp_path, FIELDS + "y"*1100 + "\nUNIT-COMPLETE: u1\n")) == "DONE"
def test_running_is_RUNNING(tmp_path):
    assert poll.classify("RUNNING", U, None) == "RUNNING"
def test_below_1024_floor_is_FAILED(tmp_path):
    assert poll.classify("TERMINATED", U, art(tmp_path, FIELDS + "\nUNIT-COMPLETE: u1")) == "FAILED"
def test_schema_missing_fields_is_FAILED(tmp_path):
    assert poll.classify("TERMINATED", U, art(tmp_path, "x"*1100 + "\nUNIT-COMPLETE: u1\n")) == "FAILED"
def test_all_unknown_skeleton_is_FAILED(tmp_path):
    from harness.contract import SKELETON
    fields = ["file","uncovered_before","tests_added","suite_status","coverage_after","branch_pushed"]
    body = "\n".join(f"{f}: {SKELETON}" for f in fields)
    assert poll.classify("TERMINATED", U, art(tmp_path, body + "\n" + "x"*1100 + "\nUNIT-COMPLETE: u1\n")) == "FAILED"
def test_unreadable_reason_maps_to_UNKNOWN(tmp_path, monkeypatch):   # [G3-FIX] the 4th matrix cell
    monkeypatch.setattr(poll, "and_gate_artifact", lambda *a, **k: (False, "unreadable-x", 0))
    assert poll.classify("TERMINATED", U, art(tmp_path, "anything")) == "UNKNOWN"
