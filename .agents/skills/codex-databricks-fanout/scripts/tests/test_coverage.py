from harness.lanes import coverage


def test_unit_per_gap_with_branch_schema_and_full_honesty():
    gaps = [
        {"file": "src/a.py", "uncovered": [10, 11]},
        {"file": "src/b.py", "uncovered": [3]},
    ]
    units = coverage.coverage_units("env-inspector", gaps)
    assert len(units) == 2 and all(u.lane == "coverage" for u in units)
    p = units[0].prompt
    assert "env-inspector" in p and "src/a.py" in p and "10" in p
    assert (
        "agent/E-env-inspector-" in p and "never" in p.lower() and "main" in p.lower()
    )
    assert "UNKNOWN - not yet measured" in p  # verbatim ASCII write-as-you-go
    assert "CONTRADICTED" in p  # full confidence vocab
    assert "COVERAGE:" in p  # coverage line
    assert "1200" in p  # byte-parity instruction
    for fld in (
        "uncovered_before",
        "tests_added",
        "suite_status",
        "coverage_after",
        "branch_pushed",
    ):
        assert fld in p  # schema fields the 5th gate clause validates
    assert units[0].artifact.startswith("/dbfs/tmp/E-coverage/results/")
