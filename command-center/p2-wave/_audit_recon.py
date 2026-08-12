"""AUDIT: verify AUD-0041's 4/4 static-vs-API reconciliation and the 56-skipped-steps claim."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PW = REPO / "command-center/p2-wave"

d = json.loads((PW / "probes/AUD-0041/probe2-actions-api.json").read_text(encoding="utf-8"))
tot = 0
print(f"  api error field: {d.get('error')!r}")
for r in d["runs"]:
    sk = sum(len(j["skipped_steps"]) for j in r["jobs"])
    tot += sk
    print(f"  {r['workflow']:<22} run={r['run_id']} api_jobs={r['api_job_count']} skipped_steps={sk}")
print(f"  runs sampled: {len(d['runs'])}   TOTAL skipped steps: {tot}")

a = json.loads((REPO / "command-center/audit/AUD-0041-ci-step-inventory.json").read_text(encoding="utf-8"))
rec = a["report"]["leg_reconciliation"]
print()
print(f"  leg_reconciliation type={type(rec).__name__}")
print(json.dumps(rec, indent=1)[:1200])

# control: did the matrix expander actually get exercised?
ctl = json.loads((PW / "probes/AUD-0041/control-matrix-expansion.json").read_text(encoding="utf-8"))
print()
print("  control-matrix-expansion.json:")
print(json.dumps(ctl, indent=1)[:900])
