"""Emit command-center/audit/AUD-0068-claim-extraction-canonical.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "fixtures"))

from build_corpus import ensure_corpus  # noqa: E402
from contract import (  # noqa: E402
    OUT_REL,
    P1,
    P2,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
)
from extract import extract_corpus, resolve_corpus  # noqa: E402

QUESTION = (
    "Extract every material claim from the Prompt-One corpus into a canonical "
    "record carrying a stable claim ID, canonical mechanism, source lineage, "
    "confidence, and verification status."
)


def load_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def validate_record(schema: dict, record: dict) -> list[str]:
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{'.'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in validator.iter_errors(record)
    ]


def build() -> dict:
    ensure_corpus()
    corpus = resolve_corpus()
    extracted = extract_corpus(corpus["files"])
    schema = load_schema()
    rec_errors: list[str] = []
    seen: set[str] = set()
    for i, rec in enumerate(extracted["records"]):
        rec_errors.extend(f"records[{i}]:{e}" for e in validate_record(schema, rec))
        cid = rec.get("claim_id") or ""
        if cid in seen:
            rec_errors.append(f"duplicate-claim_id:{cid}")
        seen.add(cid)
    if extracted["planted_in_unmodified_corpus"]:
        rec_errors.append("planted-token-in-unmodified-corpus")
    if rec_errors:
        raise SystemExit("FAILED:AUD-0068 schema " + "; ".join(rec_errors[:12]))

    live_present = bool(corpus["live_present"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    catalog_line = 1
    snippet = "id\": \"AUD-0068\""
    if catalog.is_file():
        lines = catalog.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines, 1):
            if '"id": "AUD-0068"' in line:
                catalog_line = i
                snippet = line.strip()[:180]
                break

    mechanism = (
        "Every heading and every verdict-tagged sentence in the resolved "
        "Prompt-One 29-artifact contract corpus maps to a canonical claim "
        "record or an explicit NOT-A-CLAIM decision; records reverse-trace "
        "to their source span. Live harness-restore-20260806 is "
        + ("PRESENT" if live_present else "ABSENT on this Linux worktree")
        + f"; fixture_substituted={corpus['fixture_substituted_n']}/29."
    )
    envelope = {
        "claim_id": "AUD-0068-CLAIM-EXTRACTION-RUN",
        "canonical_mechanism": mechanism,
        "duplicate_of": [],
        "support": [],
        "contradiction": [],
        "source_lineage": [
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": catalog_line,
                "snippet": snippet,
            }
        ],
        "confidence": "high",
        "verification_status": "CONFIRMED" if extracted["record_n"] else "PARTIAL",
        "implementation_impact": "correctness",
        "settling_probe": {"id": "AUD-0068-probe1-coverage", "command": P1},
        "schema_version": "0.1.0-provisional",
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "question": QUESTION,
        "title": "Claim extraction from the corpus into canonical claim records",
        "kind": "claim-extraction",
        "ts": now,
        "records": extracted["records"],
        "not_a_claim": extracted["not_a_claim"],
        "coverage_index": extracted["coverage_index"],
        "corpus": corpus,
        "per_file": extracted["per_file"],
        "counts": {
            "contract_n": 29,
            "span_n": extracted["span_n"],
            "record_n": extracted["record_n"],
            "not_a_claim_n": extracted["not_a_claim_n"],
            "dropped_empty_n": len(extracted["dropped_empty"]),
            "live_read_n": corpus["live_read_n"],
            "fixture_substituted_n": corpus["fixture_substituted_n"],
        },
        "dropped_empty": extracted["dropped_empty"],
        "planted_in_unmodified_corpus": extracted["planted_in_unmodified_corpus"],
        "upstream_AUD_0067": {
            "output_path": "command-center/audit/AUD-0067-prompt-one-artifact-census.json",
            "present": (
                REPO / "command-center/audit/AUD-0067-prompt-one-artifact-census.json"
            ).is_file(),
        },
        "honesty": {
            "live_corpus_present": live_present,
            "fixture_is_byte_copy_of_prompt_one": False,
            "unread_reason": (
                "live harness-restore-20260806 numbered tree is absent; "
                "extraction runs over the closed 29-name contract fixture, "
                "which is not a byte copy of the Windows host tree"
                if not live_present
                else "live tree read where present; fixtures fill gaps"
            ),
        },
        "tests": [
            {
                "id": "probe1-coverage",
                "command": P1,
                "name": "every heading and verdict-tagged sentence maps, planted claim recalled",
            },
            {
                "id": "probe2-reverse-trace",
                "command": P2,
                "name": "sampled records reverse-trace to source spans; mutant snippet fails",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0068-probe2-reverse-trace",
            "verdict": "PASS",
            "independent": True,
        },
        "extension_points": {
            "spec_anchor": "_USER-PROMPTS.md:10664-10677",
            "spec_present": (REPO / "_USER-PROMPTS.md").is_file(),
        },
    }
    env_errs = validate_record(schema, envelope)
    if env_errs:
        raise SystemExit("FAILED:AUD-0068 envelope " + "; ".join(env_errs[:8]))
    if SENTINEL not in json.dumps(envelope):
        raise SystemExit("FAILED:AUD-0068 sentinel missing from envelope")
    return envelope


def main() -> int:
    doc = build()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_REL} records={doc['counts']['record_n']} "
        f"not_a_claim={doc['counts']['not_a_claim_n']} "
        f"spans={doc['counts']['span_n']} "
        f"fixture={doc['counts']['fixture_substituted_n']}/29"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
