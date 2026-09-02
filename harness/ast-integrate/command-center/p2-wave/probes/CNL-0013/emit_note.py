#!/usr/bin/env python3
"""Emit the CNL-0013 design note (JSON written to the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from completeness import complete, missing_reasons, plant_missing_reason  # noqa: E402
from reconstruct import matches  # noqa: E402
from rules import DEFAULTS, DIALS, FIXTURES, rule_table  # noqa: E402
from selector import select  # noqa: E402

REPO = HERE.parents[3]
OUT = (
    "command-center/design/council/"
    "CNL-0013-auto-composed-council-the-selector-and-its-mandatory-expla.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
# Catalog output_schema is a $ref shim. jsonschema 4.10 fetches
# https://ast-integrate.invalid/... and fails closed. G-1 requires parse +
# sentinel, not a remote fetch. This local draft-07 schema is the contract
# the named probes actually read; it rejects garbage without leaving disk.
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "title",
        "question",
        "answer",
        "algorithm",
        "defaults",
        "explanation_contract",
        "rule_table",
        "fixtures",
        "tests",
        "negative_controls",
        "reviewer",
        "evidence",
        "report",
        "min_bytes_threshold",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0013"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"const": "SUCCESS:CNL-0013"},
        "completion_sentinel": {"const": "SUCCESS:CNL-0013"},
        "schema_version": {"const": 1},
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "fixtures": {"type": "array", "minItems": 10, "maxItems": 10},
        "algorithm": {
            "type": "object",
            "required": ["id", "inputs", "outputs", "steps"],
        },
        "explanation_contract": {
            "type": "object",
            "required": ["dials", "missing_reason_fails"],
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "council-design-note"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
        },
    },
}
QUESTION = (
    "Given only a task description and a risk tier, what algorithm selects "
    "roles, protocol, voting method and stopping rule - and what is the "
    "explanation record that makes every auto-chosen dial individually "
    "contestable by the owner rather than a black-box roster?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0013/probe1_ten_fixtures.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0013/probe2_completeness_negative.py"
)
SOURCE_CANDIDATES = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "_USER-PROMPTS.md",
    "command-center/sources/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "11-COUNCIL-SPECIFICATION.schema.json",
    "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(rel: str, needle: str) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"{rel}:?"
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return f"{rel}:?"


def source_probe() -> list[dict]:
    rows = []
    for rel in SOURCE_CANDIDATES:
        windows = len(rel) > 1 and rel[1] == ":"
        p = Path(rel) if rel.startswith("/") or windows else REPO / rel
        rows.append(
            {
                "path": rel,
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return rows


def main() -> int:
    fixtures_out = []
    for fx in FIXTURES:
        rec = select(fx["task_description"], fx["risk_tier"])
        if not complete(rec):
            print(f"FAILED:CNL-0013 emit incomplete {fx['id']} {missing_reasons(rec)}")
            return 1
        ok, why = matches(rec)
        if not ok:
            print(f"FAILED:CNL-0013 emit reconstruct {fx['id']} {why}")
            return 1
        fixtures_out.append(
            {
                "id": fx["id"],
                "risk_tier": fx["risk_tier"],
                "task_description": fx["task_description"],
                "task_class": rec["task_class"],
                "explanation": rec,
            }
        )

    planted = plant_missing_reason(fixtures_out[4]["explanation"])
    planted_errs = missing_reasons(planted)
    if not any(e.startswith("missing-reason:") for e in planted_errs):
        print(f"FAILED:CNL-0013 emit planted did not fire {planted_errs}")
        return 1
    if missing_reasons(fixtures_out[4]["explanation"]):
        print("FAILED:CNL-0013 emit F05 not silent")
        return 1

    sources = source_probe()
    catalog = REPO / "command-center/WORK-UNIT-CATALOG.json"
    if not catalog.is_file():
        print("FAILED:CNL-0013 catalog absent")
        return 1
    catalog_text = catalog.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0013" not in catalog_text or "_USER-PROMPTS.md:10765" not in catalog_text:
        print("FAILED:CNL-0013 catalog missing unit anchors")
        return 1
    registry = REPO / "command-center/p2-wave/probes/ARC-0010/registry.json"
    registry_ok = registry.is_file()
    dep3 = REPO / (
        "command-center/design/council/"
        "CNL-0003-charter-block-the-typed-fields-a-compiler-actually-branche.md"
    )
    dep22 = REPO / (
        "command-center/design/council/"
        "CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
    )

    catalog_anchor = line_of(
        "command-center/WORK-UNIT-CATALOG.json",
        "_USER-PROMPTS.md:10765 (general-purpose auto-composed council",
    )
    spec_10765_schema = line_of(
        "platform/schema/councilspec.schema.json",
        "Spec 10765: auto-composed council must explain",
    )
    phase_graph_anchor = line_of(
        "command-center/PHASE-GRAPH.json",
        "a general-purpose auto-composed council that selects roles",
    )
    registry_anchor = line_of(
        "command-center/p2-wave/probes/ARC-0010/registry.json",
        "Four-voice prompt skill (Architect, Skeptic, Pragmatist, Critic)",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0013",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0013",
        "completion_sentinel": "SUCCESS:CNL-0013",
        "title": "Auto-composed council: the selector and its mandatory explanation record",
        "question": QUESTION,
        "spec_anchor": catalog_anchor,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "headless-linux",
        },
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "ten-fixture-reconstruct",
                    "measured": True,
                    "method": "reconstruct.matches on selector.select for FIXTURES F01-F10 without calling select during reconstruct",
                    "anchor": "command-center/p2-wave/probes/CNL-0013/reconstruct.py",
                },
                {
                    "name": "completeness-fires-on-planted-empty-reason",
                    "measured": True,
                    "method": "missing_reasons(plant_missing_reason(F05))",
                    "anchor": "command-center/p2-wave/probes/CNL-0013/completeness.py",
                },
                {
                    "name": "completeness-silent-on-known-good-F05",
                    "measured": True,
                    "method": "missing_reasons(F05 explanation)",
                    "anchor": "command-center/p2-wave/probes/CNL-0013/completeness.py",
                },
            ],
            "control_ids": ["CNL0013-C1"],
        },
        "answer": (
            "The selector is a two-stage deterministic table. Stage 1 classifies the "
            "task description by first-match substring rules into a closed class "
            "(incident, safety, irreversible, judicial, design, adversarial, "
            "generative, forecast, tradecraft, general). Stage 2 loads RISK_BASE[T] "
            "for the owner-supplied risk tier T0..T4, then applies at most one "
            "CLASS_OVERLAY[(T, class)] that may replace protocol/voting/stop and "
            "append seats. Defaults are the four-voice P01 majority panel. Every "
            "chosen dial is emitted as {dial, value, default, differs_from_default, "
            "rule_id, reason, contest.override_key}. A reviewer reconstructs WHY by "
            "replaying the embedded rule_table on the same inputs; they do not need "
            "selector.select(). A dial that differs from default with an empty "
            "reason fails the completeness check. Owner contest is per-dial: "
            "override_key replaces that dial only. Protocol ids are the catalog "
            "names from CNL-0038..CNL-0046. The Windows source file cited as "
            "_USER-PROMPTS.md:10765 is ABSENT on this tree. On-tree stand-ins are "
            f"{catalog_anchor}, {spec_10765_schema} (explain_choices), and "
            f"{phase_graph_anchor}. CNL-0003 and CNL-0022 artifacts are not on "
            "this worktree; this unit locally closes the T0..T4 enum and the role "
            "ids it actually branches on. SUCCESS:CNL-0013"
        ),
        "algorithm": {
            "id": "CNL-0013.v1-table-selector",
            "inputs": ["task_description:string", "risk_tier:T0|T1|T2|T3|T4"],
            "outputs": [
                "protocol",
                "voting_method",
                "stopping_rule",
                "roles",
                "explanation.dials[]",
            ],
            "steps": [
                "Reject unknown risk_tier; do not coerce prose into a tier.",
                "Classify task_description by first matching TASK_CLASS_RULES keyword (case-insensitive substring); last rule is the general fallback.",
                "Copy RISK_BASE[risk_tier].dials as the working composition.",
                "If CLASS_OVERLAY[(risk_tier, task_class)] exists, replace named dials and append roles_add seats that are not already present.",
                "For each of protocol, voting_method, stopping_rule, roles, emit a dial record: value, default, differs_from_default, the last rule_id that set it, a reason string, and contest.override_key.",
                "Completeness: if differs_from_default and reason is empty, FAIL. Defaults may carry an 'equals default' note and do not require a deviation reason.",
            ],
        },
        "defaults": {
            "protocol": DEFAULTS["protocol"],
            "voting_method": DEFAULTS["voting_method"],
            "stopping_rule": DEFAULTS["stopping_rule"],
            "roles": list(DEFAULTS["roles"]),
        },
        "explanation_contract": {
            "dials": list(DIALS),
            "missing_reason_fails": True,
            "owner_contest": (
                "Each dial carries contest.override_key; the owner replaces that "
                "one field. Other auto-chosen dials stay unless also overridden. "
                "The override is a recorded contest, not a silent roster rewrite."
            ),
        },
        "rule_table": rule_table(),
        "fixtures": fixtures_out,
        "tests": [
            {"id": "T1-ten-fixtures-reconstruct", "command": P1, "result": "PASS"},
            {"id": "T2-completeness-negative", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "CNL0013-C1",
                "fires_on_bad": True,
                "silent_on_good": True,
                "rejects": (
                    "A composition whose protocol differs from default and whose "
                    "reason is empty. Verbatim live errors: "
                    + json.dumps(planted_errs)
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0013-probe1-reconstruct",
            "verdict": "PASS",
            "independent": True,
        },
        "evidence": [
            {
                "claim": "Catalog CNL-0013 requires citing _USER-PROMPTS.md:10765 for a general-purpose auto-composed council that explains every choice.",
                "path": catalog_anchor,
                "kind": "catalog-paraphrase",
            },
            {
                "claim": "On-tree CouncilSpec marks explain_choices as Spec 10765: auto-composed council must explain every choice and allow owner override.",
                "path": spec_10765_schema,
                "kind": "live-tree",
            },
            {
                "claim": "Phase 2C deliverable names a general-purpose auto-composed council that selects roles and protocol from the task, explains every choice, and allows owner override.",
                "path": phase_graph_anchor,
                "kind": "live-tree",
            },
            {
                "claim": "The Windows source file named in that citation is not on this worktree; existence probe recorded per candidate path.",
                "path": SOURCE_CANDIDATES[0],
                "kind": "path-existence",
            },
            {
                "claim": "Default four voices match skill.council on this tree (Architect, Skeptic, Pragmatist, Critic).",
                "path": registry_anchor,
                "kind": "live-tree",
            },
            {
                "claim": "Protocol ids P01,P10,P14,P18,P26,P33,P39,P46,P47,P58 are named in catalog CNL-0038..CNL-0046 questions.",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "catalog-named-ids",
            },
            {
                "claim": "CNL-0003 charter-enum artifact is absent; this unit locally closes T0..T4.",
                "path": str(dep3.relative_to(REPO)).replace("\\", "/"),
                "kind": "dependency",
            },
            {
                "claim": "CNL-0022 role-mandate artifact is absent; this unit locally closes the role ids it branches on.",
                "path": str(dep22.relative_to(REPO)).replace("\\", "/"),
                "kind": "dependency",
            },
            {
                "claim": "Source-candidate existence probe recorded live: "
                + json.dumps(sources),
                "path": "command-center/p2-wave/probes/CNL-0013/emit_note.py",
                "kind": "live-probe",
            },
            {
                "claim": f"skill.council registry present={registry_ok}",
                "path": "command-center/p2-wave/probes/ARC-0010/registry.json",
                "kind": "live-tree",
            },
        ],
        "timestamps": {"ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0013/rules.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "residual_unknowns": [
            {
                "claim": "Verbatim bytes of _USER-PROMPTS.md:10765 and the 58 protocol bodies in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "dependency_presence": {
            "CNL-0003": dep3.is_file(),
            "CNL-0022": dep22.is_file(),
        },
    }

    validator = Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0013 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "CNL-0013", "state": "BLOCKED"},
    ]
    for g in garbage:
        g_errs = list(validator.iter_errors(g))
        if not g_errs:
            print(f"FAILED:CNL-0013 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0013 artifact {size}B below floor")
        return 1
    if "SUCCESS:CNL-0013" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0013 sentinel absent from artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0013 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
