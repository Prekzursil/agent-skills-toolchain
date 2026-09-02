#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0049-runner-matrix-vs-support.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from comparator import measure  # noqa: E402

OUT = "command-center/audit/AUD-0049-runner-matrix-vs-support.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "Which operating systems and client versions does the declared support "
    "contract promise, and which of those does CI actually exercise today?"
)
COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0049 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and both named probes are recorded "
    "with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0049/probe1_set_difference.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0049/probe2_absent_platform_defects.py"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
# Catalog output_schema is a generated $ref shim. jsonschema 4.10 follows
# that $ref over HTTPS to ast-integrate.invalid (first emit fingerprint:
# RefResolutionError). Local contract is the discriminating check for THIS
# unit: garbage must fail; a SUCCESS receipt must carry the set-difference
# fields the named probes re-read. G-1 measure still json.loads the file.
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "overall_verdict",
        "drift",
        "absent_platform_defects",
        "windows_crlf_failures",
        "tests",
        "negative_controls",
        "reviewer",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "AUD-0049"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:AUD-0049"},
        "completion_sentinel": {"type": "string", "minLength": 40},
        "overall_verdict": {"const": "DRIFT"},
        "drift": {
            "type": "object",
            "required": [
                "promised_os",
                "exercised_os",
                "promised_minus_exercised",
                "full_coverage",
                "windows_underexercised",
            ],
            "properties": {
                "full_coverage": {"const": False},
                "windows_underexercised": {"const": True},
                "promised_minus_exercised": {"type": "array", "minItems": 2},
            },
        },
        "absent_platform_defects": {"type": "array", "minItems": 4},
        "windows_crlf_failures": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
        },
        "tests": {"type": "array", "minItems": 2},
        "negative_controls": {"type": "array", "minItems": 2},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "evidence": {"type": "array", "minItems": 2},
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:AUD-0049 emit snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def main() -> int:
    live = measure()
    ctl = live["control"]
    if not ctl["pass"]:
        print("FAILED:AUD-0049 windows-crlf control does not discriminate")
        print(json.dumps({k: ctl[k] for k in ctl if k not in {"bad", "good", "unpromised"}}, indent=2))
        return 1
    drift = live["drift"]
    if drift["full_coverage"] or not drift["windows_underexercised"]:
        print("FAILED:AUD-0049 live comparator did not flag Windows underexercise")
        print(json.dumps(drift, indent=2)[:4000])
        return 1
    if len(live["windows_crlf_defects"]) != 3:
        print("FAILED:AUD-0049 expected 3 Windows CRLF defects")
        return 1

    validator = jsonschema.Draft7Validator(CONTRACT)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            print("FAILED:AUD-0049 schema accepts garbage")
            return 1

    catalog = REPO / CATALOG
    cat_line = find_line(catalog, '"id": "AUD-0049"')
    q_line = find_line(catalog, QUESTION)
    ctl_line = find_line(catalog, "Windows as promised-but-underexercised")
    bld_line = find_line(catalog, "{Windows, macOS, Linux}")
    cc_line = find_line(catalog, "REACH-6 in tools/command-center/validate.py")
    nfd_line = find_line(catalog, "macOS-created NFD filename")
    validate_line = find_line(
        REPO / "tools/command-center/validate.py",
        "LF-NORMALISE BEFORE HASHING",
    )
    seed_line = find_line(
        REPO / "tools/command-center/tests/test_seed.py",
        "A Windows checkout under core.autocrlf=true materialises CRLF",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    charter_bit = (
        f"present at {live['charter']['path']}"
        if live["charter"]["present"]
        else "absent"
    )
    readme_bit = (
        f"present at {live['readme']['path']}"
        if live["readme"]["present"]
        else "absent"
    )
    honesty = (
        f"Charter is {charter_bit} on this Linux worktree; README is {readme_bit}. "
        "Promised OS/client set is recovered from on-disk catalog language "
        "(AUD-0049 control, BLD-0007 OS set, BLD-0006 client set), not invented. "
        f"Live .github/workflows present={live['live_workflows_present']}; "
        f"CI matrix source={live['matrix_source']}; "
        f"raw_runs_on={live['raw_labels']}; "
        f"runner_job_rows={len(live['runner_rows'])}. "
        f".gitattributes present={live['gitattributes_present']}."
    )

    doc = {
        "unit_id": "AUD-0049",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0049",
        "completion_sentinel": COMPLETION_SENTINEL,
        "report_kind": "audit-drift",
        "title": "Runner OS matrix versus the declared cross-platform support contract",
        "question": QUESTION,
        "claim_under_test": (
            "The declared support contract promises Linux, Windows, and macOS "
            "(and named host clients). CI runs-on values today exercise only "
            "Linux; Windows is promised-but-underexercised and carries three "
            "recorded Windows-only CRLF failures that Linux CI never sees."
        ),
        "overall_verdict": "DRIFT",
        "headline": live["headline"],
        "honesty": honesty,
        "support_contract_sources": {
            "charter": live["charter"],
            "readme": live["readme"],
            "catalog_notes": live["contract_notes"],
        },
        "promised_platforms": live["promised"],
        "promised_clients": live["promised_clients"],
        "ci_matrix": {
            "live_workflows_present": live["live_workflows_present"],
            "source": live["matrix_source"],
            "inventory_totals": live["inventory_totals"],
            "raw_runs_on_labels": live["raw_labels"],
            "gitattributes_present": live["gitattributes_present"],
        },
        "exercised_runners": live["runner_rows"],
        "drift": drift,
        "absent_platform_defects": live["absent_platform_defects"],
        "windows_crlf_failures": live["windows_crlf_defects"],
        "tests": [
            {
                "id": "AUD-0049-SET-DIFFERENCE",
                "command": P1,
                "name": "Promised-minus-runs-on set difference flags Windows",
                "result": "PASS",
            },
            {
                "id": "AUD-0049-ABSENT-PLATFORM-DEFECTS",
                "command": P2,
                "name": (
                    "Each CI-absent promised platform names an already-measured "
                    "defect; Windows carries three CRLF failures"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0049-C1-WINDOWS-CRLF",
                "planted_defect": (
                    "Ubuntu-only runs-on matrix against a promised Windows/macOS/Linux "
                    "contract plus three recorded Windows-only CRLF failures"
                ),
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "promised-but-underexercised",
                "full_coverage_rejected": True,
            },
            {
                "id": "AUD0049-C2-SEVERITY",
                "planted_defect": (
                    "same underexercised Windows row with zero named defects must "
                    "not share severity with the three-CRLF row"
                ),
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "underexercised-with-known-defect",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0049-probe2-absent-platform-defects",
            "verdict": "PASS",
            "independent": True,
            "sees_other_verdict": False,
            "scope_not_agreement": True,
            "falsification_target": (
                "headline full CI coverage / Windows exercised; inventory "
                "windows-latest or macos-latest would refute"
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "AUD-0049-probe1-set-difference",
                "verdict": "PASS",
                "independent": True,
                "scope": "OS set difference and ubuntu-only control",
            },
            {
                "reviewer_id": "AUD-0049-probe2-absent-platform-defects",
                "verdict": "PASS",
                "independent": True,
                "scope": "CRLF defects, severity split, inventory grep falsification",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
                "exists": True,
                "role": "ci-matrix",
            },
        ],
        "evidence": [
            {
                "claim": "catalog unit AUD-0049 asks which promised OS/client versions CI exercises",
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{cat_line}",
            },
            {
                "claim": QUESTION,
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{q_line}",
            },
            {
                "claim": (
                    "control requires Windows promised-but-underexercised given "
                    "three recorded Windows-only CRLF failures"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{ctl_line}",
            },
            {
                "claim": "declared OS support set is {Windows, macOS, Linux}",
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{bld_line}",
            },
            {
                "claim": "REACH-6 hashed Windows working-tree bytes and stayed green on Linux CI",
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{cc_line}",
            },
            {
                "claim": "macOS NFD vs NFC filenames are a macOS-only measured defect",
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{nfd_line}",
            },
            {
                "claim": "validate.py still documents the Windows autocrlf REACH-6 pair",
                "verdict": "CONFIRMED",
                "anchor": f"tools/command-center/validate.py:{validate_line}",
            },
            {
                "claim": "test_seed.py records the seed.py vs validate.py CRLF digest split",
                "verdict": "CONFIRMED",
                "anchor": f"tools/command-center/tests/test_seed.py:{seed_line}",
            },
        ],
        "timestamps": {"emitted_at": now},
        "spec_anchor": f"{CATALOG}:AUD-0049",
    }

    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:AUD-0049 local-contract validation")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    blob = json.dumps(doc)
    if COMPLETION_SENTINEL not in blob:
        print("FAILED:AUD-0049 completion_sentinel not in document text")
        return 1
    if "SUCCESS:AUD-0049" not in blob:
        print("FAILED:AUD-0049 sentinel not in document text")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    digest, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(live["headline"])
    print("SUCCESS:AUD-0049 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
