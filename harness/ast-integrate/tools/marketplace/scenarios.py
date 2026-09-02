"""Deterministic SAT/UNSAT fixtures for the marketplace resolver (IMP-0083)."""
from __future__ import annotations

import copy
import random
from typing import Any


def sat_diamond_index() -> dict[str, list[dict[str, Any]]]:
    return {
        "foo": [
            {"version": "1.0.0", "deps": [{"name": "shared", "range": "^1.0.0"}]}
        ],
        "bar": [
            {"version": "1.0.0", "deps": [{"name": "shared", "range": "^1.0.0"}]}
        ],
        "shared": [
            {"version": "1.0.0", "deps": []},
            {"version": "1.1.0", "deps": []},
            {"version": "2.0.0", "deps": []},
        ],
    }


def sat_diamond_request() -> list[dict[str, str]]:
    return [
        {"name": "foo", "range": "^1.0.0"},
        {"name": "bar", "range": "^1.0.0"},
    ]


def expected_diamond_solution() -> dict[str, str]:
    return {"foo": "1.0.0", "bar": "1.0.0", "shared": "1.1.0"}


def unsat_conflict_index() -> dict[str, list[dict[str, Any]]]:
    return {
        "foo": [
            {"version": "1.0.0", "deps": [{"name": "shared", "range": "^1.0.0"}]}
        ],
        "bar": [
            {"version": "1.0.0", "deps": [{"name": "shared", "range": "^2.0.0"}]}
        ],
        "shared": [
            {"version": "1.0.0", "deps": []},
            {"version": "1.1.0", "deps": []},
            {"version": "2.0.0", "deps": []},
            {"version": "2.1.0", "deps": []},
        ],
    }


def unsat_conflict_request() -> list[dict[str, str]]:
    return [
        {"name": "foo", "range": "^1.0.0"},
        {"name": "bar", "range": "^1.0.0"},
    ]


def single_constraint_unsat_index() -> dict[str, list[dict[str, Any]]]:
    return {"only": [{"version": "1.0.0", "deps": []}]}


def shuffle_index(index: dict[str, list[dict[str, Any]]], seed: int) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(seed)
    keys = list(index)
    rng.shuffle(keys)
    out: dict[str, list[dict[str, Any]]] = {}
    for key in keys:
        rows = copy.deepcopy(index[key])
        rng.shuffle(rows)
        out[key] = rows
    return out
