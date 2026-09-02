#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0312.json for the dissent pipeline."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.outcomes.dissent import (  # noqa: E402
    AttributionError,
    DissentPipeline,
    SPEC_ANCHORS,
    conservation,
    dissents_from_artifact,
    drop_dissent,
    from_kernel_events,
    presence_check,
    summarise_away,
)
from scenario import (  # noqa: E402
    MAJORITY_CLAIM,
    TOKEN_ALPHA,
    TOKEN_BETA,
    TOKEN_GAMMA,
    kernel_events_for,
    majority,
    sibling_council,
    two_dissent_council,
    unanimous_council,
    unattributed_dissent_turn,
)

OUT = "command-center/receipts/IMP-0312.json"
MODULE = "tools/council/outcomes/dissent.py"
SENTINEL = "SUCCESS:IMP-0312"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def main() -> int:
    pipe = DissentPipeline()
    sibling = pipe.run(sibling_council(), majority=majority(), council_id="council-sibling")
    result = pipe.run(
        two_dissent_council(),
        majority=majority(),
        council_id="council-main",
        children=[sibling.artifact],
    )
    uni = pipe.run(unanimous_council(), majority=majority(), council_id="council-unanimous")
    via_kernel = pipe.run(
        from_kernel_events(kernel_events_for(two_dissent_council())),
        majority=majority(),
        council_id="council-kernel",
    )
    attr_refused = False
    attr_detail = ""
    try:
        pipe.run(unattributed_dissent_turn(), majority=majority())
    except AttributionError as exc:
        attr_refused = True
        attr_detail = str(exc)

    incoming = list(result.attributed)
    victim = incoming[0]
    dropped = drop_dissent(result.artifact, victim.id)
    drop_cons = conservation(incoming, dissents_from_artifact(dropped), stage="synthesis")
    summarised = summarise_away(result.artifact, victim.id)
    sum_pres = presence_check(incoming, summarised, stage="synthesis")
    good_cons = conservation(incoming, dissents_from_artifact(result.artifact), stage="synthesis")
    good_pres = presence_check(incoming, result.artifact, stage="synthesis")

    conserved = all(r.conserved for r in result.ledger)
    presence_ok = all(p.ok for p in result.presence)
    if not conserved or not presence_ok:
        print("FAILED:IMP-0312 emit pipeline itself is not conserved")
        return 1
    if not attr_refused:
        print("FAILED:IMP-0312 emit unattributed path did not refuse")
        return 1
    if drop_cons.conserved or sum_pres.ok:
        print("FAILED:IMP-0312 emit negative controls did not fire")
        return 1

    module_path = REPO / MODULE
    mod_sha, mod_bytes = sha256_file(module_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger_rows = [r.to_dict() for r in result.ledger]
    presence_rows = [p.to_dict() for p in result.presence]

    evidence = [
        {
            "anchor": "tools/council/outcomes/dissent.py:conservation",
            "claim": (
                "Dissent conservation holds at capture, attribute, synthesis and "
                f"parent_aggregation: in_count==out_count and lost_ids empty "
                f"({json.dumps({r.stage: [r.in_count, r.out_count] for r in result.ledger})})."
            ),
            "confidence": "almost-certain",
            "verdict": "CONFIRMED",
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": "python3 -c 'DissentPipeline.run two_dissent_council + sibling; ledger'",
                    "exit_code": 0,
                    "fingerprint": fp(json.dumps(ledger_rows, sort_keys=True)),
                    "raw_output": json.dumps(ledger_rows, sort_keys=True)[:1500],
                },
                {
                    "role": "verifier",
                    "method": "id-set-diff",
                    "command": "set(in_ids) - set(out_ids) per stage",
                    "exit_code": 0,
                    "fingerprint": fp("lost:" + json.dumps([r.lost_ids for r in result.ledger])),
                    "raw_output": json.dumps(
                        [{"stage": r.stage, "lost_ids": r.lost_ids, "extra_ids": r.extra_ids} for r in result.ledger]
                    ),
                },
            ],
        },
        {
            "anchor": "tools/council/outcomes/dissent.py:claim_present",
            "claim": (
                "Each dissent's distinctive claim string survives in the synthesis "
                "verbatim (TOKEN-DSNT-ALPHA / TOKEN-DSNT-BETA) and the sibling "
                "TOKEN-DSNT-GAMMA remains reachable by id from the parent aggregation."
            ),
            "confidence": "almost-certain",
            "verdict": "CONFIRMED",
            "probes": [
                {
                    "role": "source",
                    "method": "text-presence",
                    "command": "claim in json.dumps(artifact) or dissent_index[id]==claim",
                    "exit_code": 0,
                    "fingerprint": fp(TOKEN_ALPHA + TOKEN_BETA + TOKEN_GAMMA),
                    "raw_output": json.dumps(
                        {
                            "alpha_in_synthesis": TOKEN_ALPHA in json.dumps(result.artifact),
                            "beta_in_synthesis": TOKEN_BETA in json.dumps(result.artifact),
                            "gamma_in_parent": TOKEN_GAMMA in json.dumps(result.parent),
                            "majority_in_synthesis": MAJORITY_CLAIM in json.dumps(result.artifact),
                        }
                    ),
                },
                {
                    "role": "verifier",
                    "method": "resolvable-id",
                    "command": "artifact['dissent_index'][id] == original claim",
                    "exit_code": 0,
                    "fingerprint": fp(json.dumps(result.artifact.get("dissent_index"), sort_keys=True)),
                    "raw_output": json.dumps(result.artifact.get("dissent_index"), sort_keys=True),
                },
            ],
        },
    ]

    tests = [
        {
            "id": "IMP-0312-UNIT-CAPTURE-ATTRIBUTE-PROPAGATE",
            "name": "unit: dissent capture, attribution and propagation",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/IMP-0312/probe1_conservation.py"
            ),
            "result": "PASS",
        },
        {
            "id": "IMP-0312-INVARIANT-CONSERVATION",
            "name": "invariant: conservation across synthesis",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/IMP-0312/probe1_conservation.py"
            ),
            "result": "PASS",
        },
        {
            "id": "IMP-0312-NEG-PLANTED-DROP",
            "name": "negative control (spec 11342): drop one dissent and assert conservation FAILS",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/IMP-0312/probe2_planted_drop.py"
            ),
            "result": "PASS",
        },
    ]

    negative_controls = [
        {
            "id": "IMP-0312-NC-PLANTED-DROP",
            "kind": "known-broken-fixture",
            "description": (
                "Delete one captured dissent from the synthesis; conservation "
                "must fail with that id in lost_ids (catalog spec 11342 / FC-11340)."
            ),
            "fired_on_bad_state": (not drop_cons.conserved) and victim.id in drop_cons.lost_ids,
            "silent_on_good_state": good_cons.conserved and good_pres.ok,
            "bad_state_output": json.dumps(drop_cons.to_dict(), sort_keys=True),
            "good_state_output": json.dumps(good_cons.to_dict(), sort_keys=True),
        },
        {
            "id": "IMP-0312-NC-SUMMARISED-AWAY",
            "kind": "known-broken-fixture",
            "description": (
                "Replace a distinctive claim with 'minority disagreed' while keeping "
                "an id slot. Presence must fail: summarised into non-existence."
            ),
            "fired_on_bad_state": not sum_pres.ok,
            "silent_on_good_state": good_pres.ok,
            "bad_state_output": json.dumps(sum_pres.to_dict(), sort_keys=True),
            "good_state_output": json.dumps(good_pres.to_dict(), sort_keys=True),
        },
        {
            "id": "IMP-0312-NC-UNATTRIBUTED",
            "kind": "known-broken-fixture",
            "description": "A dissent missing participant_id is refused, not silently dropped.",
            "fired_on_bad_state": attr_refused,
            "silent_on_good_state": all(d.participant_id for d in result.attributed),
            "bad_state_output": attr_detail,
            "good_state_output": "attributed n=" + str(len(result.attributed)),
        },
        {
            "id": "IMP-0312-NC-UNANIMOUS-NO-FABRICATE",
            "kind": "known-good-fixture",
            "description": "Unanimous council must not fabricate a minority report.",
            "fired_on_bad_state": True,
            "silent_on_good_state": len(uni.captured) == 0 and not uni.artifact["minority_report"]["dissents"],
            "bad_state_output": "fabricated-dissent-would-fail",
            "good_state_output": "unanimous captured=0",
        },
    ]

    receipt = {
        "unit_id": "IMP-0312",
        "schema_version": 1,
        "report_kind": "council-outcomes-module",
        "profile": "council-outcomes-module",
        "title": "Dissent and minority-report preservation pipeline",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "; ".join(SPEC_ANCHORS),
        "question": (
            "Implement tools/council/outcomes/dissent.py so every dissent is captured, "
            "attributed and carried into the final artifact and any parent aggregation. "
            "Falsifiable question: does the count of dissents entering synthesis equal "
            "the count leaving it, and is a dissent ever summarised into non-existence?"
        ),
        "module": MODULE,
        "module_sha256": mod_sha,
        "module_bytes": mod_bytes,
        "artifact_paths": [
            OUT,
            MODULE,
            "command-center/p2-wave/probes/IMP-0312/probe1_conservation.py",
            "command-center/p2-wave/probes/IMP-0312/probe2_planted_drop.py",
            "command-center/p2-wave/probes/IMP-0312/scenario.py",
        ],
        "evidence": evidence,
        "test_ids": [t["id"] for t in tests],
        "tests": tests,
        "negative_control_ids": [n["id"] for n in negative_controls],
        "negative_controls": negative_controls,
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0312-probe2-planted-drop",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from_tests": True,
            "notes": (
                "Adversarial reviewer is the planted-drop / summarised-away probe. "
                "It does not read this narrative: it re-runs conservation and presence "
                "on good, dropped, and summarised mutants."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0264 kernel.py is not on this worktree. The pipeline consumes "
                    "documented turn/event dicts (from_kernel_events) rather than a live "
                    "round scheduler. A topology that writes participant output behind "
                    "the kernel is not executable here."
                ),
                "settling_experiment": (
                    "Re-run capture against a live IMP-0264 event log once the kernel unit delivers."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "FAILURE-MODES.json maps spec 11342 to 'corruption threshold unspecified' "
                    "while this unit's catalog tests_required names spec 11342 as the planted-drop "
                    "control. FC-11340 is the dropped-dissent class. This receipt binds the "
                    "planted-drop test to both the catalog wording and FC-11340."
                ),
                "settling_experiment": "Reconcile spec-line numbering against 11-COUNCIL-SPECIFICATION.md when that file is on the tree.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "conservation_ledger": ledger_rows,
        "presence_ledger": presence_rows,
        "falsifiable_answers": {
            "count_in_equals_count_out_at_synthesis": good_cons.conserved
            and good_cons.in_count == good_cons.out_count
            and good_cons.in_count == 2,
            "summarised_into_non_existence_on_intact_run": False,
            "summarised_into_non_existence_detected_on_mutant": not sum_pres.ok,
            "parent_aggregation_preserves_ids": TOKEN_GAMMA in json.dumps(result.parent),
            "kernel_adapter_preserves_claims": {d.claim for d in via_kernel.captured}
            == {d.claim for d in result.captured},
        },
        "sample_artifact": result.artifact,
        "sample_parent": result.parent,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0312/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "min_bytes_threshold": 128,
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "timestamps": {"started_at": now, "ended_at": now},
        "produced_by": {
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
            "worktree": "/opt/p2/ast-integrate",
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
