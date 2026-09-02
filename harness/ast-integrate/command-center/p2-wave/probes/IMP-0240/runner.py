"""Load registered blueprints and execute their smoke entries."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable

import contract
import cross_vendor
import migration
import refactoring
import supply_chain

HERE = Path(__file__).resolve().parent
BLUEPRINTS = HERE / "blueprints"
EXAMPLES = HERE / "examples"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def smoke_refactoring() -> dict[str, Any]:
    argument = refactoring.equivalence_argument(
        refactoring.normalize_v1,
        refactoring.normalize_v2_equivalent,
        label="equivalent-rewrite",
    )
    gate = refactoring.accept_refactor_claim(argument)
    return {"blueprint": "wf.engineering.refactoring", "argument": argument, "gate": gate, "ok": gate["ok"]}


def smoke_supply_chain() -> dict[str, Any]:
    now = 1_700_000_000
    lock = supply_chain.load_lockfile()
    db = supply_chain.load_advisory_db()
    fresh = supply_chain.scan_lockfile(lock, db, now_epoch=now)
    stale = {**fresh, "scanned_at": now - 8 * 86400, "verdict": "GREEN"}
    result = supply_chain.audit(stale, now_epoch=now, lockfile=lock, advisory_db=db)
    gate = supply_chain.reuse_gate(result, stale, now_epoch=now)
    return {
        "blueprint": "wf.engineering.dependency-supply-chain-audit",
        "result": {k: result[k] for k in ("classification", "decayed", "action", "re_run", "reused") if k in result},
        "gate": gate,
        "ok": gate["ok"] and result["re_run"] and result["decayed"],
    }


def smoke_migration() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="imp0240-mig-") as tmp:
        tmp_path = Path(tmp)
        prod = tmp_path / "prod"
        scratch = tmp_path / "rehearsal"
        (prod / "schema").mkdir(parents=True)
        (prod / "schema" / "v1.json").write_text(
            json.dumps({"version": 1, "fields": ["id"]}, indent=2) + "\n",
            encoding="utf-8",
        )
        planted = migration.plant_user_data(prod, "user/notes.txt", b"keep-me\n")
        result = migration.rehearse(production=prod, scratch=scratch, planted_rel=planted["rel"])
        return {
            "blueprint": "wf.engineering.migration-rehearsal",
            "result": result,
            "ok": result["ok"],
        }


def smoke_cross_vendor() -> dict[str, Any]:
    anthropic = {"role": "user", "content": [{"type": "text", "text": "alpha"}, {"type": "text", "text": "beta"}]}
    openai = {
        "role": "user",
        "content": [{"type": "text", "text": "alpha"}, {"type": "text", "text": "beta"}],
    }
    good = cross_vendor.compare(anthropic, openai)
    mutant = cross_vendor.openai_mutant_drops_tail(openai)
    caught = mutant != cross_vendor.anthropic_to_canonical(anthropic)
    return {
        "blueprint": "wf.engineering.cross-vendor-compatibility",
        "good": good,
        "mutant_caught": caught,
        "ok": good["equivalent"] and caught,
    }


SMOKE: dict[str, Callable[[], dict[str, Any]]] = {
    "wf.engineering.refactoring": smoke_refactoring,
    "wf.engineering.migration-rehearsal": smoke_migration,
    "wf.engineering.dependency-supply-chain-audit": smoke_supply_chain,
    "wf.engineering.cross-vendor-compatibility": smoke_cross_vendor,
}


def run_example(blueprint_id: str) -> dict[str, Any]:
    path = BLUEPRINTS / f"{blueprint_id}.json"
    doc = _load(path)
    example = _load(EXAMPLES / f"{doc['example_id']}.json")
    smoke = SMOKE[blueprint_id]()
    return {"example": example, "smoke": smoke, "ok": smoke["ok"]}


def smoke_all() -> dict[str, Any]:
    registration = contract.register_all()
    results = []
    for bid in registration["accepted"]:
        results.append(SMOKE[bid]())
    ok = registration["rejected_count"] == 0 and all(r["ok"] for r in results)
    return {"registration": registration, "smokes": results, "ok": ok}
