"""CANONICAL JSON — the ONE serialisation both runtimes must reproduce byte-for-byte.

This module exists because a receipt written by the Python runtime and a receipt written by
the JS runtime have to be the SAME BYTES, and the stock encoders are not close. MEASURED on a
75-case differential probe (CPython 3.11 vs Node 22 and Node 24): stock ``json.dumps`` and
stock ``JSON.stringify`` disagree on **47 of 75 cases (62.7%)**, and on **15 of 15** container
cases that carry at least one object key or two array elements — i.e. every realistic receipt.
Configuring the two stdlib encoders towards each other (``ensure_ascii=False``,
``separators``, ``sort_keys``, ``allow_nan=False``) only reaches 43/75; **32 cases still
diverge**, so the canonical form is a CUSTOM encoder on both sides, never a tuned stdlib call.

The rules, each tied to the measured row that forced it:

* **R1** UTF-8 bytes, no BOM. A BOM *inside* a string is data and survives.
* **R2** No insignificant whitespace; separators are exactly ``,`` and ``:``. (9 cases diverge
  on separators alone: ``{"a": 1}`` vs ``{"a":1}``.)
* **R3** Object keys sorted ascending by **UTF-16 code-unit** sequence — JS ``.sort()`` order,
  NOT Python's code-point ``str`` order. ``sort_keys=True`` does NOT fix this: V8 emits
  integer-like keys first in ascending numeric order. Measured on ``{"10","2","b","1"}``:
  Python ``1,10,2,b`` vs JS ``1,2,10,b``. Code-unit order also puts an astral emoji BEFORE
  ``U+FFFF`` (lead surrogate ``0xD83D`` < ``0xFFFF``), which code-point order gets backwards.
* **R4** Keys must be ``str``. A non-string key is REJECTED, never coerced — Python renders
  a dict holding BOTH the astral code point AND the same character as two separate lone
  surrogate code points folded to a document with a DUPLICATE key, which
  RFC 8259 calls non-interoperable and which falsified :func:`loads`' own stated fixed point
  (``dumps(loads(dumps(x))) == dumps(x)`` returned the 2-key document as a 1-key document).
  The JS encoder is injective by construction and cannot reach this arm; the code exists on
  both sides so the closed rejection set stays identical.
* **R5** Numbers rendered by the ECMAScript ``Number::toString`` algorithm (ECMA-262
  6.1.6.1.20). JS gets this from ``String(x)``; Python must implement it, because Python
  switches to exponential at 1e16 while ECMAScript switches at 1e21, and Python zero-pads the
  exponent (``1e-05`` vs ``1e-5``). :func:`number_to_string` is validated against ``String(x)``
  on **209,442 distinct doubles with zero mismatches**.
* **R6** The int/float TAG is erased: an integral real emits with no fractional part, so a
  Python ``1.0`` and a Python ``1`` are indistinguishable on the wire — exactly as in JS.
  Lossy by design, and stated rather than discovered.
* **R7** INTEGER-TYPED values (Python ``int``, JS ``BigInt``) outside ±(2**53 - 1) are
  REJECTED. A ``float`` is a double and claims no precision beyond IEEE-754, so ANY finite
  double is accepted whatever its magnitude: ``1e100`` is fine, ``int(10**30)`` is not.
* **R8** ``NaN`` / ``±Infinity`` are REJECTED. Python emits bare ``NaN`` (invalid JSON) and JS
  emits ``null`` (silent data loss); neither can be preferred, so neither is allowed.
* **R9** ``-0.0`` normalises to ``0``, adopting ES ``Number::toString(-0)``.
* **R10** Escaping is ES2019 ``QuoteJSONString`` (well-formed): ``"``, ``\\`` and C0 with the
  short forms, else lowercase ``\\u00xx``; UNPAIRED surrogates escaped as lowercase
  ``\\udxxx``; everything else raw UTF-8. Escaping unpaired surrogates is not cosmetic — with
  ``ensure_ascii=False`` a lone surrogate makes the Python ``str`` impossible to encode to
  UTF-8 at all, so the "obvious" tuning makes that case strictly WORSE than the default.
* **R11** ``U+2028`` / ``U+2029`` are ALSO escaped. A deliberate, symmetric deviation from
  ``JSON.stringify``: cost zero, and a raw U+2028 splits a physical source line.
* **R12** Only ``str``/``int``/``float``/``bool``/``None``/``list``/``tuple``/``dict`` are
  accepted, and there is NO ``toJSON`` hook. ``JSON.stringify`` silently mangles ``Date``,
  ``Map``, ``Set``, boxed primitives and array holes, and a ``toJSON`` property can hijack the
  whole document — Python has no counterpart for any of it.
* **R13** Maximum nesting depth :data:`MAX_DEPTH`. Python's recursion limit trips far earlier
  than V8's stack, so without an explicit shared cap the boundary is platform-dependent.
* **R14** DECODER: bare ``NaN`` / ``Infinity`` / ``-Infinity`` literals are rejected. Measured:
  ``json.loads("NaN")`` ACCEPTS, ``JSON.parse("NaN")`` raises — left at defaults a Python
  consumer silently ingests a document a JS consumer refuses.
* **R15** DECODER: a bare integer literal outside the safe range decodes to ``float``,
  mirroring R6. Without it ``encode(decode(encode(x)))`` is NOT a fixed point in Python: R6
  renders ``float(1e16)`` as ``10000000000000000``, ``json.loads`` reads that back as a big
  ``int``, and the next encode rejects it under R7. JS needs no equivalent — ``JSON.parse``
  always yields a double.

* **R16** DECODER: :func:`loadb` REFUSES bytes that are not valid UTF-8, and reports it as
  :data:`E_INVALID_UTF8` rather than as this interpreter's ``UnicodeDecodeError``. JS has no
  such exception and its default byte decode is LOSSY — measured, ``loadb`` there returned a
  well-formed value with U+FFFD substituted where this side raised, so ``dumpb(loadb(x)))``
  manufactured a plausible-looking canonical receipt out of corrupt input.

Every rejection code is *segment*-shaped, so :func:`agentspec.taxonomy.family` resolves all
eight to the existing closed member ``schema-invalid``. The taxonomy does NOT grow for this
module.

The rules above make the two runtimes agree on the BYTES. Agreeing on the DECISIONS is
:mod:`agentspec.wire`'s job, and it is a separate contract with a separate corpus — a
differential harness found 78 behavioural divergences while this module was already exact.

Pure: no clock, no entropy, and no I/O except :func:`read_blob_via_cat_file`, which reads one
git blob on request. :func:`agentspec.determinism.scan_package` covers it.

The WORKFLOW document layer (``export`` / ``import_workflow`` / ``round_trip_*``) sits on top
of these primitives and is documented where it starts, below ``CanonicalError``.
"""

