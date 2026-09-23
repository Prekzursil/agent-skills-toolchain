#!/usr/bin/env python3
"""Onions-lane envelope + ask/modes/tagging for the SearXNG provider (index-only).

The onion lane is **querying clearnet onion INDEXES only** -- the Ahmia index and,
since owner decision G-7 (2026-09-02), the VormWeb index -- through the SearXNG
provider the hub already fronts -- NOT a new tool and NOT a new service. This
module is the enforcement point for the hard legal/safety envelope
(``docs/legal/onions-lane-envelope.md``).

Activation model (owner decision 2026-09-02): the lane **works by default** but
**asks before searching**. Concretely, an onion-intent ``searxng_web_search``
(``engines=ahmia``, ``engines=vormweb``, or a category containing "onion") is NOT
forwarded until the caller re-invokes with ``onion_confirm=true`` and a chosen
``onion_mode`` (low|medium|high|deepest). The first call returns a **confirmation
request** (not an error) that the calling agent must surface to the human.
``ENABLE_ONIONS=0`` remains a hard **kill switch** for the whole lane;
``ENABLE_VORMWEB=0`` is a per-engine kill switch for VormWeb only. Unchanged hard
rules:

* **No Tor, no ``.onion`` fetch.** ``web_url_read`` of a ``.onion`` host is refused
  **always** (flag or confirmation regardless). Results are index metadata only
  (title + snippet + the ``.onion`` URL as a string).
* Modes control **index breadth only** (how many index hits), never onion page
  crawling/scraping/fetching.
* Onion results are **clearly tagged** as dark-web/Tor index hits, distinct from
  normal web results, and the tag names which index answered.

Engine selection: with no explicit engine (category-only intent) a confirmed
search queries **every enabled lane engine** (``ahmia,vormweb`` by default);
naming one lane engine (``engines=vormweb``) queries that one only; any non-onion
engine mixed in is dropped (the lane never blends clearnet general engines under
the dark-web banner). VormWeb caveats the owner accepted with G-7 -- operator
consent unresolved (no ToS / robots policy published) and result filtering being
VormWeb's self-declared, unverifiable policy -- are documented in the envelope,
not hidden; nothing here changes what a result IS (index metadata, never fetched).

Everything here is a pure function of tool name + arguments + environ, so it is
fully unit-testable with no network, no child, and no SearXNG instance.
"""

from __future__ import annotations

import copy
from urllib.parse import urlsplit

ENV_FLAG = "ENABLE_ONIONS"
VORMWEB_ENV_FLAG = "ENABLE_VORMWEB"
# Stock SearXNG HARD-GATES the literal ``onions`` category on a working Tor proxy
# (drops any engine whose categories contain "onions" unless using_tor_proxy is
# true, and probes check.torproject.org at startup). Our envelope forbids Tor, so
# BOTH clearnet index engines are registered under a NON-"onions" category name
# (``onion index``) and selected by ``engines=ahmia`` / ``engines=vormweb`` -- see
# the envelope doc.
ONION_CATEGORY = "onion index"
AHMIA = "ahmia"
VORMWEB = "vormweb"
# The ONLY onion engines this lane permits, in lane order (= the order of the
# ``engines`` CSV forwarded to SearXNG): the Ahmia index and the VormWeb index
# (G-7). Not Evil / Torch are deliberately excluded (dead / Tor-only); any engine
# here is index-only. Adding a third requires a new decision record (envelope).
ONION_ENGINE_ORDER: tuple[str, ...] = (AHMIA, VORMWEB)
ONION_ENGINES = frozenset(ONION_ENGINE_ORDER)
# Per-engine kill switches. Ahmia is the lane's anchor and has none: killing the
# lane (ENABLE_ONIONS=0) is how Ahmia goes off. VormWeb is DEFAULT-ON (G-7) with
# its own switch because its caveats (consent gap, self-declared filtering) are
# engine-specific and the owner may want Ahmia-only without losing the lane.
ENGINE_KILL_FLAGS: dict[str, str] = {VORMWEB: VORMWEB_ENV_FLAG}
ENGINE_LABELS: dict[str, str] = {AHMIA: "Ahmia", VORMWEB: "VormWeb"}
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


def _falsey(value) -> bool:
    return _lower(value) in ("0", "false", "no", "off")


def is_kill_switched(environ) -> bool:
    """Onion works by default; ENABLE_ONIONS explicitly falsey is a hard OFF."""
    return _falsey(environ.get(ENV_FLAG))


