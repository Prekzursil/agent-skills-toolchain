"""IMP-0261 probe 2: independent jsonschema Draft202012 agreement.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0261/probe2_jsonschema.py
Exit 0 iff the independent `jsonschema` Draft202012Validator (a different
mechanism from validate.py's hand-rolled checks) agrees item-for-item with
validate_doc over every library row, accepts a full 13-section compiled
CouncilSpec, rejects the unknown-section-key mutant, rejects the
missing-stopping mutant, and the `python -m jsonschema` CLI reaches the same
verdicts (exit 0 good, exit 1 bad).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council"))
from validate import library_report, validate_doc  # type: ignore

SCHEMA = W / "tools" / "council" / "schema" / "councilspec.schema.json"
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
validator = jsonschema.Draft202012Validator(schema)

checks: dict[str, bool] = {}

report = library_report()
rows = [i for i in report["items"] if i["kind"] in {"preset", "protocol"}]
checks["library_rows_present"] = len(rows) == 130

agree = 0
for row in rows:
    doc = {"kind": row["kind"], "id": row["id"], "name": row.get("name", ""),
           "family": row.get("family", ""), "description": row.get("description", "")}
    if row["kind"] == "preset":
        doc["stopping"] = {"rule": "quorum"}
        doc["version"] = "1"
    js_ok = validator.is_valid(doc)
    vt_ok = bool(validate_doc(doc)["valid"])
    # jsonschema is structural; validate_doc also requires stopping on presets.
    agree += 1 if (js_ok == vt_ok) else 0
checks["item_for_item_agreement_130"] = agree == 130

spec13 = {
    "kind": "councilspec", "stopping": {"rule": "quorum"},
    "charter": {"title": "13-section"}, "participants": {"n": 3},
    "roles": {"chair": "alice"}, "engagement": {"mode": "round-robin"},
    "budgets": {"max_turns": 6}, "evidence": {"required": True},
    "voting": {"mode": "majority"}, "outcomes": {"artifact": "decision"},
    "integrity": {"dupes": "audit"}, "artifacts": {"transcript": True},
    "execution": {"substrate": "local"}, "meta": {"id": "CS-13"},
}
checks["spec13_jsonschema_ok"] = validator.is_valid(spec13)
checks["spec13_validate_doc_ok"] = bool(validate_doc(spec13)["valid"])

unknown = dict(spec13)
unknown["bananas"] = {"rule": "quorum"}
checks["spec13_unknown_rejected"] = not validator.is_valid(unknown)

missing_stopping = {k: v for k, v in spec13.items() if k != "stopping"}
checks["spec13_missing_stopping_rejected"] = not validator.is_valid(missing_stopping)

with tempfile.TemporaryDirectory() as td:
    p13 = Path(td) / "spec13.json"
    pbad = Path(td) / "unknown.json"
    p13.write_text(json.dumps(spec13), encoding="utf-8")
    pbad.write_text(json.dumps(unknown), encoding="utf-8")

    def cli(path: Path) -> int:
        p = subprocess.run(
            [sys.executable, "-I", "-m", "jsonschema", "--instance", str(path), str(SCHEMA)],
            capture_output=True, text=True, cwd=str(W),
        )
        return p.returncode

    checks["cli_good_exit_0"] = cli(p13) == 0
    checks["cli_unknown_exit_1"] = cli(pbad) != 0

ok = all(checks.values())
out = {"probe": "probe2-independent-jsonschema", "unit_id": "IMP-0261",
       "agreement": f"{agree}/{len(rows)}",
       "jsonschema_impl_version": jsonschema.__version__ if hasattr(jsonschema, "__version__") else "n/a",
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True, default=str))
RAW = Path(__file__).resolve().parent / "probe2-jsonschema.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0261-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0261-probe2 independent jsonschema agrees item-for-item; negatives rejected")
