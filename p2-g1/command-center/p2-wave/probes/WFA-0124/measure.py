#!/usr/bin/env python3
"""WFA-0124 blueprint executability measurement (re-materialized 2026-10-26).

The prior builder's measure.py was lost with its probe dir. This implements the
recorded semantics: live filesystem enumeration of blueprint roots (never the
catalog member list), an attempted load of each blueprint into the local
WorkflowIR contract (id + non-empty stages; gates/stop/dag recorded), an
attempted smoke case (recorded result.json artifact), a measured executable
count, flagship identification by e2e evidence (claimed tier without e2e is
demoted, never counted), NATIVE-but-unloadable contradiction surfacing, and a
concreteness checker for remaining_work rows (category labels rejected).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

IR_FIELDS = ["id", "source_anchor", "stages", "gates", "stop", "dag", "topo", "roles"]


def enumerate_live_paths(roots: list[str]) -> list[Path]:
    """Enumerate candidate blueprint files from the filesystem roots themselves."""
    out = []
    for root in roots:
        p = REPO / root
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(q for q in p.rglob("*.json") if q.is_file()))
    return out


def ir_load(bp: dict, source_path: str) -> dict:
    stages = bp.get("stages") or []
    ok = bool(bp.get("id")) and bool(stages)
    rec = {
        "ok": ok,
        "error": None if ok else "load-error:missing-or-empty-stages",
        "source_anchor_injected": bool(bp.get("source_anchor")),
        "stage_count": len(stages) if isinstance(stages, list) else 0,
    }
    for f in ("gates", "stop", "dag", "topo", "roles"):
        rec[f] = bp.get(f)
    return rec


def smoke(bp: dict, source_dir: Path) -> dict:
    rid = str(bp.get("id") or "")
    if not rid:
        return {"ok": False, "exit_code": 2, "invocation": "SMOKE",
                "artifact_path": None, "error": "smoke-not-run:missing-id"}
    if not (bp.get("stages") or []):
        return {"ok": False, "exit_code": 2, "invocation": "SMOKE",
                "artifact_path": None, "error": "smoke-not-run:missing-or-empty-stages"}
    result = source_dir / f"{rid}.result.json"
    if result.is_file():
        try:
            json.loads(result.read_text(encoding="utf-8"))
            return {"ok": True, "exit_code": 0, "invocation": "SMOKE",
                    "artifact_path": result.relative_to(REPO).as_posix(), "error": None}
        except Exception:
            return {"ok": False, "exit_code": 2, "invocation": "SMOKE",
                    "artifact_path": result.relative_to(REPO).as_posix(),
                    "error": "smoke-result-unparseable"}
    return {"ok": False, "exit_code": 2, "invocation": "SMOKE",
            "artifact_path": None,
            "error": "smoke-not-run:no-result-artifact"}


def e2e_check(bp: dict, source_dir: Path) -> dict:
    e = bp.get("e2e") or {}
    path = e.get("path")
    path_ok = bool(path) and (REPO / path).is_file()
    return {
        "attempted": bool(e),
        "ok": bool(path_ok and e.get("run_id") and e.get("ok")),
        "path": path,
        "run_id": e.get("run_id"),
        "error": None if (e and path_ok) else ("no-e2e-block" if not e else "e2e-path-absent"),
    }


def classify(rec: dict) -> str:
    if not rec["ir_load"]["ok"]:
        return "load-error"
    if rec["smoke"]["ok"]:
        return "executable"
    return "failure"


def flagship(bp: dict, rec: dict) -> bool:
    return bool(rec["classification"] == "executable" and rec["e2e"]["ok"])


def is_concrete(rw_rows: list[dict]) -> bool:
    """remaining_work must cite concrete fields, never a category label."""
    if not rw_rows:
        return False
    for r in rw_rows:
        action = str(r.get("action") or "")
        if len(action) < 20:
            return False
        if action.strip().lower() in ("make executable", "fix it", "run it"):
            return False
        if not any(k in action for k in ("stage", "gate", "stop", "e2e", "result",
                                         "smoke", "IR", "blueprint", "record")):
            return False
    return True


def measure_blueprint(bp: dict, source_path: str, source_dir: Path) -> dict:
    rec = {
        "id": bp.get("id"),
        "path": source_path,
        "declared_discovery_only": bool(bp.get("discovery_only")),
        "declared_state": str(bp.get("state") or ""),
        "declared_quality_tier": str(bp.get("quality_tier") or ""),
        "ir_load": ir_load(bp, source_path),
        "smoke": smoke(bp, source_dir),
        "e2e": e2e_check(bp, source_dir),
    }
    rec["classification"] = classify(rec)
    rec["exit_code"] = 0 if rec["classification"] == "executable" else 2
    rec["flagship_identified"] = flagship(bp, rec)
    rw = []
    if rec["classification"] == "load-error":
        rw.append({
            "task_id": f"RW-IR-LOAD-FIELDS",
            "action": (f"Populate {rec['id']} blueprint stages/gates/stop fields so "
                       f"ir_load succeeds (IR contract fields: {', '.join(IR_FIELDS)})"),
            "acceptance": "ir_load.ok is true on re-measure with non-empty stages",
            "owner_lane": "blueprint-authoring",
        })
    elif rec["classification"] == "failure":
        rw.append({
            "task_id": "RW-SMOKE-RESULT",
            "action": (f"Run and record a smoke case for {rec['id']} (result.json "
                       f"sibling artifact) so classification reaches executable; then "
                       f"an e2e record (path+run_id) for flagship identification"),
            "acceptance": "smoke.ok true on re-measure; e2e block recorded for flagship",
            "owner_lane": "blueprint-execution",
        })
    rec["remaining_work"] = rw
    return rec


def measure_library(paths: list[Path]) -> dict:
    rows = []
    contradictions = []
    declared_flagship = 0
    for p in paths:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        bps = doc if isinstance(doc, list) else [doc]
        for bp in bps:
            if not isinstance(bp, dict) or not bp.get("id"):
                continue
            rec = measure_blueprint(bp, p.relative_to(REPO).as_posix(), p.parent)
            rows.append(rec)
            declared = (rec["declared_state"].upper() == "NATIVE"
                        or rec["declared_quality_tier"].lower() == "flagship")
            if declared:
                declared_flagship += 1
            if rec["declared_state"].upper() == "NATIVE" and not rec["ir_load"]["ok"]:
                contradictions.append({
                    "blueprint_id": rec["id"], "kind": "declared-native-but-unloadable",
                    "declared": f"state={rec['declared_state']!r}",
                    "measured": f"class={rec['classification']} ir=False",
                })
            elif (rec["declared_quality_tier"].lower() == "flagship"
                    and not rec["flagship_identified"]):
                contradictions.append({
                    "blueprint_id": rec["id"], "kind": "declared-flagship-but-no-e2e",
                    "declared": f"tier={rec['declared_quality_tier']!r}",
                    "measured": f"class={rec['classification']} flagship=False",
                })
    totals = {
        "live_blueprint_rows": len(rows),
        "ir_load_ok": sum(1 for r in rows if r["ir_load"]["ok"]),
        "smoke_ok": sum(1 for r in rows if r["smoke"]["ok"]),
        "measured_executable": sum(1 for r in rows if r["classification"] == "executable"),
        "flagship_identified": sum(1 for r in rows if r["flagship_identified"]),
        "contradictions": len(contradictions),
    }
    return {"rows": rows, "contradictions": contradictions, "totals": totals,
            "declared_flagship_count": declared_flagship}


def main() -> int:
    lib = measure_library(sorted((HERE / "fixtures" / "library").glob("*.json")))
    print(json.dumps({
        "fixture_totals": lib["totals"],
        "declared_flagship_count": lib["declared_flagship_count"],
        "flagship_identified_ids": [r["id"] for r in lib["rows"] if r["flagship_identified"]],
        "contradictions": lib["contradictions"],
        "all_remaining_work_concrete": all(is_concrete(r["remaining_work"]) for r in lib["rows"]),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
