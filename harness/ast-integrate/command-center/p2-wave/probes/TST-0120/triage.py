"""Publish a mutation score only with a reviewed exclusion trail.

Rejects: omitted exclusion_count (overclaim), boilerplate justifications,
same-author reviewers, and exclusions the oracle pack can distinguish.
"""
from __future__ import annotations

from typing import Any

from policy import (
    AUTHOR_ID,
    BOILERPLATE_JUSTIFICATIONS,
    ESTATE_OPERATORS,
    MIN_JUSTIFICATION_CHARS,
    POLICY_ID,
    REQUIRED_EXCLUSION_FIELDS,
    REVIEWER_ID,
)
from subject import MUTANTS, run_corpus

OVERCLAIM = "overclaim:score-published-without-exclusion-count"
UNJUSTIFIED = "unjustified-exclusion"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def validate_exclusion(
    row: dict[str, Any],
    *,
    author_id: str,
    measured: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(row, dict):
        return [f"{UNJUSTIFIED}:not-an-object"]
    for field in REQUIRED_EXCLUSION_FIELDS:
        if field not in row or row.get(field) in (None, ""):
            errors.append(f"{UNJUSTIFIED}:missing-field:{field}")
    mid = str(row.get("mutant_id") or "")
    just = str(row.get("justification") or "")
    reviewer = str(row.get("reviewer_id") or "")
    operator = str(row.get("operator") or "")
    if just:
        if len(just) < MIN_JUSTIFICATION_CHARS:
            errors.append(f"{UNJUSTIFIED}:justification-too-short")
        if _norm(just) in BOILERPLATE_JUSTIFICATIONS:
            errors.append(f"{UNJUSTIFIED}:boilerplate-justification")
    if reviewer and reviewer == author_id:
        errors.append(f"{UNJUSTIFIED}:reviewer-is-author")
    if operator and operator not in ESTATE_OPERATORS:
        errors.append(f"{UNJUSTIFIED}:unknown-operator:{operator}")
    if measured is not None:
        by_id = {m["mutant_id"]: m for m in measured.get("mutants") or []}
        hit = by_id.get(mid)
        if hit is None:
            errors.append(f"{UNJUSTIFIED}:unknown-mutant:{mid}")
        elif not hit.get("oracle_identical"):
            errors.append(
                f"{UNJUSTIFIED}:oracle-distinguishes:{mid}:"
                + ",".join(hit.get("diverged_oracles") or [])
            )
        elif hit.get("operator") != operator and operator:
            errors.append(f"{UNJUSTIFIED}:operator-mismatch:{mid}")
    return errors


def proposed_exclusions(
    measured: dict[str, Any], reviewer_id: str
) -> list[dict[str, Any]]:
    out = []
    for row in measured["mutants"]:
        if not row["oracle_identical"]:
            continue
        spec = MUTANTS[row["mutant_id"]]
        just = spec["justification"]
        if not just:
            continue
        out.append(
            {
                "mutant_id": row["mutant_id"],
                "operator": row["operator"],
                "location": row["location"],
                "justification": just,
                "reviewer_id": reviewer_id,
                "oracle_identical": True,
            }
        )
    return out


def publish_score(
    measured: dict[str, Any],
    exclusions: list[dict[str, Any]],
    *,
    author_id: str = AUTHOR_ID,
    omit_exclusion_count: bool = False,
    override_exclusion_count: int | None = None,
) -> dict[str, Any]:
    """Build a score record. Failures are listed in `errors`; never silent."""
    errors: list[str] = []
    for i, row in enumerate(exclusions):
        for err in validate_exclusion(row, author_id=author_id, measured=measured):
            errors.append(f"exclusions[{i}]:{err}")

    accepted: list[dict[str, Any]] = []
    if not errors:
        accepted = list(exclusions)

    killed_ids = set(measured["oracle_killed"])
    excluded_ids = {str(r["mutant_id"]) for r in accepted}
    remaining_ids = [
        m["mutant_id"]
        for m in measured["mutants"]
        if m["mutant_id"] not in excluded_ids
    ]
    killed_remaining = [mid for mid in remaining_ids if mid in killed_ids]
    surviving = [mid for mid in remaining_ids if mid not in killed_ids]
    denom = len(remaining_ids)
    score = (len(killed_remaining) / denom) if denom else None

    record: dict[str, Any] = {
        "policy_id": POLICY_ID,
        "total": int(measured["total"]),
        "killed": len(killed_remaining),
        "killed_ids": killed_remaining,
        "surviving_ids": surviving,
        "surviving": len(surviving),
        "exclusions": accepted if not errors else exclusions,
        "mutation_score": score,
        "denominator": denom,
        "formula": "killed / (total - exclusion_count)",
        "errors": errors,
        "accepted": not errors,
    }
    count = (
        override_exclusion_count
        if override_exclusion_count is not None
        else len(accepted if not errors else exclusions)
    )
    if not omit_exclusion_count:
        record["exclusion_count"] = count
        if count != len(exclusions):
            record["errors"].append(
                "overclaim:exclusion-count-mismatch"
                f":declared={count}:list={len(exclusions)}"
            )
            record["accepted"] = False
    else:
        record["errors"].append(OVERCLAIM)
        record["accepted"] = False
    return record


def check_published_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["published-record:not-an-object"]
    if "exclusion_count" not in record:
        errors.append(OVERCLAIM)
    if "mutation_score" not in record:
        errors.append("overclaim:score-missing")
    if "total" not in record:
        errors.append("overclaim:total-missing")
    declared = record.get("exclusion_count")
    excl = record.get("exclusions")
    if isinstance(excl, list) and declared is not None and declared != len(excl):
        errors.append("overclaim:exclusion-count-mismatch")
    for i, row in enumerate(excl or []):
        if not isinstance(row, dict):
            errors.append(f"exclusions[{i}]:not-an-object")
            continue
        for field in REQUIRED_EXCLUSION_FIELDS:
            if not row.get(field):
                errors.append(
                    f"exclusions[{i}]:{UNJUSTIFIED}:missing-field:{field}"
                )
    errors.extend(record.get("errors") or [])
    seen: set[str] = set()
    out: list[str] = []
    for err in errors:
        if err not in seen:
            seen.add(err)
            out.append(err)
    return out


def detector_controls(measured: dict[str, Any] | None = None) -> dict[str, Any]:
    measured = measured or run_corpus()
    clean_exclusions = proposed_exclusions(measured, REVIEWER_ID)
    clean = publish_score(measured, clean_exclusions)

    omitted = publish_score(
        measured, clean_exclusions, omit_exclusion_count=True
    )
    omitted_errors = check_published_record(omitted)

    boiler = publish_score(
        measured,
        [
            {
                "mutant_id": "M-EQ-LF-CRLF",
                "operator": "lf-crlf-flip",
                "location": "subject.write_lines",
                "justification": "equivalent",
                "reviewer_id": REVIEWER_ID,
            }
        ],
    )
    false_score = publish_score(
        measured,
        [
            {
                "mutant_id": "M-KILL-SENTINEL",
                "operator": "sentinel-deletion",
                "location": "subject.payload",
                "justification": (
                    "Claimed equivalent because the trailer still parses; this "
                    "is the classic game: exclude a killable mutant to inflate "
                    "the score. The oracle pack must reject it."
                ),
                "reviewer_id": REVIEWER_ID,
            }
        ],
    )
    missing_rev = publish_score(
        measured,
        [
            {
                "mutant_id": "M-EQ-PATH-SEP",
                "operator": "path-separator-flip",
                "location": "subject.join",
                "justification": (
                    "Path separators are normalized by the estate path "
                    "consumer before any observer sees them, so backslash "
                    "versus slash is identical on the published oracle pack."
                ),
                "reviewer_id": "",
            }
        ],
    )
    self_rev = publish_score(
        measured,
        [
            {
                "mutant_id": "M-EQ-MENTION",
                "operator": "use-vs-mention-swap",
                "location": "subject.mention",
                "justification": (
                    "Only a commented mention changes; the returned 'ok' is "
                    "the sole oracle observation, so this is mention-not-use "
                    "and is semantically identical on the pack."
                ),
                "reviewer_id": AUTHOR_ID,
            }
        ],
    )

    planted_fired = (
        OVERCLAIM in omitted_errors
        and not boiler["accepted"]
        and not false_score["accepted"]
        and not missing_rev["accepted"]
        and not self_rev["accepted"]
    )
    clean_errors = check_published_record(clean)
    clean_silent = bool(clean["accepted"]) and not clean_errors

    return {
        "measured": measured,
        "clean": clean,
        "planted": {
            "score_without_exclusion_count": {
                "accepted": omitted["accepted"],
                "errors": omitted_errors,
            },
            "boilerplate_justification": {
                "accepted": boiler["accepted"],
                "errors": boiler["errors"],
            },
            "false_equivalent_sentinel": {
                "accepted": false_score["accepted"],
                "errors": false_score["errors"],
            },
            "missing_reviewer": {
                "accepted": missing_rev["accepted"],
                "errors": missing_rev["errors"],
            },
            "reviewer_is_author": {
                "accepted": self_rev["accepted"],
                "errors": self_rev["errors"],
            },
        },
        "planted_fired": planted_fired,
        "clean_silent": clean_silent,
    }


# Names used by emit.py / probes.
detector_controls = detector_controls
proposed_exclusions = proposed_exclusions
publish_score = publish_score
check_published_record = check_published_record
