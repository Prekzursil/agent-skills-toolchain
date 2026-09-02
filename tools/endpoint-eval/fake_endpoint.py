"""Replay recorded OpenAI-wire fixtures from ``fixtures/`` (lens 08 section 5, CI column).

A ``wire-sequence`` fixture is an ordered list of HTTP envelopes ``{status, headers, body}``
exactly as a client saw them: a 429 storm, a double-encoded ``arguments`` blob, a
``refusal`` field kept versus flattened, and a bridge that strips ``tool_calls``.
``FakeEndpoint(name).chat(request)`` hands out the next envelope (a deep copy) and sticks on
the last one once the recording is exhausted; ``.sequence()`` returns the whole recording.

The two house fixtures (``tools_house``, ``schemas_house``) are grader inputs, not
replayable endpoints. ``validate_fixture`` is the freshness check every fixture must pass:
it knows the three shapes and reports every violation rather than the first.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

WIRE_SEQUENCE = "wire-sequence"
TOOLS_HOUSE_SHAPE = "tools-house"
SCHEMAS_HOUSE_SHAPE = "schemas-house"
SHAPES = (WIRE_SEQUENCE, TOOLS_HOUSE_SHAPE, SCHEMAS_HOUSE_SHAPE)

TOOLS_HOUSE = "tools_house"
SCHEMAS_HOUSE = "schemas_house"
WIRE_FIXTURES = (
    "wire_429_storm",
    "wire_stringified_args",
    "wire_refusal",
    "wire_bridge_drop",
)

_COMMON_KEYS = ("shape", "name", "recorded_at")
_TOOL_KEYS = (
    "name",
    "description",
    "parameters",
    "prompt",
    "gold",
    "good_call",
    "bad_call",
)
_SCHEMA_KEYS = ("name", "schema", "valid", "invalid")

Document = dict[str, Any]
Envelope = dict[str, Any]


def _require(
    mapping: Mapping[str, Any], keys: Sequence[str], prefix: str, errors: list[str]
) -> None:
    for key in keys:
        if key not in mapping:
            errors.append(f"{prefix}: missing {key}")


def _validate_wire(document: Document, errors: list[str]) -> None:
    responses = document.get("responses")
    if not isinstance(responses, list) or not responses:
        errors.append("responses: expected a non-empty list")
        return
    for index, response in enumerate(responses):
        prefix = f"responses[{index}]"
        if not isinstance(response, dict):
            errors.append(f"{prefix}: expected an object")
            continue
        if not isinstance(response.get("status"), int):
            errors.append(f"{prefix}.status: expected an integer")
        if not isinstance(response.get("headers"), dict):
            errors.append(f"{prefix}.headers: expected an object")
        if "body" not in response:
            errors.append(f"{prefix}.body: missing")
    labels = document.get("labels", [])
    if not isinstance(labels, list):
        errors.append("labels: expected a list")
    elif labels and len(labels) != len(responses):
        errors.append("labels: must align 1:1 with responses")


def _validate_tools(document: Document, errors: list[str]) -> None:
    tools = document.get("tools")
    if not isinstance(tools, list):
        errors.append("tools: expected a list")
        return
    for index, tool in enumerate(tools):
        prefix = f"tools[{index}]"
        if not isinstance(tool, dict):
            errors.append(f"{prefix}: expected an object")
            continue
        _require(tool, _TOOL_KEYS, prefix, errors)
        parameters = tool.get("parameters")
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            errors.append(f"{prefix}.parameters: expected an object schema")
        gold = tool.get("gold")
        if not isinstance(gold, dict) or not isinstance(gold.get("args"), dict):
            errors.append(f"{prefix}.gold: expected {{name, args}}")
        for key in ("good_call", "bad_call"):
            if not isinstance(tool.get(key), dict):
                errors.append(f"{prefix}.{key}: expected a call object")


def _validate_schemas(document: Document, errors: list[str]) -> None:
    schemas = document.get("schemas")
    if not isinstance(schemas, list):
        errors.append("schemas: expected a list")
        return
    for index, entry in enumerate(schemas):
        prefix = f"schemas[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: expected an object")
            continue
        _require(entry, _SCHEMA_KEYS, prefix, errors)
        if not isinstance(entry.get("schema"), dict):
            errors.append(f"{prefix}.schema: expected an object")


_VALIDATORS: dict[str, Callable[[Document, list[str]], None]] = {
    WIRE_SEQUENCE: _validate_wire,
    TOOLS_HOUSE_SHAPE: _validate_tools,
    SCHEMAS_HOUSE_SHAPE: _validate_schemas,
}


def validate_fixture(document: Any) -> list[str]:
    """Every shape violation in ``document`` (empty list = fresh)."""
    if not isinstance(document, dict):
        return ["document: expected a JSON object"]
    errors: list[str] = []
    _require(document, _COMMON_KEYS, "document", errors)
    shape = document.get("shape")
    if "shape" in document and shape not in SHAPES:
        errors.append(f"document: unknown shape {shape!r} (expected one of {SHAPES})")
    validator = _VALIDATORS.get(shape) if isinstance(shape, str) else None
    if validator is not None:
        validator(document, errors)
    return errors


def load_fixture(name: str, fixtures_dir: Path | None = None) -> Document:
    """Parse and validate ``<fixtures_dir>/<name>.json``; loud on every failure mode."""
    directory = FIXTURES_DIR if fixtures_dir is None else fixtures_dir
    path = directory / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"fixture {name!r} not found in {directory}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"fixture {path.name} is not JSON: {exc}") from exc
    errors = validate_fixture(document)
    if errors:
        raise ValueError(f"fixture {path.name} is invalid: " + "; ".join(errors))
    if document["name"] != name:
        raise ValueError(
            f"fixture {path.name} declares name {document['name']!r}, expected {name!r}"
        )
    return document


class FakeEndpoint:
    """Replay one ``wire-sequence`` fixture as if it were a chat endpoint."""

    def __init__(self, fixture_name: str, fixtures_dir: Path | None = None) -> None:
        self.name = fixture_name
        self.document = load_fixture(fixture_name, fixtures_dir)
        shape = self.document["shape"]
        if shape != WIRE_SEQUENCE:
            raise ValueError(
                f"fixture {fixture_name!r} has shape {shape!r}; only {WIRE_SEQUENCE} replays"
            )
        self._responses: list[Envelope] = self.document["responses"]
        self._cursor = 0
        self.calls: list[dict[str, Any]] = []

    def sequence(self) -> list[Envelope]:
        return copy.deepcopy(self._responses)

    def labels(self) -> list[str]:
        return list(self.document.get("labels", []))

    def by_label(self, label: str) -> Envelope:
        labels = self.labels()
        if label not in labels:
            raise KeyError(
                f"no response labelled {label!r} in {self.name}; have {labels}"
            )
        return copy.deepcopy(self._responses[labels.index(label)])

    @property
    def exhausted(self) -> bool:
        return self._cursor >= len(self._responses)

    def chat(self, request: Mapping[str, Any]) -> Envelope:
        index = min(self._cursor, len(self._responses) - 1)
        self._cursor += 1
        self.calls.append(dict(request))
        return copy.deepcopy(self._responses[index])

    def reset(self) -> None:
        self._cursor = 0
