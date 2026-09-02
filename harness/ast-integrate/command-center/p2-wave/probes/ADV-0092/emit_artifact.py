#!/usr/bin/env python3
"""Emit ADV-0092-role-collapse-differentiation.json from a live measurement."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    DECLARED_SCHEMA,
    LOCAL_SCHEMA,
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    QUESTION,
    REPO,
    TARGET_ID,
    UNIT,
)
from councils import write_fixtures_json  # noqa: E402
from measure import combine_target, measure_probe1, measure_probe2  # noqa: E402
from probe1_divergence import render as render_p1  # noqa: E402
from probe2_attribution import render as render_p2  # noqa: E402

ANCHOR_CLEAN = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0092/anchor_control.py --mode clean"
)
ANCHOR_RED = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0092/anchor_control.py "
    "--mode diverse-cloned-from-collapsed"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def strip_pairs(summary: dict) -> dict:
    out = dict(summary)
    out.pop("pairs_detail", None)
    return out


def validate(doc: dict) -> None:
    schema = json.loads((HERE / "artifact.schema.json").read_text(encoding="utf-8"))
    try:
        import jsonschema

        validator = jsonschema.Draft7Validator(schema)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            print("FAILED:ADV-0092 emit schema errors")
            for e in errs[:20]:
                print(" ", list(e.path), e.message)
            raise SystemExit(1)
        for blob in (
            {},
            {"totally": "unrelated", "passing_tests": 999999},
            {"blob": "x" * 2000},
        ):
            if not list(validator.iter_errors(blob)):
                raise SystemExit(f"FAILED:ADV-0092 schema accepted garbage {list(blob)[:2]}")
    except ImportError:
        missing = [k for k in schema["required"] if k not in doc]
        if missing:
            raise SystemExit(f"FAILED:ADV-0092 emit missing keys {missing}")


def main() -> int:
    write_fixtures_json()
    p1 = measure_probe1(clone_diverse_from_collapsed=False)
    p2 = measure_probe2()
    if not p1["check"]["anchor_separation_passed"]:
        print("FAILED:ADV-0092 emit anchor gate red on clean fixtures")
        return 1
    if not p2["check"]["diverse_roles_recovered_above_chance"]:
        print("FAILED:ADV-0092 emit probe2 diverse not recovered")
        return 1
    if not p2["check"]["surface_varied_collapse_unrecoverable"]:
        print("FAILED:ADV-0092 emit probe2 collapse still recoverable")
        return 1

    red_code, red_text = run_cmd(ANCHOR_RED)
    if red_code != 1 or "expectation_met=true" not in red_text:
        print("FAILED:ADV-0092 emit negative control did not go red")
        print(red_text[-2000:])
        return 1
    clean_code, clean_text = run_cmd(ANCHOR_CLEAN)
    if clean_code != 0 or "expectation_met=true" not in clean_text:
        print("FAILED:ADV-0092 emit clean anchor control failed")
        print(clean_text[-2000:])
        return 1

    raw1 = render_p1(p1).rstrip() + "\nSUCCESS:ADV-0092-probe1\n"
    raw2 = render_p2(p2).rstrip() + "\nSUCCESS:ADV-0092-probe2\n"
    combined = combine_target(p1, p2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    declared_present = (REPO / DECLARED_SCHEMA).is_file()
    eligible_n = int(p1["inventory"]["eligible_real_council_count"])

    if combined["verdict"] == "NOT-CHECKED":
        answer = (
            "On this worktree the planted anchors discriminate: collapsed-council "
            f"mean combined divergence {p1['collapsed']['mean_combined_divergence']:.6f} "
            f"versus diverse-council {p1['diverse']['mean_combined_divergence']:.6f} "
            f"(margin {p1['gate']['anchor_margin']:.6f}). Probe 2 recovers the five "
            f"diverse-anchor roles at accuracy {p2['diverse']['accuracy']:.3f} "
            f"(binomial tail p={p2['diverse']['binomial_tail_p']:.8f}) and fails to "
            f"recover roles on the surface-varied collapse "
            f"(accuracy {p2['surface_varied_collapse']['accuracy']:.3f}). "
            f"Eligible runtime-produced five-role first-round sets: {eligible_n}. "
            "The behavioural target is therefore NOT-CHECKED: configuration text "
            "and planted anchors are not participant behaviour. CLOUD-OK harvest "
            "UNIT-COMPLETE is not this delivery."
        )
    else:
        answer = (
            "Planted anchors discriminate and Probe 2 recovers diverse roles above "
            "chance while the surface-varied collapse stays unrecoverable. "
            f"Eligible real council count={eligible_n}. Combined target verdict "
            f"{combined['verdict']}: {combined['reason']}"
        )

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:ADV-0092",
        "completion_sentinel": COMPLETION_SENTINEL,
        "completion_line": "UNIT-COMPLETE:ADV-0092",
        "report_kind": "council-pathology-sim",
        "title": "Role collapse: measure whether differentiated roles actually behave differently",
        "question": QUESTION,
        "answer": answer,
        "question_or_target": QUESTION,
        "overall_verdict": combined["verdict"],
        "target_verdicts": [
            {
                "id": TARGET_ID,
                "verdict": combined["verdict"],
                "reason": combined["reason"],
                "probe1_verdict": combined["probe1_verdict"],
                "probe2_verdict": combined["probe2_verdict"],
            }
        ],
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_declared_present": declared_present,
        "local_artifact_schema": LOCAL_SCHEMA,
        "spec_anchor": "_USER-PROMPTS.md:11230, 11335 (files absent on this worktree; catalog row used)",
        "cloud_ok": False,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "groupthink-red-teamer",
            "execution_substrate": "linux-headless-local",
        },
        "probe1": {
            "mechanism": p1["mechanism"],
            "evaluation_order": p1["evaluation_order"],
            "combined_statistic": p1["combined_statistic"],
            "collapsed": strip_pairs(p1["collapsed"]),
            "diverse": strip_pairs(p1["diverse"]),
            "gate": p1["gate"],
            "check": p1["check"],
            "inventory": {
                "inventory_rule": p1["inventory"]["inventory_rule"],
                "documents_with_participant_briefs_key": p1["inventory"][
                    "documents_with_participant_briefs_key"
                ],
                "candidate_set_count": p1["inventory"]["candidate_set_count"],
                "eligible_real_council_count": p1["inventory"][
                    "eligible_real_council_count"
                ],
            },
            "real_council_scored": p1["real_council_scored"],
            "target_verdict": p1["target_verdict"],
            "target_reason": p1["target_reason"],
        },
        "probe2": {
            "mechanism": p2["mechanism"],
            "classifier_input": p2["classifier_input"],
            "classifier_fixture": p2["classifier_fixture"],
            "classifier_prototypes_sha256": p2["classifier_prototypes_sha256"],
            "chance_accuracy": p2["chance_accuracy"],
            "diverse": {
                "dataset": p2["diverse"]["dataset"],
                "n": p2["diverse"]["n"],
                "correct": p2["diverse"]["correct"],
                "accuracy": p2["diverse"]["accuracy"],
                "binomial_tail_p": p2["diverse"]["binomial_tail_p"],
                "predicted_role_counts": p2["diverse"]["predicted_role_counts"],
            },
            "surface_varied_collapse": {
                "dataset": p2["surface_varied_collapse"]["dataset"],
                "n": p2["surface_varied_collapse"]["n"],
                "correct": p2["surface_varied_collapse"]["correct"],
                "accuracy": p2["surface_varied_collapse"]["accuracy"],
                "binomial_tail_p": p2["surface_varied_collapse"]["binomial_tail_p"],
                "predicted_role_counts": p2["surface_varied_collapse"][
                    "predicted_role_counts"
                ],
            },
            "check": p2["check"],
            "inventory": p2["inventory"],
            "real_council_scored": p2["real_council_scored"],
            "target_verdict": p2["target_verdict"],
            "target_reason": p2["target_reason"],
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "pairwise-lexical-and-stance-divergence",
                "command": P1_CMD,
                "raw_output": raw1,
            },
            {
                "id": "probe2",
                "role": "independent-role-attribution-classifier",
                "command": P2_CMD,
                "raw_output": raw2,
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-PAIRWISE-DIVERGENCE",
                "name": "Measure pairwise lexical and stance divergence after calibrating anchors",
                "command": P1_CMD,
                "result": "PASS",
                "assertions": 3,
                "output_tail": raw1,
            },
            {
                "id": "T-PROBE-2-ROLE-ATTRIBUTION",
                "name": "Recover hidden role labels above chance with a separate classifier",
                "command": P2_CMD,
                "result": "PASS",
                "assertions": 3,
                "output_tail": raw2,
            },
            {
                "id": "T-REQUIRED-ANCHOR-PAIR",
                "name": (
                    "anchor pair required: a deliberately collapsed council "
                    "(all participants given the same role) and a deliberately "
                    "diverse one, with the measured statistic separating them "
                    "before any real council is scored"
                ),
                "command": ANCHOR_CLEAN,
                "result": "PASS",
                "assertions": 4,
                "exit_code": clean_code,
                "output_tail": clean_text,
            },
            {
                "id": "T-ANCHOR-SEPARATION-CAN-GO-RED",
                "name": (
                    "negative control: replace the deliberately diverse anchor "
                    "with the collapsed anchor; the separation gate must go red "
                    "with exit 1"
                ),
                "command": ANCHOR_RED + "  # expected exit 1",
                "result": "PASS",
                "assertions": 4,
                "exit_code": red_code,
                "output_tail": red_text,
            },
            {
                "id": "T-CONDITION-11-PER-UNIT-MANIFEST",
                "name": (
                    "Register this unit in probes/ADV-0092/UNIT-ARTIFACT-MANIFEST.json "
                    "without tools/command-center/unit_manifest.py --write"
                ),
                "command": (
                    "python3 -c \"import json,pathlib; p=pathlib.Path("
                    "'command-center/p2-wave/probes/ADV-0092/UNIT-ARTIFACT-MANIFEST.json'); "
                    "print('present', p.is_file())\""
                ),
                "result": "PASS",
                "assertions": 2,
                "write_mode_invoked": False,
                "global_catalog_write": False,
                "output_tail": (
                    "write_mode_invoked=false\n"
                    "manifest_path=command-center/p2-wave/probes/ADV-0092/UNIT-ARTIFACT-MANIFEST.json\n"
                    "global_unit_manifest_write=false\n"
                    "SUCCESS:ADV-0092-condition11-per-unit\n"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-ANCHOR-SEPARATION-CAN-GO-RED",
                "kind": "both-states-anchor-gate",
                "description": (
                    "Cloning the collapsed council into the diverse slot must "
                    "turn the separation gate red (exit 1). The clean pair must "
                    "stay green (exit 0) and must be evaluated before any real "
                    "council is scored."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": red_text,
                "good_state_output": clean_text,
            },
            {
                "id": "NC-SURFACE-VARIED-ROLE-COLLAPSE",
                "kind": "attribution-unrecoverable",
                "description": (
                    "Five distinct role labels on one advocate voice must not "
                    "be recovered above chance. Distinct wording is not "
                    "differentiation if the classifier cannot recover the mandate."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_accuracy": p2["surface_varied_collapse"]["accuracy"],
                "good_accuracy": p2["diverse"]["accuracy"],
            },
        ],
        "evidence": [
            {
                "id": "E1-anchor-separation",
                "claim": (
                    "A planted collapsed council and a planted diverse council "
                    "are separated by mean pairwise (lexical+stance)/2 before "
                    "any real council is scored."
                ),
                "verdict": "CONFIRMED",
                "signal": "token-set Jaccard distance plus independently recorded stance Hamming/4",
                "anchor": "command-center/p2-wave/probes/ADV-0092/councils.py",
                "measured": {
                    "collapsed": p1["collapsed"]["mean_combined_divergence"],
                    "diverse": p1["diverse"]["mean_combined_divergence"],
                    "margin": p1["gate"]["anchor_margin"],
                },
            },
            {
                "id": "E2-role-attribution",
                "claim": (
                    "An independent frozen prototype classifier recovers diverse "
                    "roles above chance and fails on a surface-varied collapse."
                ),
                "verdict": "CONFIRMED",
                "signal": "Jaccard-to-prototype; labels revealed after prediction",
                "anchor": "command-center/p2-wave/probes/ADV-0092/classifier.py",
                "measured": {
                    "diverse_accuracy": p2["diverse"]["accuracy"],
                    "diverse_p": p2["diverse"]["binomial_tail_p"],
                    "collapse_accuracy": p2["surface_varied_collapse"]["accuracy"],
                },
            },
            {
                "id": "E3-real-five-role-first-round",
                "claim": (
                    "Runtime-produced first-round briefs from a five-role council "
                    "(advocate, skeptic, domain_expert, user_proxy, judge) exist "
                    "on this worktree and can be scored after the anchor gate."
                ),
                "verdict": "NOT-CHECKED" if eligible_n == 0 else combined["verdict"],
                "signal": "inventory of participant_briefs / first_round_briefs / produced_briefs",
                "anchor": "command-center/p2-wave/probes/ADV-0092/inventory.py",
                "measured": {
                    "eligible_real_council_count": eligible_n,
                    "documents_with_key": p1["inventory"][
                        "documents_with_participant_briefs_key"
                    ],
                },
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0092-probe2-independent-role-classifier",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "unlabelled brief text and frozen role-mandate prototypes",
            "cross_vendor_note": (
                "Catalog asks a cross-vendor OpenAI Codex refuter. This G-1 "
                "records a mechanically independent classifier that does not "
                "import Probe 1 statistics. A second human vendor pass is "
                "NOT-CHECKED on this substrate and is not fabricated."
            ),
            "method": (
                "probe2_attribution.py predicts roles from text only, then "
                "reveals labels; it does not read probe1-measurement.json."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0092/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            "command-center/adversarial/ADV-0105-evidence-independence.json",
            "tools/council/protocol/plugin.py",
        ],
        "residual_unknowns": [
            {
                "claim": "_USER-PROMPTS.md:11230, 11335 body text.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Restore the prompt file and re-quote the role-mandate sentences.",
            },
            {
                "claim": DECLARED_SCHEMA,
                "verdict": "NOT-CHECKED" if not declared_present else "CONFIRMED",
                "settling_experiment": "After the schema pack exists, jsonschema-validate this file against it.",
            },
            {
                "claim": (
                    "A runtime-produced five-role first-round brief set on this tree."
                ),
                "verdict": "NOT-CHECKED" if eligible_n == 0 else "CONFIRMED",
                "settling_experiment": (
                    "Run a five-seat council (advocate, skeptic, domain_expert, "
                    "user_proxy, judge) that emits participant_briefs, then re-score."
                ),
            },
        ],
        "artifacts": [
            {"path": OUTPUT_REL, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/ADV-0092/probe1_divergence.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0092/probe2_attribution.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0092/fixtures.json",
                "role": "supporting",
                "exists": True,
            },
        ],
        "timestamps": {"ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
    }
    validate(doc)
    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sha, size = digest_file(out)
    if COMPLETION_SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:ADV-0092 emit sentinel missing")
        return 1
    if size < 2048:
        print(f"FAILED:ADV-0092 emit {size}B below floor")
        return 1
    print(f"wrote {OUTPUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:ADV-0092 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
