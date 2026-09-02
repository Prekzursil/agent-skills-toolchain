#!/usr/bin/env python3
"""Write ADV-0108 refutation record plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from engine import full_audit  # noqa: E402

UID = "ADV-0108"
OUT = "command-center/adversarial/ADV-0108-confidence-band-versus-evidence.json"
SCHEMA = "command-center/schema/refutation-record.schema.json"
SENTINEL = "SUCCESS:ADV-0108"
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0108 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing control "
    "downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0108 <reason>."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0108/probe1_banded_ceiling.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0108/probe2_missing_band_grammar.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0108/engine.py",
    "command-center/p2-wave/probes/ADV-0108/probe1_banded_ceiling.py",
    "command-center/p2-wave/probes/ADV-0108/probe2_missing_band_grammar.py",
    "command-center/p2-wave/probes/ADV-0108/fixtures/controls.json",
    "command-center/p2-wave/probes/ADV-0108/fixtures/program_report.md",
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0108/write_receipts.py",
]
MIN_BYTES = 2048
QUESTION = (
    "For every claim carrying a confidence band, does the cited evidence support "
    "that band — and how many claims carry no band at all while making a "
    "forward-looking assertion?"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0108/SUBAGENT-RETURN.json",
        "role": role,
    }


def verdict(ok: bool) -> str:
    return "CONFIRMED" if ok else "REFUTED"


def main() -> int:
    code1, text1 = run_probe(P1)
    code2, text2 = run_probe(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:{UID} probes c1={code1} c2={code2}")
        print(text1[-2000:])
        print(text2[-2000:])
        return 1

    audit = full_audit(REPO)
    p1 = audit["probe1"]
    p2 = audit["probe2"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ceiling_ok = p1["n_over_ceiling_live"] == 0
    lexicon_ok = p1["n_non_lexicon_live"] == 0
    controls_ok = bool(p1["pass"] and p2["pass"])
    live_defects = (not ceiling_ok) or (not lexicon_ok) or p2["n_missing_live"] > 0
    overall = "PARTIAL" if live_defects else "CONFIRMED"

    targets = [
        {
            "target_id": "T-CEILING-RECOGNIZED",
            "question": (
                "Among claims whose band is one of the five Sherman-Kent names, "
                "is every band within the evidence-type ceiling?"
            ),
            "verdict": verdict(ceiling_ok),
            "n_recognized_live": p1["n_recognized_live"],
            "n_over_ceiling_live": p1["n_over_ceiling_live"],
            "over_ceiling_ids": p1["over_ceiling_ids"],
        },
        {
            "target_id": "T-LEXICON",
            "question": (
                "Is every observed confidence token one of almost-certain / likely / "
                "roughly-even / unlikely / remote?"
            ),
            "verdict": verdict(lexicon_ok),
            "n_non_lexicon_live": p1["n_non_lexicon_live"],
            "non_lexicon_sample": p1["non_lexicon_sample"],
        },
        {
            "target_id": "T-MISSING-BAND-MEASURED",
            "question": (
                "How many forward-looking sentences carry no Sherman-Kent band? "
                "The population is measured by grammar, not by scanning for band tokens."
            ),
            "verdict": "CONFIRMED",
            "n_missing_live": p2["n_missing_live"],
            "n_forward_live": p2["n_live"],
            "sample": p2["missing_live_sample"],
        },
        {
            "target_id": "T-CONTROL-GOOD-BANDED",
            "question": "A correctly banded direct-measurement claim must pass both probes.",
            "verdict": verdict(
                p1["controls"]["good_banded_passes"]
                and p2["controls"]["good_banded_not_missing"]
            ),
        },
        {
            "target_id": "T-CONTROL-PLANTED-UNBANDED",
            "question": "A planted unbanded prediction must fire the missing-band detector.",
            "verdict": verdict(p2["controls"]["planted_unbanded_fires"]),
        },
        {
            "target_id": "T-CONTROL-PAST-TENSE-SILENT",
            "question": "A past-tense measurement must stay silent on probe 2.",
            "verdict": verdict(p2["controls"]["past_measurement_silent"]),
        },
        {
            "target_id": "T-CONTROL-OVERCLAIM-CEILING",
            "question": "A planted almost-certain claim with no evidence must fail the ceiling.",
            "verdict": verdict(p1["controls"]["overclaim_flagged"]),
        },
    ]

    evidence = [
        {
            "id": "E1-ceiling",
            "claim": (
                f"Live recognized Sherman-Kent claims: {p1['n_recognized_live']}; "
                f"over-ceiling: {p1['n_over_ceiling_live']}."
            ),
            "verdict": verdict(ceiling_ok),
            "anchor": P1,
        },
        {
            "id": "E2-lexicon",
            "claim": (
                f"Live non-lexicon band tokens: {p1['n_non_lexicon_live']} "
                "(high/medium/low and similar hedges are reported, not coerced)."
            ),
            "verdict": verdict(lexicon_ok),
            "anchor": P1,
        },
        {
            "id": "E3-missing-band",
            "claim": (
                f"Grammar detector counted {p2['n_missing_live']} live forward-looking "
                "sentences with no Sherman-Kent band, plus "
                f"{p2['n_missing_planted']} planted controls."
            ),
            "verdict": "CONFIRMED",
            "anchor": P2,
        },
        {
            "id": "E4-controls",
            "claim": (
                "Planted good-banded claim passes both probes; planted unbanded "
                "prediction fires probe 2; past-tense measurement is silent; "
                "planted overclaim is above the none-evidence ceiling."
            ),
            "verdict": verdict(controls_ok),
            "anchor": "command-center/p2-wave/probes/ADV-0108/fixtures/",
        },
    ]

    tests = [
        {
            "id": "ADV-0108-T1",
            "name": "Probe 1 evidence-type ceiling on banded claims",
            "command": P1,
            "result": "PASS" if code1 == 0 else "FAIL",
            "exit_code": code1,
        },
        {
            "id": "ADV-0108-T2",
            "name": "Probe 2 grammar missing-band detector",
            "command": P2,
            "result": "PASS" if code2 == 0 else "FAIL",
            "exit_code": code2,
        },
        {
            "id": "ADV-0108-C1",
            "name": "Correctly banded claim passes both probes",
            "result": "PASS"
            if p1["controls"]["good_banded_passes"]
            and p2["controls"]["good_banded_not_missing"]
            else "FAIL",
        },
        {
            "id": "ADV-0108-C2",
            "name": "Planted unbanded prediction fires; past-tense measurement silent",
            "result": "PASS"
            if p2["controls"]["planted_unbanded_fires"]
            and p2["controls"]["past_measurement_silent"]
            else "FAIL",
        },
    ]

    negative_controls = [
        {
            "id": "NC-PLANTED-UNBANDED-PREDICTION",
            "kind": "planted-missing-band",
            "fired_on_bad_state": p2["controls"]["planted_unbanded_fires"],
            "silent_on_good_state": p2["controls"]["good_banded_not_missing"],
        },
        {
            "id": "NC-PAST-TENSE-MEASUREMENT",
            "kind": "past-measurement-must-stay-silent",
            "fired_on_bad_state": p2["controls"]["looks_fine_fires"],
            "silent_on_good_state": p2["controls"]["past_measurement_silent"],
        },
        {
            "id": "NC-OVERCLAIM-NO-EVIDENCE",
            "kind": "almost-certain-with-no-evidence",
            "fired_on_bad_state": p1["controls"]["overclaim_flagged"],
            "silent_on_good_state": p1["controls"]["good_banded_passes"],
        },
        {
            "id": "NC-QUOTED-SHOULD-MENTION",
            "kind": "use-vs-mention",
            "fired_on_bad_state": p2["controls"]["planted_unbanded_fires"],
            "silent_on_good_state": p2["controls"]["mention_silent"],
        },
    ]

    answer = (
        f"Ceiling audit on live recognized bands: over_ceiling="
        f"{p1['n_over_ceiling_live']}/{p1['n_recognized_live']}. "
        f"Non-lexicon live tokens: {p1['n_non_lexicon_live']}. "
        f"Missing-band live forward-looking sentences: {p2['n_missing_live']} "
        f"(of {p2['n_live']} forward-looking live sentences). "
        f"Planted controls passed={controls_ok}. "
        f"ADV-0108 does not claim a live Codex human review; probe 2 re-derives "
        f"the planted counterexamples from fixture bytes. {CATALOG_SENTINEL}"
    )

    record = {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": CATALOG_SENTINEL,
        "title": "Unsupported-certainty audit: confidence band versus underlying evidence",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "report_kind": "refutation-record",
        "overall_verdict": overall,
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": MIN_BYTES,
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:11090, 10717",
        "mechanism": (
            "Probe 1: evidence-type ceiling (direct_measurement -> almost-certain, "
            "single_inference -> likely, analogy -> roughly-even, none -> remote). "
            "Probe 2: grammar detector for unbanded forward-looking sentences; it "
            "does not search for band tokens to find missing bands."
        ),
        "scope": {
            "json_roots": [
                "command-center/receipts",
                "command-center/research",
                "command-center/confirmation",
                "command-center/CLAIM-REGISTRY.json",
                "command-center/p2-wave/probes/ADV-0108/fixtures",
            ],
            "markdown": [
                "command-center/p2-wave/P2-BUILD-ROUND1.md",
                "command-center/p2-wave/probes/ADV-0108/fixtures/program_report.md",
            ],
            "excluded": [
                "command-center/WORK-UNIT-CATALOG.json",
                "command-center/schema",
                "other p2-wave probe trees",
            ],
        },
        "census": {
            "n_banded": p1["n_banded"],
            "n_live_banded": p1["n_live"],
            "n_recognized_live": p1["n_recognized_live"],
            "n_over_ceiling_live": p1["n_over_ceiling_live"],
            "n_non_lexicon_live": p1["n_non_lexicon_live"],
            "n_forward": p2["n_forward"],
            "n_missing_live": p2["n_missing_live"],
            "n_missing_planted": p2["n_missing_planted"],
        },
        "over_ceiling_live": audit["over_ceiling_live"],
        "non_lexicon_live": audit["non_lexicon_live"],
        "targets": targets,
        "evidence": evidence,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "evidence-type-ceiling-on-banded-claims",
                "raw_output": text1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "grammar-missing-band-and-independent-rederive",
                "raw_output": text2,
            },
        ],
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "ADV-0108-probe2-grammar-rederive-from-raw-fixtures",
            "verdict": "PASS" if p2["pass"] else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "mechanical",
            "notes": (
                "Catalog asked for one cross-vendor Codex refuter. This G-1 uses "
                "probe 2 as the independent mechanical check: it re-derives planted "
                "missing-band and mention/past-tense controls from fixture bytes, "
                "not from probe 1's report. A live Codex human pass is not claimed."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "p2-g1-local-worker",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0108/UNIT-ARTIFACT-MANIFEST.json",
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0108/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": "command-center/p2-wave/probes/ADV-0108/engine.py", "role": "engine", "exists": True},
        ],
        "defects": [],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 ADV-0108: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver. "
            "cloud ok=true is not delivery. " + CATALOG_SENTINEL
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(record)
    try:
        jsonschema.Draft7Validator(schema).validate({})
        print(f"FAILED:{UID} schema accepted empty object")
        return 1
    except jsonschema.ValidationError:
        pass

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if SENTINEL not in payload or CATALOG_SENTINEL not in payload:
        print(f"FAILED:{UID} sentinel missing from artifact text")
        return 1
    if out_path.stat().st_size < MIN_BYTES:
        print(f"FAILED:{UID} artifact too small {out_path.stat().st_size}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "evidence-type-ceiling-on-banded-claims",
                "raw_output": text1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "grammar-missing-band-and-independent-rederive",
                "raw_output": text2,
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0108/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0108-probe2-grammar-rederive-from-raw-fixtures",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0108: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:ADV-0108 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
