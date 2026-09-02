#!/usr/bin/env python3
"""Reconstructed v1 charter schema + 58 protocol / 72 preset catalogue fixtures.

The catalog inputs
  C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json
  C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json
are ABSENT on this worktree (same finding as ARC-0003/ARC-0010). Fixtures are
derived from catalog-cited structure, not from those files:

  * 13 v1 sections / 12 required: IMP-0261 question_or_target
  * $defs.stopping_expr (string form): CNL-0010 evidence_requirement
  * $defs.seat / $defs.role / $defs.outcome: CNL-0005, CNL-0022, CNL-0072
  * 58 protocol P-ids and 9 families: CNL-0038..CNL-0046 question_or_target
  * 72 presets, 20 keys including editable_dials + default_binding: CNL-0101
  * axes anti_failure/audit/voting/consensus/stopping: R-A09 disposition_evidence
  * C-M01 is the 20-key record cited by CNL-0002 (4 of 20 keys in the v1 set)

A later unit that obtains the harness files must replace these fixtures; this
unit does not invent a byte-copy of an unread file.
"""
from __future__ import annotations

from copy import deepcopy

V1_PROPERTIES = (
    "charter",
    "participants",
    "roles",
    "engagement",
    "budgets",
    "evidence",
    "voting",
    "stopping",
    "outcomes",
    "integrity",
    "artifacts",
    "execution",
    "meta",
)
V1_REQUIRED = V1_PROPERTIES[:-1]  # meta is the one optional property
SHAPE_CHANGE_PROPERTY = "stopping"

# Four names that also appear on catalogue records (CNL-0002: 4 of 20 recognised).
V1_CATALOGUE_OVERLAP = ("roles", "evidence", "voting", "stopping")

PRESET_KEYS = (
    "id",
    "name",
    "status",
    "description",
    "family",
    "base_spec",
    "default_binding",
    "editable_dials",
    "editable",
    "roles",
    "anti_failure",
    "audit",
    "voting",
    "consensus",
    "stopping",
    "evidence",
    "outcome",
    "protocol_binding",
    "anonymity",
    "replay",
)
assert len(PRESET_KEYS) == 20
assert set(V1_CATALOGUE_OVERLAP).issubset(PRESET_KEYS)
assert len(set(PRESET_KEYS) & set(V1_PROPERTIES)) == 4

PROTOCOL_KEYS = (
    "id",
    "family",
    "name",
    "description",
    "status",
    "anti_failure",
    "audit",
    "voting",
    "consensus",
    "stopping",
    "roles",
    "evidence",
    "turn_model",
)

PROTOCOL_FAMILIES: list[tuple[str, tuple[tuple[str, str], ...]]] = [
    (
        "DELIBERATIVE",
        (
            ("P01", "free-form-moderated-panel"),
            ("P02", "round-robin"),
            ("P03", "fishbowl"),
            ("P04", "consensus-conference"),
            ("P05", "rotating-chair"),
            ("P06", "nominal-group-technique"),
        ),
    ),
    (
        "ADVERSARIAL",
        (
            ("P07", "oxford-debate"),
            ("P08", "red-blue-team"),
            ("P09", "dialectical-inquiry"),
            ("P10", "mandated-devils-advocate"),
            ("P11", "team-b-competitive-estimate"),
            ("P12", "adversarial-collaboration"),
            ("P13", "hostile-cross-examination"),
        ),
    ),
    (
        "JUDICIAL",
        (
            ("P14", "judge-and-jury"),
            ("P15", "claim-by-claim-adjudication"),
            ("P16", "grand-jury-threshold"),
            ("P17", "jury-with-allowed-hung"),
            ("P18", "two-key-dual-control"),
            ("P19", "rfc-last-call"),
        ),
    ),
    (
        "ANONYMOUS",
        (
            ("P20", "delphi-anonymous-rounds"),
            ("P21", "wideband-delphi-estimation"),
            ("P22", "brainwriting-635"),
            ("P23", "silent-start-pooling"),
            ("P24", "surprisingly-popular-bts"),
            ("P25", "blind-reevaluation"),
        ),
    ),
    (
        "GENERATIVE",
        (
            ("P26", "brainstorming-swarm"),
            ("P27", "design-charrette"),
            ("P28", "morphological-analysis"),
            ("P29", "triz-contradiction"),
            ("P30", "six-hats-rotation"),
            ("P31", "constraint-relaxation"),
            ("P32", "counterfactual-council"),
        ),
    ),
    (
        "FORECASTING",
        (
            ("P33", "prediction-tournament"),
            ("P34", "scenario-planning"),
            ("P35", "reference-class-planning-poker"),
            ("P36", "calibration-tournament"),
            ("P37", "pairwise-comparison"),
        ),
    ),
    (
        "TRADECRAFT",
        (
            ("P38", "analysis-of-competing-hypotheses"),
            ("P39", "key-assumptions-check"),
            ("P40", "quality-of-information-check"),
            ("P41", "deception-detection"),
            ("P42", "argument-mapping"),
            ("P43", "premortem"),
            ("P44", "postmortem-5whys-causal"),
        ),
    ),
    (
        "ENGINEERING-REVIEW",
        (
            ("P45", "scientific-peer-review"),
            ("P46", "architecture-review-board"),
            ("P47", "incident-war-room"),
            ("P48", "kill-the-company"),
            ("P49", "socratic-interrogation"),
            ("P50", "evidence-clerk-led"),
            ("P51", "timeboxed-spike-council"),
        ),
    ),
    (
        "META-COMPOSITION",
        (
            ("P52", "nested-subcouncils-meta-council"),
            ("P53", "escalation-ladder"),
            ("P54", "cross-vendor-mirrored"),
            ("P55", "shadow-council"),
            ("P56", "minority-report-mandatory"),
            ("P57", "stopping-rule-tournament"),
            ("P58", "owner-in-the-loop-stepwise"),
        ),
    ),
]


