#!/usr/bin/env python3
"""Named probe 1: kill-at-40% then resume equals a clean run by artifact hash.

Signal 1: hash-set equality of final artifacts (path, sha256) between the
killed-and-resumed workdir and an uninterrupted clean run.
Signal 2: the resumed invocation's dispatch count is strictly less than the
clean run's (proven units are not re-dispatched).
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.resume import (  # noqa: E402
    KillAtFraction,
    ResumableRunner,
    artifact_index,
    hash_set,
    load_checkpoint,
)
from scenario import UNIT_IDS, kill_after_units, workflow  # noqa: E402


def run_clean(root: Path) -> dict:
    runner = ResumableRunner(root)
    return runner.run(workflow(), run_id="clean")


def run_killed_then_resume(root: Path) -> dict:
    wf = workflow()
    stop = kill_after_units(len(wf.units))
    first = ResumableRunner(root)
    try:
        first.run(wf, run_id="killed", stop_after_units=stop)
    except KillAtFraction as exc:
        killed_dispatched = exc.dispatched
    else:
        raise AssertionError("kill point was not reached")
    ckpt = load_checkpoint(root / "RESUME-CHECKPOINT.json")
    resume = ResumableRunner(root)
    result = resume.run(wf, run_id="resume")
    result["killed_dispatched"] = killed_dispatched
    result["kill_checkpoint"] = ckpt
    return result


def main() -> int:
    stop = kill_after_units()
    tmp = Path(tempfile.mkdtemp(prefix="imp0145-probe1-"))
    try:
        clean_dir = tmp / "clean"
        resume_dir = tmp / "killed-resume"
        clean = run_clean(clean_dir)
        resumed = run_killed_then_resume(resume_dir)
        clean_hashes = hash_set(artifact_index(clean_dir))
        resume_hashes = hash_set(artifact_index(resume_dir))
        ckpt = resumed["kill_checkpoint"]
        schema_ok = True
        schema_error = ""
        try:
            import jsonschema

            schema = json.loads(
                (HERE / "checkpoint.schema.json").read_text(encoding="utf-8")
            )
            jsonschema.Draft202012Validator(schema).validate(ckpt)
        except Exception as exc:  # schema miss or jsonschema absent is a fail
            schema_ok = False
            schema_error = f"{type(exc).__name__}:{exc}"
        payload = {
            "probe": "probe1-kill-resume",
            "unit_id": "IMP-0145",
            "workflow_units": len(UNIT_IDS),
            "kill_after_units": stop,
            "kill_fraction": 0.4,
            "clean_dispatch_count": clean["dispatch_count"],
            "killed_dispatch_count": resumed["killed_dispatched"],
            "resume_dispatch_count": resumed["dispatch_count"],
            "resume_dispatch_log": resumed["dispatch_log"],
            "clean_artifact_count": len(clean_hashes),
            "resume_artifact_count": len(resume_hashes),
            "hash_set_equal": clean_hashes == resume_hashes,
            "resume_dispatch_strictly_less": (
                resumed["dispatch_count"] < clean["dispatch_count"]
            ),
            "checkpoint_completed_at_kill": list(ckpt.get("completed_unit_ids") or []),
            "checkpoint_open_nodes_at_kill": len(ckpt.get("open_nodes") or []),
            "param_bindings_frozen": ckpt.get("param_bindings"),
            "checkpoint_schema_ok": schema_ok,
            "pass": False,
        }
        errors: list[str] = []
        if not schema_ok:
            errors.append(f"checkpoint-schema:{schema_error}")
        if clean["dispatch_count"] != len(UNIT_IDS):
            errors.append("clean-did-not-dispatch-all")
        if resumed["killed_dispatched"] != stop:
            errors.append("kill-count-mismatch")
        if len(ckpt.get("completed_unit_ids") or []) != stop:
            errors.append("checkpoint-completed-count")
        if len(ckpt.get("open_nodes") or []) != len(UNIT_IDS) - stop:
            errors.append("checkpoint-open-count")
        if clean_hashes != resume_hashes:
            errors.append("hash-set-mismatch")
        if not (resumed["dispatch_count"] < clean["dispatch_count"]):
            errors.append("resume-dispatch-not-strictly-less")
        if resumed["dispatch_count"] != len(UNIT_IDS) - stop:
            errors.append("resume-should-dispatch-remainder-only")
        payload["errors"] = errors
        payload["pass"] = not errors
        print(json.dumps(payload, sort_keys=True))
        if errors:
            print("FAILED:IMP-0145-probe1", ",".join(errors))
            return 1
        print(
            f"hash_set_equal=True clean={clean['dispatch_count']} "
            f"resume={resumed['dispatch_count']} kill_at={stop}"
        )
        print("SUCCESS:IMP-0145-probe1 kill-at-40%-then-resume hash-set equality")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
