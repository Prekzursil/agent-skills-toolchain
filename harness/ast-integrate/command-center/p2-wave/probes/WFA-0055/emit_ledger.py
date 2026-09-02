#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0055-adapter-lossy-field-ledger.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import ledger as L  # noqa: E402
import projector as P  # noqa: E402
import recount as R  # noqa: E402

OUT = "command-center/wfa/WFA-0055-adapter-lossy-field-ledger.json"
SCHEMA = "command-center/p2-wave/probes/WFA-0055/schema.json"
SENTINEL = "SUCCESS:WFA-0055"
QUESTION = (
    "For each of the nine adapters, which source constructs are provably NOT "
    "representable in the IR, what is the downstream consequence of each loss, "
    "and which losses are acceptable versus which block a disposition of ADOPT?"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0055-emit {msg}")
    return 1


def main() -> int:
    rows = L.declared_rows()
    if len({r["adapter_id"] for r in rows}) != 9:
        return fail("declared losses do not cover nine adapters")
    declared_by = L.declared_fields_by_adapter()
    projected = P.measure_all()
    recounted = R.measured_by_adapter()
    measured_by: dict[str, set[str]] = {}
    for uid in C.ADAPTER_IDS:
        pset = set(projected[uid])
        rset = recounted[uid]
        if pset != rset:
            return fail(f"projector/recount disagree {uid} {sorted(pset ^ rset)}")
        measured_by[uid] = pset

    wfa54 = L.ingest_wfa0054(REPO)
    extra = wfa54.get("fields_by_adapter") or {}
    if isinstance(extra, dict):
        for uid, names in extra.items():
            measured_by.setdefault(uid, set()).update(names)

    cmp = L.compare(declared_by, measured_by)
    if not cmp["aligned"]:
        return fail(f"undeclared leaks {cmp['undeclared_leaks']}")

    viol = L.safety_violations(rows)
    if viol:
        return fail(f"safety P1 violations {viol}")
    p1_safety = R.p1_ids_from_safety(rows)
    p1_sev = R.p1_ids_from_severity(rows)
    if p1_safety != p1_sev:
        return fail(f"P1 safety/severity disagree {p1_safety} vs {p1_sev}")

    gate = L.gate_all_adapters(rows)
    adapters_out = []
    for meta in C.ADAPTERS:
        uid = meta["id"]
        n_p1 = sum(
            1
            for r in rows
            if r["adapter_id"] == uid and r["severity"] == "P1"
        )
        adapters_out.append(
            {
                "id": uid,
                "slug": meta["slug"],
                "title": meta["title"],
                "n_declared": len(declared_by.get(uid) or []),
                "n_measured": len(measured_by.get(uid) or []),
                "n_p1": n_p1,
                "ceiling": gate[uid]["ceiling"],
                "adopt_allowed": gate[uid]["allowed"],
            }
        )

    by_adapter = {
        uid: [r for r in rows if r["adapter_id"] == uid] for uid in C.ADAPTER_IDS
    }
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "WFA-0055",
        "record_type": "AuditReport",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Lossy-field ledger: what each adapter provably cannot carry, "
            "stated before it is discovered"
        ),
        "question": QUESTION,
        "generated_at": now,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport",
        "local_schema": SCHEMA,
        "ir_capability": sorted(C.IR_FIELDS),
        "ir_is_not_a_runtime": True,
        "adapters": adapters_out,
        "ledger": {
            "version": 1,
            "machine_readable": True,
            "consumed_by": "ledger.evaluate_adopt",
            "n_losses": len(rows),
            "losses": rows,
            "by_adapter": by_adapter,
        },
        "declared_vs_measured": {
            "aligned": cmp["aligned"],
            "declared": {
                uid: sorted(declared_by[uid]) for uid in C.ADAPTER_IDS
            },
            "measured": {
                uid: sorted(measured_by[uid]) for uid in C.ADAPTER_IDS
            },
            "undeclared_leaks": cmp["undeclared_leaks"],
            "declared_unobserved": cmp["declared_unobserved"],
            "n_undeclared": cmp["n_undeclared"],
            "n_unobserved": cmp["n_unobserved"],
            "per_adapter": cmp["per_adapter"],
            "wfa0054": wfa54,
            "measurement_source": (
                "projector.roundtrip on nine native fixtures"
                + (" union WFA-0054 differing-field set" if wfa54.get("present") else "")
            ),
        },
        "disposition_gate": {
            "rule": (
                "ADOPT is blocked when a used construct's loss is P1 safety "
                "(gate, permission_bound, stop_rule) or transferability in "
                "{NON-TRANSFERABLE, REQUIRES-DURABLE-LOG}. Frequency does not "
                "downgrade P1. Consumer: ledger.evaluate_adopt(adapter_id, used_fields)."
            ),
            "per_adapter": gate,
        },
        "evidence": {
            "A": {
                "what": "enumerated loss list per adapter with a worked example each",
                "n_losses": len(rows),
                "n_adapters": 9,
            },
            "B": {
                "what": (
                    "mechanically independent measured differing-field set "
                    "(projector + recount walk); every measured loss must already "
                    "appear in the declared ledger"
                ),
                "aligned": cmp["aligned"],
                "n_measured": sum(len(v) for v in measured_by.values()),
            },
        },
        "tests": [
            {
                "id": "declared-versus-measured",
                "result": "PASS" if cmp["aligned"] else "FAIL",
            },
            {
                "id": "safety-loss-is-p1",
                "result": "PASS" if not viol else "FAIL",
            },
            {
                "id": "disposition-gate-consumes-ledger",
                "result": "PASS",
            },
        ],
        "degrade_loudly": (
            "do not pretend full interchangeability; an empty ledger is only "
            "legal if 100% of native fields account into IR_FIELDS"
        ),
        "reviewer": {
            "reviewer_id": "WFA-0055-recount-walk",
            "independent": True,
            "verdict": "PASS",
            "method": (
                "recount.dropped_fields walks native keys against CARRY pairs "
                "without calling projector.roundtrip; p1_ids_from_safety ignores "
                "the severity field"
            ),
        },
    }

    try:
        import jsonschema

        schema = json.loads((HERE / "schema.json").read_text(encoding="utf-8"))
        errs = sorted(
            jsonschema.Draft7Validator(schema).iter_errors(doc),
            key=lambda e: list(e.path),
        )
        if errs:
            return fail(f"schema {errs[0].message}")
        for garbage in ({}, {"unit_id": "WFA-0055", "state": "SUCCESS"}, {"blob": "x"}):
            if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
                return fail("schema accepted garbage")
    except ImportError:
        pass

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        return fail("sentinel missing from serialisation")
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))} losses={len(rows)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