def _section_object(extra_props: dict | None = None) -> dict:
    props = {
        "standard": {"type": "string", "minLength": 1},
        "hash_inputs": {"type": "boolean"},
    }
    if extra_props:
        props.update(extra_props)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["standard"],
        "properties": props,
    }


def v1_charter_schema() -> dict:
    """Reconstructed Council Charter v1 (11-COUNCIL-SPECIFICATION.schema.json)."""
    role = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name"],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "obligation": {"type": "string"},
            "permission": {"type": "string"},
            "right": {"type": "string"},
        },
    }
    seat = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "role"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "model": {"type": "string"},
            "vendor": {"type": "string"},
            "expertise": {"type": "string"},
            "role": {"type": "string", "minLength": 1},
            "authority": {"type": "string"},
            "vote_weight": {"type": "number"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "effort": {"type": "string"},
            "context": {"type": "string"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/schema/v1-council-charter.schema.json",
        "title": "Council Charter v1 (reconstructed; harness file absent)",
        "type": "object",
        "additionalProperties": False,
        "required": list(V1_REQUIRED),
        "properties": {
            "charter": {
                "type": "object",
                "additionalProperties": False,
                "required": ["objective"],
                "properties": {
                    "objective": {"type": "string", "minLength": 1},
                    "risk_tier": {"type": "string"},
                    "desired_output": {"type": "string"},
                    "success_criteria": {"type": "string"},
                    "consensus_intent": {"type": "string"},
                },
            },
            "participants": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/seat"}},
            "roles": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "engagement": {
                "type": "object",
                "additionalProperties": False,
                "required": ["min_turns"],
                "properties": {
                    "min_turns": {"type": "integer", "minimum": 1},
                    "max_inactivity": {"type": "integer", "minimum": 0},
                },
            },
            "budgets": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tokens"],
                "properties": {
                    "tokens": {"type": "integer", "minimum": 1},
                    "time_seconds": {"type": "integer", "minimum": 1},
                },
            },
            "evidence": _section_object(),
            "voting": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rule", "quorum"],
                "properties": {
                    "rule": {"type": "string", "minLength": 1},
                    "quorum": {"type": "integer", "minimum": 1},
                },
            },
            # THE v1 shape that cannot accept catalogue records: a bare expression string.
            "stopping": {"$ref": "#/$defs/stopping_expr"},
            "outcomes": {
                "type": "object",
                "additionalProperties": False,
                "required": ["allowed"],
                "properties": {
                    "allowed": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"$ref": "#/$defs/outcome"},
                    }
                },
            },
            "integrity": {
                "type": "object",
                "additionalProperties": False,
                "required": ["hash_transcript"],
                "properties": {"hash_transcript": {"type": "boolean"}},
            },
            "artifacts": {
                "type": "object",
                "additionalProperties": False,
                "required": ["persist"],
                "properties": {"persist": {"type": "boolean"}},
            },
            "execution": {
                "type": "object",
                "additionalProperties": False,
                "required": ["runtime"],
                "properties": {"runtime": {"type": "string", "minLength": 1}},
            },
            "meta": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"schema_version": {"type": "string"}},
            },
        },
        "$defs": {
            "seat": seat,
            "role": role,
            "stopping_expr": {"type": "string", "minLength": 1},
            "outcome": {
                "type": "string",
                "enum": [
                    "decision",
                    "conditional-decision",
                    "no-decision",
                    "irreducible-disagreement",
                    "dissent-with-minority-report",
                    "proof-of-impossibility",
                    "accept",
                    "reject",
                    "defer",
                    "escalate",
                    "hung",
                    "timeout",
                    "owner-override",
                    "replay",
                    "split",
                    "merge",
                    "unknown",
                ],
            },
        },
    }


