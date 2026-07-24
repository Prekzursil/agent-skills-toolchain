"""Browser rail: drive a logged-in Chrome/Edge over CDP with Playwright.

Why this module exists
----------------------
Chrome 136+ ignores ``--remote-debugging-port`` when it is pointed at the DEFAULT
user-data-dir, so the old "just attach to the browser the owner already has open"
recipe silently does nothing. The rail therefore drives a DEDICATED automation
profile (see ``Start-BrowserRail.ps1``), which the owner signs into ONCE by hand.
No credential ever passes through an agent.

Layout contract
---------------
Everything above ``--- playwright-touching ---`` is PURE: importable and unit
tested with no browser, no network and no ``playwright`` install. Everything
below it imports ``playwright`` lazily, so this module stays importable (and its
tests stay runnable) on a machine that has never installed it.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:  # pragma: no cover -- typing-only, never executed at runtime
    from collections.abc import Iterable, Iterator

DEFAULT_CDP_HOST = "127.0.0.1"
DEFAULT_CDP_PORT = 9222

#: Ports ``browser_list_sessions`` probes for a live CDP endpoint. 9222 is the
#: primary automation profile; 9333 is the conventional second profile (see
#: ``Start-BrowserRail.ps1``). Pure data here -- the network probe that reads it
#: lives below the playwright marker.
DEFAULT_CDP_PORTS: tuple[int, ...] = (DEFAULT_CDP_PORT, 9333)

#: Roles worth reading when probing a page for auth state. Deliberately small:
#: ``page.accessibility`` does NOT exist in playwright 1.61 (measured), so the
#: rail reads the a11y tree through role locators instead of an AX snapshot.
DEFAULT_PROBE_ROLES: tuple[str, ...] = ("button", "link")

#: ``assert_payload_not_inlined`` only scans payload strings at least this long.
#: Shorter strings ("ok", "id", "on") occur naturally inside ordinary JS source
#: and would make the guard fire constantly. DETECTOR WEAKNESS, stated plainly:
#: this is a lint against the common mistake, NOT a proof of non-inlining -- a
#: payload of 11 characters or fewer is not checked at all.
MIN_SCANNED_PAYLOAD_LEN = 12


class BrowserRailError(RuntimeError):
    """Base class for every error this module raises deliberately."""


class PayloadInlinedError(BrowserRailError):
    """Raised when caller-supplied content was concatenated into JS source.

    Content must travel as an ``evaluate`` ARGUMENT. Inlining it into the source
    string re-parses it as code: quotes, backslashes and ``</script>`` in the
    payload then change what executes.
    """


# --------------------------------------------------------------------------
# Pure logic (no playwright, no network) -- unit tested
# --------------------------------------------------------------------------


def cdp_http_endpoint(
    port: int = DEFAULT_CDP_PORT, host: str = DEFAULT_CDP_HOST
) -> str:
    """Return the HTTP CDP endpoint Playwright's ``connect_over_cdp`` expects."""
    return f"http://{host}:{port}"


def cdp_version_endpoint(
    port: int = DEFAULT_CDP_PORT, host: str = DEFAULT_CDP_HOST
) -> str:
    """Return the CDP ``/json/version`` URL used to probe for a live session."""
    return f"{cdp_http_endpoint(port, host)}/json/version"


def normalize_domain(url_or_domain: str) -> str:
    """Reduce a URL or bare domain to a comparable lowercase host.

    Strips scheme, credentials, port, path and a single leading ``www.``.
    Returns ``""`` for input with no host (``about:blank``, ``""``).
    """
    raw = (url_or_domain or "").strip()
    if not raw:
        return ""
    if "://" in raw:
        host = urlsplit(raw).hostname or ""
    else:
        parts = urlsplit(raw)
        # A no-authority scheme (about:, data:, file:, mailto:) has no host at
        # all. "localhost:3000" parses the same way, so a purely numeric
        # remainder is treated as a port rather than a scheme's path.
        if parts.scheme and not parts.path.isdigit():
            return ""
        # urlsplit only finds a host behind an authority marker, so give the
        # bare domain one before parsing.
        host = urlsplit(f"//{raw}").hostname or ""
    host = host.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def domain_matches(page_url: str, domain: str) -> bool:
    """True when ``page_url`` is on ``domain`` or one of its subdomains.

    Guards the two failure modes a naive ``domain in url`` check has: a suffix
    collision (``notgrok.com`` vs ``grok.com``) and a path-position match
    (``https://evil.com/grok.com``). Both are covered by tests.
    """
    target = normalize_domain(domain)
    if not target:
        return False
    host = normalize_domain(page_url)
    if not host:
        return False
    return host == target or host.endswith(f".{target}")


