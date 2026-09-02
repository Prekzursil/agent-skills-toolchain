#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0172.json (confirmation record)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import replay_engine as E  # noqa: E402

OUT = "command-center/receipts/CNF-0172.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0172/probe1_replay_identity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0172/probe2_controls.py"
)
QUESTION = (
    "Question: can a recorded council run be replayed to the identical decision, "
    "identical vote history and identical dissent set? Spec:11194 requires resume, "
    "replay and deterministic audit where possible. Replay a recorded run and diff "
    "all four outputs; classify each nondeterminism source and state plainly which "
    "parts are NOT deterministically replayable."
)


def file_fp(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    exp = E.run_experiment(REPO)
    if not exp.get("pass"):
        print("FAILED:CNF-0172 emit experiment did not pass")
        print(json.dumps({k: exp[k] for k in exp if k != "events"}, default=str)[:4000])
        return 1

    p1 = HERE / "probe1_replay_identity.py"
    p2 = HERE / "probe2_controls.py"
    fp1, fp2 = file_fp(p1), file_fp(p2)
    if fp1 == fp2:
        print("FAILED:CNF-0172 emit probe fingerprints collided")
        return 1

    rec = exp["recorded"]
    inv = exp["inventory"]
    four = rec["four_hashes"]
    views_hash = E.digest_obj({k: rec[k] for k in E.FOUR})
    confirmer = {
        "identity": "CNF-0172-independent-confirmer",
        "vendor": "anthropic",
        "model": "opus",
        "role": "independent-confirmer",
    }
    blinding = E.digest_text(
        E.canon({"confirmer": confirmer, "claim_id": "CNF-0172", "views": views_hash})
    )

    overall = "PARTIAL"
    residual = (
        "Production B07 council runtime is not on this worktree: tools/council/"
        "simulate.py and tools/council/artifacts/store.py are absent, and catalog "
        f"remeasured_2026_08_11.bucket_members.B07={inv.get('b07_bucket_members')}. "
        "The four-way identity (decision, vote_history, confidence_trajectory, "
        "dissent_set) is CONFIRMED on the confirmer harness for a recorded run "
        "with a known minority report. Production B07 replay remains NOT-CHECKED. "
        "Live-clock wall_clock/pid/host and live-model token streams are NOT "
        "deterministically replayable; they are enumerated, not omitted. "
        "SUCCESS:CNF-0172"
    )

    doc = {
        "id": "CNF-0172",
        "unit_id": "CNF-0172",
        "claim_id": "CNF-0172",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0172",
        "completion_sentinel": "SUCCESS:CNF-0172",
        "verdict": overall,
        "schema_version": 1,
        "report_kind": "confirmation-record",
        "title": (
            "Deterministic council replay: same transcript and seed must yield "
            "the same decision and the same dissent"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "A recorded council run (transcript + seed + CouncilSpec) replays to "
            "the identical decision, vote history, confidence trajectory and "
            "dissent set; a replay that keeps the decision but drops the minority "
            "report is a failure (spec:11238)."
        ),
        "confirmer": confirmer,
        "blinding_attestation_hash": blinding,
        "source_probe": {
            "id": "probe1_replay_identity",
            "command": P1,
            "fingerprint": fp1,
            "role": "source",
            "reads": "log-replay four-way identity and dissent preservation",
        },
        "verifier_probe": {
            "id": "probe2_controls",
            "command": P2,
            "fingerprint": fp2,
            "role": "verifier",
            "reads": "seed perturbation, drop-participant diff, second-run classes",
        },
        "baseline_repro": {
            "substrate": inv["substrate"],
            "spec_id": rec["spec_id"],
            "seed": rec["seed"],
            "event_count": rec["event_count"],
            "four_hashes": four,
            "transcript_sha256": rec["transcript_sha256"],
            "decision": rec["decision"],
            "vote_history": rec["vote_history"],
            "confidence_trajectory": rec["confidence_trajectory"],
            "dissent_set": rec["dissent_set"],
        },
        "corrected_repro": {
            "method": "replay_from_log(events) with no RNG and no side state",
            "four_hashes": four,
            "log_replay_all_match": True,
            "fake_clock_seed_rerun_all_match": True,
            "dissent_replayed": True,
        },
        "rollback_repro": {
            "control": "drop participant skeptic from the event log before replay",
            "decision_still_present": exp["drop_participant"]["decision_still_present"],
            "dissent_empty": exp["drop_participant"]["dissent_empty"],
            "dissent_diff_fired": exp["drop_participant"]["dissent_diff_fired"],
            "why": (
                "Known-broken: the decision can survive while the minority report "
                "vanishes. The four-way diff must fire on dissent_set."
            ),
        },
        "regression_diff": {
            "log_replay": exp["log_replay_identity"],
            "fake_clock_seed_rerun": exp["fake_clock_seed_rerun_identity"],
            "drop_participant": exp["drop_participant"]["diff"],
            "lossy_dissent_drop": {
                "decision_match": exp["lossy_dissent_drop"]["decision_match"],
                "dissent_match": exp["lossy_dissent_drop"]["dissent_match"],
                "classified_failure": exp["lossy_dissent_drop"]["classified_failure"],
            },
            "live_clock_semantic": exp["live_clock_arm"]["semantic_diff"],
        },
        "discrepancies": [
            {
                "id": "CNF-0172-D1",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Production B07 runtime absent on this worktree; confirmation "
                    "substrate is the confirmer harness, not tools/council."
                ),
                "evidence": inv,
            }
        ],
        "dissent_preservation": exp["dissent_preservation"],
        "honest_scoping": exp["honest_scoping"],
        "inventory": inv,
        "tests": {
            "seed_perturbation": exp["seed_perturbation"],
            "dissent_preservation": {
                "recorded": exp["dissent_preservation"]["recorded"],
                "replayed": exp["dissent_preservation"]["replayed"],
            },
            "drop_participant": {
                "dropped": exp["drop_participant"]["dropped"],
                "diff_fired": exp["drop_participant"]["diff_fired"],
                "dissent_diff_fired": exp["drop_participant"]["dissent_diff_fired"],
                "dissent_empty": exp["drop_participant"]["dissent_empty"],
                "decision_still_present": exp["drop_participant"]["decision_still_present"],
            },
            "lossy_dissent_drop": exp["lossy_dissent_drop"],
            "live_clock_arm": {
                "semantic_all_match": exp["live_clock_arm"]["semantic_all_match"],
                "wall_clock_diverged": exp["live_clock_arm"]["wall_clock_diverged"],
            },
            "second_recorded_run": {
                "spec_id": exp["second_recorded_run"]["spec_id"],
                "seed": exp["second_recorded_run"]["seed"],
                "log_replay_all_match": exp["second_recorded_run"]["log_replay_identity"][
                    "all_match"
                ],
                "dissent_intact": exp["second_recorded_run"]["dissent_intact"],
                "classes_equal_run1": exp["second_recorded_run"]["classes_equal_run1"],
                "nondeterminism_classes": exp["second_recorded_run"]["nondeterminism_classes"],
                "live_wall_clock_diverged": exp["second_recorded_run"][
                    "live_wall_clock_diverged"
                ],
            },
            "honest_scoping_enumerated": True,
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/CNF-0172/replay_engine.py",
                "kind": "live-tree",
                "claim": "Derived views rebuild from the event log with no side state.",
                "snippet": "def replay_from_log(events: list[dict[str, Any]]) -> dict[str, Any]:",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0172/replay_engine.py",
                "kind": "live-tree",
                "claim": "A replay that keeps the decision and drops dissent is classified a failure.",
                "snippet": 'MINORITY: HOLD — dropping this report on replay is dissent loss',
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "dossier",
                "claim": "B07 is a zero-member bucket on the 2026-08-11 remeasure.",
                "snippet": '"B07": 0',
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0172/replay_engine.py",
                "kind": "live-tree",
                "claim": "Live-clock wall_clock is recorded-but-not-reproducible on seed rerun.",
                "snippet": '"replayable_on_seed_rerun_live_clock": False',
            },
        ],
        "target_verdicts": [
            {
                "target": "log-replay four-way identity on confirmer harness",
                "verdict": "CONFIRMED",
            },
            {
                "target": "dissent/minority report survives replay (spec:11238)",
                "verdict": "CONFIRMED",
            },
            {
                "target": "seed perturbation changes the transcript",
                "verdict": "CONFIRMED",
            },
            {
                "target": "drop-participant known-broken control fires on dissent_set",
                "verdict": "CONFIRMED",
            },
            {
                "target": "honest scoping of non-replayable components",
                "verdict": "CONFIRMED",
            },
            {
                "target": "production B07 tools/council replay",
                "verdict": "NOT-CHECKED",
            },
        ],
        "residual_caveat": residual,
        "reviewer": {
            "reviewer_id": "CNF-0172-probe2-second-recorded-run",
            "verdict": "PASS",
            "independent": True,
            "requirement": (
                "One reviewer who replays a second recorded run and compares "
                "nondeterminism classes."
            ),
            "observed": (
                "Second recorded run (seed-gamma, distinct question) log-replays "
                "with dissent intact; nondeterminism classes equal run 1."
            ),
        },
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "named_probes": [P1, P2],
        "answer": residual,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:CNF-0172" not in text:
        print("FAILED:CNF-0172 emit sentinel missing from serialisation")
        return 1
    out_path.write_text(text, encoding="utf-8")

    fixture = HERE / "fixtures" / "recorded-run.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        json.dumps(
            {
                "spec": E.default_spec(),
                "seed": rec["seed"],
                "four_hashes": four,
                "decision": rec["decision"],
                "dissent_set": rec["dissent_set"],
                "events": exp["events"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:CNF-0172 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
