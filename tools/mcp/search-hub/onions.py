#!/usr/bin/env python3
"""Onions-lane envelope guard for the SearXNG provider (index-only, default OFF).

The onion lane is **querying the Ahmia index only**, through the SearXNG provider
the hub already fronts -- NOT a new tool and NOT a new service. This module is the
enforcement point for the hard legal/safety envelope
(``docs/legal/onions-lane-envelope.md``):

* The ``onions`` category / the ``ahmia`` engine on ``searxng_web_search`` is
  offered ONLY when ``ENABLE_ONIONS`` is truthy. Default OFF: a request for that
  category with the flag unset is refused with a truthful error and **not
  forwarded** to any child.
* ``web_url_read`` is **never** allowed to fetch a ``.onion`` URL, flag or no flag
  -- the lane's scope is index metadata (title + indexed snippet + the ``.onion``
  URL as a string), never fetching/rendering/crawling/scraping an onion service.

Everything here is a pure function of the tool name + arguments + the flag, so it
is fully unit-testable with no network, no child, and no SearXNG instance.
"""

from __future__ import annotations

from urllib.parse import urlsplit

ENV_FLAG = "ENABLE_ONIONS"
# Stock SearXNG HARD-GATES the literal ``onions`` category on a working Tor proxy
# (it drops any engine whose categories contain "onions" unless using_tor_proxy is
# true, and probes check.torproject.org at startup). Our envelope forbids Tor, so
# the clearnet Ahmia engine is registered under a NON-"onions" category name
# (``onion index``) and is selected by ``engines=ahmia`` -- see the envelope doc.
# The guard therefore detects onion INTENT broadly: any category token containing
# the substring "onion", or the ahmia engine.
ONION_CATEGORY = "onion index"
# The ONLY onion engine this lane permits: the Ahmia index. Not Evil / Torch are
# deliberately excluded (dead / Tor-only) and any onion engine is index-only here.
ONION_ENGINES = frozenset({"ahmia"})
ENVELOPE_DOC = "docs/legal/onions-lane-envelope.md"


def _truthy(value) -> bool:
    return isinstance(value, str) and value.strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    )


def flag_enabled(environ) -> bool:
    """True iff ENABLE_ONIONS is set to a truthy value (default OFF)."""
    return _truthy(environ.get(ENV_FLAG))


def _csv(value) -> list[str]:
    """Lower-cased tokens from a comma-separated string or a list."""
    if isinstance(value, str):
        return [part.strip().lower() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(part).strip().lower() for part in value if str(part).strip()]
    return []


def requests_onions(arguments: dict) -> bool:
    """True iff the search args select an onion category or the ahmia engine.

    Category detection is by the substring "onion" so it catches the intuitive
    ``onions`` (which stock SearXNG reserves for Tor) AND the clearnet lane's real
    category ``onion index`` -- either way the request is gated.
    """
    args = arguments or {}
    categories = _csv(args.get("categories"))
    engines = _csv(args.get("engines"))
    if any("onion" in token for token in categories):
        return True
    return bool(set(engines) & ONION_ENGINES)


def is_onion_url(url) -> bool:
    """True iff ``url`` points at a ``.onion`` host (envelope: never fetch these)."""
    if not isinstance(url, str) or not url.strip():
        return False
    candidate = url.strip()
    host = urlsplit(candidate).hostname
    if host is None and "://" not in candidate:
        # Bare host or host/path with no scheme -> parse the leading authority.
        host = urlsplit("//" + candidate).hostname
    return bool(host) and host.lower().rstrip(".").endswith(".onion")


def guard(name: str, arguments: dict, enabled: bool) -> str | None:
    """Return a block reason (truthful error text) if the call violates the
    envelope, else None. Applied to SearXNG-provider tools before forwarding."""
    args = arguments or {}
    if name == "web_url_read" and is_onion_url(args.get("url", "")):
        return (
            "onions-lane envelope: fetching/rendering a .onion URL is FORBIDDEN. "
            "This lane is index-only (Ahmia titles + metadata + the .onion URL as a "
            f"string). No Tor, no onion fetch. See {ENVELOPE_DOC}."
        )
    if name == "searxng_web_search" and requests_onions(args):
        if not enabled:
            return (
                "onion lane is OFF by default. It queries the Ahmia index only "
                "(clearnet, no Tor, no onion fetch) via engines=ahmia / "
                'categories="onion index"; set ENABLE_ONIONS=1 to enable it and read '
                f"{ENVELOPE_DOC} (scope + Ahmia removal policy + sign-off) first."
            )
    return None