@dataclass(frozen=True)
class AuthSignals:
    """Site-specific evidence used to classify a session as logged in or out.

    Two DIRECTIONS are kept apart on purpose. A detector that can only observe
    one direction cannot distinguish "signed out" from "page did not render",
    which is exactly how a silent probe gets mistaken for a verdict.
    """

    logged_out_url_substrings: tuple[str, ...] = ()
    logged_out_names: tuple[str, ...] = ()
    logged_in_names: tuple[str, ...] = ()
    probe_roles: tuple[str, ...] = DEFAULT_PROBE_ROLES

    @property
    def both_states_ready(self) -> bool:
        """True when the detector can fire in BOTH directions.

        A signal set with only logged-out markers can never return ``True`` --
        it returns ``UNKNOWN`` instead. That is the honest answer, and this flag
        is how a caller finds out before trusting a verdict.
        """
        has_out = bool(self.logged_out_url_substrings or self.logged_out_names)
        return has_out and bool(self.logged_in_names)


@dataclass(frozen=True)
class AuthVerdict:
    """Outcome of an auth probe.

    ``authed is None`` means UNKNOWN -- no configured signal fired. It is NOT a
    synonym for "logged out"; silence from a detector is not evidence.
    """

    authed: bool | None
    reason: str
    evidence: str = ""

    @property
    def known(self) -> bool:
        return self.authed is not None


def _first_containing(haystack: str, needles: tuple[str, ...]) -> str | None:
    lowered = haystack.lower()
    for needle in needles:
        if needle and needle.lower() in lowered:
            return needle
    return None


def classify_auth(
    final_url: str,
    observed_names: list[str],
    signals: AuthSignals,
) -> AuthVerdict:
    """Classify auth state from a URL plus the accessible names on the page.

    ERROR-DIRECTION BIAS, stated deliberately: logged-OUT evidence is checked
    first, so an ambiguous page reads as "not authed". A false "not authed"
    costs one manual sign-in check; a false "authed" sends the agent into a
    confusing downstream failure. The cheap error is the one we prefer.
    """
    hit = _first_containing(final_url, signals.logged_out_url_substrings)
    if hit is not None:
        return AuthVerdict(False, "logged-out-url", hit)

    joined = "\n".join(observed_names)
    hit = _first_containing(joined, signals.logged_out_names)
    if hit is not None:
        return AuthVerdict(False, "logged-out-control", hit)

    hit = _first_containing(joined, signals.logged_in_names)
    if hit is not None:
        return AuthVerdict(True, "logged-in-control", hit)

    return AuthVerdict(None, "no-signal-fired", "")


def _payload_strings(arg: Any) -> list[str]:
    if isinstance(arg, str):
        return [arg]
    if isinstance(arg, dict):
        out: list[str] = []
        for value in arg.values():
            out.extend(_payload_strings(value))
        return out
    if isinstance(arg, (list, tuple)):
        out = []
        for value in arg:
            out.extend(_payload_strings(value))
        return out
    return []


def assert_payload_not_inlined(js_source: str, arg: Any) -> None:
    """Raise if caller content appears verbatim inside the JS source string.

    See ``MIN_SCANNED_PAYLOAD_LEN`` for the stated limit of this guard.
    """
    for text in _payload_strings(arg):
        if len(text) >= MIN_SCANNED_PAYLOAD_LEN and text in js_source:
            raise PayloadInlinedError(
                "payload content found inside the JS source; pass it as the "
                f"evaluate() argument instead (offending prefix: {text[:40]!r})"
            )


#: Sets the files of an ``<input type=file>`` from text held in the ARG.
#: The content never appears in this source.
UPLOAD_TEXT_JS = """
(arg) => {
  const el = document.querySelector(arg.selector);
  if (!el) return { ok: false, error: 'selector-not-found' };
  const dt = new DataTransfer();
  dt.items.add(new File([arg.text], arg.filename, { type: arg.mime }));
  el.files = dt.files;
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return { ok: true, count: el.files.length };
}
"""

