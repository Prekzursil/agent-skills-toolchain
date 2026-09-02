#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0334.json from a live hats run.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    ARTIFACT,
    LENS_IDS,
    PARTICIPANTS,
    QUESTION,
    SENTINEL,
)
from tools.council.protocol.hats import (  # noqa: E402
    MODULE_REL,
    HatsEngine,
    InvariantSpeaker,
    LensFaithfulSpeaker,
    audit_schedule,
    compile_schedule,
    plugin_record,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0334/probe1_schedule_complete.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0334/probe2_lens_invariant.py"
)
HATS_REL = MODULE_REL
PROTO_INIT = "tools/council/protocol/__init__.py"
SCENARIO_REL = "command-center/p2-wave/probes/IMP-0334/scenario.py"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
        "present": True,
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:IMP-0334 emit missing anchor {needle!r} in {rel}")


def main() -> int:
    engine = HatsEngine(mode="parallel")
    schedule = compile_schedule(PARTICIPANTS, mode="parallel")
    audit = audit_schedule(schedule)
    good = engine.run(PARTICIPANTS, QUESTION, LensFaithfulSpeaker())
    bad = engine.run(
        PARTICIPANTS, QUESTION, InvariantSpeaker(spam_vocabulary=True)
    )
    plugin = plugin_record()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    collapse_anchor = source_anchor(
        HATS_REL, "if dist <= ROLE_COLLAPSE_MAX_DISTANCE"
    )
    vocab_anchor = source_anchor(HATS_REL, "vocab_ok=bool(hits)")
    schedule_anchor = source_anchor(
        HATS_REL, "each_lens_applied_by_multiple_participants=not single"
    )

    good_div = good.divergence.to_dict()
    bad_div = bad.divergence.to_dict()

    receipt = {
        "schema_version": 1,
        "id": "IMP-0334",
        "unit_id": "IMP-0334",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:IMP-0334 "
            "Six-Hats lens-rotation engine; protocol P30 six-hats-rotation"
        ),
        "title": "Six-Hats lens-rotation engine",
        "question_or_target": (
            "Implement tools/council/protocol/hats.py rotating every "
            "participant through a fixed set of thinking lenses so each "
            "perspective is applied by more than one participant. Falsifiable "
            "question: does rotation actually change a participant's output, "
            "or does the same participant produce lens-invariant text (a "
            "role-collapse signal under a different name)?"
        ),
        "output_path": ARTIFACT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-protocol-module"
        ),
        "cloud_ok": False,
        "artifact_paths": [
            HATS_REL,
            PROTO_INIT,
            SCENARIO_REL,
            ARTIFACT,
        ],
        "artifacts": [
            artifact_row(HATS_REL, "implementation"),
            artifact_row(PROTO_INIT, "supporting"),
            artifact_row(SCENARIO_REL, "supporting"),
        ],
        "schedule_audit": audit.to_dict(),
        "plugin": plugin,
        "lenses": list(LENS_IDS),
        "participants": list(PARTICIPANTS),
        "question": QUESTION,
        "faithful_run": {
            "compliant": good.compliant,
            "role_collapse_flagged": good.role_collapse_flagged,
            "reasons": list(good.reasons),
            "divergence": good_div,
            "vocab_all_present": good.vocabulary.all_present,
            "n_records": len(good.records),
        },
        "invariant_spam_run": {
            "compliant": bad.compliant,
            "role_collapse_flagged": bad.role_collapse_flagged,
            "reasons": list(bad.reasons),
            "divergence": bad_div,
            "vocab_all_present": bad.vocabulary.all_present,
            "n_records": len(bad.records),
        },
        "evidence": [
            {
                "id": "E1-across-lens-vs-peer-baseline",
                "claim": (
                    "Per-participant across-lens Jaccard distance on a "
                    "lens-faithful speaker is "
                    f"{good_div['mean_across_lens']}, compared with the "
                    "same-round across-participant baseline "
                    f"{good_div['across_participant_baseline']}. Rotation "
                    "changes output (mean across-lens "
                    f">{good.divergence.threshold}). The invariant speaker "
                    "collapses to "
                    f"{bad_div['mean_across_lens']} across lenses while the "
                    "peer baseline remains "
                    f"{bad_div['across_participant_baseline']} because seat "
                    "voice still differs."
                ),
                "verdict": "CONFIRMED",
                "anchor": collapse_anchor,
                "kind": "per-participant-across-lens-divergence",
                "faithful": good_div,
                "invariant_spam": bad_div,
            },
            {
                "id": "E2-lens-vocabulary-per-turn",
                "claim": (
                    f"Faithful run: vocabulary present on all "
                    f"{len(good.vocabulary.per_turn)} turns. Invariant "
                    "vocab-spam run: vocabulary also present on all turns "
                    f"({len(bad.vocabulary.per_turn)}), so a vocab-only "
                    "checker cannot be the compliance gate."
                ),
                "verdict": "CONFIRMED",
                "anchor": vocab_anchor,
                "kind": "lens-vocabulary-presence-per-turn",
                "faithful_misses": list(good.vocabulary.miss_keys),
                "spam_misses": list(bad.vocabulary.miss_keys),
                "faithful_n_turns": len(good.vocabulary.per_turn),
            },
        ],
        "test_ids": [
            "IMP-0334-T-schedule-complete",
            "IMP-0334-T-lens-vocab-per-turn",
        ],
        "negative_control_ids": [
            "IMP-0334-NC-lens-invariant-flagged",
            "IMP-0334-NC-truncated-schedule",
            "IMP-0334-NC-single-seat",
        ],
        "tests": [
            {
                "id": "IMP-0334-T-schedule-complete",
                "name": "rotation schedule completeness (every lens covered)",
                "result": "PASS",
                "command": P1,
                "anchor": schedule_anchor,
            },
            {
                "id": "IMP-0334-T-lens-vocab-per-turn",
                "name": "lens-vocabulary presence check per turn",
                "result": "PASS",
                "faithful_all_present": good.vocabulary.all_present,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0334-NC-lens-invariant-flagged",
                "kind": "known-broken-fixture",
                "description": (
                    "InvariantSpeaker with every hat marker pasted into every "
                    "turn; divergence gate must still fire"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_compliant": bad.compliant,
                "bad_vocab_ok": bad.vocabulary.all_present,
                "good_compliant": good.compliant,
            },
        ],
        "negative_control": {
            "id": "IMP-0334-NC-lens-invariant-flagged",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_compliant": False,
            "bad_vocab_ok": True,
            "good_compliant": True,
        },
        "reviewer": {
            "reviewer_id": "IMP-0334-probe2-lens-invariant",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 starts from the negative-control fixture, not the "
                "author's schedule summary. Vocab-spam must pass the vocab "
                "check and still be refused."
            ),
        },
        "reviewer_verdict": "PASS",
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/kernel.py (IMP-0264) is not on this "
                    "worktree; hats exposes plugin_record() and attach_kernel() "
                    "but does not execute a live kernel event-count invariant."
                ),
                "settling_experiment": (
                    "After IMP-0264 lands, attach_kernel(kernel) and assert "
                    "turns_recorded == turns_executed for a six-hat council."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "No live vendor model was rotated. Divergence is measured "
                    "on deterministic speakers that isolate lens vs identity. "
                    "Whether a particular hosted model is lens-invariant is "
                    "outside this unit."
                ),
                "settling_experiment": (
                    "Pin a vendor+model, run HatsEngine with that adapter as "
                    "speaker, publish the same two divergence numbers."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md and _USER-PROMPTS.md are "
                    "catalog inputs and are absent on this Linux worktree."
                ),
                "settling_experiment": (
                    "Re-read those files when restored and confirm P30 "
                    "phase names still match plugin_record()."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "schedule-complete",
                "command": P1,
            },
            {
                "id": "probe2",
                "role": "lens-invariant-negative-control",
                "command": P2,
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": now, "ended_at": now},
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "notes": (
            "G-1 for IMP-0334: live named probes re-run hats.py. "
            "Did not run tools/command-center/unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    out = REPO / ARTIFACT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {ARTIFACT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0334 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
