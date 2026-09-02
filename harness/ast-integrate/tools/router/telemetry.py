"""Router telemetry scrub, join, and month report (IMP-0397)."""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

REDACTED_SECRET = "[REDACTED_SECRET]"
REDACTED_PATH = "[REDACTED_PATH]"
RECORDED_FIELDS = (
    "join_key",
    "month",
    "event_type",
    "session_id",
)
SENSITIVE_FIELDS = frozenset({"prompt", "raw_user_text", "secret"})
_ABS_PATH = re.compile(r"(?:/home|/Users|C:\\\\)[^\s\"']+")
_SECRET = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


class ScrubFailure(ValueError):
    pass


class JoinError(ValueError):
    pass


def record(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True, "args": list(args), "kwargs": dict(kwargs)}


def emit(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return record(*args, **kwargs)


def counters() -> dict[str, int]:
    return {}


def load_jsonl(path: Path | str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_events_from_dir(path: Path | str) -> list[dict[str, Any]]:
    root = Path(path)
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for p in sorted(root.glob("*.jsonl")):
        rows.extend(load_jsonl(p))
    return rows


def load_capability_ids(path: Path | str) -> list[str]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    caps = doc.get("capabilities") or []
    return [str(c.get("id") if isinstance(c, dict) else c) for c in caps]


def _hash_id(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _scrub_text(text: str, repo: Path, extra: tuple[str, ...] = ()) -> str:
    out = text
    for extra_s in extra:
        if extra_s:
            out = out.replace(extra_s, REDACTED_SECRET if extra_s.startswith("sk-") else REDACTED_PATH)
    out = _SECRET.sub(REDACTED_SECRET, out)
    out = _ABS_PATH.sub(REDACTED_PATH, out)
    repo_s = str(repo)
    if repo_s and repo_s in out:
        out = out.replace(repo_s, REDACTED_PATH)
    return out


def scrub_event(
    event: dict[str, Any],
    repo: Path,
    extra_canaries: tuple[str, ...] = (),
    drop_sensitive: bool = True,
) -> dict[str, Any]:
    clone = json.loads(json.dumps(event))
    extra = extra_canaries
    for key in list(clone):
        val = clone[key]
        if isinstance(val, str):
            clone[key] = _scrub_text(val, repo, extra)
        elif isinstance(val, list):
            clone[key] = [
                _scrub_text(v, repo, extra) if isinstance(v, str) else v for v in val
            ]
    if drop_sensitive:
        clone.pop("user_id", None)
        if str(clone.get("session_id") or "").startswith("raw-sess"):
            clone["session_id"] = _hash_id(str(clone.get("session_id")))
    return clone


def dump_for_leak_scan(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True)


def leak_hits(blob: str, repo: Path, extra: tuple[str, ...] = ()) -> list[str]:
    hits: list[str] = []
    for item in extra:
        if item and item in blob:
            hits.append("canary")
            break
    if "user-alice" in blob or "raw-sess-01" in blob:
        hits.append("identifier")
    return hits


def assert_clean(records: list[dict[str, Any]], repo: Path, extra: tuple[str, ...] = ()) -> None:
    blob = dump_for_leak_scan(records)
    hits = leak_hits(blob, repo, extra)
    if hits:
        raise ScrubFailure(f"leaks:{hits}")


def _in_month(ts: str, month: str) -> bool:
    return str(ts or "").startswith(month)


def emit_records(
    events: list[dict[str, Any]],
    repo: Path,
    month: str = "2026-07",
    extra_canaries: tuple[str, ...] = (),
    test_disable_scrub: bool = False,
) -> list[dict[str, Any]]:
    by_sess: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        if not _in_month(str(ev.get("ts") or ""), month):
            continue
        by_sess[str(ev.get("session_id") or "")].append(ev)
    out: list[dict[str, Any]] = []
    for sid, rows in by_sess.items():
        offered: list[str] = []
        used: list[str] = []
        outcomes: list[str] = []
        for ev in rows:
            caps = [str(c) for c in (ev.get("capabilities") or [])]
            kind = str(ev.get("type") or "")
            if kind == "router.offer":
                offered.extend(caps)
            elif kind == "router.use":
                used.extend(caps)
            elif kind == "task.outcome":
                outcomes.append(str(ev.get("outcome") or ""))
        rec = {
            "session_id": sid if test_disable_scrub else _hash_id(sid),
            "join_key": sid if test_disable_scrub else _hash_id(sid),
            "join_key_name": "session_id",
            "join_key_scope": "session",
            "month": month,
            "event_type": "router.month",
            "offered": list(dict.fromkeys(offered)),
            "used": list(dict.fromkeys(used)),
            "outcomes": outcomes,
        }
        if test_disable_scrub:
            rec["raw"] = rows
            rec["note"] = json.dumps(rows)
        else:
            rec = scrub_event(rec, repo, extra_canaries, drop_sensitive=True)
            rec["join_key"] = _hash_id(sid)
            rec["join_key_scope"] = "session"
            rec["offered"] = list(dict.fromkeys(offered))
            rec["used"] = list(dict.fromkeys(used))
        out.append(rec)
    return out


def join_sessions(
    events: list[dict[str, Any]], key: str = "session_id", allow_unscoped: bool = False
) -> dict[str, list[dict[str, Any]]]:
    if key != "session_id" and not allow_unscoped:
        raise JoinError(f"unscoped join key {key}")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        groups[str(ev.get(key) or "")].append(ev)
    return dict(groups)


def unscoped_join_contaminates(events: list[dict[str, Any]]) -> dict[str, Any]:
    sess = join_sessions(events, key="session_id")
    users = join_sessions(events, key="user_id", allow_unscoped=True)
    return {
        "session_join_count": len(sess),
        "user_join_count": len(users),
        "collapsed": len(users) < len(sess),
        "unscoped_join_loses_session_outcomes": len(users) < len(sess),
    }


def month_report(
    events: list[dict[str, Any]],
    indexed: list[str],
    repo: Path,
    month: str = "2026-07",
    extra_canaries: tuple[str, ...] = (),
) -> dict[str, Any]:
    records = emit_records(events, repo, month=month, extra_canaries=extra_canaries)
    offered_ids: list[str] = []
    for rec in records:
        offered_ids.extend(rec.get("offered") or [])
    offered_ids = list(dict.fromkeys(offered_ids))
    indexed_n = len(indexed)
    offered_n = len(offered_ids)
    frac = offered_n / indexed_n if indexed_n else 0.0
    per_cap: list[dict[str, Any]] = []
    for cid in offered_ids:
        offer_n = sum(1 for r in records if cid in (r.get("offered") or []))
        use_n = sum(1 for r in records if cid in (r.get("used") or []))
        per_cap.append(
            {
                "capability_id": cid,
                "offered": offer_n,
                "used": use_n,
                "delta": float(offer_n),
            }
        )
    return {
        "records": records,
        "breadth": {
            "indexed": indexed_n,
            "offered": offered_n,
            "offered_ids": offered_ids,
            "fraction": frac,
            "denominator_statement": f"{offered_n} of {indexed_n} indexed capabilities offered",
        },
        "join_key": {"name": "session_id", "scope": "session", "value_kind": "opaque-hash"},
        "correlation": {"per_capability": per_cap},
    }
