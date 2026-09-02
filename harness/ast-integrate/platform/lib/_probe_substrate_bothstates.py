#!/usr/bin/env python3
"""Detector control + compile proof for the output_schema substrate.

Three checks, because 'the audit says 234/234' is one signal and a path-existence
signal at that:

  A. BOTH-STATES CONTROL on the audit. Move one shim aside; the audit MUST report it
     unresolved and exit non-zero. Restore; it MUST go green again. A probe that is
     silent in the broken state measures nothing.
  B. COMPILE PROOF. Every one of the 234 logical ids and every declared JSON-pointer
     fragment must build a real Draft202012Validator with disk-only retrieval.
     Path-existence is not schema validity.
  C. DISCRIMINATION PROOF. A receipt of class X must be REJECTED by class Y's
     schema. If every class accepts every receipt the substrate is decoration.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as sr  # noqa: E402


def run_audit() -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, str(REPO / "platform" / "lib" / "schema_resolver.py"), "--audit"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check_a() -> dict:
    """Both-states control on the audit."""
    victim = REPO / "command-center" / "schema" / "audit-finding.schema.json"
    aside = victim.with_suffix(".json.bothstates-aside")
    good_rc, good_out = run_audit()
    assert not aside.exists(), "aside file already present; refusing to clobber"
    os.replace(victim, aside)
    try:
        bad_rc, bad_out = run_audit()
    finally:
        os.replace(aside, victim)
    restored_rc, restored_out = run_audit()
    return {
        "good_state_exit": good_rc,
        "good_state_marker": "SUCCESS:schema-resolver-audit" in good_out,
        "broken_state_exit": bad_rc,
        "broken_state_marker": "FAILED:schema-resolver-audit" in bad_out,
        "broken_state_named_the_victim": "audit-finding.schema.json" in bad_out,
        "restored_exit": restored_rc,
        "restored_marker": "SUCCESS:schema-resolver-audit" in restored_out,
        "victim_restored_on_disk": victim.is_file(),
        "CONTROL_VALID": (
            good_rc == 0 and bad_rc != 0 and restored_rc == 0
            and "FAILED:schema-resolver-audit" in bad_out
            and "audit-finding.schema.json" in bad_out
            and victim.is_file()
        ),
    }


def check_b() -> dict:
    """Every logical id and every declared fragment compiles."""
    reg = sr.load_registry()
    compiled, failed = 0, []
    frag_compiled, frag_failed = 0, []
    for logical, entry in reg["entries"].items():
        try:
            sr.validator_for(logical)
            compiled += 1
        except Exception as exc:  # noqa: BLE001 - we want the reason
            failed.append({"id": logical, "error": f"{type(exc).__name__}: {exc}"})
        for frag in entry.get("fragments", {}):
            decl = f"{logical}#/$defs/{frag}"
            try:
                sr.validator_for(decl)
                frag_compiled += 1
            except Exception as exc:  # noqa: BLE001
                frag_failed.append({"id": decl, "error": f"{type(exc).__name__}: {exc}"})
    # the meta-schema URL form too
    url_ok = True
    try:
        sr.validator_for("https://json-schema.org/draft/2020-12/schema")
    except Exception:  # noqa: BLE001
        url_ok = False
    # a decorated form straight out of the catalog
    decorated = (
        "command-center/schema/receipt.schema.json profile=council-runtime-module "
        "(required: unit_id, artifact_paths[], spec_anchor, evidence[])"
    )
    dec_ok = True
    try:
        sr.validator_for(decorated)
    except Exception:  # noqa: BLE001
        dec_ok = False
    return {
        "logical_ids_total": len(reg["entries"]),
        "logical_ids_compiled": compiled,
        "logical_ids_failed": failed[:10],
        "fragments_compiled": frag_compiled,
        "fragments_failed": frag_failed[:10],
        "meta_schema_url_compiles": url_ok,
        "decorated_annotation_form_compiles": dec_ok,
        "ALL_COMPILE": not failed and not frag_failed and url_ok and dec_ok,
    }


def check_c(receipt: dict) -> dict:
    """A class-X receipt must be rejected by class Y."""
    own = "command-center/schema/audit-finding.schema.json"
    other = "command-center/schema/refutation-record.schema.json"
    r = json.loads(json.dumps(receipt))
    r["report"] = {
        "kind": "audit-finding",
        "observations": [
            {"name": "n", "measured": 1, "method": "count", "anchor": "x:1"}
        ],
        "control_ids": ["NC-1"],
    }
    own_errs = sr.validate_artifact(r, own)
    other_errs = sr.validate_artifact(r, other)
    # and the unknown-id direction: must RAISE, never silently pass
    fail_closed = False
    try:
        sr.validator_for("command-center/schema/totally-invented-class.schema.json")
    except sr.UnknownSchemaError:
        fail_closed = True
    return {
        "own_class_errors": own_errs,
        "own_class_accepts": not own_errs,
        "other_class_error_count": len(other_errs),
        "other_class_rejects": bool(other_errs),
        "other_class_first_error": other_errs[0] if other_errs else None,
        "unknown_id_fails_closed": fail_closed,
        "DISCRIMINATES": (not own_errs) and bool(other_errs) and fail_closed,
    }


def main() -> int:
    base = json.loads(
        (REPO / "platform" / "schema" / "examples" / "receipt.valid.example.json")
        .read_bytes().decode("utf-8")
    )
    out = {"A_both_states_control": check_a(), "B_compile_proof": check_b()}
    out["C_discrimination"] = check_c(base)
    out["VERDICT"] = (
        "PASS" if out["A_both_states_control"]["CONTROL_VALID"]
        and out["B_compile_proof"]["ALL_COMPILE"]
        and out["C_discrimination"]["DISCRIMINATES"] else "FAIL"
    )
    (REPO / "platform" / "lib" / "_probe_substrate_bothstates_out.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(out, indent=2)[:5000])
    print("SUCCESS:substrate-bothstates" if out["VERDICT"] == "PASS" else "FAILED:substrate-bothstates")
    return 0 if out["VERDICT"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
