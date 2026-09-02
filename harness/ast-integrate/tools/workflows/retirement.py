"""Workflow catalog retirement: supersession + deprecation with typed warnings.

A retired workflow is never deleted out from under its consumers. Retirement is
a RECORD (``SUPERSESSION`` or ``DEPRECATION``) kept next to the body, so a
retired id keeps resolving (to its successor) and a pinned consumer keeps
executing with a typed warning instead of a hard break. Deleting anything that
is still referenced -- by a consumer pin or by a retirement record -- is
refused with :class:`DeleteRefused`.
"""
from __future__ import annotations

from typing import Any

KIND_SUPERSESSION = "SUPERSESSION"
KIND_DEPRECATION = "DEPRECATION"
RETIREMENT_KINDS = frozenset({KIND_SUPERSESSION, KIND_DEPRECATION})
WARN_SUPERSEDED = "WARN_SUPERSEDED"
WARN_DEPRECATED = "WARN_DEPRECATED"

REF_CONSUMER_PIN = "consumer_pin"
REF_RETIREMENT_RECORD = "retirement_record"
DELETE_REFUSED = "DELETE_REFUSED"


class NotFound(KeyError):
    """The id names neither a published body nor a retirement record."""


class SchemaError(ValueError):
    """A retirement record is missing a field its kind requires."""


class DeleteRefused(RuntimeError):
    """A delete was attempted on a workflow that something still references."""

    def __init__(self, workflow_id: str, references: list[dict[str, Any]]) -> None:
        self.workflow_id = workflow_id
        self.references = [dict(r) for r in references]
        kinds = sorted({r["kind"] for r in self.references})
        super().__init__(
            f"{DELETE_REFUSED}: {workflow_id} is referenced by {len(self.references)} "
            f"record(s) ({', '.join(kinds)}); retire it instead"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": DELETE_REFUSED,
            "workflow_id": self.workflow_id,
            "references": [dict(r) for r in self.references],
        }


