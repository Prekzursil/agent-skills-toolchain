#!/usr/bin/env python3
"""CNL-0101 typed-delta preset corpus, apply, and base-version migrate.

The Windows harness file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is not on this
worktree. This module builds a 72-record catalog-class corpus whose 20-key
union is reconstructed from catalog-cited axes and the two keys named in
CNL-0101 (editable_dials, default_binding). It does not claim a byte copy of
the missing library.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
SCHEMA_REL = "command-center/schema/council-preset.schema.json"

SPEC_ID = "councilspec.v2"
SPEC_V1 = "1.0.0"
SPEC_V2 = "2.0.0"

METADATA_KEYS = (
    "id",
    "title",
    "status",
    "default_binding",
    "editable_dials",
)
BASE_KEYS = ("spec_id", "spec_version")
DELTA_KEYS = (
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
    "anti_failure",
    "audit",
    "consensus",
)
KEY_UNION = METADATA_KEYS + BASE_KEYS + DELTA_KEYS
assert len(KEY_UNION) == 20
assert len(set(KEY_UNION)) == 20

# Overlay keys that remain on the CouncilSpec and are NOT carried by presets.
# Their absence on presets is the mechanical distinction from a fork.
BASE_ONLY_SECTIONS = ("artifacts", "execution", "meta")

BASE_V1_SECTIONS = DELTA_KEYS + BASE_ONLY_SECTIONS
# v2 drops engagement (presets overlaying it cannot migrate) and adds cadence.
BASE_V2_SECTIONS = tuple(
    s for s in BASE_V1_SECTIONS if s != "engagement"
) + ("cadence",)

STATUS_DISCOVERY = "DISCOVERY - no protocol here has been executed"
OUTCOMES = (
    "decision",
    "conditional-decision",
    "no-decision",
    "irreducible-disagreement",
    "dissent-with-minority-report",
    "proof-of-impossibility",
)
ROLES = ("Architect", "Skeptic", "Pragmatist", "Critic")
TITLES = (
    "C-M01 catalog-class measured preset",
    "Generative 100-idea brainstorm",
    "Innovation moonshot",
    "Gated design critique board",
    "Release go-no-go board",
    "Anonymous peer-review with rebuttal",
    "Code-review tribunal with oracle",
    "Security red/blue council",
    "Live incident war room",
    "Retrospective postmortem",
    "Forecasting with proper scoring",
    "Expert elicitation",
    "Flagship auto-composed council",
    "Owner-in-the-loop stepwise",
    "Minority-report mandatory",
    "Stopping-rule tournament",
    "Cross-vendor mirrored",
    "Shadow council",
    "Escalation ladder",
    "Nested subcouncils meta",
)

LIBRARY_CANDIDATES = (
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/design/council/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)


def library_hits() -> dict[str, bool]:
    hits = {}
    for rel in LIBRARY_CANDIDATES:
        hits[rel] = (REPO / rel).is_file()
    win = Path(
        "/Users/Prekzursil/.claude/harness-restore-20260806/"
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    )
    hits[str(win)] = win.is_file()
    return hits


def library_present() -> bool:
    return any(library_hits().values())


def classify_key(key: str) -> str:
    if key in METADATA_KEYS:
        return "metadata"
    if key in BASE_KEYS:
        return "base"
    if key in DELTA_KEYS:
        return "delta"
    raise KeyError(key)


def key_map_rows() -> list[dict[str, str]]:
    rationale = {
        "id": "Identity of the preset record; not a CouncilSpec section.",
        "title": "Human label; not an overlay onto the base spec.",
        "status": "Catalog-cited DISCOVERY status string; metadata, not overlay.",
        "default_binding": "Named in CNL-0101; binds a protocol, does not copy a spec.",
        "editable_dials": "Named in CNL-0101; the allow-list of overlay keys.",
        "spec_id": "Names the CouncilSpec this record is a delta over.",
        "spec_version": "Pins the base version; rewritten on a successful migrate.",
        "charter": "Optional overlay of IMP-0261 section charter.",
        "participants": "Optional overlay of IMP-0261 section participants.",
        "roles": "Optional overlay of IMP-0261 section roles.",
        "engagement": "Optional overlay; dropped by the v2 bump in this unit.",
        "budgets": "Optional overlay of IMP-0261 section budgets.",
        "evidence": "Optional overlay of IMP-0261 section evidence.",
        "voting": "Optional overlay; catalog-cited axis on all 117 R-A09 specs.",
        "stopping": "Optional overlay; catalog-cited axis on all 117 R-A09 specs.",
        "outcomes": "Optional overlay; CNL-0072 6-variant / 17-enum home.",
        "integrity": "Optional overlay of IMP-0261 section integrity.",
        "anti_failure": "Optional overlay; catalog-cited R-A09 axis.",
        "audit": "Optional overlay; catalog-cited R-A09 axis.",
        "consensus": "Optional overlay; catalog-cited R-A09 axis.",
    }
    return [
        {
            "key": k,
            "class": classify_key(k),
            "rationale": rationale[k],
        }
        for k in KEY_UNION
    ]


def base_spec(version: str) -> dict[str, Any]:
    sections = BASE_V1_SECTIONS if version == SPEC_V1 else BASE_V2_SECTIONS
    spec: dict[str, Any] = {
        "spec_id": SPEC_ID,
        "spec_version": version,
        "sections": list(sections),
        "charter": {"objective": "base-objective", "risk_tier": "T2"},
        "participants": [],
        "roles": list(ROLES),
        "budgets": {"max_rounds": 8, "max_tokens": 50000},
        "evidence": {"min_anchors": 2},
        "voting": {"rule": "majority", "quorum": 3},
        "stopping": {"max_rounds": 8, "on_timeout": "halt"},
        "outcomes": "no-decision",
        "integrity": {"hash_inputs": True},
        "anti_failure": {"no_silent_average": True},
        "audit": {"persist_transcript": True},
        "consensus": {"local_completion_forbidden": True},
        "artifacts": {"transcript": True},
        "execution": {"runtime": "councilspec"},
        "meta": {"schema": "councilspec.v2"},
    }
    if "engagement" in sections:
        spec["engagement"] = {"cadence": "round-robin"}
    if "cadence" in sections:
        spec["cadence"] = {"order": "round-robin"}
    return spec


def _overlay_for(index: int, include_engagement: bool) -> dict[str, Any]:
    roles = list(ROLES[: 3 + (index % 2)])
    overlay: dict[str, Any] = {
        "roles": roles,
        "voting": {
            "rule": ("unanimous-or-record-dissent", "majority", "supermajority")[
                index % 3
            ],
            "quorum": len(roles),
        },
        "stopping": {"max_rounds": 4 + (index % 5) * 2, "on_timeout": "halt"},
        "outcomes": OUTCOMES[index % len(OUTCOMES)],
        "anti_failure": {
            "on_split": "surface-disagreement",
            "no_silent_average": True,
        },
        "audit": {"persist_transcript": True, "hash_inputs": True},
        "consensus": {"reducer": "shared-completion-predicate-name"},
    }
    if index % 4 == 0:
        overlay["evidence"] = {"min_anchors": 3, "oracle_required": index % 8 == 0}
    if index % 5 == 0:
        overlay["budgets"] = {"max_rounds": overlay["stopping"]["max_rounds"]}
    if index % 6 == 0:
        overlay["charter"] = {
            "objective": f"preset-{index}-objective",
            "risk_tier": ("T1", "T2", "T3")[index % 3],
        }
    if index % 7 == 0:
        overlay["participants"] = [
            {"seat": r, "authority": "vote"} for r in roles
        ]
    if index % 8 == 0:
        overlay["integrity"] = {"hash_inputs": True, "replay": True}
    if include_engagement:
        overlay["engagement"] = {"cadence": "owner-gated"}
    return overlay


def preset_ids() -> list[str]:
    ids = ["C-M01"]
    ids.extend(f"C-{i:03d}" for i in range(2, 73))
    if len(ids) != 72:
        raise RuntimeError(f"preset id count {len(ids)}")
    return ids


def build_presets() -> list[dict[str, Any]]:
    """72 catalog-class records. C-M01, C-002, C-003 overlay engagement."""
    rows = []
    for i, pid in enumerate(preset_ids()):
        include_engagement = pid in {"C-M01", "C-002", "C-003"}
        overlay = _overlay_for(i, include_engagement)
        title = TITLES[i] if i < len(TITLES) else f"catalog-class preset {pid}"
        proto_n = (i % 58) + 1
        rec: dict[str, Any] = {
            "id": pid,
            "title": title,
            "status": STATUS_DISCOVERY,
            "default_binding": {
                "protocol_id": f"P-{proto_n:02d}",
                "protocol_family": "catalog-class",
            },
            "editable_dials": sorted(overlay.keys()),
            "spec_id": SPEC_ID,
            "spec_version": SPEC_V1,
        }
        rec.update(overlay)
        rows.append(rec)
    return rows


def independent_union(presets: list[dict[str, Any]]) -> list[str]:
    keys: set[str] = set()
    for rec in presets:
        keys.update(k for k in rec.keys() if not str(k).startswith("_"))
    return sorted(keys)


def independent_classify(union: list[str]) -> dict[str, str]:
    """Rule-based class map. Probe1 re-implements the same three sets."""
    out = {}
    meta = set(METADATA_KEYS)
    base = set(BASE_KEYS)
    for k in union:
        if k in meta:
            out[k] = "metadata"
        elif k in base:
            out[k] = "base"
        else:
            out[k] = "delta"
    return out


def apply_delta(
    preset: dict[str, Any], spec: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Apply overlay. Silent override of a non-editable dial is REJECTED."""
    spec = spec or base_spec(str(preset.get("spec_version") or SPEC_V1))
    allowed = set(preset.get("editable_dials") or [])
    resolved = json.loads(json.dumps(spec))
    overlays = []
    for key in DELTA_KEYS:
        if key not in preset:
            continue
        if key not in allowed:
            return {
                "ok": False,
                "rejected": True,
                "reason": "non-editable-dial-override",
                "key": key,
                "preset_id": preset.get("id"),
                "verbatim": (
                    f"REJECT non-editable-dial-override preset={preset.get('id')} "
                    f"key={key} not in editable_dials={sorted(allowed)}"
                ),
            }
        if key not in spec.get("sections", []):
            return {
                "ok": False,
                "rejected": True,
                "reason": "overlay-key-absent-from-base",
                "key": key,
                "preset_id": preset.get("id"),
            }
        resolved[key] = preset[key]
        overlays.append(key)
    resolved["applied_from_preset"] = preset.get("id")
    resolved["applied_delta_keys"] = overlays
    return {"ok": True, "rejected": False, "resolved": resolved}


