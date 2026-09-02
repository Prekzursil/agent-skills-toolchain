"""Strategy + constrained-prioritisation preset family (CNL-0109).

A preset is a typed delta over a CouncilSpec base: default_binding plus
editable_dials. Direction-setting (mutually exclusive) and budget
prioritisation (not mutually exclusive) bind different voting rules.
Ranked-choice is rejected on a portfolio outcome.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_PATH = REPO / "command-center/schema/council-preset.schema.json"
FIXTURES = HERE / "fixtures"
SIBLING_FIXTURE = FIXTURES / "sibling_catalog.json"

FAMILY_ID = "council.preset.family.strategy-and-constrained-prioritisation"
DIRECTION_ID = "council.preset.strategy.direction-under-uncertainty"
PORTFOLIO_ID = "council.preset.prioritisation.budget-constrained-portfolio"
SIBLING_ID = "council.preset.catalog-class.editable"
LIBRARY_NAME = "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"

MECHANISM_AXES = (
    "roles.required",
    "protocol_schedule",
    "voting.rule",
    "stopping.expression",
    "outcome_type",
)

PROTECTED_OWNER_BLOCKLIST = frozenset(
    {
        "delta.voting.rule",
        "delta.anti_failure.ranked_choice_forbidden",
        "outcome_type",
        "protocol_schedule",
    }
)


def _direction_preset() -> dict[str, Any]:
    return {
        "id": DIRECTION_ID,
        "kind": "council_preset",
        "family_id": FAMILY_ID,
        "title": "Direction-setting under uncertainty",
        "outcome_type": "exclusive_direction",
        "base_spec_ref": "CouncilSpec.v2",
        "base_spec_version": "2.0.0",
        "extends_c_ids": [
            {
                "id": SIBLING_ID,
                "relation": "extends",
                "source": f"{LIBRARY_NAME}#presets",
                "on_this_tree": "transcribed-only-library-absent",
            },
            {
                "id": "CNL-0061",
                "relation": "contrasts",
                "source": "command-center/WORK-UNIT-CATALOG.json#CNL-0061",
                "on_this_tree": "catalog-unit",
            },
        ],
        "default_binding": {
            "protocol": "P-pairwise-deliberation",
            "task_selector": "decision_kind==exclusive_direction",
        },
        "editable_dials": [
            "delta.stopping.confidence_floor",
            "delta.stopping.max_rounds",
            "delta.voting.cycle_completion",
            "delta.roles.optional",
        ],
        "protocol_schedule": [
            "P-forecast-priors",
            "P-pairwise-deliberation",
            "P-condorcet-tally",
            "P-confidence-gate",
        ],
        "delta": {
            "roles": {
                "required": [
                    "Strategist",
                    "Forecaster",
                    "Skeptic",
                    "DevilAdvocate",
                ],
                "optional": ["DomainWitness"],
            },
            "voting": {
                "rule": "pairwise-condorcet",
                "quorum": 4,
                "cycle_completion": "minmax",
                "declared_before_ballots": True,
                "uncertainty": {
                    "model": "beta-binomial-posterior",
                    "confidence_floor": 0.67,
                },
            },
            "stopping": {
                "expression": (
                    "condorcet_winner_exists AND "
                    "posterior_mass(winner)>=confidence_floor "
                    "OR rounds>=max_rounds THEN BLOCKED"
                ),
                "max_rounds": 6,
                "on_timeout": "BLOCKED",
                "on_unresolved": "BLOCKED",
                "skip_min_deliberation": False,
            },
            "anti_failure": {
                "on_split": "surface-disagreement",
                "no_silent_average": True,
                "ranked_choice_forbidden": True,
            },
            "audit": {
                "persist_transcript": True,
                "hash_inputs": True,
            },
        },
    }


def _portfolio_preset() -> dict[str, Any]:
    return {
        "id": PORTFOLIO_ID,
        "kind": "council_preset",
        "family_id": FAMILY_ID,
        "title": "Constrained prioritisation under a fixed budget",
        "outcome_type": "budget_portfolio",
        "base_spec_ref": "CouncilSpec.v2",
        "base_spec_version": "2.0.0",
        "extends_c_ids": [
            {
                "id": SIBLING_ID,
                "relation": "extends",
                "source": f"{LIBRARY_NAME}#presets",
                "on_this_tree": "transcribed-only-library-absent",
            },
            {
                "id": "CNL-0062",
                "relation": "extends",
                "source": "command-center/WORK-UNIT-CATALOG.json#CNL-0062",
                "on_this_tree": "catalog-unit",
            },
            {
                "id": "CNL-0061",
                "relation": "contrasts",
                "source": "command-center/WORK-UNIT-CATALOG.json#CNL-0061",
                "on_this_tree": "catalog-unit",
            },
        ],
        "default_binding": {
            "protocol": "P-cardinal-knapsack",
            "task_selector": "decision_kind==budget_portfolio",
        },
        "editable_dials": [
            "delta.budget.amount",
            "delta.budget.unit",
            "delta.voting.score_scale",
            "delta.stopping.max_rounds",
        ],
        "protocol_schedule": [
            "P-score-elicit",
            "P-scale-calibrate",
            "P-dependency-graph",
            "P-knapsack-aggregate",
            "P-dissent-record",
        ],
        "delta": {
            "roles": {
                "required": [
                    "Treasurer",
                    "ValueScorer",
                    "PortfolioSkeptic",
                    "DependencyMapper",
                ],
                "optional": ["OwnerProxy"],
            },
            "voting": {
                "rule": "calibrated-score-knapsack",
                "quorum": 4,
                "score_scale": {"min": 0, "max": 10},
                "calibration": "within-participant-z-then-median-pool",
                "aggregator": "value-density-knapsack",
                "exclusivity": False,
            },
            "stopping": {
                "expression": (
                    "feasible_set_stable_for 2 rounds AND calibration_ok "
                    "OR rounds>=max_rounds THEN emit-feasible-set-with-dissent"
                ),
                "max_rounds": 5,
                "on_timeout": "emit-feasible-set-with-dissent",
                "on_unresolved": "BLOCKED",
                "skip_min_deliberation": False,
            },
            "anti_failure": {
                "ranked_choice_forbidden": True,
                "reject_reason": "options_not_mutually_exclusive",
            },
            "budget": {
                "required": True,
                "hard_constraint": True,
                "amount": None,
                "unit": "currency",
            },
            "audit": {
                "persist_transcript": True,
                "hash_inputs": True,
            },
        },
    }


def family_presets() -> list[dict[str, Any]]:
    return [_direction_preset(), _portfolio_preset()]


def find_library(repo: Path) -> Path | None:
    candidates = [
        repo / LIBRARY_NAME,
        repo / "command-center" / "sources" / LIBRARY_NAME,
        repo / "command-center" / "design" / "council" / LIBRARY_NAME,
        repo / "command-center" / "p2-wave" / "fixtures" / LIBRARY_NAME,
    ]
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _extract_presets(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict) and p.get("id")]
    if not isinstance(payload, dict):
        return []
    for key in ("presets", "records", "items", "council_presets"):
        block = payload.get(key)
        if isinstance(block, list):
            return [p for p in block if isinstance(p, dict) and p.get("id")]
        if isinstance(block, dict):
            out = []
            for pid, body in block.items():
                if isinstance(body, dict):
                    row = dict(body)
                    row.setdefault("id", pid)
                    out.append(row)
            if out:
                return out
    return []


def load_sibling_catalog(repo: Path) -> dict[str, Any]:
    real = find_library(repo)
    if real is not None:
        payload = json.loads(real.read_text(encoding="utf-8"))
        presets = _extract_presets(payload)
        return {
            "source": "on-disk-library",
            "path": str(real.relative_to(repo)).replace("\\", "/"),
            "library_present": True,
            "preset_count": len(presets),
            "presets": presets,
        }
    fixture = json.loads(SIBLING_FIXTURE.read_text(encoding="utf-8"))
    presets = list(fixture.get("presets") or [])
    return {
        "source": "transcribed-fixture-library-absent",
        "path": str(SIBLING_FIXTURE.relative_to(repo)).replace("\\", "/"),
        "library_present": False,
        "preset_count": len(presets),
        "presets": presets,
        "honesty": (
            f"{LIBRARY_NAME} is not a file on this worktree. "
            "Nearest-sibling comparison uses the on-tree transcription of "
            f"{SIBLING_ID} (ARC-0003 catalog-cited axes), not a recount of 72."
        ),
    }


def bind_preset(task: dict[str, Any], presets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    presets = presets or family_presets()
    kind = str(task.get("decision_kind") or "")
    for preset in presets:
        selector = str(preset["default_binding"]["task_selector"])
        want = selector.split("==", 1)[-1].strip()
        if kind == want:
            return copy.deepcopy(preset)
    raise ValueError(f"no preset binds decision_kind={kind!r}")


def _set_path(obj: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur: Any = obj
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def apply_owner_overrides(preset: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    out = copy.deepcopy(preset)
    if not overrides:
        return out
    allowed = set(out.get("editable_dials") or [])
    for key, value in overrides.items():
        if key in PROTECTED_OWNER_BLOCKLIST or key not in allowed:
            raise ValueError(
                f"REJECT non-editable dial {key!r} (allowed={sorted(allowed)})"
            )
        _set_path(out, key, value)
    return out


def instantiate(task: dict[str, Any], owner_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    preset = apply_owner_overrides(bind_preset(task), owner_overrides)
    if (
        preset["outcome_type"] == "budget_portfolio"
        and str(preset["delta"]["voting"]["rule"]) == "ranked-choice"
    ):
        raise ValueError(
            "REJECT ranked-choice on budget_portfolio: options are not "
            "mutually exclusive; IRV elects one substitute winner"
        )
    delta = preset["delta"]
    roster = list(delta["roles"]["required"])
    if task.get("include_optional"):
        roster.extend(delta["roles"].get("optional") or [])
    stopping = delta["stopping"]
    if preset["outcome_type"] == "budget_portfolio":
        budget = task.get("budget")
        if budget is None:
            raise ValueError("REJECT budget_portfolio task without budget")
        delta.setdefault("budget", {})["amount"] = budget
    return {
        "task_id": task["id"],
        "preset_id": preset["id"],
        "roster": roster,
        "protocol_schedule": list(preset["protocol_schedule"]),
        "voting_method": delta["voting"]["rule"],
        "stopping_expression": stopping["expression"],
        "outcome_type": preset["outcome_type"],
        "quorum": delta["voting"]["quorum"],
        "max_rounds": stopping["max_rounds"],
    }


def fingerprint(preset: dict[str, Any]) -> dict[str, Any]:
    delta = preset.get("delta") or {}
    roles = delta.get("roles") or {}
    voting = delta.get("voting") or {}
    stopping = delta.get("stopping") or {}
    schedule = preset.get("protocol_schedule")
    if not schedule:
        schedule = [str((preset.get("default_binding") or {}).get("protocol") or "")]
    return {
        "roles.required": tuple(sorted(roles.get("required") or [])),
        "protocol_schedule": tuple(schedule),
        "voting.rule": voting.get("rule") or voting.get("method") or "",
        "stopping.expression": stopping.get("expression")
        or f"max_rounds={stopping.get('max_rounds')}",
        "outcome_type": preset.get("outcome_type") or "unspecified",
    }


def profile_distance(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    fa, fb = fingerprint(a), fingerprint(b)
    differing = [axis for axis in MECHANISM_AXES if fa[axis] != fb[axis]]
    return {
        "distance": len(differing),
        "differing_axes": differing,
        "left": {k: list(v) if isinstance(v, tuple) else v for k, v in fa.items()},
        "right": {k: list(v) if isinstance(v, tuple) else v for k, v in fb.items()},
    }


def nearest_sibling(
    preset: dict[str, Any], siblings: list[dict[str, Any]]
) -> dict[str, Any]:
    if not siblings:
        raise ValueError("no sibling named: library empty")
    ranked = []
    for sib in siblings:
        if sib.get("id") == preset.get("id"):
            continue
        diff = profile_distance(preset, sib)
        ranked.append((diff["distance"], str(sib.get("id")), diff, sib))
    if not ranked:
        raise ValueError("no sibling named after dropping self")
    ranked.sort(key=lambda row: (row[0], row[1]))
    dist, sid, diff, sib = ranked[0]
    if dist == 0:
        raise ValueError(
            f"mechanism-duplicate of {sid}: differential is only the name; merge"
        )
    return {
        "named": sid,
        "source_id": sib.get("source_id")
        or sib.get("source")
        or f"{LIBRARY_NAME}#presets",
        "profile_distance": dist,
        "differing_axes": diff["differing_axes"],
        "left_fingerprint": diff["left"],
        "right_fingerprint": diff["right"],
    }


def name_only_clone(preset: dict[str, Any], new_id: str) -> dict[str, Any]:
    clone = copy.deepcopy(preset)
    clone["id"] = new_id
    return clone
