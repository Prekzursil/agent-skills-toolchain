"""Regression: the shard success count must read the verdict, not the tuple.

submit_and_gate returns {unit_id: (verdict, path)}. Comparing that tuple to "DONE" is
silently always False. Six consecutive shards reported 0/48 DONE while every artifact
passed both gates — a completion signal that can only ever say PARTIAL is worse than
no signal, because it reads as failure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))

from run_research import verdict_of  # noqa: E402


def test_reads_the_verdict_out_of_the_real_tuple_shape():
    assert verdict_of(("DONE", Path("/dbfs/x.md"))) == "DONE"
    assert verdict_of(("FAILED", None)) == "FAILED"
    assert verdict_of(("TIMEOUT", None)) == "TIMEOUT"


def test_the_exact_bug_a_tuple_must_not_compare_equal_to_the_string():
    v = ("DONE", Path("/dbfs/x.md"))
    assert v != "DONE", "premise of the bug"
    assert verdict_of(v) == "DONE", "helper must see through the tuple"


def test_tolerates_a_bare_string_shape():
    assert verdict_of("DONE") == "DONE"


def test_unknown_shapes_are_not_counted_as_done():
    for bad in (None, {}, (), 0, []):
        assert verdict_of(bad) != "DONE", f"{bad!r} must not count as DONE"


def test_counting_a_full_shard_yields_the_expected_total():
    verdicts = {f"u{i}": ("DONE", Path(f"/d/u{i}.md")) for i in range(48)}
    assert sum(1 for v in verdicts.values() if verdict_of(v) == "DONE") == 48
    verdicts["u7"] = ("FAILED", None)
    assert sum(1 for v in verdicts.values() if verdict_of(v) == "DONE") == 47
