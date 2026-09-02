"""Owner-constraint applicator: owner hard-wins, visible override, fail-closed.

Auto-composition always runs first and freezes auto_choice. Owner constraints
are a second recorded pass. A mutation without an override_log entry is a
silent-win defect. An unsatisfiable set returns BLOCKED with final_choice=null;
it never quietly drops a mandatory human or raises a ceiling.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "owner_constraint.block.schema.json"

HUMAN_COST_USD = 10.0
DOWNGRADE = {
    "opus": ("haiku", 6.0),
    "gpt-5": ("mini", 4.0),
    "sonnet": ("haiku", 6.0),
    "haiku": ("nano", 2.0),
    "mini": ("nano", 2.0),
}


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_instance(instance: dict, def_name: str) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = load_schema()
    validator = Draft202012Validator(
        {"$ref": f"#/$defs/{def_name}", "$defs": schema["$defs"]}
    )
    return [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(instance)]


def _seat(
    seat_id: str,
    kind: str,
    role: str,
    model: str | None,
    vendor: str,
    source_classes: list[str],
    cost_usd: float,
    vote_weight: float = 1.0,
) -> dict[str, Any]:
    return {
        "seat_id": seat_id,
        "kind": kind,
        "role": role,
        "model": model,
        "vendor": vendor,
        "source_classes": list(source_classes),
        "cost_usd": float(cost_usd),
        "vote_weight": float(vote_weight),
    }


def auto_compose(task: dict[str, Any]) -> dict[str, Any]:
    """Deterministic auto-composer for this unit's fixtures.

    High-risk payment work always gets a three-model adversarial roster that
    spends web-search. CNL-0013 owns a general selector; this function only
    has to disagree with the owner fixtures in a stable way.
    """
    _ = task
    roster = [
        _seat(
            "seat.architect",
            "model",
            "architect",
            "opus",
            "anthropic",
            ["repo-local", "web-search"],
            18.0,
        ),
        _seat(
            "seat.implementer",
            "model",
            "implementer",
            "gpt-5",
            "openai",
            ["repo-local"],
            16.0,
        ),
        _seat(
            "seat.adversary",
            "model",
            "adversary",
            "sonnet",
            "anthropic",
            ["repo-local", "web-search"],
            14.0,
        ),
    ]
    sources = sorted({s for seat in roster for s in seat["source_classes"]})
    budget = round(sum(seat["cost_usd"] for seat in roster), 2)
    return {
        "roster": roster,
        "budget_usd": budget,
        "source_classes": sources,
        "protocol": "adversarial-review",
    }


def choice_fingerprint(choice: dict[str, Any] | None) -> str:
    if choice is None:
        return "null"
    payload = {
        "roster": sorted(choice["roster"], key=lambda s: s["seat_id"]),
        "budget_usd": choice["budget_usd"],
        "source_classes": sorted(choice["source_classes"]),
        "protocol": choice["protocol"],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _refresh_choice(roster: list[dict[str, Any]], protocol: str) -> dict[str, Any]:
    sources = sorted({s for seat in roster for s in seat["source_classes"]})
    return {
        "roster": copy.deepcopy(roster),
        "budget_usd": round(sum(seat["cost_usd"] for seat in roster), 2),
        "source_classes": sources,
        "protocol": protocol,
    }


def _human_seat(constraint: dict[str, Any]) -> dict[str, Any]:
    return _seat(
        constraint["seat_id"],
        "human",
        constraint["role"],
        None,
        "human",
        ["owner-provided"],
        HUMAN_COST_USD,
        vote_weight=1.0,
    )


def _has_human(roster: list[dict[str, Any]], constraint: dict[str, Any]) -> bool:
    return any(
        seat["kind"] == "human"
        and (
            seat["seat_id"] == constraint["seat_id"]
            or seat["role"] == constraint["role"]
        )
        for seat in roster
    )


def _unsatisfied(
    choice: dict[str, Any] | None, constraints: list[dict[str, Any]]
) -> list[str]:
    if choice is None:
        return [c["constraint_id"] for c in constraints]
    bad: list[str] = []
    for c in constraints:
        cls = c["constraint_class"]
        if cls == "budget_ceiling" and choice["budget_usd"] > c["max_usd"] + 1e-9:
            bad.append(c["constraint_id"])
        elif cls == "forbidden_source_class":
            src = c["source_class"]
            if src in choice["source_classes"] or any(
                src in seat["source_classes"] for seat in choice["roster"]
            ):
                bad.append(c["constraint_id"])
        elif cls == "mandatory_human_seat":
            if not _has_human(choice["roster"], c):
                bad.append(c["constraint_id"])
    return bad


def _fit_budget(
    roster: list[dict[str, Any]],
    cap: float,
    protected_ids: set[str],
) -> tuple[list[dict[str, Any]] | None, list[str]]:
    roster = copy.deepcopy(roster)
    mutations: list[str] = []
    while sum(s["cost_usd"] for s in roster) > cap + 1e-9:
        candidates = [
            s
            for s in roster
            if s["kind"] == "model"
            and s["seat_id"] not in protected_ids
            and s.get("model") in DOWNGRADE
            and DOWNGRADE[s["model"]][1] < s["cost_usd"]
        ]
        if candidates:
            seat = max(candidates, key=lambda s: s["cost_usd"])
            new_model, new_cost = DOWNGRADE[seat["model"]]
            mutations.append(
                f"downgrade {seat['seat_id']} {seat['model']}->{new_model} "
                f"{seat['cost_usd']}->{new_cost}"
            )
            seat["model"] = new_model
            seat["cost_usd"] = new_cost
            continue
        droppable = [
            s
            for s in roster
            if s["kind"] == "model" and s["seat_id"] not in protected_ids
        ]
        if not droppable:
            return None, mutations
        seat = min(droppable, key=lambda s: s["cost_usd"])
        mutations.append(f"drop {seat['seat_id']} cost={seat['cost_usd']}")
        roster.remove(seat)
    return roster, mutations


def silent_win(auto: dict[str, Any], final: dict[str, Any] | None, log: list) -> bool:
    if final is None:
        return False
    changed = choice_fingerprint(auto) != choice_fingerprint(final)
    return changed and len(log) == 0


def apply_owner_constraints(
    task: dict[str, Any],
    constraints: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    for c in constraints:
        errors.extend(validate_instance(c, "owner_constraint"))
    if errors:
        raise ValueError("invalid owner constraints: " + "; ".join(errors))

    auto = auto_compose(task)
    roster = copy.deepcopy(auto["roster"])
    protocol = auto["protocol"]
    log: list[dict[str, Any]] = []
    attempted: list[str] = []
    protected: set[str] = set()

    budget_c = next(
        (c for c in constraints if c["constraint_class"] == "budget_ceiling"), None
    )
    source_cs = [
        c for c in constraints if c["constraint_class"] == "forbidden_source_class"
    ]
    human_cs = [
        c for c in constraints if c["constraint_class"] == "mandatory_human_seat"
    ]

    for c in source_cs:
        src = c["source_class"]
        affected = [s["seat_id"] for s in roster if src in s["source_classes"]]
        if not affected:
            continue
        for seat in roster:
            if src in seat["source_classes"]:
                seat["source_classes"] = [x for x in seat["source_classes"] if x != src]
        mutation = [f"remove source_class {src} from {sid}" for sid in affected]
        attempted.extend(mutation)
        log.append(
            {
                "constraint_id": c["constraint_id"],
                "constraint_class": "forbidden_source_class",
                "auto_value": sorted(
                    {s for seat in auto["roster"] for s in seat["source_classes"]}
                ),
                "owner_value": src,
                "mutation": mutation,
                "visible": True,
            }
        )

    for c in human_cs:
        protected.add(c["seat_id"])
        if _has_human(roster, c):
            continue
        roster.append(_human_seat(c))
        mutation = [f"insert mandatory human seat {c['seat_id']} role={c['role']}"]
        attempted.extend(mutation)
        log.append(
            {
                "constraint_id": c["constraint_id"],
                "constraint_class": "mandatory_human_seat",
                "auto_value": [s["seat_id"] for s in auto["roster"]],
                "owner_value": {"seat_id": c["seat_id"], "role": c["role"]},
                "mutation": mutation,
                "visible": True,
            }
        )

    if budget_c is not None:
        cap = float(budget_c["max_usd"])
        current = round(sum(s["cost_usd"] for s in roster), 2)
        if current > cap + 1e-9:
            fitted, mutations = _fit_budget(roster, cap, protected)
            attempted.extend(mutations)
            if fitted is None:
                return {
                    "status": "BLOCKED",
                    "task_id": task["id"],
                    "auto_choice": auto,
                    "final_choice": None,
                    "override_log": log,
                    "blocked": {
                        "reason": (
                            f"budget_ceiling {cap} cannot be met without dropping "
                            "a mandatory human seat or raising the owner ceiling"
                        ),
                        "unsatisfied_constraint_ids": [budget_c["constraint_id"]]
                        + [h["constraint_id"] for h in human_cs],
                        "attempted_mutations": attempted,
                    },
                    "visibility": {
                        "override_log_is_primary_record": True,
                        "roster_diff_is_not_sufficient": True,
                        "silent_win": False,
                    },
                }
            roster = fitted
            log.append(
                {
                    "constraint_id": budget_c["constraint_id"],
                    "constraint_class": "budget_ceiling",
                    "auto_value": auto["budget_usd"],
                    "owner_value": cap,
                    "mutation": mutations,
                    "visible": True,
                }
            )

    final = _refresh_choice(roster, protocol)
    bad = _unsatisfied(final, constraints)
    if bad:
        return {
            "status": "BLOCKED",
            "task_id": task["id"],
            "auto_choice": auto,
            "final_choice": None,
            "override_log": log,
            "blocked": {
                "reason": (
                    "owner constraints remain unsatisfied after every "
                    "non-relaxing mutation; refusing quiet relaxation"
                ),
                "unsatisfied_constraint_ids": bad,
                "attempted_mutations": attempted,
            },
            "visibility": {
                "override_log_is_primary_record": True,
                "roster_diff_is_not_sufficient": True,
                "silent_win": False,
            },
        }

    if silent_win(auto, final, log):
        raise AssertionError("silent-win produced by applicator (authoring bug)")
    return {
        "status": "COMPOSED",
        "task_id": task["id"],
        "auto_choice": auto,
        "final_choice": final,
        "override_log": log,
        "blocked": None,
        "visibility": {
            "override_log_is_primary_record": True,
            "roster_diff_is_not_sufficient": True,
            "silent_win": False,
        },
    }


def plant_silent_win(result: dict[str, Any]) -> dict[str, Any]:
    """Planted-bad: same mutated roster, empty override_log."""
    planted = copy.deepcopy(result)
    planted["override_log"] = []
    planted["visibility"]["silent_win"] = silent_win(
        planted["auto_choice"], planted["final_choice"], planted["override_log"]
    )
    return planted


def plant_quiet_relaxation(
    unsat_result: dict[str, Any], auto: dict[str, Any]
) -> dict[str, Any]:
    """Planted-bad: COMPOSED with the auto roster despite unsatisfiable constraints."""
    planted = copy.deepcopy(unsat_result)
    planted["status"] = "COMPOSED"
    planted["final_choice"] = copy.deepcopy(auto)
    planted["blocked"] = None
    planted["override_log"] = []
    planted["visibility"]["silent_win"] = False
    return planted