from __future__ import annotations

import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from agentspec.spec import (
    DEFAULT_ON_FAILURE,
    Barrier,
    DynamicFanOut,
    FanOut,
    HumanCheckpoint,
    Loop,
    Param,
    ParamBinding,
    Pipeline,
    ReceiptSpec,
    Routing,
    SecretRef,
    Subworkflow,
    UnitTemplate,
    Workflow,
    WorkUnit,
)
from agentspec.wire import utf16_sort_key as utf16_sort_key

MAX_SAFE_INTEGER = 2**53 - 1
"""R7. Beyond this an integer-typed value cannot survive a JS ``Number`` round trip."""

MIN_SAFE_INTEGER = -(2**53 - 1)

MAX_DEPTH = 100
"""R13. The shared nesting cap, so the boundary is identical on both runtimes."""

E_NONFINITE = "schema-invalid-nonfinite"
E_INT_RANGE = "schema-invalid-int-range"
E_KEY_TYPE = "schema-invalid-nonstring-key"
E_KEY_COLLISION = "schema-invalid-key-collision"
E_VALUE_TYPE = "schema-invalid-unsupported-type"
E_CYCLIC = "schema-invalid-cyclic"
E_MAX_DEPTH = "schema-invalid-max-depth"
E_INVALID_UTF8 = "schema-invalid-utf8"

REJECTION_CODES: tuple[str, ...] = (
    E_CYCLIC,
    E_INT_RANGE,
    E_KEY_COLLISION,
    E_MAX_DEPTH,
    E_NONFINITE,
    E_KEY_TYPE,
    E_VALUE_TYPE,
    E_INVALID_UTF8,
)
"""Sorted and CLOSED. The JS mirror asserts set equality against this tuple."""

_SHORT_ESCAPES: dict[int, str] = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}

_LINE_SEPARATORS: tuple[int, int] = (0x2028, 0x2029)

_HIGH_SURROGATE_FIRST = 0xD800
_HIGH_SURROGATE_LAST = 0xDBFF
_LOW_SURROGATE_FIRST = 0xDC00
_LOW_SURROGATE_LAST = 0xDFFF


class CanonicalJsonError(ValueError):
    """A value canonical JSON refuses to represent, carrying its ``schema-invalid`` sub-code."""

    reason = "schema-invalid"

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


CanonicalError = CanonicalJsonError

# --------------------------------------------------------------------------- IMP-0146
# The WORKFLOW canonical document: one byte-stable rendering of a :class:`Workflow` that
# carries every node kind in ``EXISTING_NODE_KINDS | NEW_NODE_KINDS`` and satisfies
# ``export(import_workflow(export(w))) == export(w)`` for every workflow.
#
# Shape (keys in UTF-16 code-unit order, two-space indent, LF, one trailing LF, no CR):
#
#   {"canonical_format": "agentspec.workflow.canonical", "canonical_format_version": 1,
#    "workflow": {"id", "kind": "Workflow", "nodes": [...], "params": [...],
#                 "spec_version", "units": [...]}}
#
# The declarative Phase-7 fields of a unit are ALWAYS written; the dispatch-form fields
# (``prompt``, ``timeout_s``, ``receipt``, ``depends_on``, ``budget_micro``, ``isolation``,
# ``writes``, ``fail_family``) and the workflow's ``budget_micro`` / ``default_on_failure``
# appear only when they differ from the type's default, so a purely declarative workflow has
# a minimal form and a dispatch-form workflow still round-trips losslessly. The importer is a
# STRICT parser: an unknown key, a missing key or an unknown node kind is refused with a
# ``canonical-*`` code; nothing is coerced or dropped.

CANONICAL_FORMAT = "agentspec.workflow.canonical"
CANONICAL_FORMAT_VERSION = 1

E_CANONICAL_INVALID_JSON = "canonical-invalid-json"
E_CANONICAL_NOT_OBJECT = "canonical-not-object"
E_CANONICAL_FORMAT = "canonical-format-mismatch"
E_CANONICAL_UNKNOWN_KEY = "canonical-unknown-key"
E_CANONICAL_MISSING_KEY = "canonical-missing-key"
E_CANONICAL_UNKNOWN_KIND = "canonical-unknown-kind"
E_CANONICAL_BAD_VALUE = "canonical-bad-value"
E_CANONICAL_ARCHIVE_FORBIDDEN = "canonical-archive-forbidden"
E_CANONICAL_OBJECTISH = "canonical-objectish-invalid"
E_CANONICAL_BLOB_MISSING = "canonical-blob-missing"

