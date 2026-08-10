"""Every install gate must be LOAD-BEARING, proven by removing it.

This module is the durable form of :mod:`mkt.mutations`. It is separate from
``test_marketplace.py`` because it is the slowest thing here (measured ~2.1 s for the whole
battery) and because it answers a different question: not "does the gate refuse?" but "would
the install have SUCCEEDED without it?".

Read the distinction carefully -- it is the difference between a security control and a
coincidence. ``test_marketplace.py`` shows the installer refusing. Only this module shows that
the refusal came from the gate under test.
"""

from __future__ import annotations

import pytest

from mkt import fixture, mutations


@pytest.fixture(scope="module")
def battery(tmp_path_factory):
    root = tmp_path_factory.mktemp("mutation-battery")
    built = fixture.build(root / "fixture", now=fixture.T0)
    return mutations.run_battery(root, built=built)


def test_every_declared_mutation_ran(battery):
    """Assert the POSITIVE: N of N. A battery that ran zero mutations is not a green battery."""
    assert (
        battery["mutations_run"]
        == battery["mutations_declared"]
        == len(mutations.BATTERY)
    )
    assert battery["mutations_declared"] >= 10


@pytest.mark.parametrize("mutation_id", [m.mutation_id for m in mutations.BATTERY])
def test_gate_is_load_bearing(battery, mutation_id):
    row = next(r for r in battery["results"] if r["mutation"] == mutation_id)
    assert row["real_outcome"] == "REFUSED", (
        f"{mutation_id}: the real installer must refuse: {row}"
    )
    assert row["real_code"] == row["expected_code"], (
        f"{mutation_id}: refused for the wrong reason: {row}"
    )
    assert row["mutant_outcome"] == "SUCCESS", (
        f"{mutation_id}: with the guard removed the install must SUCCEED. It did not, which means "
        f"something OTHER than this gate blocked the scenario and the test proves nothing about "
        f"the gate: {row}"
    )


def test_battery_bottom_line(battery):
    assert battery["all_load_bearing"], [
        r for r in battery["results"] if not r["load_bearing"]
    ]


def test_a_mutation_that_matches_nothing_raises():
    """Detector discipline on the instrument itself.

    A zero-match substitution yields an UNMUTATED mutant, which then refuses -- and would be read
    as "the guard is load-bearing". That is a false pass, so it must raise instead.
    """
    with pytest.raises(mutations.MutationError, match="exactly once, found 0"):
        mutations.mutate("a = 1\n", "no such line", "x = 2")


def test_a_mutation_that_matches_twice_raises():
    with pytest.raises(mutations.MutationError, match="exactly once, found 2"):
        mutations.mutate("if False:\nif False:\n", "if False:", "if True:")


def test_every_battery_pattern_is_unique_in_the_source():
    """The patterns must still match after any refactor of install.py, or the battery goes blind.

    This test earned its place: ``ruff format`` wrapped four of the guarded lines and every literal
    needle stopped matching. Because ``mutate`` raises on a zero-match, the battery FAILED rather
    than reporting ten false "load-bearing" passes -- but this test is what named the cause in one
    line instead of ten confusing errors.
    """
    source = mutations.install_source()
    for mutation in mutations.BATTERY:
        working = source
        for needle, replacement in mutation.edits:
            assert mutations.count_matches(working, needle) == 1, (
                f"{mutation.mutation_id}: pattern is not unique: {needle!r}"
            )
            working = mutations.mutate(working, needle, replacement)


def test_whitespace_flexibility_survives_a_line_wrap():
    """The needle must match the same code before and after a formatter wraps it."""
    flat = 'ok, why = verify_document(manifest, "mkt.manifest.v1", expected_public_key=pub_key)'
    wrapped = (
        "        ok, why = verify_document(\n"
        '            manifest, "mkt.manifest.v1", expected_public_key=pub_key\n'
        "        )\n"
    )
    assert mutations.count_matches(wrapped, flat) == 1
    assert 'ok, why = True, ""' in mutations.mutate(wrapped, flat, 'ok, why = True, ""')


def test_mutant_module_is_unloaded_after_use():
    """A leaked mutant in sys.modules would let a later test import a deliberately broken gate."""
    import sys

    assert mutations.MUTANT_MODULE not in sys.modules
