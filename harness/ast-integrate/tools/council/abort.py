"""Abort-safe council event log. Torn writes remain parseable. IMP-0353."""
from __future__ import annotations

import json
import os
import random
import zlib
from pathlib import Path
from typing import Any

ABORTED_LABEL = "ABORTED"


class NotADecision(ValueError):
    pass


def strip_aborted_label(record: dict[str, Any] | str) -> dict[str, Any] | str:
    """Negative-control helper: what a careless consumer sees once the ABORTED marking is removed.

    For an artifact dict it returns a *copy* with every abort marking dropped
    (``abort_label``, ``aborted``, an ABORTED ``label``); the original is left
    untouched so it keeps being refused.  For plain text it removes the label.
    """
    if isinstance(record, dict):
        out = {k: v for k, v in record.items() if k != "abort_label"}
        out["aborted"] = False
        if out.get("label") == ABORTED_LABEL:
            out["label"] = "UNLABELLED"
        return out
    return str(record).replace(ABORTED_LABEL, "").strip()


def consume_as_decision(record: dict[str, Any]) -> dict[str, Any]:
    """Accept a council artifact as a decision, refusing anything marked aborted."""
    if record.get("abort_label") == ABORTED_LABEL or record.get("label") == ABORTED_LABEL:
        raise NotADecision(f"artifact carries {ABORTED_LABEL} label: not a decision")
    if record.get("aborted"):
        raise NotADecision("aborted council artifact is not a decision")
    return record


FRAME_HEADER_LEN = 16  # 8 hex chars payload length + 8 hex chars CRC32 of the payload


def encode_frame(record: dict[str, Any]) -> bytes:
    """Frame one event: ``<len:08x><crc32:08x><json>\\n``.

    The header commits the frame's length and checksum before the payload, so a
    write aborted anywhere inside the frame leaves an *incomplete* tail that a
    reader can recognise and drop, instead of a torn line it has to guess at.
    """
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    header = f"{len(payload):08x}{zlib.crc32(payload) & 0xFFFFFFFF:08x}".encode("ascii")
    return header + payload + b"\n"


def _decode_frames(raw: bytes) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    torn = False
    incomplete_tail = False
    offset = 0
    total = len(raw)
    while offset < total:
        header = raw[offset : offset + FRAME_HEADER_LEN]
        if len(header) < FRAME_HEADER_LEN:
            incomplete_tail = True  # abort landed inside a header: frame never committed
            break
        try:
            length = int(header[:8], 16)
            crc = int(header[8:16], 16)
        except ValueError:
            torn = True  # a committed header that is not hex: corrupt log
            break
        start = offset + FRAME_HEADER_LEN
        end = start + length
        if end + 1 > total:
            incomplete_tail = True  # abort landed inside the payload / terminator
            break
        payload = raw[start:end]
        if raw[end : end + 1] != b"\n" or (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
            torn = True  # full-length frame present but corrupt: real damage
            break
        try:
            events.append(json.loads(payload.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            torn = True
            break
        offset = end + 1
    return {
        "parseable": True,
        "torn": torn,
        "incomplete_tail": incomplete_tail,
        "events": events,
        "format": "clog-framed",
        "committed_bytes": offset,
    }


def _looks_framed(raw: bytes) -> bool:
    head = raw[:FRAME_HEADER_LEN]
    if len(head) < FRAME_HEADER_LEN:
        return len(raw) > 0 and not raw.lstrip().startswith(b"{")
    try:
        int(head, 16)
    except ValueError:
        return False
    return True


def parse_log_bytes(raw: bytes) -> dict[str, Any]:
    """Parse a council event log.

    Framed ``.clog`` bytes (see ``encode_frame``) decode frame by frame: an
    incomplete final frame is dropped and reported as ``incomplete_tail`` (the
    expected shape of an aborted write), while a full-length frame whose CRC or
    JSON is wrong is ``torn``.  Plain JSONL is still accepted for legacy logs,
    where any undecodable line marks the log ``torn``.
    """
    if _looks_framed(raw):
        return _decode_frames(raw)
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
    return {
        "parseable": True,
        "torn": torn,
        "incomplete_tail": False,
        "events": events,
        "format": "jsonl",
        "committed_bytes": len(raw),
    }


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
    with path.open("wb") as fh:
        for i in range(limit):
            rec = {"i": i, "kind": "event", "council_id": council_id}
            events.append(rec)
            fh.write(encode_frame(rec))
            fh.flush()
            os.fsync(fh.fileno())
    # The decision payload the council had reached when it stopped: complete
    # when every planned event landed, otherwise the partial state an abort
    # leaves behind (kept so a consumer refusing it is a real refusal).
    decision = {
        "outcome": "adopt" if len(events) >= n_events else "undecided",
        "events_seen": len(events),
        "events_planned": n_events,
        "partial": len(events) < n_events,
    }
    artifact = {
        "council_id": council_id,
        "owner_id": owner_id,
        "aborted": aborted,
        "abort_label": ABORTED_LABEL if aborted else None,
        "abort_reason": abort_reason,
        "events": events,
        "decision": decision,
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
    n_events = 12
    for i in range(n):
        trial = root / f"trial-{i:02d}"
        trial.mkdir(parents=True, exist_ok=True)
        log = trial / "events.clog"
        frames = [encode_frame({"i": j, "kind": "event", "council_id": f"chaos-{i:02d}"}) for j in range(n_events)]
        full = b"".join(frames)
        first_end = len(frames[0])
        # Abort at a random byte strictly inside the log, after the first committed frame.
        cut = rng.randint(first_end, max(first_end, len(full) - 1))
        log.write_bytes(full[:cut])
        parsed = parse_log_bytes(log.read_bytes())
        expected_committed = sum(1 for k in range(n_events) if sum(len(f) for f in frames[: k + 1]) <= cut)
        row_ok = bool(
            parsed["parseable"]
            and not parsed["torn"]
            and parsed["events"]
            and len(parsed["events"]) == expected_committed
        )
        if row_ok:
            ok += 1
        trials.append(
            {
                "i": i,
                "ok": row_ok,
                "path": log.as_posix(),
                "cut": cut,
                "bytes_total": len(full),
                "events_committed": len(parsed["events"]),
                "events_expected": expected_committed,
                "incomplete_tail": parsed["incomplete_tail"],
                "torn": parsed["torn"],
            }
        )
    return {
        "n": n,
        "ok": ok,
        "pass": ok == n,
        "all_parse": ok == n,
        "trials": trials,
        "n_events": n_events,
        "frame_len": FRAME_HEADER_LEN,
        "seed": seed,
    }
