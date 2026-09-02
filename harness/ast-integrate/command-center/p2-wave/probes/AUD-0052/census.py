"""Live census: shuffled seeds vs identical-order repeats."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import constants as C  # noqa: E402
import shuffle_plugin as P  # noqa: E402


def catalog_unit() -> dict:
    data = json.loads(
        (C.REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == C.UNIT:
            return unit
    raise RuntimeError("AUD-0052 missing from catalog")


def _nid_suffix(nid: str, name: str) -> bool:
    return nid.endswith(f"::{name}") and "/AUD-0052/lab/" in nid.replace("\\", "/")


def find_lab(items: list[dict], name: str) -> str:
    hits = [i["nodeid"] for i in items if _nid_suffix(i["nodeid"], name)]
    if len(hits) != 1:
        raise RuntimeError(f"lab node {name} hits={hits}")
    return hits[0]


def classify(
    declaration: dict,
    shuffle_runs: list[dict],
    repeat_runs: list[dict],
) -> dict[str, list[str]]:
    nids = [
        nid
        for nid, outcome in declaration["outcomes"].items()
        if outcome != "not-run"
    ]
    order_dependent: list[str] = []
    flakes: list[str] = []
    stable_pass: list[str] = []
    for nid in nids:
        decl = declaration["outcomes"].get(nid)
        shuffle_set = {run["outcomes"].get(nid) for run in shuffle_runs}
        repeat_set = {run["outcomes"].get(nid) for run in repeat_runs}
        is_flake = len(repeat_set) > 1
        if is_flake:
            flakes.append(nid)
            continue
        if decl == "passed" and "failed" in shuffle_set:
            order_dependent.append(nid)
            continue
        if decl == "passed" and shuffle_set == {"passed"} and repeat_set == {"passed"}:
            stable_pass.append(nid)
    return {
        "order_dependent": order_dependent,
        "flakes": flakes,
        "stable_pass": stable_pass,
    }


def measure() -> dict[str, Any]:
    lab_items = P.collect_tests(C.REPO / C.LAB_REL, C.REPO)
    product_items = P.collect_tests(C.REPO / C.PRODUCT_ROOT_REL, C.REPO)
    if len(lab_items) < 5:
        raise RuntimeError(f"lab too small n={len(lab_items)}")
    if len(product_items) < C.PRODUCT_COLLECT_FLOOR:
        raise RuntimeError(
            f"product collect below floor n={len(product_items)} "
            f"floor={C.PRODUCT_COLLECT_FLOOR}"
        )

    lab_decl_order = P.nodeids(lab_items)
    identity_orders = [P.nodeids(lab_items) for _ in C.SEEDS]
    lab_shuffle_orders = {
        str(seed): P.nodeids(P.shuffle_items(lab_items, seed)) for seed in C.SEEDS
    }
    product_shuffle_orders = {
        str(seed): P.nodeids(P.shuffle_items(product_items, seed)) for seed in C.SEEDS
    }
    lab_orders_differ = P.orders_differ(list(lab_shuffle_orders.values()))
    product_orders_differ = P.orders_differ(list(product_shuffle_orders.values()))
    identity_equal = P.orders_differ(identity_orders) is False
    if not lab_orders_differ:
        raise RuntimeError("lab shuffle did not reorder across seeds")
    if not product_orders_differ:
        raise RuntimeError("product shuffle did not reorder across seeds")
    if not identity_equal:
        raise RuntimeError("identity control reordered; detector is not the shuffle")

    declaration = P.run_session(lab_items, repo=C.REPO, repeat_mode=False)
    shuffle_runs = []
    for seed in C.SEEDS:
        run = P.run_session(
            P.shuffle_items(lab_items, seed), repo=C.REPO, repeat_mode=False
        )
        run["seed"] = seed
        shuffle_runs.append(run)

    P.reset_flake_counter()
    repeat_runs = []
    for i in range(C.N_REPEATS):
        run = P.run_session(lab_items, repo=C.REPO, repeat_mode=True)
        run["repeat_index"] = i
        repeat_runs.append(run)

    classes = classify(declaration, shuffle_runs, repeat_runs)
    get_id = find_lab(lab_items, "test_get")
    put_id = find_lab(lab_items, "test_put")
    flake_id = find_lab(lab_items, "test_planted_flake")
    alpha_id = find_lab(lab_items, "test_alpha")
    bravo_id = find_lab(lab_items, "test_bravo")

    get_failed_shuffle = any(
        run["outcomes"].get(get_id) == "failed" for run in shuffle_runs
    )
    get_decl_pass = declaration["outcomes"].get(get_id) == "passed"
    get_repeat_stable = len({run["outcomes"].get(get_id) for run in repeat_runs}) == 1
    flake_varies = len({run["outcomes"].get(flake_id) for run in repeat_runs}) > 1
    put_always = declaration["outcomes"].get(put_id) == "passed" and all(
        run["outcomes"].get(put_id) == "passed" for run in shuffle_runs
    )

    if not get_decl_pass:
        raise RuntimeError("planted order-dep test_get failed in declaration order")
    if not get_failed_shuffle:
        raise RuntimeError("planted order-dep test_get never failed under shuffle")
    if not get_repeat_stable:
        raise RuntimeError("planted order-dep test_get was unstable on identical-order repeats")
    if get_id not in classes["order_dependent"]:
        raise RuntimeError("classifier missed planted order-dep test_get")
    if flake_id not in classes["flakes"]:
        raise RuntimeError("classifier missed planted flake")
    if flake_id in classes["order_dependent"]:
        raise RuntimeError("planted flake misclassified as order-dependent")
    if alpha_id not in classes["stable_pass"] or bravo_id not in classes["stable_pass"]:
        raise RuntimeError("stable lab tests were not stable-pass")
    if not flake_varies:
        raise RuntimeError("planted flake did not vary across identical-order repeats")
    if not put_always:
        raise RuntimeError("test_put was not a stable pass under shuffle")

    return {
        "seeds": list(C.SEEDS),
        "n_repeats": C.N_REPEATS,
        "lab_collected": len(lab_items),
        "product_collected": len(product_items),
        "lab_declaration_order": lab_decl_order,
        "lab_shuffle_orders": lab_shuffle_orders,
        "product_shuffle_orders_heads": {
            seed: order[:8] for seed, order in product_shuffle_orders.items()
        },
        "product_order_fingerprints": {
            seed: [len(order), order[0], order[-1]]
            for seed, order in product_shuffle_orders.items()
        },
        "lab_orders_differ": lab_orders_differ,
        "product_orders_differ": product_orders_differ,
        "identity_equal": identity_equal,
        "declaration_outcomes": declaration["outcomes"],
        "shuffle_outcomes": [
            {"seed": run["seed"], "order": run["order"], "outcomes": run["outcomes"]}
            for run in shuffle_runs
        ],
        "repeat_outcomes": [
            {
                "repeat_index": run["repeat_index"],
                "order": run["order"],
                "outcomes": run["outcomes"],
            }
            for run in repeat_runs
        ],
        "classification": classes,
        "plants": {
            "test_get": get_id,
            "test_put": put_id,
            "test_planted_flake": flake_id,
            "test_alpha": alpha_id,
            "test_bravo": bravo_id,
        },
        "product_executed": 0,
        "product_execution": "NOT-CHECKED",
        "product_execution_reason": (
            "pytest is absent from this worktree (externally-managed env, no venv); "
            "importlib execution of tools/**/test_*.py risks mutating the tree "
            "(retain/revert tests write files). Product tests were collected and "
            "shuffle-reordered only. Lab cohort was executed."
        ),
    }


def probe1_live() -> dict[str, Any]:
    lab_items = P.collect_tests(C.REPO / C.LAB_REL, C.REPO)
    product_items = P.collect_tests(C.REPO / C.PRODUCT_ROOT_REL, C.REPO)
    declaration = P.run_session(lab_items, repo=C.REPO, repeat_mode=False)
    shuffle_runs = []
    for seed in C.SEEDS:
        run = P.run_session(
            P.shuffle_items(lab_items, seed), repo=C.REPO, repeat_mode=False
        )
        run["seed"] = seed
        shuffle_runs.append(run)
    lab_orders = [run["order"] for run in shuffle_runs]
    product_orders = [
        P.nodeids(P.shuffle_items(product_items, seed)) for seed in C.SEEDS
    ]
    identity_orders = [P.nodeids(lab_items) for _ in C.SEEDS]
    get_id = find_lab(lab_items, "test_get")
    return {
        "lab_collected": len(lab_items),
        "product_collected": len(product_items),
        "seeds": list(C.SEEDS),
        "lab_orders_differ": P.orders_differ(lab_orders),
        "product_orders_differ": P.orders_differ(product_orders),
        "identity_equal": not P.orders_differ(identity_orders),
        "declaration_get": declaration["outcomes"].get(get_id),
        "shuffle_get": [run["outcomes"].get(get_id) for run in shuffle_runs],
        "get_id": get_id,
        "lab_orders": lab_orders,
        "declaration_outcomes": declaration["outcomes"],
        "shuffle_outcomes": [run["outcomes"] for run in shuffle_runs],
    }


def artifact_census(doc: dict) -> dict:
    if isinstance(doc.get("census"), dict):
        return doc["census"]
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("census"), dict):
        return report["census"]
    return {}


def artifact_headline(doc: dict) -> int:
    candidates = [doc.get("summary")]
    report = doc.get("report")
    if isinstance(report, dict):
        candidates.append(report.get("summary"))
        try:
            return int(report.get("headline_count"))
        except (TypeError, ValueError):
            pass
    for blob in candidates:
        if isinstance(blob, dict):
            try:
                return int(blob.get("headline_count"))
            except (TypeError, ValueError):
                continue
    return -1


def probe2_live() -> dict[str, Any]:
    lab_items = P.collect_tests(C.REPO / C.LAB_REL, C.REPO)
    P.reset_flake_counter()
    repeats = []
    for i in range(C.N_REPEATS):
        run = P.run_session(lab_items, repo=C.REPO, repeat_mode=True)
        run["repeat_index"] = i
        repeats.append(run)
    get_id = find_lab(lab_items, "test_get")
    flake_id = find_lab(lab_items, "test_planted_flake")
    orders = [run["order"] for run in repeats]
    get_set = {run["outcomes"].get(get_id) for run in repeats}
    flake_set = {run["outcomes"].get(flake_id) for run in repeats}
    return {
        "n_repeats": C.N_REPEATS,
        "identical_order": not P.orders_differ(orders),
        "get_id": get_id,
        "flake_id": flake_id,
        "get_outcomes": [run["outcomes"].get(get_id) for run in repeats],
        "flake_outcomes": [run["outcomes"].get(flake_id) for run in repeats],
        "get_stable": len(get_set) == 1,
        "flake_varies": len(flake_set) > 1,
        "orders": orders,
    }
