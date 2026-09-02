"""REL-0002 rollback-contract validator.

Draft 2020-12 structural schema plus the two hard invariants the catalog
names: an inverse target must sit inside that action's recorded creation
set, and an inverse must not remove a command, skill or setting that
pre-dated the install.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from jsonschema.exceptions import ValidationError
from jsonschema.validators import Draft202012Validator, extend

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROLLBACK_SCHEMA = (
    REPO / "command-center" / "schema" / "rollback-contract.schema.json"
)
RECEIPT_SCHEMA = (
    REPO / "command-center" / "schema" / "contract-spec-receipt.schema.json"
)

INV_PATH = "an inverse may never remove a path the installer did not create"
INV_PREDATE = (
    "an inverse may never remove a command, skill or setting that pre-dated "
    "the install"
)
REMOVAL_KINDS = frozenset(
    {
        "delete_path",
        "unregister_hook",
        "remove_mcp_entry",
        "delete_scheduled_task",
        "purge_seeded_cache",
        "remove_state_record",
    }
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _invariants_keyword(
    validator, flag: object, instance: object, schema: object
) -> Iterator[ValidationError]:
    if not flag or not isinstance(instance, dict):
        return
    creation_doc = instance.get("recorded_creation_set")
    predates = instance.get("predated_install_set")
    actions = instance.get("actions")
    if not isinstance(creation_doc, list) or not isinstance(predates, list):
        return
    if not isinstance(actions, list):
        return
    creation_set = {str(x) for x in creation_doc}
    predate_set = {str(x) for x in predates}
    overlap = sorted(creation_set & predate_set)
    if overlap:
        yield ValidationError(
            f"recorded_creation_set overlaps predated_install_set: {overlap}"
        )
    union: set[str] = set()
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        creates = {str(x) for x in (action.get("creates") or [])}
        union |= creates
        inverse = action.get("inverse")
        if not isinstance(inverse, dict):
            continue
        target = str(inverse.get("target") or "")
        kind = str(inverse.get("kind") or "")
        removes = inverse.get("removes")
        if removes is None:
            removes = kind in REMOVAL_KINDS
        if target and target not in creates:
            yield ValidationError(
                f"{INV_PATH}: inverse target {target!r} lies outside the "
                f"recorded creation set {sorted(creates)}",
                path=["actions", i, "inverse", "target"],
            )
        if removes and target and target in predate_set:
            yield ValidationError(
                f"{INV_PREDATE}: inverse target {target!r} is in "
                "predated_install_set",
                path=["actions", i, "inverse", "target"],
            )
        if target and target not in creation_set:
            yield ValidationError(
                f"{INV_PATH}: inverse target {target!r} is absent from "
                "document recorded_creation_set",
                path=["actions", i, "inverse", "target"],
            )
    missing = sorted(union - creation_set)
    extra = sorted(creation_set - union)
    if missing or extra:
        yield ValidationError(
            "recorded_creation_set must equal the union of action.creates "
            f"(missing={missing} extra={extra})"
        )


Rel0002Validator = extend(
    Draft202012Validator, {"x-rel0002-invariants": _invariants_keyword}
)


def rollback_schema() -> dict[str, Any]:
    return load_json(ROLLBACK_SCHEMA)


def receipt_schema() -> dict[str, Any]:
    return load_json(RECEIPT_SCHEMA)


def check_meta(schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)


def rollback_validator() -> Draft202012Validator:
    schema = rollback_schema()
    check_meta(schema)
    return Rel0002Validator(schema)


def receipt_validator() -> Draft202012Validator:
    schema = receipt_schema()
    check_meta(schema)
    return Draft202012Validator(schema)


def error_strings(validator: Draft202012Validator, instance: object) -> list[str]:
    out = []
    for err in validator.iter_errors(instance):
        loc = "/".join(str(p) for p in err.path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def locate_invariants() -> list[dict[str, Any]]:
    rel = ROLLBACK_SCHEMA.relative_to(REPO).as_posix()
    lines = ROLLBACK_SCHEMA.read_text(encoding="utf-8").splitlines()
    found: list[dict[str, Any]] = []
    wanted = [("INV-PATH", INV_PATH), ("INV-PREDATE", INV_PREDATE)]
    for inv_id, text in wanted:
        hits = [i for i, line in enumerate(lines, 1) if text in line]
        if len(hits) < 1:
            raise RuntimeError(f"invariant {inv_id} not found in {rel}")
        found.append(
            {
                "id": inv_id,
                "text": text,
                "file": rel,
                "line": hits[0],
                "occurrences": hits,
            }
        )
    return found


def mutant_no_inverse_no_irreversible(doc: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(doc)
    action = out["actions"][0]
    action.pop("inverse", None)
    action.pop("irreversible", None)
    action.pop("post_inverse_invariant", None)
    return out


def mutant_inverse_outside_creation_set(doc: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(doc)
    outsider = str(out["predated_install_set"][0])
    action = out["actions"][0]
    action["inverse"]["target"] = outsider
    action["inverse"]["removes"] = True
    return out


def mutant_partial_omits_residue(doc: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(doc)
    for action in out["actions"]:
        inv = action.get("inverse") or {}
        if inv.get("completeness") == "partial":
            inv.pop("residue", None)
            return out
    raise RuntimeError("inventory has no partial inverse to strip residue from")
