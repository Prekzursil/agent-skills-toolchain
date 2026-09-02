"""Shared typed-workflow runtime for the foundry (``workflow-scout`` dogfoods it).

A typed workflow is a JSON *document*, never a script: :func:`load_workflow` refuses
``.py`` (and other program) files outright and validates the document shape before
anything runs. :func:`execute` drives the document's ordered stages through a
caller-supplied handler table. A stage handler is a plain Python callable that receives
the shared ``ctx`` mapping; workflow inputs are stored on ``ctx["inputs"]`` and are never
interpolated into a shell string, an argv vector, or any other process adapter. This
module imports neither ``subprocess`` nor ``os`` and spawns nothing (ADV-0031 measures
exactly that property).

Document shape (``foundry.typed-workflow.v1``)::

    {
      "id": "wf.example",              # non-empty string
      "kind": "typed-workflow",        # required, exactly this value
      "spec_version": "foundry.typed-workflow.v1",   # optional; "schema" is accepted as alias
      "title": "...",                  # optional
      "stages": [                      # non-empty, ordered
        {"id": "a", "handler": "pkg.a", "kind": "python", "depends_on": []},
        {"id": "b", "depends_on": ["a"]}   # handler defaults to the stage id
      ]
    }

``depends_on`` may only name stages that appear *earlier* in the list, so the document
order is already a valid execution order and there is nothing to schedule at run time.

Receipts are pure functions of their inputs: no wall-clock timestamps and no absolute
paths, so two runs over the same document and inputs are byte-identical.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ENGINE = "foundry.runtime"
SPEC_VERSION = "foundry.typed-workflow.v1"
DOCUMENT_KIND = "typed-workflow"
DEFAULT_STAGE_KIND = "python"
JSON_SUFFIX = ".json"
#: File types that are programs. A typed workflow is data; a program is a bespoke script.
SCRIPT_SUFFIXES = frozenset({".py", ".pyw", ".pyc", ".sh", ".bash", ".ps1", ".bat", ".cmd"})

Handler = Callable[[dict[str, Any]], Any]


class TypedWorkflowError(Exception):
    """A document, handler table, or execution request violates the typed-workflow contract."""


@dataclass(frozen=True)
class Stage:
    """One ordered unit of a typed workflow, dispatched by ``handler`` name."""

    id: str
    handler: str
    kind: str = DEFAULT_STAGE_KIND
    depends_on: tuple[str, ...] = ()

    def to_document(self) -> dict[str, Any]:
        """Normalized JSON-ready form of the stage (every optional field made explicit)."""
        return {
            "id": self.id,
            "handler": self.handler,
            "kind": self.kind,
            "depends_on": list(self.depends_on),
        }


@dataclass(frozen=True)
class Workflow:
    """A validated typed-workflow document."""

    id: str
    stages: tuple[Stage, ...]
    spec_version: str = SPEC_VERSION
    title: str = ""
    #: Top-level keys the runtime does not interpret, preserved for round-tripping.
    extra: Mapping[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def from_document(cls, doc: Any) -> "Workflow":
        """Validate ``doc`` and build the typed form; raise :class:`TypedWorkflowError` listing every defect."""
        if isinstance(doc, Workflow):
            return doc
        errors = validate_document(doc)
        if errors:
            raise TypedWorkflowError("typed-workflow document rejected: " + "; ".join(errors))
        stages = tuple(_stage_from_document(raw) for raw in doc["stages"])
        version = doc.get("spec_version", doc.get("schema", SPEC_VERSION))
        extra = {
            key: value
            for key, value in doc.items()
            if key not in {"id", "kind", "spec_version", "schema", "title", "stages"}
        }
        return cls(
            id=doc["id"],
            stages=stages,
            spec_version=version,
            title=str(doc.get("title") or ""),
            extra=extra,
        )

    def to_document(self) -> dict[str, Any]:
        """Normalized JSON-ready document (``kind``/``spec_version`` explicit, stages normalized)."""
        doc: dict[str, Any] = dict(self.extra)
        doc["id"] = self.id
        doc["kind"] = DOCUMENT_KIND
        doc["spec_version"] = self.spec_version
        if self.title:
            doc["title"] = self.title
        doc["stages"] = [stage.to_document() for stage in self.stages]
        return doc

    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.id for stage in self.stages)

    def handler_names(self) -> tuple[str, ...]:
        """Distinct handler names in first-use order; the keys a handler table must provide."""
        return tuple(dict.fromkeys(stage.handler for stage in self.stages))


def _is_name(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_document(doc: Any) -> list[str]:
    """Return every contract violation in ``doc`` (empty list means valid).

    Checked: object shape, ``kind``, spec version, ``id``, ``title`` type, non-empty
    ``stages`` list, per-stage ``id``/``handler``/``kind``/``depends_on`` types, duplicate
    stage ids, and that every dependency names an earlier stage.
    """
    if not isinstance(doc, Mapping):
        return [f"document must be a JSON object, got {type(doc).__name__}"]
    errors: list[str] = []
    kind = doc.get("kind")
    if kind != DOCUMENT_KIND:
        errors.append(f"kind must be {DOCUMENT_KIND!r}, got {kind!r}")
    for key in ("spec_version", "schema"):
        if key in doc and doc[key] != SPEC_VERSION:
            errors.append(f"{key} {doc[key]!r} is not supported (expected {SPEC_VERSION!r})")
    if not _is_name(doc.get("id")):
        errors.append("id must be a non-empty string")
    if "title" in doc and not isinstance(doc["title"], str):
        errors.append("title must be a string")
    stages = doc.get("stages")
    if not isinstance(stages, list) or not stages:
        errors.append("stages must be a non-empty list")
        return errors
    seen: set[str] = set()
    for index, raw in enumerate(stages):
        label = f"stages[{index}]"
        if not isinstance(raw, Mapping):
            errors.append(f"{label} must be an object, got {type(raw).__name__}")
            continue
        sid = raw.get("id")
        if not _is_name(sid):
            errors.append(f"{label}.id must be a non-empty string")
            continue
        label = f"stage {sid!r}"
        if sid in seen:
            errors.append(f"duplicate stage id {sid!r}")
        if "handler" in raw and not _is_name(raw["handler"]):
            errors.append(f"{label}.handler must be a non-empty string when present")
        if "kind" in raw and not _is_name(raw["kind"]):
            errors.append(f"{label}.kind must be a non-empty string when present")
        deps = raw.get("depends_on", [])
        if not isinstance(deps, list) or not all(isinstance(dep, str) for dep in deps):
            errors.append(f"{label}.depends_on must be a list of stage ids")
        else:
            for dep in deps:
                if dep not in seen:
                    errors.append(f"{label} depends on {dep!r}, which is not an earlier stage")
        seen.add(sid)
    return errors


def _stage_from_document(raw: Mapping[str, Any]) -> Stage:
    """Build a :class:`Stage` from an already-validated stage object."""
    sid = str(raw["id"])
    return Stage(
        id=sid,
        handler=str(raw.get("handler") or sid),
        kind=str(raw.get("kind") or DEFAULT_STAGE_KIND),
        depends_on=tuple(raw.get("depends_on") or ()),
    )


def load_workflow(path: str | Path) -> dict[str, Any]:
    """Read, refuse-or-validate, and normalize a typed-workflow JSON document.

    Programs (``.py`` and friends) are refused before they are read: a workflow is data
    the runtime interprets, never a bespoke script it runs. Anything that is not a
    ``.json`` file, is unreadable, is not valid JSON, or fails :func:`validate_document`
    raises :class:`TypedWorkflowError`. Returns :meth:`Workflow.to_document` of the
    validated document (stages normalized, ``kind``/``spec_version`` explicit).
    """
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix in SCRIPT_SUFFIXES:
        raise TypedWorkflowError(
            f"bespoke script refused: {target.name!r} is a {suffix} program; "
            "a typed workflow must be a JSON document"
        )
    if suffix != JSON_SUFFIX:
        raise TypedWorkflowError(
            f"typed workflow must be a {JSON_SUFFIX} JSON document, got {target.name!r}"
        )
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        reason = exc.strerror or type(exc).__name__
        raise TypedWorkflowError(f"cannot read typed workflow {target.name!r}: {reason}") from exc
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TypedWorkflowError(
            f"typed workflow {target.name!r} is not valid JSON: {exc.msg} (line {exc.lineno})"
        ) from exc
    return Workflow.from_document(doc).to_document()


def _checked_handler_table(
    workflow: Workflow, handler_table: Mapping[str, Handler] | None
) -> Mapping[str, Handler]:
    """Fail closed before any stage runs: every stage handler must be present and callable."""
    table: Mapping[str, Handler] = handler_table if handler_table is not None else {}
    if not isinstance(table, Mapping):
        raise TypedWorkflowError(
            "handler_table must map handler name -> callable, "
            f"got {type(table).__name__}"
        )
    missing = [name for name in workflow.handler_names() if name not in table]
    not_callable = [
        name for name in workflow.handler_names() if name in table and not callable(table[name])
    ]
    problems: list[str] = []
    if missing:
        problems.append("missing handlers " + ", ".join(repr(name) for name in missing))
    if not_callable:
        problems.append("non-callable handlers " + ", ".join(repr(name) for name in not_callable))
    if problems:
        raise TypedWorkflowError(
            f"workflow {workflow.id!r} cannot be dispatched: " + "; ".join(problems)
        )
    return table


def execute(
    workflow: Workflow | Mapping[str, Any],
    *,
    inputs: Mapping[str, Any] | None = None,
    handler_table: Mapping[str, Handler] | None = None,
) -> dict[str, Any]:
    """Run every stage of ``workflow`` in document order and return a deterministic receipt.

    ``workflow`` is a :class:`Workflow` or a document accepted by
    :meth:`Workflow.from_document`. ``inputs`` are copied onto ``ctx["inputs"]`` untouched;
    handlers are looked up by stage ``handler`` name in ``handler_table`` and called as
    ``handler(ctx)`` with the shared mapping::

        ctx = {"inputs": {...}, "result": {...}, "workflow_id": str,
               "stage": <current stage id>, "completed": [<stage ids>]}

    A handler communicates by mutating (or replacing) ``ctx["result"]``, which must stay a
    mapping. A handler that raises marks its stage ``failed``; the remaining stages are
    recorded as ``skipped`` and the receipt carries ``ok=False`` plus the ``error``. A
    document or handler-table defect raises :class:`TypedWorkflowError` before any stage
    runs. Nothing here spawns a process; ``spawned`` is always ``False``.
    """
    wf = workflow if isinstance(workflow, Workflow) else Workflow.from_document(workflow)
    if inputs is None:
        inputs = {}
    if not isinstance(inputs, Mapping):
        raise TypedWorkflowError(f"inputs must be a mapping, got {type(inputs).__name__}")
    table = _checked_handler_table(wf, handler_table)

    ctx: dict[str, Any] = {
        "inputs": dict(inputs),
        "result": {},
        "workflow_id": wf.id,
        "stage": None,
        "completed": [],
    }
    trace: list[dict[str, Any]] = []
    error: dict[str, Any] | None = None
    for stage in wf.stages:
        row = {"id": stage.id, "handler": stage.handler, "kind": stage.kind, "status": "skipped"}
        trace.append(row)
        if error is not None:
            continue
        ctx["stage"] = stage.id
        try:
            table[stage.handler](ctx)
            result = ctx.get("result")
            if not isinstance(result, Mapping):
                raise TypedWorkflowError(
                    f"handler {stage.handler!r} replaced ctx['result'] with "
                    f"{type(result).__name__}; a mapping is required"
                )
        except Exception as exc:  # noqa: BLE001 - a failing stage is a recorded outcome, not a crash
            row["status"] = "failed"
            error = {
                "stage": stage.id,
                "handler": stage.handler,
                "type": type(exc).__name__,
                "message": str(exc),
            }
            continue
        row["status"] = "completed"
        ctx["completed"].append(stage.id)
    ctx["stage"] = None

    result = ctx["result"]
    outputs = dict(result) if isinstance(result, Mapping) else {}
    return {
        "engine": ENGINE,
        "spec_version": wf.spec_version,
        "workflow_id": wf.id,
        "ok": error is None,
        "outputs": outputs,
        "inputs": dict(inputs),
        "trace": trace,
        "stages_total": len(wf.stages),
        "stages_completed": len(ctx["completed"]),
        "error": error,
        "spawned": False,
        "bespoke_script": False,
    }


__all__ = [
    "DEFAULT_STAGE_KIND",
    "DOCUMENT_KIND",
    "ENGINE",
    "Handler",
    "SCRIPT_SUFFIXES",
    "SPEC_VERSION",
    "Stage",
    "TypedWorkflowError",
    "Workflow",
    "execute",
    "load_workflow",
    "validate_document",
]
