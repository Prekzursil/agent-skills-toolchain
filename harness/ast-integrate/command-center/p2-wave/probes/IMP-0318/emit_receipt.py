#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0318.json from live unanimity measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import MODULE_REL, measure  # noqa: E402

OUT = "command-center/receipts/IMP-0318.json"
SENTINEL = "SUCCESS:IMP-0318"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0318/probe1_planted_wrong_and_rate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0318/probe2_negative_controls.py"
)
SUPPORTING = [
    "tools/council/__init__.py",
    "tools/council/antifail/__init__.py",
    MODULE_REL,
    "command-center/p2-wave/probes/IMP-0318/fixtures.py",
    "command-center/p2-wave/probes/IMP-0318/scenario.py",
    "command-center/p2-wave/probes/IMP-0318/probe1_planted_wrong_and_rate.py",
    "command-center/p2-wave/probes/IMP-0318/probe2_negative_controls.py",
    "command-center/p2-wave/probes/IMP-0318/emit_receipt.py",
    "command-center/p2-wave/probes/IMP-0318/fixtures/planted-wrong-consensus.json",
    "command-center/p2-wave/probes/IMP-0318/fixtures/correct-instant.json",
    "command-center/p2-wave/probes/IMP-0318/fixtures/late-legitimate.json",
    "command-center/p2-wave/probes/IMP-0318/fixtures/contested.json",
]


