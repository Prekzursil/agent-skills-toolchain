"""Council-claim registration into the program claim registry (IMP-0259 / AUD-0037).

A council transcript carries claims inside its turns. This module

* extracts them into flat claim records with provenance (:func:`extract_claims`),
* validates the record schema and the ``VERIFIED``-needs-a-resolvable-anchor
  invariant (:func:`validate_record`, :func:`resolve_anchor`),
* moves records through the verification-status state machine
  (:data:`TRANSITIONS`, :func:`transition`),
* upserts them by id into ``CLAIM-REGISTRY.json`` without dropping records that
  were already there (:func:`emit`, :func:`load_registry`),
* measures decision-to-registry coverage from the written bytes
  (:func:`coverage_report`), and
* runs the anchor-resolution pass every VERIFIED record must survive
  (:func:`resolution_pass`).

Anchors are ``"<repo-relative path>:<start>[-<end>]"`` strings (or mappings with
``path`` / ``start_line`` / ``end_line``). Mechanical resolution asks only two
questions: does the file exist, and does it have at least ``start`` lines. The
semantic SUPPORTS / MENTIONS-ONLY read of the cited span is AUD-0037's job; the
AUD-0037 engine calls :func:`resolve_anchor` and requires its verdict to agree
with its own resolver, so the line-counting rules here must not drift from it.
Nothing in this module writes timestamps or absolute paths into a registry.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- schema

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "text",
    "canonical_mechanism",
    "evidence_anchors",
    "load_bearing",
    "settling_probe",
    "verification_status",
    "council_id",
    "turn_id",
    "speaker",
)
"""Fields every registered council claim must carry (claim body + provenance)."""

VERIFICATION_STATUSES: tuple[str, ...] = (
    "UNVERIFIED",
    "INFERRED",
    "VERIFIED",
    "REJECTED",
    "DEFERRED",
)

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "UNVERIFIED": ("INFERRED", "VERIFIED", "REJECTED", "DEFERRED"),
    "INFERRED": ("UNVERIFIED", "VERIFIED", "REJECTED", "DEFERRED"),
    "VERIFIED": ("UNVERIFIED", "INFERRED", "REJECTED", "DEFERRED"),
    # A rejected or parked claim must be re-examined (UNVERIFIED / INFERRED)
    # before it can become VERIFIED again; there is no direct edge.
    "REJECTED": ("UNVERIFIED", "INFERRED", "DEFERRED"),
    "DEFERRED": ("UNVERIFIED", "INFERRED", "REJECTED"),
}
"""Legal status edges: 18 in total, none of them into VERIFIED from REJECTED/DEFERRED."""

REGISTRY_SCHEMA_VERSION = 1
REGISTRY_PURPOSE = (
    "Every load-bearing claim this command center makes, with the SOURCE probe "
    "that produced it and the mechanically independent VERIFIER that checked it."
)

_ANCHOR_RE = re.compile(r"^(?P<path>.+?)(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?$")
_MAX_ANCHOR_BYTES = 2_000_000


# --------------------------------------------------------------------------- anchors


def parse_anchor(raw: Any) -> dict[str, Any]:
    """Normalise an anchor into ``{"path", "start_line", "end_line"}``.

    Accepts ``"path"``, ``"path:12"``, ``"path:12-20"`` or a mapping with
    ``path`` and ``start_line``/``line`` (+ optional ``end_line``). Backslashes
    are normalised to ``/``. Raises :class:`ValueError` for an empty anchor.
    """
    if isinstance(raw, Mapping):
        path = str(raw.get("path") or "").replace("\\", "/").strip()
        if not path:
            raise ValueError(f"anchor missing path: {raw!r}")
        start = raw.get("start_line", raw.get("line"))
        end = raw.get("end_line", start)
        start_i = int(start) if start not in (None, "") else None
        end_i = int(end) if end not in (None, "") else start_i
        return {"path": path, "start_line": start_i, "end_line": end_i}
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"empty anchor: {raw!r}")
    text = raw.replace("\\", "/").strip()
    match = _ANCHOR_RE.match(text)
    if not match:
        return {"path": text, "start_line": None, "end_line": None}
    start = match.group("start")
    end = match.group("end")
    start_i = int(start) if start else None
    end_i = int(end) if end else start_i
    return {"path": match.group("path"), "start_line": start_i, "end_line": end_i}


def format_anchor(parsed: Mapping[str, Any]) -> str:
    """Inverse of :func:`parse_anchor` for the string form."""
    path = str(parsed.get("path") or "")
    start = parsed.get("start_line")
    end = parsed.get("end_line")
    if start is None:
        return path
    if end is None or end == start:
        return f"{path}:{start}"
    return f"{path}:{start}-{end}"


def count_lines(path: Path, max_bytes: int = _MAX_ANCHOR_BYTES) -> int:
    """Line count with CRLF folded to LF; a trailing newline does not add a line."""
    data = path.read_bytes()[:max_bytes].replace(b"\r\n", b"\n")
    text = data.decode("utf-8", "replace")
    if not text:
        return 0
    if text.endswith("\n"):
        return text.count("\n")
    return text.count("\n") + 1


def resolve_anchor(raw: Any, *, root: Path | str | None = None) -> dict[str, Any]:
    """Mechanically resolve one anchor: file exists and has >= ``start_line`` lines.

    Returns ``path``, ``start_line``, ``end_line``, ``exists``, ``line_count``,
    ``end_line_ok``, ``resolved`` and ``reason`` (``"ok"``, ``"missing-file"`` or
    ``"line-past-eof"``). Relative paths resolve against ``root`` (default: the
    current working directory). This is not a semantic read of the span.
    """
    parsed = parse_anchor(raw)
    rel = parsed["path"]
    path = Path(rel)
    if not path.is_absolute():
        path = Path(root) / rel if root is not None else Path.cwd() / rel
    exists = path.is_file()
    line_count = count_lines(path) if exists else 0
    start = parsed["start_line"]
    end = parsed["end_line"]
    line_ok = start is None or (exists and line_count >= start)
    end_ok = end is None or (exists and line_count >= end)
    resolved = bool(exists and line_ok)
    if resolved:
        reason = "ok"
    elif not exists:
        reason = "missing-file"
    else:
        reason = "line-past-eof"
    return {
        "path": rel,
        "start_line": start,
        "end_line": end,
        "exists": exists,
        "line_count": line_count,
        "end_line_ok": bool(end_ok),
        "resolved": resolved,
        "reason": reason,
    }


def claim_anchors(record: Mapping[str, Any]) -> list[Any]:
    """The anchor list of a record (``evidence_anchors``), tolerant of a scalar."""
    raw = record.get("evidence_anchors")
    if raw is None:
        raw = record.get("anchors")
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return [raw]


# --------------------------------------------------------------------------- extraction


def _require_mapping(value: Any, what: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{what} must be a JSON object, got {type(value).__name__}")
    return value


def influential_ids(council: Mapping[str, Any]) -> list[str]:
    """Ids that influenced the decision: the decision's own list plus load-bearing claims."""
    council = _require_mapping(council, "council")
    decision = council.get("decision") or {}
    listed = decision.get("influencing_claim_ids") if isinstance(decision, Mapping) else None
    out: list[str] = []
    seen: set[str] = set()
    for cid in listed or []:
        sid = str(cid)
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    for turn in council.get("turns") or []:
        if not isinstance(turn, Mapping):
            continue
        for claim in turn.get("claims") or []:
            if isinstance(claim, Mapping) and claim.get("load_bearing") is True:
                sid = str(claim.get("id"))
                if sid not in seen:
                    seen.add(sid)
                    out.append(sid)
    return out


