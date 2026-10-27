"""What does the completion predicate actually say about the 7 review-only units, BEFORE and
AFTER the reviewer gate is satisfied? Measure it; do not guess which state to write."""

import copy
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
IDS = [
    "AUD-0006",
    "AUD-0020",
    "AUD-0021",
    "AUD-0030",
    "AUD-0041",
    "AUD-0051",
    "CC-0002",
]
cat = json.loads(
    (ROOT / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by_id = {u["id"]: u for u in cat["work_units"]}

rvspec = importlib.util.spec_from_file_location(
    "receipt_validate", ROOT / "command-center/receipt_validate.py"
)
rv = importlib.util.module_from_spec(rvspec)
rvspec.loader.exec_module(rv)
ids = rv.catalog_ids()
# NOTE: import the gate through receipt_validate._load_gate(). A direct
# spec_from_file_location+exec_module raises inside @dataclass on py3.14 because the module is
# not yet in sys.modules; _load_gate registers it first. Reviewer-instrument note, recorded.
gate = g = rv._load_gate()
print("gate public names:", [n for n in dir(gate) if not n.startswith("_")][:40])

report = {}
for uid in IDS:
    p = ROOT / by_id[uid]["output_path"]
    doc = json.loads(p.read_text(encoding="utf-8"))
    admitted, _, reason = rv.admit(p, ids, g)
    errs = gate.validate_receipt(doc)
    row = {
        "path": by_id[uid]["output_path"],
        "state": doc.get("state"),
        "admitted": admitted,
        "admit_reason": reason,
        "schema_errors": errs[:3],
        "manifest_registration": doc.get("manifest_registration"),
        "reviewer": doc.get("reviewer"),
        "defects_open": len(
            [
                d
                for d in (doc.get("defects") or [])
                if str(d.get("status", "")).lower() not in ("closed", "fixed")
            ]
        ),
    }
    # what does the reducer/predicate say?
    for fn in (
        "evaluate_receipt",
        "completion_predicate",
        "evaluate",
        "reduce_receipt",
        "predicate",
        "evaluate_completion",
    ):
        f = getattr(gate, fn, None)
        if callable(f):
            try:
                res = f(doc)
                row["predicate_fn"] = fn
                row["predicate_result"] = (
                    res
                    if isinstance(res, (str, int, bool))
                    else json.loads(json.dumps(res, default=str))[:6]
                    if isinstance(res, list)
                    else str(res)[:900]
                )
            except Exception as exc:  # noqa: BLE001
                row["predicate_fn"] = fn
                row["predicate_result"] = f"{type(exc).__name__}: {exc}"
            break
    # AFTER simulating an independent PASS reviewer
    sim = copy.deepcopy(doc)
    sim["reviewer"] = {"independent": True, "reviewer_id": "SIM", "verdict": "PASS"}
    sim["state"] = "SUCCESS"
    row["schema_errors_after_sim"] = gate.validate_receipt(sim)[:3]
    f = getattr(gate, row.get("predicate_fn", ""), None)
    if callable(f):
        try:
            row["predicate_after_sim"] = str(f(sim))[:900]
        except Exception as exc:  # noqa: BLE001
            row["predicate_after_sim"] = f"{type(exc).__name__}: {exc}"
    report[uid] = row
    print(
        f"\n{uid}  state={row['state']} admitted={admitted} "
        f"manifest_registration={row['manifest_registration']} open_defects={row['defects_open']}"
    )
    print(f"   schema_errors now  : {row['schema_errors']}")
    print(f"   schema_errors (sim): {row['schema_errors_after_sim']}")
    print(
        f"   predicate  now  [{row.get('predicate_fn')}]: {str(row.get('predicate_result'))[:500]}"
    )
    print(f"   predicate (sim)     : {str(row.get('predicate_after_sim'))[:500]}")

(ROOT / "command-center/p2-next/REVIEW-PREDICATE-PROBE.json").write_text(
    json.dumps(report, indent=2, default=str), encoding="utf-8"
)
print("\nSUCCESS:predicate-probe")
