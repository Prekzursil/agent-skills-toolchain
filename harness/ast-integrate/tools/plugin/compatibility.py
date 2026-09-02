"""Support-contract compatibility gate and both-states matrix (TST-0078).

The plugin publishes a *support contract*: a declared list of client / client
version / operating-system cells, each marked SUPPORTED or UNSUPPORTED, derived
from one policy (``supported_clients``, a version floor and a version ceiling)
over the platforms the plugin is actually tested on.  Every cartesian cell of
the axes that is *not* declared is UNTESTED: it is never inferred SUPPORTED and
is never silently omitted from a matrix run.

The install gate (`negotiate` / `attempt_install`) fails closed: it refuses an
UNSUPPORTED cell, an undeclared cell, an incomplete cell and an unparsable
version, writing zero files in every refusal.  `run_matrix` attempts an install
for every declared cell against a published fixture and records, per cell,
whether the observed outcome matched the declaration - the both-states evidence
the receipt for TST-0078 carries.

The on-disk contract (`support_contract.json`, next to this module) is the
serialisation of `build_contract()`; `load_contract` validates it structurally
and falls back to the builder when the file is absent.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "support_contract.json"

# --- declared support policy -------------------------------------------------
SUPPORTED_CLIENTS: tuple[str, ...] = ("claude-code", "codex-cli")
MIN_CLIENT_VERSION = "2.0.0"
MAX_CLIENT_VERSION = "2.0.0"
# Platforms the plugin is exercised on; every other OS axis value stays UNTESTED.
TESTED_PLATFORMS: tuple[str, ...] = ("linux", "windows")

# --- matrix axes (the negative probes are deliberate: an unknown client, a
# version below the floor and one above the ceiling) -------------------------
OS_AXIS: tuple[str, ...] = ("linux", "windows", "macos")
CLIENT_AXIS: tuple[str, ...] = ("claude-code", "codex-cli", "antigravity")
VERSION_AXIS: tuple[str, ...] = ("1.0.0", "2.0.0", "3.0.0")
AXIS_ORDER: tuple[str, ...] = ("os", "client", "client_version")

SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
UNTESTED = "UNTESTED"
PROCEEDED = "PROCEEDED"
REFUSED = "REFUSED"

REASON_SUPPORTED = "supported"
REASON_UNSUPPORTED_CLIENT = "unsupported-client"
REASON_BELOW_FLOOR = "below-floor"
REASON_ABOVE_CEILING = "above-ceiling"
REASON_UNTESTED = "untested"
REASON_UNPARSABLE = "unparsable-version"
REASON_INCOMPLETE = "incomplete-cell"
DECLARED_REASONS: tuple[str, ...] = (
    REASON_SUPPORTED,
    REASON_UNSUPPORTED_CLIENT,
    REASON_BELOW_FLOOR,
    REASON_ABOVE_CEILING,
)

UNTESTED_RULE = (
    "A cartesian cell absent from declared[] is UNTESTED. It is never inferred "
    "SUPPORTED and is never silently omitted from the receipt."
)
VERSION_PATTERN = r"^[0-9]+(\.[0-9]+)*$"
_VERSION_RE = re.compile(VERSION_PATTERN)
_OS_ENUM = ["linux", "windows", "macos"]

CONTRACT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Plugin support contract (client x client_version x os)",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "artifact",
        "supported_clients",
        "min_client_version",
        "max_client_version",
        "tested_platforms",
        "axes",
        "declared",
        "untested_rule",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "artifact": {"const": "support-contract"},
        "supported_clients": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "min_client_version": {"type": "string", "pattern": VERSION_PATTERN},
        "max_client_version": {"type": "string", "pattern": VERSION_PATTERN},
        "tested_platforms": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"enum": _OS_ENUM},
        },
        "axes": {
            "type": "object",
            "additionalProperties": False,
            "required": list(AXIS_ORDER),
            "properties": {
                "os": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"enum": _OS_ENUM},
                },
                "client": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
                "client_version": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"type": "string", "pattern": VERSION_PATTERN},
                },
            },
        },
        "declared": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "os",
                    "client",
                    "client_version",
                    "cell_id",
                    "status",
                    "reason_code",
                ],
                "properties": {
                    "os": {"enum": _OS_ENUM},
                    "client": {"type": "string", "minLength": 1},
                    "client_version": {"type": "string", "pattern": VERSION_PATTERN},
                    "cell_id": {"type": "string", "minLength": 5},
                    "status": {"enum": [SUPPORTED, UNSUPPORTED]},
                    "reason_code": {"enum": list(DECLARED_REASONS)},
                },
            },
        },
        "untested_rule": {"type": "string", "minLength": 1},
    },
}


class ContractError(ValueError):
    """The support contract is structurally invalid or self-contradictory."""


# --- cells and versions -------------------------------------------------------
def cell_id(os_name: str, client: str, client_version: str) -> str:
    """Stable identity of one matrix cell: ``os|client|client_version``."""
    return f"{os_name}|{client}|{client_version}"


def cell_id_of(cell: dict[str, Any]) -> str:
    return cell_id(str(cell["os"]), str(cell["client"]), str(cell["client_version"]))


def parse_version(text: Any) -> tuple[int, ...] | None:
    """Parse a dotted numeric version; ``None`` when it is not one."""
    if not isinstance(text, str) or not _VERSION_RE.match(text):
        return None
    return tuple(int(part) for part in text.split("."))


def compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    """Three-way compare with zero-padding (``2.0`` == ``2.0.0``)."""
    width = max(len(left), len(right))
    a = left + (0,) * (width - len(left))
    b = right + (0,) * (width - len(right))
    return (a > b) - (a < b)


def cartesian(axes: dict[str, list[str]]) -> list[dict[str, str]]:
    """Every combination of the axes, os-major in `AXIS_ORDER` then any extra axis."""
    ordered = [name for name in AXIS_ORDER if name in axes]
    ordered += [name for name in axes if name not in ordered]
    cells: list[dict[str, str]] = [{}]
    for axis in ordered:
        values = axes[axis]
        if not isinstance(values, (list, tuple)) or not values:
            raise ContractError(f"axis {axis!r} must be a non-empty list")
        cells = [dict(cell, **{axis: str(val)}) for cell in cells for val in values]
    return cells


# --- the contract --------------------------------------------------------------
def classify(cell: dict[str, Any], contract: dict[str, Any]) -> tuple[str, str]:
    """Apply the support policy to a parsable cell -> (status, reason_code)."""
    version = parse_version(cell.get("client_version"))
    if version is None:
        raise ContractError(f"unparsable client_version in {cell!r}")
    if cell.get("client") not in contract["supported_clients"]:
        return UNSUPPORTED, REASON_UNSUPPORTED_CLIENT
    floor = parse_version(contract["min_client_version"])
    ceiling = parse_version(contract["max_client_version"])
    if floor is None or ceiling is None:
        raise ContractError("contract floor/ceiling versions are not dotted numeric")
    if compare_versions(version, floor) < 0:
        return UNSUPPORTED, REASON_BELOW_FLOOR
    if compare_versions(version, ceiling) > 0:
        return UNSUPPORTED, REASON_ABOVE_CEILING
    return SUPPORTED, REASON_SUPPORTED


def build_contract() -> dict[str, Any]:
    """Derive the declared support contract from the policy constants."""
    axes = {
        "os": list(OS_AXIS),
        "client": list(CLIENT_AXIS),
        "client_version": list(VERSION_AXIS),
    }
    policy: dict[str, Any] = {
        "supported_clients": list(SUPPORTED_CLIENTS),
        "min_client_version": MIN_CLIENT_VERSION,
        "max_client_version": MAX_CLIENT_VERSION,
    }
    declared = []
    for cell in cartesian(axes):
        if cell["os"] not in TESTED_PLATFORMS:
            continue  # not exercised -> stays undeclared, i.e. UNTESTED
        status, reason = classify(cell, policy)
        declared.append(
            {
                **cell,
                "cell_id": cell_id_of(cell),
                "status": status,
                "reason_code": reason,
            }
        )
    return {
        "schema_version": 1,
        "artifact": "support-contract",
        **policy,
        "tested_platforms": list(TESTED_PLATFORMS),
        "axes": axes,
        "declared": declared,
        "untested_rule": UNTESTED_RULE,
    }


def validate_contract(contract: Any) -> dict[str, Any]:
    """Structural + semantic validation mirroring `CONTRACT_SCHEMA`; raises ContractError."""
    if not isinstance(contract, dict):
        raise ContractError("contract must be a JSON object")
    missing = [k for k in CONTRACT_SCHEMA["required"] if k not in contract]
    if missing:
        raise ContractError(f"contract missing keys: {missing}")
    extra = sorted(set(contract) - set(CONTRACT_SCHEMA["properties"]))
    if extra:
        raise ContractError(f"contract has unknown keys: {extra}")
    if contract["schema_version"] != 1 or contract["artifact"] != "support-contract":
        raise ContractError("contract schema_version/artifact mismatch")
    clients = contract["supported_clients"]
    if (
        not isinstance(clients, list)
        or not clients
        or len(set(clients)) != len(clients)
    ):
        raise ContractError("supported_clients must be a non-empty unique list")
    floor = parse_version(contract["min_client_version"])
    ceiling = parse_version(contract["max_client_version"])
    if floor is None or ceiling is None:
        raise ContractError("min/max client version must be dotted numeric")
    if compare_versions(floor, ceiling) > 0:
        raise ContractError("min_client_version exceeds max_client_version")
    platforms = contract["tested_platforms"]
    if (
        not isinstance(platforms, list)
        or not platforms
        or any(p not in _OS_ENUM for p in platforms)
    ):
        raise ContractError(f"tested_platforms must be a subset of {_OS_ENUM}")
    axes = contract["axes"]
    if not isinstance(axes, dict) or set(axes) != set(AXIS_ORDER):
        raise ContractError(f"axes must be exactly {list(AXIS_ORDER)}")
    for name, values in axes.items():
        if (
            not isinstance(values, list)
            or not values
            or len(set(values)) != len(values)
        ):
            raise ContractError(f"axis {name!r} must be a non-empty unique list")
    if any(v not in _OS_ENUM for v in axes["os"]):
        raise ContractError("axis os has a value outside the OS enum")
    if any(parse_version(v) is None for v in axes["client_version"]):
        raise ContractError("axis client_version has a non-numeric version")
    expected = {cell_id_of(c) for c in cartesian(axes)}
    seen: set[str] = set()
    for row in contract["declared"]:
        if not isinstance(row, dict):
            raise ContractError("declared rows must be objects")
        for key in (
            "os",
            "client",
            "client_version",
            "cell_id",
            "status",
            "reason_code",
        ):
            if key not in row:
                raise ContractError(f"declared row missing {key!r}: {row!r}")
        key = cell_id_of(row)
        if row["cell_id"] != key:
            raise ContractError(f"declared cell_id {row['cell_id']!r} != {key!r}")
        if key not in expected:
            raise ContractError(f"declared cell {key!r} is outside the axes")
        if key in seen:
            raise ContractError(f"declared cell {key!r} listed twice")
        seen.add(key)
        if row["status"] not in (SUPPORTED, UNSUPPORTED):
            raise ContractError(
                f"declared status {row['status']!r} is not SUPPORTED/UNSUPPORTED"
            )
        if row["reason_code"] not in DECLARED_REASONS:
            raise ContractError(f"declared reason_code {row['reason_code']!r} unknown")
        if (row["status"] == SUPPORTED) != (row["reason_code"] == REASON_SUPPORTED):
            raise ContractError(f"declared row status/reason disagree: {key!r}")
    if not isinstance(contract["untested_rule"], str) or not contract["untested_rule"]:
        raise ContractError("untested_rule must be a non-empty string")
    return contract


def write_contract(path: Path | None = None) -> dict[str, Any]:
    """Serialise `build_contract()` to ``path`` (default `CONTRACT_PATH`), LF, sorted keys."""
    target = Path(path or CONTRACT_PATH)
    doc = validate_contract(build_contract())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return doc


def load_contract(path: Path | None = None) -> dict[str, Any]:
    """Read and validate the on-disk contract; absent file -> the builder's contract."""
    target = Path(path or CONTRACT_PATH)
    if not target.is_file():
        return build_contract()
    try:
        doc = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read support contract {target}: {exc}") from exc
    return validate_contract(doc)


