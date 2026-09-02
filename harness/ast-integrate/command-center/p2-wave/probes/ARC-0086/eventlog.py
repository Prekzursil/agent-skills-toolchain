"""ARC-0086 append-only event record: schema, hash chain, write-time redaction.

Consumer call site for the Phase 4 contract. Isolated tempfile by default;
refuses to write command-center/events/EVENTS.jsonl unless allow_live=True.
Chain: sha256 = SHA256(prev_sha256 || LF || canonical body without chain
fields). tools/command-center/status_ledger.py is absent on this worktree;
this module is the contracted verifier, not a wrapper around a missing file.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
LIVE_EVENTS = REPO / "command-center" / "events" / "EVENTS.jsonl"
GENESIS = "0" * 64
CHAIN_EXCLUDE = frozenset({"prev_sha256", "prev_hash", "prev", "sha256", "hash"})
CANARY_SECRET = "ARC0086-CANARY-SECRET"
REDACTED_PATH = "[REDACTED:personal-path]"
ENFORCEMENT_ID = "hash-chain-prev_sha256-sha256"
SCHEMA_VERSION = 1

REQUIRED_FIELDS = (
    "event_id",
    "seq",
    "ts",
    "actor",
    "unit_id",
    "phase",
    "from_state",
    "to_state",
    "correlation_id",
    "causality_id",
    "substrate",
    "writer_id",
    "payload",
    "redactions",
)

SECRET_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pem-private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github-pat", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("bearer-token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}")),
    (
        "assigned-secret",
        re.compile(
            r"(?i)(?:api[_-]?key|secret|password|passwd|authorization)\s*[:=]\s*\S+"
        ),
    ),
)

HOME_RE = re.compile(
    r"(?:"
    r"/home/[^/\s\"']+"
    r"|/Users/[^/\s\"']+"
    r"|[A-Za-z]:[\\/]Users[\\/][^\\/\s\"']+"
    r")"
)


class SecretRejected(ValueError):
    """Raised when a write carries a secret; the durable log must not change."""


class ChainBroken(ValueError):
    """Raised when append would extend a broken or unchained prefix."""


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chain_body(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: rec[k] for k in rec if k not in CHAIN_EXCLUDE}


def link_digest(prev: str, rec: dict[str, Any]) -> str:
    return sha256_text(f"{prev}\n{canon(chain_body(rec))}")


def is_live_events(path: Path) -> bool:
    try:
        return path.resolve() == LIVE_EVENTS.resolve()
    except OSError:
        return False


def walk_strings(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(obj, str):
        found.append((prefix or "$", obj))
    elif isinstance(obj, dict):
        for key, val in obj.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            found.extend(walk_strings(val, child))
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            child = f"{prefix}[{idx}]"
            found.extend(walk_strings(val, child))
    return found


def secret_hits(text: str) -> list[str]:
    hits: list[str] = []
    if CANARY_SECRET in text:
        hits.append("canary-secret")
    for name, rx in SECRET_RES:
        if rx.search(text):
            hits.append(name)
    return hits


def find_secrets(obj: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path, text in walk_strings(obj):
        kinds = secret_hits(text)
        if kinds:
            out.append({"path": path, "kinds": kinds})
    return out


def redact_personal_paths(obj: Any) -> tuple[Any, list[dict[str, str]]]:
    redactions: list[dict[str, str]] = []

    def walk(node: Any, prefix: str) -> Any:
        if isinstance(node, str):
            if HOME_RE.search(node):
                redactions.append(
                    {
                        "path": prefix or "$",
                        "kind": "personal-path",
                        "action": "redact",
                    }
                )
                return HOME_RE.sub(REDACTED_PATH, node)
            return node
        if isinstance(node, dict):
            return {
                key: walk(val, f"{prefix}.{key}" if prefix else str(key))
                for key, val in node.items()
            }
        if isinstance(node, list):
            return [walk(val, f"{prefix}[{idx}]") for idx, val in enumerate(node)]
        return node

    return walk(obj, ""), redactions


def parse_ts(ts: str) -> datetime:
    text = str(ts).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"timestamp-not-iso8601:{ts!r}") from exc
    if moment.tzinfo is None:
        raise ValueError(f"timestamp-missing-timezone:{ts!r}")
    return moment


def encode_ts(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def event_record_schema() -> dict[str, Any]:
    hex64 = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "command-center/schema/event-record.schema.json",
        "title": "Append-only event record (ARC-0086)",
        "type": "object",
        "additionalProperties": False,
        "required": list(REQUIRED_FIELDS) + ["prev_sha256", "sha256", "schema_version"],
        "properties": {
            "schema_version": {"type": "integer", "const": SCHEMA_VERSION},
            "event_id": {"type": "string", "minLength": 3},
            "seq": {"type": "integer", "minimum": 1},
            "ts": {
                "type": "string",
                "description": "RFC3339 / ISO-8601 datetime with explicit timezone.",
                "minLength": 20,
            },
            "actor": {"type": "string", "minLength": 1},
            "unit_id": {"type": "string", "minLength": 1},
            "phase": {"type": "string", "minLength": 1},
            "from_state": {"type": "string", "minLength": 1},
            "to_state": {"type": "string", "minLength": 1},
            "correlation_id": {"type": "string", "minLength": 1},
            "causality_id": {
                "type": "string",
                "minLength": 1,
                "description": "Parent event_id this record happens-after, or 'genesis'.",
            },
            "substrate": {"type": "string", "minLength": 1},
            "writer_id": {"type": "string", "minLength": 1},
            "payload": {"type": "object"},
            "redactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "kind", "action"],
                    "properties": {
                        "path": {"type": "string"},
                        "kind": {"type": "string"},
                        "action": {"type": "string"},
                    },
                },
            },
            "prev_sha256": hex64,
            "sha256": hex64,
        },
    }


def missing_required(obj: dict[str, Any]) -> list[str]:
    need = list(REQUIRED_FIELDS) + ["prev_sha256", "sha256"]
    return [name for name in need if name not in obj]


def classify_object(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {
            "class": "bad-record",
            "reason": f"not-object:{type(obj).__name__}",
        }
    secrets = find_secrets(obj)
    if secrets:
        return {
            "class": "bad-record",
            "reason": "secret-in-durable-bytes",
            "secrets": secrets,
        }
    missing = missing_required(obj)
    if missing:
        return {
            "class": "schema-gap",
            "reason": "missing-required-fields",
            "missing_fields": missing,
            "keys": sorted(obj),
        }
    try:
        parse_ts(str(obj.get("ts")))
    except ValueError as exc:
        return {"class": "bad-record", "reason": str(exc)}
    seq = obj.get("seq")
    if not isinstance(seq, int) or seq < 1:
        return {"class": "bad-record", "reason": "seq-not-positive-int"}
    if not isinstance(obj.get("payload"), dict):
        return {"class": "bad-record", "reason": "payload-not-object"}
    prev = obj.get("prev_sha256")
    digest = obj.get("sha256")
    if not (
        isinstance(prev, str)
        and re.fullmatch(r"[0-9a-f]{64}", prev)
        and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        return {"class": "bad-record", "reason": "chain-fields-not-sha256-hex"}
    return {"class": "parse-ok", "reason": "contract-shape", "event_id": obj.get("event_id")}


def split_jsonl(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def parse_and_classify(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": "command-center/events/EVENTS.jsonl"
        if is_live_events(path)
        else str(path),
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "line_count": 0,
        "blank_lines": 0,
        "records_parsed": 0,
        "parse_failures": 0,
        "schema_gaps": 0,
        "bad_records": 0,
        "parse_ok": 0,
        "classifications": [],
    }
    if not path.is_file():
        result["note"] = (
            "File absent. Zero lines parsed. Absence is not a parse failure."
        )
        return result
    if path.stat().st_size == 0:
        result["note"] = (
            "File present and empty. Zero lines parsed. Empty is not a parse failure."
        )
        return result
    text = path.read_text(encoding="utf-8")
    raw_lines = split_jsonl(text)
    result["line_count"] = len(raw_lines)
    for idx, line in enumerate(raw_lines, 1):
        if not line.strip():
            result["blank_lines"] += 1
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            result["parse_failures"] += 1
            result["bad_records"] += 1
            result["classifications"].append(
                {
                    "line": idx,
                    "class": "bad-record",
                    "reason": f"unparseable:{exc.msg}",
                }
            )
            continue
        verdict = classify_object(obj)
        result["classifications"].append({"line": idx, **verdict})
        if verdict["class"] == "schema-gap":
            result["schema_gaps"] += 1
            result["records_parsed"] += 1
        elif verdict["class"] == "bad-record":
            result["bad_records"] += 1
            result["parse_failures"] += 1
            result["records_parsed"] += 1
        else:
            result["parse_ok"] += 1
            result["records_parsed"] += 1
    return result


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in split_jsonl(path.read_text(encoding="utf-8")):
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError("non-object-line")
        records.append(obj)
    return records


def verify_chain(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Recompute each link from GENESIS. Names the first broken index."""
    prev = GENESIS
    links_ok = 0
    broken_at: int | None = None
    broken_event_id: str | None = None
    reasons: list[dict[str, Any]] = []
    for idx, rec in enumerate(records):
        stated_prev = rec.get("prev_sha256")
        stated_hash = rec.get("sha256")
        digest = link_digest(prev, rec)
        prev_ok = stated_prev == prev
        hash_ok = stated_hash == digest
        if prev_ok and hash_ok:
            links_ok += 1
            prev = stated_hash
            continue
        if broken_at is None:
            broken_at = idx
            broken_event_id = str(rec.get("event_id") or "")
        reasons.append(
            {
                "index": idx,
                "event_id": rec.get("event_id"),
                "prev_ok": prev_ok,
                "hash_ok": hash_ok,
                "stated_prev": stated_prev,
                "expected_prev": prev,
                "stated_sha256": stated_hash,
                "recomputed_sha256": digest,
            }
        )
        prev = stated_hash if isinstance(stated_hash, str) else digest
    return {
        "ok": broken_at is None,
        "record_count": len(records),
        "links_ok": links_ok,
        "links_broken": len(reasons),
        "broken_at": broken_at,
        "broken_event_id": broken_event_id,
        "reasons": reasons,
        "enforcement": ENFORCEMENT_ID,
    }


