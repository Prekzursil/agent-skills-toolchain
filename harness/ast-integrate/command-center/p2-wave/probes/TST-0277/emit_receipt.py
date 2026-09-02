#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0277.json from live confirmation runs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import (  # noqa: E402
    cosmetic_verdict,
    covered_verdict,
    hole_verdict,
    synonym_verdict,
)
from fixtures import UNIQUE_CLAIM_ID, UNIQUE_CLAIM_TEXT  # noqa: E402
from simulate import covered_run, hole_run, synonym_run  # noqa: E402

OUT = "command-center/receipts/TST-0277.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0277/probe1_competency_hole.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0277/probe2_false_gap.py"
)
QUESTION = (
    "Question: can the runtime notice that nobody on the panel knows the thing "
    "the decision turns on? Spec :10944 lists missing expertise, and :10924 "
    "allows dynamic recruitment. Build the coverage check that maps the "
    "decision's required competencies against declared seat competencies, fires "
    "on an uncovered competency, and recruits, then prove the recruited seat "
    "actually changes the deliberation rather than rubber-stamping it."
)
COMPLETION_SENTINEL = "SUCCESS:TST-0277"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0277 emit snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def main() -> int:
    live_hole = hole_run(recruited_mode="substantive")
    live_covered = covered_run()
    live_rubber = hole_run(recruited_mode="rubberstamp")
    live_syn = synonym_run()

    hv = hole_verdict(live_hole)
    cv = covered_verdict(live_covered)
    rv = cosmetic_verdict(live_rubber)
    sv = synonym_verdict(live_syn)
    if not live_hole.get("completed") or not live_covered.get("completed"):
        print("FAILED:TST-0277 a designed run did not complete")
        return 1
    if not hv["pass"]:
        print("FAILED:TST-0277 hole run")
        print(json.dumps(hv, indent=2)[:2000])
        return 1
    if not cv["pass"]:
        print("FAILED:TST-0277 covered run triggered")
        print(json.dumps(cv, indent=2)[:2000])
        return 1
    if not rv["pass"]:
        print("FAILED:TST-0277 rubberstamp control silent")
        print(json.dumps(rv, indent=2)[:2000])
        return 1
    if not sv["pass"]:
        print("FAILED:TST-0277 synonym panel treated as covered")
        print(json.dumps(sv, indent=2)[:2000])
        return 1
    if live_hole["transcript"] == live_covered["transcript"]:
        print("FAILED:TST-0277 transcripts did not differ")
        return 1
    exclusive = (live_hole.get("exclusive_by_recruit") or {}).get(UNIQUE_CLAIM_ID)
    if not exclusive:
        print("FAILED:TST-0277 exclusive claim missing from hole run")
        return 1

    catalog = REPO / CATALOG
    cat_line = find_line(catalog, '"id": "TST-0277"')
    q_line = find_line(catalog, "nobody on the panel knows the thing the decision turns on")
    ev_line = find_line(
        catalog,
        "Name the uncovered competency, the recruitment trigger, and at least one claim",
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hole_sha = sha_text(live_hole["transcript"])
    covered_sha = sha_text(live_covered["transcript"])

    schema_path = "command-center/schema/receipt.schema.json"
    schema_exists = (REPO / schema_path).is_file()
    simulate_prod = (REPO / "tools/council/simulate.py").is_file()

    doc = {
        "unit_id": "TST-0277",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "title": (
            "Detect missing expertise on the panel and recruit an independent "
            "critic to fill it"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "A coverage check that diffs required competencies against declared "
            "seat competencies names an uncovered competency, fires the "
            "missing-expertise trigger, recruits an independent critic, and "
            "the recruited seat contributes a claim that is absent from the "
            "pre-recruitment transcript; a fully covered panel does not recruit."
        ),
        "spec_anchor": (
            "catalog TST-0277; _USER-PROMPTS.md:10944 missing expertise; "
            ":10924 dynamic recruitment. Spec files are not on this worktree; "
            "the catalog question_or_target and tests_required are the live contract."
        ),
        "substrate": {
            "production_council_runtime": (
                "present"
                if simulate_prod
                else "absent (tools/council/simulate.py is not on this worktree)"
            ),
            "production_b05_taxonomy": "absent on this worktree",
            "confirmation_runtime": (
                "command-center/p2-wave/probes/TST-0277/simulate.py"
            ),
            "confirmation_taxonomy": (
                "command-center/p2-wave/probes/TST-0277/fixtures.py TAXONOMY"
            ),
            "honesty": (
                "This unit confirms missing-expertise detection and recruitment "
                "efficacy of the confirmation-local simulator. It does not claim "
                "a missing production tools/council package or a missing B05 "
                "taxonomy dump was exercised. A later wave that lands those "
                "must re-run these probes against them. Coverage is exact-id; "
                "a declared synonym does not cover a required taxonomy id."
            ),
            "declared_output_schema": schema_path,
            "declared_output_schema_present": schema_exists,
        },
        "named_evidence": {
            "uncovered_competency": "cryptography",
            "named_gap": list(live_hole["coverage"]["named_gap"]),
            "recruitment_trigger": "missing-expertise",
            "exclusive_claim_id": UNIQUE_CLAIM_ID,
            "exclusive_claim_author": exclusive["author"],
            "exclusive_claim_text": UNIQUE_CLAIM_TEXT,
            "exists_only_because_of_new_seat": True,
        },
        "runs": [
            {
                "id": "competency-hole",
                "completed": True,
                "panel": "HOLE_PANEL",
                "uncovered_competency": "cryptography",
                "named_gap": list(live_hole["coverage"]["named_gap"]),
                "recruitment_trigger": "missing-expertise",
                "recruitment_triggered": True,
                "recruited_seat_ids": list(live_hole["recruitment"]["seated_ids"]),
                "exclusive_claim_id": UNIQUE_CLAIM_ID,
                "exclusive_claim_author": exclusive["author"],
                "recommendation": live_hole["recommendation"],
                "transcript": live_hole["transcript"],
                "transcript_sha256": hole_sha,
            },
            {
                "id": "fully-covered",
                "completed": True,
                "panel": "COVERED_PANEL",
                "uncovered_competency": None,
                "named_gap": [],
                "recruitment_trigger": None,
                "recruitment_triggered": False,
                "recruited_seat_ids": [],
                "exclusive_claim_id": None,
                "recommendation": live_covered["recommendation"],
                "transcript": live_covered["transcript"],
                "transcript_sha256": covered_sha,
            },
        ],
        "comparison": {
            "recruitment_differs": True,
            "transcripts_differ": True,
            "method": "utf-8 sha256 of transcript plus recruitment.triggered inequality",
            "hole_transcript_sha256": hole_sha,
            "covered_transcript_sha256": covered_sha,
        },
        "tests": [
            {
                "id": "TST-0277-HOLE",
                "command": P1,
                "name": (
                    "Panel with a deliberate competency hole -> gap detected "
                    "and named; recruited seat contributes a new claim"
                ),
                "result": "PASS",
            },
            {
                "id": "TST-0277-COVERED",
                "command": P2,
                "name": "False-gap control: a fully covered panel must not trigger recruitment",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0277-RUBBERSTAMP",
                "planted_defect": (
                    "recruited seat emits concurrence with no new claim"
                ),
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "cosmetic-recruitment",
            },
            {
                "id": "TST-0277-SYNONYM",
                "planted_defect": (
                    "seats declare crypto/threats/legal aliases instead of taxonomy ids"
                ),
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "missing-expertise",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0277-probe2-false-gap",
            "verdict": "PASS",
            "independent": True,
            "sees_other_verdict": False,
            "scope_not_agreement": True,
        },
        "reviewers": [
            {
                "reviewer_id": "TST-0277-probe1-competency-hole",
                "verdict": "PASS",
                "independent": True,
                "sees_other_verdict": False,
                "scope": "named gap, exclusive claim, rubberstamp and synonym controls",
            },
            {
                "reviewer_id": "TST-0277-probe2-false-gap",
                "verdict": "PASS",
                "independent": True,
                "sees_other_verdict": False,
                "scope": "covered panel silence and both-states recruitment differential",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0277/simulate.py",
                "exists": True,
                "role": "confirmation-runtime",
            },
        ],
        "min_bytes_threshold": 2048,
        "evidence": [
            {
                "claim": "catalog TST-0277 requires a named competency hole, recruitment efficacy, and a false-gap control",
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
                    "evidence_requirement names the uncovered competency, the "
                    "recruitment trigger, and a post-recruitment-only claim"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{ev_line}",
            },
            {
                "claim": (
                    f"uncovered competency cryptography, trigger missing-expertise, "
                    f"exclusive claim {UNIQUE_CLAIM_ID} authored by recruited-crypto-critic"
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0277/fixtures.py:UNIQUE_CLAIM_TEXT"
                ),
            },
        ],
        "timestamps": {"emitted_at": now},
    }

    if COMPLETION_SENTINEL not in json.dumps(doc):
        print("FAILED:TST-0277 completion_sentinel not in document text")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    digest, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0277 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
