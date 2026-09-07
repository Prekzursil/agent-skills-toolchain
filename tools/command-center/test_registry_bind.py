#!/usr/bin/env python3
"""CC-0014: bind tests to claims to units; refuse coverage until a mutation proves fire.

Status machine:
  UNPROVEN   — registered, no mutation_record that made the test FAIL
  PROTECTING — mutation_record with outcome=FAILED (test went red on the mutant)
  HOLE       — mutation_record with outcome=SURVIVED (mutant lived; not coverage)

UNPROVEN and HOLE never count toward protected-claim coverage totals.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO / "command-center" / "TEST-REGISTRY.json"
DEFAULT_CLAIMS = REPO / "command-center" / "CLAIM-REGISTRY.json"

STATUS_UNPROVEN = "UNPROVEN"
STATUS_PROTECTING = "PROTECTING"
STATUS_HOLE = "HOLE"
VALID_STATUSES = frozenset({STATUS_UNPROVEN, STATUS_PROTECTING, STATUS_HOLE})
MUTATION_FAILED = "FAILED"
MUTATION_SURVIVED = "SURVIVED"


class RegistryError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_entry(entry: dict[str, Any]) -> str:
    """Derive status from mutation_record. Explicit status must agree or is overwritten."""
    mut = entry.get("mutation_record")
    if not mut:
        return STATUS_UNPROVEN
    outcome = str(mut.get("outcome", "")).upper()
    if outcome == MUTATION_FAILED:
        # Require pointers so PROTECTING cannot be asserted from a bare flag.
        if not mut.get("diff_ref") or not mut.get("failing_output_ref"):
            raise RegistryError(
                f"entry {entry.get('id')}: PROTECTING requires mutation_record.diff_ref "
                "and failing_output_ref citing the fail evidence"
            )
        return STATUS_PROTECTING
    if outcome == MUTATION_SURVIVED:
        return STATUS_HOLE
    raise RegistryError(
        f"entry {entry.get('id')}: mutation_record.outcome must be "
        f"{MUTATION_FAILED} or {MUTATION_SURVIVED}, got {outcome!r}"
    )


def normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(entry)
    if "id" not in out:
        raise RegistryError("entry missing id")
    if "test_id" not in out:
        raise RegistryError(f"entry {out['id']}: missing test_id")
    if "claim_ids" not in out or not isinstance(out["claim_ids"], list):
        raise RegistryError(f"entry {out['id']}: claim_ids must be a list")
    if "unit_ids" not in out or not isinstance(out["unit_ids"], list):
        raise RegistryError(f"entry {out['id']}: unit_ids must be a list")
    status = classify_entry(out)
    out["status"] = status
    return out


def register_entry(registry: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Insert/replace a binding entry; returns the normalized entry."""
    normalized = normalize_entry(entry)
    bindings = list(registry.get("bindings") or [])
    bindings = [b for b in bindings if b.get("id") != normalized["id"]]
    bindings.append(normalized)
    registry["bindings"] = sorted(bindings, key=lambda b: str(b["id"]))
    return normalized


def coverage_summary(registry: dict[str, Any]) -> dict[str, Any]:
    """Aggregate coverage. All-UNPROVEN => 0 protected claims (never 100%)."""
    bindings = [normalize_entry(b) for b in (registry.get("bindings") or [])]
    by_status = {STATUS_UNPROVEN: 0, STATUS_PROTECTING: 0, STATUS_HOLE: 0}
    protected_claims: set[str] = set()
    holes: list[dict[str, Any]] = []
    for b in bindings:
        st = b["status"]
        by_status[st] = by_status.get(st, 0) + 1
        if st == STATUS_PROTECTING:
            protected_claims.update(str(c) for c in b.get("claim_ids") or [])
        elif st == STATUS_HOLE:
            holes.append(
                {
                    "entry_id": b["id"],
                    "test_id": b["test_id"],
                    "claim_ids": list(b.get("claim_ids") or []),
                    "mutation_record": b.get("mutation_record"),
                }
            )
    total = len(bindings)
    protecting = by_status[STATUS_PROTECTING]
    return {
        "binding_count": total,
        "by_status": by_status,
        "protected_claim_count": len(protected_claims),
        "protected_claims": sorted(protected_claims),
        "holes": holes,
        "hole_count": len(holes),
        "coverage_ratio": (protecting / total) if total else 0.0,
        # Explicit anti-false-green: UNPROVEN never inflate coverage.
        "unproven_count_toward_coverage": 0,
        "protecting_only_counts": True,
    }


def ensure_bindings_scaffold(registry: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a narrative TEST-REGISTRY with an empty bindings array if missing."""
    out = deepcopy(registry)
    if "bindings" not in out:
        out["bindings"] = []
    out.setdefault(
        "binding_contract",
        {
            "statuses": sorted(VALID_STATUSES),
            "rule": (
                "PROTECTING only when mutation_record.outcome=FAILED with diff_ref and "
                "failing_output_ref; UNPROVEN without mutation; HOLE when SURVIVED."
            ),
            "coverage_rule": "Only PROTECTING entries count toward protected_claim_count.",
        },
    )
    return out


def load_registry(path: Path | None = None) -> dict[str, Any]:
    return ensure_bindings_scaffold(load_json(path or DEFAULT_REGISTRY))


def save_registry(registry: dict[str, Any], path: Path | None = None) -> Path:
    target = path or DEFAULT_REGISTRY
    text = json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print coverage summary for the registry bindings.",
    )
    parser.add_argument(
        "--register-json",
        type=Path,
        help="Path to a binding entry JSON to register (mutates --registry).",
    )
    args = parser.parse_args(argv)

    try:
        reg = load_registry(args.registry)
        if args.register_json:
            entry = load_json(args.register_json)
            normalized = register_entry(reg, entry)
            save_registry(reg, args.registry)
            print(json.dumps({"registered": normalized}, indent=2, sort_keys=True))
        if args.summary or not args.register_json:
            summary = coverage_summary(reg)
            print(json.dumps(summary, indent=2, sort_keys=True))
    except RegistryError as exc:
        print(f"FAILED:test-registry-bind {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