def declared_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``cell_id -> declared row``; a cell declared twice is a contract defect."""
    out: dict[str, dict[str, Any]] = {}
    for row in contract.get("declared") or []:
        key = cell_id_of(row)
        if key in out:
            raise ContractError(f"declared cell {key!r} listed twice")
        out[key] = row
    return out


def completeness_ok(
    cells: list[dict[str, Any]], axes: dict[str, list[str]]
) -> dict[str, Any]:
    """Does ``cells`` cover the cartesian product exactly once, nothing more?"""
    expected = {cell_id_of(c) for c in cartesian(axes)}
    got_list = [cell_id_of(c) for c in cells]
    got = set(got_list)
    duplicates = sorted({k for k in got_list if got_list.count(k) > 1})
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    return {
        "ok": not missing and not extra and not duplicates,
        "expected": len(expected),
        "present": len(expected & got),
        "missing": missing,
        "extra": extra,
        "duplicates": duplicates,
    }


# --- the gate ---------------------------------------------------------------------
@dataclass
class NegotiateResult:
    """Gate decision for one cell: ``proceed`` or ``refuse`` with a reason code."""

    action: str
    reason_code: str | None = None
    status: str | None = None
    message: str | None = None
    cell_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _policy_text(contract: dict[str, Any]) -> str:
    return (
        f"supported_clients={list(contract['supported_clients'])!r}, "
        f"min_client_version={contract['min_client_version']}, "
        f"max_client_version={contract['max_client_version']}"
    )


def negotiate(
    cell: dict[str, Any], contract: dict[str, Any] | None = None
) -> NegotiateResult:
    """Decide whether an install may proceed for ``cell``; fails closed on every doubt."""
    if contract is None:
        contract = load_contract()
    if not all(isinstance(cell.get(k), str) and cell.get(k) for k in AXIS_ORDER):
        return NegotiateResult(
            action="refuse",
            reason_code=REASON_INCOMPLETE,
            message="compatibility gate refused install: cell is missing os/client/client_version",
        )
    version = cell["client_version"]
    if parse_version(version) is None:
        return NegotiateResult(
            action="refuse",
            reason_code=REASON_UNPARSABLE,
            message=(
                f"compatibility gate refused install: client_version {version!r} "
                "is not a dotted numeric version"
            ),
        )
    key = cell_id_of(cell)
    label = f"{cell['os']}/{cell['client']}/{version}"
    row = declared_map(contract).get(key)
    if row is None:
        return NegotiateResult(
            action="refuse",
            reason_code=REASON_UNTESTED,
            status=UNTESTED,
            message=(
                f"compatibility gate refused install: {label} is not declared in the "
                "support contract (UNTESTED is never inferred SUPPORTED)"
            ),
            cell_id=key,
        )
    status = row.get("status")
    reason = row.get("reason_code")
    if status not in (SUPPORTED, UNSUPPORTED) or reason not in DECLARED_REASONS:
        status, reason = classify(cell, contract)
    if status == UNSUPPORTED:
        return NegotiateResult(
            action="refuse",
            reason_code=reason,
            status=UNSUPPORTED,
            message=(
                f"compatibility gate refused install: {label} is declared UNSUPPORTED "
                f"({_policy_text(contract)})"
            ),
            cell_id=key,
        )
    return NegotiateResult(
        action="proceed",
        reason_code=REASON_SUPPORTED,
        status=SUPPORTED,
        message="compatibility gate allowed install for a SUPPORTED cell",
        cell_id=key,
    )


def attempt_install(
    source: Path,
    dest: Path,
    cell: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate then install ``source`` into ``dest``; a refusal touches nothing on disk."""
    src = Path(source)
    if not src.is_dir():
        raise FileNotFoundError(f"published fixture directory not found: {src}")
    decision = negotiate(cell or {}, contract)
    if decision.action != "proceed":
        return {
            "installed": False,
            "outcome": REFUSED,
            "plugin_present": False,
            "files_written": 0,
            "action": decision.action,
            "reason_code": decision.reason_code,
            "message": decision.message,
        }
    dst = Path(dest)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    files = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file())
    return {
        "installed": True,
        "outcome": PROCEEDED,
        "plugin_present": (dst / "plugin.json").is_file(),
        "files_written": len(files),
        "action": decision.action,
        "reason_code": decision.reason_code,
        "message": decision.message,
    }


