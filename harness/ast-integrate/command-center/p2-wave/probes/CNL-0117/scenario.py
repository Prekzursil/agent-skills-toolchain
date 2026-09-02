"""Load and validate the CNL-0117 scripted-council fixture."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "scenario.json"
ALLOWED_KINDS = frozenset({"position", "vote", "refusal", "death", "silence"})
REQUIRED_KINDS = frozenset({"position", "vote", "refusal"})


def load_scenario(path: Path | None = None) -> dict:
    target = path or FIXTURE
    doc = json.loads(target.read_text(encoding="utf-8"))
    errors = validate_scenario(doc)
    if errors:
        raise ValueError("scenario invalid: " + "; ".join(errors))
    return doc


def validate_scenario(scenario: dict) -> list[str]:
    errors: list[str] = []
    roster = scenario.get("roster")
    scripts = scenario.get("scripts")
    ceiling = scenario.get("round_ceiling")
    if not isinstance(roster, list) or len(roster) < 2:
        errors.append("roster must list at least two participants")
        return errors
    if not isinstance(scripts, dict):
        errors.append("scripts must be an object keyed by participant id")
        return errors
    if not isinstance(ceiling, int) or ceiling < 1:
        errors.append("round_ceiling must be a positive integer")
        return errors
    roster_ids = []
    for row in roster:
        if not isinstance(row, dict) or not row.get("id"):
            errors.append("roster row missing id")
            continue
        roster_ids.append(row["id"])
    if len(roster_ids) != len(set(roster_ids)):
        errors.append("duplicate roster id")
    if set(scripts) != set(roster_ids):
        errors.append("scripts keys must equal roster ids")
    seen: set[tuple[str, int]] = set()
    kinds: set[str] = set()
    for aid in roster_ids:
        acts = scripts.get(aid)
        if not isinstance(acts, list) or not acts:
            errors.append(f"script empty for {aid}")
            continue
        for act in acts:
            if not isinstance(act, dict):
                errors.append(f"non-object act in {aid}")
                continue
            kind = act.get("kind")
            rnd = act.get("round")
            payload = act.get("payload")
            if kind not in ALLOWED_KINDS:
                errors.append(f"unknown kind {kind!r} for {aid}")
            if not isinstance(rnd, int) or rnd < 1 or rnd > ceiling:
                errors.append(f"round out of range for {aid}: {rnd!r}")
                continue
            if not isinstance(payload, dict):
                errors.append(f"payload must be an object for {aid} round {rnd}")
            key = (aid, rnd)
            if key in seen:
                errors.append(f"duplicate act {key}")
            seen.add(key)
            if isinstance(kind, str):
                kinds.add(kind)
    for rnd in range(1, ceiling + 1):
        for aid in roster_ids:
            if (aid, rnd) not in seen:
                errors.append(f"missing scripted act for {(aid, rnd)}")
    missing_kinds = sorted(REQUIRED_KINDS - kinds)
    if missing_kinds:
        errors.append(
            "fixture must include scripted "
            + ", ".join(sorted(REQUIRED_KINDS))
            + f"; missing {missing_kinds}"
        )
    if scenario.get("tally_method") != "plurality":
        errors.append("this substrate freeze is plurality-only")
    return errors


def roster_ids(scenario: dict) -> list[str]:
    return [row["id"] for row in scenario["roster"]]
