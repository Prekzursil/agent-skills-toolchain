#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0206.json from a live dual-scanner run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from canary import PREFIX  # noqa: E402

UNIT = "TST-0206"
OUT = "command-center/receipts/TST-0206.json"
SCHEMA = "command-center/p2-wave/probes/TST-0206/receipt.schema.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json#/$defs/security_report"
QUESTION = (
    "With canary tokens planted in the environment and in local config, does a "
    "scan of every produced artifact directory find zero occurrences? PASS "
    "requires the scan first PROVE it can find a planted canary inside an "
    "artifact before any zero is trusted."
)
SENTINEL = "SUCCESS:TST-0206"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0206/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0206/probe2_produced_zero.py"
)


def _surface_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "method": row["method"],
        "known_present_found": bool(row.get("known_present_found")),
        "files_scanned": row.get("files_scanned"),
        "pattern_canary_hits": row.get("pattern_canary_hits"),
        "entropy_canary_hits": row.get("entropy_canary_hits"),
        "absent": row.get("absent", False),
    }


def build_doc(run: S.ScenarioResult) -> dict:
    pub = run.public
    agr = pub["agreement"]
    live = pub["live_produced"]
    ctl = pub["detector_control"]
    plant = pub["planting"]
    ok = bool(pub.get("pass"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"Yes on this worktree after a proven detector control. Canary prefix "
        f"{PREFIX} (sha256 {pub['canary_sha256'][:12]}…, body never stored) was "
        f"planted in env keys {plant['env_keys']} and local config files "
        f"{plant['config_files']}. Pattern and entropy scanners both found it "
        f"inside a planted artifact (pattern_canary_hits="
        f"{ctl['pattern_canary_hits']}, entropy_canary_hits="
        f"{ctl['entropy_canary_hits']}) and both found it in a leaky producer "
        f"that dumped those env keys. A sandbox produced-clean tree had zero "
        f"canary hits on both scanners. Live produced directories "
        f"{live['dirs']} were walked ({live['files_scanned']} files, "
        f"{live['bytes_scanned']} bytes); enumerator liveness via "
        f"{live['liveness_path']}={live['enumerator_liveness']}; live canary "
        f"hits pattern={live['pattern_canary_hits']} entropy="
        f"{live['entropy_canary_hits']}. Optional dirs not treated as clean: "
        f"{live['optional_absent_not_scanned_as_clean']}. Regression zip with "
        f"a JSON password/decrypted_secret plus a synthetic PEM fired both "
        f"scanners (pattern_rule_ids="
        f"{pub['regression_bundle'].get('pattern_rule_ids')}). "
        f"tools/lib/security.mjs absent="
        f"{pub['inputs_absent']['tools/lib/security.mjs']}; scanners live in "
        f"this probe directory. {SENTINEL}"
    )
    result = "PASS" if ok else "FAIL"
    state = "SUCCESS" if ok else "FAILED"
    surfaces = [
        _surface_row(ctl),
        _surface_row(pub["produced_clean"]),
        _surface_row(pub["produced_leaky"]),
        _surface_row(pub["regression_bundle"]),
    ]
    for row in live.get("surfaces") or []:
        if "id" in row and "method" in row:
            surfaces.append(
                {
                    "id": row["id"],
                    "method": row["method"],
                    "known_present_found": bool(row.get("known_present_found")),
                    "files_scanned": row.get("files_scanned"),
                    "pattern_canary_hits": row.get("pattern_canary_hits"),
                    "entropy_canary_hits": row.get("entropy_canary_hits"),
                    "absent": row.get("absent", False),
                }
            )
    return {
        "unit_id": UNIT,
        "state": state,
        "sentinel": SENTINEL,
        "report_kind": "security_report",
        "title": "Canary-seeded scan proves no secret enters any produced artifact",
        "question": QUESTION,
        "answer": answer,
        "profile": "canary-seeded-dual-scanner",
        "canary": {
            "prefix": PREFIX,
            "sha256": pub["canary_sha256"],
            "len": pub["canary_len"],
            "body_stored": False,
        },
        "planting": plant,
        "detector_control": {
            "id": ctl["id"],
            "pattern_canary_hits": ctl["pattern_canary_hits"],
            "entropy_canary_hits": ctl["entropy_canary_hits"],
            "agree": ctl.get("agree"),
            "files_scanned": ctl["files_scanned"],
        },
        "produced_clean": {
            "pattern_canary_hits": pub["produced_clean"]["pattern_canary_hits"],
            "entropy_canary_hits": pub["produced_clean"]["entropy_canary_hits"],
            "agree_zero": pub["produced_clean"].get("agree_zero"),
        },
        "produced_leaky": {
            "pattern_canary_hits": pub["produced_leaky"]["pattern_canary_hits"],
            "entropy_canary_hits": pub["produced_leaky"]["entropy_canary_hits"],
            "agree_present": pub["produced_leaky"].get("agree_present"),
        },
        "regression_bundle": {
            "pattern_credential_fired": pub["regression_bundle"].get(
                "pattern_credential_fired"
            ),
            "entropy_fired": pub["regression_bundle"].get("entropy_fired"),
            "pattern_rule_ids": pub["regression_bundle"].get("pattern_rule_ids"),
            "agree_dirty": pub["regression_bundle"].get("agree_dirty"),
        },
        "live_produced": live,
        "agreement": agr,
        "inputs_absent": pub["inputs_absent"],
        "tests": [
            {
                "id": "TST0206-T1-DETECTOR-CONTROL",
                "command": P1,
                "result": result if agr["detector_control"] else "FAIL",
            },
            {
                "id": "TST0206-T2-PRODUCED-ZERO-AFTER-PLANT",
                "command": P2,
                "result": result
                if agr["produced_clean_zero"] and agr["live_produced_zero"]
                else "FAIL",
            },
            {
                "id": "TST0206-T3-REGRESSION-BUNDLE",
                "command": P2,
                "result": result if agr["regression_dirty"] else "FAIL",
            },
            {
                "id": "TST0206-T4-SCANNERS-AGREE",
                "command": P1 + " && " + P2,
                "result": result if agr["both_scanners_agree"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0206-probe2-entropy-scanner-independent-of-pattern",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-runs the scenario and trusts a produced-dir zero "
                "only after the entropy scanner independently fires on the "
                "planted control, the leaky producer, and the credential bundle."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/TST-0206/pattern_scan.py",
                "exists": True,
                "role": "pattern-scanner",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0206/entropy_scan.py",
                "exists": True,
                "role": "entropy-scanner",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0206/probe1_detector_control.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0206/probe2_produced_zero.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "evidence": [
            {
                "id": "pattern-scanner",
                "claim": (
                    "A pattern scanner over the artifact tree found the planted "
                    "canary in the detector-control artifact and in the leaky "
                    "producer, found zero canary occurrences in sandbox-clean "
                    "and live produced directories, and fired credential rules "
                    "on the regression bundle."
                ),
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "anchor": "command-center/p2-wave/probes/TST-0206/pattern_scan.py",
            },
            {
                "id": "entropy-scanner",
                "claim": (
                    "An entropy scanner, run independently with no canary prefix "
                    "table, agreed on every tree: suffix-bearing high-entropy "
                    "tokens on detector-control and leaky producer, zero suffix "
                    "matches on produced-clean and live produced dirs, and "
                    "high-entropy tokens in the regression bundle."
                ),
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "anchor": "command-center/p2-wave/probes/TST-0206/entropy_scan.py",
            },
        ],
        "surfaces": surfaces,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "detector-control"},
            {"id": "probe2", "command": P2, "role": "produced-zero-and-regression"},
        ],
        "cloud_ok": False,
        "ended_at": now,
        "schema_version": 1,
        "output_schema": CATALOG_SCHEMA,
        "output_schema_local": SCHEMA,
    }


def validate(doc: dict) -> None:
    # Local schema: catalog security-report.schema.json is a $ref shim to
    # ast-integrate.invalid (no DNS). Draft7 must not fetch that host.
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0206 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"state": "SUCCESS"},
        {"unit_id": UNIT, "state": "SUCCESS", "sentinel": SENTINEL},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:TST-0206 schema accepted garbage {list(garbage)[:2]}")
            raise SystemExit(1)


def main() -> int:
    run = S.run_scenario()
    if not run.public.get("pass"):
        print("FAILED:TST-0206 scenario did not pass")
        print(json.dumps(run.public.get("agreement"), indent=2, sort_keys=True)[:4000])
        print(json.dumps(run.public.get("planting"), indent=2, sort_keys=True)[:2000])
        print(
            json.dumps(run.public.get("detector_control"), indent=2, sort_keys=True)[
                :2000
            ]
        )
        return 1
    doc = build_doc(run)
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print("FAILED:TST-0206 a required test is not PASS")
        return 1
    validate(doc)
    raw = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if run.contains_canary(raw):
        print("FAILED:TST-0206 emit leaked canary body into receipt")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(raw, encoding="utf-8")
    if run.contains_canary(out.read_bytes()):
        print("FAILED:TST-0206 written receipt contains canary body")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0206 sentinel absent after write")
        return 1
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:TST-0206 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
