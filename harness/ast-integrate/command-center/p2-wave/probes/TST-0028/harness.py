#!/usr/bin/env python3
"""Worktree-isolated differential replay harness for TST-0028.

Materialises two copies of subject/ in temp directories, records a run in
build A, replays recorded inputs against build B (identical) and against a
planted-behaviour build C. Diffs the semantic artifact set and decision trace.
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
from typing import Any

HERE = Path(__file__).resolve().parent
SUBJECT = HERE / "subject"
PLAN_NEEDLE = 'PLAN_MARKER = "accept-v1"'
PLANTED = 'PLAN_MARKER = "accept-v2-planted"'
COMMENT_PLANT = 'PLAN_MARKER = "accept-v1"  # non-behaviour comment plant'


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_obj(obj: Any) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "TST0028_LIVE_TOKEN"):
        env.pop(key, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return env


def materialize(dest: Path, mutate: str | None = None) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SUBJECT, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    wf = dest / "workflow.py"
    text = wf.read_text(encoding="utf-8")
    if mutate == "behaviour":
        if PLAN_NEEDLE not in text:
            raise RuntimeError("PLAN_MARKER needle missing; cannot plant behaviour change")
        wf.write_text(text.replace(PLAN_NEEDLE, PLANTED, 1), encoding="utf-8")
    elif mutate == "comment":
        if PLAN_NEEDLE not in text:
            raise RuntimeError("PLAN_MARKER needle missing; cannot plant comment")
        wf.write_text(text.replace(PLAN_NEEDLE, COMMENT_PLANT, 1), encoding="utf-8")


def run_subject(build: Path, argv: list[str], timeout: int = 30) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-B", "workflow.py", *argv],
        cwd=str(build),
        env=child_env(),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"subject rc={proc.returncode} argv={argv}\n"
            f"stdout={proc.stdout[-1500:]}\nstderr={proc.stderr[-1500:]}"
        )
    return proc


def load_json(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise RuntimeError(f"expected object in {path}")
    return doc


def record_build(build: Path) -> dict[str, Any]:
    run_subject(
        build,
        ["record", "--out", "recording.json", "--artifacts-dir", "artifacts"],
    )
    return load_json(build / "recording.json")


def replay_build(build: Path, recording: dict[str, Any]) -> dict[str, Any]:
    rec_path = build / "recording.json"
    rec_path.write_text(json.dumps(recording, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run_subject(
        build,
        [
            "replay",
            "--out",
            "replay.json",
            "--artifacts-dir",
            "artifacts",
            "--recording",
            "recording.json",
            "--offline",
        ],
    )
    return load_json(build / "replay.json")


def diff_sets(record_set: dict[str, str], replay_set: dict[str, str]) -> dict[str, Any]:
    only_record = sorted(set(record_set) - set(replay_set))
    only_replay = sorted(set(replay_set) - set(record_set))
    changed = [
        {"path": path, "record_sha256": record_set[path], "replay_sha256": replay_set[path]}
        for path in sorted(set(record_set) & set(replay_set))
        if record_set[path] != replay_set[path]
    ]
    empty = not only_record and not only_replay and not changed
    return {
        "only_in_record": only_record,
        "only_in_replay": only_replay,
        "changed": changed,
        "empty": empty,
    }


def diff_traces(record_tr: list[dict[str, Any]], replay_tr: list[dict[str, Any]]) -> dict[str, Any]:
    rec = {row["id"]: row.get("decision_sha256") for row in record_tr}
    rep = {row["id"]: row.get("decision_sha256") for row in replay_tr}
    only_record = sorted(set(rec) - set(rep))
    only_replay = sorted(set(rep) - set(rec))
    changed = [
        {"id": sid, "record_sha256": rec[sid], "replay_sha256": rep[sid]}
        for sid in sorted(set(rec) & set(rep))
        if rec[sid] != rep[sid]
    ]
    empty = not only_record and not only_replay and not changed
    return {
        "only_in_record": only_record,
        "only_in_replay": only_replay,
        "changed": changed,
        "empty": empty,
    }


def pair_diff(recorded: dict[str, Any], replayed: dict[str, Any]) -> dict[str, Any]:
    arts = diff_sets(recorded.get("artifact_set") or {}, replayed.get("artifact_set") or {})
    trace = diff_traces(recorded.get("decision_trace") or [], replayed.get("decision_trace") or [])
    return {
        "artifact_set": arts,
        "decision_trace": trace,
        "empty": bool(arts["empty"] and trace["empty"]),
        "record_plan_marker": recorded.get("plan_marker"),
        "replay_plan_marker": replayed.get("plan_marker"),
    }


def replayability(recorded: dict[str, Any]) -> dict[str, Any]:
    steps = list(recorded.get("steps") or [])
    enumerated: list[dict[str, Any]] = []
    replayable_offline: list[str] = []
    local_only: list[str] = []
    for step in steps:
        sid = str(step.get("id"))
        reason = step.get("reason")
        klass = str(step.get("reason_class") or "local")
        offline = reason not in {"network", "credential", "GUI"}
        if offline:
            replayable_offline.append(sid)
        if klass == "local" and reason is None:
            local_only.append(sid)
        if reason in {"network", "credential", "clock", "GUI"}:
            enumerated.append(
                {
                    "step_id": sid,
                    "reason": reason,
                    "reason_class": klass,
                    "outcome": step.get("outcome"),
                    "replayable_without_live_network_or_credentials": offline,
                    "replayable_if_frozen_from_recording": reason == "clock",
                    "why": {
                        "network": (
                            "Step opens a TCP connection to TEST-NET-1 (192.0.2.1). "
                            "Offline replay skips the socket."
                        ),
                        "credential": (
                            "Step requires TST0028_LIVE_TOKEN. The value is never "
                            "copied into the recording; offline replay does not "
                            "read credentials."
                        ),
                        "clock": (
                            "Live wall-clock (time.time_ns) is not identically "
                            "replayable. The recorded unix_ns is frozen on replay."
                        ),
                        "GUI": (
                            "UI capture needs a live GUI session. This harness "
                            "records the block and does not screenshot."
                        ),
                    }.get(str(reason), "unclassified"),
                }
            )
    n = len(steps)
    n_off = len(replayable_offline)
    n_local = len(local_only)
    reasons = sorted({row["reason"] for row in enumerated})
    return {
        "denominator_steps": n,
        "replayable_without_live_network_or_credentials": {
            "count": n_off,
            "percent": round((100.0 * n_off / n) if n else 0.0, 1),
            "step_ids": replayable_offline,
            "note": (
                "Frozen recorded clock is allowed. Network, credential, and GUI "
                "steps are excluded."
            ),
        },
        "replayable_local_only": {
            "count": n_local,
            "percent": round((100.0 * n_local / n) if n else 0.0, 1),
            "step_ids": local_only,
            "note": "Excludes clock, network, credential, and GUI.",
        },
        "non_replayable_enumerated_by_reason": enumerated,
        "reasons_present": reasons,
    }


def run_experiment() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tst0028-") as tmp:
        root = Path(tmp)
        build_a = root / "build-a"
        build_b = root / "build-b"
        build_c = root / "build-c-planted"
        build_d = root / "build-d-comment"
        materialize(build_a)
        materialize(build_b)
        materialize(build_c, mutate="behaviour")
        materialize(build_d, mutate="comment")
        recorded = record_build(build_a)
        identical = replay_build(build_b, recorded)
        planted = replay_build(build_c, recorded)
        comment = replay_build(build_d, recorded)
        ident_diff = pair_diff(recorded, identical)
        plant_diff = pair_diff(recorded, planted)
        comment_diff = pair_diff(recorded, comment)
        stats = replayability(recorded)
        builds = {
            "record": str(build_a.name),
            "identical_replay": str(build_b.name),
            "planted_replay": str(build_c.name),
            "comment_replay": str(build_d.name),
            "parent": str(root.name),
            "side_by_side": True,
        }
        # TemporaryDirectory is about to vanish; copy comparable hashes only.
        result = {
            "materialised_builds": builds,
            "recorded": {
                "plan_marker": recorded.get("plan_marker"),
                "step_ids": [s.get("id") for s in recorded.get("steps") or []],
                "step_count": len(recorded.get("steps") or []),
                "tool_call_count": len(recorded.get("tool_calls") or []),
                "artifact_set": recorded.get("artifact_set"),
                "decision_trace_ids": [r.get("id") for r in recorded.get("decision_trace") or []],
                "decision_trace_sha256": digest_obj(recorded.get("decision_trace")),
                "frozen_clock_unix_ns": recorded.get("frozen_clock_unix_ns"),
                "fetch_external": next(
                    (s.get("decision") for s in recorded.get("steps") or [] if s.get("id") == "fetch_external"),
                    {},
                ),
                "credential_gate": next(
                    (s.get("decision") for s in recorded.get("steps") or [] if s.get("id") == "credential_gate"),
                    {},
                ),
                "gui_capture": next(
                    (s.get("decision") for s in recorded.get("steps") or [] if s.get("id") == "gui_capture"),
                    {},
                ),
            },
            "identical_replay": ident_diff,
            "planted_behaviour_change": plant_diff,
            "comment_only_control": comment_diff,
            "replayability": stats,
            "tests": {
                "test_identical_build_replays_with_an_empty_diff": ident_diff["empty"],
                "test_a_planted_behaviour_change_shows_up_in_the_diff": (
                    (not plant_diff["empty"])
                    and (not plant_diff["artifact_set"]["empty"])
                    and (not plant_diff["decision_trace"]["empty"])
                ),
                "test_comment_only_mutation_is_not_a_behaviour_change": comment_diff["empty"],
            },
        }
        result["pass"] = bool(
            result["tests"]["test_identical_build_replays_with_an_empty_diff"]
            and result["tests"]["test_a_planted_behaviour_change_shows_up_in_the_diff"]
            and result["tests"]["test_comment_only_mutation_is_not_a_behaviour_change"]
            and set(stats["reasons_present"]) >= {"network", "credential", "clock", "GUI"}
            and stats["replayable_without_live_network_or_credentials"]["count"] >= 1
            and stats["denominator_steps"] == 8
        )
        return result


if __name__ == "__main__":
    exp = run_experiment()
    print(json.dumps({k: exp[k] for k in exp}, sort_keys=True, default=str))
    raise SystemExit(0 if exp.get("pass") else 1)
