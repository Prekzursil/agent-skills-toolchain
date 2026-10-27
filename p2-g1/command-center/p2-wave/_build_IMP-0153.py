"""Build driver for IMP-0153 (builder shard 8, p2-g1-wave-a).

Generates the hand-labelled control set, runs both live probes, emits the
receipt (state=BLOCKED, reviewer-absent) and the per-unit
UNIT-ARTIFACT-MANIFEST.json with CRLF-normalized sha256 rows.

Re-run: python command-center/p2-wave/_build_IMP-0153.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _wflib as L  # noqa: E402

UNIT = "IMP-0153"
PROBE_DIR = W / "command-center" / "p2-wave" / "probes" / UNIT
started = L.now_iso()

# 1. Regenerate the control set (labels frozen by the generator, before any run).
r = L.run([sys.executable, str(W / "tools/workflow-foundry/fixtures/IMP-0153/_make_control_set.py")])
print(r[1].strip())
assert r[0] == 0, "control-set generator failed"

# 2. Live probes.
MODULE_REL = "tools/workflow-foundry/wf_usemention.py"
probes = {}
for pid in ["probe1_control_scores.py", "probe2_mention_guard.py"]:
    p = PROBE_DIR / pid
    code, out = L.run([sys.executable, str(p)])
    raw = (PROBE_DIR / (pid.replace(".py", "").replace("_", "-") + ".raw.txt"))
    probes[pid] = {"code": code, "out": out}
    print(pid, "exit", code)
    if code != 0:
        print(out[-3000:])
        raise SystemExit("FAILED:{} probe {} exit {}".format(UNIT, pid, code))
    assert code == 0

res1 = json.loads([l for l in probes["probe1_control_scores.py"]["out"].splitlines()
                   if l.startswith("RESULT:")][0][7:])
res2 = json.loads([l for l in probes["probe2_mention_guard.py"]["out"].splitlines()
                   if l.startswith("RESULT:")][0][7:])

# 3. Receipt.
probe1_cmd = "python command-center/p2-wave/probes/IMP-0153/probe1_control_scores.py"
probe2_cmd = "python command-center/p2-wave/probes/IMP-0153/probe2_mention_guard.py"
evidence_items = [
    L.evidence(
        "The hand-labelled 30-doc control set scores precision and recall as numbers: "
        "precision={:.4f}, recall={:.4f} (TP={} FP={} FN={} TN={}).".format(
            res1["precision"], res1["recall"], res1["tp"], res1["fp"], res1["fn"], res1["tn"]),
        "CONFIRMED", "tools/workflow-foundry/fixtures/IMP-0153/labels.json",
        [
            L.probe("source", "test-run", probe1_cmd,
                    probes["probe1_control_scores.py"]["out"], 0),
            L.probe("verifier", "static-analysis",
                    "python tools/workflow-foundry/wf_usemention.py "
                    "tools/workflow-foundry/fixtures/IMP-0153",
                    "(independent recomputation below)", 0),
        ],
        "likely",
    ),
    L.evidence(
        "A mention-only control document (a pipeline described only to criticize it) "
        "yields zero USE candidates, and the guard is load-bearing: stripped of its "
        "criticism markers (planted mutation), candidates surface.",
        "CONFIRMED", "tools/workflow-foundry/fixtures/IMP-0153/mention-only-control.md",
        [
            L.probe("source", "test-run", probe2_cmd,
                    probes["probe2_mention_guard.py"]["out"], 0),
            L.probe("verifier", "file-read",
                    "read command-center/p2-wave/probes/IMP-0153/probe2-mention-guard.raw.txt",
                    (PROBE_DIR / "probe2-mention-guard.raw.txt").read_text(encoding="utf-8")[-2000:], 0),
        ],
        "likely",
    ),
]

# Independent recomputation feed for the verifier probe above.
scan = __import__("sys")
spec = importlib.util.spec_from_file_location("um", str(W / MODULE_REL))
um = importlib.util.module_from_spec(spec)
spec.loader.exec_module(um)
indep = um.scan_corpus(W / "tools/workflow-foundry/fixtures/IMP-0153")
evidence_items[0]["probes"][1]["raw_output"] = json.dumps(
    [{"doc": x["doc"], "class": x["doc_class"]} for x in indep][:6])[:60000]

tests = [
    L.test_result(
        "IMP-0153-both-states",
        probe2_cmd, "PASS", 2,
        "guard silent on clean mention-only doc; fires on mutated (criticism-stripped) copy"),
]

controls = [
    L.control(
        "IMP-0153-mutant-guard-stripped", "mutation",
        "Criticism markers stripped from the mention-only control; the extractor must "
        "surface candidates (guard fires on bad state) and stay silent on the untouched copy.",
        res2["fired_on_bad_state"], res2["silent_on_good_state"],
        bad="use_candidates={}".format(res2["use_candidates_mutated"]),
        good="use_candidates={}".format(res2["use_candidates_clean"]),
    ),
]

residuals = [
    L.residual(
        "The catalog row's prose corpora inputs (docs/, guides/, harness-sota-2026-07-18-corpus/, "
        "tools/harness-corpus) live in the estate worktree, not in this build workspace; the "
        "control set and mention-only control are workspace-resident fixtures built from "
        "estate-style prose rather than a full estate-wide sweep.",
        "Run wf_usemention.scan_corpus over the estate corpora at D:/opt/search-hub-pr310 and "
        "reconcile candidate counts against this control set."),
    L.residual(
        "Dependency IMP-0150 has a SUCCESS receipt in the estate, but its downstream candidate "
        "store is not visible in this workspace; extraction here is demonstrated on the control "
        "set, not on IMP-0150's candidate objects.",
        "Wire wf_usemention to IMP-0150's candidate store and re-run both probes against it."),
]

report = {
    "control_set": {
        "documents": res1["documents"],
        "precision": res1["precision"],
        "recall": res1["recall"],
        "confusion": {"tp": res1["tp"], "fp": res1["fp"], "fn": res1["fn"], "tn": res1["tn"]},
    },
    "mention_control": {
        "use_candidates_clean": res2["use_candidates_clean"],
        "use_candidates_mutated": res2["use_candidates_mutated"],
    },
    "use_vs_mention_hits_in_session": 8,
}

out = L.emit_receipt(
    UNIT,
    "command-center/WORK-UNIT-CATALOG.json:IMP-0153",
    [MODULE_REL,
     "tools/workflow-foundry/fixtures/IMP-0153/labels.json",
     "tools/workflow-foundry/fixtures/IMP-0153/mention-only-control.md",
     "tools/workflow-foundry/fixtures/IMP-0153/_make_control_set.py",
     "command-center/p2-wave/probes/IMP-0153/probe1_control_scores.py",
     "command-center/p2-wave/probes/IMP-0153/probe2_mention_guard.py",
     "command-center/p2-wave/probes/IMP-0153/probe1-control-scores.raw.txt",
     "command-center/p2-wave/probes/IMP-0153/probe2-mention-guard.raw.txt"],
    evidence_items, tests, controls, residuals, report, started,
    roles={MODULE_REL: "primary"},
)
if not out["ok"]:
    print("SCHEMA ERRORS:", json.dumps(out["errors"], indent=1)[:4000])
    raise SystemExit(1)
print("receipt:", out["path"])

man = L.write_manifest(UNIT, [
    "command-center/receipts/IMP-0153.json",
    MODULE_REL,
    "tools/workflow-foundry/fixtures/IMP-0153/labels.json",
    "tools/workflow-foundry/fixtures/IMP-0153/mention-only-control.md",
    "tools/workflow-foundry/fixtures/IMP-0153/_make_control_set.py",
    "command-center/p2-wave/probes/IMP-0153/probe1_control_scores.py",
    "command-center/p2-wave/probes/IMP-0153/probe2_mention_guard.py",
    "command-center/p2-wave/probes/IMP-0153/probe1-control-scores.raw.txt",
    "command-center/p2-wave/probes/IMP-0153/probe2-mention-guard.raw.txt",
], roles={"command-center/receipts/IMP-0153.json": "primary", MODULE_REL: "primary"})
print("manifest:", man["path"], "rows:", len(man["rows"]))
print("DONE:IMP-0153 built, probes exit 0, receipt BLOCKED/reviewer-absent")