def migrate_one(
    preset: dict[str, Any], new_version: str = SPEC_V2
) -> dict[str, Any]:
    new_spec = base_spec(new_version)
    sections = set(new_spec["sections"])
    missing = []
    for key in DELTA_KEYS:
        if key in preset and key not in sections:
            missing.append(key)
    if missing:
        return {
            "ok": False,
            "migrated": False,
            "id": preset["id"],
            "missing_in_new_base": missing,
        }
    migrated = json.loads(json.dumps(preset))
    migrated["spec_version"] = new_version
    return {"ok": True, "migrated": True, "id": preset["id"], "preset": migrated}


def migrate_all(
    presets: list[dict[str, Any]], new_version: str = SPEC_V2
) -> dict[str, Any]:
    migrated = []
    blocked = []
    for rec in presets:
        row = migrate_one(rec, new_version)
        if row["migrated"]:
            migrated.append(row["id"])
        else:
            blocked.append(
                {"id": row["id"], "missing_in_new_base": row["missing_in_new_base"]}
            )
    if len(migrated) + len(blocked) != len(presets):
        raise RuntimeError("migrate_all lost a preset")
    return {
        "from_version": SPEC_V1,
        "to_version": new_version,
        "preset_count": len(presets),
        "migrated_count": len(migrated),
        "cannot_migrate_count": len(blocked),
        "cannot_migrate_ids": [b["id"] for b in blocked],
        "cannot_migrate": blocked,
        "dropped_base_keys": ["engagement"],
        "added_base_keys": ["cadence"],
    }


