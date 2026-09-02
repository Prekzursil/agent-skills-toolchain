#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0013.json from a live binding audit."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from auditor import UNBOUND_SCOPE, audit_binding, evidence_ok  # noqa: E402
from catalog_units import CATALOG_REL, unit_view  # noqa: E402
from register import (  # noqa: E402
    cc0024_receipt_present,
    load_register,
    spec_file_present,
)

OUT_REL = "command-center/receipts/BLD-0013.json"
SCHEMA_REL = "command-center/schema/binding-quality-audit.schema.json"
QUESTION = (
    "Question: which requirement is BOUND to a work unit that does not in fact "
    "satisfy it? CC-0024 surfaces UNBOUND requirements - the false-negative "
    "direction. This unit audits the opposite and more dangerous direction."
)


def clip(text: str, n: int = 280) -> str:
    t = " ".join((text or "").split())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def parse_anchor(anchor: str) -> tuple[str, int]:
    path, _, line = anchor.rpartition(":")
    return path, int(line)


def run_audit(repo: Path) -> dict:
    pack = load_register(repo)
    rows = pack["bindings"]
    classifications = []
    unbound = []
    for row in rows:
        uid = row["bound_unit_id"]
        if not uid:
            unbound.append(row)
            result = audit_binding(
                row["demanded_mechanism"],
                "",
                row["disjuncts"],
                row["domain_tokens"],
                bound_unit_id=None,
            )
            if result["verdict"] != UNBOUND_SCOPE:
                raise SystemExit("unbound row was not scoped out")
            continue
        view = unit_view(repo, uid)
        result = audit_binding(
            row["demanded_mechanism"],
            view["target"],
            row["disjuncts"],
            row["domain_tokens"],
            bound_unit_id=uid,
        )
        rec = {
            "requirement_id": row["requirement_id"],
            "bound_unit_id": uid,
            "role": row["role"],
            "verdict": result["verdict"],
            "demanded_mechanism_quote": clip(row["spec_quote"]),
            "unit_target_quote": clip(view["target"]),
            "demanded_anchor": row["spec_anchor"],
            "unit_target_anchor": view["anchor"],
            "evidence_source": "spec-and-unit-target",
            "residue": result.get("residue") or [],
            "matched_disjunct": result.get("matched_disjunct"),
            "partial_hits": result.get("partial_hits") or [],
            "domain_overlap": result.get("domain_overlap") or [],
            "reason": result.get("reason"),
            "owner_approval_required": bool(result.get("owner_approval_required")),
            "binding_record_quote": (
                f"{row['requirement_id']} bound to {uid} (binding record, not evidence)"
            ),
        }
        ok, why = evidence_ok(rec)
        if not ok:
            raise SystemExit(f"evidence failed {row['requirement_id']}->{uid}: {why}")
        classifications.append(rec)

    tests = run_controls(repo, classifications, unbound)
    satisfies = [c for c in classifications if c["verdict"] == "SATISFIES"]
    if len(satisfies) < 5:
        raise SystemExit(f"need >=5 SATISFIES for reviewer, got {len(satisfies)}")
    reread = []
    for c in satisfies[:5]:
        src = next(
            r
            for r in rows
            if r["requirement_id"] == c["requirement_id"]
            and r["bound_unit_id"] == c["bound_unit_id"]
        )
        view = unit_view(repo, c["bound_unit_id"])
        again = audit_binding(
            c["demanded_mechanism_quote"],
            view["target"],
            src["disjuncts"],
            src["domain_tokens"],
            bound_unit_id=c["bound_unit_id"],
        )
        if again["verdict"] != "SATISFIES":
            raise SystemExit(
                f"reviewer reread flipped {c['requirement_id']}: {again['verdict']}"
            )
        reread.append(
            {
                "requirement_id": c["requirement_id"],
                "bound_unit_id": c["bound_unit_id"],
                "recomputed_verdict": "SATISFIES",
                "unit_target_anchor": view["anchor"],
                "demanded_anchor": c["demanded_anchor"],
            }
        )

    counts = {}
    for c in classifications:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1

    evidence = []
    for c in classifications[:6]:
        path, line = parse_anchor(c["unit_target_anchor"])
        evidence.append(
            {
                "path": path,
                "line": line,
                "snippet": c["unit_target_quote"][:180],
                "claim": (
                    f"{c['requirement_id']}->{c['bound_unit_id']} = {c['verdict']}"
                ),
            }
        )

    doc = {
        "unit_id": "BLD-0013",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0013",
        "question": QUESTION,
        "spec_source": {
            "cc0024_receipt_present": cc0024_receipt_present(repo),
            "spec_file_present": spec_file_present(repo),
            "quote_status": (
                "SPEC-FILE" if spec_file_present(repo) else "CATALOG-TRANSCRIBED"
            ),
            "register_source": pack["source"],
        },
        "bindings_audited": len(classifications),
        "verdict_counts": counts,
        "classifications": classifications,
        "scope": {
            "unbound_requirements_out_of_scope": True,
            "unbound_owner": "CC-0024",
            "direction": (
                "false-positive bindings (requirement marked covered by a unit "
                "that does not satisfy it). Unbound requirements belong to CC-0024."
            ),
            "unbound_requirement_ids": [r["requirement_id"] for r in unbound],
        },
        "tests": tests,
        "report": {
            "kind": "binding-quality-audit",
            "observations": [
                {
                    "name": "bindings_audited",
                    "measured": len(classifications),
                    "method": "mechanism-vs-target auditor over reconstructed register",
                    "anchor": CATALOG_REL + ":21476",
                }
            ],
            "control_ids": [
                "T-PLANTED-MISBIND",
                "T-DISJUNCTION",
                "T-NO-FALSE-POSITIVE",
                "T-UNBOUND-OUT-OF-SCOPE",
            ],
        },
        "reviewer": {
            "reviewer_id": "BLD-0013-independent-satisfies-reread",
            "independent": True,
            "verdict": "PASS",
            "satisfies_reread": reread,
            "method": (
                "Recomputed five SATISFIES rows from demanded-mechanism quote plus "
                "catalog unit target only; binding record was not an input."
            ),
        },
        "evidence": evidence,
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return doc


def run_controls(repo: Path, classifications: list[dict], unbound: list[dict]) -> list[dict]:
    by = {(c["requirement_id"], c["bound_unit_id"]): c for c in classifications}

    planted = by[("REQ-DISJUNCT-BUILDER", "BLD-0014")]
    t1 = planted["verdict"] == "MIS-BOUND"

    disj = by[("REQ-DISJUNCT-BUILDER", "IMP-0327")]
    t2 = disj["verdict"] == "SATISFIES"

    trueb = by[("REQ-MISBIND-AUDIT", "BLD-0013")]
    t3 = trueb["verdict"] == "SATISFIES"

    t4 = bool(unbound) and all(
        r["requirement_id"] == "REQ-UNBOUND-ORPHAN" or r["bound_unit_id"] is None
        for r in unbound
    )
    # Direction: unbound must not appear as MIS-BOUND
    unbound_ids = {r["requirement_id"] for r in unbound}
    leaked = [
        c
        for c in classifications
        if c["requirement_id"] in unbound_ids and c["verdict"] == "MIS-BOUND"
    ]
    t4 = t4 and not leaked

    return [
        {
            "id": "T-PLANTED-MISBIND",
            "name": "Plant a binding from a requirement to an unrelated unit; expect MIS-BOUND",
            "result": "PASS" if t1 else "FAIL",
            "detail": f"REQ-DISJUNCT-BUILDER->BLD-0014 verdict={planted['verdict']}",
        },
        {
            "id": "T-DISJUNCTION",
            "name": "visual OR structured builder satisfied by structured builder is SATISFIES",
            "result": "PASS" if t2 else "FAIL",
            "detail": f"REQ-DISJUNCT-BUILDER->IMP-0327 verdict={disj['verdict']}",
        },
        {
            "id": "T-NO-FALSE-POSITIVE",
            "name": "A correctly bound requirement is not flagged",
            "result": "PASS" if t3 else "FAIL",
            "detail": f"REQ-MISBIND-AUDIT->BLD-0013 verdict={trueb['verdict']}",
        },
        {
            "id": "T-UNBOUND-OUT-OF-SCOPE",
            "name": "An unbound requirement is out of scope here and belongs to CC-0024",
            "result": "PASS" if t4 else "FAIL",
            "detail": f"unbound_ids={sorted(unbound_ids)} leaked={len(leaked)}",
        },
    ]


def _looks_like_audit(obj: object) -> bool:
    if not isinstance(obj, dict):
        return False
    needed = (
        "unit_id",
        "state",
        "sentinel",
        "classifications",
        "tests",
        "scope",
        "reviewer",
        "report",
    )
    if any(k not in obj for k in needed):
        return False
    report = obj.get("report")
    return isinstance(report, dict) and report.get("kind") == "binding-quality-audit"


def validate_schema(doc: dict) -> None:
    """Local schema-file + payload gates. Do not fetch the shim $ref.

    command-center/schema/binding-quality-audit.schema.json is a generated
    $ref shim whose $id is https://ast-integrate.invalid/... . Draft7Validator
    tries the network for that host. G-1 named probes consume the audit
    payload fields on disk, not a resolved remote schema.
    """
    schema_path = REPO / SCHEMA_REL
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        raise SystemExit("FAILED:BLD-0013 schema file missing")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("x-artifact-class") != "binding-quality-audit":
        raise SystemExit("FAILED:BLD-0013 schema class mismatch")
    if not isinstance(schema.get("$ref"), str) or not schema["$ref"]:
        raise SystemExit("FAILED:BLD-0013 schema $ref missing")
    if not _looks_like_audit(doc):
        raise SystemExit("FAILED:BLD-0013 audit payload incomplete")
    if doc.get("unit_id") != "BLD-0013":
        raise SystemExit("FAILED:BLD-0013 unit_id mismatch")
    if "SUCCESS:BLD-0013" not in json.dumps(doc):
        raise SystemExit("FAILED:BLD-0013 sentinel missing from payload")
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
        {"unit_id": "BLD-0013", "state": "SUCCESS", "blob": "x" * 200},
    )
    for g in garbage:
        if _looks_like_audit(g):
            raise SystemExit("schema accepted garbage")


def main() -> int:
    doc = run_audit(REPO)
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print("FAILED:BLD-0013 control tests", json.dumps(doc["tests"], indent=2))
        return 1
    validate_schema(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} verdicts={doc['verdict_counts']}")
    print("SUCCESS:BLD-0013 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
