"""Seeded shuffle runner and order-dependence classifier for TST-0127.

Re-running the same recorded seed is a reproduction, not a retry: order and
per-test outcomes must match. Same-order repeats (TST-0032 shape) must also
match — that is flakiness, not order dependence.
"""
from __future__ import annotations

import ast
import hashlib
import random
from pathlib import Path
from typing import Any

from suite import (
    ALWAYS_FAIL,
    INDEPENDENTS_PASS,
    NODE_IDS,
    PLANT_CHANNELS,
    PLANTED_READERS,
    PLANTED_WRITERS,
    RunState,
    bind_tests,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

PRIMARY_SEEDS: list[int] = [12701, 12702, 12703, 12704, 12705, 12706, 12707, 12708]


def seeded_order(node_ids: list[str], seed: int) -> list[str]:
    rng = random.Random(seed)
    order = list(node_ids)
    rng.shuffle(order)
    return order


def run_fixed_order(order: list[str]) -> dict[str, Any]:
    state = RunState()
    try:
        state.reset()
        tests = bind_tests(state)
        outcomes: dict[str, str] = {}
        errors: dict[str, str] = {}
        for nid in order:
            try:
                tests[nid]()
                outcomes[nid] = "PASS"
            except Exception as exc:
                outcomes[nid] = "FAIL"
                errors[nid] = f"{type(exc).__name__}: {exc}"
        return {"order": list(order), "outcomes": outcomes, "errors": errors}
    finally:
        state.cleanup()


def run_seed(seed: int, node_ids: list[str] | None = None) -> dict[str, Any]:
    ids = list(node_ids or NODE_IDS)
    order = seeded_order(ids, seed)
    result = run_fixed_order(order)
    result["seed"] = seed
    return result


def pairwise_suspects(test_id: str, runs: list[dict[str, Any]]) -> list[str]:
    others: set[str] = set()
    for run in runs:
        others.update(run["order"])
    others.discard(test_id)
    suspects: list[str] = []
    for writer in sorted(others):
        before: list[str] = []
        after: list[str] = []
        for run in runs:
            order = run["order"]
            if test_id not in order or writer not in order:
                continue
            outcome = run["outcomes"][test_id]
            if order.index(writer) < order.index(test_id):
                before.append(outcome)
            else:
                after.append(outcome)
        if not before or not after:
            continue
        if all(x == "PASS" for x in before) and all(x == "FAIL" for x in after):
            suspects.append(writer)
    return suspects


def classify_tests(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for nid in NODE_IDS:
        series = [run["outcomes"][nid] for run in runs]
        unique = sorted(set(series))
        invariant = len(unique) == 1
        suspects = [] if invariant else pairwise_suspects(nid, runs)
        planted = PLANT_CHANNELS.get(nid)
        if planted:
            shared = {
                "channel": planted["channel"],
                "symbol": planted["symbol"],
                "kind": planted["kind"],
                "known_writer": planted["writer"],
                "pairwise_suspects": suspects,
            }
        elif not invariant:
            shared = {
                "channel": "unattributed-cross-test-state",
                "symbol": "unknown",
                "kind": "unknown",
                "known_writer": None,
                "pairwise_suspects": suspects,
            }
        else:
            shared = None
        rows.append(
            {
                "id": nid,
                "outcomes": series,
                "unique_outcomes": unique,
                "invariant": invariant,
                "classification": "INVARIANT" if invariant else "ORDER_DEPENDENT",
                "suspected_shared_state": shared,
                "pass_ratio": series.count("PASS") / len(series) if series else 0.0,
            }
        )
    return rows


def planted_has_both(runs: list[dict[str, Any]]) -> bool:
    for nid in PLANTED_READERS:
        uniq = {run["outcomes"][nid] for run in runs}
        if uniq != {"PASS", "FAIL"}:
            return False
    return True


def extend_seeds(seeds: list[int], runs: list[dict[str, Any]]) -> None:
    extra = 0
    while not planted_has_both(runs) and extra < 64:
        cand = 13000 + extra
        extra += 1
        if cand in seeds:
            continue
        seeds.append(cand)
        runs.append(run_seed(cand))


def reproduce_seed(seed: int) -> dict[str, Any]:
    a = run_seed(seed)
    b = run_seed(seed)
    return {
        "seed": seed,
        "orders_equal": a["order"] == b["order"],
        "outcomes_equal": a["outcomes"] == b["outcomes"],
        "first": {"order": a["order"], "outcomes": a["outcomes"]},
        "second": {"order": b["order"], "outcomes": b["outcomes"]},
    }


def flake_repeats(order: list[str], n: int = 5) -> dict[str, Any]:
    repeats = [run_fixed_order(order) for _ in range(n)]
    outcomes = [r["outcomes"] for r in repeats]
    identical = all(o == outcomes[0] for o in outcomes[1:])
    return {
        "n": n,
        "order": list(order),
        "identical": identical,
        "outcomes": outcomes,
        "classification": "DETERMINISTIC-AT-FIXED-ORDER" if identical else "FLAKY",
    }


def collect_repo_inventory(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    files: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for path in sorted(root.glob("tools/**/tests/test_*.py")):
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw)
        tree = ast.parse(raw.decode("utf-8"))
        names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        files.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
                "bytes": len(raw.replace(b"\r\n", b"\n")),
                "test_functions": names,
                "n_tests": len(names),
            }
        )
    try:
        import pytest  # noqa: F401

        pytest_installed = True
    except ImportError:
        pytest_installed = False
    return {
        "n_files": len(files),
        "n_tests": sum(f["n_tests"] for f in files),
        "content_sha256": digest.hexdigest(),
        "pytest_installed": pytest_installed,
        "files": files,
    }


