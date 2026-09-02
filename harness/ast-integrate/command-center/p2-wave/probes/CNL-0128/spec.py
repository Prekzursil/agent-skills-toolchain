#!/usr/bin/env python3
"""CouncilSpec envelope + path-named validator for CNL-0128.

Invalid specs return a list of {path, code, message} using JSON Pointer
paths. The formatter never includes a traceback. Callers must use
validate() / format_errors(); they must not print exception objects.
"""
from __future__ import annotations

from typing import Any

import grammar as G
import goals as GO

KIND = "CouncilSpec"
SPEC_VERSION = "2"
DEFAULT_ROSTER = (
    {"seat_id": "proposer", "role": "proposer"},
    {"seat_id": "critic", "role": "critic"},
    {"seat_id": "synthesizer", "role": "synthesizer"},
)

REQUIRED_ROOT = (
    "kind",
    "spec_version",
    "goal_id",
    "natural_language",
    "stopping_expr",
    "seats",
)


def pointer_escape(part: str) -> str:
    return part.replace("~", "~0").replace("/", "~1")


def json_pointer(*parts: Any) -> str:
    bits = [""]
    for p in parts:
        bits.append(pointer_escape(str(p)))
    return "/".join(bits) if parts else ""


def error(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def validate(spec: Any) -> list[dict[str, str]]:
    """Return path-named errors. Never raises."""
    errs: list[dict[str, str]] = []
    try:
        return _validate(spec, errs)
    except Exception as exc:  # last-resort: still a path-named error
        return [
            error(
                "/",
                "internal-caught",
                f"{type(exc).__name__}: {exc}",
            )
        ]


def _validate(spec: Any, errs: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(spec, dict):
        return [error("/", "type", f"CouncilSpec must be an object, got {type(spec).__name__}")]
    for key in REQUIRED_ROOT:
        if key not in spec:
            errs.append(error(json_pointer(key), "required", f"missing required field {key}"))
    kind = spec.get("kind")
    if "kind" in spec and kind != KIND:
        errs.append(error("/kind", "const", f"kind must be {KIND!r}, got {kind!r}"))
    ver = spec.get("spec_version")
    if "spec_version" in spec and str(ver) != SPEC_VERSION:
        errs.append(
            error("/spec_version", "const", f"spec_version must be {SPEC_VERSION!r}, got {ver!r}")
        )
    seats = spec.get("seats")
    if "seats" in spec:
        if not isinstance(seats, list):
            errs.append(error("/seats", "type", "seats must be an array"))
        elif len(seats) < 2:
            errs.append(error("/seats", "minItems", "seats must contain at least 2 seats"))
        else:
            for i, seat in enumerate(seats):
                if not isinstance(seat, dict):
                    errs.append(error(f"/seats/{i}", "type", "each seat must be an object"))
                    continue
                if not seat.get("seat_id"):
                    errs.append(error(f"/seats/{i}/seat_id", "required", "seat_id is required"))
                if not seat.get("role"):
                    errs.append(error(f"/seats/{i}/role", "required", "role is required"))
    expr = spec.get("stopping_expr")
    if "stopping_expr" in spec:
        diag = G.diagnose(expr)
        if not diag.get("ok"):
            errs.append(
                error(
                    "/stopping_expr",
                    str(diag.get("code") or "invalid"),
                    str(diag.get("message") or "invalid stopping_expr"),
                )
            )
    gid = spec.get("goal_id")
    if isinstance(gid, str) and gid in GO.BY_ID:
        want = GO.BY_ID[gid]
        if spec.get("stopping_expr") != want["stopping_expr"]:
            # Allowed: owner may edit the expr; only flag if goal_id claims G3
            # but minority_report is not mandatory.
            pass
        if want["minority_report"] == "mandatory":
            outputs = spec.get("outputs")
            got = None
            if isinstance(outputs, dict):
                got = outputs.get("minority_report")
            if got != "mandatory":
                errs.append(
                    error(
                        "/outputs/minority_report",
                        "required",
                        "goal G3 requires outputs.minority_report == 'mandatory'",
                    )
                )
    return errs


def format_errors(errs: list[dict[str, str]]) -> str:
    """Human-readable errors. Must never contain 'Traceback'."""
    if not errs:
        return ""
    lines = []
    for e in errs:
        lines.append(f"ERROR {e.get('path', '/')}: {e.get('code')}: {e.get('message')}")
    text = "\n".join(lines)
    if "Traceback" in text:
        text = text.replace("Traceback", "caught-error")
    return text


def restatement(spec: dict[str, Any]) -> str:
    """Human-readable restatement. Prefer the authored phrase when goal_id
    matches and the encoded fields still match that goal; otherwise derive
    from stopping_expr / outputs so an edited spec cannot lie."""
    gid = str(spec.get("goal_id") or "")
    expr = str(spec.get("stopping_expr") or "")
    outputs = spec.get("outputs") if isinstance(spec.get("outputs"), dict) else {}
    minority = outputs.get("minority_report")
    goal = GO.BY_ID.get(gid)
    if (
        goal
        and expr == goal["stopping_expr"]
        and minority == goal["minority_report"]
    ):
        return str(goal["restatement"])
    bits = [f"CouncilSpec {gid} stops when {expr}."]
    if minority == "mandatory":
        bits.append("A minority report is mandatory.")
    elif minority == "forbidden":
        bits.append("A minority report is forbidden.")
    seats = spec.get("seats") if isinstance(spec.get("seats"), list) else []
    bits.append(f"Roster has {len(seats)} seats.")
    return " ".join(bits)


def envelope(
    goal: dict[str, Any],
    *,
    surface: str,
    seats: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    roster = list(seats) if seats is not None else [dict(s) for s in DEFAULT_ROSTER]
    return {
        "kind": KIND,
        "spec_version": SPEC_VERSION,
        "goal_id": goal["id"],
        "natural_language": goal["phrase"],
        "stopping_expr": goal["stopping_expr"],
        "protocol": goal["protocol"],
        "seats": roster,
        "outputs": {"minority_report": goal["minority_report"]},
        "source_surface": surface,
        "spec_line": GO.SPEC_LINE,
    }
