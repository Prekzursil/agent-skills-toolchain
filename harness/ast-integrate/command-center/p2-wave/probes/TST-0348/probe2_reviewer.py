#!/usr/bin/env python3
"""Probe 2: independent AST recount + coverage arithmetic (does not classify()).

Walks planted/live sources with a second, thinner AST pass: counts ast.Assert
and assertion-named calls, recounts vacuous file:line lists from the receipt
against those facts, and recomputes excluding-vacuous coverage from the lists.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ART = REPO / "command-center/receipts/TST-0348.json"
SENTINEL = "SUCCESS:TST-0348"
ASSERT_HELPERS = frozenset({"raises", "warns", "deprecated_call", "fail"})


def fail(msg: str) -> int:
    print(f"FAILED:TST-0348-probe2 {msg}")
    return 1


def basename(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def independent_use_counts(source: str) -> dict:
    tree = ast.parse(source)
    uses = 0
    mentions = 0
    mock_ctors = 0
    swallows = 0
    tests = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            tests += 1
        if isinstance(node, ast.Assert):
            uses += 1
        if isinstance(node, ast.Call):
            name = basename(node.func)
            if name.startswith("assert") or name in ASSERT_HELPERS:
                uses += 1
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "assert" in node.value
        ):
            mentions += 1
        if isinstance(node, ast.Call) and basename(node.func) in {
            "Mock",
            "MagicMock",
            "AsyncMock",
        }:
            mock_ctors += 1
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                tname = basename(handler.type) if handler.type is not None else "bare"
                if tname in {"Exception", "BaseException", "AssertionError", "bare"}:
                    if all(isinstance(s, (ast.Pass, ast.Expr)) for s in handler.body):
                        swallows += 1
    return {
        "tests": tests,
        "uses": uses,
        "mentions": mentions,
        "mock_ctors": mock_ctors,
        "swallows": swallows,
    }


def recompute_from_lists(n_tests: int, union_file_line: list) -> float:
    n_v = len(set(union_file_line))
    if n_tests <= 0:
        return 0.0
    return round(100.0 * (n_tests - n_v) / n_tests, 4)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    fixtures = HERE / "fixtures"
    plants = {
        "planted_no_assertion.py": {"uses": 0, "mentions_min": 1, "swallows": 0},
        "planted_assert_constant.py": {"uses_min": 1, "mentions_min": 0},
        "planted_assert_own_mock.py": {"mock_ctors_min": 1, "uses_min": 1},
        "planted_swallowed.py": {"swallows_min": 1, "uses_min": 1},
        "genuine_known_good.py": {"uses_min": 3, "mentions_min": 1, "swallows": 0},
    }
    observed = {}
    for name, want in plants.items():
        src = (fixtures / name).read_text(encoding="utf-8")
        got = independent_use_counts(src)
        observed[name] = got
        if "uses" in want and got["uses"] != want["uses"]:
            return fail(f"{name} uses={got['uses']} want={want['uses']}")
        if got["uses"] < want.get("uses_min", 0):
            return fail(f"{name} uses={got['uses']} < {want.get('uses_min')}")
        if got["mentions"] < want.get("mentions_min", 0):
            return fail(f"{name} mentions={got['mentions']}")
        if got["mock_ctors"] < want.get("mock_ctors_min", 0):
            return fail(f"{name} mock_ctors={got['mock_ctors']}")
        if "swallows" in want and got["swallows"] != want["swallows"]:
            return fail(f"{name} swallows={got['swallows']}")
        if got["swallows"] < want.get("swallows_min", 0):
            return fail(f"{name} swallows={got['swallows']}")

    # Mention fixture must not be counted as asserting by use-count.
    if observed["planted_no_assertion.py"]["uses"] != 0:
        return fail("mention fixture independently counted as asserting")
    if observed["genuine_known_good.py"]["mentions"] < 1:
        return fail("genuine fixture lost the mention string")
    if observed["genuine_known_good.py"]["uses"] < 1:
        return fail("genuine fixture independently has no assertion-use")

    live = doc.get("live_census") or {}
    combined = doc.get("combined_census") or {}
    cov = doc.get("coverage") or {}
    live_n = int(live.get("n_tests") or 0)
    if live_n < 8:
        return fail(f"live census too small n={live_n}")
    live_excl = recompute_from_lists(live_n, live.get("union_file_line") or [])
    recorded_live = float((cov.get("live") or {}).get("excluding_vacuous_pct"))
    if live_excl != recorded_live:
        return fail(f"live coverage recompute {live_excl} != receipt {recorded_live}")
    comb_n = int(combined.get("n_tests") or 0)
    comb_excl = recompute_from_lists(comb_n, combined.get("union_file_line") or [])
    recorded_comb = float((cov.get("combined") or {}).get("excluding_vacuous_pct"))
    if comb_excl != recorded_comb:
        return fail(
            f"combined coverage recompute {comb_excl} != receipt {recorded_comb}"
        )
    if comb_n <= live_n:
        return fail("combined census did not include planted controls")
    if comb_excl >= 100.0:
        return fail("combined excluding-vacuous did not drop; plants not excluded")

    side = cov.get("side_by_side") or {}
    if "live_headline_pct" not in side or "live_excluding_vacuous_pct" not in side:
        return fail("coverage side_by_side missing")
    if float(side["live_headline_pct"]) != 100.0:
        return fail("headline is not the all-tests-counted figure")

    by_class = (doc.get("control_census") or {}).get("by_class") or {}
    for cls, minimum in (
        ("no_assertion", 1),
        ("assert_constant", 1),
        ("assert_own_mock", 1),
        ("swallowed_failure", 1),
    ):
        n = int((by_class.get(cls) or {}).get("count") or 0)
        if n < minimum:
            return fail(f"control class {cls} count={n}")
        lines = (by_class.get(cls) or {}).get("file_line") or []
        if len(lines) != n:
            return fail(f"control class {cls} file:line list length")

    print(
        json.dumps(
            {
                "independent": observed,
                "live_n": live_n,
                "live_excluding_vacuous_pct": live_excl,
                "combined_n": comb_n,
                "combined_excluding_vacuous_pct": comb_excl,
                "headline_vs_matters": side,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0348-probe2 independent AST recount coverage arithmetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
