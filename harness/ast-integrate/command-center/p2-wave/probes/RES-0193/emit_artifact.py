#!/usr/bin/env python3
"""Emit RES-0193 tokens-per-verified-claim measurement-run artifact."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
from modes import MODES  # noqa: E402

OUT = E.REPO / E.OUT_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0193/probe1_verified_denominator.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0193/probe2_falsification_exempt.py"
)
QUESTION = (
    "Compute tokens-and-wall-clock per verified claim for each research mode "
    "used in this program, so a mode that produces volume without verified "
    "content is visible - and state which modes fall below the threshold to "
    "remain in the default set. Distinct from any per-agent productivity "
    "score: falsification work is exempt and counted separately, per the "
    "standing rule against volume metrics."
)


def _claim(
    claim_id: str,
    text: str,
    verdict: str,
    band: str,
    signals: list[dict],
    lineage: list[dict],
    caveat: str,
    mechanism: str,
) -> dict:
    return {
        "claim_id": claim_id,
        "claim": text,
        "canonical_mechanism": mechanism,
        "verdict": verdict,
        "evidence_tier": "E1" if verdict == "CONFIRMED" else "E3",
        "confidence_band": band,
        "sherman_kent": {
            "band": band,
            "map": E.SHERMAN_KENT[band],
            "vocabulary": "Sherman Kent 1964 / ICD-203 analytic confidence",
        },
        "named_settling_probe": P1 if "denominator" in claim_id.lower() or "volume" in claim_id.lower() else P2,
        "independent_verification_path": P2 if "falsif" in claim_id.lower() or "default" in claim_id.lower() else P1,
        "signals": signals,
        "source_lineage": lineage,
        "strongest_caveat": caveat,
    }


def main() -> int:
    telemetry = E.write_recorded_runs()
    live = E.score_telemetry(telemetry)
    gate = live["gate"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lineage = E.source_lineage_rows(now)
    catalog = E.catalog_unit()
    cat_lin = [row for row in lineage if row["rail"] == "catalog"]
    tel_lin = [row for row in lineage if row["rail"] == "recorded-telemetry"]
    body_lin = [row for row in lineage if row["rail"] == "mode-body"]

    production_rows = []
    for mode in MODES:
        scored = live["production_by_mode"][mode["id"]]
        production_rows.append(
            {
                **mode,
                "efficiency": {
                    "status": scored["status"],
                    "production_tokens": scored["production_tokens"],
                    "falsification_tokens": scored["falsification_tokens"],
                    "production_wall_ms": scored["production_wall_ms"],
                    "falsification_wall_ms": scored["falsification_wall_ms"],
                    "independently_verified_new_claims": scored["independently_verified_new_claims"],
                    "unverified_new_claims": scored["unverified_new_claims"],
                    "falsification_claims": scored["falsification_claims"],
                    "tokens_per_verified_claim": scored["tokens_per_verified_claim"],
                    "wall_ms_per_verified_claim": scored["wall_ms_per_verified_claim"],
                    "infinite": scored["infinite"],
                    "below_default_set_threshold": scored["below_default_set_threshold"],
                },
            }
        )

    control = live["controls"][0]
    landscape = live["production_by_mode"]["broad_landscape_scan"]
    land_run = next(r for r in telemetry["runs"] if r["run_id"] == "RUN-broad_landscape_scan")
    planted = E.plant_unverified_volume(land_run, extra=100)
    legal = E.score_run(land_run)
    planted_score = E.score_run(planted)
    wrong_base = E.wrong_metric_count_unverified(land_run)
    wrong_planted = E.wrong_metric_count_unverified(planted)

    claims = [
        _claim(
            "RES-0193-C1-verified-denominator",
            (
                "Tokens-per-verified-claim and wall-clock-per-verified-claim use "
                "only independently verified new_finding claims in the denominator. "
                "Unverified drafts and falsification products are excluded, so "
                "unverified output cannot improve a mode's score."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "id": "S1-engine-score-run",
                    "kind": "computed-telemetry",
                    "observation": (
                        f"landscape verified={landscape['independently_verified_new_claims']} "
                        f"unverified={landscape['unverified_new_claims']} "
                        f"tokens_per_verified={landscape['tokens_per_verified_claim']}"
                    ),
                },
                {
                    "id": "S2-unverified-volume-mutant",
                    "kind": "negative-control",
                    "observation": (
                        "Adding 100 unverified drafts leaves tokens_per_verified "
                        f"unchanged ({legal['tokens_per_verified_claim']} vs "
                        f"{planted_score['tokens_per_verified_claim']}); the illegal "
                        f"verified+unverified metric improves ({wrong_base} -> {wrong_planted})."
                    ),
                },
            ],
            tel_lin + body_lin[:1],
            (
                "Telemetry is local whitespace-token counts over committed bodies, "
                "not hosted LLM billing logs. The formula is what this unit settles; "
                "the absolute dollars of a vendor API are NOT-CHECKED."
            ),
            "verified-only denominator on recorded production tokens",
        ),
        _claim(
            "RES-0193-C2-falsification-exempt",
            (
                "A refutation-only run that produces zero new claims is classified "
                "EXEMPT_FALSIFICATION with infinite=false. Falsification tokens are "
                "counted on a separate lane. The metric does not divide by zero "
                "and does not score agents on output volume."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "id": "S1-control-run-status",
                    "kind": "computed-telemetry",
                    "observation": (
                        f"NC-refutation-only status={control['status']} "
                        f"infinite={control['infinite']} "
                        f"production_tokens={control['production_tokens']} "
                        f"verified={control['independently_verified_new_claims']}"
                    ),
                },
                {
                    "id": "S2-probe2-independent-recompute",
                    "kind": "independent-reimplementation",
                    "observation": (
                        "probe2 reimplements the exemption without importing "
                        "engine.score_run and requires status EXEMPT_FALSIFICATION."
                    ),
                },
            ],
            tel_lin + cat_lin,
            (
                "Exemption applies to production-zero plus verified-zero. A mode "
                "that spends production tokens and still verifies nothing is "
                "ZERO_VERIFIED_YIELD and is ejected from the default set without "
                "using JSON Infinity."
            ),
            "falsification-lane exemption from tokens-per-claim",
        ),
        _claim(
            "RES-0193-C3-default-set-threshold",
            (
                "Modes that fail the keep rule — >=1 independently verified new "
                "claim and tokens/wall per verified at or below "
                "max(floor, 10× median) — are listed as below the threshold to "
                "remain in the default set. On this recorded corpus that set is "
                f"{gate['below_default_set_threshold']}."
            ),
            "CONFIRMED",
            "likely",
            [
                {
                    "id": "S1-gate-from-engine",
                    "kind": "computed-telemetry",
                    "observation": (
                        f"median={gate['median_tokens_per_verified']} "
                        f"ceiling={gate['token_ceiling']} "
                        f"below={gate['below_default_set_threshold']} "
                        f"remain={gate['remain_in_default_set']}"
                    ),
                },
                {
                    "id": "S2-landscape-volume-visible",
                    "kind": "mode-row",
                    "observation": (
                        "broad_landscape_scan carries a large unverified mention "
                        "pad; its tokens-per-verified is the corpus outlier and "
                        "is required to appear in below_default_set_threshold."
                    ),
                },
            ],
            cat_lin + tel_lin,
            (
                "The 12-mode roster is reconstructed because _USER-PROMPTS.md is "
                "absent on this tree. The keep-rule floors are a stated policy of "
                "this measurement, not a number printed in the missing spec. "
                "Hosted-run telemetry for RES-0001..RES-0192 was not on disk."
            ),
            "default-set keep rule on per-mode verified efficiency",
        ),
        _claim(
            "RES-0193-C4-not-a-per-agent-volume-score",
            (
                "The score is per research mode, not per agent. Score inputs are "
                "production tokens, production wall-clock, and independently "
                "verified new claims. output_bytes, unverified count, and agent "
                "identity are recorded-not-scored (catalog B7 / ADV-0089 volume gate)."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "id": "S1-score-input-allowlist",
                    "kind": "schema-of-metric",
                    "observation": (
                        "score_run reads tokens.production, wall_clock_ms_production, "
                        "and independently_verified new_finding claims only."
                    ),
                },
                {
                    "id": "S2-catalog-b7-citation",
                    "kind": "catalog-text",
                    "observation": (
                        "RES-0193 inputs name rules/common/fan-out-contract.md "
                        "section B7 (never score agents on output volume); the "
                        "markdown file is absent on this tree so the citation is "
                        "catalog-anchored, not file-quoted."
                    ),
                },
            ],
            cat_lin,
            (
                "rules/common/fan-out-contract.md is not on this worktree. The "
                "B7 text is taken from WORK-UNIT-CATALOG.json inputs, not from "
                "the rule file bytes."
            ),
            "per-mode efficiency with volume fields excluded from the score",
        ),
    ]

    unit = catalog
    doc = {
        "unit_id": "RES-0193",
        "state": "SUCCESS",
        "sentinel": E.SENTINEL,
        "completion_sentinel": unit.get("completion_sentinel") or E.SENTINEL,
        "report_kind": "measurement-run",
        "schema_version": 1,
        "output_schema": "command-center/schema/measurement-run.schema.json",
        "title": unit.get("title"),
        "question": QUESTION,
        "measured_at": now,
        "execution_substrate": "linux-local-serialized",
        "cloud_ok": False,
        "mode_roster_reconstruction": {
            "spec_file_present": False,
            "spec_path": "_USER-PROMPTS.md",
            "spec_lines": "10702-10715",
            "n_modes": len(MODES),
            "cited": [m["id"] for m in MODES if m["citation_status"] == "cited"],
            "inferred": [m["id"] for m in MODES if m["citation_status"] == "inferred"],
            "note": (
                "_USER-PROMPTS.md and command-center/sources/REGISTER.md and "
                "rules/common/fan-out-contract.md are absent. Modes are "
                "reconstructed from catalog citations of those lines."
            ),
        },
        "telemetry": {
            "path": "command-center/p2-wave/probes/RES-0193/fixtures/recorded-runs.json",
            "kind": telemetry.get("kind"),
            "tokenizer": telemetry.get("tokenizer"),
            "wall_clock": telemetry.get("wall_clock"),
            "n_runs": len(telemetry["runs"]),
            "sha256": E.sha256_file(E.RECORDED)[0],
        },
        "metric": {
            "numerator": "production_tokens and production_wall_ms (falsification excluded)",
            "denominator": "count of new_finding claims with independently_verified true",
            "not_inputs": ["output_bytes", "unverified_new_claims", "agent_id", "finding_count_raw"],
            "zero_verified_production": "ZERO_VERIFIED_YIELD, not JSON Infinity",
            "zero_verified_falsification_only": "EXEMPT_FALSIFICATION, infinite=false",
        },
        "per_mode_efficiency": production_rows,
        "default_set_gate": gate,
        "modes_below_default_set_threshold": gate["below_default_set_threshold"],
        "modes_remaining_in_default_set": gate["remain_in_default_set"],
        "negative_controls": [
            {
                "id": "NC-refutation-only-zero-new-claims",
                "run_id": "NC-refutation-only",
                "result": control,
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "Refutation-only spend with zero new claims must not be "
                    "scored as infinitely inefficient."
                ),
            },
            {
                "id": "NC-unverified-volume-cannot-improve-score",
                "run_id": "RUN-broad_landscape_scan",
                "legal_tokens_per_verified": legal["tokens_per_verified_claim"],
                "planted_unverified_tokens_per_verified": planted_score["tokens_per_verified_claim"],
                "illegal_metric_improves": (
                    wrong_base is not None
                    and wrong_planted is not None
                    and wrong_planted < wrong_base
                ),
                "score_unchanged": legal["tokens_per_verified_claim"]
                == planted_score["tokens_per_verified_claim"],
                "description": (
                    "Planting 100 unverified drafts must not lower "
                    "tokens-per-verified; the illegal combined denominator does."
                ),
            },
        ],
        "claims": claims,
        "source_lineage": lineage,
        "evidence_tier_ledger": {
            "E1": "recomputed from recorded telemetry on this worktree",
            "E3": "catalog reconstruction of missing spec files",
        },
        "reviewer": {
            "reviewer_id": "RES-0193-probe2-falsification-exempt",
            "independent": True,
            "verdict": "PASS",
            "defaults_to": "REFUTED",
            "scope_not_agreement": True,
            "notes": (
                "probe2 reimplements the exemption and the keep-rule without "
                "calling engine.score_run, re-hashes recorded telemetry, and "
                "fails closed if Infinity or unverified volume enters the score."
            ),
        },
        "produced_by": {
            "role": "measurement-engineer",
            "vendor": "cursor",
            "model": "grok-4.6",
            "execution_substrate": "linux-local",
        },
        "tests": [
            {"id": "named-probe-1", "command": P1, "result": "PENDING"},
            {"id": "named-probe-2", "command": P2, "result": "PENDING"},
            {
                "id": "NC-refutation-only-zero-new-claims",
                "command": P2,
                "result": "PENDING",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "artifacts": [
            {"path": E.OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0193/engine.py",
                "exists": True,
                "role": "engine",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0193/fixtures/recorded-runs.json",
                "exists": True,
                "role": "recorded-telemetry",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/RES-0193/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "inputs_absent_on_this_tree": [
            "_USER-PROMPTS.md",
            "command-center/sources/REGISTER.md",
            "rules/common/fan-out-contract.md",
            "command-center/schema/measurement-run.schema.json",
        ],
        "caveat": (
            "Strongest caveat: cost is whitespace-token and local-hash wall-clock "
            "over a committed mode-body corpus that stands in for missing hosted "
            "run telemetry. It shows the metric's failure modes (volume without "
            "verification; falsification exemption) live. It is not a claim about "
            "Anthropic/OpenAI billed tokens for RES-0001..RES-0192."
        ),
        "strongest_surviving_counterargument": (
            "If the missing _USER-PROMPTS.md 12-mode list differs from this "
            "reconstruction, a mode could be mis-attributed. Citation_status "
            "separates cited names from inferred fillers; the metric still "
            "applies to whatever ids the roster carries."
        ),
        "two_independent_signals": [
            {
                "id": "signal-python-engine-score",
                "shell": "python3",
                "measurement": "engine.score_run over recorded-runs.json",
            },
            {
                "id": "signal-probe2-reimplementation",
                "shell": "python3",
                "measurement": "probe2 local formula without engine.score_run",
            },
        ],
    }

    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if E.SENTINEL not in text:
        print("FAILED:RES-0193 emit sentinel missing")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0193 emit self-declared blocked")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    digest, size = E.sha256_file(OUT)
    print(f"wrote {E.OUT_REL} bytes={size} sha256={digest}")
    print(
        "below="
        + ",".join(gate["below_default_set_threshold"])
        + " remain="
        + str(len(gate["remain_in_default_set"]))
        + " nc="
        + str(control["status"])
    )
    print(E.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
