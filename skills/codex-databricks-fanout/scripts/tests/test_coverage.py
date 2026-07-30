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
    assert "COVERAGE:" in p  # SPEC section 6.1 coverage line
    assert "1200" in p  # byte-parity instruction
    for fld in (
        "uncovered_before",
        "tests_added",
        "suite_status",
        "coverage_after",
        "branch_ready",
    ):
        assert fld in p  # schema fields the 5th gate clause validates
    assert units[0].artifact.startswith("/dbfs/tmp/E-coverage/results/")


def test_unit_is_told_the_node_holds_no_write_token():
    """R1: the fan-out node is shared+ephemeral, so it carries no write credential and the unit
    must commit LOCALLY and not push. The earlier prompt said `commit + push ... using the node's
    GITHUB_TOKEN`, which asks the unit to use a token that R1 forbids putting there; the schema
    field was renamed branch_pushed -> branch_ready in the same change. Asserted here because the
    field-name check above passes on the rename alone and would not notice the instruction
    reverting to a push model."""
    units = coverage.coverage_units(
        "env-inspector", [{"file": "src/a.py", "uncovered": [10]}]
    )
    p = units[0].prompt
    assert "Do NOT push" in p, (
        "the unit must be told not to push (no token on the node)"
    )
    assert "R1" in p, "the prompt must name the constraint so the unit can cite it"
    assert "GITHUB_TOKEN" not in p, "R1 forbids a write credential on the node"


def test_unit_exports_a_patch_so_the_work_survives_the_node():
    """The node is ephemeral. Measured 2026-07-26: units reached suite-green and 100% coverage,
    committed to a local agent/ branch, and the artifact recorded only `branch_ready:<local-sha>`
    — a sha on a machine about to be destroyed. DBFS held reports and no diff, so the loop proved
    a fix was possible and then discarded it.

    Exporting `git format-patch` to DBFS keeps R1 intact (still no token on the node) while making
    the work harvestable for the curated out-of-band push."""
    units = coverage.coverage_units(
        "env-inspector", [{"file": "src/a.py", "uncovered": [10]}]
    )
    p = units[0].prompt
    assert "format-patch" in p, (
        "the node must export the commit, not just report its sha"
    )
    assert "/dbfs/tmp/E-coverage/patches/" in p, (
        "the patch must land on DBFS to outlive the node"
    )
    assert "patch_file" in p, (
        "the artifact must record the patch path for the harvester"
    )
