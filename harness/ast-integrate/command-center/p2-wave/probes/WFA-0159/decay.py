"""Time-decay revalidation that demotes an adoption when its upstream changes.

WFA-0159: an archived or relicensed upstream demotes the candidate to
UNKNOWN-NEEDS-PROBE. An unchanged upstream must not. An unreachable
upstream is UNKNOWN, never still-fine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from clock import clock_stale

ADOPT_CLASSES = frozenset({"ADOPT-AS-IS", "ADOPT-WITH-WRAPPER"})
DEMOTE_CLASS = "UNKNOWN-NEEDS-PROBE"
DEMOTE_SIGNAL = "UPSTREAM_DRIFT_OR_CLOCK_DECAY"

KEEP = "KEEP"
DEMOTE = "DEMOTE"
UNKNOWN = "UNKNOWN"

INTERVALS_SEC = {
    "git-default-branch": 30 * 86400,
    "github-release": 14 * 86400,
    "package-registry": 14 * 86400,
    "marketplace-index": 7 * 86400,
    "documentation": 90 * 86400,
    "unknown": 7 * 86400,
}

_LICENSE_ALIASES = {
    "MIT": "MIT",
    "MIT LICENSE": "MIT",
    "APACHE-2.0": "APACHE-2.0",
    "APACHE 2.0": "APACHE-2.0",
    "APACHE LICENSE 2.0": "APACHE-2.0",
    "BSD-3-CLAUSE": "BSD-3-CLAUSE",
    "BSD-2-CLAUSE": "BSD-2-CLAUSE",
    "GPL-3.0": "GPL-3.0",
    "GPL-3.0-ONLY": "GPL-3.0",
    "GPL-3.0-OR-LATER": "GPL-3.0-OR-LATER",
    "AGPL-3.0": "AGPL-3.0",
    "MPL-2.0": "MPL-2.0",
    "ISC": "ISC",
    "UNLICENSE": "UNLICENSE",
    "CC0-1.0": "CC0-1.0",
}

_UNKNOWN_LICENSES = frozenset(
    {"", "NONE", "UNKNOWN", "NOASSERTION", "OTHER", "UNLICENSED", "PROPRIETARY-UNKNOWN"}
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(now: Optional[datetime] = None) -> str:
    dt = now or utcnow()
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def interval_for(candidate: dict) -> int:
    sc = str(candidate.get("source_class") or "unknown")
    return int(INTERVALS_SEC.get(sc, INTERVALS_SEC["unknown"]))


def normalize_license(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    text = str(value).strip().upper()
    if text in _UNKNOWN_LICENSES:
        return "UNKNOWN"
    return _LICENSE_ALIASES.get(text, text)


def license_changed(adopted: Any, live: Any) -> Optional[str]:
    a = normalize_license(adopted)
    b = normalize_license(live)
    if a == b:
        return None
    if a != "UNKNOWN" and b == "UNKNOWN":
        return "LICENSE_UNCONFIRMED"
    if a == "UNKNOWN":
        return None
    return "RELICENSED"


def version_drift(adopted: Any, live: Any) -> bool:
    if adopted in (None, "") or live in (None, ""):
        return False
    return str(adopted).strip() != str(live).strip()


def live_is_ok(live: Optional[dict]) -> bool:
    return isinstance(live, dict) and live.get("ok") is True


def revalidate(
    candidate: dict,
    live: Optional[dict],
    now: Optional[datetime] = None,
) -> dict:
    """Compare an adoption snapshot to a live upstream read.

    Unreachable upstream is UNKNOWN, never still-fine.
    """
    now = now or utcnow()
    classification = str(candidate.get("classification") or "")
    adopted = candidate.get("adopted") if isinstance(candidate.get("adopted"), dict) else {}
    interval = interval_for(candidate)
    base = {
        "id": candidate.get("id"),
        "classification": classification,
        "interval_seconds": interval,
        "fetch_date": (live or {}).get("fetch_date") if isinstance(live, dict) else None,
        "upstream_url": (live or {}).get("url") if isinstance(live, dict) else candidate.get("upstream_url"),
        "demotion_signal": DEMOTE_SIGNAL,
        "demote_to": DEMOTE_CLASS,
    }
    if not live_is_ok(live):
        status = None
        if isinstance(live, dict):
            status = live.get("http_status")
        return {
            **base,
            "verdict": UNKNOWN,
            "reasons": ["UNREACHABLE"],
            "new_classification": DEMOTE_CLASS,
            "note": "unreachable upstream is UNKNOWN, never still-fine",
            "http_status": status,
        }

    reasons: list[str] = []
    if bool(live.get("archived")) and not bool(adopted.get("archived")):
        reasons.append("ARCHIVED")
    lic = license_changed(adopted.get("license"), live.get("license"))
    if lic:
        reasons.append(lic)
    if version_drift(adopted.get("version"), live.get("version")):
        reasons.append("VERSION_DRIFT")
    validated_at = adopted.get("validated_at")
    if clock_stale(validated_at, interval, now):
        reasons.append("CLOCK_DECAY")

    if reasons:
        return {
            **base,
            "verdict": DEMOTE,
            "reasons": reasons,
            "new_classification": DEMOTE_CLASS,
            "note": (
                "UPSTREAM_DRIFT_OR_CLOCK_DECAY demotes the adoption to "
                "UNKNOWN-NEEDS-PROBE"
            ),
            "http_status": live.get("http_status"),
        }
    return {
        **base,
        "verdict": KEEP,
        "reasons": [],
        "new_classification": classification,
        "note": "unchanged upstream within revalidation interval; adoption holds",
        "http_status": live.get("http_status"),
    }


def apply_relative_validated_at(candidate: dict, now: datetime) -> dict:
    """Materialize validated_at from validated_at_offset_seconds if present."""
    out = dict(candidate)
    adopted = dict(out.get("adopted") or {})
    if "validated_at_offset_seconds" in adopted and not adopted.get("validated_at"):
        offset = int(adopted["validated_at_offset_seconds"])
        stamp = datetime.fromtimestamp(now.timestamp() - offset, tz=timezone.utc)
        adopted["validated_at"] = iso(stamp)
    out["adopted"] = adopted
    return out