WORKFLOW_REJECTION_CODES: tuple[str, ...] = (
    E_CANONICAL_ARCHIVE_FORBIDDEN,
    E_CANONICAL_BAD_VALUE,
    E_CANONICAL_BLOB_MISSING,
    E_CANONICAL_FORMAT,
    E_CANONICAL_INVALID_JSON,
    E_CANONICAL_MISSING_KEY,
    E_CANONICAL_NOT_OBJECT,
    E_CANONICAL_OBJECTISH,
    E_CANONICAL_UNKNOWN_KEY,
    E_CANONICAL_UNKNOWN_KIND,
)
"""Sorted and CLOSED: every code the workflow-document layer can raise."""

_DOCUMENT_KEYS = frozenset({"canonical_format", "canonical_format_version", "workflow"})
_WORKFLOW_REQUIRED = frozenset({"id", "kind", "nodes", "params", "spec_version", "units"})
_WORKFLOW_OPTIONAL = frozenset({"budget_micro", "default_on_failure"})
_UNIT_REQUIRED = frozenset(
    {
        "id",
        "kind",
        "on_failure",
        "owner_flags",
        "prompt_ref",
        "routing",
        "source_policy",
        "tool_permissions",
    }
)
_UNIT_OPTIONAL = frozenset(
    {
        "prompt",
        "timeout_s",
        "receipt",
        "depends_on",
        "budget_micro",
        "isolation",
        "writes",
        "fail_family",
    }
)
_ROUTING_KEYS = frozenset({"fallbacks", "model", "role", "vendor"})
_RECEIPT_KEYS = frozenset({"fmt", "required_fields", "forbidden_markers"})
_PARAM_REQUIRED = frozenset({"default", "enum", "name", "param_type", "required", "secret_ref"})
_PARAM_OPTIONAL = frozenset({"ref"})
_BINDING_KEYS = frozenset({"name", "value"})
_TEMPLATE_KEYS = frozenset({"id", "prompt_ref"})
_NODE_REQUIRED: dict[str, frozenset[str]] = {
    "FanOut": frozenset({"id", "kind", "on_failure", "unit_ids"}),
    "Barrier": frozenset({"id", "kind", "on_failure", "wait_for"}),
    "Pipeline": frozenset({"id", "kind", "on_failure", "stages"}),
    "Subworkflow": frozenset(
        {"id", "id_namespace", "kind", "on_failure", "param_bindings", "workflow_ref"}
    ),
    "Loop": frozenset(
        {
            "body",
            "convergence_expr",
            "id",
            "kind",
            "max_iterations",
            "on_bound_reached",
            "on_failure",
        }
    ),
    "HumanCheckpoint": frozenset(
        {
            "allowed_responses",
            "default_if_unanswered",
            "id",
            "kind",
            "on_failure",
            "pause_token",
            "prompt_ref",
        }
    ),
    "DynamicFanOut": frozenset(
        {
            "id",
            "item_path",
            "kind",
            "max_cardinality",
            "on_failure",
            "producer_unit",
            "unit_template",
        }
    ),
}
_NODE_OPTIONAL: dict[str, frozenset[str]] = {
    "Barrier": frozenset({"policy", "null_tolerant"}),
}


def _ordered(value: Any) -> Any:
    """Recursively order mapping keys by UTF-16 code units (R3) for the indented renderer."""
    if isinstance(value, dict):
        return {
            key: _ordered(value[key]) for key in sorted(value, key=utf16_sort_key)
        }
    if isinstance(value, (list, tuple)):
        return [_ordered(item) for item in value]
    return value


def _wire_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, f"{where}: expected an integer")
    if not MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        raise CanonicalJsonError(E_INT_RANGE, f"{where}: integer outside the safe range")
    return value


def _routing_document(routing: Routing) -> dict[str, Any]:
    return {
        "fallbacks": list(routing.fallbacks),
        "model": routing.model,
        "role": routing.role,
        "vendor": routing.vendor,
    }


def _unit_document(unit: WorkUnit) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "id": unit.id,
        "kind": unit.kind,
        "on_failure": unit.on_failure,
        "owner_flags": list(unit.owner_flags),
        "prompt_ref": unit.prompt_ref,
        "routing": None if unit.routing is None else _routing_document(unit.routing),
        "source_policy": list(unit.source_policy),
        "tool_permissions": list(unit.tool_permissions),
    }
    if unit.prompt:
        doc["prompt"] = unit.prompt
    if unit.timeout_s:
        doc["timeout_s"] = _wire_int(unit.timeout_s, f"unit {unit.id!r} timeout_s")
    if unit.receipt is not None:
        doc["receipt"] = {
            "fmt": unit.receipt.fmt,
            "required_fields": list(unit.receipt.required_fields),
            "forbidden_markers": list(unit.receipt.forbidden_markers),
        }
    if unit.depends_on:
        doc["depends_on"] = list(unit.depends_on)
    if unit.budget_micro:
        doc["budget_micro"] = _wire_int(unit.budget_micro, f"unit {unit.id!r} budget_micro")
    if unit.isolation != "shared":
        doc["isolation"] = unit.isolation
    if unit.writes:
        doc["writes"] = list(unit.writes)
    if unit.fail_family is not None:
        doc["fail_family"] = unit.fail_family
    return doc


