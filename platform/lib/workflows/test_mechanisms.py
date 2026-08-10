"""Unit tests for the executable primitives the bp-3 blueprints declare.

Each test also carries its NEGATIVE case, so no primitive is asserted only in the direction that
happens to pass. A one-directional test is how a two-directional divergence goes unnoticed.
"""

from __future__ import annotations

import pytest

import mechanisms as m

# ------------------------------------------------------------------------- overlap primitive


def test_overlap_finds_shared_path_and_ignores_disjoint_sets():
    ov = m.pairwise_overlap({"a": ["x.py", "y.py"], "b": ["x.py"], "c": ["z.py"]})
    assert ov == {("a", "b"): frozenset({"x.py"})}
    assert ("a", "c") not in ov and ("b", "c") not in ov


def test_unknown_footprint_overlaps_everything_not_nothing():
    """Adverse inference: a None set must conflict with every peer, never with none of them."""
    ov = m.pairwise_overlap({"a": ["x.py"], "b": ["z.py"], "u": None})
    assert ("a", "u") in ov and ("b", "u") in ov
    assert ov[("a", "u")] == frozenset({"<unknown-file-set>"})
    assert ("a", "b") not in ov


def test_serial_groups_are_connected_components():
    keys = ["a", "b", "c", "d"]
    ov = m.pairwise_overlap({"a": ["x"], "b": ["x", "y"], "c": ["y"], "d": ["q"]})
    assert m.serial_groups(keys, ov) == [["a", "b", "c"], ["d"]]


def test_serial_groups_keeps_fully_disjoint_units_separate():
    keys = ["a", "b"]
    ov = m.pairwise_overlap({"a": ["x"], "b": ["y"]})
    assert m.serial_groups(keys, ov) == [["a"], ["b"]]


def test_worktree_is_the_default_for_mutating_units_and_unknown_is_serial():
    iso = m.assign_isolation({"a": ["x"], "b": ["y"], "u": None}, mutating=["a", "u"])
    assert iso == {"a": "worktree", "b": "scoped-add", "u": "serial"}


# ------------------------------------------------------------- byte identity / supersession


def test_byte_identical_overlap_is_stackable_and_differing_bytes_conflict():
    a = {"ci.yml": b"on: push\n", "a.py": b"x = 1\n"}
    b = {"ci.yml": b"on: push\n", "b.py": b"y = 2\n"}
    identical, conflict = m.classify_overlap(a, b)
    assert identical == frozenset({"ci.yml"}) and conflict == frozenset()

    c = {"ci.yml": b"on: pull_request\n"}
    identical2, conflict2 = m.classify_overlap(a, c)
    assert identical2 == frozenset() and conflict2 == frozenset({"ci.yml"})


def test_superset_detection_is_directional():
    assert m.is_superset(["c1"], ["c1", "c2"]) is True
    assert m.is_superset(["c1", "c2"], ["c1"]) is False


def test_merge_order_ranks_by_measured_surface_not_by_size():
    order = m.merge_order(["big", "small"], {}, {"big": 1, "small": 3})
    assert order == ["big", "small"], "a large diff with a small conflict surface must not be last"
    assert m.merge_order(["b", "a"], {}, {"a": 0, "b": 0}) == ["a", "b"], "ties break deterministically"


# ----------------------------------------------------------------------- EVPI clarification


def _q(text, opts):
    return m.Question(text=text, options=opts)


def test_zero_evpi_question_is_dropped_and_positive_evpi_survives():
    kept = m.evpi_questions(
        [
            _q("in-place or shadow table?", {"a": "plan-A", "b": "plan-B"}),
            _q("which font?", {"i": "same-plan", "r": "same-plan", "s": "same-plan"}),
        ],
        star_prefixed=False,
        actions_elapsed=0,
    )
    assert [k.text for k in kept] == ["in-place or shadow table?"]


def test_star_bypass_and_closed_window_each_return_zero_questions():
    cands = [_q("real ambiguity?", {"a": "plan-A", "b": "plan-B"})]
    assert m.evpi_questions(cands, star_prefixed=True, actions_elapsed=0) == []
    assert m.evpi_questions(cands, star_prefixed=False, actions_elapsed=3) == []
    assert len(m.evpi_questions(cands, star_prefixed=False, actions_elapsed=2)) == 1


def test_question_cap_is_enforced():
    cands = [_q(f"q{i}", {"a": f"plan-{i}-a", "b": f"plan-{i}-b"}) for i in range(6)]
    assert len(m.evpi_questions(cands, star_prefixed=False, actions_elapsed=0)) == 3


# ---------------------------------------------------------------------- assumption ledger


def test_low_confidence_load_bearing_without_a_probe_is_unhandled():
    rows = [
        m.Assumption("stale pinned ref", True, "low"),
        m.Assumption("suite is fast", False, "low"),
        m.Assumption("coverage cmd exists", True, "low", verification_probe="run enforcement.command"),
        m.Assumption("git is installed", True, "high"),
    ]
    assert [r.text for r in m.unhandled_assumptions(rows)] == ["stale pinned ref"]


