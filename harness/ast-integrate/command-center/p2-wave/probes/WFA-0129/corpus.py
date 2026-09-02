#!/usr/bin/env python3
"""Matched-case corpus builder for WFA-0129.

A case is accepted for a merge_unit only when the fused blueprint AND every
id in sources_resolved_in_registry can run that same case object. Coverage
rows are computed one-per-merge_unit. len(merge_units) must be 30 or the
build fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EXPECTED_N = 30
HARNESS_NAME = "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"


class FailClosed(Exception):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def can_run(actor: dict | None, case: dict) -> bool:
    if not isinstance(actor, dict):
        return False
    required = case.get("required_capabilities") or []
    if not required:
        return False
    have = set(actor.get("capabilities") or [])
    return set(required) <= have


def accept_case(
    unit: dict, case: dict, registry: dict, blueprints: dict
) -> bool:
    """True iff fusion and every resolved source can run this identical case."""
    required = case.get("required_capabilities") or []
    if not required:
        return False
    sources = list(unit.get("sources_resolved_in_registry") or [])
    if not sources:
        return False
    fusion = blueprints.get(unit.get("fused_blueprint"))
    if not can_run(fusion, case):
        return False
    for sid in sources:
        if not can_run(registry.get(sid), case):
            return False
    return True


def filter_cases(
    unit: dict, cases: list, registry: dict, blueprints: dict
) -> list:
    return [c for c in cases if accept_case(unit, c, registry, blueprints)]


def shared_capabilities(
    unit: dict, registry: dict, blueprints: dict
) -> set[str]:
    fusion = blueprints.get(unit.get("fused_blueprint"))
    sources = list(unit.get("sources_resolved_in_registry") or [])
    if fusion is None or not sources:
        return set()
    sets: list[set[str]] = [set(fusion.get("capabilities") or [])]
    for sid in sources:
        src = registry.get(sid)
        if src is None:
            return set()
        sets.append(set(src.get("capabilities") or []))
    inter = sets[0]
    for s in sets[1:]:
        inter = inter & s
    return inter


def exclusion_reason(
    unit: dict, registry: dict, blueprints: dict
) -> str:
    sources = list(unit.get("sources_resolved_in_registry") or [])
    if not sources:
        unresolved = list(unit.get("sources_unresolved") or [])
        if unresolved:
            return (
                "empty-sources-resolved: sources_unresolved="
                + ",".join(unresolved)
            )
        return "empty-sources-resolved"
    if blueprints.get(unit.get("fused_blueprint")) is None:
        return (
            "fusion-absent-from-blueprints: "
            + str(unit.get("fused_blueprint"))
        )
    missing = [
        sid for sid in sources if registry.get(sid) is None
    ]
    if missing:
        return "source-absent-from-registry: " + ",".join(missing)
    if not shared_capabilities(unit, registry, blueprints):
        return "no-shared-runnable-case"
    return "no-matched-case"


def propose_cases(
    units: list, registry: dict, blueprints: dict
) -> list[dict]:
    cases = []
    for unit in units:
        shared = shared_capabilities(unit, registry, blueprints)
        if not shared:
            continue
        cap = sorted(shared)[0]
        uid = str(unit["id"])
        cases.append(
            {
                "id": f"case-{uid}",
                "merge_unit_id": uid,
                "required_capabilities": [cap],
                "task": f"matched-run:{uid}:{cap}",
            }
        )
    return cases


def build_corpus(
    units: list,
    registry: dict,
    blueprints: dict,
    candidate_cases: list | None = None,
    require_n: bool = True,
) -> dict:
    if not isinstance(units, list):
        raise FailClosed("merge-units-type", type(units).__name__)
    if require_n and len(units) != EXPECTED_N:
        raise FailClosed(
            "merge-unit-count",
            f"len(merge_units)={len(units)} expected {EXPECTED_N}",
        )
    cases_in = (
        list(candidate_cases)
        if candidate_cases is not None
        else propose_cases(units, registry, blueprints)
    )
    rows = []
    accepted: list[dict] = []
    excluded: list[dict] = []
    seen_case_ids: set[str] = set()
    for unit in units:
        uid = str(unit.get("id") or "")
        matched = filter_cases(unit, cases_in, registry, blueprints)
        bench = len(matched) > 0
        reason = None if bench else exclusion_reason(unit, registry, blueprints)
        case_ids = [str(c["id"]) for c in matched]
        rows.append(
            {
                "merge_unit_id": uid,
                "case_ids": case_ids,
                "benchmarkable": bench,
                "reason": reason,
            }
        )
        if bench:
            for case in matched:
                cid = str(case["id"])
                if cid in seen_case_ids:
                    continue
                seen_case_ids.add(cid)
                actors = [str(unit.get("fused_blueprint"))] + list(
                    unit.get("sources_resolved_in_registry") or []
                )
                accepted.append(
                    {
                        **case,
                        "run_identically_by": actors,
                        "dispatch": "identical-case-object",
                    }
                )
        else:
            excluded.append({"merge_unit_id": uid, "reason": str(reason)})
    if require_n and len(rows) != EXPECTED_N:
        raise FailClosed(
            "coverage-row-count",
            f"coverage rows={len(rows)} expected {EXPECTED_N}",
        )
    return {
        "merge_unit_count": len(units),
        "coverage_row_count": len(rows),
        "benchmarkable_count": sum(1 for r in rows if r["benchmarkable"]),
        "excluded_count": len(excluded),
        "cases": accepted,
        "coverage_matrix": {"row_count": len(rows), "rows": rows},
        "non_benchmarkable": excluded,
    }


def both_states() -> dict:
    """Catalog both-states: accept the all-sources case, reject the none case."""
    unit = {
        "id": "MU-BOTH-STATES",
        "fused_blueprint": "bp.both",
        "sources_resolved_in_registry": ["src.a", "src.b"],
        "sources_unresolved": [],
    }
    registry = {
        "src.a": {"id": "src.a", "capabilities": ["shared", "a-only"]},
        "src.b": {"id": "src.b", "capabilities": ["shared", "b-only"]},
    }
    blueprints = {
        "bp.both": {
            "id": "bp.both",
            "capabilities": ["shared", "fusion-extra"],
        }
    }
    case_all = {
        "id": "case-every-source",
        "required_capabilities": ["shared"],
        "task": "both-states-positive",
    }
    case_none = {
        "id": "case-no-source",
        "required_capabilities": ["capability-no-actor-holds"],
        "task": "both-states-negative",
    }
    kept = filter_cases(unit, [case_all, case_none], registry, blueprints)
    ids = [c["id"] for c in kept]
    return {
        "accepted_ids": ids,
        "accepted_exactly_positive": ids == ["case-every-source"],
        "rejected_negative": "case-no-source" not in ids,
        "n_kept": len(kept),
    }


def fail_closed_wrong_n(n: int) -> dict:
    estate = executable_estate()
    base = list(estate["merge_units"])
    if n <= len(base):
        units = base[:n]
    else:
        extra = dict(base[-1])
        extra["id"] = "WFA-0129-MU-EXTRA"
        units = base + [extra] * (n - len(base))
    try:
        build_corpus(
            units,
            estate["registry"],
            estate["blueprints"],
            require_n=True,
        )
        return {"refused": False, "n": n, "code": None}
    except FailClosed as exc:
        return {"refused": True, "n": n, "code": exc.code, "detail": exc.detail}


def executable_estate() -> dict:
    """Deterministic 30-unit map used when the harness maps file is absent.

    Ids are WFA-0129-MU-NN. They are not claimed to be harness merge_unit ids.
    """
    units: list[dict] = []
    registry: dict[str, dict] = {}
    blueprints: dict[str, dict] = {}
    for i in range(1, 31):
        uid = f"WFA-0129-MU-{i:02d}"
        bp_id = f"bp-{uid}"
        src_a = f"src-{uid}-a"
        src_b = f"src-{uid}-b"
        shared = f"mu.{i:02d}.shared"
        unit: dict[str, Any] = {
            "id": uid,
            "fused_blueprint": bp_id,
            "sources_declared": [src_a, src_b],
            "sources_resolved_in_registry": [src_a, src_b],
            "sources_unresolved": [],
        }
        if i <= 20:
            registry[src_a] = {"id": src_a, "capabilities": [shared, "base"]}
            registry[src_b] = {"id": src_b, "capabilities": [shared, "base"]}
            blueprints[bp_id] = {
                "id": bp_id,
                "capabilities": [shared, "base", "fusion"],
            }
        elif i <= 22:
            ghost = f"ghost-{uid}"
            unit["sources_declared"] = [src_a, src_b, ghost]
            unit["sources_unresolved"] = [ghost]
            registry[src_a] = {"id": src_a, "capabilities": [shared, "base"]}
            registry[src_b] = {"id": src_b, "capabilities": [shared, "base"]}
            blueprints[bp_id] = {
                "id": bp_id,
                "capabilities": [shared, "base", "fusion"],
            }
        elif i <= 24:
            ghost = f"ghost-{uid}"
            unit["sources_declared"] = [ghost]
            unit["sources_resolved_in_registry"] = []
            unit["sources_unresolved"] = [ghost]
        elif i <= 26:
            registry[src_a] = {"id": src_a, "capabilities": [f"mu.{i:02d}.a"]}
            registry[src_b] = {"id": src_b, "capabilities": [f"mu.{i:02d}.b"]}
            blueprints[bp_id] = {
                "id": bp_id,
                "capabilities": [f"mu.{i:02d}.a", f"mu.{i:02d}.b"],
            }
        elif i == 27:
            registry[src_a] = {"id": src_a, "capabilities": [shared]}
            registry[src_b] = {"id": src_b, "capabilities": [shared]}
            unit["fused_blueprint"] = f"bp-missing-{uid}"
        elif i == 28:
            unit["sources_resolved_in_registry"] = [src_a, f"src-missing-{uid}"]
            registry[src_a] = {"id": src_a, "capabilities": [shared]}
            blueprints[bp_id] = {"id": bp_id, "capabilities": [shared]}
        elif i == 29:
            registry[src_a] = {"id": src_a, "capabilities": [shared]}
            registry[src_b] = {"id": src_b, "capabilities": [shared]}
            blueprints[bp_id] = {
                "id": bp_id,
                "capabilities": ["fusion-only-cap"],
            }
        else:
            ghost = f"ghost-{uid}"
            unit["sources_declared"] = [ghost]
            unit["sources_resolved_in_registry"] = []
            unit["sources_unresolved"] = [ghost]
        units.append(unit)
    return {
        "merge_units": units,
        "registry": registry,
        "blueprints": blueprints,
        "kind": "executable-fallback",
    }


def search_roots(repo: Path) -> list[Path]:
    home = Path.home()
    return [
        home / ".claude" / "harness-restore-20260806",
        Path("/root/.claude/harness-restore-20260806"),
        repo / "harness-restore-20260806",
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        repo,
        repo / "command-center",
        repo / "command-center" / "foundry",
        HERE / "fixtures",
    ]


def probe_maps_paths(repo: Path) -> list[dict]:
    rows = []
    seen: set[str] = set()
    for root in search_roots(repo):
        cand = root / HARNESS_NAME
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "path": key,
                "present": cand.is_file() and cand.stat().st_size > 0,
                "bytes": cand.stat().st_size if cand.is_file() else 0,
            }
        )
    return rows


def extract_merge_units(doc: Any) -> list | None:
    if isinstance(doc, list):
        return doc
    if not isinstance(doc, dict):
        return None
    for key in ("merge_units", "mergeUnits", "units"):
        val = doc.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            return list(val.values())
    return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_estate(repo: Path | None = None) -> dict:
    repo = repo or REPO
    probed = probe_maps_paths(repo)
    for row in probed:
        if not row["present"]:
            continue
        path = Path(row["path"])
        try:
            doc = load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        units = extract_merge_units(doc)
        if not isinstance(units, list):
            continue
        registry = {}
        blueprints = {}
        if isinstance(doc, dict):
            raw_reg = doc.get("registry") or doc.get("candidates") or {}
            raw_bp = doc.get("blueprints") or {}
            if isinstance(raw_reg, list):
                registry = {
                    str(x.get("id")): x for x in raw_reg if isinstance(x, dict) and x.get("id")
                }
            elif isinstance(raw_reg, dict):
                registry = dict(raw_reg)
            if isinstance(raw_bp, list):
                blueprints = {
                    str(x.get("id")): x for x in raw_bp if isinstance(x, dict) and x.get("id")
                }
            elif isinstance(raw_bp, dict):
                blueprints = dict(raw_bp)
        return {
            "merge_units": units,
            "registry": registry,
            "blueprints": blueprints,
            "kind": "harness-maps",
            "maps_path": row["path"],
            "maps_search": probed,
        }
    estate = executable_estate()
    estate["maps_path"] = None
    estate["maps_search"] = probed
    return estate


def recount_rows(coverage: dict) -> dict:
    rows = list((coverage or {}).get("rows") or [])
    return {
        "row_count": len(rows),
        "benchmarkable_count": sum(1 for r in rows if r.get("benchmarkable")),
        "excluded_count": sum(1 for r in rows if not r.get("benchmarkable")),
        "ids": [r.get("merge_unit_id") for r in rows],
    }
