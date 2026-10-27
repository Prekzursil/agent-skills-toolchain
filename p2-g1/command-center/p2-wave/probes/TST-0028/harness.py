#!/usr/bin/env python3
"""TST-0028 differential replay harness: record, replay, diff.

Materialises four side-by-side copies of the subject into a temp dir:
  build-a          record (live machine)
  build-b          identical replay (offline, frozen clock, no credentials)
  build-c-planted  replay with PLAN_MARKER behaviour planted
  build-d-comment  replay with a comment-only source edit (must not fire)
Diffs are semantic: artifact_set (file -> sha256) and decision_trace.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBJECT = HERE / "subject" / "workflow.py"
PLAN_MARKER_RECORD = "accept-v1"
PLAN_MARKER_PLANTED = "accept-v2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialise(parent: Path, name: str, plan_marker: str,
                comment_edit: bool = False) -> Path:
    build = parent / name
    build.mkdir(parents=True)
    (build / "inputs.txt").write_text(
        "alpha\nbeta\ngamma\n", encoding="utf-8")
    (build / "plan.txt").write_text(plan_marker + "\n", encoding="utf-8")
    src = SUBJECT.read_text(encoding="utf-8")
    if comment_edit:
        src = "# replay-comment-control: comment-only edit, no behaviour change\n" + src
    (build / "workflow.py").write_text(src, encoding="utf-8")
    return build


def child_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k != "TST0028_LIVE_TOKEN"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


def run_subject(build: Path, mode: str, freeze_ns: int | None = None) -> dict:
    argv = [sys.executable, "-B", str(build / "workflow.py"),
            "--build-dir", str(build), "--mode", mode]
    if freeze_ns is not None:
        argv += ["--freeze-clock", str(freeze_ns)]
    proc = subprocess.run(argv, capture_output=True, text=True,
                          timeout=120, env=child_env())
    if proc.returncode != 0:
        raise RuntimeError(f"workflow {mode} failed rc={proc.returncode}: "
                           f"{proc.stderr[-400:]}")
    return json.loads((build / "record.json").read_text(encoding="utf-8"))


def artifact_set(build: Path) -> dict:
    return {
        name: sha(build / name)
        for name in ("digest.txt", "report.json")
        if (build / name).is_file()
    }


def diff_set(recorded: dict, replayed: dict) -> dict:
    changed = sorted(
        key for key in set(recorded) | set(replayed)
        if recorded.get(key) != replayed.get(key))
    return {
        "changed": [{"path": k, "record_sha256": recorded.get(k),
                     "replay_sha256": replayed.get(k)} for k in changed],
        "only_in_record": sorted(set(recorded) - set(replayed)),
        "only_in_replay": sorted(set(replayed) - set(recorded)),
        "empty": not changed and not (set(recorded) ^ set(replayed)),
    }


def trace_diff(rec: dict, rep: dict) -> dict:
    a, b = list(rec["decision_trace"]), list(rep["decision_trace"])
    changed = [x for x in a if x not in b] + [x for x in b if x not in a]
    return {
        "changed": changed,
        "record_trace_sha256": rec["decision_trace_sha256"],
        "replay_trace_sha256": rep["decision_trace_sha256"],
        "empty": changed == [] and rec["decision_trace_sha256"] == rep["decision_trace_sha256"],
    }


def record_step_outcomes(doc: dict) -> dict:
    return {s["step_id"]: {"outcome": s["outcome"],
                           "reason_class": s.get("reason_class")}
            for s in doc["steps"]}


def replayability(doc: dict) -> dict:
    outcomes = record_step_outcomes(doc)
    blocked = [sid for sid, o in outcomes.items() if o["outcome"] == "blocked"]
    replayable = [sid for sid, o in outcomes.items() if o["outcome"] == "ok"]
    reasons = {sid: outcomes[sid]["reason_class"] for sid in blocked}
    return {
        "denominator_steps": len(doc["step_ids"]),
        "replayable_steps": replayable,
        "blocked_steps": blocked,
        "blocked_enumerated_by_reason": reasons,
        "replayable_fraction": f"{len(replayable)}/{len(doc['step_ids'])}",
    }


def run_cycle(parent: Path, planted: bool = False, comment_only: bool = False) -> dict:
    """Record on build-a, replay on the requested variant. Returns the diff doc."""
    a = materialise(parent, "build-a", PLAN_MARKER_RECORD)
    rec_doc = run_subject(a, "record")
    rec = {
        "artifact_set": artifact_set(a),
        "decision_trace": rec_doc["decision_trace"],
        "decision_trace_ids": rec_doc["decision_trace_ids"],
        "decision_trace_sha256": rec_doc["decision_trace_sha256"],
        "frozen_clock_unix_ns": next(
            s["unix_ns"] for s in rec_doc["steps"] if s["step_id"] == "stamp_clock"),
        "plan_marker": rec_doc["plan_marker"],
        "steps": rec_doc["steps"],
        "step_ids": rec_doc["step_ids"],
    }
    if comment_only:
        variant = materialise(parent, "build-d-comment", PLAN_MARKER_RECORD,
                              comment_edit=True)
    elif planted:
        variant = materialise(parent, "build-c-planted", PLAN_MARKER_PLANTED)
    else:
        variant = materialise(parent, "build-b", PLAN_MARKER_RECORD)
    rep_doc = run_subject(variant, "replay", freeze_ns=rec["frozen_clock_unix_ns"])
    rep = {
        "artifact_set": artifact_set(variant),
        "decision_trace": rep_doc["decision_trace"],
        "decision_trace_ids": rep_doc["decision_trace_ids"],
        "decision_trace_sha256": rep_doc["decision_trace_sha256"],
        "plan_marker": rep_doc["plan_marker"],
    }
    return {
        "record": rec,
        "replay": rep,
        "artifact_set": diff_set(rec["artifact_set"], rep["artifact_set"]),
        "decision_trace": trace_diff(rec, rep),
        "replayability": replayability(rec_doc),
        "record_step_outcomes": record_step_outcomes(rec_doc),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", choices=["identical", "planted", "comment"],
                    required=True)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="tst0028-") as tmp:
        doc = run_cycle(Path(tmp),
                        planted=(args.cycle == "planted"),
                        comment_only=(args.cycle == "comment"))
    print(json.dumps(doc, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
