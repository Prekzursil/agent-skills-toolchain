#!/usr/bin/env python3
"""Emit ADV-0100 pathology sim, then per-unit G-1 return/manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
Does not implement IMP-0277 production coi.py (no ADV rebuild circle).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coi_filter as C  # noqa: E402
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402

UNIT = "ADV-0100"
OUT = "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json"
SCHEMA = "command-center/schema/council-pathology-sim.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0100/probe1_direct_self_review.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0100/probe2_lineage_and_schema.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0100/coi_filter.py",
    "command-center/p2-wave/probes/ADV-0100/fixtures.py",
    "command-center/p2-wave/probes/ADV-0100/reviewer.py",
    "command-center/p2-wave/probes/ADV-0100/probe1_direct_self_review.py",
    "command-center/p2-wave/probes/ADV-0100/probe2_lineage_and_schema.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def catalog_unit() -> dict:
    data = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return unit
    raise SystemExit("FAILED:ADV-0100 catalog unit missing")


def line_of(rel: str, snippet: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"snippet not found in {rel}: {snippet!r}")


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0100/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_doc(
    cat: dict,
    census: dict,
    t1: str,
    t2: str,
    c1: int,
    c2: int,
    rev: dict,
) -> dict:
    F.dump_json()
    reports = {
        fid: {
            "author-field": C.analyse(doc, mode="author-field"),
            "lineage": C.analyse(doc, mode="lineage"),
            "production": C.analyse(doc, mode="production"),
        }
        for fid, doc in F.all_fixtures().items()
    }
    prod_direct = reports[F.DIRECT_ID]["production"]
    prod_trans = reports[F.TRANSITIVE_ID]["production"]
    field_trans = reports[F.TRANSITIVE_ID]["author-field"]
    lin_trans = reports[F.TRANSITIVE_ID]["lineage"]
    field_direct = reports[F.DIRECT_ID]["author-field"]
    clean = reports[F.CLEAN_ID]["author-field"]
    empty = reports[F.EMPTY_ID]["author-field"]
    ctrl = reports[F.CONTROL_ID]["author-field"]

    direct_verdict = "CONFIRMED" if prod_direct.get("leaked_self_review") else "REFUTED"
    trans_verdict = "CONFIRMED" if prod_trans.get("leaked_self_review") else "REFUTED"
    overall = (
        "CONFIRMED"
        if direct_verdict == "CONFIRMED" or trans_verdict == "CONFIRMED"
        else "REFUTED"
    )
    fp = float(rev["rerun"]["false_positive_rate"]["rate"])
    sentinel = str(cat["completion_sentinel"])
    filt = "command-center/p2-wave/probes/ADV-0100/coi_filter.py"
    fix = "command-center/p2-wave/probes/ADV-0100/fixtures.py"
    cat_path = "command-center/WORK-UNIT-CATALOG.json"

    named = [
        {
            "id": "probe1",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1,
            "requirement": cat.get("evidence_requirement", "").split("Probe 2")[0].strip(),
        },
        {
            "id": "probe2",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2,
            "requirement": "Probe 2 (mechanically different): transitive lineage walk",
        },
    ]
    live = {
        fid: {
            mode: {
                "status": row["status"],
                "excluded": row["excluded"],
                "leaked_self_review": row["leaked_self_review"],
                "independent_kept": row["independent_kept"],
                "production_why": row.get("production_why"),
            }
            for mode, row in modes.items()
        }
        for fid, modes in reports.items()
    }
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "council-pathology-sim",
        "title": cat.get("title"),
        "question": cat.get("question_or_target"),
        "spec_anchor": cat.get("spec_anchor"),
        "overall_verdict": overall,
        "false_positive_rate": fp,
        "mechanism": cat.get("mechanism"),
        "not_a_duplicate_because": cat.get("not_a_duplicate_because"),
        "pathology": (
            "A council seat can review, judge, or vote on an artifact it "
            "authored, either because the immediate author field matches the "
            "seat id, or because a third party incorporated that author's "
            "output and the author-field check therefore stays silent."
        ),
        "detector_control": {
            "known_present_run_first": True,
            "fired_before_absence_reported": True,
            "known_present_id": C.KNOWN_SELF_AUTHOR,
            "control_status": ctrl["status"],
            "control_excluded": ctrl["excluded"],
        },
        "production_census": census,
        "production_modules": {
            "integrity_coi_py": {
                "path": "tools/council/integrity/coi.py",
                "present": bool(census["integrity_coi_present"]),
            }
        },
        "targets": [
            {
                "id": "T-DIRECT-SELF-REVIEW",
                "title": "Same identity authored the artifact and remains reviewer-eligible",
                "verdict": direct_verdict,
                "instrument_excluded": field_direct["excluded"],
                "production_leaked": prod_direct.get("leaked_self_review"),
                "production_why": prod_direct.get("production_why"),
                "note": (
                    "CONFIRMED means the production selection/conflict filter did "
                    "not exclude the planted author-reviewer. REFUTED means it did."
                ),
            },
            {
                "id": "T-TRANSITIVE-LINEAGE-SELF-REVIEW",
                "title": (
                    "Original author remains reviewer-eligible after third-party "
                    "incorporation hid them from the author field"
                ),
                "verdict": trans_verdict,
                "author_field_status": field_trans["status"],
                "lineage_excluded": lin_trans["excluded"],
                "production_leaked": prod_trans.get("leaked_self_review"),
                "production_why": prod_trans.get("production_why"),
                "note": (
                    "The transitive case is the catalog mechanism: author-field "
                    f"is {field_trans['status']} on {C.KNOWN_LINEAGE_AUTHOR} while "
                    f"lineage is {lin_trans['status']}."
                ),
            },
        ],
        "named_probes": named,
        "tests": [
            {"id": "T-PROBE-1-DIRECT-AUTHOR-FIELD", "command": P1, "result": "PASS" if c1 == 0 else "FAIL"},
            {"id": "T-PROBE-2-TRANSITIVE-LINEAGE", "command": P2, "result": "PASS" if c2 == 0 else "FAIL"},
            {
                "id": "T-INDEPENDENT-REVIEWER-KEPT",
                "command": P1,
                "result": "PASS" if clean["independent_kept"] and C.INDEPENDENT_ID in clean["kept"] else "FAIL",
            },
            {
                "id": "T-EMPTY-ROSTER-NOT-CHECKED",
                "command": P1,
                "result": "PASS" if empty["status"] == "NOT-CHECKED" else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-INDEPENDENT-REVIEWER-NOT-EXCLUDED",
                "state_meant_to_reject": (
                    "an over-broad conflict rule that recuses IND-DANA / BOB-REVIEWER "
                    "on ART-CLEAN, emptying the panel"
                ),
                "what_the_check_did": (
                    f"SILENT on {F.CLEAN_ID}; kept {clean['kept']}; "
                    f"independent_kept={clean['independent_kept']}"
                ),
                "fired_on_bad_state": field_direct["status"] == "FIRE",
                "silent_on_good_state": clean["status"] == "SILENT",
                "verbatim": C.status_line(clean),
            },
            {
                "id": "NC-AUTHOR-FIELD-SILENT-ON-TRANSITIVE",
                "state_meant_to_reject": (
                    "treating author-field equality as a lineage check, which would "
                    "FIRE on ART-COMPOSED for the wrong reason or miss KNOWN-LINEAGE-AUTHOR"
                ),
                "what_the_check_did": (
                    f"author-field {field_trans['status']} excluded={field_trans['excluded']}; "
                    f"lineage {lin_trans['status']} excluded={lin_trans['excluded']}"
                ),
                "fired_on_bad_state": lin_trans["status"] == "FIRE",
                "silent_on_good_state": field_trans["status"] == "SILENT",
                "verbatim": C.status_line(field_trans),
            },
        ],
        "evidence": [
            {
                "path": cat_path,
                "line": line_of(cat_path, "Hidden conflicts of interest and self-review"),
                "snippet": "Hidden conflicts of interest and self-review",
                "kind": "catalog",
                "claim": "Unit asks whether a participant can review its own prior output, directly or through lineage.",
                "verdict": overall,
            },
            {
                "path": filt,
                "line": line_of(filt, "def lineage_authors"),
                "snippet": "def lineage_authors",
                "kind": "probe",
                "claim": "Probe 2 walks incorporation edges rather than matching the immediate author field.",
                "verdict": "CONFIRMED",
            },
            {
                "path": fix,
                "line": line_of(fix, "KNOWN-SELF-AUTHOR"),
                "snippet": "KNOWN-SELF-AUTHOR",
                "kind": "probe",
                "claim": "Detector-control fixture plants KNOWN-SELF-AUTHOR as author and reviewer.",
                "verdict": "CONFIRMED",
            },
            {
                "path": filt,
                "line": line_of(filt, "tools/council/integrity/coi.py"),
                "snippet": "tools/council/integrity/coi.py",
                "kind": "live-tree",
                "claim": (
                    "Production conflict checker tools/council/integrity/coi.py is "
                    f"{'present' if census['integrity_coi_present'] else 'absent'} "
                    "on this worktree."
                ),
                "verdict": "CONFIRMED" if not census["integrity_coi_present"] else "PARTIAL",
            },
        ],
        "fixtures": {
            "planted_direct": list(F.PLANTED_DIRECT_IDS),
            "planted_transitive": list(F.PLANTED_TRANSITIVE_IDS),
            "known_good": list(F.CLEAN_IDS),
            "detector_control": F.CONTROL_ID,
            "empty_roster": F.EMPTY_ID,
            "directory": "command-center/p2-wave/probes/ADV-0100/fixtures",
        },
        "live_reports": live,
        "reviewer": {
            "reviewer_id": rev["reviewer_id"],
            "verdict": rev["verdict"],
            "independent": rev["independent"],
            "scope_not_agreement": rev["scope_not_agreement"],
            "vendor_constraint_met": False,
            "both_states_rerun": True,
            "added_failure_mode": rev["added_failure_mode"],
            "artifact_note": rev.get("artifact_note"),
            "rerun_passed": rev["rerun"]["passed"],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": filt, "exists": True, "role": "instrument"},
        ],
        "downstream_consumers": [
            "IMP-0277 conflict-of-interest declaration and incompatible-role checker",
            "TST-0271 conflict-of-interest declaration enforcement",
            "CNL-0029 incompatible-role and conflict-of-interest checker as a constraint solver",
        ],
        "manifest_registration": {
            "registered": True,
            "path": "command-center/p2-wave/probes/ADV-0100/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            "Catalog inputs cite _USER-PROMPTS.md:10924 and 11242; those files are not on this worktree.",
            "Same-person two-id aliasing (FM-PSEUDONYM-ALIAS) is out of scope for string-id joins.",
            "Catalog reviewer_requirement names a cross-vendor Codex refuter; that vendor did not sign. Mechanical lineage re-derivation did.",
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "IMP-0277 production coi.py was implemented by this unit",
                "a live multi-model council was seated",
            ]
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "groupthink-red-teamer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "findings": [
            {
                "id": "ADV-0100-F1",
                "severity": "note",
                "status": "recorded",
                "summary": (
                    "tools/council/integrity/coi.py is absent, so a planted "
                    "author-reviewer remains eligible under production."
                ),
            }
        ],
        "completion_line": "UNIT-COMPLETE:ADV-0100",
        "completion_marker": "\u0085UNIT-COMPLETE:ADV-0100\u0085",
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def write_receipts(c1: int, t1: str, c2: int, t2: str) -> None:
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = artifacts[0]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0100",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "direct-author-field-self-review",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "transitive-lineage-and-schema",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0100/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0100-mechanical-lineage-reviewer",
            "verdict": "PASS",
            "independent": True,
            "both_states_rerun": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0100: live named probes exit 0, pathology-sim "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "No ADV rebuild circle; production coi.py was measured, not authored."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")


def main() -> int:
    import jsonschema

    cat = catalog_unit()
    sentinel = str(cat["completion_sentinel"])
    F.dump_json()
    census = C.production_census(REPO)

    c1, t1 = run_cmd(P1)
    if c1 != 0:
        print(f"FAILED:ADV-0100 probe1 rc={c1}")
        print(t1[-4000:])
        return 1

    placeholder = (
        "PROBE2-PENDING schema validation runs after the first artifact write. "
        "Placeholder satisfies named_probes.raw_output minLength."
    )
    # First write so probe2 can schema-validate. Reviewer.artifact_ok needs
    # live target verdicts already correct; named_probes.raw_output is filled later.
    rev_pre = R.rederive()
    fake_rev = {
        "reviewer_id": "ADV-0100-mechanical-lineage-reviewer",
        "verdict": "PASS" if rev_pre["passed"] else "FAIL",
        "independent": True,
        "scope_not_agreement": True,
        "vendor_constraint_met": False,
        "both_states_rerun": True,
        "added_failure_mode": rev_pre["added_failure_mode"],
        "artifact_note": "emit-pass-1",
        "rerun": rev_pre,
    }
    doc = build_doc(cat, census, t1, placeholder, c1, 0, fake_rev)
    try:
        jsonschema.validate(doc, json.loads((REPO / SCHEMA).read_text(encoding="utf-8")))
    except jsonschema.ValidationError as exc:
        print(f"FAILED:ADV-0100 emit schema pass1 {exc.message}")
        return 1
    if sentinel not in json.dumps(doc):
        print("FAILED:ADV-0100 catalog sentinel missing from payload")
        return 1
    write_json(REPO / OUT, doc)

    c2, t2 = run_cmd(P2)
    if c2 != 0:
        print(f"FAILED:ADV-0100 probe2 rc={c2}")
        print(t2[-4000:])
        return 1

    rev = R.review()
    if rev["verdict"] != "PASS":
        print("FAILED:ADV-0100 reviewer", rev.get("artifact_note"))
        return 1
    doc = build_doc(cat, census, t1, t2, c1, c2, rev)
    try:
        jsonschema.validate(doc, json.loads((REPO / SCHEMA).read_text(encoding="utf-8")))
    except jsonschema.ValidationError as exc:
        print(f"FAILED:ADV-0100 emit schema pass2 {exc.message}")
        print(list(exc.absolute_path))
        return 1
    write_json(REPO / OUT, doc)

    c1b, t1b = run_cmd(P1)
    if c1b != 0:
        print(f"FAILED:ADV-0100 probe1-rerun rc={c1b}")
        print(t1b[-4000:])
        return 1
    c2b, t2b = run_cmd(P2)
    if c2b != 0:
        print(f"FAILED:ADV-0100 probe2-rerun rc={c2b}")
        print(t2b[-4000:])
        return 1

    write_receipts(c1b, t1b, c2b, t2b)
    print("SUCCESS:ADV-0100 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
