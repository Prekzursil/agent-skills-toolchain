#!/usr/bin/env python
"""Self-audit: every load-bearing number asserted in security-first.md must be
re-derivable from the measurement JSONs or from disk. A doc claim that no probe
supports is an overclaim and must be reported as one.

Control: two DELIBERATELY WRONG claims are injected into the expectation table
below (marked ctl_). If the auditor passes them, the auditor is broken.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
ARCH = REPO / "platform" / "architecture"
DOC = (ARCH / "security-first.md").read_text(encoding="utf-8")


def j(name: str) -> dict:
    return json.load(io.open(ARCH / name, encoding="utf-8"))


m1, m2, m3 = (
    j("_secfirst_measure.out.json"),
    j("_secfirst_measure2.out.json"),
    j("_secfirst_measure3.out.json"),
)
dd = j("_secfirst_probe_denydefault.out.json")
cat = json.load(
    io.open(REPO / "command-center" / "WORK-UNIT-CATALOG.json", encoding="utf-8")
)
wus = cat["work_units"]
AMBIENT = {"Read", "Grep", "Glob", "Write", "Edit", "Bash", "PowerShell"}
toks: set[str] = set()
only_amb = mcp_u = wild_u = 0
for u in wus:
    s = set(map(str, u.get("tool_permissions") or []))
    toks |= s
    if s and s <= AMBIENT:
        only_amb += 1
    if any(t.startswith("mcp__") for t in s):
        mcp_u += 1
    if any("*" in t for t in s):
        wild_u += 1
nonamb = sorted(t for t in toks if t not in AMBIENT)

CHECKS: list[tuple[str, object, object]] = [
    # (label, doc-asserted value, independently derived value)
    ("HEAD", "9f2dac7a", m2["git_scope"]["head"][:8]),
    ("platform schemas", 9, m1["wave1_inventory"]["schemas_platform_n"]),
    ("lib py", 64, m1["wave1_inventory"]["lib_py_n"]),
    ("councilspecs", 117, m1["wave1_inventory"]["council_specs_n"]),
    ("protocols", 48, m1["wave1_inventory"]["council_protocol_n"]),
    ("presets", 69, m1["wave1_inventory"]["council_preset_n"]),
    ("registry files", 7, len(m1["wave1_inventory"]["registry_files"])),
    ("cc schema shims", 233, m1["wave1_inventory"]["cc_schema_n"]),
    ("work_units", 2007, len(wus)),
    ("primary artifact set 431", 431, 9 + 64 + 117 + 7 + 233 + 1),
    ("reused unchanged 427", 427, (9 - 2) + (64 - 2) + 117 + 7 + 233 + 1),
    ("tracked cc schema", 0, m2["git_scope"]["tracked_cc_schema"]),
    ("untracked cc schema", 233, m2["git_scope"]["untracked_cc_schema"]),
    ("untracked total", 369, m2["git_scope"]["untracked_total"]),
    (
        "gitignore mentions cc/schema",
        False,
        m2["git_scope"]["gitignore_mentions_cc_schema"],
    ),
    ("receipt defs", 39, m1["receipt"]["defs_n"]),
    ("receipt mentions signature", 0, m1["receipt"]["mentions_signature"]),
    ("receipt mentions attestation", 0, m1["receipt"]["mentions_attestation"]),
    ("receipt mentions source_ref", 0, m1["receipt"]["mentions_source_ref"]),
    ("receipt mentions sha256", 3, m1["receipt"]["mentions_sha256"]),
    (
        "core requires produced_by",
        False,
        m3["receipt_authz_binding"]["core_requires_produced_by"],
    ),
    (
        "produced_by required",
        ["vendor", "model"],
        m3["receipt_authz_binding"]["produced_by_required"],
    ),
    (
        "receipt mentions tool_permissions",
        0,
        m3["receipt_authz_binding"]["mentions_tool_permissions"],
    ),
    (
        "security_report users",
        24,
        m2["output_schema"]["security_report_fragment_users"],
    ),
    ("output_schema refs", 2007, m2["output_schema"]["refs_total"]),
    (
        "tool_permissions distinct sets",
        151,
        m2["authorization_surface"]["tool_permissions_distinct"],
    ),
    (
        "owner_approval true",
        144,
        m2["authorization_surface"]["owner_approval_required"]["True"],
    ),
    (
        "owner_approval false",
        1863,
        m2["authorization_surface"]["owner_approval_required"]["False"],
    ),
    (
        "cloud-batch units",
        202,
        m2["authorization_surface"]["execution_substrate"]["cloud-batch"],
    ),
    ("security-bearing units", 132, m1["catalog"]["security_bearing_units_n"]),
    ("distinct tokens", 85, len(toks)),
    ("non-ambient tokens", 78, len(nonamb)),
    ("only-ambient units", 1435, only_amb),
    ("mcp-holding units", 261, mcp_u),
    ("wildcard units", 120, wild_u),
    ("prose/paren tokens", 16, len([t for t in nonamb if "(" in t])),
    ("colon-form tokens", 10, len([t for t in nonamb if ":" in t and "(" not in t])),
    ("mcp tokens", 48, len([t for t in nonamb if t.startswith("mcp__")])),
    (
        "plain native tokens",
        5,
        len(
            [
                t
                for t in nonamb
                if "(" not in t and ":" not in t and not t.startswith("mcp__")
            ]
        ),
    ),
    ("wfdsl rules", 14, dd["plane_asymmetry"]["workflow_dsl_rules_n"]),
    ("wfdsl authz rules", 1, len(dd["plane_asymmetry"]["workflow_dsl_authz_rules"])),
    ("work-unit rules", 7, dd["plane_asymmetry"]["work_unit_rules_n"]),
    ("work-unit authz rules", 0, len(dd["plane_asymmetry"]["work_unit_authz_rules"])),
    ("S1 fail-closed violations", 2, dd["S1_absent_policy"]["n_violations"]),
    ("S2 clean", 0, dd["S2_allowlisted"]["n_violations"]),
    ("S3 deny fires", 1, dd["S3_explicit_deny"]["n_violations"]),
    ("S4 default-allow clean", 0, dd["S4_default_allow"]["n_violations"]),
    ("quality.yml lines", 1427, m1["quality_yml"]["lines"]),
    ("quality.yml bytes", 98826, m1["quality_yml"]["bytes"]),
    ("ci jobs", 7, m2["ci_permissions"]["jobs_n"]),
    ("ci jobs with own perms", 1, m2["ci_permissions"]["jobs_with_own_permissions"]),
    ("ci top-level perms", True, m2["ci_permissions"]["top_level_permissions"]),
    ("gitleaks mentions", 34, m1["quality_yml"]["scanner_mentions"]["gitleaks"]),
    ("pull_request_target", 0, m1["quality_yml"]["pull_request_target"]),
    ("bandit absent", True, "bandit" in m2["ci_absent_scanners"]),
    ("codeql absent", True, "codeql" in m2["ci_absent_scanners"]),
    # Scoped to the 8 WAVE 1 test files. platform/lib/workflows/test_*.py is a CONCURRENT
    # sibling's in-flight work (mtimes postdate this unit) and is deliberately excluded --
    # a moving denominator is not a baseline.
    (
        "test functions (wave1 8 files)",
        214,
        sum(
            len(re.findall(r"^\s*def test_", io.open(p, encoding="utf-8").read(), re.M))
            for p in (REPO / "platform" / "lib").rglob("test_*.py")
            if "__pycache__" not in p.parts and "workflows" not in p.parts
        ),
    ),
    (
        "wave1 test files",
        8,
        len(
            [
                p
                for p in (REPO / "platform" / "lib").rglob("test_*.py")
                if "__pycache__" not in p.parts and "workflows" not in p.parts
            ]
        ),
    ),
    ("detector control OK", "DETECTOR-OK", m3["control_verdict"]),
    # ---- deliberately WRONG controls: the auditor MUST flag both ----
    ("ctl_wrong_workunits", 9999, len(wus)),
    ("ctl_wrong_presets", 1, m1["wave1_inventory"]["council_preset_n"]),
]

# VOLATILE claims are working-tree counts that concurrent sibling units move under us. They
# were correct at the measurement pin 9f2dac7a and the doc says so in its header. Drift in
# these is REPORTED, never treated as a doc error -- but drift in a STABLE claim (one derived
# from git-tracked content that the pin fixes) IS an error.
VOLATILE = {
    "HEAD",
    "lib py",
    "untracked total",
    "primary artifact set 431",
    "reused unchanged 427",
    "test functions (wave1 8 files)",
    "wave1 test files",
}

rows, bad, drift, ctl_caught = [], [], [], 0
for label, asserted, derived in CHECKS:
    ok = asserted == derived
    row = {
        "claim": label,
        "doc": asserted,
        "derived": derived,
        "ok": ok,
        "class": "volatile" if label in VOLATILE else "stable",
    }
    rows.append(row)
    if label.startswith("ctl_"):
        if not ok:
            ctl_caught += 1
    elif not ok:
        (drift if label in VOLATILE else bad).append(row)

# The pin claim the doc actually rests on: none of the 5 files this architecture modifies may
# have changed since 9f2dac7a, or the design section is stale.
import subprocess  # noqa: E402

PIN = "9f2dac7a"
TOUCHED = [
    "platform/schema/receipt.schema.json",
    "platform/schema/work-unit.normative.schema.json",
    "platform/lib/wfdsl/semantics.py",
    "platform/lib/completion_predicate.py",
    ".github/workflows/quality.yml",
    "command-center/WORK-UNIT-CATALOG.json",
]
diff = subprocess.run(
    ["git", "diff", "--name-only", f"{PIN}..HEAD", "--", *TOUCHED],
    cwd=str(REPO),
    capture_output=True,
    text=True,
    check=False,
).stdout.split()
commits = subprocess.run(
    ["git", "rev-list", "--count", f"{PIN}..HEAD"],
    cwd=str(REPO),
    capture_output=True,
    text=True,
    check=False,
).stdout.strip()

# also: does the doc TEXT literally contain each headline figure?
TEXT_FIGURES = [
    "9f2dac7a",
    "2,007",
    "151",
    "144",
    "1,435",
    "71.5",
    "261",
    "120",
    "78",
    "85",
    "233",
    "369",
    "427",
    "431",
    "132",
    "214",
    "1,427",
    "24",
    "48",
    "69",
    "117",
]
missing_in_text = [f for f in TEXT_FIGURES if f not in DOC]

out = {
    "probe": "secfirst_selfaudit",
    "pin": PIN,
    "commits_since_pin": commits,
    "design_touched_files_changed_since_pin": diff,
    "checks_n": len(CHECKS),
    "controls_n": sum(1 for c in CHECKS if c[0].startswith("ctl_")),
    "controls_caught": ctl_caught,
    "stable_mismatches": bad,
    "volatile_drift": drift,
    "figures_missing_from_doc_text": missing_in_text,
    "rows": rows,
}
auditor_ok = ctl_caught == out["controls_n"]
out["auditor_valid"] = auditor_ok
out["design_still_current"] = not diff
(ARCH / "_secfirst_selfaudit.out.json").write_text(
    json.dumps(out, indent=1, default=str), encoding="utf-8"
)

print(f"checks={len(CHECKS)} controls={out['controls_n']} controls_caught={ctl_caught}")
print(f"auditor_valid={auditor_ok}  (if False, every verdict below is meaningless)")
print(f"commits since pin {PIN}: {commits}")
print(
    f"design-touched files changed since pin: {diff or 'NONE -> design section is current'}"
)
print(f"STABLE mismatches (errors)  = {len(bad)}")
for b in bad:
    print("  MISMATCH", b)
print(f"VOLATILE drift (tree moved) = {len(drift)}")
for d in drift:
    print("  DRIFT", {k: d[k] for k in ("claim", "doc", "derived")})
print("figures missing from doc text:", missing_in_text)
ok = auditor_ok and not bad and not missing_in_text and not diff
print(
    "SUCCESS:secfirst-selfaudit" if ok else "FAILED:secfirst-selfaudit see-mismatches"
)
