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
    from collections.abc import Iterator

DEFAULT_CDP_HOST = "127.0.0.1"
DEFAULT_CDP_PORT = 9222

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
    for context in browser.contexts:
        for page in context.pages:
            if domain_matches(page.url, target):
                return page, False
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto(url)
    return page, True


def visible_role_names(
    page: Any,
    roles: tuple[str, ...] = DEFAULT_PROBE_ROLES,
    limit: int = 120,
) -> list[str]:  # pragma: no cover -- requires a live browser
    """Read visible accessible names via ROLE locators (not a pixel screenshot).

    ``page.accessibility`` does not exist in playwright 1.61 (measured), so role
    locators are the a11y-tree access path.
    """
    names: list[str] = []
    for role in roles:
        locator = page.get_by_role(role)
        for index in range(min(locator.count(), limit)):
            item = locator.nth(index)
            if not item.is_visible():
                continue
            text = (item.get_attribute("aria-label") or item.inner_text() or "").strip()
            if text:
                names.append(text)
    return names


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
