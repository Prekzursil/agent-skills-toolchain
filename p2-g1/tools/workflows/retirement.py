"""Workflow catalog retirement: supersession + deprecation with typed warnings."""
from __future__ import annotations

from typing import Any

KIND_SUPERSESSION = "SUPERSESSION"
KIND_DEPRECATION = "DEPRECATION"
WARN_SUPERSEDED = "WARN_SUPERSEDED"
WARN_DEPRECATED = "WARN_DEPRECATED"


class NotFound(KeyError):
    pass


class SchemaError(ValueError):
    pass


class DeleteRefused(Exception):
    """FC-11347: retirement is never silent removal; delete() refuses."""


class Catalog:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._pins: dict[str, str] = {}
        self._retire: dict[str, dict[str, Any]] = {}

    def publish(self, rec: dict[str, Any]) -> None:
        iid = rec.get("id")
        if not iid:
            raise SchemaError("publish requires id")
        self._items[str(iid)] = dict(rec)

    def pin_consumer(self, consumer_id: str, workflow_id: str) -> None:
        if workflow_id not in self._items:
            raise NotFound(workflow_id)
        self._pins[consumer_id] = workflow_id

    def retire(self, rec: dict[str, Any]) -> None:
        # One rule source: the same validator the schema probe uses.
        ok, errors = validate_retirement(rec, published_ids=set(self._items))
        if not ok:
            raise SchemaError(";".join(errors))
        self._retire[str(rec["retired_id"])] = dict(rec)

    def supersede(
        self,
        old_id: str,
        new_id: str,
        migration: dict[str, Any],
        retired_at: str | None = None,
        reason: str | None = None,
    ) -> None:
        if not migration or not migration.get("path"):
            raise SchemaError("supersession-without-migration")
        if new_id not in self._items:
            raise SchemaError("dangling-successor")
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
        if not reason:
            raise SchemaError("deprecation-without-reason")
        if not removal_date:
            raise SchemaError("deprecation-without-removal-date")
        rec = {
            "kind": KIND_DEPRECATION,
            "retired_id": old_id,
            "reason": reason,
            "removal_date": removal_date,
            "retired_at": retired_at,
        }
        if successor_id:
            rec["successor_id"] = successor_id
        self.retire(rec)

    def resolve(self, workflow_id: str) -> dict[str, Any]:
        item = self._items.get(workflow_id)
        rec = self._retire.get(workflow_id)
        if item is None and rec is None:
            raise NotFound(workflow_id)
        successor_id = (rec or {}).get("successor_id")
        successor = self._items.get(str(successor_id)) if successor_id else None
        return {
            "present": item is not None,
            "retired": rec is not None,
            "id": workflow_id,
            "body": (item or {}).get("body"),
            "successor_id": successor_id,
            "successor": successor,
            "record": rec,
        }

    def execute_consumer(self, consumer_id: str) -> dict[str, Any]:
        wid = self._pins.get(consumer_id)
        if not wid:
            raise NotFound(consumer_id)
        return self._execute(wid, pinned=True)

    def execute_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._execute(workflow_id, pinned=False)

    def _execute(self, workflow_id: str, pinned: bool) -> dict[str, Any]:
        rec = self._retire.get(workflow_id)
        item = self._items.get(workflow_id)
        warnings = []
        if rec and rec.get("kind") == KIND_SUPERSESSION:
            warnings.append(
                {
                    "code": WARN_SUPERSEDED,
                    "successor_id": rec.get("successor_id"),
                    "retired_id": workflow_id,
                }
            )
        if rec and rec.get("kind") == KIND_DEPRECATION:
            warnings.append(
                {
                    "code": WARN_DEPRECATED,
                    "successor_id": rec.get("successor_id"),
                    "retired_id": workflow_id,
                }
            )
        return {
            "ok": True,
            "hard_break": False,
            "executed_id": workflow_id,
            "body": (item or {}).get("body"),
            "warnings": warnings,
            "pinned": pinned,
        }

    def delete(self, workflow_id: str) -> None:
        """Refuse deletion of a referenced or retired workflow (FC-11347)."""
        if workflow_id in self._pins.values():
            raise DeleteRefused(f"{workflow_id} is pinned by a consumer")
        if workflow_id in self._retire:
            raise DeleteRefused(f"{workflow_id} carries a retirement record")
        if workflow_id in self._items:
            raise DeleteRefused(f"{workflow_id} is published; retire it first")
        raise NotFound(workflow_id)

    def force_drop_for_probe(self, workflow_id: str) -> None:
        """MUTANT: the silent-deletion counterexample. Drops body AND record so
        probes can prove that resolve()/execute hard-break without retirement -
        the exact behaviour the public delete() path must never have."""
        self._items.pop(workflow_id, None)
        self._retire.pop(workflow_id, None)
        self._pins = {k: v for k, v in self._pins.items() if v != workflow_id}


def validate_retirement(rec: dict[str, Any], published_ids: set[str] | None = None):
    """Validate a retirement record. Returns (ok, errors).

    Only SUPERSESSION (successor + migration, successor must be published when
    ``published_ids`` is given) or DEPRECATION (reason + removal_date) are
    admitted; a DELETION kind or a dangling successor is rejected.
    """
    errors: list[str] = []
    kind = rec.get("kind")
    if kind == "DELETION":
        errors.append("deletion-kind-rejected")
        return False, errors
    if kind not in {KIND_SUPERSESSION, KIND_DEPRECATION}:
        errors.append(f"unsupported-retirement-kind:{kind}")
        return False, errors
    if not rec.get("retired_id"):
        errors.append("retired_id-required")
    if kind == KIND_SUPERSESSION:
        if not rec.get("successor_id"):
            errors.append("supersession-without-successor")
        if not rec.get("migration"):
            errors.append("supersession-without-migration")
        elif not (rec.get("migration") or {}).get("path"):
            errors.append("supersession-migration-without-path")
        if rec.get("successor_id") and published_ids is not None                 and rec["successor_id"] not in published_ids:
            errors.append("dangling-successor")
    if kind == KIND_DEPRECATION:
        if not rec.get("reason"):
            errors.append("deprecation-without-reason")
        if not rec.get("removal_date"):
            errors.append("deprecation-without-removal-date")
    return (not errors), errors