def _matches(declared: str, inst: dict[str, Any]) -> bool:
    if declared == SUPPORTED:
        return bool(
            inst["outcome"] == PROCEEDED
            and inst["installed"]
            and inst["plugin_present"]
            and inst["files_written"] > 0
        )
    return bool(
        inst["outcome"] == REFUSED
        and not inst["installed"]
        and not inst["plugin_present"]
        and inst["files_written"] == 0
    )


def run_matrix(
    published: Path, cells_dir: Path, contract: dict[str, Any]
) -> dict[str, Any]:
    """Attempt every declared cell; report undeclared cells as UNTESTED, never drop them."""
    contract = validate_contract(contract)
    axes = contract["axes"]
    lookup = declared_map(contract)
    cells_dir = Path(cells_dir)
    cells_dir.mkdir(parents=True, exist_ok=True)
    product = cartesian(axes)
    counts = {
        "cartesian": len(product),
        "supported_declared": 0,
        "supported_proceeded": 0,
        "unsupported_declared": 0,
        "unsupported_refused": 0,
        "untested": 0,
        "mismatched": 0,
        "blank": 0,
    }
    cells: list[dict[str, Any]] = []
    for axis_cell in product:
        key = cell_id_of(axis_cell)
        row = lookup.get(key)
        if row is None:
            cells.append(
                {
                    **axis_cell,
                    "cell_id": key,
                    "declared": UNTESTED,
                    "reason_code": REASON_UNTESTED,
                    "outcome": UNTESTED,
                    "installed": False,
                    "plugin_present": False,
                    "files_written": 0,
                    "attempted": False,
                    "match": True,
                }
            )
            counts["untested"] += 1
            continue
        declared = str(row["status"])
        inst = attempt_install(
            published, cells_dir / key.replace("|", "_"), axis_cell, contract
        )
        match = _matches(declared, inst)
        cells.append(
            {
                **axis_cell,
                "cell_id": key,
                "declared": declared,
                "action": inst["action"],
                "reason_code": inst["reason_code"],
                "message": inst["message"],
                "outcome": inst["outcome"],
                "installed": inst["installed"],
                "plugin_present": inst["plugin_present"],
                "files_written": inst["files_written"],
                "attempted": True,
                "match": match,
            }
        )
        if declared == SUPPORTED:
            counts["supported_declared"] += 1
            counts["supported_proceeded"] += int(match)
        else:
            counts["unsupported_declared"] += 1
            counts["unsupported_refused"] += int(match)
        counts["mismatched"] += int(not match)
    counts["blank"] = sum(
        1 for c in cells if not c.get("declared") or not c.get("outcome")
    )
    return {"axes": axes, "cells": cells, "counts": counts}


# --- CLI ---------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write-contract", help="serialise the built contract")
    w.add_argument("--path", type=Path, default=None)
    n = sub.add_parser("negotiate", help="gate decision for one cell")
    n.add_argument("os")
    n.add_argument("client")
    n.add_argument("client_version")
    m = sub.add_parser(
        "matrix", help="run the both-states matrix against a fixture dir"
    )
    m.add_argument("published", type=Path)
    m.add_argument("cells_dir", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "write-contract":
        doc = write_contract(args.path)
        print(f"wrote {args.path or CONTRACT_PATH} declared={len(doc['declared'])}")
        return 0
    if args.cmd == "negotiate":
        result = negotiate(
            {
                "os": args.os,
                "client": args.client,
                "client_version": args.client_version,
            }
        )
        print(json.dumps(result.to_dict(), sort_keys=True))
        return 0 if result.action == "proceed" else 2
    matrix = run_matrix(args.published, args.cells_dir, load_contract())
    print(json.dumps(matrix["counts"], sort_keys=True))
    return 0 if matrix["counts"]["mismatched"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
