#!/usr/bin/env python3
"""On-demand per-key usage lookups for the search-hub rotator (stdlib only).

Each function queries ONE provider's usage endpoint with the SAME API key the
search server uses (Bearer auth) and returns a normalized dict::

    {"provider", "label", "remaining", "spend", "note", "ok", "error"}

* Firecrawl -- ``GET /v2/team/credit-usage`` -> ``data.remainingCredits``.
* Tavily    -- ``GET /usage`` -> remaining = (plan_limit - plan_usage) plus any
  pay-as-you-go headroom (paygo_limit - paygo_usage).
* Exa       -- NO per-key balance API (a spend figure needs a separate admin/
  service key + key-id), so this is ``remaining: None`` with an "error-driven"
  note; Exa rotation is purely reactive on its 402 tags.

The blocking HTTP call is injected (``getter``) so every parser is unit-testable
with canned ``(status, json, raw)`` triples -- no network, no live key. Never
raises: a transport/parse failure comes back as ``ok=False`` with an ``error``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

# getter(url, key, timeout) -> (http_status, parsed_json_or_None, raw_text)
Getter = Callable[[str, str, float], "tuple[int, dict | None, str]"]

FIRECRAWL_USAGE_URL = "https://api.firecrawl.dev/v2/team/credit-usage"
TAVILY_USAGE_URL = "https://api.tavily.com/usage"
DEFAULT_TIMEOUT = 10.0


def _default_getter(url: str, key: str, timeout: float) -> tuple[int, dict | None, str]:
    """Real Bearer GET returning (status, parsed-json-or-None, raw-body). Safe."""
    req = urllib.request.Request(  # noqa: S310 (https literal URLs only)
        url,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status = resp.getcode() or 0
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, None, f"request failed: {exc}"
    try:
        return status, json.loads(raw), raw
    except (json.JSONDecodeError, ValueError):
        return status, None, raw


def _result(provider: str, label: str, **extra) -> dict:
    base = {
        "provider": provider,
        "label": label,
        "remaining": None,
        "spend": None,
        "note": "",
        "ok": True,
        "error": None,
    }
    base.update(extra)
    return base


def _as_number(value) -> float | None:
    return (
        value
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


def firecrawl_usage(key: str, label: str = "", getter: Getter | None = None) -> dict:
    """Remaining Firecrawl credits for ``key`` (data.remainingCredits)."""
    get = getter or _default_getter
    status, body, raw = get(FIRECRAWL_USAGE_URL, key, DEFAULT_TIMEOUT)
    if body is None:
        return _result(
            "firecrawl", label, ok=False, error=f"HTTP {status}: {raw[:200]}"
        )
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    remaining = _as_number(data.get("remainingCredits"))
    return _result(
        "firecrawl",
        label,
        remaining=remaining,
        note="remainingCredits from /v2/team/credit-usage",
    )


def tavily_usage(key: str, label: str = "", getter: Getter | None = None) -> dict:
    """Remaining Tavily allowance = plan headroom + pay-as-you-go headroom."""
    get = getter or _default_getter
    status, body, raw = get(TAVILY_USAGE_URL, key, DEFAULT_TIMEOUT)
    if body is None:
        return _result("tavily", label, ok=False, error=f"HTTP {status}: {raw[:200]}")
    account = body.get("account") if isinstance(body.get("account"), dict) else {}
    remaining = _tavily_remaining(account)
    return _result(
        "tavily",
        label,
        remaining=remaining,
        note="plan_limit-plan_usage (+paygo headroom) from /usage",
    )


def _tavily_remaining(account: dict) -> float | None:
    """(plan_limit - plan_usage) + (paygo_limit - paygo_usage); None if no cap."""
    plan_limit = _as_number(account.get("plan_limit"))
    plan_usage = _as_number(account.get("plan_usage")) or 0
    if plan_limit is None:
        return None  # no plan cap advertised -> treat as unmetered
    remaining = plan_limit - plan_usage
    paygo_limit = _as_number(account.get("paygo_limit"))
    paygo_usage = _as_number(account.get("paygo_usage")) or 0
    if paygo_limit is not None:
        remaining += paygo_limit - paygo_usage
    return remaining


def exa_usage(key: str = "", label: str = "") -> dict:
    """Exa has no per-key balance API -> report error-driven (no probe)."""
    return _result(
        "exa",
        label,
        remaining=None,
        note="error-driven (no balance API); rotates reactively on 402 "
        "NO_MORE_CREDITS / API_KEY_BUDGET_EXCEEDED",
    )


def usage_for(
    usage_kind: str, key: str, label: str = "", getter: Getter | None = None
) -> dict:
    """Dispatch to the right usage lookup by provider ``usage_kind``."""
    if usage_kind == "firecrawl":
        return firecrawl_usage(key, label, getter)
    if usage_kind == "tavily":
        return tavily_usage(key, label, getter)
    return exa_usage(key, label)