def _node_document(node: Any) -> dict[str, Any]:
    kind = getattr(node, "kind", type(node).__name__)
    if kind not in _NODE_REQUIRED:
        raise CanonicalJsonError(E_CANONICAL_UNKNOWN_KIND, f"node kind {kind!r}")
    doc: dict[str, Any] = {"id": node.id, "kind": kind, "on_failure": node.on_failure}
    if isinstance(node, FanOut):
        doc["unit_ids"] = list(node.unit_ids or node.units)
    elif isinstance(node, Barrier):
        doc["wait_for"] = list(node.wait_for or node.awaits)
        if node.policy != "all":
            doc["policy"] = node.policy
        if node.null_tolerant is not True:
            doc["null_tolerant"] = bool(node.null_tolerant)
    elif isinstance(node, Pipeline):
        doc["stages"] = list(node.stages)
    elif isinstance(node, Subworkflow):
        doc["workflow_ref"] = node.workflow_ref
        doc["id_namespace"] = node.id_namespace
        doc["param_bindings"] = [
            {"name": binding.name, "value": binding.value} for binding in node.param_bindings
        ]
    elif isinstance(node, Loop):
        doc["body"] = list(node.body)
        doc["convergence_expr"] = node.convergence_expr
        doc["max_iterations"] = (
            None
            if node.max_iterations is None
            else _wire_int(node.max_iterations, f"loop {node.id!r} max_iterations")
        )
        doc["on_bound_reached"] = node.on_bound_reached
    elif isinstance(node, HumanCheckpoint):
        doc["prompt_ref"] = node.prompt_ref
        doc["allowed_responses"] = list(node.allowed_responses)
        doc["default_if_unanswered"] = node.default_if_unanswered
        doc["pause_token"] = node.pause_token
    elif isinstance(node, DynamicFanOut):
        doc["producer_unit"] = node.producer_unit
        doc["item_path"] = node.item_path
        template = node.unit_template
        doc["unit_template"] = (
            {"id": template.id, "prompt_ref": template.prompt_ref}
            if isinstance(template, UnitTemplate)
            else template
        )
        doc["max_cardinality"] = _wire_int(
            node.max_cardinality, f"dynamic fan-out {node.id!r} max_cardinality"
        )
    return doc


def _param_document(param: Param) -> dict[str, Any]:
    secret = param.secret_ref
    if isinstance(secret, SecretRef):
        secret = f"{secret.source}:{secret.name}"
    doc: dict[str, Any] = {
        "default": param.default,
        "enum": list(param.enum),
        "name": param.name or param.id,
        "param_type": param.param_type or param.kind,
        "required": bool(param.required),
        "secret_ref": secret,
    }
    if param.ref is not None:
        doc["ref"] = dict(param.ref)
    return doc


def workflow_to_document(workflow: Workflow) -> dict[str, Any]:
    """The canonical document (plain JSON-typed mapping) of ``workflow``."""
    if not isinstance(workflow, Workflow):
        raise CanonicalJsonError(
            E_CANONICAL_NOT_OBJECT, f"expected a Workflow, got {type(workflow).__name__}"
        )
    body: dict[str, Any] = {
        "id": workflow.id,
        "kind": workflow.kind,
        "spec_version": str(workflow.spec_version),
        "units": [_unit_document(unit) for unit in workflow.units],
        "nodes": [_node_document(node) for node in workflow.nodes],
        "params": [_param_document(param) for param in workflow.params],
    }
    if workflow.budget_micro:
        body["budget_micro"] = _wire_int(workflow.budget_micro, "workflow budget_micro")
    if workflow.default_on_failure != DEFAULT_ON_FAILURE:
        body["default_on_failure"] = workflow.default_on_failure
    return {
        "canonical_format": CANONICAL_FORMAT,
        "canonical_format_version": CANONICAL_FORMAT_VERSION,
        "workflow": body,
    }


def _check_keys(
    mapping: Any, required: frozenset[str], optional: frozenset[str], where: str
) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        raise CanonicalJsonError(E_CANONICAL_NOT_OBJECT, f"{where}: expected an object")
    keys = set(mapping)
    unknown = sorted(keys - required - optional)
    if unknown:
        raise CanonicalJsonError(E_CANONICAL_UNKNOWN_KEY, f"{where}: unknown key(s) {unknown}")
    missing = sorted(required - keys)
    if missing:
        raise CanonicalJsonError(E_CANONICAL_MISSING_KEY, f"{where}: missing key(s) {missing}")
    return mapping


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, f"{where}: expected a string")
    return value


def _text_or_none(value: Any, where: str) -> str | None:
    return None if value is None else _text(value, where)


def _texts(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, f"{where}: expected a list of strings")
    return tuple(_text(item, where) for item in value)


def _flag(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, f"{where}: expected a boolean")
    return value


def _unit_from_document(doc: Any, index: int) -> WorkUnit:
    where = f"units[{index}]"
    doc = _check_keys(doc, _UNIT_REQUIRED, _UNIT_OPTIONAL, where)
    if doc["kind"] != "WorkUnit":
        raise CanonicalJsonError(E_CANONICAL_UNKNOWN_KIND, f"{where}: kind {doc['kind']!r}")
    routing = None
    if doc["routing"] is not None:
        routing_doc = _check_keys(doc["routing"], _ROUTING_KEYS, frozenset(), f"{where}.routing")
        routing = Routing(
            vendor=_text(routing_doc["vendor"], f"{where}.routing.vendor"),
            model=_text(routing_doc["model"], f"{where}.routing.model"),
            role=_text(routing_doc["role"], f"{where}.routing.role"),
            fallbacks=_texts(routing_doc["fallbacks"], f"{where}.routing.fallbacks"),
        )
    receipt = None
    if doc.get("receipt") is not None:
        receipt_doc = _check_keys(doc["receipt"], _RECEIPT_KEYS, frozenset(), f"{where}.receipt")
        receipt = ReceiptSpec(
            fmt=_text(receipt_doc["fmt"], f"{where}.receipt.fmt"),
            required_fields=_texts(receipt_doc["required_fields"], f"{where}.receipt"),
            forbidden_markers=_texts(receipt_doc["forbidden_markers"], f"{where}.receipt"),
        )
    return WorkUnit(
        id=_text(doc["id"], f"{where}.id"),
        prompt=_text(doc.get("prompt", ""), f"{where}.prompt"),
        timeout_s=_wire_int(doc.get("timeout_s", 0), f"{where}.timeout_s"),
        receipt=receipt,
        depends_on=_texts(doc.get("depends_on", []), f"{where}.depends_on"),
        budget_micro=_wire_int(doc.get("budget_micro", 0), f"{where}.budget_micro"),
        isolation=_text(doc.get("isolation", "shared"), f"{where}.isolation"),
        writes=_texts(doc.get("writes", []), f"{where}.writes"),
        source_policy=_texts(doc["source_policy"], f"{where}.source_policy"),
        owner_flags=_texts(doc["owner_flags"], f"{where}.owner_flags"),
        prompt_ref=_text(doc["prompt_ref"], f"{where}.prompt_ref"),
        routing=routing,
        tool_permissions=_texts(doc["tool_permissions"], f"{where}.tool_permissions"),
        on_failure=_text(doc["on_failure"], f"{where}.on_failure"),
        fail_family=_text_or_none(doc.get("fail_family"), f"{where}.fail_family"),
    )


