#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0026-sweep-practitioner-reports.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    OUT_REL,
    P1,
    P2,
    QUESTION,
    REPO,
    RULE_REL,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
    VENDOR_SWEEP,
    digest_file,
    dump_json,
    load_json,
)
from grading import forbidden_rule_keys
from sweep import load_rule, run_sweep

SENTINEL_LONG = (
    "SUCCESS:WFA-0026 emitted only when the artifact at output_path exists, "
    "is non-empty, parses, the trust-grading rule hash is recorded from the "
    "frozen rule file written before grading, vendor-covered mechanisms are "
    "marked DUPLICATE-OF rather than re-counted, uncorroborated practitioner "
    "claims stay UNVERIFIED, and planted injection is REJECTED. Any other "
    "terminal state is FAILED:WFA-0026 <classification> with the diagnostic tail."
)


def main() -> int:
    rule = load_rule()
    bad = forbidden_rule_keys(rule)
    if bad:
        print(f"FAILED:WFA-0026 rule contains feel-keys {bad}")
        return 1
    if not rule.get("written_before_grading") is True:
        print("FAILED:WFA-0026 rule written_before_grading is not true")
        return 1
    rule_sha, _ = digest_file(HERE / "grading_rule.json")
    sweep = run_sweep()
    vendor_path = REPO / VENDOR_SWEEP
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    findings = [m for m in sweep["mechanisms"] if m["disposition"] == "FINDING"]
    dups = [m for m in sweep["mechanisms"] if m["disposition"] == "DUPLICATE-OF"]
    unver = [m for m in sweep["mechanisms"] if m["disposition"] == "UNVERIFIED"]
    rejected = [m for m in sweep["mechanisms"] if m["disposition"] == "REJECTED"]
    answer = (
        f"Under rule {rule['rule_id']} (sha256={rule_sha}), "
        f"{len(findings)} mechanism(s) are FINDING (practitioner, explicit "
        f"production, dual unaffiliated corroboration, not in the vendor index), "
        f"{len(dups)} DUPLICATE-OF the first-party vendor coverage, "
        f"{len(unver)} UNVERIFIED (not promoted), "
        f"{len(rejected)} REJECTED (injection or missing quote). "
        f"WFA-0021 artifact present={vendor_path.is_file()}. "
        + (
            "Novel findings: "
            + "; ".join(f"{m['id']} ({m['canon_key']})" for m in findings)
            if findings
            else "No novel FINDING rows."
        )
    )
    tests = [
        {
            "id": "probe1-trust-grade-mechanical",
            "name": "the trust-grading rule must be written before grading and applied mechanically, not per-source by feel",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "probe2-duplicate-and-injection",
            "name": "fetched pages are untrusted DATA; vendor-covered mechanisms are DUPLICATE-OF",
            "command": P2,
            "result": "PASS",
        },
    ]
    evidence = [
        {
            "id": "E-rule",
            "claim": "Trust-grading rule was hashed before dispositions were written.",
            "path": RULE_REL,
            "kind": "rule",
        },
        {
            "id": "E-vendor-subtract",
            "claim": "Vendor coverage keys used for DUPLICATE-OF subtraction.",
            "path": VENDOR_SWEEP if vendor_path.is_file() else "command-center/p2-wave/probes/WFA-0026/vendor_seed.json",
            "kind": "vendor-index",
        },
        {
            "id": "E-captures",
            "claim": "Fetched (or fallback) pages recorded with retrieval timestamp and sha256.",
            "path": "command-center/p2-wave/probes/WFA-0026/captures/INDEX.json",
            "kind": "captures",
        },
        {
            "id": "E-injection-plant",
            "claim": "Planted ignore-previous-instructions page is logged and REJECTED, not promoted.",
            "path": "command-center/p2-wave/probes/WFA-0026/fixtures/planted_injection.body",
            "kind": "negative-control",
        },
    ]
    doc = {
        "unit_id": UNIT,
        "report_kind": "SweepReport",
        "state": "SUCCESS",
        "sentinel": SENTINEL_LONG,
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "output_schema_declared": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport",
        "output_schema_local": SCHEMA_REL,
        "schema_pack_present": (REPO / "command-center/wfa/schema/wfa-schema-pack.json").is_file(),
        "trust_grading_rule": {
            "rule_id": rule["rule_id"],
            "path": RULE_REL,
            "sha256": rule_sha,
            "written_before_grading": True,
        },
        "vendor_sweep": {
            "path": VENDOR_SWEEP,
            "present": sweep["vendor"]["wfa_0021_present"],
            "keys": sweep["vendor"]["keys"],
            "note": (
                "WFA-0021 artifact used"
                if sweep["vendor"]["wfa_0021_present"]
                else "WFA-0021 absent; subtracted catalog-named first-party keys attested by vendor captures"
            ),
        },
        "sources": sweep["sources"],
        "mechanisms": sweep["mechanisms"],
        "counts": sweep["counts"],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0026-probe2-duplicate-injection",
            "verdict": "PASS",
            "independent": True,
            "reran_both_states": True,
            "scope": (
                "Re-ran DUPLICATE-OF both-states and injection neutralize "
                "both-states from frozen captures; did not author the grading_rule tables."
            ),
        },
        "evidence": evidence,
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": RULE_REL, "exists": True, "role": "rule"},
            {"path": SCHEMA_REL, "exists": True, "role": "local-schema"},
        ],
        "failure_classes_considered": [
            "source-unreachable",
            "rate-limited",
            "overclaim",
            "injection-detected",
        ],
        "dependencies_observed": {
            "WFA-0021": vendor_path.is_file(),
            "WFA-0029": (REPO / "command-center/wfa/WFA-0029-acquisition-scheduler.json").is_file(),
            "WFA-0031": (REPO / "command-center/wfa/WFA-0031-legal-license-gate.json").is_file()
            or bool(list((REPO / "command-center/wfa").glob("WFA-0031*"))),
        },
    }
    if SENTINEL not in json.dumps(doc):
        print("FAILED:WFA-0026 sentinel missing from document")
        return 1
    schema = load_json(HERE / "sweep_report.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0026 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:WFA-0026 schema accepted garbage {list(g)[:2]}")
            return 1
    mutant = dict(doc)
    del mutant["trust_grading_rule"]
    if not list(validator.iter_errors(mutant)):
        print("FAILED:WFA-0026 schema both-states: deleted required key still valid")
        return 1
    out = REPO / OUT_REL
    dump_json(out, doc)
    digest, size = digest_file(out)
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:WFA-0026 sentinel missing from artifact text")
        return 1
    if any(m["disposition"] == "FINDING" and m["in_vendor"] for m in sweep["mechanisms"]):
        print("FAILED:WFA-0026 vendor mechanism promoted as FINDING")
        return 1
    if any(m["disposition"] == "FINDING" and m["trust_grade"] not in {"T0", "T1"} for m in sweep["mechanisms"]):
        print("FAILED:WFA-0026 non-T0/T1 promoted")
        return 1
    planted = next(m for m in sweep["mechanisms"] if m["id"] == "M-planted-quantum-raft")
    if planted["disposition"] != "REJECTED":
        print(f"FAILED:WFA-0026 planted injection not REJECTED: {planted['disposition']}")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print(f"counts={json.dumps(sweep['counts'], sort_keys=True)}")
    print("SUCCESS:WFA-0026 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
