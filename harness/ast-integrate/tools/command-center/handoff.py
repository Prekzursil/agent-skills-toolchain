"""Typed handoff record: structured sections only, never a raw-output prefix.

IMP-0414 contract (catalog question_or_target):
  the handoff API must accept only typed sections; a raw string must be
  rejected at the boundary. Goal is re-anchored as section 1 even when the
  caller passes it last. A handoff missing that goal fails completeness.

The catalog path command-center/schema/handoff.schema.json is a generated
$ref shim (no constraints of its own). The live type/object and
sections[0].kind==goal rules live here so a raw string and a nongoal-first
document are rejected at this boundary, not by a prompt-level plea.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator

__all__ = [
    "HANDOFF_SCHEMA",
    "Handoff",
    "HandoffBoundaryError",
    "HandoffCompletenessError",
    "TypedSection",
    "accept_handoff",
    "capture_refusal",
    "load_handoff",
    "make_section",
    "prefix_for_next_agent",
    "validate_document",
]

SCHEMA_VERSION = 1
KIND = "typed-handoff"
BOUNDARY = "typed-handoff"
SECTION_KINDS = ("goal", "context", "evidence", "residual", "findings", "next-action")

# Draft 2020-12: type=object rejects a string root; prefixItems const "goal"
# produces jsonschema's "'goal' was expected" on a nongoal first section.
HANDOFF_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ast-integrate.invalid/tools/command-center/handoff.schema.json",
    "title": "Typed handoff record",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "kind",
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "sections",
    ],
    "properties": {
        "kind": {"const": KIND},
        "schema_version": {"type": "integer", "const": SCHEMA_VERSION},
        "unit_id": {"type": "string", "minLength": 1},
        "state": {"type": "string", "minLength": 1},
        "sentinel": {"type": "string", "minLength": 1},
        "sections": {
            "type": "array",
            "minItems": 1,
            "prefixItems": [
                {
                    "type": "object",
                    "required": ["kind", "ordinal", "id", "title", "body"],
                    "properties": {
                        "kind": {"const": "goal"},
                        "ordinal": {"const": 1},
                        "id": {"type": "string", "minLength": 1},
                        "title": {"type": "string"},
                        "body": {"type": "object"},
                        "evidence_anchors": {"type": "array"},
                    },
                }
            ],
            "items": {
                "type": "object",
                "required": ["kind", "ordinal", "id"],
                "properties": {
                    "kind": {"type": "string", "not": {"const": "goal"}},
                    "ordinal": {"type": "integer", "minimum": 2},
                    "id": {"type": "string", "minLength": 1},
                    "title": {"type": "string"},
                    "body": {},
                    "evidence_anchors": {"type": "array"},
                },
            },
        },
    },
}

_VALIDATOR = Draft202012Validator(HANDOFF_SCHEMA)


class HandoffBoundaryError(TypeError):
    """Raw str/bytes (or any untyped payload) crossed the typed-handoff boundary."""

    def __init__(self, message: str, *, trace: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.trace = dict(trace or {})


class HandoffCompletenessError(ValueError):
    """Typed document is missing the re-anchored goal section."""


@dataclass(frozen=True)
class TypedSection:
    kind: str
    title: str
    body: dict[str, Any]
    id: str
    evidence_anchors: tuple[dict[str, Any], ...] = ()
    ordinal: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "ordinal": self.ordinal,
            "title": self.title,
            "body": json.loads(json.dumps(self.body)),
            "evidence_anchors": [dict(a) for a in self.evidence_anchors],
        }


@dataclass
class Handoff:
    """Accepted typed handoff. prefix_for_next_agent consumes this, never a string."""

    _data: dict[str, Any] = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._data))

    def write(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self._data, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return out


def make_section(
    kind: str,
    title: str,
    body: Mapping[str, Any],
    anchors: Sequence[Mapping[str, Any]] | None = None,
    id: str | None = None,
) -> TypedSection:
    if not isinstance(kind, str) or not kind.strip():
        raise HandoffCompletenessError("section kind must be a non-empty string")
    if not isinstance(title, str):
        raise HandoffCompletenessError("section title must be a string")
    if not isinstance(body, Mapping):
        raise HandoffBoundaryError(
            "section body must be a mapping, not a raw string",
            trace=_raw_trace(body, via="make_section"),
        )
    sid = id if id is not None else kind
    anchor_tuples = tuple(dict(a) for a in (anchors or ()))
    return TypedSection(
        kind=kind,
        title=title,
        body=dict(body),
        id=str(sid),
        evidence_anchors=anchor_tuples,
    )


def validate_document(document: Any) -> list[str]:
    """Return schema error strings; empty list means the document is valid.

    A raw string root is invalid (type=object). A document whose first section
    is not a goal is invalid (prefixItems const).
    """
    errors: list[str] = []
    for err in _VALIDATOR.iter_errors(document):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return sorted(errors)


def capture_refusal(payload: Any, via: str = "accept_handoff") -> dict[str, Any]:
    """Run the named boundary and return the refusal trace (never raises)."""
    fn = prefix_for_next_agent if via == "prefix_for_next_agent" else accept_handoff
    try:
        fn(payload)
    except HandoffBoundaryError as exc:
        return dict(exc.trace)
    return {
        "boundary": BOUNDARY,
        "error_type": "HandoffBoundaryError",
        "payload_type": type(payload).__name__,
        "reason": f"{via} accepted an untyped payload",
        "refused": False,
        "refused_kind": "none",
    }


def load_handoff(path: str | Path) -> Handoff:
    text = Path(path).read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HandoffBoundaryError(
            f"handoff artifact is not JSON: {exc}",
            trace=_raw_trace(text, via="load_handoff"),
        ) from exc
    return accept_handoff(doc)


def prefix_for_next_agent(handoff: Any) -> tuple[dict[str, Any], ...]:
    """Next-agent prefix: a tuple of typed section objects, never a string."""
    _refuse_raw(handoff, via="prefix_for_next_agent")
    if isinstance(handoff, Handoff):
        sections = list(handoff.to_dict().get("sections") or [])
    elif isinstance(handoff, Mapping):
        live = accept_handoff(dict(handoff))
        sections = list(live.to_dict().get("sections") or [])
    else:
        raise HandoffBoundaryError(
            "prefix_for_next_agent accepts only a Handoff instance",
            trace=_raw_trace(handoff, via="prefix_for_next_agent"),
        )
    if not sections or sections[0].get("kind") != "goal" or sections[0].get("ordinal") != 1:
        raise HandoffCompletenessError(
            "prefix is incomplete: section 1 must be the re-anchored goal"
        )
    out: list[dict[str, Any]] = []
    for item in sections:
        if isinstance(item, (str, bytes, bytearray)):
            raise HandoffBoundaryError(
                "prefix contained a raw string member",
                trace=_raw_trace(item, via="prefix_for_next_agent"),
            )
        if not isinstance(item, Mapping):
            raise HandoffBoundaryError(
                "prefix_for_next_agent accepts only typed section objects",
                trace=_raw_trace(item, via="prefix_for_next_agent"),
            )
        out.append(dict(item))
    return tuple(out)


def accept_handoff(*args: Any, **kwargs: Any) -> Handoff:
    """Accept a typed handoff; refuse raw transcripts at the boundary.

    Call shapes:
      accept_handoff(raw_str)            -> HandoffBoundaryError
      accept_handoff(mapping)            -> Handoff (re-anchors goal)
      accept_handoff(Handoff)            -> Handoff
      accept_handoff(unit_id=..., sections=..., **fields)
    """
    if args and kwargs:
        raise TypeError("accept_handoff: pass either one positional payload or keyword fields")
    if len(args) > 1:
        raise TypeError("accept_handoff: expected at most one positional payload")
    if args:
        payload = args[0]
        _refuse_raw(payload, via="accept_handoff")
        if isinstance(payload, Handoff):
            return accept_handoff(payload.to_dict())
        if isinstance(payload, Mapping):
            return _from_mapping(dict(payload))
        raise HandoffBoundaryError(
            "accept_handoff refuses untyped payloads; typed sections only",
            trace=_raw_trace(payload, via="accept_handoff"),
        )
    return _from_mapping(dict(kwargs))


def _refuse_raw(payload: Any, *, via: str) -> None:
    if isinstance(payload, (str, bytes, bytearray)):
        raise HandoffBoundaryError(
            (
                f"{via} refuses raw str; typed sections only — raw upstream output "
                "cannot become prefix context"
            ),
            trace=_raw_trace(payload, via=via),
        )


def _raw_trace(payload: Any, *, via: str) -> dict[str, Any]:
    if isinstance(payload, (bytes, bytearray)):
        preview_len = len(payload)
        payload_type = type(payload).__name__
    elif isinstance(payload, str):
        preview_len = len(payload)
        payload_type = "str"
    else:
        preview_len = len(repr(payload))
        payload_type = type(payload).__name__
    return {
        "boundary": BOUNDARY,
        "error_type": "HandoffBoundaryError",
        "payload_preview_len": preview_len,
        "payload_type": payload_type,
        "reason": (
            f"{via} refuses raw str; typed sections only — raw upstream output "
            "cannot become prefix context"
        ),
        "refused": True,
        "refused_kind": "raw-string",
    }


def _section_to_dict(section: Any) -> dict[str, Any]:
    if isinstance(section, TypedSection):
        return section.to_dict()
    if isinstance(section, Mapping):
        body = section.get("body", {})
        if isinstance(body, (str, bytes, bytearray)):
            raise HandoffBoundaryError(
                "section body must not be a raw string",
                trace=_raw_trace(body, via="accept_handoff"),
            )
        anchors = section.get("evidence_anchors") or []
        if not isinstance(anchors, Sequence) or isinstance(anchors, (str, bytes, bytearray)):
            anchors = []
        return {
            "id": str(section.get("id") or section.get("kind") or "section"),
            "kind": str(section.get("kind") or ""),
            "ordinal": int(section["ordinal"]) if "ordinal" in section else 0,
            "title": str(section.get("title") or ""),
            "body": dict(body) if isinstance(body, Mapping) else {"value": body},
            "evidence_anchors": [dict(a) for a in anchors if isinstance(a, Mapping)],
        }
    raise HandoffBoundaryError(
        "accept_handoff refuses raw section members; typed sections only",
        trace=_raw_trace(section, via="accept_handoff"),
    )


def _reanchor(sections: Iterable[Any]) -> list[dict[str, Any]]:
    converted = [_section_to_dict(s) for s in sections]
    goals = [s for s in converted if s.get("kind") == "goal"]
    rest = [s for s in converted if s.get("kind") != "goal"]
    if not goals:
        raise HandoffCompletenessError(
            "handoff is incomplete: a re-anchored 'goal' section was expected "
            "and is required as section 1"
        )
    # Last goal wins when the caller passes the re-anchored goal after context.
    ordered = [goals[-1], *rest]
    for index, section in enumerate(ordered, start=1):
        section["ordinal"] = index
    return ordered


def _from_mapping(data: dict[str, Any]) -> Handoff:
    _refuse_raw(data.get("sections"), via="accept_handoff")
    raw_sections = data.get("sections")
    if raw_sections is None:
        raise HandoffCompletenessError(
            "handoff is incomplete: a re-anchored 'goal' section was expected"
        )
    if isinstance(raw_sections, (str, bytes, bytearray)):
        raise HandoffBoundaryError(
            "accept_handoff refuses a raw sections string; typed sections only",
            trace=_raw_trace(raw_sections, via="accept_handoff"),
        )
    if not isinstance(raw_sections, Sequence):
        raise HandoffBoundaryError(
            "sections must be a sequence of typed section objects",
            trace=_raw_trace(raw_sections, via="accept_handoff"),
        )
    ordered = _reanchor(raw_sections)
    unit_id = str(data.get("unit_id") or "")
    sentinel = str(data.get("sentinel") or "")
    if not unit_id:
        raise HandoffCompletenessError("handoff is incomplete: unit_id was expected")
    if not sentinel:
        raise HandoffCompletenessError("handoff is incomplete: sentinel was expected")
    doc: dict[str, Any] = dict(data)
    doc["kind"] = KIND
    doc["schema_version"] = SCHEMA_VERSION
    doc["unit_id"] = unit_id
    doc["state"] = str(data.get("state") or "SUCCESS")
    doc["sentinel"] = sentinel
    doc["sections"] = ordered
    errors = validate_document(doc)
    if errors:
        sample = errors[0]
        if "goal" in sample.lower():
            raise HandoffCompletenessError(
                f"handoff is incomplete: a re-anchored 'goal' section was expected ({sample})"
            )
        raise HandoffBoundaryError(
            f"handoff failed typed-schema validation: {sample}",
            trace={
                "boundary": BOUNDARY,
                "error_type": "HandoffBoundaryError",
                "payload_type": "dict",
                "reason": sample,
                "refused": True,
                "refused_kind": "schema-invalid",
            },
        )
    return Handoff(_data=doc)
