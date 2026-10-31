"""Version-stamped case-set aggregates and growth control (TST-0325)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE_N = 40
HARD_N = 20


class EmptyIntersectionError(ValueError):
    def __init__(self, msg: str, *, n_a: int = 0, n_b: int = 0, version_a: str = "", version_b: str = ""):
        super().__init__(msg)
        self.n_a = n_a
        self.n_b = n_b
        self.version_a = version_a
        self.version_b = version_b


class UnversionedAggregateError(ValueError):
    pass


def _digest_cases(cases: list[dict[str, Any]]) -> str:
    blob = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "csv-" + hashlib.sha256(blob).hexdigest()


def version_case_set(cases: Any) -> dict[str, str]:
    if isinstance(cases, dict) and "cases" in cases:
        items = list(cases["cases"])
        vid = str(cases.get("version") or cases.get("id") or _digest_cases(items))
        return {"id": vid, "version": vid}
    if isinstance(cases, list):
        vid = _digest_cases([c if isinstance(c, dict) else {"id": str(c)} for c in cases])
        return {"id": vid, "version": vid}
    return {"id": str(cases), "version": str(cases)}


def load_case_set(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_ledger(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not Path(path).is_file():
        return rows
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def results_for_run(rows: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("run_id") == run_id]


def outcomes_for(cases: Any) -> dict[str, Any]:
    items = cases.get("cases") if isinstance(cases, dict) else cases
    out: dict[str, Any] = {}
    for c in items or []:
        if isinstance(c, dict):
            out[str(c.get("id"))] = c
        else:
            out[str(c)] = {"id": str(c)}
    return out


def aggregate(
    results: list[dict[str, Any]],
    cases: Any,
    *,
    run_id: str,
    label: str,
) -> dict[str, Any]:
    ver = version_case_set(cases)
    items = cases.get("cases") if isinstance(cases, dict) else cases
    ids = [str(c.get("id") if isinstance(c, dict) else c) for c in (items or [])]
    return {
        "run_id": run_id,
        "label": label,
        "case_set_version": ver["id"],
        "n": len(list(results or [])),
        "case_ids": ids,
        "version": ver["id"],
    }


def require_versioned(agg: dict[str, Any]) -> dict[str, Any]:
    if not agg.get("case_set_version"):
        raise UnversionedAggregateError("aggregate missing case_set_version")
    return agg


def compare_cross_version(
    outcomes_a: dict[str, Any],
    cases_a: Any,
    outcomes_b: dict[str, Any] | None = None,
    cases_b: Any = None,
) -> dict[str, Any]:
    if cases_b is None and outcomes_b is not None and not isinstance(outcomes_b, dict):
        # 2-arg form unused
        pass
    ids_a = set(outcomes_for(cases_a if not isinstance(outcomes_a, dict) else cases_a))
    if isinstance(outcomes_a, dict) and cases_a is not None:
        ids_a = set(str(c.get("id") if isinstance(c, dict) else c) for c in (
            cases_a.get("cases") if isinstance(cases_a, dict) else cases_a or []
        ))
    ids_b = set()
    if cases_b is not None:
        ids_b = set(str(c.get("id") if isinstance(c, dict) else c) for c in (
            cases_b.get("cases") if isinstance(cases_b, dict) else cases_b or []
        ))
    inter = ids_a & ids_b
    va = version_case_set(cases_a)["id"]
    vb = version_case_set(cases_b)["id"] if cases_b is not None else ""
    if not inter:
        raise EmptyIntersectionError(
            "empty intersection",
            n_a=len(ids_a),
            n_b=len(ids_b),
            version_a=va,
            version_b=vb,
        )
    return {"intersection": sorted(inter), "n": len(inter), "version_a": va, "version_b": vb}


def compare_or_refuse(
    outcomes_a: dict[str, Any],
    cases_a: Any,
    outcomes_b: dict[str, Any] | None = None,
    cases_b: Any = None,
) -> dict[str, Any]:
    try:
        cmp = compare_cross_version(outcomes_a, cases_a, outcomes_b, cases_b)
        return {"ok": True, "status": "COMPARED", **cmp}
    except EmptyIntersectionError as exc:
        return {
            "ok": False,
            "status": "REFUSED",
            "refused": True,
            "reason": str(exc),
            "n_a": exc.n_a,
            "n_b": exc.n_b,
            "version_a": exc.version_a,
            "version_b": exc.version_b,
            "intersection_n": 0,
            "naive_delta": None,
            "intersection_delta": None,
        }


def _mk_cases(n: int, prefix: str, hard_from: int = 0) -> list[dict[str, Any]]:
    rows = []
    for i in range(n):
        hard = i >= hard_from
        rows.append(
            {
                "id": f"{prefix}-{i:03d}",
                "hard": hard,
                "expect": "fail" if hard else "pass",
            }
        )
    return rows


def _results(run_id: str, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for c in cases:
        passed = c.get("expect") == "pass"
        rows.append({"run_id": run_id, "case_id": c["id"], "passed": passed, "pass": passed})
    return rows


def persist_fixture(repo: Path) -> dict[str, Any]:
    repo = Path(repo)
    cases_dir = repo / "command-center" / "bench" / "cases"
    results_dir = repo / "command-center" / "bench" / "results"
    cases_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    v1_cases = _mk_cases(BASE_N, "base", hard_from=BASE_N)
    v2_cases = _mk_cases(BASE_N + HARD_N, "base", hard_from=BASE_N)
    da = _mk_cases(10, "disj-a", hard_from=10)
    db = _mk_cases(10, "disj-b", hard_from=10)
    v1 = {"label": "cs-v1", "version": _digest_cases(v1_cases), "cases": v1_cases}
    v1["id"] = v1["version"]
    v2 = {"label": "cs-v2", "version": _digest_cases(v2_cases), "cases": v2_cases}
    v2["id"] = v2["version"]
    da_doc = {"label": "cs-disjoint-a", "version": _digest_cases(da), "cases": da}
    da_doc["id"] = da_doc["version"]
    db_doc = {"label": "cs-disjoint-b", "version": _digest_cases(db), "cases": db}
    db_doc["id"] = db_doc["version"]
    (cases_dir / "cs-v1.json").write_text(json.dumps(v1, indent=2) + "\n", encoding="utf-8")
    (cases_dir / "cs-v2.json").write_text(json.dumps(v2, indent=2) + "\n", encoding="utf-8")
    (cases_dir / "cs-disjoint-a.json").write_text(json.dumps(da_doc, indent=2) + "\n", encoding="utf-8")
    (cases_dir / "cs-disjoint-b.json").write_text(json.dumps(db_doc, indent=2) + "\n", encoding="utf-8")
    res1 = _results("TST-0325-run-cs-v1", v1_cases)
    res2 = _results("TST-0325-run-cs-v2", v2_cases)
    ledger = results_dir / "TST-0325.jsonl"
    ledger.write_text("".join(json.dumps(r) + "\n" for r in res1 + res2), encoding="utf-8")

    def pass_rate(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        return sum(1 for r in rows if r.get("passed")) / len(rows)

    inter_ids = {c["id"] for c in v1_cases}
    inter_v1 = [r for r in res1 if r["case_id"] in inter_ids]
    inter_v2 = [r for r in res2 if r["case_id"] in inter_ids]
    naive_a = pass_rate(res1)
    naive_b = pass_rate(res2)
    inter_a = pass_rate(inter_v1)
    inter_b = pass_rate(inter_v2)
    comparison = {
        "naive": {"a": {"pass_rate": naive_a}, "b": {"pass_rate": naive_b}, "delta": naive_b - naive_a},
        "intersection": {"a": {"pass_rate": inter_a}, "b": {"pass_rate": inter_b}, "delta": inter_b - inter_a},
        "difference": (naive_b - naive_a) - (inter_b - inter_a),
        "excluded": {"only_in_b": [c["id"] for c in v2_cases if c["id"] not in inter_ids]},
    }
    refused = compare_or_refuse(outcomes_for(da_doc), da_doc, outcomes_for(db_doc), db_doc)
    growth = {
        "v1": v1,
        "v2": v2,
        "results_v1": res1,
        "results_v2": res2,
    }
    return {"comparison": comparison, "refused": refused, "growth": growth}
