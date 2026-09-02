#!/usr/bin/env python3
"""Live SIGKILL + fan-in scenarios for TST-0088."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
RUN = HERE / "runtime"

from fanin import classify  # noqa: E402
from kill_harness import run_and_kill, run_complete  # noqa: E402
from writers import VICTIM_SENTINEL, VICTIM_UNIT  # noqa: E402

SENTINEL = VICTIM_SENTINEL
UNIT = VICTIM_UNIT


def _wipe(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _preserve_truncated(src: Path) -> dict:
    FIX.mkdir(parents=True, exist_ok=True)
    dest = FIX / "truncated-partial.json"
    dest.write_bytes(src.read_bytes())
    sha, nbytes = _digest(dest)
    meta = {
        "path": "command-center/p2-wave/probes/TST-0088/fixtures/truncated-partial.json",
        "bytes": nbytes,
        "sha256": sha,
        "source": str(src.relative_to(HERE)) if src.is_relative_to(HERE) else str(src),
    }
    (FIX / "truncated-meta.json").write_text(
        json.dumps(meta, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return meta


def truncated_kill() -> dict:
    work = RUN / "streaming-kill"
    _wipe(work)
    dest = work / "artifact.json"
    ready = work / "ready.txt"
    kill = run_and_kill(mode="streaming", dest=dest, ready=ready)
    if not kill["saw_ready"]:
        raise RuntimeError("streaming kill missed the hold window (ready marker absent)")
    if not dest.is_file():
        raise RuntimeError("streaming SIGKILL left no destination file; not measuring a partial")
    verdict = classify(dest, expected_sentinel=SENTINEL, expected_unit_id=UNIT)
    if verdict["verdict"] == "SUCCESS":
        raise RuntimeError("fan-in classified truncated artifact SUCCESS")
    if verdict["condition_id"] != 5:
        raise RuntimeError(
            f"truncated artifact rejected at condition {verdict['condition_id']}, expected 5"
        )
    if not verdict["parses"] or not verdict["looks_plausible"]:
        raise RuntimeError(
            f"truncated artifact must parse and look plausible; got parses={verdict['parses']} "
            f"plausible={verdict['looks_plausible']} parse_err={verdict['parse_err']}"
        )
    if verdict["sentinel_present"]:
        raise RuntimeError("truncated artifact unexpectedly carries the sentinel")
    fixture = _preserve_truncated(dest)
    return {"kill": kill, "classification": verdict, "fixture": fixture}


def complete_streaming() -> dict:
    work = RUN / "streaming-complete"
    _wipe(work)
    dest = work / "artifact.json"
    ready = work / "ready.txt"
    run = run_complete(mode="streaming", dest=dest, ready=ready)
    if run["returncode"] != 0 or not dest.is_file():
        raise RuntimeError(f"complete streaming write failed: {run}")
    verdict = classify(dest, expected_sentinel=SENTINEL, expected_unit_id=UNIT)
    if verdict["verdict"] != "SUCCESS" or verdict["condition_id"] is not None:
        raise RuntimeError(f"complete streaming artifact was not SUCCESS: {verdict}")
    return {"run": run, "classification": verdict}


def absent_artifact() -> dict:
    work = RUN / "absent"
    _wipe(work)
    dest = work / "missing.json"
    verdict = classify(dest, expected_sentinel=SENTINEL, expected_unit_id=UNIT)
    if verdict["verdict"] == "SUCCESS":
        raise RuntimeError("absent path classified SUCCESS")
    if verdict["condition_id"] != 2:
        raise RuntimeError(
            f"absent artifact must fail at condition 2 (TST-0004 class), got {verdict['condition_id']}"
        )
    return {"classification": verdict}


def atomic_kill() -> dict:
    work = RUN / "atomic-kill"
    _wipe(work)
    dest = work / "artifact.json"
    ready = work / "ready.txt"
    kill = run_and_kill(mode="atomic", dest=dest, ready=ready)
    if not kill["saw_ready"]:
        raise RuntimeError("atomic kill missed the hold window (ready marker absent)")
    if dest.is_file():
        # Visible destination after kill-before-rename is a leaked partial or a raced complete.
        verdict = classify(dest, expected_sentinel=SENTINEL, expected_unit_id=UNIT)
        raise RuntimeError(
            "atomic SIGKILL made the destination visible "
            f"(bytes={kill['dest_bytes']} verdict={verdict['verdict']} cond={verdict['condition_id']})"
        )
    return {
        "kill": kill,
        "destination_visible": False,
        "tmp_leftover_ok": True,
        "published_partial": False,
    }


def complete_atomic() -> dict:
    work = RUN / "atomic-complete"
    _wipe(work)
    dest = work / "artifact.json"
    ready = work / "ready.txt"
    run = run_complete(mode="atomic", dest=dest, ready=ready)
    if run["returncode"] != 0 or not dest.is_file():
        raise RuntimeError(f"complete atomic write failed: {run}")
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.is_file():
        raise RuntimeError("atomic complete left a tmp sibling")
    verdict = classify(dest, expected_sentinel=SENTINEL, expected_unit_id=UNIT)
    if verdict["verdict"] != "SUCCESS":
        raise RuntimeError(f"complete atomic artifact was not SUCCESS: {verdict}")
    return {"run": run, "classification": verdict}