def is_engine_kill_switched(engine: str, environ) -> bool:
    """Per-engine switch (only VormWeb has one): explicitly falsey -> that engine is
    OFF; unset / truthy -> ON. Engines without a switch are never kill-switched."""
    flag = ENGINE_KILL_FLAGS.get(engine)
    return flag is not None and _falsey(environ.get(flag))


def enabled_engines(environ) -> list[str]:
    """The DEFAULT engine list for a confirmed onion search: every lane engine whose
    own kill switch is not set, in lane order (``ahmia,vormweb`` by default)."""
    return [e for e in ONION_ENGINE_ORDER if not is_engine_kill_switched(e, environ)]


def _csv(value) -> list[str]:
    """Lower-cased tokens from a comma-separated string or a list."""
    if isinstance(value, str):
        return [part.strip().lower() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(part).strip().lower() for part in value if str(part).strip()]
    return []


def requested_onion_engines(arguments: dict) -> list[str]:
    """The lane engines the caller named EXPLICITLY in ``engines``, in lane order.
    Non-onion engines are dropped (never blended under the dark-web banner)."""
    named = set(_csv((arguments or {}).get("engines")))
    return [e for e in ONION_ENGINE_ORDER if e in named]


def killed_engines_requested(arguments: dict, environ) -> list[str]:
    """Lane engines the caller named explicitly whose kill switch is set -> refuse
    truthfully instead of silently narrowing an explicit request."""
    return [
        e
        for e in requested_onion_engines(arguments)
        if is_engine_kill_switched(e, environ)
    ]


def resolve_engines(arguments: dict, environ) -> list[str]:
    """Engines a confirmed onion search will query: the caller's explicit lane
    engines if any (``engines=vormweb`` -> VormWeb only), else the enabled default
    set. Callers must check ``killed_engines_requested`` first."""
    return requested_onion_engines(arguments) or enabled_engines(environ)


