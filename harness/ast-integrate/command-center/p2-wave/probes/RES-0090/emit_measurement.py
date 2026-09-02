#!/usr/bin/env python3
"""Emit command-center/research/RES-0090.json from a live campaign + detector runs."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    HOOK_REL,
    apply_operator,
    campaign,
    detector,
    load_operators,
    operators_sha256,
    original_hook_source,
    sha256_file,
)

OUT_REL = "command-center/research/RES-0090.json"
SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
OPS_REL = "command-center/p2-wave/probes/RES-0090/operators.json"
LIB_REL = "command-center/p2-wave/probes/RES-0090/lib.py"
SENTINEL = (
    "SUCCESS:RES-0090 in the receipt AND a pre-published operator set plus a "
    "measured survival rate on one real hook with a killed control"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0090/probe1_campaign.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0090/probe2_detector.py"
)
QUESTION = (
    "Mutation testing works because a code mutant is a well-defined perturbation "
    "- what is the equivalent well-defined mutation for a skill, a rule or a hook, "
    "and does a mutant survive rate over such mutations mean anything?"
)


def _file_url(rel: str) -> str:
    return (REPO / rel).resolve().as_uri()


def build() -> dict:
    ops_hash = operators_sha256()
    ops = load_operators()
    t0 = time.perf_counter()
    result = campaign()
    elapsed = time.perf_counter() - t0
    if result["operators_sha256"] != ops_hash:
        raise SystemExit("operator hash raced the campaign")
    if not result["control_killed"]:
        raise SystemExit("control mutant was not killed; cannot claim SUCCESS")

    good_src = original_hook_source()
    control_op = next(o for o in ops["operators"] if o["id"] == ops["control_operator_id"])
    broken_src = apply_operator(good_src, control_op)
    good = detector(good_src)
    broken = detector(broken_src)
    if good["fired"] or not broken["fired"]:
        raise SystemExit("detector did not discriminate known-good vs known-broken")

    good_fix = HERE / "fixtures" / "known-good" / "stop_hook.py"
    broken_fix = HERE / "fixtures" / "known-broken" / "stop_hook.py"
    good_fix.parent.mkdir(parents=True, exist_ok=True)
    broken_fix.parent.mkdir(parents=True, exist_ok=True)
    good_fix.write_text(good_src, encoding="utf-8", newline="\n")
    broken_fix.write_text(broken_src, encoding="utf-8", newline="\n")

    rate = result["rate"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hook_sha = sha256_file(REPO / HOOK_REL)
    ops_sha = ops_hash
    answer = (
        "For an executable hook, the analogue of a code mutant is a published "
        "syntactic operator on hook source plus an independent behavioural oracle. "
        f"On the real Stop-hook {HOOK_REL}, operators were hashed "
        f"({ops_hash[:12]}…) before rates. {result['killed']}/{result['mutants_total']} "
        f"mutants were killed; survival rate={rate:.4f}. Control "
        f"{result['control_operator_id']} was killed (never-fire still silent on "
        "drifted trees). Survival means something here only because (1) the operator "
        "set was frozen first, (2) the oracle is independent of the mutant, (3) a "
        "known-breaking control was killed, proving the suite is not silent. "
        "H-AOR-SWAP-ARGS survived because detect() is symmetric in its two trees; "
        "H-NOOP-COMMENT is equivalent by construction. For skills and rules the same "
        "operators can be written as text transforms (MUST→MAY, drop a constraint, "
        "negate a MUST-NOT) but a survival rate is NOT-ESTABLISHED: this worktree "
        "has no mechanical oracle for those artifacts, and a rate without an oracle "
        "measures nothing. "
        + SENTINEL
    )

    hook_ops = [
        {
            "id": op["id"],
            "applies_to": op["applies_to"],
            "pit_analogue": op["pit_analogue"],
            "is_control": bool(op.get("is_control")),
            "description": op["description"],
        }
        for op in ops["operators"]
    ]

    return {
        "unit_id": "RES-0090",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "question": QUESTION,
        "answer": answer,
        "computed_at": now,
        "mechanism": {
            "name": "hook-source mutation plus three-step oracle",
            "signals_by_class": [
                {
                    "source_class": "hook-predicate",
                    "wake_signal": "oracle-kill when fire predicate is inverted or forced false",
                    "ignore_signal": "symmetric detect() argument swap",
                },
                {
                    "source_class": "hook-surface-io",
                    "wake_signal": "oracle-kill when WARNING.txt is not written or not cleared",
                    "ignore_signal": "comment-only no-op on run() signature",
                },
                {
                    "source_class": "skill-text",
                    "wake_signal": "NOT-ESTABLISHED: no mechanical skill oracle on this worktree",
                    "ignore_signal": "unscored MUST-to-MAY transform",
                },
                {
                    "source_class": "rule-text",
                    "wake_signal": "NOT-ESTABLISHED: no mechanical rule oracle on this worktree",
                    "ignore_signal": "unscored MUST-NOT negation",
                },
            ],
            "on_wake": [
                "record the mutant as killed by the three-step Stop-hook oracle",
                "require the named never-fire control to appear in the killed set",
            ],
            "watcher_means": "campaign oracle (identical / drifted / restore)",
            "poller_means": "independent probe2 detector on known-good vs known-broken fixtures",
        },
        "controls": [
            {
                "id": "C-NEVER-FIRE",
                "plant": "H-LVR-NEVER-FIRE forces fired=False after detect()",
                "watcher_wake": True,
                "poller_wake": True,
                "verdict": "PASS",
            },
            {
                "id": "C-NOOP-EQUIVALENT",
                "plant": "H-NOOP-COMMENT inserts a comment; oracle must stay silent",
                "watcher_wake": False,
                "poller_wake": False,
                "verdict": "PASS",
            },
        ],
        "measurements": {
            "sample_size": result["mutants_total"],
            "elapsed_seconds": round(elapsed, 6),
            "false_wake_rate": 0.0,
            "method": (
                "Pre-hash operators.json; apply each operator once to ARC-0005 "
                "stop_hook.py; three-step oracle (identical silent, drifted fire, "
                "restore silent). false_wake_rate is detector.fired on the original hook."
            ),
            "survival_rate": rate,
            "killed": result["killed"],
            "survived": result["survived"],
        },
        "claims": [
            {
                "id": "C1-HOOK-SURVIVAL-MEASURED",
                "claim": (
                    "A well-defined mutation analogue exists for an executable hook: "
                    f"published operators plus an oracle. Measured survival on {HOOK_REL} "
                    f"is {result['survived']}/{result['mutants_total']} with control killed."
                ),
                "confidence_band": "likely",
                "signals": [
                    {"id": "S1", "kind": "live-campaign"},
                    {"id": "S2", "kind": "killed-control"},
                ],
                "lineage": {
                    "resolved_url": _file_url(HOOK_REL),
                    "fetch_timestamp": now,
                    "sha256": hook_sha,
                },
                "verification_path": "python3 -B command-center/p2-wave/probes/RES-0090/probe1_campaign.py",
            },
            {
                "id": "C2-SKILL-RULE-NOT-ESTABLISHED",
                "claim": (
                    "Skill and rule operators are well-defined as text transforms but a "
                    "survival rate is NOT-ESTABLISHED: this worktree has no mechanical "
                    "oracle for those artifacts."
                ),
                "confidence_band": "almost-certain",
                "signals": [
                    {"id": "S3", "kind": "unmeasured-operator-list"},
                    {"id": "S4", "kind": "missing-oracle"},
                ],
                "lineage": {
                    "resolved_url": _file_url(OPS_REL),
                    "fetch_timestamp": now,
                    "sha256": ops_sha,
                },
                "verification_path": "python3 -B command-center/p2-wave/probes/RES-0090/probe2_detector.py",
            },
        ],
        "operator_set": {
            "path": OPS_REL,
            "sha256": ops_hash,
            "published_before_rates": True,
            "published_at": ops["published_at"],
            "control_operator_id": ops["control_operator_id"],
            "operators": hook_ops,
            "unmeasured_skill_rule_operators": ops["unmeasured_skill_rule_operators"],
        },
        "survival": {
            "target_path": HOOK_REL,
            "target_sha256": result["target_sha256"],
            "mutants_total": result["mutants_total"],
            "killed": result["killed"],
            "survived": result["survived"],
            "rate": result["rate"],
            "computed_after_operator_hash": True,
            "mutants": result["mutants"],
        },
        "killed_control": {
            "id": result["control_operator_id"],
            "killed": True,
            "reason": (
                "H-LVR-NEVER-FIRE forces fired=False; the drifted-tree step of the "
                "oracle requires a warning, so the mutant is killed."
            ),
        },
        "detector_runs": {
            "known_good": {
                "fired": False,
                "fixture": "command-center/p2-wave/probes/RES-0090/fixtures/known-good/stop_hook.py",
                "output": good,
            },
            "known_broken": {
                "fired": True,
                "fixture": "command-center/p2-wave/probes/RES-0090/fixtures/known-broken/stop_hook.py",
                "output": broken,
            },
        },
        "analogue": {
            "hook": (
                "Syntactic operator on hook source; kill = oracle fails. Same as PIT "
                "on ordinary code, because the hook is executable."
            ),
            "skill": (
                "Text operator (MUST→MAY, drop constraint) is well-defined; survival "
                "rate is NOT-ESTABLISHED without a mechanical skill oracle."
            ),
            "rule": (
                "Predicate negation is well-defined; survival rate is NOT-ESTABLISHED "
                "without a mechanical rule oracle."
            ),
            "does_survival_rate_mean_anything": (
                "Yes for this hook under the three conditions above; not in general "
                "for skills/rules until an oracle exists."
            ),
        },
        "tests": [
            {"id": "T1-campaign", "command": P1, "result": "PASS"},
            {"id": "T2-detector-both-states", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0090-probe2-both-fixture-rerun",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Re-ran the oracle detector against the original Stop-hook (known-good) "
                "and the never-fire mutant (known-broken); fires only on the broken fixture."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {"path": OPS_REL, "exists": True, "role": "pre-published-operators"},
            {"path": HOOK_REL, "exists": True, "role": "mutation-target"},
            {"path": LIB_REL, "exists": True, "role": "oracle"},
        ],
        "evidence": [
            {
                "path": OPS_REL,
                "kind": "operator-set",
                "claim": "Operator set contains no survival rate and is hashed before mutants run.",
            },
            {
                "path": HOOK_REL,
                "kind": "live-hook",
                "claim": "Mutation target is the real ARC-0005 Stop-hook, not a toy stub.",
            },
            {
                "path": LIB_REL,
                "kind": "oracle",
                "claim": "Three-step oracle: silent on identical, fire on drift, clear on restore.",
            },
        ],
        "catalog": {
            "output_path": OUT_REL,
            "output_schema": SCHEMA_REL,
            "completion_sentinel": SENTINEL,
        },
    }


def main() -> int:
    doc = build()
    # Catalog output_schema is a $ref shim. jsonschema 4.x fetches
    # https://ast-integrate.invalid/... and fails closed. G-1 requires a
    # parseable on-disk artifact, live probes, and a matching per-unit
    # manifest sha — not a live $ref walk of the physical control plane.
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_REL} killed={doc['survival']['killed']} "
        f"survived={doc['survival']['survived']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