RECORD_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNL-0101/fixtures/preset.record.schema.json"
)


def record_schema(_full: dict[str, Any] | None = None) -> dict[str, Any]:
    return json.loads((REPO / RECORD_SCHEMA_REL).read_text(encoding="utf-8"))


def load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def write_fixtures() -> dict[str, Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    presets = build_presets()
    paths = {
        "presets": FIXTURES / "presets.json",
        "base_v1": FIXTURES / "base_spec_v1.json",
        "base_v2": FIXTURES / "base_spec_v2.json",
        "invalid": FIXTURES / "invalid_preset.json",
        "silent_override": FIXTURES / "silent_non_editable.json",
    }
    paths["presets"].write_text(
        json.dumps(presets, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    paths["base_v1"].write_text(
        json.dumps(base_spec(SPEC_V1), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["base_v2"].write_text(
        json.dumps(base_spec(SPEC_V2), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["invalid"].write_text(
        json.dumps(
            {
                "id": "C-BAD",
                "title": "deliberately invalid",
                "status": STATUS_DISCOVERY,
                "default_binding": {"protocol_id": "P-01"},
                "editable_dials": ["roles"],
                "spec_id": SPEC_ID,
                "spec_version": SPEC_V1,
                "fork_copied_artifacts": True,
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    silent = {
        "id": "C-SILENT-OVERRIDE",
        "title": "planted silent non-editable overlay",
        "status": STATUS_DISCOVERY,
        "default_binding": {"protocol_id": "P-01", "protocol_family": "catalog-class"},
        "editable_dials": ["roles"],
        "spec_id": SPEC_ID,
        "spec_version": SPEC_V1,
        "roles": ["Architect", "Skeptic"],
        "voting": {"rule": "unanimous", "quorum": 99},
    }
    paths["silent_override"].write_text(
        json.dumps(silent, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return paths


def load_presets() -> list[dict[str, Any]]:
    path = FIXTURES / "presets.json"
    if not path.is_file():
        write_fixtures()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != 72:
        raise RuntimeError(f"expected 72 presets, got {type(data)} len={getattr(data, '__len__', lambda: None)()}")
    return data
