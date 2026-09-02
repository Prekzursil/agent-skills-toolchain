#!/usr/bin/env python3
"""CNL-0024: veto scope, override path, and abuse detection.

A veto is a RIGHT (CNL-0022 trichotomy used locally): once granted, a valid
in-scope exercise cannot be denied by stripping the right mid-council.
Scope is not unlimited. Abuse is not "vetoed more than once".

Named discriminator
-------------------
``pretext_veto_count``: number of *accepted* vetoes whose cited invariant is
NOT among the object's actual ``violations``.

A consistent principled dissenter cites an invariant that actually holds on
every object they block, and files a minority report. A serial vetoer cites
an invariant that does not hold (pretext), often the same noble phrase on
unrelated objects. Raw veto *count* is not the discriminator: the principled
fixture vetoes as often as the serial one.

Fire rule: abuse FIRES iff pretext_veto_count >= 2.
SILENT when pretext_veto_count == 0 (including unused veto rights).

Independent recount (second signal): walk the log and recompute
``cited_invariant in object.violations`` without reading the engine's
``abuse`` / ``pretext`` fields.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any  # noqa: F401

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

ALLOWED_SCOPES = frozenset({"option", "decision"})
REJECTED_SCOPES = frozenset({"council"})

# cited invariant id -> violation token that must appear on the object
INVARIANT_VIOLATION = {
    "preserve-minority-report": "dropped-minority-report",
    "no-secret-exfiltration": "secret-exfiltration",
    "role-mandate-enforced": "unenforced-role",
}

PRETEXT_FIRE_THRESHOLD = 2
OVERRIDE_NUMERATOR = 2
OVERRIDE_DENOMINATOR = 3


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture(name: str) -> dict[str, Any]:
    return load_json(FIX / name)


def object_sha256(obj: dict[str, Any]) -> str:
    blob = json.dumps(
        {
            "id": obj.get("id"),
            "kind": obj.get("kind"),
            "class": obj.get("class"),
            "violations": sorted(obj.get("violations") or []),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def invariant_holds(obj: dict[str, Any], invariant_id: str) -> bool:
    token = INVARIANT_VIOLATION.get(str(invariant_id))
    if token is None:
        return False
    return token in list(obj.get("violations") or [])


def seat_map(council: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(s["id"]): s for s in (council.get("seats") or [])}


def has_right(seat: dict[str, Any] | None, right: str) -> bool:
    if not seat:
        return False
    return right in [str(r) for r in (seat.get("rights") or [])]


def other_eligible(council: dict[str, Any], accused: str) -> list[str]:
    out = []
    for seat in council.get("seats") or []:
        sid = str(seat["id"])
        if sid == accused:
            continue
        rights = [str(r) for r in (seat.get("rights") or [])]
        if "vote" in rights or "veto" in rights:
            out.append(sid)
    return out


def apply_veto(
    council: dict[str, Any],
    objects: dict[str, dict[str, Any]],
    exercise: dict[str, Any],
    prior_log: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attempt one veto. Never mutates council; caller applies effects."""
    prior_log = prior_log or []
    seats = seat_map(council)
    seat_id = str(exercise.get("seat") or "")
    scope = str(exercise.get("scope") or "")
    object_id = str(exercise.get("object_id") or "")
    cited = str(exercise.get("cited_invariant") or "")
    obj = objects.get(object_id)
    seat = seats.get(seat_id)
    report = exercise.get("minority_report")
    has_report = isinstance(report, dict) and bool(str(report.get("body") or "").strip())

    base = {
        "seat": seat_id,
        "scope": scope,
        "object_id": object_id,
        "cited_invariant": cited,
        "has_minority_report": has_report,
        "object_sha256": object_sha256(obj) if obj else None,
        "effect": None,
    }

    if not has_right(seat, "veto"):
        return {**base, "status": "unauthorized", "pretext": None, "reason": "no-veto-right"}
    if scope in REJECTED_SCOPES or scope not in ALLOWED_SCOPES:
        return {
            **base,
            "status": "invalid_scope",
            "pretext": None,
            "reason": "council-scope-veto-forbidden",
        }
    if obj is None:
        return {**base, "status": "no-object", "pretext": None, "reason": "unknown-object"}

    live_sha = object_sha256(obj)
    for prev in prior_log:
        if (
            prev.get("status") == "overridden"
            and prev.get("seat") == seat_id
            and prev.get("object_sha256") == live_sha
        ):
            return {
                **base,
                "status": "repeat_identical",
                "pretext": None,
                "reason": "re-veto-of-overridden-identical-object",
                "object_sha256": live_sha,
            }

    holds = invariant_holds(obj, cited)
    pretext = not holds
    effect = "remove-option" if scope == "option" else "block-decision"
    return {
        **base,
        "status": "applied",
        "pretext": pretext,
        "reason": "invariant-mismatch" if pretext else "invariant-holds",
        "invariant_holds": holds,
        "effect": effect,
        "object_sha256": live_sha,
        "object_class": obj.get("class"),
        "object_violations": list(obj.get("violations") or []),
    }


