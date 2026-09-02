import json
import sys
import tempfile
from pathlib import Path

HERE = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\IMP-0426")
REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import output_schema_gate as gate  # noqa: E402
from scenario import run_schema_invalid, run_valid  # noqa: E402

with tempfile.TemporaryDirectory(prefix="s09-imp0426-") as tmp:
    root = Path(tmp)
    valid = run_valid(workdir=root / "valid")
    invalid = run_schema_invalid(workdir=root / "invalid")

vg = valid["schema_gate"]
ig = invalid["schema_gate"]
checks = {
    "valid.terminal_kind==SUCCESS": valid["terminal_kind"] == "SUCCESS",
    "vg.classification==CLASS_OK": vg["classification"] == gate.CLASS_OK,
    "vg.valid is True": vg["valid"] is True,
    "vg.enforced is True": vg["enforced"] is True,
    "vg.retries_used==0": vg["retries_used"] == 0,
    "vg.consumer_invoked is True": vg["consumer_invoked"] is True,
    "len(valid.consumer_payloads)==1": len(valid["consumer_payloads"]) == 1,
    "valid payload answer": valid["consumer_payloads"][0].get("answer") == "typed-output-path-ok" if valid["consumer_payloads"] else False,
    "invalid.terminal_kind==FAILED": invalid["terminal_kind"] == "FAILED",
    "ig.classification==CLASS_SCHEMA_INVALID": ig["classification"] == gate.CLASS_SCHEMA_INVALID,
    "ig.valid is False": ig["valid"] is False,
    "ig.retries_used==0": ig["retries_used"] == 0,
    "ig.consumer_invoked is False": ig["consumer_invoked"] is False,
    "len(invalid.consumer_payloads)==0": len(invalid["consumer_payloads"]) == 0,
    "len(invalid.attempts)==1": len(invalid["attempts"]) == 1,
    "decide_retry(SCHEMA_INVALID,0,False) is None": gate.decide_retry(gate.CLASS_SCHEMA_INVALID, 0, False) is None,
    "decide_retry(MCP,0,False)=='ignore-user-config'": gate.decide_retry(gate.CLASS_MCP, 0, False) == "ignore-user-config",
    "decide_retry(MCP,1,False) is None": gate.decide_retry(gate.CLASS_MCP, 1, False) is None,
}
for k, v in checks.items():
    print(("PASS " if v else "FAIL "), k)
print()
print("valid.terminal_kind:", valid["terminal_kind"])
print("vg:", json.dumps({k: vg.get(k) for k in ("classification", "valid", "enforced", "retries_used", "consumer_invoked")}, default=str))
print("invalid.terminal_kind:", invalid["terminal_kind"])
print("ig:", json.dumps({k: ig.get(k) for k in ("classification", "valid", "enforced", "retries_used", "consumer_invoked")}, default=str))
print("gate CLASS_OK:", gate.CLASS_OK, "CLASS_SCHEMA_INVALID:", gate.CLASS_SCHEMA_INVALID, "CLASS_MCP:", gate.CLASS_MCP)
print("decide_retry MCP,0:", gate.decide_retry(gate.CLASS_MCP, 0, False))