#: POSTs JSON from the page's own origin, inheriting its cookies/session.
POST_JSON_JS = """
async (arg) => {
  const res = await fetch(arg.url, {
    method: arg.method,
    credentials: 'include',
    headers: Object.assign({ 'Content-Type': 'application/json' }, arg.headers),
    body: JSON.stringify(arg.payload),
  });
  let body = null;
  try { body = await res.json(); } catch (e) { body = await res.text(); }
  return { ok: res.ok, status: res.status, body: body };
}
"""


# --------------------------------------------------------------------------
# Canonical verb vocabulary -- the Browser Use naming borrow
# --------------------------------------------------------------------------
#
# The rail is a Python import surface, not an MCP tool surface, so a "verb" is a
# module-level function. VERB_TABLE adopts Browser Use's ``browser_*`` names as a
# thin, stable ALIAS layer over the rail's own functions: a canonical name a
# caller can rely on even if an underlying helper is later renamed. Addressing
# stays role+name (which survives a page restyle); this only standardises the
# NAMES. Every value is the ``__name__`` of a function defined in this module, so
# the whole mapping is checkable without a browser -- ``getattr(module, target)``
# must resolve for every entry (see test_browser_rail.py).
#
# Only ``browser_navigate`` maps to a differently-named existing function
# (``find_or_open_page``, kept for its tab reuse). The rest are implemented as
# ``browser_*`` functions of the same name below the marker.
#
# ``retry_with_browser_use_agent`` is deliberately EXCLUDED: it is Browser Use's
# nested-agent verb, and the rail is a primitive layer, not an agent runtime.

#: Browser Use's 13 borrowed navigation / interaction / session verbs -> the name
#: of the function in THIS module that implements each.
VERB_TABLE: dict[str, str] = {
    "browser_navigate": "find_or_open_page",
    "browser_click": "browser_click",
    "browser_type": "browser_type",
    "browser_get_state": "browser_get_state",
    "browser_scroll": "browser_scroll",
    "browser_go_back": "browser_go_back",
    "browser_list_tabs": "browser_list_tabs",
    "browser_switch_tab": "browser_switch_tab",
    "browser_close_tab": "browser_close_tab",
    "browser_extract_content": "browser_extract_content",
    "browser_list_sessions": "browser_list_sessions",
    "browser_close_session": "browser_close_session",
    "browser_close_all": "browser_close_all",
}

#: The four rail-specific verbs Browser Use has no equivalent for, each given a
#: matching ``browser_*`` alias so the whole surface reads uniformly. Kept apart
#: from VERB_TABLE because they are NOT part of the borrowed vocabulary.
RAIL_VERBS: dict[str, str] = {
    "browser_is_authed": "is_authed",
    "browser_evaluate": "evaluate_with_arg",
    "browser_upload_text": "upload_text_as_file",
    "browser_post_json": "post_json",
}


# --------------------------------------------------------------------------
# --- playwright-touching --- (lazy import; manual verification only)
# --------------------------------------------------------------------------


