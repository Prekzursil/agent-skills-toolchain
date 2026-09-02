"""Fan-in barrier: typed PARTIAL on 429-blocked units, denominator frozen.

The launched cohort is the denominator. A unit that is HTTP 429-blocked at
the barrier is named on a typed PARTIAL result. Silently dropping blocked
units and reporting "N of N complete" is the contracted failure mode.

``drop_blocked_from_denominator=True`` is the negative-control mutant used
by probe 2; production calls leave it False.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

VERDICT_COMPLETE = "COMPLETE"
VERDICT_PARTIAL = "PARTIAL"
STATUS_COMPLETE = "COMPLETE"
STATUS_429 = "RATE_LIMITED_429"
HTTP_429 = 429

LAUNCH_IDS: tuple[str, ...] = tuple(f"TST-0142-U{i:02d}" for i in range(1, 9))


def is_429(outcome: Mapping[str, Any] | None) -> bool:
    if not isinstance(outcome, Mapping):
        return False
    if int(outcome.get("http_status") or 0) == HTTP_429:
        return True
    status = str(outcome.get("status") or "").upper()
    return status in {STATUS_429, "BLOCKED_429", "429", "HTTP_429"}


def is_complete(outcome: Mapping[str, Any] | None) -> bool:
    if not isinstance(outcome, Mapping):
        return False
    if is_429(outcome):
        return False
    return str(outcome.get("status") or "").upper() == STATUS_COMPLETE


def launch_ids_of(manifest: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in manifest:
        if isinstance(item, Mapping):
            ids.append(str(item.get("id") or item.get("unit_id") or ""))
        else:
            ids.append(str(item))
    if any(not uid for uid in ids):
        raise ValueError("launch manifest contains an empty unit id")
    return ids


def half_blocked_outcomes(ids: list[str] | None = None) -> dict[str, dict[str, Any]]:
    ids = list(ids or LAUNCH_IDS)
    out: dict[str, dict[str, Any]] = {}
    for i, uid in enumerate(ids):
        if i % 2 == 1:
            out[uid] = {"status": STATUS_429, "http_status": HTTP_429}
        else:
            out[uid] = {"status": STATUS_COMPLETE, "http_status": 200}
    return out


def all_complete_outcomes(ids: list[str] | None = None) -> dict[str, dict[str, Any]]:
    ids = list(ids or LAUNCH_IDS)
    return {uid: {"status": STATUS_COMPLETE, "http_status": 200} for uid in ids}


def expected_blocked(outcomes: Mapping[str, Mapping[str, Any]], ids: list[str]) -> list[str]:
    return [uid for uid in ids if is_429(outcomes.get(uid))]


def expected_complete(outcomes: Mapping[str, Mapping[str, Any]], ids: list[str]) -> list[str]:
    return [uid for uid in ids if is_complete(outcomes.get(uid))]


def count_receipts_on_disk(receipt_dir: Path) -> int:
    if not receipt_dir.is_dir():
        return 0
    return len([p for p in receipt_dir.glob("*.json") if p.is_file()])


def write_cohort_receipts(
    receipt_dir: Path,
    launch_ids: list[str],
    outcomes: Mapping[str, Mapping[str, Any]],
) -> int:
    """Write one on-disk receipt per launched id (complete and 429 alike)."""
    if receipt_dir.exists():
        shutil.rmtree(receipt_dir)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    for uid in launch_ids:
        oc = dict(outcomes.get(uid) or {})
        rec = {
            "blocked_429": is_429(oc),
            "http_status": oc.get("http_status"),
            "launched": True,
            "status": oc.get("status"),
            "unit_id": uid,
        }
        (receipt_dir / f"{uid}.json").write_text(
            json.dumps(rec, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return count_receipts_on_disk(receipt_dir)


@dataclass
class FanInResult:
    verdict: str
    launched_count: int
    complete_count: int
    blocked_unit_ids: list[str] = field(default_factory=list)
    complete_unit_ids: list[str] = field(default_factory=list)
    roster: list[str] = field(default_factory=list)
    summary: str = ""
    drop_blocked_from_denominator: bool = False

    @property
    def denominator(self) -> int:
        return self.launched_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked_unit_ids": list(self.blocked_unit_ids),
            "complete_count": self.complete_count,
            "complete_unit_ids": list(self.complete_unit_ids),
            "denominator": self.denominator,
            "drop_blocked_from_denominator": self.drop_blocked_from_denominator,
            "launched_count": self.launched_count,
            "roster": list(self.roster),
            "summary": self.summary,
            "verdict": self.verdict,
        }

    to_dict = to_dict


def fan_in(
    launch_manifest: list[Any],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    drop_blocked_from_denominator: bool = False,
) -> FanInResult:
    """Reduce a launched cohort.

    Production (drop_blocked_from_denominator=False):
      denominator = len(launch_manifest)
      any 429-blocked unit => typed PARTIAL naming every blocked id
      all complete => COMPLETE, same denominator

    Mutant (drop_blocked_from_denominator=True):
      blocked units are filtered out of the denominator and unnamed,
      so a half-blocked cohort reports "N of N complete".
    """
    launched = launch_ids_of(launch_manifest)
    blocked = [uid for uid in launched if is_429(outcomes.get(uid))]
    complete = [uid for uid in launched if is_complete(outcomes.get(uid))]

    if drop_blocked_from_denominator:
        visible = [uid for uid in launched if uid not in blocked]
        n_complete = len([uid for uid in complete if uid in visible])
        denom = len(visible)
        verdict = (
            VERDICT_COMPLETE
            if denom > 0 and n_complete == denom
            else VERDICT_PARTIAL
        )
        return FanInResult(
            verdict=verdict,
            launched_count=denom,
            complete_count=n_complete,
            blocked_unit_ids=[],
            complete_unit_ids=[uid for uid in complete if uid in visible],
            roster=list(visible),
            summary=f"{n_complete} of {denom} complete",
            drop_blocked_from_denominator=True,
        )

    denom = len(launched)
    if blocked:
        verdict = VERDICT_PARTIAL
    elif len(complete) == denom and denom > 0:
        verdict = VERDICT_COMPLETE
    else:
        verdict = VERDICT_PARTIAL
    return FanInResult(
        verdict=verdict,
        launched_count=denom,
        complete_count=len(complete),
        blocked_unit_ids=list(blocked),
        complete_unit_ids=list(complete),
        roster=list(launched),
        summary=f"{len(complete)} of {denom} complete",
        drop_blocked_from_denominator=False,
    )


def contract_errors(
    result: Mapping[str, Any],
    launch_ids: list[str],
    disk_receipt_count: int,
    expected_blocked_ids: list[str],
) -> list[str]:
    """Two independent signals vs the launch manifest and on-disk receipts."""
    errors: list[str] = []
    launched_n = len(launch_ids)
    raw_denom = result.get("denominator")
    if raw_denom is None:
        raw_denom = result.get("launched_count")
    denom = int(raw_denom if raw_denom is not None else -1)
    roster = list(result.get("roster") or [])
    blocked = list(result.get("blocked_unit_ids") or [])
    complete = list(result.get("complete_unit_ids") or [])
    verdict = str(result.get("verdict") or "")
    summary = str(result.get("summary") or "")

    if denom != launched_n:
        errors.append(f"denominator {denom} != launched {launched_n}")
    if roster != list(launch_ids):
        errors.append("roster does not equal launch-manifest ids")
    if set(roster) != set(launch_ids):
        errors.append("roster set does not equal launch-manifest ids")
    if disk_receipt_count != launched_n:
        errors.append(
            f"disk receipt count {disk_receipt_count} != launched {launched_n}"
        )
    if expected_blocked_ids:
        if verdict != VERDICT_PARTIAL:
            errors.append(f"expected typed PARTIAL, got {verdict!r}")
        missing = [uid for uid in expected_blocked_ids if uid not in blocked]
        extra = [uid for uid in blocked if uid not in expected_blocked_ids]
        if missing:
            errors.append(f"unnamed blocked unit ids: {missing}")
        if extra:
            errors.append(f"unexpected blocked unit ids: {extra}")
        n_complete = int(result.get("complete_count") or 0)
        if (
            summary == f"{n_complete} of {n_complete} complete"
            and n_complete != launched_n
        ):
            errors.append(f"shrunken summary {summary!r}")
    else:
        if verdict != VERDICT_COMPLETE:
            errors.append(f"unblocked cohort expected COMPLETE, got {verdict!r}")
        if blocked:
            errors.append(f"unblocked cohort named blocked ids {blocked}")
        if complete != list(launch_ids):
            errors.append("unblocked complete_unit_ids != launch manifest")
        if int(result.get("complete_count") or 0) != launched_n:
            errors.append("unblocked complete_count != launched")
        if summary != f"{launched_n} of {launched_n} complete":
            errors.append(f"unblocked summary {summary!r}")
    return errors


# Aliases used by probes / write_receipts (single implementation).
all_complete_outcomes = all_complete_outcomes
count_receipts_on_disk = count_receipts_on_disk
expected_blocked = expected_blocked
expected_complete = expected_complete
fan_in = fan_in
half_blocked_outcomes = half_blocked_outcomes
