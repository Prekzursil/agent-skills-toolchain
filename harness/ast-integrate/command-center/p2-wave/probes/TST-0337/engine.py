#!/usr/bin/env python3
"""Mutation corpus, in-process runner, and full-vs-subset differential for TST-0337."""
from __future__ import annotations

import builtins
import time
import types
from typing import Callable

import product as P
import selector as S

HELPER_OLD = "return VALUE * 3 + OFFSET"
SECRET_OLD = "return VALUE + 100"
PUBLIC_OLD = "return VALUE + OFFSET"
INDEP_OLD = "return VALUE"
MID_OLD = "return h0() + h1()"
ROOT_OLD = "return " + " + ".join(f"{m}_public()" for m in P.MIDS)


def build_mutations() -> list[dict]:
    """At least 100 mutations over the product source. Deterministic ids."""
    muts: list[dict] = []
    n = 0

    def add(module: str, kind: str, old: str, new: str, cls: str) -> None:
        nonlocal n
        n += 1
        muts.append(
            {
                "id": f"m{n:04d}",
                "module": module,
                "file": f"{module}.py",
                "kind": kind,
                "old": old,
                "new": new,
                "class": cls,
            }
        )

    # Helper-only: leaf public() tests stay green; mid/root catch.
    for leaf in P.LEAVES:
        for k in (0, 1, 2, 4, 5, 6, 7, 8, 9):
            add(leaf, "helper-mult", HELPER_OLD, f"return VALUE * {k} + OFFSET", "helper")
        for extra in (10, 20, 30):
            add(
                leaf,
                "helper-add",
                HELPER_OLD,
                f"return VALUE * 3 + OFFSET + {extra}",
                "helper",
            )

    # secret() only the unmapped new-file test catches (plus nothing else).
    for delta in (1, 2):
        add(
            P.LEAVES[0],
            "secret-delta",
            SECRET_OLD,
            f"return VALUE + {100 + delta}",
            "secret",
        )

    # Mid operator: leaf public tests stay green.
    for mid in P.MIDS:
        add(mid, "mid-sub", MID_OLD, "return h0() - h1()", "mid")
        add(mid, "mid-mul", MID_OLD, "return h0() * h1() if False else h0() - h1()", "mid")

    # Independent and root (direct catch by their own tests).
    for extra in (1, 2, 3):
        add(P.INDEPENDENT, "indep-add", INDEP_OLD, f"return VALUE + {extra}", "independent")
    add(P.ROOT, "root-add", ROOT_OLD, ROOT_OLD + " + 1", "root")

    # A few public() mutations so filename-only is not always empty-handed.
    for leaf in P.LEAVES[:4]:
        add(leaf, "public-add", PUBLIC_OLD, "return VALUE + OFFSET + 17", "public")

    if len(muts) < 100:
        raise RuntimeError(f"mutation corpus too small: {len(muts)}")
    return muts


def apply_mutation(sources: dict[str, str], mut: dict) -> dict[str, str]:
    src = sources[mut["module"]]
    if mut["old"] not in src:
        raise ValueError(f"{mut['id']}: old fragment not in {mut['module']}")
    out = dict(sources)
    out[mut["module"]] = src.replace(mut["old"], mut["new"], 1)
    return out