def _sync_playwright() -> Any:
    """Import playwright only when a caller actually drives a browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover -- needs playwright uninstalled
        raise BrowserRailError(
            "playwright is not installed; run: pip install playwright"
        ) from exc
    return sync_playwright


@contextmanager
def rail(
    port: int = DEFAULT_CDP_PORT,
    host: str = DEFAULT_CDP_HOST,
) -> Iterator[Any]:  # pragma: no cover -- requires a live browser
    """Attach to the running rail browser and yield the Playwright ``Browser``.

    Start the browser first with ``Start-BrowserRail.ps1``. Exiting the block
    DISCONNECTS; it does not quit the owner's browser, and pages opened inside
    are deliberately left open so the owner can see what happened.
    """
    factory = _sync_playwright()
    with factory() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_http_endpoint(port, host))
        try:
            yield browser
        finally:
            browser.close()


def _iter_pages(browser: Any) -> Iterator[Any]:  # pragma: no cover -- live browser
    """Yield every open page across all of ``browser``'s contexts, in order.

    Factored out so :func:`find_or_open_page` (the tab-reuse lookup) and
    :func:`browser_list_tabs` (the tab inventory) walk the tabs the same way.
    """
    for context in browser.contexts:
        yield from context.pages


def find_or_open_page(
    browser: Any,
    url: str,
    domain: str | None = None,
) -> tuple[Any, bool]:  # pragma: no cover -- requires a live browser
    """Return ``(page, opened)`` for ``url``, reusing a matching tab if present.

    Reuse matters: the owner's already-open tab is usually the authenticated
    one, and opening a duplicate loses in-page state.
    """
    target = domain or url
    for page in _iter_pages(browser):
        if domain_matches(page.url, target):
            return page, False
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto(url)
    return page, True


def _iter_role_names(
    page: Any,
    roles: tuple[str, ...],
    limit: int,
) -> Iterator[tuple[str, str]]:  # pragma: no cover -- requires a live browser
    """Yield ``(role, accessible_name)`` for each visible, named role element.

    The single a11y-tree walk shared by :func:`visible_role_names` (which keeps
    only the names) and :func:`browser_get_state` (which also needs the role and
    a running index).
    """
    for role in roles:
        locator = page.get_by_role(role)
        for index in range(min(locator.count(), limit)):
            item = locator.nth(index)
            if not item.is_visible():
                continue
            text = (item.get_attribute("aria-label") or item.inner_text() or "").strip()
            if text:
                yield role, text


def visible_role_names(
    page: Any,
    roles: tuple[str, ...] = DEFAULT_PROBE_ROLES,
    limit: int = 120,
) -> list[str]:  # pragma: no cover -- requires a live browser
    """Read visible accessible names via ROLE locators (not a pixel screenshot).

    ``page.accessibility`` does not exist in playwright 1.61 (measured), so role
    locators are the a11y-tree access path.
    """
    return [name for _role, name in _iter_role_names(page, roles, limit)]


def is_authed(
    page: Any,
    signals: AuthSignals,
    url: str | None = None,
) -> AuthVerdict:  # pragma: no cover -- requires a live browser
    """Navigate (optionally) and classify whether the session is signed in."""
    if url:
        page.goto(url)
    return classify_auth(
        page.url, visible_role_names(page, signals.probe_roles), signals
    )


def evaluate_with_arg(
    page: Any,
    js_source: str,
    arg: Any,
) -> Any:  # pragma: no cover -- requires a live browser
    """``page.evaluate`` with the anti-inlining guard applied first."""
    assert_payload_not_inlined(js_source, arg)
    return page.evaluate(js_source, arg)


def upload_text_as_file(
    page: Any,
    selector: str,
    filename: str,
    text: str,
    mime: str = "text/plain",
) -> Any:  # pragma: no cover -- requires a live browser
    """Attach ``text`` to a file input as ``filename`` without touching disk."""
    return evaluate_with_arg(
        page,
        UPLOAD_TEXT_JS,
        {"selector": selector, "filename": filename, "text": text, "mime": mime},
    )


@dataclass
class PostRequest:
    """Arguments for :func:`post_json`, kept typed so callers cannot swap them."""

    url: str
    payload: Any
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)


def post_json(
    page: Any,
    request: PostRequest,
) -> Any:  # pragma: no cover -- requires a live browser
    """POST JSON from the page's own origin, inheriting its logged-in session."""
    return evaluate_with_arg(
        page,
        POST_JSON_JS,
        {
            "url": request.url,
            "payload": request.payload,
            "method": request.method,
            "headers": request.headers,
        },
    )


# --------------------------------------------------------------------------
# Browser Use verb layer -- thin wrappers named for VERB_TABLE / RAIL_VERBS
# --------------------------------------------------------------------------
#
# Each function below is a target named in VERB_TABLE. They are deliberately
# thin: addressing stays role+name (which survives a restyle) and the
# rail-specific verbs remain the richer surface. Every one needs a live browser
# (or, for browser_list_sessions, a live CDP endpoint), so all are
# pragma-no-cover; the checkable contract -- names present, retry verb absent,
# every target resolvable -- is enforced against the pure VERB_TABLE by the tests.


def browser_click(
    page: Any, *, role: str, name: str
) -> None:  # pragma: no cover -- requires a live browser
    """Click the element addressed by ARIA ``role`` + accessible ``name``."""
    page.get_by_role(role, name=name).click()


