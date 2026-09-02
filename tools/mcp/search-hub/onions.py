#!/usr/bin/env python3
"""Onions-lane envelope + ask/modes/tagging for the SearXNG provider (index-only).

The onion lane is **querying the Ahmia index only**, through the SearXNG provider
the hub already fronts -- NOT a new tool and NOT a new service. This module is the
enforcement point for the hard legal/safety envelope
(``docs/legal/onions-lane-envelope.md``).

Activation model (owner decision 2026-09-02): the lane **works by default** but
**asks before searching**. Concretely, an onion-intent ``searxng_web_search``
(``engines=ahmia`` or a category containing "onion") is NOT forwarded until the
caller re-invokes with ``onion_confirm=true`` and a chosen ``onion_mode``
(low|medium|high|deepest). The first call returns a **confirmation request** (not
an error) that the calling agent must surface to the human. ``ENABLE_ONIONS=0``
remains a hard **kill switch**. Unchanged hard rules:

* **No Tor, no ``.onion`` fetch.** ``web_url_read`` of a ``.onion`` host is refused
  **always** (flag or confirmation regardless). Results are index metadata only
  (title + snippet + the ``.onion`` URL as a string).
* Modes control **index breadth only** (how many Ahmia index hits), never onion
  page crawling/scraping/fetching.
* Onion results are **clearly tagged** as dark-web/Tor index hits, distinct from
  normal web results.

Everything here is a pure function of tool name + arguments + environ, so it is
fully unit-testable with no network, no child, and no SearXNG instance.
"""

from __future__ import annotations

import copy
from urllib.parse import urlsplit

ENV_FLAG = "ENABLE_ONIONS"
# Stock SearXNG HARD-GATES the literal ``onions`` category on a working Tor proxy
# (drops any engine whose categories contain "onions" unless using_tor_proxy is
# true, and probes check.torproject.org at startup). Our envelope forbids Tor, so
# the clearnet Ahmia engine is registered under a NON-"onions" category name
# (``onion index``) and selected by ``engines=ahmia`` -- see the envelope doc.
ONION_CATEGORY = "onion index"
# The ONLY onion engine this lane permits: the Ahmia index. Not Evil / Torch are
# deliberately excluded (dead / Tor-only) and any onion engine is index-only here.
ONION_ENGINES = frozenset({"ahmia"})
ENVELOPE_DOC = "docs/legal/onions-lane-envelope.md"

# Control arguments the caller adds to confirm + pick a mode; stripped before the
# request is forwarded to the SearXNG child (mcp-searxng would not understand them).
CONFIRM_ARG = "onion_confirm"
MODE_ARG = "onion_mode"

# Search modes -> Ahmia INDEX breadth only (num_results is the mcp-searxng cap,
# 1-20). "depth" here means how many index hits, NOT crawling/fetching onion pages.
MODES: dict[str, dict] = {
    "low": {"num_results": 5, "blurb": "~5 index hits (fast)"},
    "medium": {"num_results": 10, "blurb": "~10 index hits"},
    "high": {"num_results": 20, "blurb": "~20 index hits (broad)"},
    "deepest": {
        "num_results": 20,
        "blurb": "max index breadth (~20, still INDEX-ONLY; never fetches .onion)",
    },
}
DEFAULT_MODE = "low"

# Decision actions returned by ``onion_decision``.
PASS = "pass"  # not an onion call -> forward normally
FORBID = "forbid"  # .onion fetch -> refuse always (isError)
KILLED = "killed"  # onion intent but ENABLE_ONIONS=0 kill switch (isError)
ASK = "ask"  # onion intent, not confirmed -> return the confirmation request
RUN = "run"  # confirmed -> forward the mode-applied onion args, then tag results