def apply_effect(council: dict[str, Any], result: dict[str, Any]) -> None:
    if result.get("status") != "applied":
        return
    oid = result.get("object_id")
    if result.get("scope") == "option":
        feas = [x for x in (council.get("feasible_options") or []) if x != oid]
        council["feasible_options"] = feas
    elif result.get("scope") == "decision":
        po = dict(council.get("proposed_outcome") or {})
        if po.get("id") == oid or oid:
            po["blocked"] = True
            po["blocked_by"] = result.get("seat")
            po["id"] = po.get("id") or oid
            council["proposed_outcome"] = po
    council["status"] = "open"


def recount_pretext(
    log: list[dict[str, Any]],
    objects: dict[str, dict[str, Any]],
    seat_id: str,
) -> dict[str, Any]:
    """Second signal: recompute pretext from cited_invariant vs violations.

    Does not read result['pretext'] or result['abuse'].
    """
    accepted = [
        row
        for row in log
        if row.get("seat") == seat_id and row.get("status") in {"applied", "overridden"}
    ]
    pretext_ids = []
    matched_ids = []
    reports = 0
    for row in accepted:
        obj = objects.get(str(row.get("object_id") or ""))
        cited = str(row.get("cited_invariant") or "")
        holds = bool(obj) and invariant_holds(obj, cited)
        if holds:
            matched_ids.append(row.get("object_id"))
        else:
            pretext_ids.append(row.get("object_id"))
        if row.get("has_minority_report"):
            reports += 1
    pretext_count = len(pretext_ids)
    return {
        "seat": seat_id,
        "accepted": len(accepted),
        "pretext_veto_count": pretext_count,
        "matched_veto_count": len(matched_ids),
        "minority_report_count": reports,
        "pretext_object_ids": pretext_ids,
        "matched_object_ids": matched_ids,
        "abuse": pretext_count >= PRETEXT_FIRE_THRESHOLD,
        "discriminating_feature": "pretext_veto_count",
        "fire_rule": f"pretext_veto_count >= {PRETEXT_FIRE_THRESHOLD}",
        "signal": "invariant-membership-recount",
    }


def classify_seat(
    log: list[dict[str, Any]],
    objects: dict[str, dict[str, Any]],
    seat_id: str,
) -> dict[str, Any]:
    """Engine classification. Uses the applied-row pretext bit as signal 1."""
    accepted = [
        row
        for row in log
        if row.get("seat") == seat_id and row.get("status") in {"applied", "overridden"}
    ]
    pretext_count = sum(1 for row in accepted if row.get("pretext") is True)
    matched = sum(1 for row in accepted if row.get("pretext") is False)
    reports = sum(1 for row in accepted if row.get("has_minority_report"))
    abuse = pretext_count >= PRETEXT_FIRE_THRESHOLD
    return {
        "seat": seat_id,
        "accepted": len(accepted),
        "pretext_veto_count": pretext_count,
        "matched_veto_count": matched,
        "minority_report_count": reports,
        "abuse": abuse,
        "verdict": "ABUSE" if abuse else "SILENT",
        "discriminating_feature": "pretext_veto_count",
        "fire_rule": f"pretext_veto_count >= {PRETEXT_FIRE_THRESHOLD}",
        "signal": "engine-pretext-bit",
    }


