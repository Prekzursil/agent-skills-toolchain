#!/usr/bin/env python3
"""Probe 2: static AST of the installer — digest re-check vs boolean trust.

Mechanically different from probe 1: no install is executed. Reads
tools/plugin/install.py (and the validator / placement callees) with the
ast module and records whether payload_digest is invoked after
place_payload_files, and whether staged census compares hashes or only
destination paths.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0030"
INSTALL = REPO / "tools" / "plugin" / "install.py"
HANDOFF = REPO / "tools" / "marketplace" / "handoff.py"
PLACEMENT = REPO / "tools" / "plugin" / "placement.py"
PAYLOAD = REPO / "tools" / "plugin" / "payload.py"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def function_named(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def calls_in(fn: ast.AST) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            out.append((node.lineno, node.col_offset, call_name(node)))
    out.sort()
    return out


def names_in(fn: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def census_compares_paths_only(fn: ast.FunctionDef) -> dict:
    """True when staged census is compared via sorted(dict) (keys), not values."""
    hits: list[dict] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if not (isinstance(left, ast.Call) and call_name(left) == "sorted"):
            continue
        args = list(left.args)
        if not args:
            continue
        arg0 = args[0]
        arg_name = arg0.id if isinstance(arg0, ast.Name) else ""
        comparators = []
        for cmp_ in node.comparators:
            if isinstance(cmp_, ast.Name):
                comparators.append(cmp_.id)
        hits.append(
            {
                "lineno": node.lineno,
                "sorted_arg": arg_name,
                "comparators": comparators,
                "ops": [type(op).__name__ for op in node.ops],
            }
        )
    path_only = any(
        h["sorted_arg"] in {"staged_census", "census", "live"}
        or "census" in h["sorted_arg"]
        for h in hits
    )
    # Production uses: if sorted(staged_census) != expected_dests
    production_shape = any(
        h["sorted_arg"] == "staged_census" and "expected_dests" in h["comparators"]
        for h in hits
    )
    return {
        "sorted_dict_compares": hits,
        "census_path_only_compare": path_only or production_shape,
        "production_sorted_staged_census_vs_expected_dests": production_shape,
    }


def analyze() -> dict:
    install_src = INSTALL.read_text(encoding="utf-8")
    install_tree = parse(INSTALL)
    handoff_tree = parse(HANDOFF)
    place_tree = parse(PLACEMENT)
    payload_tree = parse(PAYLOAD)

    install_fn = function_named(install_tree, "install_from_handoff")
    validate_fn = function_named(handoff_tree, "validate_handoff")
    place_fn = function_named(place_tree, "place_payload_files")
    digest_fn = function_named(payload_tree, "payload_digest")

    missing = []
    if install_fn is None:
        missing.append("install_from_handoff")
    if validate_fn is None:
        missing.append("validate_handoff")
    if place_fn is None:
        missing.append("place_payload_files")
    if digest_fn is None:
        missing.append("payload_digest")

    install_calls = calls_in(install_fn) if install_fn is not None else []
    validate_calls = calls_in(validate_fn) if validate_fn is not None else []
    place_calls = calls_in(place_fn) if place_fn is not None else []

    digest_at = [(ln, col) for ln, col, n in install_calls if n == "payload_digest"]
    place_at = [(ln, col) for ln, col, n in install_calls if n == "place_payload_files"]
    validate_at = [(ln, col) for ln, col, n in install_calls if n == "validate_handoff"]
    census_at = [(ln, col) for ln, col, n in install_calls if n == "census_tree"]

    digest_after_place = bool(digest_at and place_at) and any(
        d[0] > p[0] for d in digest_at for p in place_at
    )
    digest_before_place = bool(digest_at and place_at) and any(
        d[0] < p[0] for d in digest_at for p in place_at
    )
    validate_before_digest = bool(validate_at and digest_at) and any(
        v[0] < d[0] for v in validate_at for d in digest_at
    )

    validate_calls_digest = any(n == "payload_digest" for _, _, n in validate_calls)
    place_hashes = any(
        n in {"payload_digest", "sha256", "hexdigest"} for _, _, n in place_calls
    )

    census_info = (
        census_compares_paths_only(install_fn)
        if install_fn is not None
        else {
            "sorted_dict_compares": [],
            "census_path_only_compare": False,
            "production_sorted_staged_census_vs_expected_dests": False,
        }
    )

    trusts_boolean_only = (
        bool(validate_at)
        and not digest_at
        and bool(place_at)
    )
    rechecks_handoff_digest = bool(digest_at) and digest_before_place
    rechecks_at_point_of_use = digest_after_place

    return {
        "probe": "probe2-static-recheck",
        "unit_id": UNIT,
        "method": "ast-call-order-and-compare-shape",
        "used_grep": False,
        "used_ast": True,
        "paths": {
            "install": "tools/plugin/install.py",
            "handoff": "tools/marketplace/handoff.py",
            "placement": "tools/plugin/placement.py",
            "payload": "tools/plugin/payload.py",
        },
        "missing_symbols": missing,
        "install_call_order": [
            {"lineno": ln, "name": n} for ln, _, n in install_calls if n
        ],
        "validate_handoff_present": validate_at,
        "payload_digest_present": digest_at,
        "place_payload_files_present": place_at,
        "census_tree_present": census_at,
        "validate_before_digest": validate_before_digest,
        "digest_before_place": digest_before_place,
        "digest_after_place": digest_after_place,
        "digest_call_count_in_install_from_handoff": len(digest_at),
        "validator_calls_payload_digest": validate_calls_digest,
        "placement_hashes_bytes": place_hashes,
        "trusts_validator_boolean_only": trusts_boolean_only,
        "rechecks_handoff_digest_before_place": rechecks_handoff_digest,
        "rechecks_digest_at_point_of_use": rechecks_at_point_of_use,
        "census": census_info,
        "install_mentions_payload_digest": "payload_digest" in install_src,
        "install_mentions_place_payload_files": "place_payload_files" in install_src,
    }


def main() -> int:
    info = analyze()
    missing = info["missing_symbols"]
    checks = [
        ("install_file_exists", INSTALL.is_file()),
        ("handoff_file_exists", HANDOFF.is_file()),
        ("placement_file_exists", PLACEMENT.is_file()),
        ("payload_file_exists", PAYLOAD.is_file()),
        ("required_symbols_present", missing == []),
        ("used_ast", info["used_ast"] is True),
        ("did_not_use_grep", info["used_grep"] is False),
        ("validate_called", bool(info["validate_handoff_present"])),
        ("payload_digest_called", bool(info["payload_digest_present"])),
        ("place_called", bool(info["place_payload_files_present"])),
        ("validate_before_digest", info["validate_before_digest"] is True),
        ("digest_before_place", info["digest_before_place"] is True),
        (
            "validator_does_not_hash_payload",
            info["validator_calls_payload_digest"] is False,
        ),
        ("placement_does_not_hash", info["placement_hashes_bytes"] is False),
        (
            "does_not_recheck_digest_after_place",
            info["digest_after_place"] is False,
        ),
        (
            "census_compares_sorted_keys_not_payload_digest",
            info["census"]["production_sorted_staged_census_vs_expected_dests"]
            is True,
        ),
        (
            "does_not_trust_boolean_only",
            info["trusts_validator_boolean_only"] is False,
        ),
    ]
    payload = {
        **info,
        "checks": {name: bool(ok) for name, ok in checks},
        "pass": all(ok for _, ok in checks),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            return fail(name)
    print(
        "SUCCESS:ADV-0030-probe2 static recheck: digest once before place; "
        "no digest after place; census is path-only; validator does not hash"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