def _lower(value) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def is_kill_switched(environ) -> bool:
    """Onion works by default; ENABLE_ONIONS explicitly falsey is a hard OFF."""
    return _lower(environ.get(ENV_FLAG)) in ("0", "false", "no", "off")


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
    category ``onion index``.
    """
    args = arguments or {}
    categories = _csv(args.get("categories"))
    engines = _csv(args.get("engines"))
    if any("onion" in token for token in categories):
        return True
    return bool(set(engines) & ONION_ENGINES)


def is_confirmed(arguments: dict) -> bool:
    value = (arguments or {}).get(CONFIRM_ARG)
    return value is True or _lower(value) in ("1", "true", "yes", "on")


def selected_mode(arguments: dict) -> str:
    mode = _lower((arguments or {}).get(MODE_ARG)) or DEFAULT_MODE
    return mode if mode in MODES else DEFAULT_MODE


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


def confirmation_request(arguments: dict) -> dict:
    """The 'ask before searching' payload (NOT an error) for the calling agent to
    surface to the human, listing the search modes and the envelope."""
    return {
        "onion_confirmation_required": True,
        "action_required": (
            "STOP and ask the human to choose a search mode and confirm before this "
            "dark-web (Ahmia) INDEX search runs. Do not auto-confirm."
        ),
        "query": (arguments or {}).get("query", ""),
        "modes": [
            {"mode": name, "means": spec["blurb"]} for name, spec in MODES.items()
        ],
        "how_to_confirm": (
            "Re-call searxng_web_search with the SAME query plus "
            f'{CONFIRM_ARG}=true and {MODE_ARG}="<low|medium|high|deepest>".'
        ),
        "scope": (
            "Ahmia dark-web INDEX over CLEARNET only: no Tor, no .onion fetch. "
            "Results are titles + snippets + the .onion URL as a string. Modes set "
            "index breadth only, never onion-page crawling."
        ),
        "envelope_doc": ENVELOPE_DOC,
    }


def prepare_onion_args(arguments: dict) -> dict:
    """Return the SearXNG args for a CONFIRMED onion search: pin the Ahmia index,
    apply the mode's index breadth, and strip the onion control args."""
    args = dict(arguments or {})
    mode = selected_mode(args)
    args.pop(CONFIRM_ARG, None)
    args.pop(MODE_ARG, None)
    # Pin the clearnet Ahmia index engine + its category; set breadth from the mode.
    args["engines"] = "ahmia"
    args["categories"] = ONION_CATEGORY
    args["num_results"] = MODES[mode]["num_results"]
    return args


def _onion_banner(mode: str) -> dict:
    return {
        "type": "text",
        "text": (
            "TOR / DARK-WEB INDEX RESULTS -- Ahmia index (clearnet, INDEX-ONLY, "
            f"mode={mode}). These are .onion hidden-service listings (title + snippet "
            "+ the .onion URL as a STRING). The .onion URLs are NOT fetched or "
            "rendered (envelope: no Tor, no onion fetch). Treat as UNVERIFIED "
            "dark-web index hits -- clearly distinct from normal web results."
        ),
    }


def tag_onion_response(response: dict, mode: str) -> dict:
    """Prepend a clear dark-web banner + a structured marker to a child response so
    onion results are unambiguously differentiated from normal web results."""
    tagged = copy.deepcopy(response) if isinstance(response, dict) else response
    if not isinstance(tagged, dict):
        return response
    result = tagged.get("result")
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            result["content"] = [_onion_banner(mode), *content]
        result["_onion"] = {
            "lane": "ahmia-index",
            "mode": mode,
            "tor": True,
            "onion_fetched": False,
            "verified": False,
        }
    return tagged


def onion_decision(name: str, arguments: dict, environ) -> tuple[str, object]:
    """Decide how the hub should handle a SearXNG-provider call.

    Returns ``(action, payload)``:
      * ``(PASS, None)``            -- not an onion call; forward normally.
      * ``(FORBID, text)``          -- ``.onion`` ``web_url_read``; refuse always.
      * ``(KILLED, text)``          -- onion intent but ``ENABLE_ONIONS=0``.
      * ``(ASK, request_dict)``     -- onion intent, unconfirmed; return the ask.
      * ``(RUN, (searxng_args, mode))`` -- confirmed; forward these, then tag.
    """
    args = arguments or {}
    if name == "web_url_read" and is_onion_url(args.get("url", "")):
        return FORBID, (
            "onions-lane envelope: fetching/rendering a .onion URL is FORBIDDEN. "
            "This lane is index-only (Ahmia titles + metadata + the .onion URL as a "
            f"string). No Tor, no onion fetch. See {ENVELOPE_DOC}."
        )
    if name != "searxng_web_search" or not requests_onions(args):
        return PASS, None
    if is_kill_switched(environ):
        return KILLED, (
            "onion lane is hard-disabled (ENABLE_ONIONS=0). Unset it to restore the "
            f"default ask-before-search dark-web index lane. See {ENVELOPE_DOC}."
        )
    if not is_confirmed(args):
        return ASK, confirmation_request(args)
    return RUN, (prepare_onion_args(args), selected_mode(args))