def _per_writer_seq(records: list[dict[str, Any]], writer_id: str) -> int:
    seqs = [
        int(rec["seq"])
        for rec in records
        if rec.get("writer_id") == writer_id and isinstance(rec.get("seq"), int)
    ]
    return (max(seqs) + 1) if seqs else 1


def append_record(
    path: Path,
    *,
    actor: str,
    unit_id: str,
    phase: str,
    from_state: str,
    to_state: str,
    correlation_id: str,
    payload: dict[str, Any] | None = None,
    causality_id: str | None = None,
    writer_id: str = "default",
    substrate: str = "headless-linux",
    ts: str | None = None,
    allow_live: bool = False,
) -> dict[str, Any]:
    """Write one contracted event. Secrets reject; personal paths redact."""
    if not allow_live and is_live_events(path):
        raise RuntimeError("refusing to write command-center/events/EVENTS.jsonl")
    incoming = dict(payload or {})
    scan = {
        "actor": actor,
        "unit_id": unit_id,
        "phase": phase,
        "from_state": from_state,
        "to_state": to_state,
        "correlation_id": correlation_id,
        "payload": incoming,
    }
    secrets = find_secrets(scan)
    if secrets:
        raise SecretRejected(
            "secret-rejected-at-write:"
            + ",".join(f"{h['path']}:{':'.join(h['kinds'])}" for h in secrets)
        )
    redacted_payload, redactions = redact_personal_paths(incoming)
    existing = load_records(path) if path.is_file() else []
    if existing:
        chain = verify_chain(existing)
        if not chain["ok"]:
            raise ChainBroken(f"broken-at:{chain['broken_at']}")
        unchained = [
            rec for rec in existing if not rec.get("sha256") or not rec.get("prev_sha256")
        ]
        if unchained:
            raise ChainBroken("unchained-prefix")
    seq = _per_writer_seq(existing, writer_id)
    parent = causality_id
    if parent is None:
        parent = str(existing[-1]["event_id"]) if existing else "genesis"
    moment = parse_ts(ts) if ts else datetime.now(timezone.utc)
    stamp = encode_ts(moment)
    event_id = f"{writer_id}:{seq}"
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "seq": seq,
        "ts": stamp,
        "actor": actor,
        "unit_id": unit_id,
        "phase": phase,
        "from_state": from_state,
        "to_state": to_state,
        "correlation_id": correlation_id,
        "causality_id": parent,
        "substrate": substrate,
        "writer_id": writer_id,
        "payload": redacted_payload,
        "redactions": redactions,
    }
    prev = existing[-1]["sha256"] if existing else GENESIS
    record["prev_sha256"] = prev
    record["sha256"] = link_digest(prev, record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
    return record


def tamper_line(path: Path, index: int, field: str, value: Any) -> dict[str, Any]:
    """In-place rewrite of one historical JSONL object. Line count unchanged."""
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    parts = raw.split(b"\n")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    if index < 0 or index >= len(parts):
        raise IndexError(index)
    obj = json.loads(parts[index].decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("tamper-target-not-object")
    cursor: Any = obj
    keys = field.split(".")
    for key in keys[:-1]:
        cursor = cursor[key]
    cursor[keys[-1]] = value
    parts[index] = json.dumps(obj, sort_keys=True, ensure_ascii=True).encode("utf-8")
    path.write_bytes(b"\n".join(parts) + b"\n")
    return obj


def happens_before(
    ancestor: dict[str, Any],
    descendant: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> bool:
    seen: set[str] = set()
    cur: dict[str, Any] | None = descendant
    target = str(ancestor.get("event_id") or "")
    while cur is not None:
        cid = str(cur.get("causality_id") or "")
        if cid in {"", "genesis"}:
            return False
        if cid == target:
            return True
        if cid in seen:
            return False
        seen.add(cid)
        cur = by_id.get(cid)
    return False


def causal_order(records: list[dict[str, Any]]) -> list[str]:
    """Topological order by causality_id. Ties broken by event_id, never by ts."""
    by_id = {str(rec["event_id"]): rec for rec in records}
    ids = [str(rec["event_id"]) for rec in records]
    remaining = set(ids)
    ordered: list[str] = []
    while remaining:
        ready = []
        for eid in remaining:
            rec = by_id[eid]
            cid = str(rec.get("causality_id") or "genesis")
            if cid in {"", "genesis"} or cid not in remaining:
                ready.append(eid)
        if not ready:
            ready = sorted(remaining)
        ready.sort()
        pick = ready[0]
        ordered.append(pick)
        remaining.remove(pick)
    return ordered


def wall_clock_order(records: list[dict[str, Any]]) -> list[str]:
    return [
        str(rec["event_id"])
        for rec in sorted(records, key=lambda r: (str(r.get("ts") or ""), str(r["event_id"])))
    ]