class Catalog:
    """In-memory workflow catalog with pins and retirement records."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._pins: dict[str, str] = {}
        self._retire: dict[str, dict[str, Any]] = {}

    # -- publication / pinning -------------------------------------------------

    def publish(self, rec: dict[str, Any]) -> None:
        iid = rec.get("id")
        if not iid:
            raise SchemaError("publish requires id")
        self._items[str(iid)] = dict(rec)

    def pin_consumer(self, consumer_id: str, workflow_id: str) -> None:
        if workflow_id not in self._items:
            raise NotFound(workflow_id)
        self._pins[consumer_id] = workflow_id

    # -- retirement ------------------------------------------------------------

    def retire(self, rec: dict[str, Any]) -> None:
        """Validate and store a retirement record. Only the two closed kinds are legal."""
        kind = rec.get("kind")
        if kind not in RETIREMENT_KINDS:
            raise SchemaError(f"unsupported retirement kind {kind}")
        retired_id = rec.get("retired_id")
        if not retired_id:
            raise SchemaError("retired_id required")
        if kind == KIND_SUPERSESSION:
            if not rec.get("successor_id"):
                raise SchemaError("supersession-without-successor")
            migration = rec.get("migration")
            if not migration or not isinstance(migration, dict) or not migration.get("path"):
                raise SchemaError("supersession-without-migration")
            if rec["successor_id"] not in self._items:
                raise SchemaError("dangling-successor")
        if kind == KIND_DEPRECATION:
            if not rec.get("reason"):
                raise SchemaError("deprecation-without-reason")
            if not rec.get("removal_date"):
                raise SchemaError("deprecation-without-removal-date")
            successor_id = rec.get("successor_id")
            if successor_id and successor_id not in self._items:
                raise SchemaError("dangling-successor")
        self._retire[str(retired_id)] = dict(rec)

    def supersede(
        self,
        old_id: str,
        new_id: str,
        migration: dict[str, Any],
        retired_at: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.retire(
            {
                "kind": KIND_SUPERSESSION,
                "retired_id": old_id,
                "successor_id": new_id,
                "migration": migration,
                "retired_at": retired_at,
                "reason": reason,
            }
        )

    def deprecate(
        self,
        old_id: str,
        reason: str = "",
        removal_date: str = "",
        successor_id: str | None = None,
        retired_at: str | None = None,
    ) -> None:
        rec: dict[str, Any] = {
            "kind": KIND_DEPRECATION,
            "retired_id": old_id,
            "reason": reason,
            "removal_date": removal_date,
            "retired_at": retired_at,
        }
        if successor_id:
            rec["successor_id"] = successor_id
        self.retire(rec)

    # -- lookup ----------------------------------------------------------------

    def resolve(self, workflow_id: str) -> dict[str, Any]:
        """Resolve an id to its body and, when retired, its record and successor."""
        item = self._items.get(workflow_id)
        rec = self._retire.get(workflow_id)
        if item is None and rec is None:
            raise NotFound(workflow_id)
        successor_id = (rec or {}).get("successor_id")
        successor = self._items.get(str(successor_id)) if successor_id else None
        return {
            "present": item is not None,
            "retired": rec is not None,
            "kind": (rec or {}).get("kind"),
            "id": workflow_id,
            "body": (item or {}).get("body"),
            "successor_id": successor_id,
            "successor": successor,
            "record": rec,
        }

    def references(self, workflow_id: str) -> list[dict[str, Any]]:
        """Everything that still points at ``workflow_id``: pins and retirement records."""
        refs: list[dict[str, Any]] = []
        for consumer_id, target in sorted(self._pins.items()):
            if target == workflow_id:
                refs.append({"kind": REF_CONSUMER_PIN, "consumer_id": consumer_id})
        for retired_id, rec in sorted(self._retire.items()):
            if retired_id == workflow_id:
                refs.append(
                    {"kind": REF_RETIREMENT_RECORD, "role": "retired_id", "retired_id": retired_id}
                )
            elif rec.get("successor_id") == workflow_id:
                refs.append(
                    {"kind": REF_RETIREMENT_RECORD, "role": "successor_id", "retired_id": retired_id}
                )
        return refs

    def snapshot(self) -> dict[str, Any]:
        return {
            "items": {k: dict(v) for k, v in self._items.items()},
            "pins": dict(self._pins),
            "retirements": {k: dict(v) for k, v in self._retire.items()},
        }

    # -- deletion --------------------------------------------------------------

    def delete(self, workflow_id: str) -> None:
        """Remove an UNREFERENCED body. Anything referenced must be retired, not deleted."""
        if workflow_id not in self._items and workflow_id not in self._retire:
            raise NotFound(workflow_id)
        refs = self.references(workflow_id)
        if refs:
            raise DeleteRefused(workflow_id, refs)
        self._items.pop(workflow_id, None)
        self._retire.pop(workflow_id, None)

    def force_drop_for_probe(self, workflow_id: str) -> None:
        """The silent-deletion mutant (the 11347 failure). NOT part of the public path.

        Drops body and record without checking references, so probes can show that
        resolve() and pinned execution hard-break when this path is taken.
        """
        self._items.pop(workflow_id, None)
        self._retire.pop(workflow_id, None)

    # -- execution -------------------------------------------------------------

    def execute_consumer(self, consumer_id: str) -> dict[str, Any]:
        wid = self._pins.get(consumer_id)
        if not wid:
            raise NotFound(consumer_id)
        return self._execute(wid, pinned=True)

    def execute_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._execute(workflow_id, pinned=False)

    def _execute(self, workflow_id: str, pinned: bool) -> dict[str, Any]:
        item = self._items.get(workflow_id)
        if item is None:
            raise NotFound(workflow_id)
        rec = self._retire.get(workflow_id)
        warnings: list[dict[str, Any]] = []
        if rec and rec.get("kind") == KIND_SUPERSESSION:
            warnings.append(
                {
                    "code": WARN_SUPERSEDED,
                    "successor_id": rec.get("successor_id"),
                    "retired_id": workflow_id,
                    "migration": dict(rec.get("migration") or {}),
                }
            )
        if rec and rec.get("kind") == KIND_DEPRECATION:
            warnings.append(
                {
                    "code": WARN_DEPRECATED,
                    "successor_id": rec.get("successor_id"),
                    "retired_id": workflow_id,
                    "reason": rec.get("reason"),
                    "removal_date": rec.get("removal_date"),
                }
            )
        return {
            "ok": True,
            "hard_break": False,
            "executed_id": workflow_id,
            "body": item.get("body"),
            "warnings": warnings,
            "pinned": pinned,
        }