def v1_charter_instance() -> dict:
    """A complete v1 charter used for round-trip (13 properties, 12 required)."""
    return {
        "charter": {
            "objective": "Select a protocol that validates catalogue records without dropping charter fields",
            "risk_tier": "high",
            "desired_output": "CouncilSpec v2 root envelope",
            "success_criteria": "130 catalogue records validate; v1 round-trip is byte-identical",
            "consensus_intent": "unanimous-or-record-dissent",
        },
        "participants": [
            {
                "id": "seat-architect",
                "model": "opus",
                "vendor": "anthropic",
                "expertise": "council-systems",
                "role": "Architect",
                "authority": "draft",
                "vote_weight": 1,
                "tools": ["Read"],
                "effort": "high",
                "context": "envelope-design",
            }
        ],
        "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        "engagement": {"min_turns": 2, "max_inactivity": 4},
        "budgets": {"tokens": 8000, "time_seconds": 3600},
        "evidence": {"standard": "executable-proof-only", "hash_inputs": True},
        "voting": {"rule": "unanimous-or-record-dissent", "quorum": 4},
        "stopping": "ALL(votes_cast) AND NOT timeout",
        "outcomes": {"allowed": ["decision", "irreducible-disagreement"]},
        "integrity": {"hash_transcript": True},
        "artifacts": {"persist": True},
        "execution": {"runtime": "councilspec-compiler"},
        "meta": {"schema_version": "1"},
    }


def _axes(i: int) -> dict:
    return {
        "anti_failure": {"on_split": "surface-disagreement", "no_silent_average": True},
        "audit": {
            "persist_transcript": True,
            "hash_inputs": True,
            "replay": True,
            "calibration": i % 2 == 0,
            "determinism": True,
            "persistence": True,
            "privacy": "named",
            "resume": True,
        },
        "voting": {"rule": "unanimous-or-record-dissent", "quorum": 4},
        "consensus": {
            "reducer": "shared-completion-predicate-name",
            "local_completion_forbidden": True,
        },
        "stopping": {"max_rounds": 4 + (i % 8), "on_timeout": "halt", "on_unresolved": "BLOCKED"},
        "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        "evidence": {"standard": "executable-proof-only", "hash_inputs": True},
    }


def protocol_records() -> list[dict]:
    rows: list[dict] = []
    n = 0
    for family, members in PROTOCOL_FAMILIES:
        for pid, name in members:
            n += 1
            axes = _axes(n)
            rec = {
                "id": pid,
                "family": family,
                "name": name,
                "description": f"{family} protocol {pid} ({name})",
                "status": "DISCOVERY - no protocol here has been executed",
                "anti_failure": axes["anti_failure"],
                "audit": axes["audit"],
                "voting": axes["voting"],
                "consensus": axes["consensus"],
                "stopping": axes["stopping"],
                "roles": axes["roles"],
                "evidence": axes["evidence"],
                "turn_model": "round-robin" if family != "ADVERSARIAL" else "attack-then-reply",
            }
            assert tuple(rec.keys()) == PROTOCOL_KEYS
            rows.append(rec)
    assert len(rows) == 58
    return rows


def preset_records() -> list[dict]:
    protocols = protocol_records()
    rows: list[dict] = []
    ids = ["C-M01"] + [f"C-{i:02d}" for i in range(2, 73)]
    assert len(ids) == 72
    for i, cid in enumerate(ids, start=1):
        proto = protocols[(i - 1) % 58]
        axes = _axes(i + 100)
        rec = {
            "id": cid,
            "name": f"preset-{cid.lower()}",
            "status": "DISCOVERY - no protocol here has been executed",
            "description": f"Typed delta over protocol {proto['id']}",
            "family": proto["family"],
            "base_spec": "councilspec-v2",
            "default_binding": proto["id"],
            "editable_dials": ["voting.quorum", "stopping.max_rounds"],
            "editable": True,
            "roles": axes["roles"],
            "anti_failure": axes["anti_failure"],
            "audit": axes["audit"],
            "voting": axes["voting"],
            "consensus": axes["consensus"],
            "stopping": axes["stopping"],
            "evidence": axes["evidence"],
            "outcome": "decision",
            "protocol_binding": proto["id"],
            "anonymity": "named",
            "replay": True,
        }
        assert tuple(rec.keys()) == PRESET_KEYS
        rows.append(rec)
    assert rows[0]["id"] == "C-M01"
    assert len(rows[0]) == 20
    return rows


def catalogue_file() -> dict:
    """Root object of 12-COUNCIL-PROTOCOLS-AND-PRESETS.json (reconstructed)."""
    return {
        "protocols": protocol_records(),
        "presets": preset_records(),
    }


def catalogue_records() -> list[dict]:
    cat = catalogue_file()
    return list(cat["protocols"]) + list(cat["presets"])


def cm01() -> dict:
    return deepcopy(preset_records()[0])