def extract_claims(council: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten every claim in ``council["turns"]`` into a registry record.

    Each record keeps the claim body, gains ``council_id`` / ``turn_id`` /
    ``speaker`` provenance and an ``influential`` flag (decision input or
    load-bearing). Transcript order is preserved. Duplicate ids, missing ids and
    non-object turns/claims raise :class:`ValueError` so a corrupt transcript is
    never silently registered.
    """
    council = _require_mapping(council, "council")
    council_id = str(council.get("council_id") or council.get("id") or "")
    if not council_id:
        raise ValueError("council has no council_id")
    turns = council.get("turns")
    if not isinstance(turns, Sequence) or isinstance(turns, (str, bytes)):
        raise ValueError("council.turns must be a list")
    influential = set(influential_ids(council))
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for t_index, turn in enumerate(turns):
        turn = _require_mapping(turn, f"turns[{t_index}]")
        turn_id = str(turn.get("id") or f"t{t_index + 1}")
        speaker = str(turn.get("speaker") or "")
        claims = turn.get("claims") or []
        if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
            raise ValueError(f"turns[{t_index}].claims must be a list")
        for c_index, claim in enumerate(claims):
            claim = _require_mapping(claim, f"turns[{t_index}].claims[{c_index}]")
            cid = str(claim.get("id") or "").strip()
            if not cid:
                raise ValueError(f"claim without id in turn {turn_id}")
            if cid in seen:
                raise ValueError(f"duplicate claim id {cid!r} in council {council_id}")
            seen.add(cid)
            anchors = claim_anchors(claim)
            record: dict[str, Any] = dict(claim)
            record.update(
                {
                    "id": cid,
                    "text": str(claim.get("text") or claim.get("claim") or "").strip(),
                    "canonical_mechanism": str(claim.get("canonical_mechanism") or ""),
                    "evidence_anchors": [
                        a if isinstance(a, str) else dict(a) if isinstance(a, Mapping) else str(a)
                        for a in anchors
                    ],
                    "load_bearing": bool(claim.get("load_bearing", False)),
                    "settling_probe": str(claim.get("settling_probe") or ""),
                    "verification_status": str(
                        claim.get("verification_status") or "UNVERIFIED"
                    ).upper(),
                    "council_id": council_id,
                    "turn_id": turn_id,
                    "speaker": speaker,
                    "influential": cid in influential,
                }
            )
            records.append(record)
    return records


# --------------------------------------------------------------------------- validation


def validate_record(record: Mapping[str, Any], *, root: Path | str | None = None) -> list[str]:
    """Return the list of schema errors for one record (empty when valid).

    Codes: ``missing-field:<f>``, ``bad-type:<f>``, ``unknown-status:<s>``,
    ``bad-anchor:<repr>``, ``verified-without-anchor`` and, when ``root`` is
    given, ``unresolved-anchor:<anchor>:<reason>`` for every anchor of a
    VERIFIED record that does not resolve on disk.
    """
    if not isinstance(record, Mapping):
        return [f"bad-type:record:{type(record).__name__}"]
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"missing-field:{field}")
    cid = record.get("id")
    if "id" in record and (not isinstance(cid, str) or not cid.strip()):
        errors.append("bad-type:id")
    if "text" in record and (not isinstance(record.get("text"), str) or not record["text"].strip()):
        errors.append("bad-type:text")
    if "load_bearing" in record and not isinstance(record.get("load_bearing"), bool):
        errors.append("bad-type:load_bearing")
    anchors_raw = record.get("evidence_anchors")
    if "evidence_anchors" in record and not isinstance(anchors_raw, (list, tuple)):
        errors.append("bad-type:evidence_anchors")
    status = record.get("verification_status")
    if "verification_status" in record and status not in VERIFICATION_STATUSES:
        errors.append(f"unknown-status:{status}")

    anchors = claim_anchors(record) if isinstance(anchors_raw, (list, tuple)) else []
    parsed: list[tuple[Any, dict[str, Any] | None]] = []
    for anchor in anchors:
        try:
            parsed.append((anchor, parse_anchor(anchor)))
        except ValueError:
            errors.append(f"bad-anchor:{anchor!r}")
            parsed.append((anchor, None))

    if status == "VERIFIED":
        if not anchors:
            errors.append("verified-without-anchor")
        elif root is not None:
            for anchor, meta in parsed:
                if meta is None:
                    continue
                res = resolve_anchor(anchor, root=root)
                if not res["resolved"]:
                    errors.append(f"unresolved-anchor:{format_anchor(meta)}:{res['reason']}")
    return errors


def transition(
    record: Mapping[str, Any], new_status: str, *, root: Path | str | None = None
) -> dict[str, Any]:
    """Return a copy of ``record`` moved to ``new_status``.

    Raises :class:`ValueError` ``"illegal transition A -> B"`` for an edge that
    is not in :data:`TRANSITIONS`, and ``"cannot enter VERIFIED: [...]"`` when the
    would-be VERIFIED record fails :func:`validate_record` (no anchors, or an
    anchor that does not resolve under ``root``). The input is not mutated; the
    move is appended to the record's ``status_history``.
    """
    if not isinstance(record, Mapping):
        raise ValueError("record must be a mapping")
    target = str(new_status or "").upper()
    if target not in VERIFICATION_STATUSES:
        raise ValueError(f"unknown status {new_status!r}")
    current = str(record.get("verification_status") or "UNVERIFIED").upper()
    if current not in VERIFICATION_STATUSES:
        raise ValueError(f"record has unknown status {current!r}")
    out = dict(record)
    if target == current:
        return out
    if target not in TRANSITIONS[current]:
        raise ValueError(f"illegal transition {current} -> {target}")
    out["verification_status"] = target
    if target == "VERIFIED":
        problems = validate_record(out, root=root)
        if problems:
            raise ValueError(f"cannot enter VERIFIED: {problems}")
    history = list(record.get("status_history") or [])
    history.append({"from": current, "to": target})
    out["status_history"] = history
    return out


def mark_verified_unanchored(record: Mapping[str, Any]) -> dict[str, Any]:
    """Negative-control mutation: force VERIFIED with no anchors, bypassing :func:`transition`.

    The result is deliberately invalid; :func:`validate_record` reports
    ``verified-without-anchor`` and :func:`resolution_pass` fires on it.
    """
    mutant = dict(record)
    mutant["verification_status"] = "VERIFIED"
    mutant["evidence_anchors"] = []
    return mutant


# --------------------------------------------------------------------------- registry


def _empty_registry() -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "purpose": REGISTRY_PURPOSE,
        "claims": [],
    }


def load_registry(path: Path | str) -> dict[str, Any]:
    """Load ``CLAIM-REGISTRY.json``; a missing file is an empty registry.

    The document must be a JSON object whose ``claims`` is a list of objects;
    anything else raises :class:`ValueError` rather than being coerced.
    """
    target = Path(path)
    if not target.is_file():
        return _empty_registry()
    doc = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{target}: registry is not a JSON object")
    claims = doc.get("claims")
    if claims is None:
        doc["claims"] = []
    elif not isinstance(claims, list) or not all(isinstance(c, Mapping) for c in claims):
        raise ValueError(f"{target}: registry.claims must be a list of objects")
    return doc


def _registry_ids(registry: Mapping[str, Any]) -> set[str]:
    return {str(c.get("id")) for c in registry.get("claims") or [] if isinstance(c, Mapping)}


def emit(
    council: Mapping[str, Any],
    *,
    registry_path: Path | str,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Extract, validate and upsert a council's claims into the registry file.

    Existing records (any id) are kept; records whose id is already present are
    replaced in place, new ones are appended in transcript order. A record with
    schema errors aborts the write with :class:`ValueError`. Returns the emitted
    records and a ``coverage`` block (``registry_size``, ``emitted_ids``,
    ``inserted_ids``, ``updated_ids``) computed from the bytes just written.
    """
    records = extract_claims(council)
    problems = {r["id"]: validate_record(r, root=root) for r in records}
    bad = {cid: errs for cid, errs in problems.items() if errs}
    if bad:
        raise ValueError(f"refusing to register invalid claims: {bad}")

    target = Path(registry_path)
    registry = load_registry(target)
    existing: list[dict[str, Any]] = [dict(c) for c in registry.get("claims") or []]
    index = {str(c.get("id")): i for i, c in enumerate(existing)}
    inserted: list[str] = []
    updated: list[str] = []
    for rec in records:
        if rec["id"] in index:
            existing[index[rec["id"]]] = dict(rec)
            updated.append(rec["id"])
        else:
            index[rec["id"]] = len(existing)
            existing.append(dict(rec))
            inserted.append(rec["id"])
    registry["claims"] = existing
    registry.setdefault("schema_version", REGISTRY_SCHEMA_VERSION)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    written = load_registry(target)
    return {
        "claims": records,
        "coverage": {
            "registry_size": len(written.get("claims") or []),
            "emitted_ids": [r["id"] for r in records],
            "inserted_ids": inserted,
            "updated_ids": updated,
        },
    }


def coverage_report(council: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    """Decision-to-registry coverage measured against a loaded registry.

    ``influential`` claims are the decision's ``influencing_claim_ids`` plus every
    load-bearing claim; each must be present in ``registry["claims"]``.
    Non-influential claims are reported separately and never counted as
    misses; ``false_positive_if_required`` lists them, i.e. what a checker that
    demanded every claim would wrongly flag. ``coverage_ratio`` is 1.0 when
    there is nothing influential to cover.
    """
    council = _require_mapping(council, "council")
    registry = _require_mapping(registry, "registry")
    registered = _registry_ids(registry)
    influential = influential_ids(council)
    all_ids: list[str] = []
    for turn in council.get("turns") or []:
        if not isinstance(turn, Mapping):
            continue
        for claim in turn.get("claims") or []:
            if isinstance(claim, Mapping) and claim.get("id") is not None:
                all_ids.append(str(claim.get("id")))
    influential_set = set(influential)
    non_influential = [cid for cid in all_ids if cid not in influential_set]
    unregistered = [cid for cid in influential if cid not in registered]
    registered_count = len(influential) - len(unregistered)
    ratio = 1.0 if not influential else round(registered_count / len(influential), 6)
    return {
        "influential_count": len(influential),
        "registered_influential_count": registered_count,
        "unregistered_influential": unregistered,
        "non_influential_ids": non_influential,
        "false_positive_if_required": non_influential,
        "coverage_ratio": ratio,
        "registry_size": len(registry.get("claims") or []),
    }


# --------------------------------------------------------------------------- resolution pass


def resolution_pass(
    claims: Sequence[Mapping[str, Any]], *, root: Path | str | None = None
) -> dict[str, Any]:
    """Walk every VERIFIED claim and resolve each of its anchors on disk.

    A VERIFIED claim with no anchors, or with any anchor that is
    ``missing-file`` / ``line-past-eof`` / unparseable, is a failure. Returns
    ``checked`` (number of VERIFIED claims), ``fired``, ``fired_count``,
    ``failures`` (per claim: ``id``, ``reasons``, the failing ``anchors`` with
    their resolution rows) and ``silent`` (ids that passed).
    """
    failures: list[dict[str, Any]] = []
    silent: list[str] = []
    checked = 0
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        if str(claim.get("verification_status") or "").upper() != "VERIFIED":
            continue
        checked += 1
        cid = str(claim.get("id"))
        anchors = claim_anchors(claim)
        if not anchors:
            failures.append({"id": cid, "reasons": ["verified-without-anchor"], "anchors": []})
            continue
        bad_rows: list[dict[str, Any]] = []
        for anchor in anchors:
            try:
                row = resolve_anchor(anchor, root=root)
            except ValueError as exc:
                row = {
                    "path": None,
                    "start_line": None,
                    "end_line": None,
                    "exists": False,
                    "line_count": 0,
                    "end_line_ok": False,
                    "resolved": False,
                    "reason": "bad-anchor",
                    "error": str(exc),
                }
            row["anchor"] = anchor if isinstance(anchor, (str, dict)) else str(anchor)
            if not row["resolved"]:
                bad_rows.append(row)
        if bad_rows:
            failures.append(
                {
                    "id": cid,
                    "reasons": [r["reason"] for r in bad_rows],
                    "anchors": bad_rows,
                    "anchor_count": len(anchors),
                }
            )
        else:
            silent.append(cid)
    return {
        "checked": checked,
        "fired": bool(failures),
        "fired_count": len(failures),
        "failures": failures,
        "silent": silent,
    }


__all__ = [
    "REQUIRED_FIELDS",
    "TRANSITIONS",
    "VERIFICATION_STATUSES",
    "claim_anchors",
    "count_lines",
    "coverage_report",
    "emit",
    "extract_claims",
    "format_anchor",
    "influential_ids",
    "load_registry",
    "mark_verified_unanchored",
    "parse_anchor",
    "resolution_pass",
    "resolve_anchor",
    "transition",
    "validate_record",
]
