import pytest

from harness.contract import LANE_SCHEMAS, Unit, schema_valid
from harness.lanes import derive

# CROSS-LANE GATE (A00 pure-additions lane). LANE_SCHEMAS lives in harness/contract.py, a
# DIVERGED file owned by the M03 merge lane. The toolchain copy registers only
# {coverage, smoke}, so schema_valid() sees an EMPTY required-field set for lane
# "derive" and returns schema-ok for ANY body. Measured: without this gate the positive
# assertion PASSES VACUOUSLY (a green test that measures nothing) and the skeleton
# rejection FAILS. Skipped, not deleted -- arms itself when M03 lands the schema.
# Settling experiment: `"derive" in harness.contract.LANE_SCHEMAS` becomes True.
_needs_derive_schema = pytest.mark.skipif(
    "derive" not in LANE_SCHEMAS,
    reason="LANE_SCHEMAS['derive'] not merged yet (M03 lane owns harness/contract.py)",
)


def test_one_unit_per_corpus_item():
    units = derive.derive_units(
        [
            {"id": "A001", "targets": ["rules/common/agents.md"], "stale_targets": []},
            {"id": "F030", "targets": ["harness/storage.py"], "stale_targets": []},
        ]
    )
    assert len(units) == 2
    assert all(u.lane == "derive" for u in units)
    assert len({u.id for u in units}) == 2, (
        "ids must be unique or DBFS artifacts collide"
    )


def test_each_prompt_names_its_own_corpus_doc_and_targets():
    units = derive.derive_units(
        [{"id": "A001", "targets": ["rules/common/agents.md"], "stale_targets": []}]
    )
    p = units[0].prompt
    assert "A001" in p
    assert "rules/common/agents.md" in p


def test_stale_targets_are_flagged_loudly():
    """A finding whose target changed since the corpus date must be re-derived, not
    applied. The prior 1582-finding audit on this estate was 19 commits stale."""
    fresh = derive.derive_units(
        [{"id": "A002", "targets": ["a.py"], "stale_targets": []}]
    )[0].prompt
    stale = derive.derive_units(
        [{"id": "A003", "targets": ["a.py"], "stale_targets": ["a.py"]}]
    )[0].prompt
    assert "CHANGED" in stale and "a.py" in stale
    assert "CHANGED" not in fresh, "do not cry stale on an unchanged target"


def test_prompt_is_read_only_and_forbids_pushing():
    p = derive.derive_units([{"id": "A001", "targets": ["a.py"], "stale_targets": []}])[
        0
    ].prompt
    low = p.lower()
    assert "read-only" in low
    assert "never" in low and "push" in low


def test_prompt_offers_the_full_verdict_set_not_just_confirm_refute():
    """A nine-day-old audit should be able to say ALREADY_FIXED. Collapsing that into
    'refuted' loses the difference between 'we fixed it' and 'it was never real'."""
    p = derive.derive_units([{"id": "A001", "targets": ["a.py"], "stale_targets": []}])[
        0
    ].prompt
    for v in (
        "STILL_TRUE",
        "ALREADY_FIXED",
        "NOT_A_DEFECT",
        "STALE_REDERIVED",
        "UNCLEAR",
    ):
        assert v in p


def test_artifact_paths_are_derive_scoped_and_unique():
    units = derive.derive_units(
        [
            {"id": "A001", "targets": ["a.py"], "stale_targets": []},
            {"id": "A002", "targets": ["b.py"], "stale_targets": []},
        ]
    )
    paths = [u.artifact for u in units]
    assert len(set(paths)) == 2
    assert all(p.startswith("/dbfs/tmp/R-derive/results/") for p in paths)


def test_empty_input_yields_no_units():
    assert derive.derive_units([]) == []


def test_a_brief_entry_reads_from_dbfs_instead_of_the_corpus():
    """Program R findings live in per-file briefs, not corpus docs. Same adjudication,
    different source — the node must be told which, or it clones the toolchain and finds
    nothing to read."""
    u = derive.derive_units(
        [
            {
                "id": "wu-07",
                "targets": ["harness/ledger.py"],
                "stale_targets": [],
                "brief": "/dbfs/tmp/R-derive/briefs/wu-07.md",
            }
        ]
    )[0]
    p = u.prompt
    assert "/dbfs/tmp/R-derive/briefs/wu-07.md" in p
    assert "harness-sota-2026-07-18-corpus" not in p, "must not send it to the corpus"


def test_a_corpus_entry_still_reads_from_the_corpus():
    p = derive.derive_units([{"id": "A001", "targets": ["a.py"], "stale_targets": []}])[
        0
    ].prompt
    assert "harness-sota-2026-07-18-corpus/A001.md" in p
    assert "/dbfs/tmp/R-derive/briefs/" not in p


@_needs_derive_schema
def test_derive_lane_schema_is_registered_and_gated():
    assert "derive" in LANE_SCHEMAS
    assert {"unit", "verdict", "evidence", "actionable"} <= LANE_SCHEMAS["derive"]


@_needs_derive_schema
def test_a_measured_derive_artifact_passes_the_gate(tmp_path):
    body = (
        "unit: A001\nverdict: STILL_TRUE\nseverity: high\n"
        "evidence: probe returned allowed=True for a denied class\n"
        "targets: rules/common/agents.md\nactionable: true\n"
    )
    a = tmp_path / "d.md"
    a.write_text(body + "x" * 1100, encoding="utf-8")
    u = Unit(id="A001", lane="derive", prompt="p", artifact=str(a))
    ok, reason = schema_valid(u, a)
    assert ok and reason == "schema-ok"


@_needs_derive_schema
def test_a_skeleton_derive_artifact_is_rejected(tmp_path):
    from harness.contract import SKELETON

    fields = ["unit", "verdict", "severity", "evidence", "targets", "actionable"]
    a = tmp_path / "d.md"
    a.write_text(
        "\n".join(f"{f}: {SKELETON}" for f in fields) + "\n" + "x" * 1100,
        encoding="utf-8",
    )
    u = Unit(id="A001", lane="derive", prompt="p", artifact=str(a))
    ok, reason = schema_valid(u, a)
    assert not ok and reason == "all-unknown-skeleton"


def test_sentinel_exemption_carried_over_from_the_research_lane():
    """Two research units lost complete work by skeletonising UNIT-COMPLETE itself."""
    p = derive.derive_units([{"id": "A001", "targets": ["a.py"], "stale_targets": []}])[
        0
    ].prompt
    assert "NEVER" in p and "skeletonis" in p
    assert p.index("skeleton") < p.index("completion marker")