def requests_onions(arguments: dict) -> bool:
    """True iff the search args select an onion category or a lane engine
    (``ahmia`` / ``vormweb``).

    Category detection is by the substring "onion" so it catches the intuitive
    ``onions`` (which stock SearXNG reserves for Tor) AND the clearnet lane's real
    category ``onion index``. A kill-switched engine still counts as onion intent
    (it is then refused, not silently passed through to a general search).
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


def _engine_names(engines: list[str]) -> str:
    """Human labels for the banner / ask text: ``Ahmia + VormWeb`` (or ``onion`` when
    the engine list is unknown -- never claim a specific index)."""
    return " + ".join(ENGINE_LABELS.get(e, e) for e in engines) or "onion"


def lane_label(engines: list[str]) -> str:
    """Structured lane marker: ``ahmia-index`` / ``vormweb-index`` (mirrors the
    original value) / ``ahmia+vormweb-index`` when both indexes were queried;
    ``onion-index`` when the engine list is unknown."""
    return ("+".join(engines) if engines else "onion") + "-index"


def confirmation_request(arguments: dict, engines: list[str] | None = None) -> dict:
    """The 'ask before searching' payload (NOT an error) for the calling agent to
    surface to the human, listing the engines it will query, the search modes
    and the envelope. ``engines`` is the resolved list (see ``resolve_engines``);
    when omitted it is resolved with no environ (the enabled defaults)."""
    engines = list(engines) if engines is not None else resolve_engines(arguments, {})
    names = _engine_names(engines)
    scope = (
        f"{names} dark-web INDEX over CLEARNET only: no Tor, no .onion fetch. "
        "Results are titles + snippets + the .onion URL as a string. Modes set "
        "index breadth only, never onion-page crawling."
    )
    if VORMWEB in engines:
        # G-7 caveats travel with every VormWeb ask (documented, never silent).
        scope += (
            " VormWeb caveats: operator consent unresolved (no ToS/robots policy "
            "published); its filtering is self-declared and unverified -- see the "
            "envelope doc."
        )
    return {
        "onion_confirmation_required": True,
        "action_required": (
            "STOP and ask the human to choose a search mode and confirm before this "
            f"dark-web ({names}) INDEX search runs. Do not auto-confirm."
        ),
        "query": (arguments or {}).get("query", ""),
        "engines": engines,
        "modes": [
            {"mode": name, "means": spec["blurb"]} for name, spec in MODES.items()
        ],
        "how_to_confirm": (
            "Re-call searxng_web_search with the SAME query plus "
            f'{CONFIRM_ARG}=true and {MODE_ARG}="<low|medium|high|deepest>". '
            "Pass engines=ahmia or engines=vormweb to query ONE index; omit "
            "engines (or name both) for every enabled index."
        ),
        "scope": scope,
        "envelope_doc": ENVELOPE_DOC,
    }


def prepare_onion_args(arguments: dict, engines: list[str] | None = None) -> dict:
    """Return the SearXNG args for a CONFIRMED onion search: pin the clearnet index
    engine(s), apply the mode's index breadth, and strip the onion control args.
    ``engines`` is the resolved list from ``onion_decision``; when omitted it is
    resolved from the arguments with no environ (the enabled defaults)."""
    args = dict(arguments or {})
    mode = selected_mode(args)
    resolved = list(engines) if engines else resolve_engines(args, {})
    args.pop(CONFIRM_ARG, None)
    args.pop(MODE_ARG, None)
    # Pin the clearnet index engine(s) + their category; set breadth from the mode.
    args["engines"] = ",".join(resolved)
    args["categories"] = ONION_CATEGORY
    args["num_results"] = MODES[mode]["num_results"]
    return args


def _onion_banner(mode: str, engines: list[str]) -> dict:
    return {
        "type": "text",
        "text": (
            f"TOR / DARK-WEB INDEX RESULTS -- {_engine_names(engines)} index "
            f"(clearnet, INDEX-ONLY, mode={mode}). These are .onion hidden-service "
            "listings (title + snippet + the .onion URL as a STRING). The .onion "
            "URLs are NOT fetched or rendered (envelope: no Tor, no onion fetch). "
            "Treat as UNVERIFIED dark-web index hits -- clearly distinct from normal "
            "web results. Any 'Verified' badge is the index operator's own claim, "
            "not ours."
        ),
    }


def tag_onion_response(
    response: dict, mode: str, searxng_args: dict | None = None
) -> dict:
    """Prepend a clear dark-web banner + a structured marker to a child response so
    onion results are unambiguously differentiated from normal web results.

    ``searxng_args`` are the pinned args that were FORWARDED (``engines`` names the
    index(es) that answered); the marker's ``lane`` mirrors them
    (``ahmia-index`` / ``vormweb-index`` / ``ahmia+vormweb-index``). Without them
    the marker stays truthfully generic (``onion-index``, ``engines: []``)."""
    tagged = copy.deepcopy(response) if isinstance(response, dict) else response
    if not isinstance(tagged, dict):
        return response
    engines = requested_onion_engines(searxng_args or {})
    result = tagged.get("result")
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            result["content"] = [_onion_banner(mode, engines), *content]
        result["_onion"] = {
            "lane": lane_label(engines),
            "engines": engines,
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
      * ``(KILLED, text)``          -- onion intent but ``ENABLE_ONIONS=0``, or an
                                       EXPLICIT request for an engine whose own
                                       kill switch is set (``ENABLE_VORMWEB=0``).
      * ``(ASK, request_dict)``     -- onion intent, unconfirmed; return the ask.
      * ``(RUN, (searxng_args, mode))`` -- confirmed; forward these, then tag
                                       (pass ``searxng_args`` to the tagger).
    """
    args = arguments or {}
    if name == "web_url_read" and is_onion_url(args.get("url", "")):
        return FORBID, (
            "onions-lane envelope: fetching/rendering a .onion URL is FORBIDDEN. "
            "This lane is index-only (Ahmia / VormWeb index titles + metadata + the "
            f".onion URL as a string). No Tor, no onion fetch. See {ENVELOPE_DOC}."
        )
    if name != "searxng_web_search" or not requests_onions(args):
        return PASS, None
    if is_kill_switched(environ):
        return KILLED, (
            "onion lane is hard-disabled (ENABLE_ONIONS=0). Unset it to restore the "
            f"default ask-before-search dark-web index lane. See {ENVELOPE_DOC}."
        )
    killed = killed_engines_requested(args, environ)
    if killed:
        flags = ", ".join(f"{ENGINE_KILL_FLAGS[e]}=0" for e in killed)
        remaining = ",".join(enabled_engines(environ)) or "none"
        return KILLED, (
            f"onion index engine(s) {','.join(killed)} are hard-disabled ({flags}); "
            "an explicit request for them is refused rather than silently narrowed. "
            f"Drop them from `engines` (enabled lane engines: {remaining}) or unset "
            f"the flag. See {ENVELOPE_DOC}."
        )
    engines = resolve_engines(args, environ)
    if not is_confirmed(args):
        return ASK, confirmation_request(args, engines)
    return RUN, (prepare_onion_args(args, engines), selected_mode(args))
