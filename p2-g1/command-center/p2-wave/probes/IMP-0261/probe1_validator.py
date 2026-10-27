"""IMP-0269 probe 1 sibling for IMP-0261: target validator over the 58/72 library.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0261/probe1_validator.py
Exit 0 iff the live tools/council/validate.py --library --report exits 0 with
58 protocols + 72 presets and zero invalid rows, AND the two catalog negative
controls fire: an unknown section key fails closed (CS-UNKNOWN-SECTION-KEY,
CLI exit 1) and a preset missing its stopping rule fails closed
(CS-STOPPING-MISSING, CLI exit 1).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council"))
from validate import library_report, validate_doc  # type: ignore

CS_UNKNOWN_SECTION_KEY = "CS-UNKNOWN-SECTION-KEY"
CS_STOPPING_MISSING = "CS-STOPPING-MISSING"

checks: dict[str, bool] = {}
report = library_report()
checks["library_58_protocols"] = report["protocols"] == 58
checks["library_72_presets"] = report["presets"] == 72
checks["library_zero_invalid"] = report["invalid"] == []
checks["library_report_ok"] = report["ok"] is True

good_preset = {"kind": "preset", "id": "PR-NEG", "name": "neg", "stopping": {"rule": "quorum"}}
unknown = dict(good_preset)
unknown["bananas"] = {"rule": "quorum"}  # unknown section key
missing_stopping = {k: v for k, v in good_preset.items() if k != "stopping"}

r_unknown = validate_doc(unknown)
r_missing = validate_doc(missing_stopping)
checks["unknown_key_fails_closed"] = (
    not r_unknown["ok"]
    and any(v["id"] == CS_UNKNOWN_SECTION_KEY for v in r_unknown["violations"])
)
checks["missing_stopping_fails_closed"] = (
    not r_missing["ok"]
    and any(v["id"] == CS_STOPPING_MISSING for v in r_missing["violations"])
)

with tempfile.TemporaryDirectory() as td:
    p_good = Path(td) / "good.json"
    p_unknown = Path(td) / "unknown.json"
    p_missing = Path(td) / "missing.json"
    p_good.write_text(json.dumps(good_preset), encoding="utf-8")
    p_unknown.write_text(json.dumps(unknown), encoding="utf-8")
    p_missing.write_text(json.dumps(missing_stopping), encoding="utf-8")
    validator = W / "tools" / "council" / "validate.py"
    def cli(path: Path) -> int:
        return subprocess.run(
            [sys.executable, "-B", str(validator), str(path)],
            capture_output=True, text=True, cwd=str(W),
        ).returncode
    checks["cli_good_exit_0"] = cli(p_good) == 0
    checks["cli_unknown_exit_1"] = cli(p_unknown) == 1
    checks["cli_missing_stopping_exit_1"] = cli(p_missing) == 1

ok = all(checks.values())
out = {"probe": "probe1-library-and-negative-controls", "unit_id": "IMP-0261",
       "protocols": report["protocols"], "presets": report["presets"],
       "invalid": report["invalid"], "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-validator.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0261-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0261-probe1 58/72 library validates; unknown-key and missing-stopping fail closed")