def test_a_probe_moves_a_row_out_of_unhandled():
    rows = [m.Assumption("stale pinned ref", True, "low", verification_probe="re-resolve the ref")]
    assert m.unhandled_assumptions(rows) == []


def test_unknown_confidence_band_raises_rather_than_passing_silently():
    with pytest.raises(ValueError):
        m.unhandled_assumptions([m.Assumption("x", True, "probably-fine")])


def test_blank_required_field_resolves_to_worst_case():
    assert m.blank_field_default("", "no rollback path exists") == "no rollback path exists"
    assert m.blank_field_default(None, "worst") == "worst"
    assert m.blank_field_default([], "worst") == "worst"
    assert m.blank_field_default("declared value", "worst") == "declared value"


# ------------------------------------------------------------- acceptance-criterion lint


@pytest.mark.parametrize(
    "criterion,expected",
    [
        ("p95 export latency <= 2000 ms measured over 100 runs", True),
        ("exactly 0 rows are dropped when the source file is truncated", True),
        ("The export should feel fast", False),
        ("the UI is clean and modern", False),
        ("", False),
        ("it works", False),
    ],
)
def test_testability_requires_a_comparator_and_a_quantity(criterion, expected):
    assert m.is_testable(criterion) is expected


def test_orphan_requirement_is_one_with_no_decision_ancestor():
    reqs = {"R1": "D-004", "R2": "D-004", "R3": "D-099", "R4": None}
    assert m.orphan_requirements(reqs, ["D-004", "D-007"]) == ["R3", "R4"]


# ------------------------------------------------------------------ tournament primitives


def _arch(name, corr, rec, crit=(), fp=""):
    return m.Architecture(
        name=name, scores={"correctness": corr, "recoverability": rec}, critical_errors=list(crit), fingerprint=fp
    )


def test_critical_error_eliminates_before_any_averaging():
    cands = [_arch("alpha", 4, 4, crit=["stores a credential"], fp="a"), _arch("beta", 2, 1, fp="b")]
    live, out = m.eliminate_critical(cands)
    assert out == ["alpha"] and [c.name for c in live] == ["beta"]


def test_near_duplicate_architectures_are_an_independence_failure():
    cands = [_arch("beta", 4, 1, fp="b"), _arch("delta", 4, 1, fp="b"), _arch("gamma", 2, 4, fp="c")]
    assert m.near_duplicates(cands) == [("beta", "delta")]
    assert m.near_duplicates([_arch("a", 1, 1, fp="x"), _arch("b", 1, 1, fp="y")]) == []


def test_champion_names_a_deciding_dimension_and_minority_report_is_non_empty():
    weights = {"correctness": 0.6, "recoverability": 0.4}
    cands = [_arch("beta", 4, 1, fp="b"), _arch("gamma", 2, 4, fp="c")]
    champ, rounds = m.bracket(cands, weights)
    assert champ == "beta"
    assert rounds[0]["deciding_dimension"] in weights
    assert m.minority_report(rounds) == ["recoverability"]


def test_without_the_override_the_fatal_architecture_would_win():
    """The control that proves the override is load-bearing, not decorative."""
    weights = {"correctness": 0.6, "recoverability": 0.4}
    fatal_cleared = [_arch("alpha", 4, 4, fp="a"), _arch("beta", 4, 1, fp="b")]
    champ, _ = m.bracket(fatal_cleared, weights)
    assert champ == "alpha"


def test_bracket_returns_none_when_every_candidate_is_fatal():
    champ, rounds = m.bracket([_arch("a", 4, 4, crit=["fatal"], fp="a")], {"correctness": 1.0})
    assert champ is None and rounds == []


# ---------------------------------------------------------------------------- lint ladder


def test_lint_ladder_escalates_at_the_cap_and_never_beyond():
    assert m.lint_ladder([False, False, False, True], cap=3) == ("escalate", 3)


def test_lint_ladder_can_also_come_back_clean():
    assert m.lint_ladder([False, True, False], cap=3) == ("clean", 2)
    assert m.lint_ladder([True], cap=3) == ("clean", 1)


def test_lint_ladder_rejects_a_nonsense_cap():
    with pytest.raises(ValueError):
        m.lint_ladder([True], cap=0)


# ------------------------------------------------------------------ failure-domain mapping


def test_try_except_importerror_flags_fail_open_and_a_missing_probe_is_unmonitored():
    rows = m.failure_domain_walk(
        ["try-except-importerror", "pins-a-ref"],
        probes={"stale-pinned-ref": "re-resolve the ref and compare to the pin"},
    )
    assert len(rows) == len(m.FAILURE_CLASSES) == 10
    applicable = [r.failure_class for r in rows if r.applies]
    assert applicable == ["fail-open-on-missing-dependency", "stale-pinned-ref"]
    assert m.unmonitored_domains(rows) == ["fail-open-on-missing-dependency"]