def run_census(seeds: list[int] | None = None) -> dict[str, Any]:
    used = list(seeds or PRIMARY_SEEDS)
    runs = [run_seed(s) for s in used]
    extend_seeds(used, runs)
    rows = classify_tests(runs)
    orders = [tuple(r["order"]) for r in runs]
    declaration = tuple(NODE_IDS)
    shuffled_away = sum(1 for o in orders if o != declaration)
    repro = reproduce_seed(used[0])
    flake = flake_repeats(runs[0]["order"], n=5)
    od = [r for r in rows if r["classification"] == "ORDER_DEPENDENT"]
    return {
        "seeds": used,
        "n_orders": len(runs),
        "n_distinct_orders": len(set(orders)),
        "declaration_order": list(NODE_IDS),
        "n_shuffled_away_from_declaration": shuffled_away,
        "runs": [
            {
                "seed": r["seed"],
                "order": r["order"],
                "outcomes": r["outcomes"],
                "errors": r["errors"],
            }
            for r in runs
        ],
        "tests": rows,
        "order_dependent": [
            {
                "id": r["id"],
                "classification": r["classification"],
                "suspected_shared_state": r["suspected_shared_state"],
                "pass_ratio": r["pass_ratio"],
            }
            for r in od
        ],
        "reproduction": repro,
        "same_order_repeats": flake,
        "controls": {
            "planted_readers_both_outcomes": planted_has_both(runs),
            "independents_invariant": all(
                next(t for t in rows if t["id"] == i)["invariant"]
                for i in INDEPENDENTS_PASS
            ),
            "always_fail_invariant_fail": next(
                t for t in rows if t["id"] == ALWAYS_FAIL
            )["unique_outcomes"]
            == ["FAIL"],
            "writers_always_pass": all(
                next(t for t in rows if t["id"] == w)["unique_outcomes"] == ["PASS"]
                for w in PLANTED_WRITERS
            ),
            "shuffle_actually_reordered": shuffled_away >= 1
            and len(set(orders)) >= 2,
        },
    }
