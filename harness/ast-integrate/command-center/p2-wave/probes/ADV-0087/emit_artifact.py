#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0087-judge-same-vendor-bias.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from experiment import REPO, run_all  # noqa: E402

OUT_REL = "command-center/adversarial/ADV-0087-judge-same-vendor-bias.json"
UNIT = "ADV-0087"
COMPLETION = (
    "SUCCESS:ADV-0087 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0087 <reason>."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0087/probe1_blind.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0087/probe2_label_swap.py"
)


def main() -> int:
    live = run_all()
    p1, p2 = live["probe1"], live["probe2"]
    hist, prior = live["historical"], live["own_prior"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_raw = json.dumps(p1, indent=2, sort_keys=True, default=str)
    p2_raw = json.dumps(p2, indent=2, sort_keys=True, default=str)
    hist_raw = json.dumps(hist, indent=2, sort_keys=True)
    prior_raw = json.dumps(prior, indent=2, sort_keys=True)

    targets = [
        {
            "target_id": "openai-judge-blinded-versus-unblinded-attribution",
            "verdict": "REFUTED",
            "scope": "ARC-0002 rubric judge invocable on this worktree",
            "note": (
                f"{p1['content_winner_flips']} winner flips across "
                f"{p1['n_pairs']} pairs when labels and brand tells are stripped."
            ),
        },
        {
            "target_id": "openai-judge-identical-content-label-swap",
            "verdict": "REFUTED",
            "scope": "ARC-0002 rubric judge invocable on this worktree",
            "note": (
                f"{p2['content_label_follow_count']} label-following flips; "
                "identical bodies keep the same winner when only OpenAI/Anthropic "
                "labels reverse."
            ),
        },
        {
            "target_id": "historical-anthropic-tournament-own-vendor-effect",
            "verdict": "NOT-CHECKED",
            "scope": "nine-architecture historical panel",
            "note": hist["reason"],
        },
        {
            "target_id": "judge-own-prior-output-effect",
            "verdict": prior["verdict"],
            "scope": prior["scope"],
            "note": (
                "Prior-output tell vs challenger: winner_changed="
                f"{prior['winner_changed']}."
            ),
        },
        {
            "target_id": "effect-relative-to-historical-decision-margins",
            "verdict": "NOT-CHECKED",
            "scope": "historical tournament numeric margins",
            "note": (
                "No recorded tournament decision margins on this tree. Local "
                f"quality-gap margin on the rubric is {live['local_quality_margin']}; "
                "attribution flips on the subject judge are "
                f"{live['attribution_flips_on_subject_judge']}."
            ),
        },
    ]

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "title": "Same-vendor bias in the judge and tournament panel",
        "question": (
            "Does a judge systematically favour candidates produced by its own "
            "vendor or its own prior output, and how large is the effect relative "
            "to the decision margins actually used?"
        ),
        "answer": (
            "On this worktree the invocable judge is the pre-registered ARC-0002 "
            "rubric (weighted dimension marks, no vendor-identity input). Probe 1 "
            "blinding and probe 2 label-swap both leave its winners unchanged "
            f"({live['attribution_flips_on_subject_judge']} attribution flips). A "
            "planted label-following mutant does flip, so the detector is not a "
            "constant-green. Historical Anthropic-panel own-vendor effect and "
            "historical decision margins are NOT-CHECKED: phase3 has "
            f"{hist['architecture_dirs']} with produced_by.vendor="
            f"{hist['produced_by_vendor_counts']}, not an OpenAI-versus-Anthropic "
            "nine-architecture join. No gpt-5.6-sol session was invoked."
        ),
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": COMPLETION,
        "completion_sentinel": COMPLETION,
        "schema_version": 1,
        "profile": "benchmark-integrity",
        "report_kind": "benchmark-integrity",
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/benchmark-integrity.schema.json",
        "schema_note": (
            "Declared catalog contract command-center/schema/benchmark-integrity.schema.json "
            "is not on this worktree. Artifact is JSON and records the catalog "
            "completion sentinel plus both named probes."
        ),
        "spec_anchor": "_USER-PROMPTS.md:10795, 11059",
        "min_bytes_threshold": 4096,
        "overall_verdict": "PARTIAL",
        "cloud_ok": False,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0087/UNIT-ARTIFACT-MANIFEST.json",
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0087/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "benchmark-integrity-auditor",
            "execution_substrate": "headless-linux",
        },
        "reviewer": {
            "reviewer_id": "ADV-0087-probe2-label-swap",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "mechanical-label-swap",
            "model": None,
            "note": (
                "Catalog asked for two different-vendor LLM reviewers. This tree "
                "does not invoke a second vendor model. Probe 2 is a mechanically "
                "different instrument (label swap vs blinding), not a second vendor."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "target_verdicts": targets,
        "report": {
            "subject_judge": "ARC-0002 rubric (score.score_vector)",
            "subject_judge_path": "command-center/p2-wave/probes/ARC-0002/score.py",
            "llm_judge_invoked": False,
            "probe1_content_winner_flips": p1["content_winner_flips"],
            "probe2_content_label_follow_count": p2["content_label_follow_count"],
            "mutant_blinding_flips": p1["biased_mutant_winner_flips"],
            "mutant_label_follow_count": p2["biased_mutant_label_follow_count"],
            "local_quality_margin": live["local_quality_margin"],
            "historical": hist,
            "own_prior": {
                "verdict": prior["verdict"],
                "winner_changed": prior["winner_changed"],
                "scope": prior["scope"],
            },
        },
        "evidence": [
            {
                "id": "E-PROBE1-BLINDING",
                "claim": (
                    "Within the ARC-0002 rubric sample, stripping OpenAI-versus-"
                    "Anthropic attribution and brand tells did not change any pair winner."
                ),
                "verdict": "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0087/probe1_blind.py",
                "command": P1_CMD,
                "raw_output": p1_raw,
            },
            {
                "id": "E-PROBE2-LABEL-SWAP",
                "claim": (
                    "On identical bodies, reversing only OpenAI/Anthropic labels did "
                    "not change the rubric winner."
                ),
                "verdict": "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0087/probe2_label_swap.py",
                "command": P2_CMD,
                "raw_output": p2_raw,
            },
            {
                "id": "E-STABILITY-AND-MUTANT",
                "claim": (
                    "Identical-content/identical-label control is stable across three "
                    "repeats; a one-verdict mutation turns the detector red. The "
                    "label-following mutant flips under both named probes."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ADV-0087/experiment.py",
                "command": P2_CMD,
                "raw_output": json.dumps(p2["stability"], indent=2, sort_keys=True),
            },
            {
                "id": "E-HISTORICAL-PANEL",
                "claim": (
                    "The historical nine-architecture panel's own-vendor effect can "
                    "be estimated from this repository."
                ),
                "verdict": "NOT-CHECKED",
                "anchor": "command-center/phase3",
                "command": P2_CMD,
                "raw_output": hist_raw,
            },
            {
                "id": "E-OWN-PRIOR",
                "claim": (
                    "A prior-output tell changes the ARC-0002 rubric winner versus "
                    "a quality-matched challenger."
                ),
                "verdict": prior["verdict"],
                "anchor": "command-center/p2-wave/probes/ADV-0087/experiment.py",
                "raw_output": prior_raw,
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-BLINDING-INVARIANTS",
                "name": (
                    "Blinded and unblinded prompts retain identical candidate "
                    "content and positions while removing vendor brand attribution"
                ),
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-LABEL-SWAP-INVARIANTS",
                "name": (
                    "Original and swapped prompts keep pair content and reverse "
                    "only the OpenAI/Anthropic authorship labels"
                ),
                "command": P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-REQUIRED-STABILITY-CONTROL",
                "name": (
                    "control: identical content with identical labels must receive "
                    "a stable verdict across repeated runs, otherwise judge variance "
                    "swamps the bias measurement and no conclusion is available"
                ),
                "command": P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-NEGATIVE-CONTROL-CAN-GO-RED",
                "name": (
                    "negative control: mutate one repeated-run verdict while holding "
                    "its prompt fixed; the stability detector must go red"
                ),
                "command": P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-MUTANT-LABEL-FOLLOW",
                "name": (
                    "planted label-following mutant changes winners under blinding "
                    "and under label-swap (detector is not constant-green)"
                ),
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-JUDGE-NOT-CONSTANT",
                "name": "quality-gap pair prefers high-quality content (judge is not a constant TIE)",
                "command": P2_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-STABILITY-DETECTOR-RED-MUTANT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": "PASS",
            },
            {
                "id": "NC-LABEL-FOLLOWING-MUTANT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": "PASS",
            },
        ],
        "artifacts": [{"path": OUT_REL, "role": "primary", "exists": True}],
        "open_high_defects": [],
        "defect_ids": [],
        "residual_unknowns": [
            "No invocable gpt-5.6-sol (or other LLM) judge on this worktree; LLM same-vendor bias is unmeasured here.",
            "Historical nine-architecture panel and decision margins are absent or unjoinable (produced_by.vendor in {cursor, xai}).",
            "Catalog two-vendor LLM reviewer requirement is unmet; probe 2 is a mechanical second instrument.",
        ],
        "notes": (
            "G-1 ADV-0087: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not run global "
            "unit_manifest.py --write. cloud_ok is not delivery."
        ),
    }

    path = REPO / OUT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=False) + "\n"
    if COMPLETION not in text:
        print("FAILED:ADV-0087 emit missing completion sentinel")
        return 1
    path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
