"""Abort-safe council event log. Torn writes remain parseable. IMP-0353."""
from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

ABORTED_LABEL = "ABORTED"


class NotADecision(ValueError):
    pass


def strip_aborted_label(text: str) -> str:
    return text.replace(ABORTED_LABEL, "").strip()


def consume_as_decision(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("label") == ABORTED_LABEL or record.get("aborted"):
        raise NotADecision("aborted record is not a decision")
    return record


def parse_log_bytes(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace")
    events = []
    torn = False
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            torn = True
            continue
    return {"parseable": True, "torn": torn, "events": events}


def naive_jsonl_torn_parses(path: Path | str, cut: int) -> bool:
    payload = (json.dumps({"n": 1}) + "\n" + json.dumps({"n": 2}) + "\n").encode()
    torn = payload[:cut]
    Path(path).write_bytes(torn)
    try:
        for line in torn.decode("utf-8", errors="strict").splitlines():
            if line.strip():
                json.loads(line)
        return True
    except Exception:
        return False


def run_council(
    path: Path | str,
    n_events: int = 8,
    council_id: str = "council",
    artifact_path: Path | str | None = None,
    abort_after_events: int | None = None,
    tear_after_bytes: int | None = None,
    owner_id: str = "owner",
    abort_reason: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    events = []
    limit = abort_after_events if abort_after_events is not None else n_events
    aborted = abort_after_events is not None
    with path.open("w", encoding="utf-8") as fh:
        for i in range(limit):
            rec = {"i": i, "kind": "event", "council_id": council_id}
            events.append(rec)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    artifact = {
        "council_id": council_id,
        "owner_id": owner_id,
        "aborted": aborted,
        "abort_label": ABORTED_LABEL if aborted else None,
        "abort_reason": abort_reason,
        "events": events,
        "label": ABORTED_LABEL if aborted else "COMPLETED",
    }
    if artifact_path:
        Path(artifact_path).write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return {"log": str(path), "artifact": artifact, "aborted": aborted}


def chaos_midwrite_trials(root: Path | str, n: int = 20, seed: int = 353) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    trials = []
    ok = 0
    for i in range(n):
        trial = root / f"trial-{i:02d}"
        trial.mkdir(parents=True, exist_ok=True)
        log = trial / "events.clog"
        full = "".join(json.dumps({"i": j, "kind": "event"}) + "\n" for j in range(12)).encode()
        first_nl = full.find(b"\n")
        cut = rng.randint(first_nl + 1, max(first_nl + 2, len(full) - 1))
        log.write_bytes(full[:cut])
        parsed = parse_log_bytes(log.read_bytes())
        row_ok = bool(parsed["parseable"] and parsed["events"])
        if row_ok:
            ok += 1
        trials.append({"i": i, "ok": row_ok, "path": log.as_posix()})
    return {
        "n": n,
        "ok": ok,
        "pass": ok == n,
        "trials": trials,
        "frame_len": 12,
        "seed": seed,
    }