def _node_from_document(doc: Any, index: int) -> Any:
    where = f"nodes[{index}]"
    if not isinstance(doc, dict):
        raise CanonicalJsonError(E_CANONICAL_NOT_OBJECT, f"{where}: expected an object")
    kind = doc.get("kind")
    if kind not in _NODE_REQUIRED:
        raise CanonicalJsonError(E_CANONICAL_UNKNOWN_KIND, f"{where}: node kind {kind!r}")
    doc = _check_keys(doc, _NODE_REQUIRED[kind], _NODE_OPTIONAL.get(kind, frozenset()), where)
    node_id = _text(doc["id"], f"{where}.id")
    on_failure = _text(doc["on_failure"], f"{where}.on_failure")
    if kind == "FanOut":
        return FanOut(
            id=node_id, unit_ids=_texts(doc["unit_ids"], f"{where}.unit_ids"), on_failure=on_failure
        )
    if kind == "Barrier":
        return Barrier(
            id=node_id,
            wait_for=_texts(doc["wait_for"], f"{where}.wait_for"),
            policy=_text(doc.get("policy", "all"), f"{where}.policy"),
            null_tolerant=_flag(doc.get("null_tolerant", True), f"{where}.null_tolerant"),
            on_failure=on_failure,
        )
    if kind == "Pipeline":
        return Pipeline(
            id=node_id, stages=_texts(doc["stages"], f"{where}.stages"), on_failure=on_failure
        )
    if kind == "Subworkflow":
        bindings_doc = doc["param_bindings"]
        if not isinstance(bindings_doc, list):
            raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, f"{where}.param_bindings: list")
        bindings = tuple(
            ParamBinding(
                name=_text(binding["name"], f"{where}.param_bindings[{i}].name"),
                value=binding["value"],
            )
            for i, binding in enumerate(
                _check_keys(b, _BINDING_KEYS, frozenset(), f"{where}.param_bindings[{i}]")
                for i, b in enumerate(bindings_doc)
            )
        )
        return Subworkflow(
            id=node_id,
            workflow_ref=_text(doc["workflow_ref"], f"{where}.workflow_ref"),
            param_bindings=bindings,
            id_namespace=_text(doc["id_namespace"], f"{where}.id_namespace"),
            on_failure=on_failure,
        )
    if kind == "Loop":
        max_iterations = doc["max_iterations"]
        return Loop(
            id=node_id,
            body=_texts(doc["body"], f"{where}.body"),
            convergence_expr=_text_or_none(doc["convergence_expr"], f"{where}.convergence_expr"),
            max_iterations=(
                None
                if max_iterations is None
                else _wire_int(max_iterations, f"{where}.max_iterations")
            ),
            on_bound_reached=_text(doc["on_bound_reached"], f"{where}.on_bound_reached"),
            on_failure=on_failure,
        )
    if kind == "HumanCheckpoint":
        # The object model has no ``on_failure`` on a checkpoint (IMP-0131 pins its five
        # fields); the wire form carries the fixed default. Any other value could not survive
        # a round trip, so it is refused rather than silently rewritten.
        if on_failure != DEFAULT_ON_FAILURE:
            raise CanonicalJsonError(
                E_CANONICAL_BAD_VALUE,
                f"{where}.on_failure: a HumanCheckpoint carries only {DEFAULT_ON_FAILURE!r}",
            )
        return HumanCheckpoint(
            id=node_id,
            prompt_ref=_text(doc["prompt_ref"], f"{where}.prompt_ref"),
            allowed_responses=_texts(doc["allowed_responses"], f"{where}.allowed_responses"),
            default_if_unanswered=_text_or_none(
                doc["default_if_unanswered"], f"{where}.default_if_unanswered"
            ),
            pause_token=_text(doc["pause_token"], f"{where}.pause_token"),
        )
    template_doc = doc["unit_template"]
    if isinstance(template_doc, dict):
        template_doc = _check_keys(template_doc, _TEMPLATE_KEYS, frozenset(), f"{where}.unit_template")
        template: UnitTemplate | str = UnitTemplate(
            id=_text(template_doc["id"], f"{where}.unit_template.id"),
            prompt_ref=_text(template_doc["prompt_ref"], f"{where}.unit_template.prompt_ref"),
        )
    else:
        template = _text(template_doc, f"{where}.unit_template")
    return DynamicFanOut(
        id=node_id,
        producer_unit=_text(doc["producer_unit"], f"{where}.producer_unit"),
        item_path=_text(doc["item_path"], f"{where}.item_path"),
        unit_template=template,
        max_cardinality=_wire_int(doc["max_cardinality"], f"{where}.max_cardinality"),
        on_failure=on_failure,
    )


