import pytest

from harness.contract import LANE_SCHEMAS, Unit, schema_valid
from harness.lanes import research

# CROSS-LANE GATE (A00 pure-additions lane). LANE_SCHEMAS lives in harness/contract.py, a
# DIVERGED file owned by the M03 merge lane. The toolchain copy registers only
# {coverage, smoke}, so schema_valid() sees an EMPTY required-field set for lane
# "research" and returns schema-ok for ANY body. Measured: without this gate the positive
# assertion PASSES VACUOUSLY (a green test that measures nothing) and the skeleton
# rejection FAILS. Skipped, not deleted -- arms itself when M03 lands the schema.
# Settling experiment: `"research" in harness.contract.LANE_SCHEMAS` becomes True.
_needs_research_schema = pytest.mark.skipif(
    "research" not in LANE_SCHEMAS,
    reason="LANE_SCHEMAS['research'] not merged yet (M03 lane owns harness/contract.py)",
)


def test_matrix_is_the_cross_product_of_targets_and_lenses():
    units = research.research_units(
        ["harness/modules.py", "skills/router"], ["bugs", "security"]
    )
    assert len(units) == 4
    assert all(u.lane == "research" for u in units)
    assert len({u.id for u in units}) == 4, (
        "unit ids must be unique or DBFS artifacts collide"
    )


def test_every_unit_carries_a_distinct_question_not_a_shared_one():
    """500 identical prompts is 500x the spend for 1x the information. The lens must
    actually reach the prompt text, or the fan-out degenerates into duplicates."""
    units = research.research_units(
        ["harness/modules.py"], ["bugs", "security", "new-venues"]
    )
    prompts = [u.prompt for u in units]
    assert len(set(prompts)) == 3
    for u in units:
        assert u.meta["lens"] in u.prompt
        assert u.meta["target"] in u.prompt


def test_artifact_paths_are_research_scoped_and_unique():
    units = research.research_units(["a/b.py", "a/c.py"], ["bugs"])
    paths = [u.artifact for u in units]
    assert len(set(paths)) == 2
    assert all(p.startswith("/dbfs/tmp/R-research/results/") for p in paths)


def test_cap_truncates_deterministically_and_reports_the_drop():
    """A silent cap reads as 'covered everything' when it did not."""
    units, dropped = research.plan_wave(
        [f"f{i}.py" for i in range(10)], ["bugs", "security"], cap=7
    )
    assert len(units) == 7
    assert dropped == 13
    again, _ = research.plan_wave(
        [f"f{i}.py" for i in range(10)], ["bugs", "security"], cap=7
    )
    assert [u.id for u in units] == [u.id for u in again], "cap must be deterministic"


def test_plan_wave_with_no_cap_keeps_everything():
    units, dropped = research.plan_wave(["a.py", "b.py"], ["bugs"], cap=None)
    assert len(units) == 2 and dropped == 0


def test_shards_cover_every_unit_exactly_once():
    """500 units cannot exceed the R9 ceiling in one wave; sharding must not lose or
    duplicate a unit."""
    units, _ = research.plan_wave(
        [f"f{i}.py" for i in range(50)], ["bugs", "security"], cap=None
    )
    shards = research.shard(units, size=48)
    assert sum(len(s) for s in shards) == len(units)
    flat = [u.id for s in shards for u in s]
    assert len(set(flat)) == len(units), "a unit appears in two shards"
    assert all(len(s) <= 48 for s in shards)


def test_shard_rejects_a_nonpositive_size():
    units, _ = research.plan_wave(["a.py"], ["bugs"], cap=None)
    for bad in (0, -1):
        try:
            research.shard(units, size=bad)
        except ValueError:
            continue
        raise AssertionError(f"shard(size={bad}) must refuse, not loop forever")


def test_empty_inputs_produce_no_units_rather_than_a_bogus_one():
    assert research.research_units([], ["bugs"]) == []
    assert research.research_units(["a.py"], []) == []


def test_prompt_forbids_writing_and_pushing():
    """R1: research units are READ-ONLY. A research agent that commits is out of contract."""
    p = research.research_units(["a.py"], ["bugs"])[0].prompt
    low = p.lower()
    assert "read-only" in low
    assert "never" in low and "push" in low


def test_harness_targets_are_fetched_from_the_dbfs_bundle_not_cloned():
    """~/.agents/harness is not a git repo and is absent from the toolchain remote
    (verified 2026-07-26). A unit told to clone it would research nothing."""
    p = research.research_units(["harness/modules.py"], ["bugs"])[0].prompt
    assert "harness.tgz" in p, "harness units must fetch the DBFS bundle"
    assert "git clone" not in p, "there is no repo to clone for the harness"


def test_toolchain_targets_are_cloned_from_the_remote():
    p = research.research_units(["toolchain/rules/common/security.md"], ["bugs"])[
        0
    ].prompt
    assert "git clone" in p and "agent-skills-toolchain" in p
    assert "harness.tgz" not in p


def test_prompt_demands_evidence_anchors_and_confidence():
    p = research.research_units(["a.py"], ["bugs"])[0].prompt
    assert "VERIFIED" in p and "CONTRADICTED" in p
    assert "file:line" in p


def test_prompt_forbids_skeletonising_the_completion_sentinel():
    """Measured 2026-07-26: a unit produced four VERIFIED findings and then wrote
    `UNIT-COMPLETE: UNKNOWN - not yet measured`, so the harvest gate discarded complete
    work on the one line that declares it complete. The write-as-you-go instruction says
    to skeletonise 'every field'; the sentinel is not a field and must be exempted
    explicitly, or the instruction reads as covering it."""
    p = research.research_units(["a.py"], ["bugs"])[0].prompt
    assert "NEVER" in p and "skeletonis" in p
    assert "completion marker" in p
    # The exemption must appear AFTER the skeleton instruction it is correcting,
    # otherwise a unit reads 'skeletonise every field' last and does exactly that.
    assert p.index("skeleton") < p.index("completion marker")


@_needs_research_schema
def test_research_lane_has_a_registered_schema_the_gate_enforces():
    assert "research" in LANE_SCHEMAS
    required = LANE_SCHEMAS["research"]
    assert {"target", "lens", "findings", "confidence"} <= required


@_needs_research_schema
def test_a_measured_research_artifact_passes_the_gate(tmp_path):
    body = (
        "target: harness/modules.py\nlens: bugs\nfindings: 2\n"
        "severity: high\nevidence: modules.py:1359\n"
        "recommendation: scope the goal read\nconfidence: VERIFIED\n"
    )
    a = tmp_path / "r.md"
    a.write_text(body + "x" * 1100, encoding="utf-8")
    u = Unit(id="R-x", lane="research", prompt="p", artifact=str(a))
    ok, reason = schema_valid(u, a)
    assert ok and reason == "schema-ok"


@_needs_research_schema
def test_a_skeleton_research_artifact_is_rejected(tmp_path):
    from harness.contract import SKELETON

    fields = [
        "target",
        "lens",
        "findings",
        "severity",
        "evidence",
        "recommendation",
        "confidence",
    ]
    body = "\n".join(f"{f}: {SKELETON}" for f in fields)
    a = tmp_path / "r.md"
    a.write_text(body + "\n" + "x" * 1100, encoding="utf-8")
    u = Unit(id="R-x", lane="research", prompt="p", artifact=str(a))
    ok, reason = schema_valid(u, a)
    assert not ok and reason == "all-unknown-skeleton"
