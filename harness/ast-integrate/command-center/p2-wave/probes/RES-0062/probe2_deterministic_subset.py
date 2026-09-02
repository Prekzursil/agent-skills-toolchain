#!/usr/bin/env python3
"""Probe 2: control — name the subset that CAN be replayed deterministically."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanics as m  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0062-probe2 {msg}")
    return 1


def snapshot_text(by_id: dict, sid: str) -> str:
    rec = by_id[sid]
    return (m.REPO / rec["snapshot_path"]).read_bytes().decode("utf-8", "replace")


def main() -> int:
    snap = m.verify_snapshots()
    if not snap["pass"]:
        return fail(f"snapshots bad={snap['bad']} quotes={snap['missing_quotes']}")
    by_id = snap["by_id"]
    restate = snapshot_text(by_id, "restate-sdk-python-server-context")
    if "if not run.replayed:" not in restate:
        return fail("Restate SDK missing replay skip")
    if "Schedule the run closure only if the run wasn't replayed." not in restate:
        return fail("Restate SDK missing replay-skip comment")
    dbos = snapshot_text(by_id, "dbos-transact-py-core")
    if "if recorded_step_output:" not in dbos:
        return fail("DBOS missing recorded_step_output replay")
    temporal = snapshot_text(by_id, "temporal-docs-workflows")
    if "Activities aren't executed again during replay" not in temporal:
        return fail("Temporal docs missing activity-not-replayed")

    live = m.build_record()
    graded = m.grade_artifact(live)
    if not graded["pass"]:
        return fail(f"live-grade {graded['reasons']}")
    mutant = m.mutant_llm_as_subset(live)
    bad = m.grade_artifact(mutant)
    if bad["pass"]:
        return fail("LLM-as-subset mutant was silent")
    if "subset-id-missing" not in bad["reasons"]:
        return fail(f"mutant reasons {bad['reasons']}")

    art_path = m.REPO / m.ART_REL
    if not art_path.is_file():
        return fail("artifact missing")
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    art_grade = m.grade_artifact(doc)
    if not art_grade["pass"]:
        return fail(f"artifact-grade {art_grade['reasons']}")
    ds = doc["answer"]["deterministic_subset"]
    if ds.get("id") != m.SUBSET_ID:
        return fail("artifact subset id")
    includes = set(map(str, ds.get("includes") or []))
    excludes = set(map(str, ds.get("excludes") or []))
    if not m.NEED_INCLUDES.issubset(includes):
        return fail("artifact subset includes")
    if not m.NEED_EXCLUDES.issubset(excludes):
        return fail("artifact subset excludes")
    if "LLM token sampling" not in excludes:
        return fail("LLM sampling not excluded from subset")
    if doc["answer"].get("rejects_partial_replay_conclusion") is not True:
        return fail("artifact did not reject partial-replay hedge")
    claims = {c["id"]: c for c in doc["claims"]}
    subset_claim = claims["C-DETERMINISTIC-SUBSET"]
    if subset_claim.get("evidence_tier") not in {"E1", "E2"}:
        return fail(f"subset claim tier {subset_claim.get('evidence_tier')}")
    kinds = {r["kind"] for r in subset_claim["rails"]}
    if "prose" not in kinds or "api" not in kinds:
        return fail(f"subset rails not dual-kind {kinds}")
    report = {
        "probe": "probe2-deterministic-subset",
        "unit_id": m.UNIT,
        "subset_id": m.SUBSET_ID,
        "restate_replay_skip": True,
        "dbos_checkpoint_replay": True,
        "temporal_activity_not_replayed": True,
        "mutant_reasons": bad["reasons"],
        "live_pass": True,
        "artifact_pass": True,
        "subset_tier": subset_claim.get("evidence_tier"),
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:RES-0062-probe2 deterministic subset named and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
