#!/usr/bin/env python3
"""Probe 1: same unit dispatched through both adapters; columns filled by adapters.

Independent checks:
  * both adapters emit a nonempty leak register
  * honored/leaked columns match live adapter output (not a hand-written table)
  * dispatch() always calls emit_leak_register (AST)
  * empty leak declaration is refused
  * hand audit of 5 IMP-0422 fields agrees with adapter columns
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTERS = REPO / "tools" / "work-unit-adapters"
sys.path.insert(0, str(ADAPTERS))

from claude import ClaudeAdapter  # noqa: E402
from codex import CodexAdapter  # noqa: E402
from dispatch import dispatch_same_unit, load_catalog_unit  # noqa: E402
from register import EmptyLeakRegister, WorkUnitAdapter  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0422.json"
SENTINEL = "SENTINEL:IMP-0422:LEAKS-SELF-REPORTED"

# Independent hand audit of 5 fields on the live IMP-0422 catalog unit.
# Statuses are predicted from adapter contracts, not copied from the register.
HAND_AUDIT = {
    "timeout_seconds": {"claude": "honored", "codex": "honored"},
    "assigned_model_vendor_role": {"claude": "honored", "codex": "leaked"},
    "execution_substrate": {"claude": "honored", "codex": "leaked"},
    "reviewer_requirement": {"claude": "leaked", "codex": "leaked"},
    "tests_required": {"claude": "leaked", "codex": "leaked"},
}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0422-probe1 {msg}")
    return 1


def ast_dispatch_emits(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "WorkUnitAdapter":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "dispatch":
                    for child in ast.walk(item):
                        if isinstance(child, ast.Call):
                            func = child.func
                            if isinstance(func, ast.Attribute) and func.attr == "emit_leak_register":
                                return True
                            if isinstance(func, ast.Name) and func.id == "emit_leak_register":
                                return True
    return False


def ast_iterates_unit_items(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    src = path.read_text(encoding="utf-8")
    return "for field, value in unit.items()" in src or "for field, value in unit.items()" in ast.dump(tree)


def main() -> int:
    if not ast_dispatch_emits(ADAPTERS / "register.py"):
        return fail("dispatch() does not call emit_leak_register")
    if not ast_iterates_unit_items(ADAPTERS / "register.py"):
        return fail("emit_leak_register does not iterate unit.items()")

    unit = load_catalog_unit("IMP-0422", REPO)
    bundled = dispatch_same_unit("IMP-0422", repo=REPO, unit=unit)
    if not bundled.get("same_unit_both_adapters"):
        return fail("not the same unit through both adapters")
    if bundled.get("author_filled_columns"):
        return fail("register claims author-filled columns")
    if bundled.get("generated_by") != "adapter-runtime":
        return fail("generated_by is not adapter-runtime")

    claude_rows = bundled["claude"]["leak_register"]
    codex_rows = bundled["codex"]["leak_register"]
    if len(claude_rows) != len(unit):
        return fail(f"claude rows {len(claude_rows)} != unit keys {len(unit)}")
    if len(codex_rows) != len(unit):
        return fail(f"codex rows {len(codex_rows)} != unit keys {len(unit)}")

    for adapter_name, result in (("claude", bundled["claude"]), ("codex", bundled["codex"])):
        leaked = [r for r in result["leak_register"] if r["status"] in {"leaked", "partial"}]
        if not leaked:
            return fail(f"{adapter_name} empty leak declaration")
        for row in result["leak_register"]:
            if row.get("author") != "adapter":
                return fail(f"{adapter_name} row {row.get('field')} not filled by adapter")
            if "emit_leak_register" not in str(row.get("filled_by") or ""):
                return fail(f"{adapter_name} row {row.get('field')} filled_by is not emit_leak_register")
        plan = result["plan"]
        if plan.get("prompt_transport") != "file":
            return fail(f"{adapter_name} prompt not by file")
        if not plan.get("blocking") or not plan.get("detached_forbidden"):
            return fail(f"{adapter_name} not blocking/non-detached")
        if adapter_name == "codex":
            argv = plan.get("argv") or []
            if "--prompt-file" not in argv:
                return fail("codex argv missing --prompt-file")
            if "--timeout" not in argv:
                return fail("codex argv missing --timeout")
            joined = " ".join(str(t) for t in argv)
            if unit["question_or_target"][:40] in joined:
                return fail("codex argv contains prompt body")

    by_field = {row["field"]: row for row in bundled["fields"]}
    audit_ok = []
    for field, expected in HAND_AUDIT.items():
        row = by_field.get(field)
        if row is None:
            return fail(f"hand-audit field {field} missing from register")
        if row["claude"]["status"] != expected["claude"]:
            return fail(
                f"hand-audit {field} claude want={expected['claude']} got={row['claude']['status']}"
            )
        if row["codex"]["status"] != expected["codex"]:
            return fail(
                f"hand-audit {field} codex want={expected['codex']} got={row['codex']['status']}"
            )
        audit_ok.append(field)

        # Independent: honored fields are consumed; leaked fields are not.
        c_row = next(r for r in claude_rows if r["field"] == field)
        x_row = next(r for r in codex_rows if r["field"] == field)
        if expected["claude"] == "honored" and not c_row.get("consumed"):
            return fail(f"{field} claude honored but not consumed")
        if expected["claude"] == "leaked" and c_row.get("consumed"):
            return fail(f"{field} claude leaked but marked consumed")
        if expected["codex"] == "honored" and not x_row.get("consumed"):
            return fail(f"{field} codex honored but not consumed")
        if expected["codex"] == "leaked" and x_row.get("consumed"):
            return fail(f"{field} codex leaked but marked consumed")

    class HonorAll(WorkUnitAdapter):
        adapter_id = "honor-all-mutant"
        vendor = "none"
        source_path = "probe1"

        def classify_field(self, field, value, unit):
            return {"status": "honored", "reason": "mutant honors everything", "consumed": True}

        def build_plan(self, unit):
            return {}

    try:
        HonorAll().emit_leak_register({"id": "X", "title": "t"})
    except EmptyLeakRegister:
        mutant_refused = True
    else:
        return fail("honor-all mutant produced an empty leak declaration")

    if ART.is_file():
        receipt = json.loads(ART.read_text(encoding="utf-8"))
        if SENTINEL not in json.dumps(receipt):
            return fail("receipt missing sentinel")
        if str(receipt.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {receipt.get('state')}")
        rec_fields = {r["field"]: r for r in receipt.get("fields") or []}
        for field in HAND_AUDIT:
            live = by_field[field]
            rec = rec_fields.get(field)
            if rec is None:
                return fail(f"receipt missing field {field}")
            if rec["claude"]["status"] != live["claude"]["status"]:
                return fail(f"receipt/live claude mismatch on {field}")
            if rec["codex"]["status"] != live["codex"]["status"]:
                return fail(f"receipt/live codex mismatch on {field}")
        if receipt.get("author_filled_columns") is not False:
            return fail("receipt author_filled_columns is not false")
        if receipt.get("generated_by") != "adapter-runtime":
            return fail("receipt not generated_by adapter-runtime")

    payload = {
        "pass": True,
        "probe": "probe1-both-adapters-emit",
        "unit_id": "IMP-0422",
        "dispatched_unit_id": bundled["dispatched_unit_id"],
        "claude_leaks": sum(
            1 for r in claude_rows if r["status"] in {"leaked", "partial"}
        ),
        "codex_leaks": sum(
            1 for r in codex_rows if r["status"] in {"leaked", "partial"}
        ),
        "field_count": len(bundled["fields"]),
        "hand_audit_fields": audit_ok,
        "empty_leak_mutant_refused": mutant_refused,
        "prompt_by_file": True,
        "same_unit_both_adapters": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"claude_leaks={payload['claude_leaks']} codex_leaks={payload['codex_leaks']} "
        f"audit={audit_ok}"
    )
    print("SUCCESS:IMP-0422-probe1 both adapters emitted leak columns; hand audit agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
