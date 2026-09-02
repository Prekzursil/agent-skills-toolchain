"""Exact roster resolution and capability negotiation.

Exact named seats that are not reachable are REFUSED. A LOUD degradation
record is mandatory. Same-vendor substitution is forbidden, silent or loud.
"""
from __future__ import annotations

from typing import Any

LOUD = "LOUD"
REFUSE_SEAT = "REFUSE-SEAT"


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _requested(seat: dict) -> dict:
    return {
        "id": seat.get("id"),
        "vendor": _norm(seat.get("vendor")),
        "model": _norm(seat.get("model")),
        "transport": _norm(seat.get("transport")),
        "role": _norm(seat.get("role")),
    }


def _entries(estate: dict) -> list[dict]:
    rows = estate.get("reachable_entries")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def find_exact(seat: dict, estate: dict) -> dict | None:
    want = _requested(seat)
    for entry in _entries(estate):
        if _norm(entry.get("vendor")) != want["vendor"]:
            continue
        if _norm(entry.get("model")) != want["model"]:
            continue
        need_t = want["transport"]
        have_t = _norm(entry.get("transport"))
        if need_t and have_t != need_t:
            continue
        return entry
    return None


def same_vendor_options(seat: dict, estate: dict) -> list[dict]:
    vendor = _requested(seat)["vendor"]
    out = []
    for entry in _entries(estate):
        if _norm(entry.get("vendor")) == vendor:
            out.append(
                {
                    "vendor": _norm(entry.get("vendor")),
                    "model": _norm(entry.get("model")),
                    "transport": _norm(entry.get("transport")),
                }
            )
    return out


def unmet_reason(seat: dict, estate: dict) -> str:
    want = _requested(seat)
    vendors = estate.get("vendors") or {}
    row = vendors.get(want["vendor"] or "") or {}
    mcp = estate.get("mcp_inventory") or {}
    session = estate.get("session") or {}
    if want["transport"] == "in-session":
        if session.get("vendor") != want["vendor"] or session.get("model_id") != want["model"]:
            return (
                "in-session-mismatch: session vendor="
                + str(session.get("vendor"))
                + " model="
                + str(session.get("model_id"))
            )
    if want["transport"] and want["transport"].startswith("mcp:"):
        server = want["transport"].split(":", 1)[-1]
        names = [n.lower() for n in (mcp.get("server_names") or [])]
        if server.lower() not in names and not any(server.lower() in n for n in names):
            return f"mcp-server-unmounted:{server}"
    cred = row.get("credential") or {}
    if not cred.get("present"):
        return f"credential-absent:{want['vendor']}"
    if row.get("reachable") is False:
        auth = row.get("http_authenticated_models") or {}
        return f"vendor-not-reachable:auth={auth.get('error') or auth.get('status')}"
    options = same_vendor_options(seat, estate)
    if options:
        return "exact-model-not-in-reachable-inventory"
    return "exact-seat-unmatched"


def negotiate(spec: dict, estate: dict, degradations: list[dict], seated: list[dict]) -> dict:
    requested = [_requested(s) for s in spec.get("seats") or []]
    available = [
        {
            "vendor": _norm(e.get("vendor")),
            "model": _norm(e.get("model")),
            "transport": _norm(e.get("transport")),
        }
        for e in _entries(estate)
    ]
    intersection = []
    for seat in requested:
        if find_exact(seat, estate):
            intersection.append(seat)
    return {
        "requested": requested,
        "available": available,
        "intersection": intersection,
        "gaps": [d.get("requested") for d in degradations],
        "seated_ids": [s.get("id") for s in seated],
    }


def resolve_exact(spec: dict, estate: dict) -> dict:
    mode = spec.get("roster_mode") or "exact"
    if mode != "exact":
        raise ValueError("CNL-0012 resolver implements roster_mode=exact only")
    degradations: list[dict] = []
    would_have: list[dict] = []
    for seat in spec.get("seats") or []:
        match = find_exact(seat, estate)
        if match:
            would_have.append(
                {
                    **_requested(seat),
                    "resolved_from": match.get("source"),
                    "resolved_transport": _norm(match.get("transport")),
                }
            )
            continue
        want = _requested(seat)
        degradations.append(
            {
                "seat_id": want["id"],
                "class": LOUD,
                "action": REFUSE_SEAT,
                "reason": unmet_reason(seat, estate),
                "requested": want,
                "available_same_vendor": same_vendor_options(seat, estate),
                "substituted": False,
            }
        )
    decision = "SEATED" if not degradations else "REFUSED"
    seated = would_have if decision == "SEATED" else []
    return {
        "decision": decision,
        "roster_mode": "exact",
        "seated": seated,
        "would_have_seated": would_have,
        "degradations": degradations,
        "silent_substitution": False,
        "capability_negotiation": negotiate(spec, estate, degradations, seated),
    }


def silent_substitution_violations(spec: dict, result: dict) -> list[str]:
    """Return violation ids. Empty means the check is silent (known-good)."""
    violations: list[str] = []
    seated = {s.get("id"): s for s in (result.get("seated") or []) if isinstance(s, dict)}
    degs = {
        d.get("seat_id"): d
        for d in (result.get("degradations") or [])
        if isinstance(d, dict)
    }
    for seat in spec.get("seats") or []:
        want = _requested(seat)
        got = seated.get(want["id"])
        deg = degs.get(want["id"])
        if got:
            same = (
                _norm(got.get("vendor")) == want["vendor"]
                and _norm(got.get("model")) == want["model"]
            )
            if not same:
                if _norm(got.get("vendor")) == want["vendor"]:
                    violations.append(f"same-vendor-substitution:{want['id']}")
                else:
                    violations.append(f"cross-vendor-substitution:{want['id']}")
                if not deg or deg.get("class") != LOUD:
                    violations.append(f"silent-substitution:{want['id']}")
        else:
            if not deg or deg.get("class") != LOUD:
                violations.append(f"unseated-without-loud-record:{want['id']}")
            elif deg.get("substituted") is True:
                violations.append(f"degradation-claims-substitution:{want['id']}")
    if result.get("silent_substitution") is True:
        violations.append("result-flag-silent-substitution")
    return violations


def planted_silent_same_vendor_substitution(spec: dict) -> dict:
    """Negative-control payload: seat a different same-vendor model with no record."""
    seated = []
    for seat in spec.get("seats") or []:
        want = _requested(seat)
        model = want["model"] or "unknown"
        swapped = model
        if "opus" in model:
            swapped = model.replace("opus", "sonnet")
        elif "sonnet" in model:
            swapped = model.replace("sonnet", "haiku")
        else:
            swapped = model + "-substitute"
        seated.append(
            {
                "id": want["id"],
                "vendor": want["vendor"],
                "model": swapped,
                "transport": want["transport"],
                "role": want["role"],
            }
        )
    return {
        "decision": "SEATED",
        "roster_mode": "exact",
        "seated": seated,
        "would_have_seated": seated,
        "degradations": [],
        "silent_substitution": True,
        "capability_negotiation": {},
        "planted": True,
    }