def browser_type(
    page: Any, *, role: str, name: str, text: str
) -> None:  # pragma: no cover -- requires a live browser
    """Fill the ``role`` + ``name`` field with ``text`` (replacing any value)."""
    page.get_by_role(role, name=name).fill(text)


def browser_get_state(
    page: Any,
    roles: tuple[str, ...] = DEFAULT_PROBE_ROLES,
    limit: int = 120,
) -> dict[str, Any]:  # pragma: no cover -- requires a live browser
    """Return ``{url, title, elements:[{index, role, name}]}`` for ``page``.

    The Browser Use ``get_state`` shape, read from the same role-locator walk as
    :func:`visible_role_names` rather than from a pixel screenshot.
    """
    elements = [
        {"index": index, "role": role, "name": name}
        for index, (role, name) in enumerate(_iter_role_names(page, roles, limit))
    ]
    return {"url": page.url, "title": page.title(), "elements": elements}


def browser_scroll(
    page: Any, *, dy: float, dx: float = 0
) -> None:  # pragma: no cover -- requires a live browser
    """Scroll by ``(dx, dy)`` wheel deltas (positive ``dy`` scrolls down)."""
    page.mouse.wheel(dx, dy)


def browser_go_back(page: Any) -> Any:  # pragma: no cover -- requires a live browser
    """Navigate back one entry in the tab's history."""
    return page.go_back()


def browser_list_tabs(
    browser: Any,
) -> list[dict[str, Any]]:  # pragma: no cover -- requires a live browser
    """List every open tab as ``{index, url, title}`` across all contexts."""
    return [
        {"index": index, "url": page.url, "title": page.title()}
        for index, page in enumerate(_iter_pages(browser))
    ]


def browser_switch_tab(page: Any) -> None:  # pragma: no cover -- live browser
    """Bring ``page`` to the foreground (the rail addresses tabs by object)."""
    page.bring_to_front()


def browser_close_tab(page: Any) -> None:  # pragma: no cover -- live browser
    """Close a single tab; the rest of the session is untouched."""
    page.close()


def browser_extract_content(
    page: Any,
) -> str:  # pragma: no cover -- requires a live browser
    """Return the page body's rendered inner text."""
    return page.inner_text("body")


def browser_list_sessions(
    ports: tuple[int, ...] = DEFAULT_CDP_PORTS,
    host: str = DEFAULT_CDP_HOST,
    timeout: float = 0.5,
) -> list[dict[str, Any]]:  # pragma: no cover -- requires a live endpoint
    """Probe ``ports`` for reachable CDP endpoints; one entry per live session.

    Uses stdlib ``urllib`` (NOT playwright) against ``/json/version`` with a short
    timeout, so an absent endpoint is skipped rather than raising. This is a
    network probe, which is why it lives below the playwright marker.
    """
    import json
    import urllib.error
    import urllib.request

    sessions: list[dict[str, Any]] = []
    for port in ports:
        try:
            with urllib.request.urlopen(
                cdp_version_endpoint(port, host), timeout=timeout
            ) as response:
                info = json.load(response)
        except (urllib.error.URLError, OSError, ValueError):
            continue
        sessions.append(
            {"port": port, "endpoint": cdp_http_endpoint(port, host), "info": info}
        )
    return sessions


def browser_close_session(
    browser: Any,
) -> None:  # pragma: no cover -- requires a live browser
    """DISCONNECT the rail from ``browser``.

    Over CDP this detaches the automation client; it does NOT quit the owner's
    browser or close their tabs. Named to make that distinction explicit.
    """
    browser.close()


def browser_close_all(
    browsers: Iterable[Any],
) -> None:  # pragma: no cover -- requires a live browser
    """Disconnect every rail connection in ``browsers``.

    Each is a detach, not a quit -- see :func:`browser_close_session`.
    """
    for browser in browsers:
        browser.close()


# browser_* canonical aliases for the functions that keep their original rail
# name -- the ALIAS entry in VERB_TABLE plus every RAIL_VERBS entry.
browser_navigate = find_or_open_page
browser_is_authed = is_authed
browser_evaluate = evaluate_with_arg
browser_upload_text = upload_text_as_file
browser_post_json = post_json
