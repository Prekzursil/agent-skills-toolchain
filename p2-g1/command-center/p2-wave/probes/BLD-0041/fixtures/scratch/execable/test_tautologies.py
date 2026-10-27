"""Planted tautological tests plus well-formed and filename-trap negatives.

This is a scratch copy, not a live product suite. Detector controls live here.
The JSON fixture named full_corpus.json is empty; the one named empty.json
holds three items. Input cardinality is measured at runtime from loaded bytes.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def bench_consume(items):
    n = 0
    for item in items:
        n += hash(str(item)) & 0xFFFF
    return n


def test_c1_no_assert():
    bench_consume([1, 2, 3])


def test_c2_unreachable_assert():
    ready = True
    if False:
        assert ready is False


def test_c3_bench_full_corpus():
    items = _load("full_corpus.json")
    bench_consume(items)


def test_c4_well_formed():
    items = [1, 2, 3]
    got = bench_consume(items)
    assert isinstance(got, int)
    assert got != bench_consume([])


def test_c5_raise_assertion_error():
    items = [1, 2, 3]
    got = bench_consume(items)
    if not isinstance(got, int):
        raise AssertionError("bench_consume did not return int")
    if got == bench_consume([]):
        raise AssertionError("empty and nonempty hashed equal")


def test_r01_assert_true():
    assert True


def test_r02_assert_literal():
    assert 1


def test_r03_empty_loop():
    for item in []:
        assert item == "never"


def test_r05_empty_loop_tuple():
    for item in ():
        assert item is not None


def test_r07_assert_string():
    assert "ok"


def test_r08_dead_if_zero():
    if 0:
        assert 1 == 2


def test_r09_for_empty_call():
    for item in list():
        assert item


def test_bench_named_empty_but_full():
    items = _load("empty.json")
    n = len(items)
    assert n == 3
    assert bench_consume(items) != bench_consume([])
