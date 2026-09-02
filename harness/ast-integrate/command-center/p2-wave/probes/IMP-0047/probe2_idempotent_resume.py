#!/usr/bin/env python3
"""Named probe 2: idempotency census, dry-run fidelity, target cap, resume.

Independent of probe 1's round-trip. Idempotency is measured by a separate
blake2 census of apply-once vs apply-twice trees. Partial apply is journalled
and resumed without re-running already-applied steps.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.migration import (  # noqa: E402
    MigrationError,
    build_demo_tree,
    censuses,
    censuses_equal,
    demo_engine,
)

ART = REPO / "command-center/receipts/IMP-0047.json"
UNIT = "IMP-0047"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0047-p2-") as tmp:
        base = Path(tmp)
        once = build_demo_tree(base / "once")
        twice = build_demo_tree(base / "twice")
        engine = demo_engine()
        engine.migrate(once, "3", journal=base / "once.json")
        engine.migrate(twice, "3", journal=base / "twice.json")
        engine.migrate(twice, "3", journal=base / "twice.json", resume=False)
        if not censuses_equal(censuses(once), censuses(twice)):
            return fail("apply-twice tree differs from apply-once")

        dry_root = build_demo_tree(base / "dry")
        dry_journal = base / "dry-journal.json"
        dry_journal.write_text("{}\n", encoding="utf-8")
        prior = dry_journal.read_bytes()
        before = censuses(dry_root)
        dry = engine.migrate(dry_root, "3", journal=dry_journal, dry_run=True)
        if not censuses_equal(before, censuses(dry_root)):
            return fail("dry-run mutated the live tree")
        if dry_journal.read_bytes() != prior:
            return fail("dry-run wrote the caller journal")
        if not dry.get("dry_run"):
            return fail("dry-run flag missing")

        cap_engine = demo_engine()
        cap_root = build_demo_tree(base / "cap")
        cap = cap_engine.migrate(cap_root, "2", journal=base / "cap.json")
        if cap["current_version"] != "2":
            return fail(f"target 2 left version {cap['current_version']}")
        if cap_engine.by_id["s3-dispatch-hooks"].apply_calls != 0:
            return fail("step past target version executed")
        if not (cap_root / "hooks" / "old.json").is_file():
            return fail("target-2 run applied s3 delete")

        resume_engine = demo_engine()
        resume_root = build_demo_tree(base / "resume")
        resume_journal = base / "resume.json"
        partial = resume_engine.migrate(
            resume_root, "3", journal=resume_journal, kill_after="s1-relocate-key"
        )
        if partial["status"] != "in_progress":
            return fail(f"partial status={partial['status']}")
        jdoc = json.loads(resume_journal.read_text(encoding="utf-8"))
        if jdoc.get("applied_step_ids") != ["s1-relocate-key"]:
            return fail(f"journal not partial: {jdoc}")
        if resume_engine.by_id["s1-relocate-key"].apply_calls != 1:
            return fail("s1 apply_calls after partial")
        resumed = resume_engine.migrate(resume_root, "3", journal=resume_journal, resume=True)
        if resume_engine.by_id["s1-relocate-key"].apply_calls != 1:
            return fail("resume re-ran s1 (silently restarted)")
        if resumed["newly_applied_step_ids"] != ["s2-move-skill", "s3-dispatch-hooks"]:
            return fail(f"resume newly={resumed['newly_applied_step_ids']}")
        if (resume_root / "layout-version").read_text(encoding="utf-8") != "3\n":
            return fail("resume did not reach version 3")

        fail_engine = demo_engine()
        fail_root = build_demo_tree(base / "fail")
        fail_journal = base / "fail.json"
        fail_engine.migrate(fail_root, "1", journal=fail_journal)
        fail_journal.write_text(
            json.dumps(
                {
                    "schema": "imp-0047-migration-journal/v1",
                    "status": "failed",
                    "failed_step": "s2-move-skill",
                    "current_version": "1",
                    "applied_step_ids": ["s1-relocate-key"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        refused = False
        try:
            fail_engine.migrate(fail_root, "3", journal=fail_journal)
        except MigrationError as exc:
            refused = "inverted before retry" in str(exc)
        if not refused:
            return fail("failed journal allowed retry without invert")
        fail_engine.invert(fail_root, "0", journal=fail_journal)
        after_invert = fail_engine.migrate(fail_root, "3", journal=fail_journal)
        if after_invert["status"] != "complete":
            return fail("retry after invert did not complete")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        blob = json.dumps(doc)
        if "SUCCESS:IMP-0047" not in blob:
            return fail("sentinel absent")
        idem = doc.get("idempotency") or {}
        if idem.get("apply_once_equals_apply_twice") is not True:
            return fail("artifact missing idempotency proof")
        resume = doc.get("resume") or {}
        if resume.get("s1_not_rerun") is not True:
            return fail("artifact missing resume proof")

    out = {
        "probe": "probe2-idempotent-resume",
        "unit_id": UNIT,
        "idempotent": True,
        "dry_run_zero_writes": True,
        "target_version_capped": True,
        "partial_recorded": True,
        "resume_skipped_applied": True,
        "failed_retry_refused_until_invert": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"SUCCESS:{UNIT}-probe2 idempotency, dry-run, target cap, resume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
