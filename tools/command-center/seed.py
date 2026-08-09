"""Seed WORK-UNIT-CATALOG.json from REGISTER.md + the authored overlay.

Deterministic and re-runnable: same inputs -> same bytes (there is no clock in
the output). That property is what `tests/test_seed.py` uses to prove the
committed catalog was not hand-edited into disagreement with its own source.

Division of labour, and the reason for it:
  * DERIVED (here, mechanically): id, title, program, section, status, effort,
    evidence, sources, phase, target, inputs, output_path, completion_sentinel.
  * AUTHORED (command-center/sources/overlay.json): dependency edges, owner
    gates, security class, next smallest action -- the four things the register
    states in prose and no parser can recover.
  * DECLARED ONCE (catalog `defaults`): the operational work-unit fields
    (assignment, tool_permissions, substrate, timeout, retry, reviewer,
    failure classification, output schema, evidence requirement). These are
    policy, not per-item facts. Declaring them once, visibly, is honest;
    stamping 103 invented per-item values would not be, and an empty template
    would be the same failure in a new location.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog as cat
import register_parse as rp

DEFAULTS: dict[str, Any] = {
    "assignment": {
        "model": "opus",
        "vendor": "anthropic",
        "role": "implementer",
        "basis": "rules/common/performance.md - substantive subagents default to Opus",
    },
    "tool_permissions": ["Read", "Grep", "Glob", "Bash", "PowerShell", "Write", "Edit"],
    "execution_substrate": "local-windows-pwsh7",
    "timeout_seconds": 1800,
    "output_schema": "command-center/schema/receipt.schema.json",
    "evidence_requirement": (
        "two mechanically independent signals, each anchored to a file:line or a "
        "reproducible command (rules/common/single-signal-verification.md)"
    ),
    "reviewer_requirement": "one independent adversarial reviewer in a fresh context",
    "retry_policy": "two strikes then pivot; enumerate >=2 alternatives before a third attempt (AGENTS.md 4b)",
    "failure_classification": [
        "green-not-live",
        "overclaim",
        "detector-failure",
        "uncontrolled-silence",
        "dependency-blocked",
        "owner-blocked",
    ],
    "tests_required": ["a both-states control: the check must fire on the bad state and be silent on the good one"],
    "owner_approval_required": False,
}

_PHASE_BY_PROGRAM = {
    "A-toolchain": "prompt-two",
    "HARNESS": "unified-contract",
    "MONITOR": "monitor-cockpit",
    "B-workflow_design": "program-b",
}

_STATUS_TOKENS = (
    "DONE-VERIFIED",
    "DONE-CLAIMED",
    "IN-FLIGHT",
    "DROPPED-BY-OWNER",
    "SUPERSEDED",
    "UNKNOWN",
    "OPEN",
)


def _status_of(row: rp.RegisterRow) -> str:
    """Read the status column when the table has one, else infer from the section.

    Only the OUTSTANDING tables carry a status column; the three closed sections
    encode status entirely by section, which is why this cannot be a plain
    column read."""
    if row.section == rp.SECTION_OUTSTANDING and len(row.cells) > 2:
        cell = rp._strip_markup(row.cells[2]).upper()
        for token in _STATUS_TOKENS:
            if token in cell:
                return token
    return {
        rp.SECTION_SKIPPED: "DROPPED-BY-OWNER",
        rp.SECTION_SUPERSEDED: "SUPERSEDED",
        rp.SECTION_SETTLED: "DONE-VERIFIED",
    }.get(row.section, "OPEN")


def _column(row: rp.RegisterRow, index: int) -> str:
    return rp._strip_markup(row.cells[index]) if len(row.cells) > index else ""


def _evidence_of(row: rp.RegisterRow) -> str:
    if row.section == rp.SECTION_OUTSTANDING:
        return _column(row, 4)
    if row.section == rp.SECTION_SETTLED:
        return _column(row, 2)
    # skipped / superseded tables: column 2 is the decision or the replacement.
    return _column(row, 2)


def _sources_of(row: rp.RegisterRow) -> list[str]:
    if row.section != rp.SECTION_OUTSTANDING:
        return []
    raw = _column(row, 5)
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_catalog(register_path: Path, overlay_path: Path) -> dict[str, Any]:
    parsed = rp.parse_file(register_path)
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    per_item: dict[str, Any] = overlay.get("items", {})
    register_bytes = register_path.read_bytes()

    items: list[dict[str, Any]] = []
    for row in parsed.rows:
        extra: dict[str, Any] = per_item.get(row.row_id, {})
        section_disposition = cat.SECTION_DISPOSITION.get(row.section)
        item: dict[str, Any] = {
            "id": row.row_id,
            "title": row.title,
            "phase": _PHASE_BY_PROGRAM.get(row.program, "cross-program"),
            "target": rp.short_title(row.title, 160),
            "inputs": ["command-center/sources/REGISTER.md#" + row.row_id],
            "dependencies": list(extra.get("dependencies", [])),
            "output_path": f"command-center/receipts/{row.row_id}.json",
            "completion_sentinel": f"SUCCESS:{row.row_id}",
            "program": row.program or "cross-program",
            "section": row.section,
            "status": _status_of(row),
            "disposition": section_disposition,
            "disposition_evidence": _evidence_of(row) if section_disposition else "",
            "effort": _column(row, 3) if row.section == rp.SECTION_OUTSTANDING else "",
            "evidence": _evidence_of(row),
            "sources": _sources_of(row),
            "owner_gate": list(extra.get("owner_gate", [])),
            "security_class": extra.get("security_class", "none"),
            "next_smallest_action": extra.get("next_smallest_action", cat.UNKNOWN),
            "defer": None,
            "history": [],
        }
        items.append(item)

    owner_questions = [
        {"id": qid, "text": text, "state": "OPEN"} for qid, text in parsed.owner_questions
    ]
    return {
        "schema_version": cat.SCHEMA_VERSION,
        "contract": {
            "work_unit_fields": list(cat.WORK_UNIT_FIELDS),
            "work_unit_fields_source": "_USER-PROMPTS.md:10607-10625 (Prompt Two, 19 mandatory fields)",
            "backlog_fields_source": "L14-unified-contract.md:129-134 (33 mandatory backlog fields)",
            "reachability_rule": "every item must be reachable from a final disposition (contract L2001)",
        },
        "provenance": {
            "register": "command-center/sources/REGISTER.md",
            "register_sha256": hashlib.sha256(register_bytes).hexdigest(),
            "register_bytes": len(register_bytes),
            "overlay": "command-center/sources/overlay.json",
            "seeded_by": "tools/command-center/seed.py",
        },
        "terminal_dispositions": list(cat.TERMINAL_DISPOSITIONS),
        "defaults": DEFAULTS,
        "owner_questions": owner_questions,
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", default=str(cat.command_center_dir() / "sources" / "REGISTER.md"))
    parser.add_argument("--overlay", default=str(cat.command_center_dir() / "sources" / "overlay.json"))
    parser.add_argument("--out", default=str(cat.catalog_path()))
    parser.add_argument("--graph", default=str(cat.graph_path()))
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing catalog (seeding is destructive: it discards close/defer history)",
    )
    args = parser.parse_args(argv)

    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"FAILED:seed {out} exists; re-seeding discards history. Pass --force if that is intended.")
        return 1
    built = build_catalog(Path(args.register), Path(args.overlay))
    cat.save(built, out)
    cat.save(cat.build_graph(built), Path(args.graph))
    print(f"SUCCESS:seed items={len(built['items'])} open={len(cat.open_items(built))} -> {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
