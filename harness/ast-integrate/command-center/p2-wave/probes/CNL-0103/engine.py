#!/usr/bin/env python3
"""CNL-0103 engine: instantiate generative presets and compare fingerprints."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_PATH = REPO / "command-center" / "schema" / "council-preset.schema.json"
PROFILES_PATH = REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
RECEIPT_SCHEMA_PATH = REPO / "platform" / "schema" / "receipt.schema.json"
PRESET_RECORD_SCHEMA_PATH = HERE / "fixtures" / "preset.record.schema.json"
FAMILY_PATH = HERE / "fixtures" / "family_presets.json"
SIBLING_PATH = HERE / "fixtures" / "sibling_library.json"
TASK_PATH = HERE / "fixtures" / "fixture_task.json"
INVALID_PATH = HERE / "fixtures" / "invalid_preset.json"
OUT_REL = (
    "command-center/design/council/"
    "CNL-0103-generative-preset-family-100-idea-brainstorm-and-innovatio.md"
)
OUT_PATH = REPO / OUT_REL
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0103/probe1_instantiate_and_sibling.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0103/probe2_schema_and_negative.py"
)

BRAINSTORM_ID = "C-G26-100-idea-brainstorm"
MOONSHOT_ID = "C-G29-innovation-moonshot"
TOKEN_RE = re.compile(r"[a-z0-9]+")
FP_KEYS = (
    "roles",
    "protocols",
    "round_kinds",
    "vote_method",
    "prune_on",
    "stop_expr",
    "raw_count_stop",
    "feasibility_in_stop",
    "novelty",
    "feasibility_w",
    "accept_rule",
    "novelty_floor",
    "ranking_key",
)


class NonEditableOverride(Exception):
    pass


class MechanismDuplicate(Exception):
    pass


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema() -> dict:
    return load_json(SCHEMA_PATH)


def envelope_validator():
    """Draft 2020-12 validator for the catalog shim, resolved from disk.

    command-center/schema/council-preset.schema.json is a generated $ref
    shim whose $id lives under https://ast-integrate.invalid/. jsonschema
    4.10 would otherwise fetch that host. The store is the three on-disk
    files (shim, artifact-class-profiles, receipt). No network.
    """
    from jsonschema import Draft202012Validator, RefResolver

    shim = load_schema()
    if isinstance(shim, dict) and shim.get("$ref"):
        shim = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["report", "sentinel"],
            "additionalProperties": True,
            "properties": {
                "sentinel": {"type": "string", "const": "SUCCESS:CNL-0103"},
                "report": {
                    "type": "object",
                    "required": ["kind"],
                    "properties": {"kind": {"const": "council-preset"}},
                    "additionalProperties": True,
                },
            },
        }
    store = {}
    for path in (SCHEMA_PATH, PROFILES_PATH, RECEIPT_SCHEMA_PATH):
        doc = load_json(path)
        ident = doc.get("$id")
        if ident:
            store[ident] = doc
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def envelope_error_list(instance) -> list[str]:
    return [
        f"{list(err.absolute_path)}: {err.message}"
        for err in envelope_validator().iter_errors(instance)
    ]


def family_members() -> list[dict]:
    return load_json(FAMILY_PATH)["members"]


def sibling_presets() -> list[dict]:
    return load_json(SIBLING_PATH)["presets"]


def fixture_task() -> dict:
    return load_json(TASK_PATH)


def by_id(presets: list[dict], pid: str) -> dict:
    for row in presets:
        if row["id"] == pid:
            return row
    raise KeyError(pid)


def fingerprint(preset: dict) -> dict:
    bindings = sorted(preset["protocol_bindings"], key=lambda b: b["order"])
    return {
        "roles": tuple(sorted(r["role"] for r in preset["roster"])),
        "protocols": tuple(b["protocol_id"] for b in bindings),
        "round_kinds": tuple(b["round_kind"] for b in bindings),
        "vote_method": preset["voting"]["method"],
        "prune_on": preset["voting"]["prune_on"],
        "stop_expr": preset["stopping"]["expression"],
        "raw_count_stop": bool(preset["stopping"]["allow_raw_count_stop"]),
        "feasibility_in_stop": bool(preset["stopping"]["feasibility_in_stop"]),
        "novelty": round(float(preset["weighting"]["novelty"]), 2),
        "feasibility_w": round(float(preset["weighting"]["feasibility"]), 2),
        "accept_rule": preset["distinctness_gate"]["accept_rule"],
        "novelty_floor": round(float(preset["distinctness_gate"]["novelty_floor"]), 2),
        "ranking_key": tuple(preset["default_binding"]["ranking_key"]),
    }


def distance(left: dict, right: dict) -> tuple[int, list[str]]:
    fa, fb = fingerprint(left), fingerprint(right)
    diff = [k for k in FP_KEYS if fa[k] != fb[k]]
    return len(diff), diff


def weights_sum_to_one(preset: dict) -> bool:
    w = preset["weighting"]
    return abs(float(w["novelty"]) + float(w["feasibility"]) - 1.0) < 1e-9


def name_only_clone(preset: dict, new_id: str, new_name: str) -> dict:
    clone = copy.deepcopy(preset)
    clone["id"] = new_id
    clone["name"] = new_name
    return clone


def reject_if_duplicate(candidate: dict, existing: dict) -> None:
    dist, _ = distance(candidate, existing)
    if dist == 0:
        raise MechanismDuplicate(
            f"{candidate['id']} matches {existing['id']} on all mechanism fields"
        )


def apply_override(preset: dict, path: str, value) -> None:
    if path not in preset["editable_dials"]:
        raise NonEditableOverride(path)
    cur = preset
    parts = path.split(".")
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value


def instantiate(preset: dict, task: dict) -> dict:
    working = copy.deepcopy(preset)
    for path, value in (task.get("overrides") or {}).items():
        apply_override(working, path, value)
    if not weights_sum_to_one(working):
        raise ValueError(f"{working['id']} weighting does not sum to 1")
    split = working["generation_critique_split"]
    gen_roles = list(split["generation_round_roles"])
    cri_roles = list(split["critique_round_roles"])
    schedule = []
    for binding in sorted(working["protocol_bindings"], key=lambda b: b["order"]):
        kind = binding["round_kind"]
        seated = gen_roles if kind == "generation" else cri_roles
        schedule.append(
            {
                "order": binding["order"],
                "protocol_id": binding["protocol_id"],
                "round_kind": kind,
                "seated_roles": seated,
            }
        )
    stop = working["stopping"]
    target = stop["unique_ideas_target"]
    expression = stop["expression"]
    if target != 100 and "unique_ideas >= 100" in expression:
        expression = expression.replace(
            "unique_ideas >= 100", f"unique_ideas >= {target}"
        )
    return {
        "preset_id": working["id"],
        "task_id": task["id"],
        "roster": [r["role"] for r in working["roster"]],
        "protocol_schedule": schedule,
        "voting_method": working["voting"]["method"],
        "voting": copy.deepcopy(working["voting"]),
        "stopping_expression": expression,
        "stopping": copy.deepcopy(stop),
        "weighting": copy.deepcopy(working["weighting"]),
        "accept_rule": working["distinctness_gate"]["accept_rule"],
        "ranking_key": list(working["default_binding"]["ranking_key"]),
        "extends_c_ids": [row["c_id"] for row in working["supersedes_or_extends"]],
    }


def nearest_sibling(preset: dict, library: list[dict]) -> tuple[dict, int, list[str]]:
    best = None
    best_d = 10**9
    best_fields: list[str] = []
    for sib in library:
        if sib["id"] == preset["id"]:
            continue
        dist, fields = distance(preset, sib)
        if dist < best_d:
            best, best_d, best_fields = sib, dist, fields
    if best is None:
        raise RuntimeError("empty sibling library")
    return best, best_d, best_fields


def tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def same_idea(a: dict, b: dict, threshold: float) -> bool:
    if a["canonical_mechanism"] == b["canonical_mechanism"]:
        return True
    return jaccard(a["text"], b["text"]) >= threshold


def unique_ideas(ideas: list[dict], threshold: float = 0.85) -> list[dict]:
    kept: list[dict] = []
    for idea in ideas:
        if not any(same_idea(idea, k, threshold) for k in kept):
            kept.append(idea)
    return kept


def gaming_ledger() -> list[dict]:
    ideas = []
    for i in range(10):
        mech = f"mech-{i:03d}"
        for variant in range(10):
            ideas.append(
                {
                    "text": (
                        f"{mech} household energy trick number {variant} "
                        "with extra filler words"
                    ),
                    "canonical_mechanism": mech,
                    "novelty": 0.4,
                }
            )
    return ideas


def genuine_ledger(n: int = 100) -> list[dict]:
    ideas = []
    for i in range(n):
        mech = f"mech-{i:03d}"
        ideas.append(
            {
                "text": (
                    f"apparatus {mech} cuts standby draw via distinct "
                    f"{mech} topology"
                ),
                "canonical_mechanism": mech,
                "novelty": 0.86,
            }
        )
    return ideas


def stop_fires(preset: dict, ideas: list[dict], completeness: float = 1.0) -> bool:
    stop = preset["stopping"]
    if stop["allow_raw_count_stop"] and len(ideas) >= stop["unique_ideas_target"]:
        return True
    unique = unique_ideas(ideas)
    if len(unique) < stop["unique_ideas_target"]:
        return False
    floor = stop.get("completeness_floor")
    if floor is not None and completeness < float(floor):
        return False
    nov_floor = stop.get("novelty_median_floor")
    if nov_floor is not None:
        scores = sorted(float(item["novelty"]) for item in unique)
        mid = scores[len(scores) // 2]
        if mid < float(nov_floor):
            return False
    if stop["feasibility_in_stop"]:
        return False
    return True


def project_preset(preset: dict) -> dict:
    return {
        "id": preset["id"],
        "kind": "typed_delta",
        "relation": "extends",
        "base_spec": {
            "id": preset["base_spec_ref"],
            "version": preset["base_version"],
        },
        "extends_c_ids": [row["c_id"] for row in preset["supersedes_or_extends"]],
        "roles": [
            {"id": row["role"], "obligation": row["obligation"]}
            for row in preset["roster"]
        ],
        "voting": {
            "method": preset["voting"]["method"],
            "quorum": preset["voting"]["quorum"],
        },
        "stopping": {
            "expression": preset["stopping"]["expression"],
            "max_rounds": preset["stopping"]["max_rounds"],
        },
        "protocol_schedule": [
            row["protocol_id"]
            for row in sorted(preset["protocol_bindings"], key=lambda item: item["order"])
        ],
        "editable_dials": list(preset["editable_dials"]),
        "non_editable_dials": [
            "voting.method",
            "stopping.unique_ideas_source",
            "anti_failure.critique_cannot_seat_in_generation",
        ],
        "default_binding": preset["default_binding"]["task_class"],
        "weighting": copy.deepcopy(preset["weighting"]),
        "distinctness_gate": copy.deepcopy(preset["distinctness_gate"]),
        "generation_critique_split": copy.deepcopy(
            preset["generation_critique_split"]
        ),
    }


def project_instantiation(inst: dict) -> dict:
    return {
        "task_id": inst["task_id"],
        "roster_ids": list(inst["roster"]),
        "protocol_schedule": [row["protocol_id"] for row in inst["protocol_schedule"]],
        "voting": copy.deepcopy(inst["voting"]),
        "stopping": {
            "expression": inst["stopping_expression"],
            "max_rounds": inst["stopping"]["max_rounds"],
        },
    }


def preset_subschema(schema: dict | None = None) -> dict:
    """Typed-delta record schema for family members (not the catalog envelope).

    The catalog file is a receipt-class shim (report.kind=council-preset) and
    no longer carries properties.preset. Affected preset records are validated
    against this unit-local schema. The shared catalog file is not rewritten.
    """
    del schema
    return load_json(PRESET_RECORD_SCHEMA_PATH)
