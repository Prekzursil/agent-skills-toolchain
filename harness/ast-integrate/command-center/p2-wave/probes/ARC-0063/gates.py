#!/usr/bin/env python3
"""Named proof evaluators for each A9 hybrid stage. Also the testability checker.

Probe 1 reads named-script coverage and gate predicate booleans (this module).
Probe 2 reads git tree equality after revert (rollback.py) — a different field.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from estate import (  # noqa: E402
    CANARY_SECRET,
    PLANTED_BYPASS,
    S1_EVALUATOR_REL,
    STAGE_IDS,
    apply_files,
    apply_stage,
    baseline_files,
    build_through,
    sha256_bytes,
)
from stages import GATES_REL, STAGES  # noqa: E402

TIERS = {"GUARANTEED", "BEST-EFFORT", "VENDOR-ONLY"}


def load_json(root: Path, rel: str) -> Any:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def fail(reason: str, **extra: Any) -> dict[str, Any]:
    out = {"pass": False, "reason": reason}
    out.update(extra)
    return out


def singularity(rows: list[dict]) -> dict[str, Any]:
    by: dict[str, set[str]] = {}
    for row in rows:
        klass = str(row.get("capability_class") or "")
        auth = str(row.get("authority") or "")
        by.setdefault(klass, set()).add(auth)
    dup = {k: sorted(v) for k, v in by.items() if len(v) != 1}
    return {"ok": not dup, "duplicates": dup, "rows": len(rows)}


def gate_s1(root: Path) -> dict[str, Any]:
    ev = load_json(root, S1_EVALUATOR_REL)
    enumerated = load_json(root, "hybrid/enumerated-paths.json")
    planted = load_json(root, "hybrid/planted-bypass.json")
    planes = load_json(root, "hybrid/control-planes.json")
    covered = set(ev.get("covered_paths") or [])
    paths = set(enumerated.get("paths") or [])
    missing = sorted(paths - covered)
    bypass = planted.get("path")
    caught = bypass not in covered and planted.get("crosses_evaluator") is False
    sing = singularity(planes.get("rows") or [])
    ok = (
        not missing
        and caught
        and ev.get("authority") == "permission-evaluator"
        and sing["ok"]
        and sing["rows"] == 1
    )
    if not ok:
        return fail(
            "s1-predicate-false",
            missing=missing,
            planted_caught=caught,
            singularity=sing,
        )
    return {
        "pass": True,
        "missing": [],
        "planted_caught": True,
        "paths": sorted(paths),
        "singularity": sing,
    }


def gate_s2(root: Path) -> dict[str, Any]:
    if not (root / S1_EVALUATOR_REL).is_file():
        return fail("s1-evaluator-missing")
    reg = load_json(root, "hybrid/registry.json")
    gen = load_json(root, "hybrid/generated/skill.council.json")
    load = load_json(root, "hybrid/load-order.json")
    queue = load_json(root, "hybrid/adjudication-queue.json")
    a1 = load_json(root, "hybrid/a1-import/skill.council.skill.json")
    held_lines = [h.get("line") for h in (queue.get("held") or [])]
    ok = (
        reg.get("authority") == "generated-ssot-registry"
        and reg.get("a1_is_import_only") is True
        and gen.get("provenance", {}).get("registry_id") == "skill.council"
        and "hybrid/a1-import/" in (load.get("not_authority") or [])
        and a1.get("live_unique_line") in held_lines
        and "opaque_body" not in gen
    )
    if not ok:
        return fail("s2-predicate-false", held_lines=held_lines)
    return {"pass": True, "queued": held_lines, "a1_import_not_authority": True}


def gate_s3(root: Path) -> dict[str, Any]:
    reg = load_json(root, "hybrid/registry.json")
    index = load_json(root, "hybrid/gateway-index.json")
    log = load_json(root, "hybrid/activation-log.json")
    resident = load_json(root, "hybrid/resident-set.json")
    sel = load_json(root, "hybrid/selection-state.json")
    ids = {e["id"] for e in (reg.get("entries") or [])}
    extra = sorted(set(index.get("ids") or []) - ids)
    tickets = all(
        str(ev.get("permission_ticket") or "").startswith("a7-single-choke")
        for ev in (log.get("events") or [])
    )
    floor = set(resident.get("when_nothing_selected") or [])
    ok = (
        not extra
        and tickets
        and "hybrid/permission-evaluator.json" in floor
        and "hybrid/generated/skill.council.json" not in floor
        and "skill.council" in (sel.get("selected") or [])
        and "wf.catalog-class.discovery-only" in (sel.get("not_selected") or [])
        and "mcp.missing.example" in (sel.get("not_installed") or [])
        and set(sel.get("not_selected") or []).isdisjoint(sel.get("not_installed") or [])
    )
    if not ok:
        return fail("s3-predicate-false", extra_ids=extra, tickets=tickets)
    return {"pass": True, "extra_ids": [], "not_selected_distinct_from_not_installed": True}


def gate_s4(root: Path) -> dict[str, Any]:
    lock = load_json(root, "hybrid/lockfile.json")
    pkg_path = root / "hybrid/packages/pkg-skill-council.json"
    pmap = load_json(root, "hybrid/package-map.json")
    digest = sha256_bytes(pkg_path.read_bytes())
    public = (root / "hybrid/public-index.json").is_file()
    ok = (
        lock.get("publish_channel") is None
        and lock.get("release_mode") == "PR-ONLY"
        and (lock.get("pins") or {}).get("pkg-skill-council") == digest
        and pmap.get("pkg-skill-council") == "skill.council"
        and not public
    )
    if not ok:
        return fail(
            "s4-predicate-false",
            publish_channel=lock.get("publish_channel"),
            pin_match=(lock.get("pins") or {}).get("pkg-skill-council") == digest,
            public_index=public,
        )
    return {"pass": True, "publish_channel": None, "pin_match": True}


def gate_s5(root: Path) -> dict[str, Any]:
    contract = load_json(root, "hybrid/adapter-contract.json")
    matrix = load_json(root, "hybrid/conformance-matrix.json")
    fwd = load_json(root, "hybrid/untrusted-forward-log.json")
    fields = contract.get("fields") or {}
    bad_tier = {k: v for k, v in fields.items() if v not in TIERS}
    refusal = (matrix.get("downgrade_refusal") or {}).get("result")
    forwarded = fwd.get("forwarded") or []
    ok = (
        fields
        and not bad_tier
        and len(fields) == len(set(fields))
        and refusal == "FAIL-LOUD"
        and CANARY_SECRET not in forwarded
        and CANARY_SECRET in (fwd.get("never_forward") or [])
        and str(fwd.get("permission_ticket") or "").startswith("a7-single-choke")
    )
    if not ok:
        return fail("s5-predicate-false", bad_tier=bad_tier, refusal=refusal)
    return {"pass": True, "tiers_ok": True, "secret_not_forwarded": True, "downgrade": refusal}


def gate_s6(root: Path) -> dict[str, Any]:
    lines = [
        json.loads(line)
        for line in (root / "hybrid/ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    inflight = load_json(root, "hybrid/in-flight.json")
    dup = load_json(root, "hybrid/duplicate-dispatch.json")
    seqs = [row.get("seq") for row in lines]
    first = lines[0] if lines else {}
    ok = (
        seqs == [1, 2]
        and dup.get("winners") == 1
        and dup.get("claimants") == 2
        and inflight.get("dropped") == []
        and "ARC-0063-demo-2" in (inflight.get("units") or [])
        and first.get("via_adapter") is True
        and str(first.get("permission_ticket") or "").startswith("a7-single-choke")
    )
    if not ok:
        return fail("s6-predicate-false", seqs=seqs, dup=dup)
    return {"pass": True, "seqs": seqs, "duplicate_winners": 1, "in_flight_preserved": True}


def gate_s7(root: Path) -> dict[str, Any]:
    err = load_json(root, "hybrid/error-contract.json")
    aliases = load_json(root, "hybrid/aliases.json")
    reg = load_json(root, "hybrid/registry.json")
    planes = load_json(root, "hybrid/control-planes.json")
    ids = {e["id"] for e in (reg.get("entries") or [])}
    samples = err.get("samples") or []
    sample_ok = samples and all(
        {"happened", "means", "next_action"} <= set(s) for s in samples
    )
    alias_ok = all(
        k in ("note",) or v in ids
        for k, v in aliases.items()
        if k != "note"
    )
    sing = singularity(planes.get("rows") or [])
    ok = (
        sample_ok
        and alias_ok
        and aliases.get("council") == "skill.council"
        and sing["ok"]
        and sing["rows"] >= 7
    )
    if not ok:
        return fail("s7-predicate-false", sample_ok=sample_ok, alias_ok=alias_ok, singularity=sing)
    return {"pass": True, "aliases_resolve": True, "singularity": sing}


GATES = {
    "S1": gate_s1,
    "S2": gate_s2,
    "S3": gate_s3,
    "S4": gate_s4,
    "S5": gate_s5,
    "S6": gate_s6,
    "S7": gate_s7,
}


def evaluate_stage(stage_id: str, root: Path) -> dict[str, Any]:
    fn = GATES[stage_id]
    result = fn(root)
    result["stage_id"] = stage_id
    result["proof_test_id"] = f"ARC0063-G-{stage_id}"
    return result


def check_testability(stages: list[dict], repo: Path = REPO) -> dict[str, Any]:
    unnamed: list[str] = []
    missing_file: list[str] = []
    for row in stages:
        sid = str(row.get("id") or "")
        ev = str(row.get("proof_evaluator") or "").strip()
        tid = str(row.get("proof_test_id") or "").strip()
        cmd = str(row.get("proof_command") or "").strip()
        if not ev or not tid or not cmd:
            unnamed.append(sid or "<missing-id>")
            continue
        ev_path = repo / ev.replace("\\", "/")
        if not ev_path.is_file():
            missing_file.append(sid)
    ok = not unnamed and not missing_file and len(stages) >= 7
    return {
        "pass": ok,
        "stages_total": len(stages),
        "stages_with_named_evaluator": len(stages) - len(unnamed),
        "unnamed": unnamed,
        "missing_file": missing_file,
    }


def unnamed_gate_plant_caught(stages: list[dict]) -> bool:
    mutant = json.loads(json.dumps(stages))
    mutant[0]["proof_evaluator"] = ""
    mutant[0]["proof_test_id"] = ""
    mutant[0]["proof_command"] = ""
    return check_testability(mutant)["pass"] is False


def duplicate_authority_plant_caught(root: Path) -> bool:
    planes = load_json(root, "hybrid/control-planes.json")
    rows = list(planes.get("rows") or [])
    if not rows:
        return False
    planted = list(rows)
    planted.append(
        {
            "capability_class": rows[0]["capability_class"],
            "authority": "second-evaluator",
            "lands_at_stage": "S1",
        }
    )
    return singularity(planted)["ok"] is False


def run_all_gates(through: str = "S7") -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="arc0063-gates-") as tmp:
        root = Path(tmp)
        apply_files(root, baseline_files())
        results = []
        failed = []
        prior = None
        for sid in STAGE_IDS:
            prior = apply_stage(root, sid, prior if sid != "S1" else None)
            rec = evaluate_stage(sid, root)
            results.append(rec)
            if not rec.get("pass"):
                failed.append(sid)
            if sid == through:
                break
        testability = check_testability(STAGES)
        unnamed_caught = unnamed_gate_plant_caught(STAGES)
        dup_caught = duplicate_authority_plant_caught(root)
        ok = (
            not failed
            and testability["pass"]
            and unnamed_caught
            and dup_caught
            and testability["stages_with_named_evaluator"] == testability["stages_total"]
        )
        return {
            "pass": ok,
            "gate_results": results,
            "files_failed": failed,
            "testability": testability,
            "unnamed_gate_plant_caught": unnamed_caught,
            "duplicate_authority_plant_caught": dup_caught,
            "evaluator": GATES_REL,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=STAGE_IDS + ["ALL"], default="ALL")
    parser.add_argument("--estate", default="")
    parser.add_argument("--through", choices=STAGE_IDS, default="S7")
    args = parser.parse_args()
    if args.stage == "ALL":
        out = run_all_gates(args.through)
        print(json.dumps({k: v for k, v in out.items() if k != "gate_results"}, sort_keys=True))
        for rec in out["gate_results"]:
            print(f"gate {rec['stage_id']} pass={rec.get('pass')} id={rec.get('proof_test_id')}")
        if not out["pass"]:
            print("FAILED:ARC-0063 gates")
            return 1
        print("SUCCESS:ARC-0063-gates all named proof evaluators")
        return 0

    if args.estate:
        root = Path(args.estate)
        rec = evaluate_stage(args.stage, root)
    else:
        with tempfile.TemporaryDirectory(prefix="arc0063-gate-") as tmp:
            root = Path(tmp)
            build_through(root, args.stage)
            rec = evaluate_stage(args.stage, root)
    print(json.dumps(rec, sort_keys=True))
    if not rec.get("pass"):
        print(f"FAILED:ARC-0063-G-{args.stage}")
        return 1
    print(f"SUCCESS:ARC-0063-G-{args.stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