def _param_from_document(doc: Any, index: int) -> Param:
    where = f"params[{index}]"
    doc = _check_keys(doc, _PARAM_REQUIRED, _PARAM_OPTIONAL, where)
    enum = doc["enum"]
    if not isinstance(enum, list):
        raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, f"{where}.enum: expected a list")
    ref = doc.get("ref")
    if ref is not None and not isinstance(ref, dict):
        raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, f"{where}.ref: expected an object")
    return Param(
        name=_text(doc["name"], f"{where}.name"),
        param_type=_text(doc["param_type"], f"{where}.param_type"),
        default=doc["default"],
        required=_flag(doc["required"], f"{where}.required"),
        secret_ref=_text_or_none(doc["secret_ref"], f"{where}.secret_ref"),
        enum=tuple(enum),
        ref=ref,
    )


def document_to_workflow(document: Any) -> Workflow:
    """Strict inverse of :func:`workflow_to_document`."""
    doc = _check_keys(document, _DOCUMENT_KEYS, frozenset(), "document")
    if doc["canonical_format"] != CANONICAL_FORMAT:
        raise CanonicalJsonError(
            E_CANONICAL_FORMAT, f"canonical_format {doc['canonical_format']!r}"
        )
    if doc["canonical_format_version"] != CANONICAL_FORMAT_VERSION:
        raise CanonicalJsonError(
            E_CANONICAL_FORMAT, f"canonical_format_version {doc['canonical_format_version']!r}"
        )
    body = _check_keys(doc["workflow"], _WORKFLOW_REQUIRED, _WORKFLOW_OPTIONAL, "workflow")
    if body["kind"] != "Workflow":
        raise CanonicalJsonError(E_CANONICAL_UNKNOWN_KIND, f"workflow kind {body['kind']!r}")
    for key in ("units", "nodes", "params"):
        if not isinstance(body[key], list):
            raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, f"workflow.{key}: expected a list")
    return Workflow(
        id=_text(body["id"], "workflow.id"),
        spec_version=_text(body["spec_version"], "workflow.spec_version"),
        units=tuple(_unit_from_document(u, i) for i, u in enumerate(body["units"])),
        nodes=tuple(_node_from_document(n, i) for i, n in enumerate(body["nodes"])),
        budget_micro=_wire_int(body.get("budget_micro", 0), "workflow.budget_micro"),
        params=tuple(_param_from_document(p, i) for i, p in enumerate(body["params"])),
        default_on_failure=_text(
            body.get("default_on_failure", DEFAULT_ON_FAILURE), "workflow.default_on_failure"
        ),
    )


def export(workflow: Any) -> bytes:
    """Render ``workflow`` as the canonical document: UTF-8, LF only, one trailing LF.

    A document (mapping / str / bytes) is accepted too and is NORMALISED -- imported strictly,
    then rendered -- so ``export`` of any accepted input is always canonical bytes.
    """
    if not isinstance(workflow, Workflow):
        workflow = import_workflow(workflow)
    document = _ordered(workflow_to_document(workflow))
    try:
        text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, str(exc)) from exc
    try:
        return (text + "\n").encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalJsonError(E_CANONICAL_BAD_VALUE, "unpaired surrogate in a string") from exc


def import_workflow(data: Any) -> Workflow:
    """Parse a canonical document (bytes, text or mapping) into a :class:`Workflow`.

    Bytes may carry CRLF line ends or a leading BOM -- the working-tree copies git produces on
    an autocrlf checkout -- and import to the SAME workflow as the LF blob, which is the whole
    point of a canonical form. Anything else that differs is refused, never repaired.
    """
    if isinstance(data, Workflow):
        return data
    if isinstance(data, (bytes, bytearray, memoryview)):
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CanonicalJsonError(E_INVALID_UTF8, "not valid UTF-8") from exc
        data = text.lstrip("\ufeff")
    if isinstance(data, str):
        try:
            data = json.loads(data, parse_constant=_reject_constant)
        except (ValueError, RecursionError) as exc:
            raise CanonicalJsonError(E_CANONICAL_INVALID_JSON, str(exc)[:200]) from exc
    return document_to_workflow(data)


def round_trip_bytes(data: Any) -> bytes:
    """``export(import_workflow(data))`` -- the canonical bytes of whatever ``data`` denotes."""
    return export(import_workflow(data))


def round_trip_workflow(workflow: Workflow) -> bytes:
    """``export(import_workflow(export(workflow)))``: equal to ``export(workflow)`` iff the
    document layer is a fixed point for this workflow."""
    return export(import_workflow(export(workflow)))


def read_blob_via_cat_file(*, git_dir: Path | str, objectish: str) -> bytes:
    """The exact bytes of one git BLOB, via ``git cat-file -p`` -- never ``git archive``.

    ``cat-file -p`` streams the object as stored, so an LF blob comes back as LF even when the
    working tree is CRLF; ``git archive`` applies export attributes and EOL conversion and is
    therefore refused by name (``canonical-archive-forbidden``). ``objectish`` must be one
    token: a sha, a ref or ``<rev>:<path>``.
    """
    token = str(objectish).strip()
    if not token or any(ch.isspace() for ch in token):
        parts = token.split()
        if parts and parts[0].lower() == "archive":
            raise CanonicalJsonError(
                E_CANONICAL_ARCHIVE_FORBIDDEN, "git archive is not a blob read; use cat-file -p"
            )
        raise CanonicalJsonError(E_CANONICAL_OBJECTISH, f"objectish must be one token: {token!r}")
    if token.lower() == "archive" or token.lower().startswith("archive:"):
        raise CanonicalJsonError(
            E_CANONICAL_ARCHIVE_FORBIDDEN, "git archive is not a blob read; use cat-file -p"
        )
    if token.startswith("-"):
        raise CanonicalJsonError(E_CANONICAL_OBJECTISH, f"objectish looks like an option: {token!r}")
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    proc = subprocess.run(
        ["git", "--git-dir", str(git_dir), "cat-file", "-p", token],
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or b"").decode("utf-8", "replace").strip()[:200]
        raise CanonicalJsonError(E_CANONICAL_BLOB_MISSING, f"{token}: {detail or 'not found'}")
    return proc.stdout


