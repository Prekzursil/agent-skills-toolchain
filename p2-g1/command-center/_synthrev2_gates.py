"""Synthesis-review pass 2: RE-EXECUTE all 22 lane gates named in GRIND-GATE-RESULTS.json.

Three-state detector control runs FIRST and must discriminate before any verdict is read.
Writes JSON to stdout. Nothing here reads a lane's claim about itself.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable

GATES = [
    ("SSOT", "ssot_wiring_check", [PY, "command-center/ssot/ssot_wiring_check.py"]),
    ("SSOT", "ssot_drift_gate", [PY, "command-center/ssot/ssot_drift_gate.py"]),
    (
        "SSOT",
        "pytest test_ssot_wiring",
        [PY, "-m", "pytest", "ci/tests/test_ssot_wiring.py", "-q"],
    ),
    (
        "HOOKRESEARCH",
        "check_citations",
        [PY, "command-center/hook-audit/check_citations.py"],
    ),
    (
        "HOOKRESEARCH",
        "hook_predeploy_gate",
        [PY, "command-center/hook-audit/hook_predeploy_gate.py"],
    ),
    (
        "HOOKRESEARCH",
        "pytest test_citation_gate",
        [PY, "-m", "pytest", "command-center/hook-audit/test_citation_gate.py", "-q"],
    ),
    (
        "HOOKRESEARCH",
        "test_citation_gate DIRECT",
        [PY, "command-center/hook-audit/test_citation_gate.py"],
    ),
    ("MCPRESEARCH", "mcp-audit ci_gate", [PY, "command-center/mcp-audit/ci_gate.py"]),
    ("RULERESEARCH", "rule-audit ci_gate", [PY, "docs/rule-audit/ci_gate.py"]),
    (
        "RULERESEARCH",
        "r2_control_count_gate",
        [PY, "docs/rule-audit/r2_control_count_gate.py"],
    ),
    (
        "RULERESEARCH",
        "r3_corpus_parity_gate",
        [PY, "docs/rule-audit/r3_corpus_parity_gate.py"],
    ),
    (
        "RULERESEARCH",
        "r4_credential_rule_gate",
        [PY, "docs/rule-audit/r4_credential_rule_gate.py"],
    ),
    (
        "RULERESEARCH",
        "r4_receipt_argv_gate",
        [PY, "docs/rule-audit/r4_receipt_argv_gate.py"],
    ),
    (
        "RULERESEARCH",
        "r5_deploy_drift_gate",
        [PY, "docs/rule-audit/r5_deploy_drift_gate.py"],
    ),
    ("P2NEXT", "rail_count_gate", [PY, "command-center/p2-next/rail_count_gate.py"]),
    (
        "P2NEXT",
        "split_review_gate",
        [PY, "command-center/p2-next/split_review_gate.py"],
    ),
    (
        "SLOP",
        "check_published_commands",
        [PY, "command-center/slop-report/check_published_commands.py"],
    ),
    (
        "DOCS",
        "pytest test_docs_executable_claims",
        [PY, "-m", "pytest", "ci/tests/test_docs_executable_claims.py", "-q"],
    ),
    (
        "DOCS",
        "pytest test_docs_gate_ci_wiring",
        [PY, "-m", "pytest", "ci/tests/test_docs_gate_ci_wiring.py", "-q"],
    ),
    (
        "DOCS",
        "pytest test_command_doc_promises",
        [PY, "-m", "pytest", "ci/tests/test_command_doc_promises.py", "-q"],
    ),
    (
        "SKILLS2",
        "pytest test_deploy_skills_daily",
        [PY, "-m", "pytest", "ci/tests/test_deploy_skills_daily.py", "-q"],
    ),
    (
        "SKILLS2",
        "pytest test_check_skill_deploy_drift",
        [PY, "-m", "pytest", "ci/tests/test_check_skill_deploy_drift.py", "-q"],
    ),
    (
        "CIGREEN",
        "interpreter_floor_gate",
        [PY, "command-center/ci/interpreter_floor_gate.py"],
    ),
]


def run(args, timeout=600):
    try:
        p = subprocess.run(
            args,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"rc": None, "state": "TIMEOUT", "tail": ""}
    except FileNotFoundError as e:
        return {"rc": None, "state": "MISSING", "tail": str(e)}
    tail = ((p.stdout or "") + (p.stderr or "")).strip().replace("\r\n", "\n")
    tail = "\n".join(tail.split("\n")[-4:])[-400:]
    state = "PASS" if p.returncode == 0 else "FAIL"
    return {"rc": p.returncode, "state": state, "tail": tail}


out = {"detector_control": {}, "results": []}

# --- three-state control, run BEFORE any verdict is read -------------------------
ctl = []
ctl.append(("__control_pos", "PASS", run([PY, "-c", "raise SystemExit(0)"])))
ctl.append(("__control_neg", "FAIL", run([PY, "-c", "raise SystemExit(1)"])))
missing = run([PY, str(REPO / "command-center" / "__no_such_gate_zzz.py")])
# python on a nonexistent script exits 2 -> normalise to MISSING for the control
if missing["rc"] == 2 and "can't open file" in missing["tail"].lower():
    missing["state"] = "MISSING"
ctl.append(("__control_missing", "MISSING", missing))
out["detector_control"]["rows"] = [
    {
        "label": lbl,
        "expected": exp,
        "got": r["state"],
        "rc": r["rc"],
        "ok": r["state"] == exp,
    }
    for lbl, exp, r in ctl
]
out["detector_control"]["discriminates"] = len(
    {r["got"] for r in out["detector_control"]["rows"]}
) == 3 and all(r["ok"] for r in out["detector_control"]["rows"])

if not out["detector_control"]["discriminates"]:
    print(json.dumps(out, indent=2))
    raise SystemExit("FAILED:detector-control-did-not-discriminate")

for lane, gate, cmd in GATES:
    r = run(cmd)
    out["results"].append(
        {
            "lane": lane,
            "gate": gate,
            "cmd": " ".join(["python" if c == PY else c for c in cmd]),
            **r,
        }
    )

st = {}
for r in out["results"]:
    st[r["state"]] = st.get(r["state"], 0) + 1
out["summary"] = st
print(json.dumps(out, indent=2, ensure_ascii=False))
