"""Build a real EVENTS.jsonl slice without rewriting the production log.

command-center/events/EVENTS.jsonl is measured present-or-absent. When present,
its physical lines are the PREFIX of the probe fixture (byte-identical). The
production file is never opened for write. When the live log is too thin to
exercise conservation (need >=5 folded records and >=1 classified drop), the
production writer (tools/command-center/close.py:append_event) APPENDS extra
records onto the fixture only, plus an explicit blank line and torn JSON as
classified drops. That is not a claim the live log itself was rewritten.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_EVENTS = REPO / "command-center" / "events" / "EVENTS.jsonl"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FIXTURE = HERE / "fixtures" / "source-events.jsonl"
STAMP = "2026-08-24T20:00:00+00:00"
N_PARSEABLE = 8


def live_present() -> bool:
    return LIVE_EVENTS.is_file() and LIVE_EVENTS.stat().st_size > 0


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def physical_lines(text: str) -> list[str]:
    if text == "":
        return []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _open_item_ids(limit: int) -> list[str]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    ids: list[str] = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("disposition"):
            continue
        iid = str(item.get("id") or "")
        if iid:
            ids.append(iid)
        if len(ids) >= limit:
            break
    return ids


def _append_via_production_writer(target: Path, payload: dict) -> None:
    tools_cc = str(REPO / "tools" / "command-center")
    if tools_cc not in sys.path:
        sys.path.insert(0, tools_cc)
    import close  # noqa: WPS433  (production writer)

    close.append_event(payload, target)


def _parseable_ids(lines: list[str]) -> list[str]:
    ids: list[str] = []
    for line in lines:
        if line == "":
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            iid = obj.get("id") or obj.get("unit_id")
            if iid:
                ids.append(str(iid))
    return ids


def _n_parseable(lines: list[str]) -> int:
    n = 0
    for line in lines:
        if line == "":
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            n += 1
    return n


def _n_drop_class(lines: list[str]) -> int:
    n = 0
    for line in lines:
        if line == "":
            n += 1
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            n += 1
            continue
        if not isinstance(obj, dict):
            n += 1
    return n


def _append_notes(dest: Path, ids: list[str]) -> None:
    verbs = [
        ("note", "progress note for fold slice"),
        ("defer", "parked for drain rehearsal"),
        ("open-echo", "opened on the close rail"),
        ("note", "second note; append-only sibling"),
    ]
    for i, iid in enumerate(ids):
        _verb, detail = verbs[i % len(verbs)]
        payload = {
            "ts": STAMP,
            "verb": "note",
            "id": iid,
            "note": f"{detail} ({iid})",
        }
        _append_via_production_writer(dest, payload)


def _append_classified_drops(dest: Path) -> None:
    with dest.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n")
        handle.write('{"torn":\n')


def harvest(dest: Path | None = None) -> dict:
    dest = dest or FIXTURE
    dest.parent.mkdir(parents=True, exist_ok=True)
    live_sha_before = (
        sha256_bytes(LIVE_EVENTS.read_bytes()) if live_present() else None
    )

    if live_present():
        live_raw = LIVE_EVENTS.read_bytes()
        if not live_raw.endswith(b"\n"):
            live_raw = live_raw + b"\n"
        dest.write_bytes(live_raw)
        lines = physical_lines(dest.read_text(encoding="utf-8"))
        have = _n_parseable(lines)
        seen = set(_parseable_ids(lines))
        if have < N_PARSEABLE:
            needed = N_PARSEABLE - have
            extras: list[str] = []
            for iid in _open_item_ids(N_PARSEABLE + needed + 8):
                if iid in seen:
                    continue
                extras.append(iid)
                seen.add(iid)
                if len(extras) >= needed:
                    break
            if len(extras) < needed:
                raise RuntimeError(
                    f"not-enough-open-items:have={have} extras={len(extras)}"
                )
            _append_notes(dest, extras)
        if _n_drop_class(physical_lines(dest.read_text(encoding="utf-8"))) < 1:
            _append_classified_drops(dest)
        origin = (
            "PREFIX copied byte-for-byte from command-center/events/EVENTS.jsonl "
            "(present on this worktree). Extra parseable rows, if any, were "
            "appended onto the fixture only via "
            "tools/command-center/close.py:append_event. Classified drops "
            "(blank line + torn JSON) were appended onto the fixture only. "
            "The live EVENTS.jsonl path was never opened for write."
        )
        writer = (
            "live-file-prefix + tools/command-center/close.py:append_event "
            "(fixture only)"
        )
    else:
        if dest.exists():
            dest.unlink()
        ids = _open_item_ids(N_PARSEABLE)
        if len(ids) < N_PARSEABLE:
            raise RuntimeError(f"not-enough-open-items:{len(ids)}")
        _append_notes(dest, ids)
        _append_classified_drops(dest)
        origin = (
            "command-center/events/EVENTS.jsonl is ABSENT. Slice emitted by "
            "tools/command-center/close.py:append_event (production writer) "
            f"for {N_PARSEABLE} real OPEN catalog item ids, plus one blank line "
            "and one malformed JSON line as classified drops."
        )
        writer = "tools/command-center/close.py:append_event"

    if live_present():
        live_sha_after = sha256_bytes(LIVE_EVENTS.read_bytes())
        if live_sha_before != live_sha_after:
            raise RuntimeError("harvest-rewrote-live-EVENTS.jsonl")
        live_lines = physical_lines(LIVE_EVENTS.read_text(encoding="utf-8"))
        dest_lines = physical_lines(dest.read_text(encoding="utf-8"))
        if dest_lines[: len(live_lines)] != live_lines:
            raise RuntimeError("fixture-prefix-is-not-live-EVENTS.jsonl")

    text = dest.read_text(encoding="utf-8")
    lines = physical_lines(text)
    return {
        "present_on_worktree": live_present(),
        "catalog_path": "command-center/events/EVENTS.jsonl",
        "slice_path": dest.relative_to(REPO).as_posix(),
        "slice_origin": origin,
        "writer": writer,
        "line_count": len(lines),
        "live_sha256": live_sha_before,
        "live_unmodified": True if live_present() else None,
        "fold_does_not_rewrite_source": True,
    }
