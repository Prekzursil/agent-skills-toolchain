"""Advisory interval engine + install gate."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from marketplace.version import cmp_version


class OpenEndedUndisclosedError(ValueError):
    pass


@dataclass
class Advisory:
    identifier: str
    package: str
    affected_version_ranges: list[dict[str, str]]
    unbounded_future_disclosed: bool = False
    fixed_version: str | None = None
    severity: str = ""
    references: list[str] = field(default_factory=list)


@dataclass
class InstallVerdict:
    affected: bool
    installable: bool
    open_ended_hits: bool = False
    notes: list[str] = field(default_factory=list)


def from_record(rec: dict[str, Any]) -> Advisory:
    ranges = list(rec.get("affected_version_ranges") or [])
    unbounded = bool(rec.get("unbounded_future_disclosed"))
    has_intro = any(isinstance(r, dict) and r.get("introduced") and not r.get("fixed") for r in ranges)
    has_fixed = any(isinstance(r, dict) and r.get("fixed") and not r.get("introduced") for r in ranges)
    has_complete = any(isinstance(r, dict) and r.get("introduced") and r.get("fixed") for r in ranges)
    has_open = has_intro and not has_fixed and not has_complete
    if has_open and not unbounded:
        raise OpenEndedUndisclosedError("open-ended range must set unbounded_future_disclosed")
    return Advisory(
        identifier=str(rec.get("identifier") or rec.get("id") or ""),
        package=str(rec.get("package") or ""),
        affected_version_ranges=ranges,
        unbounded_future_disclosed=unbounded,
        fixed_version=rec.get("fixed_version"),
        severity=str(rec.get("severity") or ""),
        references=list(rec.get("references") or []),
    )


def _in_interval(version: str, rng: dict[str, str]) -> bool:
    introduced = rng.get("introduced")
    fixed = rng.get("fixed")
    if introduced and cmp_version(version, introduced) < 0:
        return False
    if fixed and cmp_version(version, fixed) >= 0:
        return False
    return True


def is_affected(adv: Advisory, version: str) -> bool:
    ranges = adv.affected_version_ranges
    if not ranges:
        return False
    # Pair introduced/fixed events if they are split records.
    intro = None
    fixed = None
    paired: list[dict[str, str]] = []
    for rng in ranges:
        if not isinstance(rng, dict):
            continue
        if "introduced" in rng and "fixed" in rng:
            paired.append(rng)
            continue
        if rng.get("introduced") and not rng.get("fixed"):
            intro = rng.get("introduced")
        if rng.get("fixed") and not rng.get("introduced"):
            fixed = rng.get("fixed")
    if intro or fixed:
        rec: dict[str, str] = {}
        if intro:
            rec["introduced"] = intro
        if fixed:
            rec["fixed"] = fixed
        paired.append(rec)
    if not paired:
        paired = [r for r in ranges if isinstance(r, dict)]
    return any(_in_interval(version, r) for r in paired)


def evaluate_installed(package: str, version: str, advisories: list[Advisory]) -> InstallVerdict:
    notes: list[str] = []
    affected = False
    open_hits = False
    for adv in advisories:
        if adv.package != package:
            continue
        if is_affected(adv, version):
            affected = True
            if adv.unbounded_future_disclosed and any(
                isinstance(r, dict) and r.get("introduced") and not r.get("fixed")
                for r in adv.affected_version_ranges
            ):
                open_hits = True
                notes.append("unbounded-future-disclosed")
    return InstallVerdict(
        affected=affected,
        installable=not affected,
        open_ended_hits=open_hits,
        notes=notes,
    )