def override_veto(
    council: dict[str, Any],
    log: list[dict[str, Any]],
    objects: dict[str, dict[str, Any]],
    veto_index: int,
    supporters: list[str],
    reason: str,
    owner: bool = False,
) -> dict[str, Any]:
    if veto_index < 0 or veto_index >= len(log):
        return {"status": "no-veto", "reason": "index-out-of-range"}
    row = log[veto_index]
    if row.get("status") != "applied":
        return {"status": "not-applied", "reason": str(row.get("status"))}
    accused = str(row.get("seat") or "")
    cls = classify_seat(log, objects, accused)
    if not owner and not cls["abuse"]:
        return {
            "status": "override-refused",
            "reason": "abuse-detector-silent",
            "abuse": False,
        }
    eligible = other_eligible(council, accused)
    support = [s for s in supporters if s in eligible]
    need = (
        (len(eligible) * OVERRIDE_NUMERATOR + OVERRIDE_DENOMINATOR - 1)
        // OVERRIDE_DENOMINATOR
        if eligible
        else 1
    )
    if owner:
        ok = True
        path = "owner-override"
    else:
        ok = len(support) >= need
        path = "supermajority-of-other-eligible-seats"
    if not ok:
        return {
            "status": "override-refused",
            "reason": "short-of-supermajority",
            "supporters": support,
            "need": need,
            "eligible": eligible,
        }
    row["status"] = "overridden"
    row["override"] = {
        "path": path,
        "supporters": support if not owner else ["owner"],
        "reason": reason,
        "need": need,
        "eligible": eligible,
    }
    # Restore the blocked object into play.
    if row.get("scope") == "option":
        feas = list(council.get("feasible_options") or [])
        oid = row.get("object_id")
        if oid and oid not in feas:
            feas.append(oid)
        council["feasible_options"] = feas
    elif row.get("scope") == "decision":
        po = dict(council.get("proposed_outcome") or {})
        po["blocked"] = False
        po.pop("blocked_by", None)
        council["proposed_outcome"] = po
    return {
        "status": "overridden",
        "path": path,
        "supporters": support if not owner else ["owner"],
        "need": need,
        "eligible": eligible,
        "veto_index": veto_index,
    }


def run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    council = copy.deepcopy(fixture["council"])
    objects = copy.deepcopy(fixture["objects"])
    log: list[dict[str, Any]] = []
    for ex in fixture.get("exercises") or []:
        result = apply_veto(council, objects, ex, prior_log=log)
        if result["status"] == "applied":
            apply_effect(council, result)
        log.append(result)
    override_rows = []
    for ov in fixture.get("overrides") or []:
        override_rows.append(
            override_veto(
                council,
                log,
                objects,
                int(ov["veto_index"]),
                list(ov.get("supporters") or []),
                str(ov.get("reason") or ""),
                owner=bool(ov.get("owner")),
            )
        )
    seats = [str(s["id"]) for s in council.get("seats") or []]
    classifications = {sid: classify_seat(log, objects, sid) for sid in seats}
    recounts = {sid: recount_pretext(log, objects, sid) for sid in seats}
    return {
        "fixture_id": fixture.get("id"),
        "council_status": council.get("status"),
        "feasible_options": list(council.get("feasible_options") or []),
        "proposed_outcome": council.get("proposed_outcome"),
        "log": log,
        "overrides": override_rows,
        "classifications": classifications,
        "recounts": recounts,
        "objects": objects,
    }


def target_seat(fixture: dict[str, Any]) -> str:
    return str(fixture.get("target_seat") or "")