def load_modules(sources: dict[str, str]) -> dict[str, types.ModuleType]:
    bag: dict[str, types.ModuleType] = {}

    def importer(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name in sources:
            return ensure(name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    builtin_ns = dict(vars(builtins))
    builtin_ns["__import__"] = importer

    def ensure(name: str) -> types.ModuleType:
        if name in bag:
            return bag[name]
        mod = types.ModuleType(name)
        bag[name] = mod
        ns = mod.__dict__
        ns["__name__"] = name
        ns["__builtins__"] = builtin_ns
        exec(compile(sources[name], f"{name}.py", "exec"), ns)  # noqa: S102
        return mod

    for name in sources:
        ensure(name)
    return bag


def run_suite(sources: dict[str, str], test_ids: list[str]) -> list[str]:
    mods = load_modules(sources)
    failed: list[str] = []
    for tid in test_ids:
        try:
            P.run_one_test(tid, mods)
        except AssertionError:
            failed.append(tid)
    return failed


def make_sound_selector() -> S.CoverageMapSelector:
    return S.CoverageMapSelector(P.coverage_map(), P.all_test_ids())


def make_graph_selector() -> S.DependencyGraphSelector:
    return S.DependencyGraphSelector(P.mapped_tests(), P.import_graph(), P.all_test_ids())


def make_unsound_selector() -> S.FilenameOnlySelector:
    return S.FilenameOnlySelector(P.all_test_ids())


def _time_saved(n_muts: int, n_tests: int, selected_sizes: list[int], full_s: float, sub_s: float) -> dict:
    full_execs = n_muts * n_tests
    sub_execs = int(sum(selected_sizes))
    saved_execs = full_execs - sub_execs
    return {
        "full_suite_test_executions": full_execs,
        "subset_test_executions": sub_execs,
        "executions_saved": saved_execs,
        "executions_saved_ratio": (saved_execs / full_execs) if full_execs else 0.0,
        "full_suite_seconds": round(full_s, 6),
        "subset_seconds": round(sub_s, 6),
        "seconds_saved": round(full_s - sub_s, 6),
        "mean_selected": (sum(selected_sizes) / len(selected_sizes)) if selected_sizes else 0.0,
        "full_suite_width": n_tests,
    }


def run_differential(selector, mutations: list[dict] | None = None) -> dict:
    sources = P.product_sources()
    tests = P.all_test_ids()
    mutations = list(mutations if mutations is not None else build_mutations())
    baseline_fail = run_suite(sources, tests)
    if baseline_fail:
        raise RuntimeError(f"unmutated product is not green: {baseline_fail}")

    caught_full: list[str] = []
    caught_subset: list[str] = []
    miss_list: list[dict] = []
    survivors: list[str] = []
    selected_sizes: list[int] = []
    per: list[dict] = []

    t_full = t_sub = 0.0
    for mut in mutations:
        mutated = apply_mutation(sources, mut)
        t0 = time.perf_counter()
        full_failed = run_suite(mutated, tests)
        t_full += time.perf_counter() - t0
        selected = selector.select([mut["file"]])
        selected_sizes.append(len(selected))
        t1 = time.perf_counter()
        sub_failed = run_suite(mutated, selected)
        t_sub += time.perf_counter() - t1

        full_caught = bool(full_failed)
        sub_caught = bool(sub_failed)
        if full_caught:
            caught_full.append(mut["id"])
        else:
            survivors.append(mut["id"])
        if sub_caught:
            caught_subset.append(mut["id"])
        missed = full_caught and not sub_caught
        if missed:
            miss_list.append(
                {
                    "mutation_id": mut["id"],
                    "file": mut["file"],
                    "module": mut["module"],
                    "kind": mut["kind"],
                    "class": mut["class"],
                    "full_failed_tests": full_failed,
                    "selected_tests": selected,
                    "subset_failed_tests": sub_failed,
                }
            )
        per.append(
            {
                "id": mut["id"],
                "file": mut["file"],
                "class": mut["class"],
                "full_caught": full_caught,
                "subset_caught": sub_caught,
                "selected_n": len(selected),
                "missed": missed,
            }
        )

    return {
        "selector_kind": getattr(selector, "kind", type(selector).__name__),
        "n_mutations": len(mutations),
        "n_tests": len(tests),
        "caught_by_full_suite": len(caught_full),
        "caught_by_subset": len(caught_subset),
        "survivors_full_suite": len(survivors),
        "miss_count": len(miss_list),
        "miss_list": miss_list,
        "sound": len(miss_list) == 0,
        "time_saved": _time_saved(len(mutations), len(tests), selected_sizes, t_full, t_sub),
        "caught_full_ids": caught_full,
        "caught_subset_ids": caught_subset,
        "per_mutation": per,
    }


def newfile_case() -> dict:
    """A test not in the coverage map must be SELECTED for every change."""
    sel = make_sound_selector()
    cmap = P.coverage_map()
    if P.NEWFILE_TEST in cmap:
        raise RuntimeError("new-file test leaked into the coverage map")
    unmapped = [t for t in P.all_test_ids() if t not in cmap]
    checks = []
    for changed in (
        [f"{P.LEAVES[0]}.py"],
        [f"{P.INDEPENDENT}.py"],
        ["root.py"],
        [f"{P.MIDS[0]}.py"],
    ):
        selected = sel.select(changed)
        checks.append(
            {
                "changed": changed,
                "newfile_selected": P.NEWFILE_TEST in selected,
                "all_unmapped_selected": all(t in selected for t in unmapped),
                "selected": selected,
            }
        )
    # Live mutation: secret() is only caught by the unmapped test.
    secret_muts = [m for m in build_mutations() if m["class"] == "secret"]
    if not secret_muts:
        raise RuntimeError("no secret() mutations in corpus")
    sources = P.product_sources()
    mutated = apply_mutation(sources, secret_muts[0])
    full_failed = run_suite(mutated, P.all_test_ids())
    mapped_only = [t for t in P.all_test_ids() if t in cmap]
    mapped_failed = run_suite(mutated, mapped_only)
    with_new = run_suite(mutated, mapped_only + [P.NEWFILE_TEST])
    return {
        "unmapped_tests": unmapped,
        "checks": checks,
        "all_changes_select_newfile": all(c["newfile_selected"] for c in checks),
        "secret_mutation_id": secret_muts[0]["id"],
        "secret_file": secret_muts[0]["file"],
        "full_failed": full_failed,
        "mapped_only_failed": mapped_failed,
        "mapped_plus_newfile_failed": with_new,
        "mapped_only_misses_secret": (not mapped_failed) and bool(full_failed),
        "newfile_is_the_catch": P.NEWFILE_TEST in full_failed
        and P.NEWFILE_TEST in with_new
        and not mapped_failed,
    }


def noml_case() -> dict:
    sound = make_sound_selector()
    graph = make_graph_selector()
    pred = S.PredictiveSelector(P.all_test_ids())
    S.reject_if_non_deterministic(sound)
    S.reject_if_non_deterministic(graph)
    rejected = False
    message = ""
    try:
        S.reject_if_non_deterministic(pred)
    except S.SelectorRejected as exc:
        rejected = True
        message = str(exc)
    # Same changed file: coverage-map and dep-graph must agree.
    changed = [f"{P.LEAVES[0]}.py"]
    a = sorted(sound.select(changed))
    b = sorted(graph.select(changed))
    return {
        "sound_kind": sound.kind,
        "graph_kind": graph.kind,
        "predictive_kind": pred.kind,
        "sound_accepted": True,
        "graph_accepted": True,
        "predictive_rejected": rejected,
        "reject_message": message,
        "graph_agrees_with_map": a == b,
        "selected_on_leaf_00": a,
    }


def run() -> dict:
    sound = run_differential(make_sound_selector())
    unsound = run_differential(make_unsound_selector())
    graph = run_differential(make_graph_selector())
    nf = newfile_case()
    ml = noml_case()
    ok = (
        sound["n_mutations"] >= 100
        and sound["sound"]
        and graph["sound"]
        and (not unsound["sound"])
        and unsound["miss_count"] > 0
        and nf["all_changes_select_newfile"]
        and nf["newfile_is_the_catch"]
        and ml["predictive_rejected"]
        and ml["graph_agrees_with_map"]
        and sound["caught_by_full_suite"] > 0
    )
    return {
        "ok": ok,
        "sound": sound,
        "unsound_filename_only": unsound,
        "dependency_graph": graph,
        "newfile": nf,
        "noml": ml,
        "both_states": {
            "known_good_coverage_map_misses": sound["miss_count"],
            "known_broken_filename_only_misses": unsound["miss_count"],
            "discriminates": sound["sound"] and unsound["miss_count"] > 0,
        },
    }