def test_supplying_the_probe_clears_the_unmonitored_flag():
    rows = m.failure_domain_walk(
        ["try-except-importerror"],
        probes={"fail-open-on-missing-dependency": "assert the guard fires when the import is removed"},
    )
    assert m.unmonitored_domains(rows) == []


def test_zero_applicable_domains_is_reachable_so_the_walk_is_not_rubber_stamping():
    rows = m.failure_domain_walk([])
    assert [r for r in rows if r.applies] == []
    assert m.unmonitored_domains(rows) == []


# --------------------------------------------------------- write-as-you-go / resume plan


def test_unknown_marker_blocks_completion_independently_of_size():
    big_but_unknown = "pairs=12; groups: " + m.UNKNOWN_MARKER + "; " + "x" * 500
    assert m.unit_complete(big_but_unknown, min_bytes=32) is False
    assert m.unit_complete("all rows measured and cited, nothing outstanding here", min_bytes=32) is True


def test_size_floor_blocks_completion_independently_of_the_marker():
    assert m.unit_complete("ok", min_bytes=32) is False


def test_resume_plan_partitions_every_unit_exactly_once():
    artifacts = {
        "u1": "measured: pairs=12 groups=3 isolation=worktree; every row cited.",
        "u2": "pairs=12; groups: " + m.UNKNOWN_MARKER,
        "u3": "ok",
    }
    plan = m.resume_plan(artifacts, min_bytes=32)
    assert plan == {"skip": ["u1"], "run": ["u2", "u3"]}
    assert sorted(plan["skip"] + plan["run"]) == sorted(artifacts)


def test_a_truthful_partial_is_still_a_success_when_non_empty():
    assert m.is_truthful_partial("claim A: " + m.UNKNOWN_MARKER) is True
    assert m.is_truthful_partial("   ") is False


# ---------------------------------------------------------------- round-trip / vendor lock


SRC_STAGES = [
    {"id": "a", "kind": "task", "depends_on": []},
    {"id": "b", "kind": "fanout", "depends_on": ["a"], "body": [{"id": "b-inner", "kind": "task", "depends_on": []}]},
    {"id": "c", "kind": "gate", "depends_on": ["b"]},
]


def test_identical_topology_round_trips_and_a_dropped_nested_stage_does_not():
    src = {"stages": SRC_STAGES}
    assert m.topology(src) == [
        ("a", "task", ()),
        ("b", "fanout", ("a",)),
        ("b-inner", "task", ()),
        ("c", "gate", ("b",)),
    ]
    assert m.roundtrip_equal(src, {"stages": SRC_STAGES}) is True

    flattened = [
        {"id": "a", "kind": "task", "depends_on": []},
        {"id": "b", "kind": "fanout", "depends_on": ["a"], "body": []},
        {"id": "c", "kind": "gate", "depends_on": ["b"]},
    ]
    assert m.roundtrip_equal(src, {"stages": flattened}) is False


def test_a_reordered_dependency_edge_breaks_the_round_trip():
    src = {"stages": [{"id": "a", "kind": "task", "depends_on": ["x", "y"]}]}
    reordered = {"stages": [{"id": "a", "kind": "task", "depends_on": ["y", "x"]}]}
    assert m.roundtrip_equal(src, reordered) is False


def test_a_stage_with_no_provider_cell_is_declared_vendor_locked():
    assert m.vendor_locked(["a", "b", "c"], {"a": {"anthropic": "task"}, "b": {"anthropic": "fanout"}, "c": {}}) == ["c"]


# ------------------------------------------------------------- disarmed vs unused (audit)


@pytest.mark.parametrize(
    "registered,fired,fires_on_bad,expected",
    [
        (True, False, False, "disarmed"),
        (True, False, True, "live-dormant"),
        (True, True, True, "live-exercised"),
        (True, False, None, "unknown-no-both-states-probe"),
        (False, False, None, "unregistered"),
    ],
)
def test_disarmed_is_never_reported_as_unused(registered, fired, fires_on_bad, expected):
    assert (
        m.classify_component(
            registered=registered, fired_recently=fired, fires_on_known_bad_state=fires_on_bad
        )
        == expected
    )


def test_removal_requires_a_trace_and_refuses_anything_security_bearing():
    assert m.removable("unregistered", blast_radius_traced=True, security_bearing=False) is True
    assert m.removable("unregistered", blast_radius_traced=False, security_bearing=False) is False
    assert m.removable("unregistered", blast_radius_traced=True, security_bearing=True) is False
    assert m.removable("disarmed", blast_radius_traced=True, security_bearing=False) is False
    assert m.removable("live-dormant", blast_radius_traced=True, security_bearing=False) is False