def encode_string(text: str) -> str:
    """R10/R11. ES2019 well-formed ``QuoteJSONString`` with U+2028/U+2029 also escaped."""
    out: list[str] = ['"']
    index = 0
    size = len(text)
    while index < size:
        char = text[index]
        code = ord(char)
        short = _SHORT_ESCAPES.get(code)
        if short is not None:
            out.append(short)
        elif code < 0x20 or code in _LINE_SEPARATORS:
            out.append(f"\\u{code:04x}")
        elif _HIGH_SURROGATE_FIRST <= code <= _HIGH_SURROGATE_LAST:
            low = _low_surrogate_at(text, index + 1, size)
            if low is not None:
                out.append(_fold_surrogate_pair(code, low))
                index += 2
                continue
            out.append(f"\\u{code:04x}")
        elif _LOW_SURROGATE_FIRST <= code <= _LOW_SURROGATE_LAST:
            out.append(f"\\u{code:04x}")
        else:
            out.append(char)
        index += 1
    out.append('"')
    return "".join(out)


def number_to_string(value: float) -> str:
    """R5/R6/R9. ECMAScript ``Number::toString`` (ECMA-262 6.1.6.1.20) for a finite double."""
    if value != value or value in (float("inf"), float("-inf")):
        raise CanonicalJsonError(E_NONFINITE, repr(value))
    if value == 0.0:
        return "0"
    sign = "-" if value < 0 else ""
    digits, exponent = _shortest_digits(abs(value))
    count = len(digits)
    point = exponent + count
    if count <= point <= 21:
        return sign + digits + "0" * (point - count)
    if 0 < point <= 21:
        return sign + digits[:point] + "." + digits[point:]
    if -6 < point <= 0:
        return sign + "0." + "0" * (-point) + digits
    return sign + _exponential(digits, count, point - 1)


def dumps(value: Any) -> str:
    """The canonical TEXT for ``value``."""
    out: list[str] = []
    _encode(value, out, 0, ())
    return "".join(out)


def dumpb(value: Any) -> bytes:
    """R1. The canonical BYTES: always valid UTF-8, because R10 escapes lone surrogates."""
    return dumps(value).encode("utf-8")


def round_trip_ok(value: Any) -> bool:
    """True iff dumps(loads(dumps(value))) equals dumps(value)."""
    encoded = dumps(value)
    return dumps(loads(encoded)) == encoded


def loads(text: str) -> Any:
    """R14/R15. Decode canonical JSON so ``dumps(loads(dumps(x))) == dumps(x)`` holds."""
    return json.loads(text, parse_constant=_reject_constant, parse_int=_parse_int)


def loadb(raw: bytes) -> Any:
    """Decode canonical BYTES, REFUSING a lossy decode.

    The failure is reported as a :class:`CanonicalJsonError` rather than as this
    interpreter's ``UnicodeDecodeError`` because the JS mirror has no such exception:
    ``Buffer.toString('utf8')`` is LOSSY by default (it substitutes U+FFFD and never
    throws), so the JS side had to be given a fatal ``TextDecoder`` AND a shared error
    class. MEASURED before the fix: ``loadb(b'{\"a\":\"\\xff\"}')`` raised here and
    returned a well-formed ``{\"a\":\"\\ufffd\"}`` there — a plausible-looking canonical
    receipt manufactured out of corrupt bytes, on a path this runtime halts.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CanonicalJsonError(E_INVALID_UTF8, "not valid UTF-8") from exc
    return loads(text)


def _low_surrogate_at(text: str, index: int, size: int) -> int | None:
    """The low-surrogate code unit at ``index``, or ``None`` when the pair is not well-formed."""
    if index >= size:
        return None
    code = ord(text[index])
    if _LOW_SURROGATE_FIRST <= code <= _LOW_SURROGATE_LAST:
        return code
    return None


def _fold_surrogate_pair(high: int, low: int) -> str:
    """THE ONE PLACE the two languages' string MODELS are reconciled.

    A JS string is a sequence of UTF-16 CODE UNITS; a Python ``str`` is a sequence of CODE
    POINTS. So a JS astral character is one well-formed surrogate pair, while the same
    character in Python is a single code point and a Python surrogate is unpaired BY
    CONSTRUCTION. Folding an adjacent well-formed pair back into its astral code point makes
    the two models agree: Python ``"\\ud83d\\ude00"`` and Python ``"\\U0001f600"`` both encode
    to the bytes JS produces for its single string.

    HONEST COST, stated rather than discovered: this is lossy in one direction. Python CAN
    represent "a lone high surrogate immediately followed by a lone low surrogate" as a value
    distinct from the astral character; JS cannot represent that at all. Folding is the only
    mapping that keeps parity TOTAL, so that one degenerate Python value is normalised away.
    Not folding is worse than lossy — it emits raw surrogates, and :func:`dumpb` then dies with
    ``UnicodeEncodeError`` instead of producing bytes (measured while building this module).

    THE CONSEQUENCE THAT WAS MISSED FIRST TIME: inside a MAPPING the fold is not merely a value
    normalisation, it is a KEY COLLISION. Two distinct dict keys folded onto one wire key and
    the encoder emitted a duplicate-key document. R4b now rejects that, so the lossiness stays
    confined to scalar values where it is a normalisation, and can never produce a document the
    module's own round-trip invariant does not hold for.
    """
    return chr(
        0x10000 + ((high - _HIGH_SURROGATE_FIRST) << 10) + (low - _LOW_SURROGATE_FIRST)
    )


def _shortest_digits(magnitude: float) -> tuple[str, int]:
    """The shortest round-tripping significand of ``magnitude``, trailing zeros stripped.

    ``repr`` has produced the shortest round-tripping decimal since CPython 3.1, so this reads
    that rather than re-deriving Grisu/Ryu. :class:`~decimal.Decimal` is used only to split the
    literal into digits and an exponent without string surgery.
    """
    _, raw_digits, raw_exponent = Decimal(repr(magnitude)).as_tuple()
    digits = list(raw_digits)
    exponent = int(raw_exponent)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return "".join(str(digit) for digit in digits), exponent


def _exponential(digits: str, count: int, power: int) -> str:
    """R5's exponential form; the exponent sign is explicit and NEVER zero-padded."""
    sign = "+" if power >= 0 else "-"
    if count == 1:
        return f"{digits}e{sign}{abs(power)}"
    return f"{digits[0]}.{digits[1:]}e{sign}{abs(power)}"


