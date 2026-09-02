#!/usr/bin/env python3
"""Order-dependence detector for TST-0344.

Run a registered suite in seeded randomised orders, bisect every failure to
a minimal ordered pair, and classify the pair as shared-state leakage.

Distinct from:
  C11 / TST-0336 — flake: outcome varies under the SAME order
  C18 / TST-0343 — seed sensitivity: outcome varies with the TEST rng seed,
                   not with relative order
Repair is different: order-dependence is almost always a fixture that mutates
global/session state. A pass across three permutations is weak evidence.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Callable, Iterable

UNIT_ID = "TST-0344"
FROZEN_CLOCK_NS = 1_725_000_000_000_000_000
FIXED_PID = 344
PERM_SEEDS = tuple(range(34401, 34413))  # 12 recorded shuffle seeds (>=10)
SAME_ORDER_REPEATS = 5
THREE_PERM_WEAK = (
    "A pass across three permutations is weak evidence and must be labelled as such."
)

# Declaration order: reader before writer (hidden-setup fails by default);
# victim before polluter (pollution passes by default). Independents are
# decoys the bisection must drop.
DECLARATION_ORDER = [
    "test_alpha_independent",
    "test_plant_reader",
    "test_beta_independent",
    "test_gamma_independent",
    "test_plant_writer",
    "test_delta_independent",
    "test_plant_victim",
    "test_epsilon_independent",
    "test_zeta_independent",
    "test_plant_polluter",
    "test_eta_independent",
    "test_seed_declared_ok",
]

PLANT_WRITER = "test_plant_writer"
PLANT_READER = "test_plant_reader"
PLANT_POLLUTER = "test_plant_polluter"
PLANT_VICTIM = "test_plant_victim"
PLANT_COIN = "test_plant_coin_flip"
SEED_TEST = "test_seed_declared_ok"

EXPECTED_PAIRS = [
    (PLANT_WRITER, PLANT_READER, "hidden-setup"),
    (PLANT_POLLUTER, PLANT_VICTIM, "pollution"),
]


class AssertionFail(Exception):
    """Test assertion failure (not an engine bug)."""


@dataclass
class Session:
    """Shared fixture state for one permutation (not reset between tests)."""

    token: str | None = None
    clean: bool = True
    test_rng_seed: int = 0
    calls: list[str] = field(default_factory=list)


@dataclass
class FlakeBox:
    """Module-lifetime counter: same order, different repeats → different outcome."""

    n: int = 0

    def odd_fail(self) -> None:
        self.n += 1
        if self.n % 2 == 1:
            raise AssertionFail("coin-flip: odd call (C11 flake plant)")


@dataclass
class RunConfig:
    seeds: tuple[int, ...] = PERM_SEEDS
    isolate_per_test: bool = False
    include_coin_flip: bool = False
    test_rng_seed: int = 0
    plants: bool = True
    declaration: tuple[str, ...] | None = None


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionFail(msg)


def test_alpha_independent(session: Session) -> None:
    session.calls.append("alpha")
    _assert(True, "alpha")


def test_beta_independent(session: Session) -> None:
    session.calls.append("beta")
    _assert(1 + 1 == 2, "beta")


def test_gamma_independent(session: Session) -> None:
    session.calls.append("gamma")
    _assert(len("gamma") == 5, "gamma")


def test_delta_independent(session: Session) -> None:
    session.calls.append("delta")
    _assert("d" in "delta", "delta")


def test_epsilon_independent(session: Session) -> None:
    session.calls.append("epsilon")
    _assert(not session.calls[-1].startswith("z"), "epsilon")


def test_zeta_independent(session: Session) -> None:
    session.calls.append("zeta")
    _assert(pow(2, 3) == 8, "zeta")


def test_eta_independent(session: Session) -> None:
    session.calls.append("eta")
    _assert(sorted((3, 1, 2)) == [1, 2, 3], "eta")


def test_plant_writer(session: Session) -> None:
    """Writes global/session state another test reads (hidden-setup helper)."""
    session.calls.append("writer")
    session.token = "written"


def test_plant_reader(session: Session) -> None:
    """Passes only because writer ran first. Shared-state leakage."""
    session.calls.append("reader")
    _assert(
        session.token == "written",
        "reader required writer-first token; this is hidden-setup leakage",
    )


def test_plant_polluter(session: Session) -> None:
    """Mutates a fixture the victim assumes is default-clean."""
    session.calls.append("polluter")
    session.clean = False


def test_plant_victim(session: Session) -> None:
    """Fails if polluter ran first. Pollution, not a flake."""
    session.calls.append("victim")
    _assert(session.clean is True, "victim saw polluted fixture (polluter ran first)")


def test_seed_declared_ok(session: Session) -> None:
    """Seed-registered: uses test_rng_seed, not shuffle seed.

    Default seed 0 always passes. Seed 99 trips a narrow assertion (C18).
    Relative order must not change this outcome.
    """
    session.calls.append("seed")
    rng = random.Random(session.test_rng_seed)
    draw = rng.randint(0, 10)
    if session.test_rng_seed == 99:
        raise AssertionFail(f"narrow assertion on test rng seed 99 draw={draw}")
    _assert(0 <= draw <= 10, "seed draw out of range")


def make_coin(box: FlakeBox) -> Callable[[Session], None]:
    def test_plant_coin_flip(session: Session) -> None:
        session.calls.append("coin")
        box.odd_fail()

    test_plant_coin_flip.__name__ = PLANT_COIN
    return test_plant_coin_flip


CORE_TESTS: dict[str, Callable[[Session], None]] = {
    "test_alpha_independent": test_alpha_independent,
    "test_beta_independent": test_beta_independent,
    "test_gamma_independent": test_gamma_independent,
    "test_delta_independent": test_delta_independent,
    "test_epsilon_independent": test_epsilon_independent,
    "test_zeta_independent": test_zeta_independent,
    "test_eta_independent": test_eta_independent,
    PLANT_WRITER: test_plant_writer,
    PLANT_READER: test_plant_reader,
    PLANT_POLLUTER: test_plant_polluter,
    PLANT_VICTIM: test_plant_victim,
    SEED_TEST: test_seed_declared_ok,
}


def registry_ids(cfg: RunConfig) -> list[str]:
    ids = list(cfg.declaration or DECLARATION_ORDER)
    if not cfg.plants:
        ids = [i for i in ids if i not in {PLANT_WRITER, PLANT_READER, PLANT_POLLUTER, PLANT_VICTIM}]
    if cfg.include_coin_flip and PLANT_COIN not in ids:
        ids.append(PLANT_COIN)
    return ids


def shuffle_order(ids: list[str], seed: int) -> list[str]:
    rng = random.Random(seed)
    out = list(ids)
    rng.shuffle(out)
    return out


def run_order(
    order: list[str],
    *,
    isolate_per_test: bool = False,
    test_rng_seed: int = 0,
    tests: dict[str, Callable[[Session], None]] | None = None,
) -> dict:
    fns = tests or CORE_TESTS
    session = Session(test_rng_seed=test_rng_seed)
    results: list[dict] = []
    for name in order:
        if isolate_per_test:
            session = Session(test_rng_seed=test_rng_seed)
        fn = fns.get(name)
        if fn is None:
            results.append({"id": name, "result": "FAIL", "error": f"unregistered:{name}"})
            continue
        try:
            fn(session)
            results.append({"id": name, "result": "PASS", "error": None})
        except AssertionFail as exc:
            results.append({"id": name, "result": "FAIL", "error": str(exc)})
    failed = [r["id"] for r in results if r["result"] == "FAIL"]
    outcomes = {r["id"]: r["result"] for r in results}
    return {
        "order": list(order),
        "results": results,
        "failed": failed,
        "outcomes": outcomes,
        "all_pass": not failed,
    }


def _predicate_target_fails(
    preds: list[str],
    target: str,
    *,
    isolate_per_test: bool,
    test_rng_seed: int,
    tests: dict[str, Callable[[Session], None]],
) -> bool:
    row = run_order(
        preds + [target],
        isolate_per_test=isolate_per_test,
        test_rng_seed=test_rng_seed,
        tests=tests,
    )
    return target in row["failed"]


def _predicate_target_passes(
    preds: list[str],
    target: str,
    *,
    isolate_per_test: bool,
    test_rng_seed: int,
    tests: dict[str, Callable[[Session], None]],
) -> bool:
    return not _predicate_target_fails(
        preds,
        target,
        isolate_per_test=isolate_per_test,
        test_rng_seed=test_rng_seed,
        tests=tests,
    )


def _bisect_preds(
    preds: list[str],
    target: str,
    want_fail: bool,
    *,
    isolate_per_test: bool,
    test_rng_seed: int,
    tests: dict[str, Callable[[Session], None]],
) -> list[str]:
    """Bisection (delta-split) of predecessors that preserve target outcome."""

    def pred_ok(chunk: list[str]) -> bool:
        fails = _predicate_target_fails(
            chunk,
            target,
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=tests,
        )
        return fails if want_fail else (not fails)

    if not pred_ok(preds):
        return []
    remaining = list(preds)
    while len(remaining) > 1:
        mid = len(remaining) // 2
        left, right = remaining[:mid], remaining[mid:]
        if pred_ok(left):
            remaining = left
            continue
        if pred_ok(right):
            remaining = right
            continue
        # Interaction of both halves: bisect each and concatenate, preserving order.
        left_min = _bisect_preds(
            left,
            target,
            want_fail,
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=tests,
        )
        right_min = _bisect_preds(
            right,
            target,
            want_fail,
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=tests,
        )
        return left_min + right_min
    return remaining


def bisect_failure(
    failing_order: list[str],
    failed_id: str,
    *,
    all_ids: list[str],
    isolate_per_test: bool = False,
    test_rng_seed: int = 0,
    tests: dict[str, Callable[[Session], None]] | None = None,
) -> dict:
    """Minimal ordered pair that reproduces the order-dependent outcome of failed_id."""
    fns = tests or CORE_TESTS
    if failed_id not in failing_order:
        return {"id": failed_id, "kind": "not-in-order", "pair": None}
    idx = failing_order.index(failed_id)
    predecessors = failing_order[:idx]
    alone = run_order(
        [failed_id],
        isolate_per_test=isolate_per_test,
        test_rng_seed=test_rng_seed,
        tests=fns,
    )
    alone_fail = failed_id in alone["failed"]

    if not alone_fail:
        # Pollution: a predecessor causes the failure. Bisect the prefix.
        culprits = _bisect_preds(
            predecessors,
            failed_id,
            True,
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=fns,
        )
        pair = [culprits[0], failed_id] if len(culprits) == 1 else None
        st = run_order(
            [culprits[0], failed_id] if culprits else [failed_id],
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=fns,
        ) if culprits else alone
        ts = run_order(
            [failed_id, culprits[0]] if culprits else [failed_id],
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=fns,
        ) if culprits else alone
        return {
            "id": failed_id,
            "kind": "pollution" if pair else "pollution-unresolved",
            "classification": "shared-state-leakage",
            "not_flake": True,
            "not_seed_sensitivity": True,
            "alone": "PASS",
            "culprits": culprits,
            "pair": pair,
            "pair_order_st": st.get("outcomes"),
            "pair_order_ts": ts.get("outcomes"),
            "failing_prefix_len": len(predecessors),
        }

    # Hidden-setup: test fails alone. Find a helper among registered ids that
    # makes it pass when run first. Prefer helpers that appear after it in the
    # failing permutation (they did not run before it, which is why it failed).
    after = failing_order[idx + 1 :]
    helpers_tried = after + [i for i in all_ids if i != failed_id and i not in after]
    helper = None
    for cand in helpers_tried:
        row = run_order(
            [cand, failed_id],
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=fns,
        )
        if failed_id not in row["failed"]:
            helper = cand
            break
    pair = [helper, failed_id] if helper else None
    st = (
        run_order(
            [helper, failed_id],
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=fns,
        )
        if helper
        else None
    )
    ts = (
        run_order(
            [failed_id, helper],
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=fns,
        )
        if helper
        else None
    )
    return {
        "id": failed_id,
        "kind": "hidden-setup" if pair else "hidden-setup-unresolved",
        "classification": "shared-state-leakage",
        "not_flake": True,
        "not_seed_sensitivity": True,
        "alone": "FAIL",
        "helper": helper,
        "pair": pair,
        "pair_order_st": None if st is None else st.get("outcomes"),
        "pair_order_ts": None if ts is None else ts.get("outcomes"),
        "failing_prefix_len": len(predecessors),
    }


def confirm_relative_order_pairs(
    ids: list[str],
    varying: Iterable[str],
    *,
    isolate_per_test: bool,
    test_rng_seed: int,
    tests: dict[str, Callable[[Session], None]],
) -> list[dict]:
    """Independent of permutation bisection: S before T vs T before S."""
    pairs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for t in varying:
        for s in ids:
            if s == t:
                continue
            st = run_order(
                [s, t],
                isolate_per_test=isolate_per_test,
                test_rng_seed=test_rng_seed,
                tests=tests,
            )
            ts = run_order(
                [t, s],
                isolate_per_test=isolate_per_test,
                test_rng_seed=test_rng_seed,
                tests=tests,
            )
            t_after_s = st["outcomes"].get(t)
            t_first = ts["outcomes"].get(t)
            if t_after_s == t_first:
                continue
            key = (s, t)
            if key in seen:
                continue
            seen.add(key)
            if t_after_s == "PASS" and t_first == "FAIL":
                kind = "hidden-setup"
            elif t_after_s == "FAIL" and t_first == "PASS":
                kind = "pollution"
            else:
                kind = "order-sensitive-other"
            pairs.append(
                {
                    "pair": [s, t],
                    "kind": kind,
                    "classification": "shared-state-leakage",
                    "t_when_s_first": t_after_s,
                    "t_when_t_first": t_first,
                }
            )
    return pairs


def _matrix_hash(permutations: list[dict]) -> str:
    payload = [
        {"seed": p["seed"], "order": p["order"], "outcomes": p["outcomes"]}
        for p in permutations
    ]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _weak_windows(permutations: list[dict]) -> list[dict]:
    out: list[dict] = []
    for i in range(0, max(0, len(permutations) - 2)):
        window = permutations[i : i + 3]
        all_pass = all(p["all_pass"] for p in window)
        out.append(
            {
                "start_index": i,
                "seeds": [p["seed"] for p in window],
                "all_pass": all_pass,
                "strength": "WEAK" if all_pass else "informative",
                "label": THREE_PERM_WEAK if all_pass else "window contains a failure",
            }
        )
    return out


def build_fns(cfg: RunConfig, box: FlakeBox | None) -> dict[str, Callable[[Session], None]]:
    fns = dict(CORE_TESTS)
    if not cfg.plants:
        def _noop_pass(session: Session) -> None:
            session.calls.append("noop")

        for pid in (PLANT_WRITER, PLANT_READER, PLANT_POLLUTER, PLANT_VICTIM):
            fns[pid] = _noop_pass
    if cfg.include_coin_flip:
        if box is None:
            raise ValueError("coin-flip requested without FlakeBox")
        fns[PLANT_COIN] = make_coin(box)
    return fns


def run_campaign(cfg: RunConfig | None = None) -> dict:
    cfg = cfg or RunConfig()
    box = FlakeBox() if cfg.include_coin_flip else None
    fns = build_fns(cfg, box)
    ids = registry_ids(cfg)
    permutations: list[dict] = []
    orders: list[list[str]] = []
    for seed in cfg.seeds:
        order = shuffle_order(ids, seed)
        orders.append(order)
        row = run_order(
            order,
            isolate_per_test=cfg.isolate_per_test,
            test_rng_seed=cfg.test_rng_seed,
            tests=fns,
        )
        permutations.append(
            {
                "seed": seed,
                "order": order,
                "outcomes": row["outcomes"],
                "failed": row["failed"],
                "all_pass": row["all_pass"],
            }
        )

    # Same-seed shuffle must replay; different seeds must actually reorder.
    replay = [shuffle_order(ids, cfg.seeds[0]) for _ in range(2)]
    same_seed_shuffle_identical = replay[0] == replay[1]
    distinct_orders = len({tuple(o) for o in orders})
    shuffle_moved = any(o != ids for o in orders)

    # Outcome matrix: tests whose result is not constant across permutations.
    names = list(ids)
    varying: list[str] = []
    constant_pass: list[str] = []
    constant_fail: list[str] = []
    mixed: dict[str, dict] = {}
    for name in names:
        bits = [p["outcomes"].get(name) for p in permutations]
        n_fail = sum(1 for b in bits if b == "FAIL")
        n_pass = sum(1 for b in bits if b == "PASS")
        mixed[name] = {"pass": n_pass, "fail": n_fail}
        if n_fail == 0:
            constant_pass.append(name)
        elif n_pass == 0:
            constant_fail.append(name)
        else:
            varying.append(name)

    failing_perms = [p for p in permutations if not p["all_pass"]]
    bisections: list[dict] = []
    for p in failing_perms:
        for failed_id in p["failed"]:
            bisections.append(
                {
                    "seed": p["seed"],
                    "failing_order": p["order"],
                    **bisect_failure(
                        p["order"],
                        failed_id,
                        all_ids=ids,
                        isolate_per_test=cfg.isolate_per_test,
                        test_rng_seed=cfg.test_rng_seed,
                        tests=fns,
                    ),
                }
            )

    relative_pairs = confirm_relative_order_pairs(
        ids,
        varying,
        isolate_per_test=cfg.isolate_per_test,
        test_rng_seed=cfg.test_rng_seed,
        tests=fns,
    )

    # Deduplicate bisection pairs.
    unique_pairs: list[list[str]] = []
    for b in bisections:
        pair = b.get("pair")
        if pair and pair not in unique_pairs:
            unique_pairs.append(pair)

    expected_found = []
    for a, b, kind in EXPECTED_PAIRS:
        found = any(p == [a, b] for p in unique_pairs) or any(
            r.get("pair") == [a, b] for r in relative_pairs
        )
        expected_found.append({"pair": [a, b], "kind": kind, "found": found})

    n = len(permutations)
    evidence_strength = (
        "ADEQUATE"
        if n >= 10
        else ("WEAK" if n >= 1 else "ABSENT")
    )
    if n < 10:
        evidence_note = (
            f"{n} permutations executed; {THREE_PERM_WEAK} Need >=10."
        )
    else:
        evidence_note = (
            f"{n} permutations executed (adequate). {THREE_PERM_WEAK}"
        )

    h1 = _matrix_hash(permutations)
    # Reproduce the campaign (fresh fns/box) for same-seed detector check.
    cfg_replay = RunConfig(
        seeds=cfg.seeds,
        isolate_per_test=cfg.isolate_per_test,
        include_coin_flip=False,
        test_rng_seed=cfg.test_rng_seed,
        plants=cfg.plants,
        declaration=cfg.declaration,
    )
    replay_report = None
    if not cfg.include_coin_flip:
        replay_report = run_campaign_matrix_only(cfg_replay)
    h2 = replay_report["matrix_sha256"] if replay_report else None
    same_seed_matrix_identical = (h2 == h1) if h2 else None

    return {
        "unit_id": UNIT_ID,
        "n_permutations": n,
        "seeds": list(cfg.seeds),
        "declaration_order": ids,
        "isolate_per_test": cfg.isolate_per_test,
        "plants": cfg.plants,
        "test_rng_seed": cfg.test_rng_seed,
        "include_coin_flip": cfg.include_coin_flip,
        "shuffle_moved": shuffle_moved,
        "distinct_orders": distinct_orders,
        "same_seed_shuffle_identical": same_seed_shuffle_identical,
        "same_seed_matrix_identical": same_seed_matrix_identical,
        "permutations": permutations,
        "failing_permutations": [
            {"seed": p["seed"], "failed": p["failed"], "order": p["order"]}
            for p in failing_perms
        ],
        "varying_tests": varying,
        "constant_pass": constant_pass,
        "constant_fail": constant_fail,
        "outcome_counts": mixed,
        "bisections": bisections,
        "minimal_pairs": unique_pairs,
        "relative_order_pairs": relative_pairs,
        "expected_planted_pairs": expected_found,
        "planted_pairs_all_found": all(x["found"] for x in expected_found)
        if cfg.plants and not cfg.isolate_per_test
        else None,
        "evidence_strength": evidence_strength,
        "evidence_note": evidence_note,
        "three_permutation_rule": THREE_PERM_WEAK,
        "three_perm_windows": _weak_windows(permutations),
        "classification_rule": (
            "Order-dependence = outcome varies with relative order and is stable "
            "under the same order (not C11 flake) and under a changed TEST rng "
            "seed (not C18). Repair: stop mutating shared fixture/global state."
        ),
        "matrix_sha256": h1,
        "frozen_clock_ns": FROZEN_CLOCK_NS,
        "fixed_pid": FIXED_PID,
    }


def run_campaign_matrix_only(cfg: RunConfig) -> dict:
    """Second pass used only for same-seed matrix hash (no nested replay)."""
    fns = build_fns(cfg, None)
    ids = registry_ids(cfg)
    permutations: list[dict] = []
    for seed in cfg.seeds:
        order = shuffle_order(ids, seed)
        row = run_order(
            order,
            isolate_per_test=cfg.isolate_per_test,
            test_rng_seed=cfg.test_rng_seed,
            tests=fns,
        )
        permutations.append(
            {
                "seed": seed,
                "order": order,
                "outcomes": row["outcomes"],
            }
        )
    return {"matrix_sha256": _matrix_hash(permutations)}


def same_order_repeat_campaign(
    seed: int,
    repeats: int = SAME_ORDER_REPEATS,
    *,
    include_coin_flip: bool = False,
    isolate_per_test: bool = False,
    test_rng_seed: int = 0,
    plants: bool = True,
) -> dict:
    cfg = RunConfig(
        seeds=(seed,),
        isolate_per_test=isolate_per_test,
        include_coin_flip=include_coin_flip,
        test_rng_seed=test_rng_seed,
        plants=plants,
    )
    box = FlakeBox() if include_coin_flip else None
    fns = build_fns(cfg, box)
    ids = registry_ids(cfg)
    order = shuffle_order(ids, seed)
    runs: list[dict] = []
    for i in range(repeats):
        row = run_order(
            order,
            isolate_per_test=isolate_per_test,
            test_rng_seed=test_rng_seed,
            tests=fns,
        )
        runs.append({"repeat": i, "outcomes": row["outcomes"], "failed": row["failed"]})
    unstable: list[str] = []
    for name in ids:
        bits = {r["outcomes"].get(name) for r in runs}
        if len(bits) > 1:
            unstable.append(name)
    return {
        "seed": seed,
        "order": order,
        "repeats": repeats,
        "include_coin_flip": include_coin_flip,
        "runs": runs,
        "unstable_under_same_order": unstable,
        "stable": not unstable,
        "classification": (
            "flake (C11)" if unstable else "same-order-stable (not C11)"
        ),
    }


def seed_sensitivity_campaign(order_seed: int) -> dict:
    """Same shuffle order, two TEST rng seeds. C18 vs order-dependence."""
    ids = list(DECLARATION_ORDER)
    order = shuffle_order(ids, order_seed)
    a = run_order(order, test_rng_seed=0)
    b = run_order(order, test_rng_seed=99)
    changed = [
        n
        for n in ids
        if a["outcomes"].get(n) != b["outcomes"].get(n)
    ]
    order_pair_ids = {PLANT_READER, PLANT_VICTIM, PLANT_WRITER, PLANT_POLLUTER}
    plants_changed = [n for n in changed if n in order_pair_ids]
    return {
        "order_seed": order_seed,
        "order": order,
        "seed_a": 0,
        "seed_b": 99,
        "changed_tests": changed,
        "seed_test_changed": SEED_TEST in changed,
        "plant_order_tests_changed": plants_changed,
        "distinct_from_order_dependence": SEED_TEST in changed and not plants_changed,
    }
