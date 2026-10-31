import json

from harness import poll
from harness.contract import LANE_SCHEMAS, Unit

U = Unit(id="u1", lane="coverage", prompt="p", artifact="/dbfs/r/u1.md")

# The coverage-lane required-field list is DERIVED from the contract, never hardcoded.
# The two long-diverged copies of harness/contract.py disagreed on it -- this tree had
# {..., branch_pushed}, the databricks copy {..., branch_ready, patch_file} -- and a
# hardcoded list silently INVERTS these tests when the contract moves: a stale name is
# simply absent from the body, so the "valid artifact" cases start asserting FAILED ==
# DONE. Measured: the pre-merge hardcoded test goes 2-failed against the databricks
# schema, this one stays green against both. Deriving keeps every case exercising the
# contract that actually ships. Values carry the databricks copy's realistic example
# data where the field is known and a placeholder otherwise, because schema_valid only
# substring-matches the field NAME.
COVERAGE_FIELDS = sorted(LANE_SCHEMAS["coverage"])
_EXAMPLE_VALUES = {
    "file": "src/a.py",
    "uncovered_before": "[1]",
    "tests_added": "1",
    "suite_status": "green",
    "coverage_after": "90",
    "branch_pushed": "agent/E-x",
    "branch_ready": "agent/E-x",
    "patch_file": "none",
}
FIELDS = "".join(
    "{}: {}\n".format(f, _EXAMPLE_VALUES.get(f, "v")) for f in COVERAGE_FIELDS
)


def art(tmp, body):
    p = tmp / "u1.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_done_needs_terminal_AND_gate_AND_schema(tmp_path):
    assert (
        poll.classify(
            "TERMINATED",
            U,
            art(tmp_path, FIELDS + "x" * 1100 + "\nUNIT-COMPLETE: u1\n"),
        )
        == "DONE"
    )


def test_job_success_no_artifact_is_FAILED(tmp_path):
    assert poll.classify("TERMINATED", U, None) == "FAILED"


def test_nonzero_exit_valid_artifact_is_DONE(tmp_path):
    assert (
        poll.classify(
            "INTERNAL_ERROR",
            U,
            art(tmp_path, FIELDS + "y" * 1100 + "\nUNIT-COMPLETE: u1\n"),
        )
        == "DONE"
    )


def test_running_is_RUNNING(tmp_path):
    assert poll.classify("RUNNING", U, None) == "RUNNING"


def test_below_1024_floor_is_FAILED(tmp_path):
    body = FIELDS + "\nUNIT-COMPLETE: u1"
    # Precondition, asserted so a schema growth fails loudly here instead of silently
    # turning this into a pass-for-the-wrong-reason: the body must be UNDER the floor.
    assert len(body.encode("utf-8")) < 1024
    assert poll.classify("TERMINATED", U, art(tmp_path, body)) == "FAILED"


def test_schema_missing_fields_is_FAILED(tmp_path):
    assert (
        poll.classify(
            "TERMINATED", U, art(tmp_path, "x" * 1100 + "\nUNIT-COMPLETE: u1\n")
        )
        == "FAILED"
    )


def test_all_unknown_skeleton_is_FAILED(tmp_path):
    from harness.contract import SKELETON

    body = "\n".join(f"{f}: {SKELETON}" for f in COVERAGE_FIELDS)
    assert (
        poll.classify(
            "TERMINATED",
            U,
            art(tmp_path, body + "\n" + "x" * 1100 + "\nUNIT-COMPLETE: u1\n"),
        )
        == "FAILED"
    )


def test_unreadable_reason_maps_to_UNKNOWN(tmp_path, monkeypatch):
    # [G3-FIX] the 4th matrix cell: a gate FAIL must split FAILED vs UNKNOWN on the
    # reason, and only an OSError-shaped "unreadable-*" reason may downgrade to UNKNOWN.
    monkeypatch.setattr(
        poll, "and_gate_artifact", lambda *a, **k: (False, "unreadable-x", 0)
    )
    assert poll.classify("TERMINATED", U, art(tmp_path, "anything")) == "UNKNOWN"


# ---------------------------------------------------------------------------
# poll_once: untested on BOTH merged sides (0 of the 8 pre-merge cases touched it),
# so the CLI-parse -> classify wiring, the JSONDecodeError fallback and the
# `state: null` fallback were all unexercised. Added here with the module merge.
# ---------------------------------------------------------------------------

_TERMINAL_OUT = json.dumps({"state": {"life_cycle_state": "TERMINATED"}})


def test_poll_once_builds_get_run_argv_and_classifies(tmp_path):
    good = art(tmp_path, FIELDS + "x" * 1100 + "\nUNIT-COMPLETE: u1\n")
    calls = []

    def run_cmd(argv):
        calls.append(argv)
        return 0, _TERMINAL_OUT, ""

    assert poll.poll_once(7, [U], run_cmd, lambda u: good) == {"u1": "DONE"}
    assert calls == [
        ["databricks", "jobs", "get-run", "7", "--profile", "bolt-datascience"]
    ]


def test_poll_once_classifies_each_unit_independently(tmp_path):
    u2 = Unit(id="u2", lane="coverage", prompt="p", artifact="/dbfs/r/u2.md")
    good = art(tmp_path, FIELDS + "x" * 1100 + "\nUNIT-COMPLETE: u1\n")
    fetched = {"u1": good, "u2": None}
    verdicts = poll.poll_once(
        9, [U, u2], lambda argv: (0, _TERMINAL_OUT, ""), lambda u: fetched[u.id]
    )
    assert verdicts == {"u1": "DONE", "u2": "FAILED"}


def test_poll_once_unparseable_json_stays_non_terminal():
    verdicts = poll.poll_once(7, [U], lambda argv: (0, "not-json", ""), lambda u: None)
    assert verdicts == {"u1": "RUNNING"}


def test_poll_once_null_state_object_stays_non_terminal():
    out = json.dumps({"state": None})
    verdicts = poll.poll_once(7, [U], lambda argv: (0, out, ""), lambda u: None)
    assert verdicts == {"u1": "RUNNING"}
