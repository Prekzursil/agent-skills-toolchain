"""In-process seed-sweep suite for TST-0343.

Callables take a seeded random.Random. The runner never seeds the process
global RNG, so a test that reads entropy outside the injected RNG is a
C11 flake, not seed-sensitivity.

Planted controls (must be detected, not "fixed" into green):
* test_planted_narrow_shuffle — asserts one permutation that only seed 127
  produces. Quietly declared seed_sensitive=false.
* test_planted_hidden_counter_flake — ignores the RNG and uses a hidden
  call counter. Same seed disagrees with itself.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO / "tools" / "command-center") not in sys.path:
    sys.path.insert(0, str(REPO / "tools" / "command-center"))

import seed_registry as SR  # noqa: E402

_FLAKE_CALLS = 0


def reset_planted_state() -> None:
    global _FLAKE_CALLS
    _FLAKE_CALLS = 0


def _rng(rng: random.Random | None) -> random.Random:
    return rng if rng is not None else random.Random(0)


def test_arithmetic_stable(rng: random.Random | None = None) -> None:
    _rng(rng)
    assert 2 + 2 == 4
    assert pow(3, 5, 7) == 5


def test_string_roundtrip(rng: random.Random | None = None) -> None:
    _rng(rng)
    payload = "TST-0343-seed-registry"
    assert payload.encode("utf-8").decode("utf-8") == payload


def test_unit_interval(rng: random.Random | None = None) -> None:
    rng = _rng(rng)
    xs = [rng.random() for _ in range(32)]
    assert all(0.0 <= x < 1.0 for x in xs)
    assert len(xs) == 32


def test_shuffle_preserves_multiset(rng: random.Random | None = None) -> None:
    rng = _rng(rng)
    items = [1, 1, 2, 3, 5, 8]
    shuffled = list(items)
    rng.shuffle(shuffled)
    assert sorted(shuffled) == sorted(items)
    assert len(shuffled) == len(items)


def test_planted_narrow_shuffle(rng: random.Random | None = None) -> None:
    """PLANTED: hardcoded permutation — passes on one recorded seed only."""
    rng = _rng(rng)
    items = list(range(6))
    rng.shuffle(items)
    assert items == SR.PLANTED_NARROW_PERMUTATION


def test_planted_hidden_counter_flake(rng: random.Random | None = None) -> None:
    """PLANTED: hidden mutable state, not captured by the seed."""
    global _FLAKE_CALLS
    _rng(rng)
    _FLAKE_CALLS += 1
    assert _FLAKE_CALLS % 2 == 1


SPECS = [
    SR.TestSpec(
        id="test_arithmetic_stable",
        seed_sensitive=False,
        why="Integer arithmetic; does not consume RNG.",
        fn=test_arithmetic_stable,
        planted=None,
    ),
    SR.TestSpec(
        id="test_string_roundtrip",
        seed_sensitive=False,
        why="UTF-8 round-trip; does not consume RNG.",
        fn=test_string_roundtrip,
        planted=None,
    ),
    SR.TestSpec(
        id="test_unit_interval",
        seed_sensitive=True,
        why="Draws from the injected RNG; assertion is the unit-interval property, which must hold for every seed.",
        fn=test_unit_interval,
        planted=None,
    ),
    SR.TestSpec(
        id="test_shuffle_preserves_multiset",
        seed_sensitive=True,
        why="Shuffles via the injected RNG; assertion is multiset equality, which must hold for every seed.",
        fn=test_shuffle_preserves_multiset,
        planted=None,
    ),
    SR.TestSpec(
        id="test_planted_narrow_shuffle",
        seed_sensitive=False,
        why="Falsely declared insensitive. Planted control: assertion pins one permutation.",
        fn=test_planted_narrow_shuffle,
        planted="narrow-assertion",
    ),
    SR.TestSpec(
        id="test_planted_hidden_counter_flake",
        seed_sensitive=False,
        why="Falsely declared insensitive. Planted C11 control: hidden call counter, not the seed.",
        fn=test_planted_hidden_counter_flake,
        planted="flaky-C11",
    ),
]
