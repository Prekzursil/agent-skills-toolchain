"""Split role-mandate checker: unmet obligation fails; unused permission does not."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
V2_SCHEMA = HERE / "role_mandate.schema.json"
V1_SCHEMA = HERE / "defs_role_v1.schema.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def draft2020_validator(schema: dict):
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def error_count(validator, instance) -> tuple[int, list[str]]:
    msgs = []
    n = 0
    for err in validator.iter_errors(instance):
        n += 1
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        msgs.append(f"{path}: {err.message}")
    return n, msgs


def grant_ids(role: dict) -> dict[str, set[str]]:
    buckets = {
        "obligation": {x["id"] for x in role.get("obligations") or []},
        "permission": {x["id"] for x in role.get("permissions") or []},
        "right": {x["id"] for x in role.get("rights") or []},
    }
    return buckets


def overlapping_ids(role: dict) -> list[str]:
    b = grant_ids(role)
    overlap = (b["obligation"] & b["permission"]) | (b["obligation"] & b["right"]) | (
        b["permission"] & b["right"]
    )
    return sorted(overlap)


def check_seat(role: dict, seat: dict) -> list[dict]:
    """v2 check. Unused permissions never produce an error."""
    findings: list[dict] = []
    discharged = set(seat.get("discharged") or [])
    denied = set(seat.get("denied_rights") or [])
    for ob in role.get("obligations") or []:
        oid = ob["id"]
        if oid not in discharged:
            findings.append(
                {
                    "code": "UNMET_OBLIGATION",
                    "id": oid,
                    "artifact": ob.get("discharge_artifact"),
                }
            )
    for perm in role.get("permissions") or []:
        # Explicit no-op: unused permission is not a finding.
        _ = perm["id"]
    for rt in role.get("rights") or []:
        rid = rt["id"]
        if rid in denied:
            findings.append({"code": "DENIED_RIGHT", "id": rid})
    return findings


def v1_conflated_check(role_v1: dict, seat: dict) -> list[dict]:
    """Treat every permissions[] string as something that MUST be discharged.

    That is the natural checker on a conflated string bag: unused optional
    tools fail the same way unmet duties fail.
    """
    discharged = set(seat.get("discharged") or [])
    used = set(seat.get("used_permissions") or [])
    done = discharged | used
    findings = []
    for item in role_v1.get("permissions") or []:
        if item not in done:
            findings.append({"code": "UNMET_PERMISSIONS_BAG", "id": item})
    return findings


def role_by_id(catalogue: dict, role_id: str) -> dict:
    for role in catalogue.get("roles") or []:
        if role.get("id") == role_id:
            return role
    raise KeyError(role_id)
