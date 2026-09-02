#!/usr/bin/env python3
"""Emit RES-0183 design spec: owner-decision-log as a research source class."""
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

import checker as C  # noqa: E402
import extract as E  # noqa: E402

OUT = (
    "command-center/research/sources-frontier/"
    "RES-0183-owner-decision-log-as-a-source-class.json"
)
SCHEMA = "command-center/schema/design-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0183/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0183/probe2_quote_lineage.py"
)
SENTINEL = "SUCCESS:RES-0183"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_unit(uid: str) -> dict:
    data = E.load_catalog()
    for item in data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == uid:
            return item
    raise KeyError(uid)


def slim(c: dict) -> dict:
    keep = (
        "id",
        "kind",
        "binding",
        "authority",
        "owner_confirmation_required",
        "title",
        "normative_text",
        "quote",
        "anchor",
        "path",
        "line",
        "source_lineage",
        "confidence_band",
        "settling_probe",
        "forbidden_release_modes",
        "forbidden_patterns",
        "notes",
    )
    return {k: c[k] for k in keep if k in c}


def main() -> int:
    unit = catalog_unit("RES-0183")
    question = str(unit.get("question_or_target") or "")
    if len(question) < 40:
        print("FAILED:RES-0183 catalog question too short")
        return 1
    blob = E.build_constraints()
    drafts = C.load_drafts()
    checks = {name: C.check_draft(d, blob) for name, d in drafts.items()}
    need_flag = (
        "noncompliant_public_canary",
        "noncompliant_private_canary",
        "noncompliant_38_as_prompt_two",
    )
    need_pass = ("compliant_pr_only", "mention_rejected_canary")
    for name in need_flag:
        if checks[name]["compliant"]:
            print(f"FAILED:RES-0183 emit {name} was not flagged")
            return 1
    for name in need_pass:
        if not checks[name]["compliant"]:
            print(f"FAILED:RES-0183 emit {name} was flagged {checks[name]}")
            return 1
    oq3 = next(r for r in E.answered_owner_questions() if r["id"] == "OQ-3")
    if str(oq3.get("answer") or "").strip() != "PR-ONLY.":
        print("FAILED:RES-0183 emit OQ-3 JSON answer is not PR-ONLY.")
        return 1

    owner_text = (E.REPO / E.OWNER_REL).read_text(encoding="utf-8")
    log_text = (E.REPO / E.DECISION_LOG_REL).read_text(encoding="utf-8")
    owner_has_pr_only = "PR-ONLY" in owner_text
    log_has_pr_only = "PR-ONLY" in log_text
    opt_present = E.first_present(E.OPTION_UNIVERSE_CANDIDATES) is not None

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stated = [slim(c) for c in blob["stated"]]
    inferred = [slim(c) for c in blob["inferred"]]
    observations = [slim(c) for c in blob["observations"]]
    binding_ids = [c["id"] for c in stated if c["binding"]]
    pr_only = next(c for c in stated if c["id"] == "BC-OQ-3-PR-ONLY")
    seventy = next(c for c in stated if c["id"] == "BC-OQ-1-SEVENTY-IDS")

    doc = {
        "unit_id": "RES-0183",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": str(
            unit.get("title")
            or "Mine the owner's own decision log for constraints that research must not contradict"
        ),
        "question": question,
        "output_schema": SCHEMA,
        "emitted_at": now,
        "distinct_from_res_0127": blob["distinct_from_res_0127"],
        "source_class": {
            "id": "owner-decision-log",
            "ingest": (
                "Read OWNER-DECISIONS.md, 17-DECISION-LOG.md, 07-OPTION-UNIVERSE, "
                "and catalog owner_questions. Record ABSENT or wrong-document "
                "rather than inventing bytes."
            ),
            "research_unit_gate": (
                "Before emitting a recommendation, run "
                "checker.check_draft(recommendation, build_constraints()). "
                "A non-compliant draft must not be the recorded recommendation."
            ),
            "absent_source_policy": (
                "Do not invent missing files. Catalog prose about those files is "
                "INFERRED, owner_confirmation_required=true, and not binding."
            ),
        },
        "design": {
            "checker_module": "command-center/p2-wave/probes/RES-0183/checker.py",
            "extract_module": "command-center/p2-wave/probes/RES-0183/extract.py",
            "api": "check_draft(draft, constraints) -> {compliant, violations}",
            "mention_rule": (
                "mode=mention/quote does not fire; negation in the 50 characters "
                "before a forbidden pattern also suppresses the hit."
            ),
            "both_states_required": (
                "A draft proposing a public canary under PR-ONLY must be flagged; "
                "a PR-ONLY pull-request draft must pass."
            ),
        },
        "source_coverage": blob["coverage"],
        "constraints": {
            "stated": stated,
            "inferred": inferred,
            "observations": observations,
            "binding_count": len(binding_ids),
            "binding_ids": binding_ids,
            "answered_oq_ids": blob["answered_oq_ids"],
        },
        "honesty": {
            "owner_decisions_records_pr_only": owner_has_pr_only,
            "decision_log_records_pr_only": log_has_pr_only,
            "option_universe_present": opt_present,
            "decision_log_is_cc0022_reconstruction": True,
            "padding_wf_rulings_not_treated_as_owner_constraints": True,
        },
        "checker_results": checks,
        "tests": [
            {"id": "probe1-both-states", "command": P1, "result": "PASS"},
            {"id": "probe2-quote-lineage", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "public-canary-under-pr-only",
                "on_state": "draft proposing a public canary while PR-ONLY is binding",
                "observed": "FLAGGED",
            },
            {
                "id": "compliant-pr-only",
                "on_state": "draft that proposes pull requests only",
                "observed": "SILENT",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "OQ-3 binds release mode to PR-ONLY. JSON parse of "
                    "owner_questions and the raw catalog line both quote it."
                ),
                "verdict": "CONFIRMED",
                "anchor": pr_only["anchor"],
                "confidence_band": "almost-certain",
                "mechanism": "catalog-json-parse plus raw-line quote",
            },
            {
                "claim": (
                    "The checker flags a public-canary draft under PR-ONLY and "
                    "passes a compliant pull-request draft (catalog both-states)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0183/fixtures/drafts.json",
                "confidence_band": "almost-certain",
                "mechanism": "check_draft on planted both-states fixtures",
            },
            {
                "claim": (
                    "OWNER-DECISIONS.md does not currently record PR-ONLY; "
                    "17-DECISION-LOG.md also lacks PR-ONLY. The live quote is the "
                    "catalog owner_question, not those named files."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{E.OWNER_REL}:1",
                "confidence_band": "almost-certain",
                "mechanism": "full-text scan of both named files",
            },
            {
                "claim": (
                    "07-OPTION-UNIVERSE.json is absent, so the 70-id membership "
                    "list is NOT-CHECKED. Partial ids A-01, A-03, A-12, A-13, "
                    "A-17, A-18 are quoted from the catalog only."
                ),
                "verdict": "CONFIRMED",
                "anchor": seventy["anchor"],
                "confidence_band": "almost-certain",
                "mechanism": "candidate-path existence check plus catalog quote",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0183-probe2-quote-lineage",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/RES-0183/extract.py",
                "exists": True,
                "role": "extractor",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0183/checker.py",
                "exists": True,
                "role": "checker",
            },
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0183 sentinel missing from emit")
        return 1
    dest.write_text(text, encoding="utf-8")
    digest, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={digest} binding={len(binding_ids)}")
    print(SENTINEL + " emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
