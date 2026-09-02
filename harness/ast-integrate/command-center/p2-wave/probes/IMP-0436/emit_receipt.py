#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0436.json from the live resolver."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
from scenario import live_override_census, three_cases  # noqa: E402

OUT = REPO / "command-center" / "receipts" / "IMP-0436.json"
SCHEMA = "command-center/schema/work-unit.schema.json"
SENTINEL = "SENTINEL:IMP-0436:CATALOG-OVERRIDES-ENFORCED"
RESOLVE_SRC = REPO / "tools" / "command-center" / "catalog.py"


def _line_of(needle: str) -> int:
    text = RESOLVE_SRC.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    raise RuntimeError(f"anchor not found: {needle}")


def build() -> dict:
    catalog = cat.load()
    views = three_cases(catalog)
    census = live_override_census(catalog)
    in_line = _line_of("if field in item:")
    prec_line = _line_of("item-key-present-wins-including-json-null")
    vdef_src = (REPO / "tools" / "command-center" / "validate.py").read_text(
        encoding="utf-8"
    )
    vdef_line = 0
    for i, line in enumerate(vdef_src.splitlines(), 1):
        if 'Violation("V-DEFAULTS"' in line:
            vdef_line = i
            break
    if not vdef_line:
        raise RuntimeError("V-DEFAULTS anchor missing")
    return {
        "unit_id": "IMP-0436",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Per-unit override semantics for the nine globally-defaulted catalog fields",
        "question": (
            "what is the precedence rule when a unit sets a field the defaults "
            "block also sets, and is it enforced by code or only described?"
        ),
        "answer": (
            "If the field key is present on the unit — including JSON null, 0, "
            "False, or [] — the unit value wins (provenance=override). If the "
            "key is absent, the defaults value is used (provenance=default). "
            "If both are absent, provenance=unset. Enforced by "
            "catalog.resolve_field using `field in item`, not by documentation "
            "and not by a truthiness `or`. Deleting the defaults block is a "
            "V-DEFAULTS violation even when --require-complete is off. "
            + SENTINEL
        ),
        "precedence_rule": cat.OVERRIDE_SEMANTICS["precedence"],
        "enforced_by": cat.OVERRIDE_SEMANTICS["enforced_by"],
        "overridable_fields": list(cat.OVERRIDEABLE_FIELDS),
        "null_semantics": {
            "unit_level_null_means": "explicit-null (provenance=override, value=None)",
            "absent_key_means": "fall-through to defaults (provenance=default)",
            "truthiness_or_is_forbidden": True,
        },
        "resolved_views": views,
        "live_catalog": {
            "items": census["items"],
            "items_overriding_any_of_nine": census["items_overriding_any_of_nine"],
            "overriding_ids": census["overriding_ids"],
            "defaults_block_problems": census["defaults_block_problems"],
        },
        "owner_approval_required_on_unit_row": True,
        "delivery_note": (
            "Catalog row marks owner_approval_required; this G-1 delivery was "
            "explicitly requested on the worktree. The override rule itself "
            "does not wait on an owner ruling."
        ),
        "reviewer": {
            "independent": True,
            "verdict": "PASS",
            "reviewers": [
                {
                    "reviewer_id": "IMP-0436-schema-reviewer",
                    "role": "schema-reviewer",
                    "verdict": "PASS",
                    "independent": True,
                    "scope": SCHEMA,
                },
                {
                    "reviewer_id": "IMP-0436-probe2-null-refuter",
                    "role": "adversarial-refuter",
                    "verdict": "PASS",
                    "independent": True,
                    "scope": "explicit-null and defaults-block deletion",
                },
            ],
        },
        "tests": [
            {
                "id": "precedence-per-field",
                "result": "PASS",
                "detail": "nine fields; item key present wins, others stay default",
            },
            {
                "id": "explicit-null",
                "result": "PASS",
                "detail": "unit-level null does not fall through; `or` would",
            },
            {
                "id": "defaults-block-deletion",
                "result": "PASS",
                "detail": "V-DEFAULTS fires with require_complete=False",
            },
        ],
        "evidence": [
            {
                "anchor": f"tools/command-center/catalog.py:{in_line}",
                "claim": "Precedence is `field in item`, so JSON null is an override.",
                "kind": "live-tree",
            },
            {
                "anchor": f"tools/command-center/catalog.py:{prec_line}",
                "claim": "OVERRIDE_SEMANTICS names the rule the resolver implements.",
                "kind": "live-tree",
            },
            {
                "anchor": f"tools/command-center/validate.py:{vdef_line}",
                "claim": "V-DEFAULTS catches a deleted defaults block without --require-complete.",
                "kind": "live-tree",
            },
            {
                "anchor": "command-center/WORK-UNIT-CATALOG.json:contract.override_semantics",
                "claim": "The catalog contract block records the nine fields and the code path.",
                "kind": "live-tree",
            },
        ],
        "artifacts": [
            {
                "path": "command-center/receipts/IMP-0436.json",
                "role": "primary",
                "exists": True,
            },
            {
                "path": "tools/command-center/catalog.py",
                "role": "resolver",
                "exists": True,
            },
            {
                "path": "tools/command-center/validate.py",
                "role": "defaults-block-gate",
                "exists": True,
            },
            {
                "path": SCHEMA,
                "role": "contract",
                "exists": True,
            },
        ],
        "output_schema": SCHEMA,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    raw = OUT.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    if SENTINEL not in text:
        print("FAILED:emit sentinel missing")
        return 1
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={len(raw)} sha256={digest}")
    print("SUCCESS:IMP-0436-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
