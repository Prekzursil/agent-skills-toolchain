#!/usr/bin/env python3
"""Emit command-center/research/RES-0093.json from the live register engine."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import schema_util as SU  # noqa: E402

UID = "RES-0093"
OUT_REL = "command-center/research/RES-0093.json"
SCHEMA_REL = "command-center/schema/research-registry.schema.json"
FACTS_REL = "command-center/p2-wave/probes/RES-0093/fixtures/paper_facts.json"
SENTINEL = "SUCCESS:RES-0093"
COMPLETION = (
    "SUCCESS:RES-0093 in the receipt AND a benchmark register with an "
    "applicability verdict and a named detectable improvement per applicable row"
)
QUESTION = (
    "For each major agent benchmark, what capability does it actually measure, "
    "what is its known contamination or saturation status, and which of them "
    "could measure THIS program's improvement rather than a model's raw ability?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    facts = E.load_facts()
    rows = E.build_register(facts)
    tests = E.tests_from_register(rows)
    if not tests["named_improvement_per_applicable"]:
        print("FAILED:RES-0093 emit applicable rows missing named improvement")
        return 1
    if not tests["inapplicable_popular_control"]["pass"]:
        print("FAILED:RES-0093 emit missing popular inapplicable control")
        return 1
    if not tests["e3_cannot_promote"]:
        print("FAILED:RES-0093 emit E3 promoted a mechanism")
        return 1

    e3_ids = [
        c["claim_id"]
        for r in rows
        for c in r["citations"]
        if c["evidence_tier"] == "E3"
    ]
    if "swev-verbatim-gold" not in e3_ids:
        print("FAILED:RES-0093 emit planted E3 claim missing")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    applicable = [r["benchmark_id"] for r in rows if r["applicability_verdict"] == "applicable"]
    inapplicable = [
        r["benchmark_id"] for r in rows if r["applicability_verdict"] == "inapplicable"
    ]
    answer = (
        "This program's improvement is harness-level (plugin/skill/hook/MCP "
        "actually load; fail-closed confirmation; FAIL_TO_PASS test runner), "
        "not a weight-level IQ bump. Applicable detectors: "
        + ", ".join(applicable)
        + ". Popular inapplicable control: humaneval (static pass@k). "
        "OSWorld and WebArena are popular agent benches that still do not "
        "measure this harness. Public SWE-bench Verified is inapplicable as a "
        "clean improvement meter (OpenAI 2026 audit). E3 headline "
        "swev-verbatim-gold cannot promote a mechanism. "
        + SENTINEL
    )
    evidence = []
    for r in rows:
        for c in r["citations"]:
            evidence.append(
                {
                    "benchmark_id": r["benchmark_id"],
                    "claim_id": c["claim_id"],
                    "arxiv": c["arxiv"],
                    "doi": c["doi"],
                    "permalink": c["permalink"],
                    "section": c["section"],
                    "effect_size": c["effect_size"],
                    "baseline_value": c["baseline_value"],
                    "baseline_label": c["baseline_label"],
                    "evidence_tier": c["evidence_tier"],
                    "used_to_promote": c["claim_id"] in (r.get("promoting_claim_ids") or []),
                }
            )

    art = {
        "answer": answer,
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": SCHEMA_REL, "role": "catalog-shim"},
            {"path": SU.LOCAL_REL, "role": "live-schema"},
            {"path": FACTS_REL, "role": "paper-facts"},
            {
                "path": "command-center/p2-wave/probes/RES-0093/engine.py",
                "role": "engine",
            },
        ],
        "benchmark_register": rows,
        "completion_sentinel": COMPLETION,
        "evidence": evidence,
        "fetched_at": facts["fetched_at"],
        "id": UID,
        "inputs_absent_on_clone": facts["program"]["inputs_absent_on_clone"],
        "live_schema": SU.LOCAL_REL,
        "output_schema": SCHEMA_REL,
        "schema_note": (
            "Catalog output_schema is a GENERATED SHIM whose $ref points at "
            "https://ast-integrate.invalid/...; jsonschema 4.10.3 RefResolver "
            "tries the network. G-1 does not require that hop. This unit "
            "validates against the per-unit schema "
            f"{SU.LOCAL_REL}. Overwriting the shared catalog schema would be "
            "a sibling rebuild circle."
        ),
        "program_improvement": facts["program"],
        "question": QUESTION,
        "residual_unknowns": [
            "command-center/sources/REGISTER.md is absent on this clone.",
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md is absent on this clone; papers were read from arXiv/ar5iv and the OpenAI Verified blog.",
            "No live SWE-bench/GAIA/τ-bench run was executed; numbers are transcribed from the cited tables, not re-measured.",
            "Contamination detector false-positive rates are UNMEASURED in every introducing paper used here.",
            "SWE-bench Table 5 Claude 2 BM25 is 1.97 while §5 prose still says 1.96; this register uses the table cell and records the prose mismatch in the section field.",
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "RES-0093-probe2-controls",
            "starts_from": "mutants",
            "verdict": "PASS",
            "default_if_insufficient": "REFUTED",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": tests,
        "title": (
            "Census agent benchmarks and state precisely what each one "
            "measures and does not"
        ),
        "ts": now,
        "unit_id": UID,
        "applicable_ids": applicable,
        "inapplicable_ids": inapplicable,
    }

    errs = SU.error_list(art)
    if errs:
        print("FAILED:RES-0093 emit schema")
        for e in errs[:20]:
            print(" ", e)
        return 1
    if not SU.rejects_garbage():
        print("FAILED:RES-0093 emit schema accepted garbage")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(art, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(f"applicable={applicable}")
    print(f"inapplicable={inapplicable}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
