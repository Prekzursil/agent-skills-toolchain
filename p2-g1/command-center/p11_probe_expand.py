"""P11 - ESCALATION EXPANSION (spec :11153).

The sampled non-confirmation rate exceeded this unit's declared 20% threshold in all three waves,
so re-verification expands from the headline rows into the audits' SUB-SECTION numbers. Two of the
sharpest sub-claims are re-derived here, both of them both-states claims (the class most likely to
be theatre if wrong):

  E1  Wave 1 detector control arm A: "6/6 known-valid PASS, 10/10 known-invalid FIRE, 5 caught by
      the schema layer only and 5 by semantics only" -> if true, a schema-only gate over presets is
      fail-open across half the defect classes, which is the load-bearing consequence.
  E2  Wave 2: "the 14 skips are not hidden failures - 11 `declares no secret param` + 3 `has no
      fanout stage`, both conditional parametrised skips".
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LIB = REPO / "platform" / "lib"
OUT: dict[str, object] = {}

# ------------------------------------------------------------------ E1
sys.path.insert(0, str(LIB))
from jsonschema.validators import Draft202012Validator  # noqa: E402

import councilspec.semantics as sem  # noqa: E402

schema = json.loads(
    (REPO / "platform/schema/councilspec.schema.json").read_text(encoding="utf-8")
)
validator = Draft202012Validator(schema)

ex_dir = REPO / "platform" / "schema" / "examples"
files = sorted(p for p in ex_dir.rglob("*.json")) if ex_dir.is_dir() else []
valid_expected = [p for p in files if re.match(r"^E\d", p.name)]
invalid_expected = [p for p in files if re.match(r"^N\d", p.name)]


def layers(p: Path) -> tuple[bool, bool, str]:
    """-> (schema_ok, semantics_ok, note)."""
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, False, f"unparseable: {e}"
    serrs = list(validator.iter_errors(d))
    schema_ok = not serrs
    sem_ok, note = True, ""
    try:
        findings = sem.check(d)
        errs = sem.errors(findings)
        sem_ok = not errs
        note = "; ".join(str(getattr(e, "message", e))[:80] for e in list(errs)[:2])
    except Exception as exc:
        sem_ok, note = False, f"semantics raised {type(exc).__name__}: {exc}"
    return schema_ok, sem_ok, note or (str(serrs[0].message)[:90] if serrs else "")


rows = []
for p in valid_expected + invalid_expected:
    s, m, note = layers(p)
    rows.append(
        {
            "file": p.name,
            "expected": "VALID" if p in valid_expected else "INVALID",
            "schema_layer": "PASS" if s else "FIRE",
            "semantics_layer": "PASS" if m else "FIRE",
            "overall": "PASS" if (s and m) else "FIRE",
            "note": note,
        }
    )
vp = [r for r in rows if r["expected"] == "VALID"]
ip = [r for r in rows if r["expected"] == "INVALID"]
schema_only = [
    r["file"]
    for r in ip
    if r["schema_layer"] == "FIRE" and r["semantics_layer"] == "PASS"
]
sem_only = [
    r["file"]
    for r in ip
    if r["schema_layer"] == "PASS" and r["semantics_layer"] == "FIRE"
]
both = [
    r["file"]
    for r in ip
    if r["schema_layer"] == "FIRE" and r["semantics_layer"] == "FIRE"
]
OUT["E1_wave1_detector_control_armA"] = {
    "claim": "6/6 known-valid PASS, 10/10 known-invalid FIRE, 5 schema-only, 5 semantics-only",
    "examples_dir": str(ex_dir),
    "known_valid_files": len(vp),
    "known_valid_all_pass": all(r["overall"] == "PASS" for r in vp),
    "known_valid_that_FIRED": [r["file"] for r in vp if r["overall"] != "PASS"],
    "known_invalid_files": len(ip),
    "known_invalid_all_fire": all(r["overall"] == "FIRE" for r in ip),
    "known_invalid_that_PASSED": [r["file"] for r in ip if r["overall"] != "FIRE"],
    "caught_by_schema_layer_only": schema_only,
    "caught_by_semantics_layer_only": sem_only,
    "caught_by_both_layers": both,
    "semantics_only_count": len(sem_only),
    "schema_only_count": len(schema_only),
    "detector_control": (
        "PASS - fires on every known-invalid AND stays silent on every known-valid"
        if all(r["overall"] == "FIRE" for r in ip)
        and all(r["overall"] == "PASS" for r in vp)
        else "FAIL - see the two mismatch lists"
    ),
    "rows": rows,
}

# ------------------------------------------------------------------ E2
p = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "workflows/test_bp1_blueprint_conformance.py",
        "-q",
        "--no-header",
        "-rs",
        "-p",
        "no:cacheprovider",
    ],
    cwd=str(LIB),
    capture_output=True,
    text=True,
    check=False,
)
txt = p.stdout + p.stderr
secret = len(re.findall(r"declares no secret param", txt))
fanout = len(re.findall(r"has no fanout stage", txt))
m = re.search(r"(\d+) passed(?:, (\d+) skipped)?", txt)
OUT["E2_wave2_skip_accounting"] = {
    "claim": "14 skips = 11 'declares no secret param' + 3 'has no fanout stage', no hidden failures",
    "exit": p.returncode,
    "summary": m.group(0) if m else None,
    "skips_reported": int(m.group(2)) if m and m.group(2) else 0,
    "reason_declares_no_secret_param": secret,
    "reason_has_no_fanout_stage": fanout,
    "reasons_sum": secret + fanout,
    "tail": txt.strip().splitlines()[-1:],
}

dest = REPO / "command-center" / "P11-EXPANSION.json"
dest.write_text(json.dumps(OUT, indent=2, default=str), encoding="utf-8")
summary = {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in OUT.items()}
print(json.dumps(summary, indent=2, default=str))
print(f"SUCCESS:p11-expansion {dest}")
