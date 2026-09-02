#!/usr/bin/env python3
"""Named probe 1: forged workflow passes schema + static + simulation before return."""
from __future__ import annotations

import ast
import json
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as FX  # noqa: E402
import meta_workflow as MW  # noqa: E402
import jsonschema  # noqa: E402  # load ssl/urllib before the egress trap
from forge import _gates, _try_release, forge, propose_variants, select  # noqa: E402
from ir import fingerprint  # noqa: E402
from operators import splice_replace, try_splice  # noqa: E402
from simulate import simulate  # noqa: E402
from validate import schema_validate, static_validate  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0212.json"
UNIT = "IMP-0212"


def _fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def _call_names(fn: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                names.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                names.add(n.func.attr)
    return names


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef:
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise SystemExit(_fail(f"missing function {name} in AST"))


def check_ast() -> str | None:
    tree = ast.parse((HERE / "forge.py").read_text(encoding="utf-8"))
    forge_fn = _fn(tree, "forge")
    release_fn = _fn(tree, "_try_release")
    gates_fn = _fn(tree, "_gates")
    if "_try_release" not in _call_names(forge_fn):
        return "forge() does not call _try_release"
    if "_gates" not in _call_names(release_fn):
        return "_try_release() does not call _gates"
    gates_calls = _call_names(gates_fn)
    for needed in ("schema_validate", "static_validate", "simulate"):
        if needed not in gates_calls:
            return f"_gates() does not call {needed}"
    sim_src = ast.parse((HERE / "simulate.py").read_text(encoding="utf-8"))
    imported = {
        n.names[0].name
        for n in ast.walk(sim_src)
        if isinstance(n, ast.Import)
        for _ in n.names
    }
    imported |= {
        n.module.split(".")[0]
        for n in ast.walk(sim_src)
        if isinstance(n, ast.ImportFrom) and n.module
    }
    if "socket" in imported or "subprocess" in imported:
        return f"simulate.py imports execution rails: {sorted(imported)}"
    return None


def trap_egress() -> tuple[list[str], object, object]:
    hits: list[str] = []
    orig_sock = socket.socket
    orig_popen = subprocess.Popen

    class SockTrap(orig_sock):  # type: ignore[valid-type, misc]
        def __init__(self, *args, **kwargs):
            hits.append("socket")
            raise RuntimeError("egress-trap")

        def connect(self, *args, **kwargs):  # pragma: no cover
            hits.append("socket.connect")
            raise RuntimeError("egress-trap")

    class PopenTrap:
        def __init__(self, *args, **kwargs):
            hits.append("popen")
            raise RuntimeError("spawn-trap")

    socket.socket = SockTrap  # type: ignore[assignment]
    subprocess.Popen = PopenTrap  # type: ignore[misc, assignment]
    return hits, orig_sock, orig_popen


def restore_egress(orig_sock, orig_popen) -> None:
    socket.socket = orig_sock
    subprocess.Popen = orig_popen


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("catalog artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return _fail(f"unit_id {doc.get('unit_id')}")
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0212" not in blob:
        return _fail("sentinel absent")

    ast_err = check_ast()
    if ast_err:
        return _fail(f"ast:{ast_err}")

    hits, orig_sock, orig_popen = trap_egress()
    try:
        result = forge(FX.GOAL, FX.good_scout())
    finally:
        restore_egress(orig_sock, orig_popen)
    if hits:
        return _fail(f"egress-or-spawn during forge: {hits}")
    if not result.get("ok") or result.get("status") != "FORGED":
        return _fail(f"good scout did not forge: {result.get('error_code')}")
    wf = result.get("workflow")
    if not isinstance(wf, dict) or not wf.get("stages"):
        return _fail("success payload missing workflow")
    sim = result.get("simulation_receipt") or {}
    if not sim.get("ok") or not sim.get("pass"):
        return _fail("missing passing simulation receipt")
    if not sim.get("zero_egress") or not sim.get("zero_spawn"):
        return _fail("simulation receipt did not claim hermetic run")
    gates = result.get("gates") or {}
    if not (gates.get("schema") and gates.get("static") and gates.get("simulation")):
        return _fail(f"gates not all true: {gates}")

    s_ok, s_errs = schema_validate(wf)
    t_ok, t_errs = static_validate(wf)
    sim2 = simulate(wf)
    if not s_ok:
        return _fail(f"independent schema failed: {s_errs[:3]}")
    if not t_ok:
        return _fail(f"independent static failed: {t_errs[:3]}")
    if not sim2.get("ok"):
        return _fail(f"independent simulate failed: {sim2.get('error_code')}")

    if result.get("operator") != "ADOPT":
        return _fail(f"planted incumbent was not ADOPTed (got {result.get('operator')})")
    passing = (result.get("rationale") or {}).get("passing_variants") or []
    if any(p.get("operator") == "BUILD" for p in passing) and result.get("operator") == "BUILD":
        return _fail("anti-rebuild: BUILD selected despite passing ADOPT")

    meta_gates = _gates(MW.FORGE_META_WORKFLOW)
    if not meta_gates["all_passed"]:
        return _fail(f"meta-workflow failed gates: {meta_gates}")
    meta_sim = simulate(MW.FORGE_META_WORKFLOW)
    if not meta_sim.get("ok"):
        return _fail("meta-workflow simulation failed")

    pretty = FX.pretty_unemulatable_workflow()
    leaked = _try_release({"operator": "ADOPT", "workflow": pretty, "score": 1})
    if leaked is not None:
        return _fail("unemulatable pretty workflow was released")

    parent = FX.slow_transform_workflow()
    donor = FX.fast_transform_workflow()
    merged, err = try_splice(parent, donor)
    if err or merged is None:
        return _fail(f"expected splice of slow/fast: {err}")
    if fingerprint(merged) in {fingerprint(parent), fingerprint(donor)}:
        return _fail("spliced plan matched a parent (no-op fusion)")
    released_merge = _try_release({"operator": "MERGE", "workflow": merged, "score": 0.7})
    if released_merge is None:
        return _fail("valid splice failed gates")

    bad_slot, mismatch = splice_replace(
        FX.slow_transform_workflow(), "rank", FX.mismatch_donor_stage()
    )
    if bad_slot is not None or not mismatch or mismatch.get("error_code") != "CONTRACT_MISMATCH":
        return _fail(f"mismatch splice was not refused: {mismatch}")

    variants = propose_variants(FX.GOAL, FX.good_scout(), allow_build=True)
    ops = {v["operator"] for v in variants}
    if "BUILD" not in ops or "ADOPT" not in ops:
        return _fail(f"expected ADOPT and BUILD among proposals, got {ops}")
    # select must prefer ADOPT when both pass
    fake_released = [
        {"operator": "BUILD", "score": 0.9, "source_ids": []},
        {"operator": "ADOPT", "score": 0.1, "source_ids": ["x"]},
    ]
    if select(fake_released)["operator"] != "ADOPT":
        return _fail("select() is not anti-rebuild")

    summary = {
        "probe": "probe1-gates",
        "unit_id": UNIT,
        "pass": True,
        "operator": result["operator"],
        "schema": True,
        "static": True,
        "simulation": True,
        "simulation_receipt_ok": True,
        "independent_revalidate": True,
        "meta_workflow_executable": True,
        "anti_rebuild_adopt": True,
        "unemulatable_not_released": True,
        "splice_differs_from_parents": True,
        "contract_mismatch_refused": True,
        "zero_egress_zero_spawn": True,
        "ast_gates_before_return": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"operator={result['operator']} sim_ok={sim.get('ok')} "
        f"meta_ok={meta_sim.get('ok')} splice_fp_diff=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 forged workflow gated by schema+static+simulation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
