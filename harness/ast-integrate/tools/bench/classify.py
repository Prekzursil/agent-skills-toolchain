"""Classify benchmark calls as hermetic or a live-source class (TST-0303).

The class is derived from the hosts a case actually contacted while it ran
under ``bench.observe.NetworkObserver``. Loopback traffic does not count as
live. A case that contacts no non-loopback host is hermetic.
"""
from __future__ import annotations

from typing import Any

from bench.observe import is_loopback_host

HERMETIC = "hermetic"
UNKNOWN_LIVE = "unknown-live"

# Ordered: the first rule whose host suffix matches wins.
HOST_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("advisory-db", ("nvd.nist.gov", "osv.dev", "api.osv.dev", "github.com/advisories")),
    ("marketplace-index", ("marketplace.visualstudio.com", "open-vsx.org")),
    ("model-endpoint", ("api.anthropic.com", "api.openai.com", "generativelanguage.googleapis.com")),
    ("package-registry", ("pypi.org", "files.pythonhosted.org", "registry.npmjs.org", "crates.io")),
    ("http-origin", ()),
)


def class_for_host(host: str, url: str = "") -> str:
    h = str(host or "").strip().lower().rstrip(".")
    blob = f"{h} {str(url or '').lower()}"
    for cls, needles in HOST_CLASSES:
        for needle in needles:
            if h == needle or h.endswith("." + needle) or needle in blob:
                return cls
    return UNKNOWN_LIVE


def live_hosts(calls: list[dict[str, Any]] | None) -> list[str]:
    hosts: list[str] = []
    for call in calls or []:
        host = str(call.get("host") or "").strip().lower().rstrip(".")
        if not host or is_loopback_host(host):
            continue
        if host not in hosts:
            hosts.append(host)
    return hosts


def classify_call_rows(calls: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Per-call classification rows (kept for callers that want the detail)."""
    rows = []
    for call in calls or []:
        host = str(call.get("host") or "")
        url = str(call.get("url") or "")
        if not host or is_loopback_host(host) or url.startswith("file:"):
            rows.append({"call": call, "class": HERMETIC})
        else:
            rows.append({"call": call, "class": class_for_host(host, url)})
    return rows


def classify_calls(calls: list[dict[str, Any]] | None = None) -> str:
    """Observed class of a case from its recorded network calls.

    Hermetic when no non-loopback host was contacted. Otherwise the most
    specific live class among the contacted hosts; advisory databases rank
    above generic origins so a single NVD hit makes the case advisory-db.
    """
    classes: list[str] = []
    for row in classify_call_rows(calls):
        if row["class"] != HERMETIC and row["class"] not in classes:
            classes.append(row["class"])
    if not classes:
        return HERMETIC
    order = [cls for cls, _ in HOST_CLASSES] + [UNKNOWN_LIVE]
    classes.sort(key=lambda c: order.index(c) if c in order else len(order))
    return classes[0]