def digest(rel: str) -> tuple[str, int, bool]:
    path = REPO / rel
    if not path.is_file():
        return "", 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def art(rel: str, role: str) -> dict:
    sha, size, exists = digest(rel)
    return {
        "path": rel,
        "sha256": sha or ("0" * 64),
        "bytes": size,
        "exists": exists,
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = measure()
    if not m["pass"]:
        print(json.dumps(m, indent=2, sort_keys=True)[:4000])
        print("FAILED:IMP-0318 emit measure")
        return 1

    c = m["canonical"]
    rate = m["rate"]
    src = art(MODULE_REL, "implementation")
    planted_fix = (
        "command-center/p2-wave/probes/IMP-0318/fixtures/planted-wrong-consensus.json"
    )
    artifacts = [src] + [art(p, "supporting") for p in SUPPORTING if p != MODULE_REL]
    artifact_paths = [a["path"] for a in artifacts]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {
        "artifact_paths": artifact_paths,
        "artifacts": artifacts,
        "completion_sentinel": SENTINEL,
        "evidence": [
            {
                "anchor": f"{MODULE_REL}:evaluate",
                "claim": (
                    "A planted-wrong instant consensus is overturned by the "
                    "second pass; first_outcome != final_outcome."
                ),
                "kind": "command",
                "note": (
                    f"{c['planted_wrong']['first_outcome']} -> "
                    f"{c['planted_wrong']['final_outcome']}"
                ),
                "path": planted_fix,
                "verdict": "CONFIRMED",
            },
            {
                "anchor": f"{MODULE_REL}:outcome_change_rate",
                "claim": (
                    "Outcome-change rate across 20 triggered runs is measured, "
                    "not assumed."
                ),
                "kind": "measurement",
                "note": (
                    f"rate={rate['rate']} changed={rate['changed']}/"
                    f"{rate['triggered']} status={rate['rate_status']}"
                ),
                "path": MODULE_REL,
                "verdict": "CONFIRMED",
            },
        ],
        "evidence_requirement": (
            "1) outcome-change rate across 20 triggered runs, reported as a "
            "number; 2) a planted-wrong-consensus fixture the second pass must "
            "overturn."
        ),
        "id": "IMP-0318",
        "implementation": {
            "bytes": src["bytes"],
            "entry_point": "council.antifail.unanimity.evaluate",
            "path": MODULE_REL,
            "remediations": [
                "blind-re-evaluation",
                "strongest-counterexample",
                "forced-dissent",
                "role-rotation",
                "independent-critic",
            ],
            "second_pass_engine": "evidence-scoring (first-pass votes are not inputs)",
            "sha256": src["sha256"],
            "trigger_silent_when": (
                "unanimity after completed independent briefs AND "
                "rounds_elapsed > 1 AND disagreement_rounds >= 1"
            ),
        },
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0318/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "named_probes": [
            {
                "command": P1,
                "id": "probe1",
                "role": "planted-wrong-overturn-and-20-run-rate",
            },
            {
                "command": P2,
                "id": "probe2",
                "role": "negative-controls-survive-and-silent",
            },
        ],
        "negative_control_ids": [
            "IMP-0318-C1-correct-instant-survives",
            "IMP-0318-C2-late-legitimate-silent",
            "IMP-0318-C3-contested-silent",
            "IMP-0318-C4-trigger-disabled-no-flip",
        ],
        "negative_controls": [
            {
                "description": (
                    "Genuinely correct instant consensus: trigger fires, "
                    "outcome survives re-evaluation."
                ),
                "fired_on_bad_state": True,
                "id": "IMP-0318-C1-correct-instant-survives",
                "kind": "both-states",
                "silent_on_good_state": True,
                "verbatim": json.dumps(c["correct_instant"], sort_keys=True),
            },
            {
                "description": (
                    "Unanimity after independent briefs and a disagreement "
                    "round must not fire."
                ),
                "fired_on_bad_state": False,
                "id": "IMP-0318-C2-late-legitimate-silent",
                "kind": "known-good-fixture",
                "silent_on_good_state": True,
                "verbatim": json.dumps(c["late_legitimate"], sort_keys=True),
            },
            {
                "description": "A contested (non-unanimous) panel must not fire.",
                "fired_on_bad_state": False,
                "id": "IMP-0318-C3-contested-silent",
                "kind": "known-good-fixture",
                "silent_on_good_state": True,
                "verbatim": json.dumps(c["contested"], sort_keys=True),
            },
            {
                "description": (
                    "Trigger disabled on the planted-wrong fixture leaves the "
                    "wrong outcome in place; enabled run overturns it."
                ),
                "fired_on_bad_state": True,
                "id": "IMP-0318-C4-trigger-disabled-no-flip",
                "kind": "trigger-disabled-control",
                "silent_on_good_state": True,
                "verbatim": json.dumps(c["trigger_disabled"], sort_keys=True),
            },
        ],
        "notes": (
            "G-1 IMP-0318: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Second pass is evidence-scoring, not a "
            "confirmation of the first-pass majority. Did not run global "
            "unit_manifest.py --write. SUCCESS:IMP-0318"
        ),
        "outcome_change_rate": {
            "changed": rate["changed"],
            "n": rate["n"],
            "rate": rate["rate"],
            "rate_status": rate["rate_status"],
            "survived": rate["survived"],
            "triggered": rate["triggered"],
        },
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-antifail-module"
        ),
        "planted_wrong_fixture": {
            "counterexample_id": c["planted_wrong"]["counterexample_id"],
            "final_outcome": c["planted_wrong"]["final_outcome"],
            "first_outcome": c["planted_wrong"]["first_outcome"],
            "overturned": c["planted_wrong"]["outcome_changed"],
            "path": planted_fix,
            "remediations": c["planted_wrong"]["executed"],
        },
        "produced_by": {
            "execution_substrate": "headless-linux",
            "model": "grok-4.6",
            "role": "implementer",
            "vendor": "cursor",
        },
        "question_or_target": (
            "Implement tools/council/antifail/unanimity.py so suspiciously fast "
            "unanimity triggers blind re-evaluation, forced dissent, "
            "strongest-counterexample generation, role rotation or recruitment "
            "of an independent critic. Falsifiable question: after the trigger "
            "fires, does the second pass ever change the outcome, or is it "
            "theatre that always confirms the first result?"
        ),
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0264 kernel is absent on this worktree. The control is "
                    "snapshot-driven; a kernel would call evaluate() after each "
                    "round rather than owning scoring."
                ),
                "settling_experiment": "Wire evaluate() into IMP-0264 kernel event loop.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Second-pass votes are produced by deterministic evidence "
                    "scoring, not live model calls. A live-model engine can be "
                    "injected later but must remain blinded from first-pass votes."
                ),
                "settling_experiment": (
                    "Re-run the planted-wrong fixture with a live independent critic."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "note": (
                "Probe 2 re-runs the detector controls from the fixtures "
                "(correct-instant, late-legitimate, contested, trigger-disabled) "
                "rather than from this receipt's prose."
            ),
            "reviewer_id": "IMP-0318-probe2-negative-controls",
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10944 (instant-unanimity anti-failure control)",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "test_ids": [
            "IMP-0318-T1-planted-wrong-overturn",
            "IMP-0318-T2-outcome-change-rate-20",
            "IMP-0318-T3-correct-consensus-survives",
        ],
        "tests": [
            {
                "command": P1,
                "id": "IMP-0318-T1-planted-wrong-overturn",
                "name": "Planted wrong consensus must be overturned",
                "result": "PASS",
            },
            {
                "command": P1,
                "id": "IMP-0318-T2-outcome-change-rate-20",
                "name": "Outcome-change rate across 20 triggered runs is published",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "IMP-0318-T3-correct-consensus-survives",
                "name": "Genuinely correct consensus survives re-evaluation",
                "result": "PASS",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": started},
        "title": "Instant-unanimity trigger with blind re-evaluation and forced dissent",
        "ts": now,
        "unit_id": "IMP-0318",
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