def _encode(value: Any, out: list[str], depth: int, seen: tuple[int, ...]) -> None:
    """R12. The closed dispatch over accepted types; anything else is rejected."""
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(encode_string(value))
    elif isinstance(value, int):
        out.append(_encode_int(value))
    elif isinstance(value, float):
        out.append(number_to_string(value))
    elif isinstance(value, dict):
        _encode_container(value, out, depth, seen, _encode_mapping)
    elif isinstance(value, (list, tuple)):
        _encode_container(value, out, depth, seen, _encode_sequence)
    else:
        raise CanonicalJsonError(E_VALUE_TYPE, type(value).__name__)


def _encode_int(value: int) -> str:
    """R7. ``bool`` never reaches here — :func:`_encode` matches it first, by identity.

    ``int.__repr__`` is called UNBOUND on purpose, and it must be ``__repr__`` -- not
    ``__str__``, not ``str()``, not ``f"{value:d}"``. ``isinstance(value, int)`` admits
    arbitrary subclasses, and each of the other three renderings can be hijacked by one:

    ==================  =====  ============  ===========  ==============  =======  =======
    candidate           plain  __repr__ sub  __str__ sub  __format__ sub  IntEnum  IntFlag
    ==================  =====  ============  ===========  ==============  =======  =======
    ``str(v)``          5      **PWNED**     **PWNED**    5               1        1
    ``int.__str__(v)``  5      **PWNED**     5            5               **bad**  **bad**
    ``f"{v:d}"``        5      5             5            **PWNED**       1        1
    ``int.__repr__(v)`` 5      5             5            5               1        1
    ==================  =====  ============  ===========  ==============  =======  =======

    ``int.__str__`` looks like the safe unbound call but is NOT: ``int.__str__ is
    object.__str__`` is ``True``, and ``object.__str__`` delegates to ``type(x).__repr__`` --
    so it does not escape the subclass, it only moves which dunder hijacks it. It also renders
    stdlib ``IntEnum``/``IntFlag`` as ``<Colour.RED: 1>``, which ``json.loads`` refuses.
    MEASURED on CPython 3.11 (CI), 3.12 and 3.14 -- not a local-interpreter artifact.

    The JS side has no counterpart: a boxed ``new Number(5)`` is already rejected as an
    unsupported type, so this is the one place Python's structural typing is laxer than JS's.
    """
    if not MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        raise CanonicalJsonError(E_INT_RANGE, int.__repr__(value))
    return int.__repr__(value)


def _encode_container(
    value: Any,
    out: list[str],
    depth: int,
    seen: tuple[int, ...],
    body: Any,
) -> None:
    """R13 + the cycle guard, shared by both container kinds so neither can drift."""
    if id(value) in seen:
        raise CanonicalJsonError(E_CYCLIC, type(value).__name__)
    if depth >= MAX_DEPTH:
        raise CanonicalJsonError(E_MAX_DEPTH, f"nesting exceeds {MAX_DEPTH}")
    body(value, out, depth + 1, (*seen, id(value)))


def _encode_mapping(
    value: dict[Any, Any], out: list[str], depth: int, seen: tuple[int, ...]
) -> None:
    """R3/R4/R4b. Keys checked before ANY output, so a rejection never emits a partial object."""
    for key in value:
        if not isinstance(key, str):
            raise CanonicalJsonError(E_KEY_TYPE, type(key).__name__)
    ordered = sorted(value, key=utf16_sort_key)
    rendered: list[str] = []
    emitted: set[str] = set()
    for key in ordered:
        wire_key = encode_string(key)
        if wire_key in emitted:
            raise CanonicalJsonError(E_KEY_COLLISION, wire_key)
        emitted.add(wire_key)
        rendered.append(wire_key)
    out.append("{")
    for position, key in enumerate(ordered):
        if position:
            out.append(",")
        out.append(rendered[position])
        out.append(":")
        _encode(value[key], out, depth, seen)
    out.append("}")


def _encode_sequence(
    value: Any, out: list[str], depth: int, seen: tuple[int, ...]
) -> None:
    out.append("[")
    for position, item in enumerate(value):
        if position:
            out.append(",")
        _encode(item, out, depth, seen)
    out.append("]")


def _reject_constant(name: str) -> Any:
    """R14. ``json.loads`` accepts bare ``NaN``/``Infinity``; ``JSON.parse`` does not."""
    raise CanonicalJsonError(E_NONFINITE, f"literal {name}")


def _parse_int(text: str) -> Any:
    """R15. An out-of-safe-range bare integer can only have come from a double under R6."""
    value = int(text)
    if MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        return value
    return float(text)
