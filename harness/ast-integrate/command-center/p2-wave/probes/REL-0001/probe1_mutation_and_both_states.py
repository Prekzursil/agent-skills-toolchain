#!/usr/bin/env python3
"""Probe 1: required-key deletion under PATCH fails; genuine PATCH is silent."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bump_linter as L  # noqa: E402
import corpus as C  # noqa: E402


def run_case(name: str) -> tuple[int, dict]:
    tmp = Path(tempfile.mkdtemp(prefix="rel0001-p1-"))
    old = C.write_tree(tmp / "old", C.baseline())
    new = C.materialize(name, tmp / "new")
    return L.invoke_cli(old, new)


def rule_ids(doc: dict) -> set[str]:
    return {str(r.get("rule_id")) for r in (doc.get("findings") or []) if isinstance(r, dict)}


def main() -> int:
    rc_bad, bad = run_case("major-key-removed")
    rc_good, good = run_case("patch-only")
    rc_under, under = run_case("patch-only-no-bump")

    errors: list[str] = []
    if rc_bad == 0:
        errors.append(f"key-removed declared PATCH must be non-zero, got {rc_bad}")
    if bad.get("derived_bump") != "MAJOR":
        errors.append(f"key-removed derived={bad.get('derived_bump')} want MAJOR")
    if "required_manifest_key_removed" not in rule_ids(bad):
        errors.append(f"key-removed missing rule id, have {sorted(rule_ids(bad))}")
    if rc_good != 0:
        errors.append(f"patch-only declared PATCH must be silent, got {rc_good}")
    if good.get("derived_bump") != "PATCH":
        errors.append(f"patch-only derived={good.get('derived_bump')} want PATCH")
    if RANK_MAJOR := (good.get("derived_bump") == "MAJOR"):
        errors.append("patch-only must not classify MAJOR (false positive)")
        del RANK_MAJOR
    if rc_under == 0:
        errors.append(
            "patch-only with undeclared bump must be non-zero "
            "(otherwise PATCH classification is inert)"
        )
    if under.get("derived_bump") != "PATCH":
        errors.append(f"under-bump derived={under.get('derived_bump')} want PATCH")

    out = {
        "probe": "probe1-mutation-and-both-states",
        "unit_id": "REL-0001",
        "mutation": {
            "case": "major-key-removed",
            "linter_exit_code": rc_bad,
            "derived_bump": bad.get("derived_bump"),
            "declared_bump": bad.get("declared_bump"),
            "rule_ids": sorted(rule_ids(bad)),
            "want_nonzero": True,
        },
        "both_states": {
            "good": {
                "case": "patch-only",
                "linter_exit_code": rc_good,
                "derived_bump": good.get("derived_bump"),
                "declared_bump": good.get("declared_bump"),
                "want_zero": True,
            },
            "underdeclared": {
                "case": "patch-only-no-bump",
                "linter_exit_code": rc_under,
                "derived_bump": under.get("derived_bump"),
                "declared_bump": under.get("declared_bump"),
                "want_nonzero": True,
            },
        },
        "pass": not errors,
        "errors": errors,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"key_removed_rc={rc_bad} derived={bad.get('derived_bump')} "
        f"patch_rc={rc_good} derived={good.get('derived_bump')} "
        f"under_rc={rc_under}"
    )
    if errors:
        print("FAILED:REL-0001-probe1 " + "; ".join(errors))
        return 1
    print(
        "SUCCESS:REL-0001-probe1 required-key PATCH mutant exits non-zero; "
        "genuine PATCH is silent; undeclared PATCH is not"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
