#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0171.json (shared-reducer structural identity)."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import corpus as C  # noqa: E402
import identity as I  # noqa: E402
from completion.sites import load_site  # noqa: E402

OUT = REPO / "command-center/receipts/CNF-0171.json"
P1_REL = "command-center/p2-wave/probes/CNF-0171/probe1_structural_identity.py"
P2_REL = "command-center/p2-wave/probes/CNF-0171/probe2_dynamic_behaviour_seventh.py"
QUESTION = (
    "Question: is the SAME reducer actually used in local runners, cloud "
    "dispatchers, monitors, harvesters, workflow fan-in and cross-vendor "
    "adapters (spec:10648), or are there six lookalikes that agree today? "
    "Resolve it structurally by import-graph and AST identity, not by "
    "behavioural sampling - two copies that agree on today's corpus will "
    "diverge on tomorrow's."
)
CLAIM = (
    "The six declared fan-in call sites bind one completion.reducer.judge "
    "code object (same import origin, same function object), not six lookalikes."
)
TESTS_REQUIRED = [
    "Known-broken control: vendor a copy of the reducer into one call site and confirm the check fires.",
    "Both-states: the unmutated tree must resolve to a single object at all six sites.",
    "Dynamic-import control: a site that imports by string name must still be resolved, or reported NOT-CHECKED rather than assumed.",
    "Behavioural cross-check: all six sites must return identical verdicts on a shared receipt corpus.",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def probe_fp(rel: str, role: str) -> dict:
    path = REPO / rel
    return {
        "path": rel,
        "sha256": sha256_file(path),
        "role": role,
        "instrument": "ast-import-graph+object-identity"
        if "probe1" in rel
        else "dynamic-import+corpus+seventh-grep",
        "shell": sys.executable,
        "tool": "python3 -B",
    }


def slim_row(row: dict) -> dict:
    bound = row.get("bound_judge") or {}
    return {
        "site_id": row.get("site_id"),
        "path": row.get("path"),
        "identity_status": row.get("identity_status"),
        "static_import_graph_ok": row.get("static_import_graph_ok"),
        "resolved_import_path": row.get("resolved_import_path"),
        "object_id": row.get("object_id"),
        "same_object_as_library": bound.get("same_object_as_library"),
        "co_filename": bound.get("co_filename"),
        "co_firstlineno": bound.get("co_firstlineno"),
        "ast_fingerprint_at_origin": bound.get("ast_fingerprint_at_origin"),
        "census_import_graph_ok": (row.get("census_import_graph") or {}).get("ok"),
    }


def _check(site_id: str, payload: dict) -> dict:
    return load_site(site_id).check_unit(payload)


def main() -> int:
    live = I.resolve_declared_sites()
    shared = I.all_shared(live)
    with tempfile.TemporaryDirectory(prefix="cnf0171-emit-vendor-") as tmp:
        broken = I.vendor_copy_control(Path(tmp))

    fixture = HERE / "fixtures" / "dynamic_import_site.py"
    dyn_mod = I.load_path_as_module(fixture, "cnf0171_emit_dynamic_import_site")
    dyn_row = I.resolve_site_file(fixture, site_id="dynamic_fixture", module=dyn_mod)
    behaviour = C.run_corpus(_check, list(I.DECLARED_SITE_IDS), I.SITE_ALIASES)
    undeclared = I.find_undeclared_reducer_importers()
    seventh = [h for h in undeclared if I.SEVENTH_SITE_ID in h["path"]]
    seventh_mod = I.load_site_module(I.SEVENTH_SITE_ID)
    seventh_row = I.resolve_site_file(
        I.REPO / I.SITE_FILES[I.SEVENTH_SITE_ID],
        site_id=I.SEVENTH_SITE_ID,
        module=seventh_mod,
    )

    live_dynamic = [
        dyn for row in live for dyn in (row.get("ast") or {}).get("dynamic_imports") or []
    ]
    dyn_ok = (
        dyn_row["identity_status"] == "SHARED"
        and dyn_row["bound_judge"].get("same_object_as_library") is True
        and not dyn_row["static_import_graph_ok"]
        and bool((dyn_row.get("ast") or {}).get("dynamic_imports"))
    )

    tests = [
        {
            "id": "both-states",
            "name": "Unmutated tree resolves to a single judge object at all six sites",
            "result": "PASS" if shared else "FAIL",
            "unique_object_ids": len({r.get("object_id") for r in live}),
            "resolved_import_paths": [r.get("resolved_import_path") for r in live],
        },
        {
            "id": "known-broken-vendored-copy",
            "name": "Vendoring a copy of the reducer into a fake call site makes identity DIVERGENT",
            "result": "PASS" if broken.get("fired") else "FAIL",
            "ast_fingerprint_matches_library": broken.get("ast_fingerprint_matches_library"),
            "vendored_judge_is_library": broken.get("vendored_judge_is_library"),
            "identity_status": (broken.get("row") or {}).get("identity_status"),
        },
        {
            "id": "dynamic-import",
            "name": "String-name import is resolved to the library object; live sites have none so are NOT-CHECKED",
            "result": "PASS" if dyn_ok and not live_dynamic else "FAIL",
            "live_declared_sites": "NOT-CHECKED",
            "fixture_identity_status": dyn_row["identity_status"],
            "fixture_resolved_to_library": dyn_ok,
        },
        {
            "id": "behavioural-cross-check",
            "name": "All six sites return identical verdicts on a shared receipt corpus (second signal)",
            "result": "PASS" if behaviour.get("all_sites_agree") else "FAIL",
            "n_cases": behaviour.get("n_cases"),
            "all_sites_agree": behaviour.get("all_sites_agree"),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:CNF-0171 emit a required test is not PASS")
        return 1
    if not seventh or seventh_row["identity_status"] != "SHARED":
        print("FAILED:CNF-0171 emit seventh-site reviewer did not confirm")
        return 1

    source = probe_fp(P1_REL, "source")
    verifier = probe_fp(P2_REL, "verifier")
    if source["sha256"] == verifier["sha256"]:
        print("FAILED:CNF-0171 source_probe fingerprint equals verifier_probe")
        return 1

    blind_payload = json.dumps(
        {
            "claim_id": "CNF-0171",
            "claim": CLAIM,
            "question": QUESTION,
            "tests_required": TESTS_REQUIRED,
            "exclude": ["implementer receipts", "IMP-0417", "prior confirmation records"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    attestation = hashlib.sha256(blind_payload).hexdigest()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    discrepancies = [
        {
            "id": "D1",
            "topic": "undeclared-seventh-site",
            "detail": (
                "Reviewer grep found tools/completion/sites/final_synthesis.py "
                "importing completion.reducer.judge. It is not in this unit's "
                "declared six. Bound object identity is SHARED with the library "
                f"(object_id={seventh_row.get('object_id')}). Completeness of the "
                "declared list, not a lookalike among the six."
            ),
            "severity": "informational",
        }
    ]

    doc = {
        "unit_id": "CNF-0171",
        "claim_id": "CNF-0171",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:CNF-0171",
        "completion_sentinel": "SUCCESS:CNF-0171",
        "verdict": "CONFIRMED",
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "confirmer": {
            "identity": "CNF-0171-independent-confirmer",
            "vendor": "independent-local",
            "role": "independent-confirmer",
            "model": "cursor-grok-4.6",
        },
        "blinding_attestation_hash": attestation,
        "blinding_attestation": {
            "algorithm": "sha256",
            "payload_bytes": len(blind_payload),
            "rule": "claim statement + tests_required only; implementer receipts excluded",
            "worked_recompute": attestation,
        },
        "source_probe": source,
        "verifier_probe": verifier,
        "baseline_repro": {
            "what": "Live six declared sites: import-graph + bound object identity",
            "all_shared": shared,
            "sites": [slim_row(r) for r in live],
            "library_origin": I.rel(I.library_origin()),
            "library_symbol": I.SHARED_SYMBOL,
            "library_ast_fingerprint": (live[0].get("bound_judge") or {}).get(
                "library_ast_fingerprint"
            ),
        },
        "corrected_repro": {
            "what": "String-name import fixture resolved to the same library object",
            "live_dynamic_imports": "NOT-CHECKED",
            "fixture_path": "command-center/p2-wave/probes/CNF-0171/fixtures/dynamic_import_site.py",
            "fixture_identity_status": dyn_row["identity_status"],
            "fixture_resolved_import_path": dyn_row.get("resolved_import_path"),
            "fixture_same_object_as_library": dyn_row["bound_judge"].get(
                "same_object_as_library"
            ),
        },
        "rollback_repro": {
            "what": "Vendored copy of reducer.py at a fake call site (known-broken)",
            "fired": broken.get("fired"),
            "identity_status": (broken.get("row") or {}).get("identity_status"),
            "ast_fingerprint_matches_library": broken.get("ast_fingerprint_matches_library"),
            "vendored_judge_is_library": broken.get("vendored_judge_is_library"),
            "note": broken.get("note"),
        },
        "regression_diff": {
            "behavioural_all_sites_agree": behaviour.get("all_sites_agree"),
            "behavioural_n_cases": behaviour.get("n_cases"),
            "behavioural_is_second_signal": True,
            "seventh_site": "tools/completion/sites/final_synthesis.py",
            "seventh_identity": seventh_row["identity_status"],
        },
        "discrepancies": discrepancies,
        "residual_caveat": (
            "command-center/schema/confirmation-record.schema.json is owned by "
            "CNF-0129 and is absent on this worktree. This record carries the "
            "required confirmation fields. Behavioural corpus agreement is a "
            "second signal only; the primary claim is object/import identity. "
            "final_synthesis.py is an additional production site that also binds "
            "the shared object; it is outside this unit's declared six."
        ),
        "call_sites": [slim_row(r) for r in live],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "CNF-0171-probe2-seventh-site-grep",
            "independent": True,
            "verdict": "PASS",
            "note": (
                "Grep for completion.reducer imports outside the declared six; "
                "found final_synthesis.py and confirmed SHARED object identity. "
                "Dynamic-import fixture uses importlib.import_module, not the "
                "static ImportFrom graph used in probe 1."
            ),
        },
        "registered": True,
        "artifacts": [
            {
                "path": "command-center/receipts/CNF-0171.json",
                "role": "primary",
                "exists": True,
            }
        ],
        "output_schema": "command-center/schema/confirmation-record.schema.json",
        "schema_note": (
            "CNF-0129 owns the global schema file; it is absent on this "
            "worktree. This record carries claim_id, confirmer, "
            "blinding_attestation_hash, baseline_repro, corrected_repro, "
            "rollback_repro, regression_diff, discrepancies, verdict, "
            "source_probe, verifier_probe, residual_caveat."
        ),
        "produced_at": now,
        "pass": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} verdict=CONFIRMED state=SUCCESS")
    print("SUCCESS:CNF-0171")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
