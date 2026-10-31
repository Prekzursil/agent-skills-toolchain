"""IMP-0204 probe 1 (source, both-states): a retired workflow id remains
resolvable and returns the successor; a consumer pinned to the retired id still
executes (no hard break) and emits the typed superseded warning naming the
successor. The silent-deletion mutant shows what the public path must NOT do.

Exit 0 iff every assertion below passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools"))
from workflows.retirement import Catalog  # noqa: E402

RAW = HERE / "probe1-resolve-and-pin.raw.txt"

OLD = "wf.catalog-class.discovery-only"
NEW = "wf.catalog-class.typed-restore"

cat = Catalog()
cat.publish({"id": OLD, "body": {"stages": ["discovery-only-scan"]}})
cat.publish({"id": NEW, "body": {"stages": ["typed-restore-scan"]}})
cat.supersede(OLD, NEW, migration={"path": "swap discovery-only for typed-restore"},
              reason="discovery-only lane corrupted receipts")

res = cat.resolve(OLD)
lines = [json.dumps({"probe": "probe1-resolve-and-pin", "unit_id": "IMP-0204",
                     "resolve_present": res["present"], "resolve_retired": res["retired"],
                     "successor_id": res["successor_id"],
                     "body_still_readable": res["body"] is not None})]
assert res["present"] and res["retired"], "retired id stopped resolving"
assert res["successor_id"] == NEW, res["successor_id"]
assert res["successor"]["body"] == {"stages": ["typed-restore-scan"]}

cat.pin_consumer("consumer-pinned-to-old", OLD)
run = cat.execute_consumer("consumer-pinned-to-old")
lines.append(json.dumps({"pin_executed": run["ok"], "hard_break": run["hard_break"],
                         "executed_id": run["executed_id"],
                         "warnings": run["warnings"]}))
assert run["ok"] and not run["hard_break"], "pinned consumer hard-broke"
assert run["executed_id"] == OLD
assert any(w["code"] == "WARN_SUPERSEDED" and w["successor_id"] == NEW
           for w in run["warnings"]), run["warnings"]

# Bad state (the mutation): silent deletion breaks resolve + pinned execute,
# which is exactly what the public delete() path refuses to do.
cat2 = Catalog()
cat2.publish({"id": OLD, "body": {"stages": ["discovery-only-scan"]}})
cat2.publish({"id": NEW, "body": {}})
cat2.pin_consumer("pinned", OLD)
cat2.force_drop_for_probe(OLD)
mutant_resolve_broke = False
try:
    cat2.resolve(OLD)
except KeyError:
    mutant_resolve_broke = True
mutant_pin_broke = False
try:
    cat2.execute_consumer("pinned")
except KeyError:
    mutant_pin_broke = True
lines.append(json.dumps({"silent_delete_resolve_broke": mutant_resolve_broke,
                         "silent_delete_pin_hard_broke": mutant_pin_broke}))
assert mutant_resolve_broke and mutant_pin_broke, "silent-deletion mutant no longer breaks"

lines.append("PASS: retired id resolves to successor, pinned consumer still runs, "
             "silent deletion breaks (counterexample live)")
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"retired_resolves": True,
                              "successor_id": res["successor_id"],
                              "pinned_still_runs": True,
                              "warning_code": "WARN_SUPERSEDED",
                              "hard_break": False}))
print("SUCCESS:IMP-0204-probe1 retired id resolves; pinned consumer still runs")
