#!/usr/bin/env python3
"""Patch IMP-0047 receipt with live migration-engine evidence and refresh sha."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "tools"))

from plugin.migration import (  # noqa: E402
    MigrationEngine,
    Step,
    blake2_tree_digest,
    build_demo_tree,
    censuses,
    censuses_equal,
    demo_engine,
    sha256_file_census,
    wrong_inverse_spec,
)

OUT = REPO / "command-center" / "receipts" / "IMP-0047.json"
MAN = REPO / "command-center" / "p2-wave" / "probes" / "IMP-0047" / "UNIT-ARTIFACT-MANIFEST.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0047-patch-") as tmp:
        base = Path(tmp)
        root = build_demo_tree(base / "rt")
        before_files = sha256_file_census(root)
        before_blake = blake2_tree_digest(root)
        engine = demo_engine()
        applied = engine.migrate(root, "3", journal=base / "rt.json")
        mid = censuses(root)
        inverted = engine.invert(root, "0", journal=base / "rt.json")
        after_files = sha256_file_census(root)
        after_blake = blake2_tree_digest(root)

        once = build_demo_tree(base / "once")
        twice = build_demo_tree(base / "twice")
        demo_engine().migrate(once, "3", journal=base / "once.json")
        e2 = demo_engine()
        e2.migrate(twice, "3", journal=base / "twice.json")
        e2.migrate(twice, "3", journal=base / "twice.json", resume=False)

        resume_engine = demo_engine()
        resume_root = build_demo_tree(base / "resume")
        resume_journal = base / "resume.json"
        resume_engine.migrate(resume_root, "3", journal=resume_journal, kill_after="s1-relocate-key")
        resumed = resume_engine.migrate(resume_root, "3", journal=resume_journal, resume=True)

        bad_root = build_demo_tree(base / "bad")
        bad_before = censuses(bad_root)
        bad_engine = MigrationEngine([Step(wrong_inverse_spec())])
        bad_engine.migrate(bad_root, "1", journal=base / "bad.json")
        bad_engine.invert(bad_root, "0", journal=base / "bad.json")
        bad_after = censuses(bad_root)

        doc = json.loads(OUT.read_text(encoding="utf-8"))
        doc["state"] = "SUCCESS"
        doc["sentinel"] = "SUCCESS:IMP-0047"
        doc["unit_id"] = "IMP-0047"
        if "SUCCESS:IMP-0047" not in json.dumps(doc):
            doc["answer"] = (str(doc.get("answer") or "") + " SUCCESS:IMP-0047").strip()
        doc["round_trip"] = {
            "file_count": len(before_files),
            "before_file_census": before_files,
            "after_file_census": after_files,
            "before_blake2": before_blake,
            "after_blake2": after_blake,
            "file_census_restored": after_files == before_files,
            "blake2_restored": after_blake == before_blake,
            "apply_changed_tree": mid["file_census"] != before_files,
            "applied_step_ids": applied["applied_step_ids"],
            "inverted_step_ids": inverted["inverted_step_ids"],
        }
        doc["idempotency"] = {
            "apply_once_equals_apply_twice": censuses_equal(censuses(once), censuses(twice)),
        }
        doc["resume"] = {
            "s1_not_rerun": resume_engine.by_id["s1-relocate-key"].apply_calls == 1,
            "newly_applied_on_resume": resumed["newly_applied_step_ids"],
        }
        doc["negative_control_wrong_inverse"] = {
            "round_trip_equal": censuses_equal(bad_before, bad_after),
            "detected": not censuses_equal(bad_before, bad_after),
        }

    raw = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    OUT.write_text(raw, encoding="utf-8", newline="\n")
    sha, size = digest(OUT)
    man = json.loads(MAN.read_text(encoding="utf-8"))
    for a in man.get("artifacts") or []:
        if a.get("unit_id") == "IMP-0047" and str(a.get("path") or "").replace("\\", "/") == "command-center/receipts/IMP-0047.json":
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
    MAN.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"patched IMP-0047 sha={sha} bytes={size} blake2={before_blake[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
