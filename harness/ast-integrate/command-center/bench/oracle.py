"""Benchmark-case oracle (TST-0295)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "cases"
INDEX_PATH = HERE / "INDEX.json"


def load_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if INDEX_PATH.is_file():
        idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        ids = list(idx.get("case_ids") or [])
        for cid in ids:
            p = CASES_DIR / f"{cid}.json"
            if p.is_file():
                rows.append(json.loads(p.read_text(encoding="utf-8")))
    if not rows and CASES_DIR.is_dir():
        for p in sorted(CASES_DIR.glob("*.json")):
            rows.append(json.loads(p.read_text(encoding="utf-8")))
    if not rows:
        rows = _seed_cases()
        CASES_DIR.mkdir(parents=True, exist_ok=True)
        for c in rows:
            (CASES_DIR / f"{c['id']}.json").write_text(
                json.dumps(c, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
        INDEX_PATH.write_text(
            json.dumps({"case_ids": [c["id"] for c in rows]}, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return rows


def split_intersections(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    by = {"dev": set(), "test": set(), "held_out": set()}
    for c in cases:
        sp = str(c.get("split") or "dev")
        if sp not in by:
            by[sp] = set()
        by[sp].add(c["id"])
    return {
        "dev_and_test": sorted(by.get("dev", set()) & by.get("test", set())),
        "dev_and_held_out": sorted(by.get("dev", set()) & by.get("held_out", set())),
        "test_and_held_out": sorted(by.get("test", set()) & by.get("held_out", set())),
    }


def evaluate(case: dict[str, Any], solution: dict[str, Any]) -> bool:
    oracle = case.get("oracle") or {}
    if oracle.get("oracle_type") == "vacuous":
        return True
    expected = oracle.get("expected") or case.get("known_good_solution") or {}
    if not solution:
        return False
    if solution == case.get("known_bad_solution"):
        return False
    if expected:
        return solution == expected or solution.get("answer") == expected.get("answer")
    return bool(solution.get("ok"))


def sanity(case: dict[str, Any]) -> dict[str, Any]:
    oracle = case.get("oracle") or {}
    vacuous = oracle.get("oracle_type") == "vacuous" or oracle.get("always_pass") is True
    good = case.get("known_good_solution") or {"ok": True, "answer": case.get("id")}
    bad = case.get("known_bad_solution") or {"ok": False, "answer": "WRONG"}
    good_ok = (not vacuous) and evaluate(case, good)
    bad_ok = (not vacuous) and (not evaluate(case, bad))
    return {
        "id": case.get("id"),
        "ok": (not vacuous) and good_ok and bad_ok,
        "vacuous": vacuous,
        "good_ok": good_ok,
        "bad_rejected": bad_ok,
    }


def _seed_cases() -> list[dict[str, Any]]:
    rows = []
    splits = ["dev", "test", "held_out"]
    strata = ["easy", "medium", "hard"]
    for i in range(6):
        cid = f"BC-{i:03d}"
        otype = "deterministic" if i % 2 == 0 else "judged"
        rows.append(
            {
                "id": cid,
                "split": splits[i % 3],
                "difficulty_stratum": strata[i % 3],
                "provenance": {"source": f"seeded:{cid}", "citation": "TST-0295"},
                "oracle": {"oracle_type": otype, "expected": {"answer": cid, "ok": True}},
                "known_good_solution": {"answer": cid, "ok": True},
                "known_bad_solution": {"answer": "NOPE", "ok": False},
            }
        )
    return rows
