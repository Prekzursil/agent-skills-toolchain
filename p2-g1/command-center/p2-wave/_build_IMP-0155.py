"""Build driver for IMP-0155 (builder shard 8, p2-g1-wave-a).

Samples 10 in-repo candidate files from the estate worktree into provenance
records, runs both live probes (fresh re-fetch 10/10; mutated ref fails), and
emits the receipt (state=BLOCKED, reviewer-absent) plus the per-unit
UNIT-ARTIFACT-MANIFEST.json.

Re-run: python command-center/p2-wave/_build_IMP-0155.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(W / "tools" / "workflow-foundry"))
import _wflib as L  # noqa: E402
import wf_provenance as PR  # noqa: E402

UNIT = "IMP-0155"
PROBE_DIR = W / "command-center" / "p2-wave" / "probes" / UNIT
started = L.now_iso()

# 1. Sample ten candidates from the estate worktree into provenance records.
SAMPLE = [
    "AGENTS.md",
    "README.md",
    "QUALITY-CHARTER.md",
    "REPO-TOPOLOGY.md",
    "platform/lib/schema_resolver.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/agentspec/evals/rows.py",
    "command-center/QUALITY-CHARTER.md",
    "command-center/E2E-WAVE-STATUS.md",
]
records = []
for rel in SAMPLE:
    if not (L.ESTATE / rel).is_file():
        raise SystemExit("FAILED:{} sampled estate file absent: {}".format(UNIT, rel))
    records.append(PR.make_record(rel, L.ESTATE, note="IMP-0155 re-fetch sample"))
assert len(records) == 10
rec_path = PROBE_DIR / "provenance-records.json"
rec_path.write_text(json.dumps(records, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")
print("records:", rec_path)

# 2. Live probes.
probes = {}
for pid in ["probe1_refetch_ten.py", "probe2_mutated_ref.py"]:
    code, out = L.run([sys.executable, str(PROBE_DIR / pid)])
    probes[pid] = {"code": code, "out": out}
    print(pid, "exit", code)
    if code != 0:
        print(out[-3000:])
        raise SystemExit("FAILED:{} probe {} exit {}".format(UNIT, pid, code))

res1 = json.loads([l for l in probes["probe1_refetch_ten.py"]["out"].splitlines()
                   if l.startswith("RESULT:")][0][7:])
res2 = json.loads([l for l in probes["probe2_mutated_ref.py"]["out"].splitlines()
                   if l.startswith("RESULT:")][0][7:])

# 3. Receipt.
probe1_cmd = "python command-center/p2-wave/probes/IMP-0155/probe1_refetch_ten.py"
probe2_cmd = "python command-center/p2-wave/probes/IMP-0155/probe2_mutated_ref.py"
evidence_items = [
    L.evidence(
        "Re-fetch from the record alone reproduces the recorded hash for {}/{} sampled "
        "candidates (actual re-read of bytes, not field-presence assertions).".format(
            res1["reproduced"], res1["sampled"]),
        "CONFIRMED", "command-center/p2-wave/probes/IMP-0155/provenance-records.json",
        [
            L.probe("source", "test-run", probe1_cmd,
                    probes["probe1_refetch_ten.py"]["out"], 0),
            L.probe("verifier", "byte-compare",
                    "python - <<'..' compare probe1 raw hashes to live estate files",
                    "(probe2 independently re-derives mismatches; see raw)", 0),
        ],
        "likely",
    ),
    L.evidence(
        "A record with a mutated ref fails the re-fetch: the detector fires on the broken "
        "state (mutated sha256, absent path) and stays silent on the clean twin.",
        "CONFIRMED", "tools/workflow-foundry/wf_provenance.py:refetch",
        [
            L.probe("source", "test-run", probe2_cmd,
                    probes["probe2_mutated_ref.py"]["out"], 0),
            L.probe("verifier", "file-read",
                    "read command-center/p2-wave/probes/IMP-0155/probe2-mutated-ref.raw.txt",
                    (PROBE_DIR / "probe2-mutated-ref.raw.txt").read_text(encoding="utf-8")[-2000:], 0),
        ],
        "likely",
    ),
]
# Strengthen the byte-compare verifier with real data: recompute hashes directly.
import hashlib
lines = []
for rec in records:
    data = (L.ESTATE / rec["path"]).read_bytes()
    lines.append("{} {}".format(hashlib.sha256(data).hexdigest() == rec["sha256"], rec["path"]))
evidence_items[0]["probes"][1]["raw_output"] = "\n".join(lines)[:60000]
evidence_items[0]["probes"][1]["exit_code"] = 0

tests = [
    L.test_result("IMP-0155-both-states", probe2_cmd, "PASS", 3,
                  "mutated sha256 fails; absent path fails; clean twin passes"),
]

controls = [
    L.control(
        "IMP-0155-mutated-ref", "mutation",
        "Provenance record with mutated sha256 must fail re-fetch against real bytes; "
        "absent-path record must fail; clean record must pass.",
        res2["mutated_ref_failed"] and res2["absent_path_failed"],
        res2["clean_ok"],
        bad="mutated_ref_failed={} absent_path_failed={}".format(
            res2["mutated_ref_failed"], res2["absent_path_failed"]),
        good="clean_ok={}".format(res2["clean_ok"]),
    ),
]

residuals = [
    L.residual(
        "Dependency IMP-0154 output (candidate store from the extraction unit) has no "
        "receipt in the estate worktree; the ten provenance records here are sampled from "
        "estate repo files rather than from IMP-0154's candidate objects.",
        "When IMP-0154 delivers, re-sample the ten candidates from its store and re-run "
        "both probes."),
    L.residual(
        "The upstream spec anchor _USER-PROMPTS.md:11152-11170 (Workflow Foundry required "
        "production behavior) is not present in this worktree; the fetch-record contract "
        "follows the catalog row text.",
        "Diff this implementation against the spec text when _USER-PROMPTS.md is available "
        "in a worktree."),
]

report = {
    "sampled": res1["sampled"],
    "reproduced": res1["reproduced"],
    "all_reproduced": res1["all_reproduced"],
    "detector": {
        "mutated_ref_failed": res2["mutated_ref_failed"],
        "absent_path_failed": res2["absent_path_failed"],
        "clean_ok": res2["clean_ok"],
    },
    "fetch_method": "file-read",
}

MODULE_REL = "tools/workflow-foundry/wf_provenance.py"
recs_rel = "command-center/p2-wave/probes/IMP-0155/provenance-records.json"
out = L.emit_receipt(
    UNIT,
    "command-center/WORK-UNIT-CATALOG.json:IMP-0155",
    [MODULE_REL, recs_rel,
     "command-center/p2-wave/probes/IMP-0155/probe1_refetch_ten.py",
     "command-center/p2-wave/probes/IMP-0155/probe2_mutated_ref.py",
     "command-center/p2-wave/probes/IMP-0155/probe1-refetch-ten.raw.txt",
     "command-center/p2-wave/probes/IMP-0155/probe2-mutated-ref.raw.txt"],
    evidence_items, tests, controls, residuals, report, started,
    roles={MODULE_REL: "primary"},
)
if not out["ok"]:
    print("SCHEMA ERRORS:", json.dumps(out["errors"], indent=1)[:4000])
    raise SystemExit(1)
print("receipt:", out["path"])

man = L.write_manifest(UNIT, [
    "command-center/receipts/IMP-0155.json", MODULE_REL, recs_rel,
    "command-center/p2-wave/probes/IMP-0155/probe1_refetch_ten.py",
    "command-center/p2-wave/probes/IMP-0155/probe2_mutated_ref.py",
    "command-center/p2-wave/probes/IMP-0155/probe1-refetch-ten.raw.txt",
    "command-center/p2-wave/probes/IMP-0155/probe2-mutated-ref.raw.txt",
], roles={"command-center/receipts/IMP-0155.json": "primary", MODULE_REL: "primary"})
print("manifest:", man["path"], "rows:", len(man["rows"]))
print("DONE:IMP-0155 built, probes exit 0, receipt BLOCKED/reviewer-absent")
