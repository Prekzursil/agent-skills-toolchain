#!/usr/bin/env python3
"""Keyed search-API lane for the search-hub (platform ``keyed``): OPT-IN, DEFAULT OFF.

Gem-hunt program, Wave 4, decisions G-2 and G-6 (``docs/plans/2026-09-02-search-
research-tools-gemhunt.md``): every vendor that needs a paid key is allowed, but
only behind a HARD spend cap, with secrets read by env NAME only, and nothing
wired until the owner opts in per vendor. Twelve vendors ride ONE mechanism --
``KeyedSearchAdapter`` below, a ``SelfHostedAdapter`` sibling that is in-process
stdlib HTTP (no child, no new dependency, ~0 MB at rest) -- so the hub gains no
process and no import, and every tool degrades truthfully.

Opt-in contract (nothing bills until BOTH are set)
--------------------------------------------------
A vendor is wired only when ``ENABLE_KEYED_<VENDOR>=1`` AND its key env is
non-empty (``BRAVE_API_KEY``, ``KAGI_API_KEY``, ``LINKUP_API_KEY``,
``MOJEEK_API_KEY``, ``YOUCOM_API_KEY``, ``PERPLEXITY_API_KEY``,
``MARGINALIA_API_KEY``, ``SERPER_API_KEY``, ``SERPAPI_API_KEY``,
``DATAFORSEO_LOGIN`` + ``DATAFORSEO_PASSWORD``, ``ZENSERP_API_KEY``,
``SCRAPINGBEE_API_KEY``). The value is read once, sent only where the vendor
documents it (header, query parameter or HTTP basic), never logged, never written
to disk, and scrubbed from every text this lane emits (an upstream body that
echoes it comes back as ``[redacted]``); the only surface is the boolean
``authenticated``. ``<VENDOR>_API_URL`` overrides the base URL (config, not a
secret) so the tests point each adapter at a loopback fake.

Hard spend cap (G-2)
--------------------
Every call FIRST reserves against a small JSON ledger (``KEYED_LEDGER_PATH``,
default ``caches/keyed-ledger.json``, git-ignored; call counts + estimated USD,
never a key): a per-vendor daily call budget ``KEYED_MAX_CALLS_PER_DAY``
(default 200) and a global per-calendar-month ``KEYED_SPEND_CAP_USD`` (default
5.00) estimated from the ``PRICE_PER_1K`` list-price table (unknown price ->
counted, not priced). A refused call makes NO request and names the cap and its
reset time. Every ATTEMPTED call counts, including failed ones, because most
vendors bill non-2xx answers too and the safe side of a hard cap is the
conservative one. Ledger writes are atomic (temp file + ``os.replace``); an
unreadable ledger is renamed aside, started fresh and reported once.

Honesty contract
----------------
No probe is ever made (a probe to a keyed vendor can bill): ``capabilities``
reports configuration only. 401/402/403/429/5xx and non-JSON answers are
``isError`` with the vendor's own message (scrubbed) and ``Retry-After`` relayed;
an unrecognised 200 shape is an error, not an empty success; results are never
fabricated. Every hit is normalised to
``{title, url, snippet, published?, score?, vendor}`` and every payload carries
``raw_count``, ``latency_ms``, ``credits_hint`` (vendor quota headers/fields when
present) and ``spend`` (the reservation just made).

The five SERP scrapers (Serper, SerpApi, DataForSEO, ZenSerp, ScrapingBee) carry
the Google-v-SerpApi legal shadow in every description: they scrape Google and
add no index the keyless SearXNG route lacks.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import quote, urlencode

import adapters
from adapters import NATIVE, AdapterTool, HeaderCaller, SelfHostedAdapter

_HERE = os.path.dirname(os.path.abspath(__file__))

LANE_TIMEOUT = 30.0
USER_AGENT = adapters.USER_AGENT

# ---- cap / ledger configuration (env NAMES; the values are numbers, not secrets)
MAX_CALLS_ENV = "KEYED_MAX_CALLS_PER_DAY"
SPEND_CAP_ENV = "KEYED_SPEND_CAP_USD"
LEDGER_PATH_ENV = "KEYED_LEDGER_PATH"
DEFAULT_MAX_CALLS_PER_DAY = 200
DEFAULT_SPEND_CAP_USD = 5.00
DEFAULT_LEDGER_PATH = os.path.join(_HERE, "caches", "keyed-ledger.json")
LEDGER_VERSION = 1
LEDGER_KEEP_DAYS = 7
LEDGER_KEEP_MONTHS = 3

# Assumed LIST prices in USD per 1,000 calls, from the vendor pricing pages read
# 2026-09-02 (URL per vendor in README.md, "Keyed search APIs"). Pay-per-use
# vendors use their published rate; subscription vendors use the SMALLEST PAID
# plan's effective per-call price rounded UP to the cent (the plan a low-volume
# owner behind a $5/month cap plausibly holds -- larger plans are cheaper per
# call, so the estimate errs high, never low). ``None`` means the vendor
# publishes no per-call price (Marginalia's commercial key is metered via its
# portal): such calls are COUNTED against the daily budget but add $0 to the
# monthly estimate, and the README says so. Per-argument surcharges (Linkup deep,
# Serper num>10, DataForSEO depth pages + search operators, ScrapingBee
# light_request=false) live in the adapters' ``_price_per_1k``.
PRICE_PER_1K: dict[str, float | None] = {
    "brave_web_search": 5.00,  # $5 per 1,000 requests ($5 free credit every month)
    "brave_llm_context": 5.00,  # same Search plan as web search
    "kagi_search": 12.00,  # Search API v1: $12/1k requests, pay per use
    "kagi_enrich_web": 2.00,  # Enrich API: $2/1k searches
    "kagi_enrich_news": 2.00,
    "linkup_search": 5.00,  # standard depth $0.005/request; deep $0.006
    "mojeek_search": 2.70,  # GBP 2 CPM (Startup, <=10/request) at 1.35 USD/GBP; >10 -> Business GBP 3
    "youcom_search": 5.00,  # Web Search API $5.00 per 1,000 calls
    "perplexity_search": 5.00,  # Search API $5.00 per 1K requests
    "marginalia_search": None,  # metered commercial key, price not published
    "serper_search": 1.00,  # Starter top-up $50 / 50k credits; 1 credit per query
    "serpapi_search": 25.00,  # Starter plan $25 / 1,000 searches (Developer = $15/1k)
    "dataforseo_serp": 2.00,  # Live advanced $0.002 per SERP page of 10 results
    "zenserp_search": 2.00,  # Small plan $49.99 / 25,000 searches
    "scrapingbee_google": 2.54,  # light request = 10 credits; Hobby $19 / 75k credits
}
# DataForSEO multiplies the SERP price by 5 for EACH of these operators in the
# keyword (its rate card + the live/advanced field reference); the estimate
# follows the card.
_DATAFORSEO_OPERATOR_RE = re.compile(
    r"\b(?:allinanchor|allintext|allintitle|allinurl|cache|define|definition|"
    r"filetype|id|inanchor|info|intext|intitle|inurl|link|site):",
    re.IGNORECASE,
)

_LEGAL_SHADOW = (
    "LEGAL SHADOW: this is a third-party Google SERP scraper (Google is litigating "
    "exactly this practice in Google v. SerpApi); it adds NO index that the keyless "
    "SearXNG route lacks -- prefer searxng_web_search and use this only when you "
    "knowingly accept that exposure. "
)
_KEYED_TAIL = (
    "Returns results[title,url,snippet,published?,score?,vendor] + raw_count, "
    "latency_ms, credits_hint and spend. Refuses with a truthful error when the "
    f"daily call budget ({MAX_CALLS_ENV}) or the monthly spend cap ({SPEND_CAP_ENV}) "
    "is hit; 401/402/403/429/5xx are relayed truthfully (Retry-After included); "
    "the key is never echoed; results are never fabricated."
)

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_COUNTRY_RE = re.compile(r"^(ALL|[A-Za-z]{2})$")
_LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
_BRAVE_FRESHNESS = ("pd", "pw", "pm", "py")
_BRAVE_RANGE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}to\d{4}-\d{2}-\d{2}$")
_SCRUB = "[redacted]"
# Response headers relayed as ``credits_hint`` when present (lower-cased names).
_HINT_MARKERS = (
    "ratelimit",
    "rate-limit",
    "credit",
    "cost",
    "quota",
    "usage",
    "remaining",
    "retry-after",
    "balance",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_utc_midnight(now: datetime) -> datetime:
    day = now.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return day + timedelta(days=1)


def _first_of_next_month(now: datetime) -> datetime:
    now = now.astimezone(timezone.utc)
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _fmt_usd(value: float) -> str:
    """``5.0 -> "5.00"``, ``0.006 -> "0.006"``: at least two decimals, never a
    rounding that misstates a small cap (``0.006`` must not read ``0.01``)."""
    whole, _, frac = f"{value:.4f}".rstrip("0").partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


# --------------------------------------------------------------------------- #
# the spend ledger (G-2): counts + estimated USD, atomic, corruption-tolerant
# --------------------------------------------------------------------------- #
class Ledger:
    """JSON ledger of keyed calls: per-vendor daily counts, per-month estimated USD.

    One instance is shared by every adapter ``build`` returns, so the monthly cap
    is GLOBAL across vendors while the daily budget is per vendor. The file is
    re-read under a lock on every reservation (another hub process appending to
    the same file is seen, last writer wins -- documented, not solved: a
    cross-process file lock is not portable to every OS this repo runs on). It
    never holds a key: vendor names, integers and dollar estimates only.
    """

    def __init__(self, path: str, now: Callable[[], datetime] | None = None) -> None:
        self.path = path
        self._now = now or _utc_now
        self._lock = threading.Lock()
        self._notes: list[str] = []

    # ---- persistence ---------------------------------------------------------
    @staticmethod
    def _fresh() -> dict:
        return {
            "version": LEDGER_VERSION,
            "note": (
                "search-hub keyed-lane usage ledger: call counts and ESTIMATED USD "
                "from list prices; it never holds a key."
            ),
            "updated": None,
            "daily": {},
            "monthly": {},
        }

    @staticmethod
    def _valid(data) -> bool:
        return (
            isinstance(data, dict)
            and data.get("version") == LEDGER_VERSION
            and isinstance(data.get("daily"), dict)
            and isinstance(data.get("monthly"), dict)
        )

    def _load(self) -> dict:
        """Read the ledger; a missing file is fresh, an unreadable one is renamed
        aside (``<path>.corrupt-<stamp>``), reported once and started fresh."""
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return self._fresh()
        except (OSError, ValueError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
            data = None
        else:
            if self._valid(data):
                return data
            reason = "unexpected shape (not a version-1 ledger object)"
        aside = f"{self.path}.corrupt-{self._now().strftime('%Y%m%dT%H%M%SZ')}"
        try:
            os.replace(self.path, aside)
            moved = f"renamed aside to {aside}"
        except OSError as exc:
            moved = f"could not be renamed aside ({exc}); it will be overwritten"
        self._notes.append(
            f"keyed ledger at {self.path} was unreadable ({reason}); {moved} and a "
            f"fresh ledger was started -- counts before this point are not enforced."
        )
        return self._fresh()

    def _save(self, data: dict) -> None:
        """Atomic write: temp file beside the target, then ``os.replace``."""
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        tmp = f"{self.path}.tmp-{os.getpid()}-{threading.get_ident()}"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    @staticmethod
    def _prune(data: dict, day: str, month: str) -> None:
        days = sorted(k for k in data["daily"] if isinstance(k, str))
        for stale in days[:-LEDGER_KEEP_DAYS]:
            if stale != day:
                data["daily"].pop(stale, None)
        months = sorted(k for k in data["monthly"] if isinstance(k, str))
        for stale in months[:-LEDGER_KEEP_MONTHS]:
            if stale != month:
                data["monthly"].pop(stale, None)

    # ---- the cap -----------------------------------------------------------------
    def reserve(
        self,
        vendor: str,
        tool: str,
        price_per_1k: float | None,
        max_calls_per_day: int,
        cap_usd: float,
    ) -> tuple[dict | None, str | None]:
        """Count one attempted call BEFORE it is made: ``(granted, None)`` or
        ``(None, refusal)``. A refusal names the cap and its reset time."""
        now = self._now()
        day = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
        month = day[:7]
        daily_reset = _iso(_next_utc_midnight(now))
        monthly_reset = _iso(_first_of_next_month(now))
        estimate = None if price_per_1k is None else round(price_per_1k / 1000.0, 6)
        with self._lock:
            data = self._load()
            today = data["daily"].setdefault(day, {})
            calls_today = int(today.get(vendor, 0) or 0)
            if calls_today >= max_calls_per_day:
                return None, (
                    f"daily call budget for {vendor} reached: {calls_today}/"
                    f"{max_calls_per_day} attempted calls today ({MAX_CALLS_ENV}="
                    f"{max_calls_per_day}); resets at {daily_reset}. No request was "
                    f"made and nothing was billed; no results are fabricated."
                )
            this_month = data["monthly"].setdefault(
                month, {"calls": 0, "usd": 0.0, "vendors": {}}
            )
            month_usd = float(this_month.get("usd", 0.0) or 0.0)
            if estimate is not None and month_usd + estimate > cap_usd + 1e-9:
                return None, (
                    f"monthly spend cap reached: an estimated ${month_usd:.4f} is "
                    f"already spent across keyed vendors this month and this "
                    f"{vendor} call (~${estimate:.4f} at ${price_per_1k:.2f}/1k list "
                    f"price) would exceed {SPEND_CAP_ENV}={_fmt_usd(cap_usd)}; resets at "
                    f"{monthly_reset}. No request was made and nothing was billed; "
                    f"no results are fabricated."
                )
            today[vendor] = calls_today + 1
            this_month["calls"] = int(this_month.get("calls", 0) or 0) + 1
            this_month["usd"] = round(month_usd + (estimate or 0.0), 6)
            per_vendor = this_month.setdefault("vendors", {}).setdefault(
                vendor, {"calls": 0, "usd": 0.0}
            )
            per_vendor["calls"] = int(per_vendor.get("calls", 0) or 0) + 1
            per_vendor["usd"] = round(
                float(per_vendor.get("usd", 0.0) or 0.0) + (estimate or 0.0), 6
            )
            self._prune(data, day, month)
            data["updated"] = _iso(now)
            try:
                self._save(data)
            except OSError as exc:
                return None, (
                    f"cannot persist the keyed spend ledger at {self.path} ({exc}); "
                    f"refusing to call {vendor} because the spend cap cannot be "
                    f"enforced without it (set {LEDGER_PATH_ENV} to a writable "
                    f"path). No request was made."
                )
            return {
                "vendor": vendor,
                "tool": tool,
                "price_per_1k_usd": price_per_1k,
                "estimated_usd": estimate,
                "calls_today": today[vendor],
                "daily_budget": max_calls_per_day,
                "month_usd_estimated": this_month["usd"],
                "monthly_cap_usd": cap_usd,
                "resets": {"daily": daily_reset, "monthly": monthly_reset},
            }, None

    def snapshot(self, vendor: str, max_calls_per_day: int, cap_usd: float) -> dict:
        """The read-only view ``capabilities`` reports (no reservation made)."""
        now = self._now()
        day = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
        month = day[:7]
        with self._lock:
            data = self._load()
        calls_today = int((data["daily"].get(day) or {}).get(vendor, 0) or 0)
        this_month = data["monthly"].get(month) or {}
        month_usd = float(this_month.get("usd", 0.0) or 0.0)
        return {
            "ledger_path": self.path,
            "today": {
                "date": day,
                "calls": calls_today,
                "budget": max_calls_per_day,
                "remaining": max(max_calls_per_day - calls_today, 0),
                "resets": _iso(_next_utc_midnight(now)),
            },
            "month": {
                "month": month,
                "calls_all_vendors": int(this_month.get("calls", 0) or 0),
                "usd_estimated_all_vendors": month_usd,
                "cap_usd": cap_usd,
                "remaining_usd": round(max(cap_usd - month_usd, 0.0), 6),
                "resets": _iso(_first_of_next_month(now)),
            },
        }

    def pop_notes(self) -> list[str]:
        with self._lock:
            notes, self._notes = self._notes, []
        return notes


# --------------------------------------------------------------------------- #
# request / auth plumbing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Auth:
    """Where a vendor wants its key: ``header`` (name + optional prefix such as
    ``"Bearer "``), ``query`` (parameter name) or ``basic`` (``login:password``)."""

    kind: str
    name: str = ""
    prefix: str = ""

    def describe(self) -> str:
        if self.kind == "header":
            shown = f"{self.prefix}<key>" if self.prefix else "<key>"
            return f"header {self.name}: {shown}"
        if self.kind == "query":
            return f"query parameter {self.name}=<key> (never echoed)"
        return "HTTP basic auth (Authorization: Basic base64(login:password))"


@dataclass
class _Request:
    """One prepared, UNAUTHENTICATED call; auth is injected at send time only."""

    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    body: dict | list | None = None
    echo: dict = field(default_factory=dict)
    auth: Auth | None = None  # per-tool override of the vendor default


class _ShapeError(ValueError):
    """A 2xx body without the documented container: an error, never an empty win."""


def _text_or_none(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value) -> str | None:
    """Titles/snippets minus the vendors' HTML highlighting (Brave ``<strong>``,
    Kagi ``<b>``) and entities, whitespace collapsed; ``None`` when nothing is left."""
    if value is None:
        return None
    text = html.unescape(_TAG_RE.sub("", str(value)))
    return re.sub(r"\s+", " ", text).strip() or None


def _query_arg(args: dict, field_name: str, max_len: int, tag: str) -> str:
    value = args.get(field_name)
    text = str(value if value is not None else "").strip()
    if not text:
        raise ValueError(f"{tag}: '{field_name}' is required (the search query)")
    if _CONTROL_RE.search(text):
        raise ValueError(f"{tag}: '{field_name}' must not contain control characters")
    if len(text) > max_len:
        raise ValueError(
            f"{tag}: '{field_name}' is {len(text)} characters; at most {max_len} "
            f"are sent (no request was made)"
        )
    return text


def _code_arg(args: dict, field_name: str, pattern: re.Pattern, tag: str) -> str:
    value = args.get(field_name)
    text = str(value if value is not None else "").strip()
    if text and not pattern.match(text):
        raise ValueError(
            f"{tag}: '{field_name}' must match {pattern.pattern} (got {text!r})"
        )
    return text


def _choice_arg(
    args: dict, field_name: str, choices: tuple, default: str, tag: str
) -> str:
    value = args.get(field_name)
    text = str(value if value is not None else "").strip() or default
    if text not in choices:
        raise ValueError(f"{tag}: '{field_name}' must be one of {'|'.join(choices)}")
    return text


def _bool_arg(args: dict, field_name: str, default: bool, tag: str) -> bool:
    value = args.get(field_name, default)
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "1", "yes", "on"):
        return True
    if isinstance(value, str) and value.strip().lower() in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"{tag}: '{field_name}' must be a boolean")


def _message_of(parsed, raw: str) -> str:
    """The vendor's own error text from the common envelopes, else the raw head."""
    if isinstance(parsed, dict):
        for key in ("message", "error", "detail", "status_message", "errors", "msg"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                inner = value.get("message") or value.get("msg") or value.get("detail")
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
                return json.dumps(value, ensure_ascii=False)[:200]
            if isinstance(value, list) and value:
                bits = []
                for item in value:
                    if isinstance(item, dict):
                        bits.append(str(item.get("msg") or item.get("message") or item))
                    else:
                        bits.append(str(item))
                return "; ".join(bits)[:300]
    if isinstance(parsed, str) and parsed.strip():
        return parsed.strip()[:300]
    if raw:
        return re.sub(r"<[^>]+>", " ", raw)[:300].strip() or "(empty body)"
    return "(empty body)"


def _items(value) -> list:
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


# --------------------------------------------------------------------------- #
# the shared keyed adapter
# --------------------------------------------------------------------------- #
class KeyedSearchAdapter(SelfHostedAdapter):
    """Base for every keyed vendor: opt-in, capped, scrubbed, truthful.

    Subclasses declare ``vendor``/``label``/``default_url``/``key_envs``/``auth``
    and implement ``_build_tools``, ``_prepare_call`` (arguments -> ``_Request``,
    ValueError before any request is spent) and ``_normalize`` (2xx JSON ->
    ``(hits, raw_count, extras)``, ``_ShapeError`` on an unrecognised body).
    """

    platform = "keyed"
    label = "Keyed search API"
    prefix = "kd"
    kind = "native"  # documented vendor APIs, native shapes
    health_path = ""  # never probed: a probe to a keyed vendor can bill
    error_tag = "keyed"
    vendor = ""
    default_url = ""
    key_envs: tuple[str, ...] = ()
    auth = Auth("header", "Authorization", "Bearer ")
    legal_shadow = False
    timeout_s = LANE_TIMEOUT
    max_query_len = 400

    def __init__(
        self,
        base_url: str,
        secret: str,
        ledger: Ledger,
        caller: HeaderCaller | None = None,
        max_calls_per_day: int = DEFAULT_MAX_CALLS_PER_DAY,
        spend_cap_usd: float = DEFAULT_SPEND_CAP_USD,
    ) -> None:
        super().__init__(base_url or self.default_url)
        self._hcaller: HeaderCaller = caller or adapters._default_header_caller
        self._caller = lambda *a: self._hcaller(*a)[:3]
        self._secret = (secret or "").strip()
        self._ledger = ledger
        self.max_calls_per_day = max_calls_per_day
        self.spend_cap_usd = spend_cap_usd
        self.error_tag = f"keyed:{self.vendor}"
        self._scrub_terms = self._terms_for(self._secret)

    # ---- env names (config surface) ----------------------------------------
    @classmethod
    def flag_env(cls) -> str:
        return f"ENABLE_KEYED_{cls.vendor.upper()}"

    @classmethod
    def url_env(cls) -> str:
        return f"{cls.vendor.upper()}_API_URL"

    @classmethod
    def secret_from(cls, environ) -> str:
        """The key by env NAME; ``""`` when absent. Basic-auth vendors join
        ``login:password`` and need BOTH parts."""
        parts = []
        for name in cls.key_envs:
            value = environ.get(name)
            text = value.strip() if isinstance(value, str) else ""
            if not text:
                return ""
            parts.append(text)
        return ":".join(parts)

    # ---- secrecy --------------------------------------------------------------
    def _terms_for(self, secret: str) -> tuple[str, ...]:
        if not secret or self._placeholder():
            return ()
        terms = {secret, quote(secret, safe=""), json.dumps(secret)[1:-1]}
        if self.auth.kind == "basic":
            terms.add(base64.b64encode(secret.encode("utf-8")).decode("ascii"))
            for part in secret.split(":", 1):
                terms.add(part)
                terms.add(quote(part, safe=""))
        # A 1-3 character "key" is not a credential any vendor issues; scrubbing it
        # would shred every digit in the JSON payload, so only real-length terms go.
        return tuple(sorted((t for t in terms if len(t) >= 4), key=len, reverse=True))

    def _placeholder(self) -> bool:
        """A value that is not really a key (vendor hook; Marginalia's ``public``)."""
        return False

    @property
    def authenticated(self) -> bool:
        return bool(self._secret) and not self._placeholder()

    def _scrub(self, text: str) -> str:
        for term in self._scrub_terms:
            text = text.replace(term, _SCRUB)
        return text

    def _error(self, text: str) -> dict:
        return super()._error(self._scrub(text))

    def _ok(self, payload) -> dict:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            "content": [{"type": "text", "text": self._scrub(text)}],
            "isError": False,
        }

    # ---- capability lattice (never probes) -----------------------------------
    def probe(self) -> tuple[bool, str]:
        return (
            self.authenticated,
            "not probed: a request to a keyed vendor can bill, so this reports "
            f"configuration only (key configured: {self.authenticated})",
        )

    def capabilities(self, probe: bool = False) -> dict:
        report = super().capabilities(probe=False)
        report["self_hosted"] = False
        report["keyless"] = False
        report["vendor"] = self.vendor
        report["authenticated"] = self.authenticated
        report["auth_env"] = " + ".join(self.key_envs) + " (value never shown)"
        report["auth_placement"] = self.auth.describe()
        report["flag_env"] = self.flag_env()
        report["url_env"] = self.url_env()
        report["legal_shadow"] = self.legal_shadow
        report["probed"] = False
        report["probe_note"] = self.probe()[1]
        report["price_per_1k_usd"] = {
            t.name: self._price_per_1k(t, {}) for t in self._tools
        }
        report["spend"] = self._ledger.snapshot(
            self.vendor, self.max_calls_per_day, self.spend_cap_usd
        )
        return report

    # ---- vendor hooks -------------------------------------------------------------
    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        raise NotImplementedError  # pragma: no cover - every vendor overrides

    def _normalize(
        self, tool: AdapterTool, args: dict, parsed, headers: dict[str, str]
    ) -> tuple[list[dict], int, dict]:
        raise NotImplementedError  # pragma: no cover - every vendor overrides

    def _price_per_1k(self, tool: AdapterTool, args: dict) -> float | None:
        return PRICE_PER_1K.get(tool.name)

    def _body_credits(self, parsed) -> dict:
        return {}

    # ---- helpers for the vendors -------------------------------------------------
    def _hit(self, title, url, snippet, published=None, score=None, **extra) -> dict:
        hit = {
            "title": _clean_text(title),
            "url": _text_or_none(url),
            "snippet": _clean_text(snippet),
            "vendor": self.vendor,
        }
        if published not in (None, ""):
            hit["published"] = str(published)
        if score is not None:
            hit["score"] = score
        for key, value in extra.items():
            if value not in (None, "", [], {}):
                hit[key] = value
        return hit

    def _query(self, args: dict, field_name: str = "q") -> str:
        return _query_arg(args, field_name, self.max_query_len, self.label)

    def _credits_hint(self, headers: dict[str, str], parsed) -> dict | None:
        hint: dict = {}
        for key, value in headers.items():
            lowered = key.lower()
            if any(marker in lowered for marker in _HINT_MARKERS):
                hint[lowered] = value
        for key, value in self._body_credits(parsed).items():
            if value is not None:
                hint[key] = value
        return hint or None

    # ---- auth injection + transport ------------------------------------------------
    def _authorize(self, req: _Request) -> tuple[str, str, bytes | None, dict]:
        auth = req.auth or self.auth
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        query = dict(req.query)
        if auth.kind == "header":
            headers[auth.name] = f"{auth.prefix}{self._secret}"
        elif auth.kind == "query":
            query[auth.name] = self._secret
        elif auth.kind == "basic":
            token = base64.b64encode(self._secret.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        else:  # pragma: no cover - a programming error, not a runtime state
            raise ValueError(f"{self.label}: unknown auth kind {auth.kind!r}")
        body = None
        if req.body is not None:
            body = json.dumps(req.body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = self.base_url + req.path
        if query:
            url = f"{url}?{urlencode(query)}"
        return req.method, url, body, headers

    def _problem(
        self, status: int, parsed, raw: str, headers: dict[str, str], path: str
    ) -> str | None:
        """The isError text for a non-usable answer, or None when it is usable."""
        env = " + ".join(self.key_envs)
        if status == 0:
            return (
                f"{self.label} at {self.base_url} not reachable ({raw}); the attempt "
                f"was counted against the daily budget (conservative). No results are "
                f"fabricated."
            )
        message = _message_of(parsed, raw)
        hint = self._credits_hint(headers, parsed if isinstance(parsed, dict) else None)
        retry = headers.get("retry-after")
        retry_text = f"; retry-after {retry}s" if retry else ""
        hint_text = f"; vendor headers {json.dumps(hint)}" if hint else ""
        if status == 401:
            return (
                f"{self.label} HTTP 401 for {path}: the key in {env} was rejected "
                f"(value never shown). Vendor said: {message}. Check the key and the "
                f"plan; no results are fabricated."
            )
        if status == 402:
            return (
                f"{self.label} HTTP 402 payment required for {path}: the vendor "
                f"account behind {env} is out of credit or needs a payment method. "
                f"Vendor said: {message}{hint_text}. No results are fabricated."
            )
        if status == 403:
            return (
                f"{self.label} HTTP 403 forbidden for {path}: the key in {env} lacks "
                f"access to this endpoint or plan (or the quota is exhausted). Vendor "
                f"said: {message}{hint_text}{retry_text}. No results are fabricated."
            )
        if status == 429:
            return (
                f"{self.label} rate limit hit: HTTP 429 for {path}{retry_text}"
                f"{hint_text}. Vendor said: {message}. Wait for the window to reset; "
                f"the attempt counted against the daily budget. No results are "
                f"fabricated."
            )
        if status >= 500:
            return (
                f"{self.label} upstream failure: HTTP {status} for {path}"
                f"{retry_text}. Vendor said: {message}. No results are fabricated."
            )
        if not (200 <= status < 300):
            return (
                f"{self.label} returned HTTP {status} for {path}: {message}"
                f"{hint_text}. No results are fabricated."
            )
        if parsed is None:
            return (
                f"{self.label} returned HTTP {status} for {path} but the body is not "
                f"JSON ({raw[:120]!r}); no results are fabricated."
            )
        return None

    # ---- the call path (always truthful) -------------------------------------------
    def handle_call(self, name: str, arguments: dict) -> dict:
        tool = self._tool(name)
        if tool is None:
            return self._error(f"unknown keyed tool {name!r}")
        env = " + ".join(self.key_envs)
        if not self._secret:
            return self._error(
                f"{self.label} is not configured: set {self.flag_env()}=1 AND a "
                f"non-empty {env} (the value is never shown). No request was made."
            )
        args = arguments or {}
        try:
            req = self._prepare_call(tool, args)
        except ValueError as exc:
            return self._error(str(exc))
        price = self._price_per_1k(tool, args)
        granted, refusal = self._ledger.reserve(
            self.vendor, name, price, self.max_calls_per_day, self.spend_cap_usd
        )
        if refusal:
            return self._error(refusal)
        method, url, body, headers = self._authorize(req)
        started = time.monotonic()
        status, parsed, raw, resp_headers = self._hcaller(
            method, url, body, headers, self.timeout_s
        )
        latency_ms = int(round((time.monotonic() - started) * 1000))
        lowered = {str(k).lower(): str(v) for k, v in (resp_headers or {}).items()}
        problem = self._problem(status, parsed, raw or "", lowered, req.path)
        if problem:
            return self._error(problem)
        try:
            hits, raw_count, extras = self._normalize(tool, args, parsed, lowered)
        except ValueError as exc:
            keys = (
                sorted(parsed)[:12]
                if isinstance(parsed, dict)
                else type(parsed).__name__
            )
            return self._error(
                f"{self.label} answered HTTP {status} for {req.path} but the body is "
                f"not the documented shape ({exc}; top-level keys {keys}); no "
                f"results are fabricated."
            )
        payload = {
            "tool": name,
            "vendor": self.vendor,
            **req.echo,
            "count": len(hits),
            "raw_count": raw_count,
            "results": hits,
            "latency_ms": latency_ms,
            "credits_hint": self._credits_hint(lowered, parsed),
            "authenticated": self.authenticated,
            "spend": granted,
        }
        payload.update(extras)
        notes = self._ledger.pop_notes()
        if notes:
            payload["ledger_notes"] = notes
        return self._ok(payload)


def _tool(
    name: str, description: str, schema: dict, path: str, method: str
) -> AdapterTool:
    return AdapterTool(
        name=name,
        description=description,
        input_schema=schema,
        path=path,
        realized_by=NATIVE,
        method=method,
    )


def _keyed_prefix(vendor_label: str, flag: str, key_env: str) -> str:
    return (
        f"KEYED: bills the owner's {vendor_label} account (opt-in: {flag}=1 + "
        f"{key_env}; default OFF). "
    )


def _count_schema(name: str, lo: int, hi: int, default: int, what: str) -> dict:
    return {
        name: {
            "type": "integer",
            "minimum": lo,
            "maximum": hi,
            "default": default,
            "description": f"{what} ({lo}-{hi})",
        }
    }


_Q = {"q": {"type": "string", "description": "the search query"}}
_COUNTRY = {
    "country": {
        "type": "string",
        "default": "",
        "description": "ISO 3166-1 alpha-2 country code, e.g. 'US' (optional)",
    }
}


# --------------------------------------------------------------------------- #
# Brave Search API -- https://api-dashboard.search.brave.com/app/documentation
# --------------------------------------------------------------------------- #
class BraveAdapter(KeyedSearchAdapter):
    vendor = "brave"
    label = "Brave Search API"
    default_url = "https://api.search.brave.com"
    key_envs = ("BRAVE_API_KEY",)
    auth = Auth("header", "X-Subscription-Token")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("Brave Search API", self.flag_env(), "BRAVE_API_KEY")
        return [
            _tool(
                "brave_web_search",
                head + "Independent-index web search via GET /res/v1/web/search "
                "(q, count<=20, offset, country, search_lang, freshness=pd|pw|pm|py|"
                "YYYY-MM-DDtoYYYY-MM-DD); ~$5/1k list price, $5/mo free credit. "
                + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        **_count_schema("count", 1, 20, 10, "results to return"),
                        "offset": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 9,
                            "default": 0,
                            "description": "page offset (0-9)",
                        },
                        **_COUNTRY,
                        "search_lang": {
                            "type": "string",
                            "default": "",
                            "description": "language code, e.g. 'en' (optional)",
                        },
                        "freshness": {
                            "type": "string",
                            "default": "",
                            "description": "pd|pw|pm|py or YYYY-MM-DDtoYYYY-MM-DD",
                        },
                    },
                    "required": ["q"],
                },
                "/res/v1/web/search",
                "GET",
            ),
            _tool(
                "brave_llm_context",
                head + "Grounding snippets for an LLM via GET /res/v1/llm/context (q, "
                "country, search_lang): each hit carries url/title plus its extracted "
                "snippets (first one as snippet, all as snippets). Assumed ~$5/1k "
                "(same Search plans). " + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        **_COUNTRY,
                        "search_lang": {
                            "type": "string",
                            "default": "",
                            "description": "language code, e.g. 'en' (optional)",
                        },
                    },
                    "required": ["q"],
                },
                "/res/v1/llm/context",
                "GET",
            ),
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        tag = self.label
        q = self._query(args)
        query = {"q": q}
        echo: dict = {"q": q}
        country = _code_arg(args, "country", _COUNTRY_RE, tag)
        lang = _code_arg(args, "search_lang", _LANG_RE, tag)
        if tool.name == "brave_web_search":
            count = adapters._int_arg(args, "count", 10, 1, 20, tag)
            offset = adapters._int_arg(args, "offset", 0, 0, 9, tag)
            query["count"] = str(count)
            echo["count"] = count
            if offset:
                query["offset"] = str(offset)
                echo["offset"] = offset
            fresh = str(args.get("freshness") or "").strip()
            if (
                fresh
                and fresh not in _BRAVE_FRESHNESS
                and not _BRAVE_RANGE_RE.match(fresh)
            ):
                raise ValueError(
                    f"{tag}: 'freshness' must be pd|pw|pm|py or YYYY-MM-DDtoYYYY-MM-DD"
                )
            if fresh:
                query["freshness"] = fresh
                echo["freshness"] = fresh
        if country:
            query["country"] = country.upper() if country != "ALL" else country
        if lang:
            query["search_lang"] = lang
        return _Request("GET", tool.path, query, None, echo)

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict):
            raise _ShapeError("body is not a JSON object")
        if tool.name == "brave_llm_context":
            grounding = parsed.get("grounding")
            if isinstance(grounding, dict):
                # ``generic``/``map`` are lists; the local-recall ``poi`` block is
                # ONE object (docs, read 2026-09-02) -- both become hits.
                items: list[tuple[str, dict]] = []
                for section, value in grounding.items():
                    if isinstance(value, dict) and value.get("url"):
                        value = [value]
                    items.extend((str(section), i) for i in _items(value))
                hits = []
                for section, item in items:
                    snippets = [
                        str(s) for s in (item.get("snippets") or []) if str(s).strip()
                    ]
                    hits.append(
                        self._hit(
                            item.get("title"),
                            item.get("url"),
                            snippets[0] if snippets else item.get("description"),
                            section=section,
                            name=item.get("name"),
                            snippets=snippets,
                        )
                    )
                return hits, len(items), {"shape": "grounding"}
        web = parsed.get("web")
        if not isinstance(web, dict) or not isinstance(web.get("results"), list):
            if tool.name == "brave_web_search" and "query" in parsed:
                return [], 0, {"note": "Brave returned no web block for this query"}
            raise _ShapeError("neither web.results nor grounding present")
        items = _items(web.get("results"))
        hits = [
            self._hit(
                i.get("title"),
                i.get("url"),
                i.get("description"),
                published=i.get("page_age"),
                age=i.get("age"),
                extra_snippets=i.get("extra_snippets"),
            )
            for i in items
        ]
        extras: dict = {"shape": "web.results"}
        query = parsed.get("query")
        if isinstance(query, dict):
            extras["query_info"] = {
                k: query.get(k)
                for k in ("original", "altered", "more_results_available")
                if query.get(k) is not None
            }
        return hits, len(items), extras


# --------------------------------------------------------------------------- #
# Kagi -- Search API v1: https://kagi.com/api/docs (OpenAPI, HTTP bearer, POST
# /api/v1/search); Enrich v0: https://help.kagi.com/kagi/api/enrich.html (GET,
# "Authorization: Bot"). Two contracts, one key -- the tools carry their own.
# --------------------------------------------------------------------------- #
_KAGI_BOT = Auth("header", "Authorization", "Bot ")


class KagiAdapter(KeyedSearchAdapter):
    vendor = "kagi"
    label = "Kagi API"
    default_url = "https://kagi.com"
    key_envs = ("KAGI_API_KEY",)
    # v1 /search declares an HTTP bearer scheme; the v0 Enrich tools override it
    # per request with the "Bot" scheme their help pages document.
    auth = Auth("header", "Authorization", "Bearer ")

    def capabilities(self, probe: bool = False) -> dict:
        report = super().capabilities(probe=probe)
        report["auth_placement"] = (
            f"{self.auth.describe()} for /api/v1/search; "
            f"{_KAGI_BOT.describe()} for /api/v0/enrich/*"
        )
        return report

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("Kagi", self.flag_env(), "KAGI_API_KEY")
        enrich_schema = {"type": "object", "properties": {**_Q}, "required": ["q"]}
        return [
            _tool(
                "kagi_search",
                head + "Kagi premium web search via POST /api/v1/search (JSON body "
                "{query, limit<=100, page<=10}; Authorization: Bearer). The v1 answer "
                "is sectioned: search/news/adjacent_question items become hits tagged "
                "with their section, related_search titles come back as "
                "related_searches, and the per-section counts as sections. $12/1k "
                "list price. " + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        **_count_schema("limit", 1, 100, 10, "results to return"),
                        "page": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 1,
                            "description": "result page (1-10)",
                        },
                    },
                    "required": ["q"],
                },
                "/api/v1/search",
                "POST",
            ),
            _tool(
                "kagi_enrich_web",
                head + "Kagi Enrich WEB: the small-web / Teclis index via GET "
                "/api/v0/enrich/web?q= (Authorization: Bot). $2/1k list price, "
                "billed on non-empty answers. " + _KEYED_TAIL,
                enrich_schema,
                "/api/v0/enrich/web",
                "GET",
            ),
            _tool(
                "kagi_enrich_news",
                head + "Kagi Enrich NEWS: the TinyGem small-web news index via GET "
                "/api/v0/enrich/news?q= (Authorization: Bot). $2/1k list price, "
                "billed on non-empty answers. " + _KEYED_TAIL,
                enrich_schema,
                "/api/v0/enrich/news",
                "GET",
            ),
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        q = self._query(args)
        if tool.name == "kagi_search":
            limit = adapters._int_arg(args, "limit", 10, 1, 100, self.label)
            page = adapters._int_arg(args, "page", 1, 1, 10, self.label)
            body: dict = {"query": q, "limit": limit}
            if page > 1:
                body["page"] = page
            echo = {"q": q, "limit": limit, "page": page}
            return _Request("POST", tool.path, {}, body, echo)
        return _Request("GET", tool.path, {"q": q}, None, {"q": q}, auth=_KAGI_BOT)

    def _body_credits(self, parsed) -> dict:
        # v0 Enrich meta carries ``api_balance``; the v1 meta is trace/node/ms only.
        meta = parsed.get("meta") if isinstance(parsed, dict) else None
        if isinstance(meta, dict) and meta.get("api_balance") is not None:
            return {"api_balance": meta.get("api_balance")}
        return {}

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict) or "data" not in parsed:
            raise _ShapeError("no 'data' key")
        data = parsed.get("data")
        extras: dict = {}
        if isinstance(data, list):
            # v0 Enrich: a LIST of ``{t: 0, rank, url, title, snippet, published}``;
            # a ``t: 1`` entry carries the related-search list.
            items: list[dict] = []
            related: list = []
            for item in _items(data):
                if item.get("t") == 1:
                    related.extend(item.get("list") or [])
                elif item.get("t") in (0, None):
                    items.append(item)
            hits = [
                self._hit(
                    i.get("title"),
                    i.get("url"),
                    i.get("snippet"),
                    published=i.get("published"),
                    position=i.get("rank"),
                )
                for i in items
            ]
            raw_count = len(items)
        elif isinstance(data, dict):
            # v1 Search: an OBJECT of sections, each a list of
            # ``{url, title, snippet?, time?, props?}``; ``related_search`` entries
            # are query suggestions, not pages, so they are counted but surfaced
            # as related_searches instead of hits.
            hits = []
            related = []
            sections: dict[str, int] = {}
            raw_count = 0
            for section, value in data.items():
                if not isinstance(value, list):
                    continue
                entries = _items(value)
                sections[str(section)] = len(entries)
                raw_count += len(entries)
                if section == "related_search":
                    related.extend(e.get("title") or e.get("url") for e in entries)
                    continue
                for entry in entries:
                    props = entry.get("props")
                    props = props if isinstance(props, dict) else {}
                    hits.append(
                        self._hit(
                            entry.get("title"),
                            entry.get("url"),
                            entry.get("snippet"),
                            published=entry.get("time"),
                            section=str(section),
                            question=props.get("question"),
                        )
                    )
            if sections:
                extras["sections"] = sections
        else:
            raise _ShapeError("'data' is neither a list nor an object")
        if related:
            extras["related_searches"] = [str(r) for r in related if r][:20]
        meta = parsed.get("meta")
        if isinstance(meta, dict):
            if meta.get("trace") is not None:
                extras["upstream_trace"] = meta.get("trace")
            if meta.get("ms") is not None:
                extras["upstream_ms"] = meta.get("ms")
        return hits, raw_count, extras


# --------------------------------------------------------------------------- #
# Linkup -- https://docs.linkup.so/pages/documentation/api-reference/endpoint/post-search
# --------------------------------------------------------------------------- #
class LinkupAdapter(KeyedSearchAdapter):
    vendor = "linkup"
    label = "Linkup"
    default_url = "https://api.linkup.so"
    key_envs = ("LINKUP_API_KEY",)
    auth = Auth("header", "Authorization", "Bearer ")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("Linkup", self.flag_env(), "LINKUP_API_KEY")
        return [
            _tool(
                "linkup_search",
                head + "Agent web search via POST /v1/search (q, depth=standard|deep, "
                "output_type=searchResults|sourcedAnswer; Bearer). searchResults "
                "normalises results[name,url,content]; sourcedAnswer returns the "
                "answer plus its sources as hits. ~$5/1k standard, ~$6/1k deep. "
                + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        "depth": {
                            "type": "string",
                            "enum": ["standard", "deep"],
                            "default": "standard",
                        },
                        "output_type": {
                            "type": "string",
                            "enum": ["searchResults", "sourcedAnswer"],
                            "default": "searchResults",
                        },
                        "include_images": {"type": "boolean", "default": False},
                    },
                    "required": ["q"],
                },
                "/v1/search",
                "POST",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        tag = self.label
        q = self._query(args)
        depth = _choice_arg(args, "depth", ("standard", "deep"), "standard", tag)
        output = _choice_arg(
            args,
            "output_type",
            ("searchResults", "sourcedAnswer"),
            "searchResults",
            tag,
        )
        images = _bool_arg(args, "include_images", False, tag)
        body = {"q": q, "depth": depth, "outputType": output, "includeImages": images}
        echo = {"q": q, "depth": depth, "output_type": output}
        return _Request("POST", tool.path, {}, body, echo)

    def _price_per_1k(self, tool: AdapterTool, args: dict) -> float | None:
        base = PRICE_PER_1K.get(tool.name)
        if base is not None and str((args or {}).get("depth") or "").strip() == "deep":
            return 6.00
        return base

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict):
            raise _ShapeError("body is not a JSON object")
        if isinstance(parsed.get("results"), list):
            items = _items(parsed["results"])
            hits = [
                self._hit(
                    i.get("name"),
                    i.get("url"),
                    i.get("content"),
                    type=i.get("type"),
                )
                for i in items
            ]
            return hits, len(items), {"shape": "searchResults"}
        if "answer" in parsed:
            sources = _items(parsed.get("sources"))
            hits = [
                self._hit(s.get("name"), s.get("url"), s.get("snippet"))
                for s in sources
            ]
            return (
                hits,
                len(sources),
                {"shape": "sourcedAnswer", "answer": parsed.get("answer")},
            )
        raise _ShapeError("neither 'results' nor 'answer' present")


# --------------------------------------------------------------------------- #
# Mojeek -- https://www.mojeek.com/support/api/search/request_parameters.html
# --------------------------------------------------------------------------- #
class MojeekAdapter(KeyedSearchAdapter):
    vendor = "mojeek"
    label = "Mojeek Search API"
    default_url = "https://www.mojeek.com"
    key_envs = ("MOJEEK_API_KEY",)
    auth = Auth("query", "api_key")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("Mojeek", self.flag_env(), "MOJEEK_API_KEY")
        return [
            _tool(
                "mojeek_search",
                head + "Independent-index (UK) web search via GET /search?fmt=json (q, "
                "count<=40 as t=; api_key query parameter, never echoed). The plans "
                "cap results per request: Startup (GBP 2 CPM, ~$2.70/1k assumed) up "
                "to 10, Business (GBP 3 CPM, ~$4.05/1k) up to 40 -- so count>10 is "
                "estimated at the Business rate, and a Startup key may return fewer "
                "hits than asked. " + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        **_count_schema("count", 1, 40, 10, "results to return"),
                    },
                    "required": ["q"],
                },
                "/search",
                "GET",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        q = self._query(args)
        count = adapters._int_arg(args, "count", 10, 1, 40, self.label)
        query = {"q": q, "fmt": "json", "t": str(count)}
        return _Request("GET", tool.path, query, None, {"q": q, "count": count})

    def _price_per_1k(self, tool: AdapterTool, args: dict) -> float | None:
        """Plan table (read 2026-09-02): Startup GBP 2 CPM serves up to 10 results
        per request, Business GBP 3 CPM up to 40. More than 10 can only come from
        the dearer plan, so that is the rate assumed (errs high, never low)."""
        try:
            count = adapters._int_arg(args or {}, "count", 10, 1, 40, self.label)
        except ValueError:
            count = 10
        return 4.05 if count > 10 else PRICE_PER_1K.get(tool.name)

    def _normalize(self, tool, args, parsed, headers):
        response = parsed.get("response") if isinstance(parsed, dict) else None
        if not isinstance(response, dict) or not isinstance(
            response.get("results"), list
        ):
            raise _ShapeError("no response.results list")
        items = _items(response["results"])
        hits = [
            self._hit(
                i.get("title"),
                i.get("url"),
                i.get("desc"),
                published=i.get("mdate") or i.get("cdate"),
            )
            for i in items
        ]
        extras: dict = {}
        head = response.get("head")
        if isinstance(head, dict):
            extras["total_results"] = head.get("totalresults") or head.get("results")
        if response.get("status") is not None:
            extras["upstream_status"] = response.get("status")
        return hits, len(items), extras


# --------------------------------------------------------------------------- #
# You.com -- https://you.com/docs/api-reference/search/v1-search
# --------------------------------------------------------------------------- #
class YouComAdapter(KeyedSearchAdapter):
    vendor = "youcom"
    label = "You.com Search API"
    default_url = "https://ydc-index.io"
    key_envs = ("YOUCOM_API_KEY",)
    auth = Auth("header", "X-API-Key")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("You.com", self.flag_env(), "YOUCOM_API_KEY")
        return [
            _tool(
                "youcom_search",
                head + "Web + auto-classified news search via POST /v1/search (query, "
                "count<=100, country, language; X-API-Key header). Hits carry "
                "section=web|news. ~$5/1k ($100 free credit on signup). " + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        **_count_schema("count", 1, 100, 10, "results per section"),
                        **_COUNTRY,
                        "language": {
                            "type": "string",
                            "default": "",
                            "description": "BCP 47 language code, e.g. 'en' (optional)",
                        },
                    },
                    "required": ["q"],
                },
                "/v1/search",
                "POST",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        tag = self.label
        q = self._query(args)
        count = adapters._int_arg(args, "count", 10, 1, 100, tag)
        body: dict = {"query": q, "count": count}
        country = _code_arg(args, "country", _COUNTRY_RE, tag)
        language = _code_arg(args, "language", _LANG_RE, tag)
        if country and country != "ALL":
            body["country"] = country.upper()
        if language:
            body["language"] = language
        return _Request("POST", tool.path, {}, body, {"q": q, "count": count})

    def _normalize(self, tool, args, parsed, headers):
        results = parsed.get("results") if isinstance(parsed, dict) else None
        if not isinstance(results, dict):
            raise _ShapeError("no 'results' object")
        web = _items(results.get("web"))
        news = _items(results.get("news"))
        hits = [
            self._hit(
                i.get("title"),
                i.get("url"),
                i.get("description"),
                published=i.get("page_age"),
                section="web",
                snippets=[str(s) for s in (i.get("snippets") or [])],
            )
            for i in web
        ] + [
            self._hit(
                i.get("title"),
                i.get("url"),
                i.get("description"),
                published=i.get("page_age"),
                section="news",
            )
            for i in news
        ]
        return (
            hits,
            len(web) + len(news),
            {"web_count": len(web), "news_count": len(news)},
        )


# --------------------------------------------------------------------------- #
# Perplexity Search API -- https://docs.perplexity.ai/api-reference/search-post
# --------------------------------------------------------------------------- #
class PerplexityAdapter(KeyedSearchAdapter):
    vendor = "perplexity"
    label = "Perplexity Search API"
    default_url = "https://api.perplexity.ai"
    key_envs = ("PERPLEXITY_API_KEY",)
    auth = Auth("header", "Authorization", "Bearer ")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("Perplexity", self.flag_env(), "PERPLEXITY_API_KEY")
        return [
            _tool(
                "perplexity_search",
                head
                + "Raw ranked web results (NOT a Sonar chat answer) via POST /search "
                "(query, max_results<=20, country; Bearer). $5.00/1k requests list "
                "price. " + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        **_count_schema("max_results", 1, 20, 10, "results to return"),
                        **_COUNTRY,
                    },
                    "required": ["q"],
                },
                "/search",
                "POST",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        tag = self.label
        q = self._query(args)
        limit = adapters._int_arg(args, "max_results", 10, 1, 20, tag)
        body: dict = {"query": q, "max_results": limit}
        country = _code_arg(args, "country", _COUNTRY_RE, tag)
        if country and country != "ALL":
            body["country"] = country.upper()
        return _Request("POST", tool.path, {}, body, {"q": q, "max_results": limit})

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
            raise _ShapeError("no 'results' list")
        items = _items(parsed["results"])
        hits = [
            self._hit(
                i.get("title"),
                i.get("url"),
                i.get("snippet"),
                published=i.get("date"),
                last_updated=i.get("last_updated"),
            )
            for i in items
        ]
        extras = {"request_id": parsed.get("id")} if parsed.get("id") else {}
        return hits, len(items), extras


# --------------------------------------------------------------------------- #
# Marginalia (commercial key) -- https://about.marginalia-search.com/article/api/
# --------------------------------------------------------------------------- #
class MarginaliaAdapter(KeyedSearchAdapter):
    vendor = "marginalia"
    label = "Marginalia Search API"
    default_url = "https://api2.marginalia-search.com"
    key_envs = ("MARGINALIA_API_KEY",)
    auth = Auth("header", "API-Key")

    def _placeholder(self) -> bool:
        return self._secret.lower() == "public"

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("Marginalia", self.flag_env(), "MARGINALIA_API_KEY")
        return [
            _tool(
                "marginalia_search",
                head + "Small-web / non-commercial-web search via GET /search (query, "
                "count<=100; API-Key header) on the NEW api2 host -- the deprecated "
                "key-in-path api.marginalia.nu/{key}/search/{query} form is not used. "
                "The free shared 'public' key is the SearXNG route and is REFUSED "
                "here; a paid metered key has no published per-call price, so calls "
                "are counted against the daily budget but add $0 to the monthly "
                "estimate. " + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        **_count_schema("count", 1, 100, 10, "results to return"),
                    },
                    "required": ["q"],
                },
                "/search",
                "GET",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        if self._placeholder():
            raise ValueError(
                f"{self.label}: MARGINALIA_API_KEY is the shared keyless 'public' key. "
                f"That key is the SearXNG route (the marginalia engine behind "
                f"searxng_web_search) and stays there; this lane needs a paid key from "
                f"marginalia-search.com. No request was made."
            )
        q = self._query(args)
        count = adapters._int_arg(args, "count", 10, 1, 100, self.label)
        query = {"query": q, "count": str(count)}
        return _Request("GET", tool.path, query, None, {"q": q, "count": count})

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
            raise _ShapeError("no 'results' list")
        items = _items(parsed["results"])
        hits = [
            self._hit(i.get("title"), i.get("url"), i.get("description")) for i in items
        ]
        extras: dict = {}
        if parsed.get("license"):
            extras["license"] = parsed.get("license")
        return hits, len(items), extras


# --------------------------------------------------------------------------- #
# SERP scrapers (legal shadow in every description)
# --------------------------------------------------------------------------- #
_GL_HL = {
    "gl": {
        "type": "string",
        "default": "",
        "description": "Google country code, e.g. 'us' (optional)",
    },
    "hl": {
        "type": "string",
        "default": "",
        "description": "Google interface language, e.g. 'en' (optional)",
    },
}


def _serp_schema(paging: dict, extra: dict | None = None) -> dict:
    props = {**_Q, **paging, **_GL_HL}
    props.update(extra or {})
    return {"type": "object", "properties": props, "required": ["q"]}


class _SerpScraper(KeyedSearchAdapter):
    legal_shadow = True

    def _gl_hl(self, args: dict) -> tuple[str, str]:
        gl = _code_arg(args, "gl", _COUNTRY_RE, self.label)
        hl = _code_arg(args, "hl", _LANG_RE, self.label)
        return (gl.lower() if gl and gl != "ALL" else ""), hl


class SerperAdapter(_SerpScraper):
    vendor = "serper"
    label = "Serper (Google SERP scraper)"
    default_url = "https://google.serper.dev"
    key_envs = ("SERPER_API_KEY",)
    auth = Auth("header", "X-API-KEY")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("Serper", self.flag_env(), "SERPER_API_KEY")
        return [
            _tool(
                "serper_search",
                head
                + _LEGAL_SHADOW
                + "Google organic results via POST /search (q, num<=100, gl, hl; "
                "X-API-KEY header). $1/1k list price (1 credit; 2 credits when "
                "num>10). Google dropped its own num parameter in 2025, so more than "
                "10 hits per call is up to the vendor. " + _KEYED_TAIL,
                _serp_schema(_count_schema("num", 1, 100, 10, "results to return")),
                "/search",
                "POST",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        q = self._query(args)
        num = adapters._int_arg(args, "num", 10, 1, 100, self.label)
        gl, hl = self._gl_hl(args)
        body: dict = {"q": q, "num": num}
        if gl:
            body["gl"] = gl
        if hl:
            body["hl"] = hl
        return _Request("POST", tool.path, {}, body, {"q": q, "num": num})

    def _price_per_1k(self, tool: AdapterTool, args: dict) -> float | None:
        try:
            num = adapters._int_arg(args or {}, "num", 10, 1, 100, self.label)
        except ValueError:
            num = 10
        return 2.00 if num > 10 else PRICE_PER_1K.get(tool.name)

    def _body_credits(self, parsed) -> dict:
        if isinstance(parsed, dict) and parsed.get("credits") is not None:
            return {"credits": parsed.get("credits")}
        return {}

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict) or not (
            isinstance(parsed.get("organic"), list) or "searchParameters" in parsed
        ):
            raise _ShapeError("no 'organic' list / searchParameters envelope")
        items = _items(parsed.get("organic"))
        hits = [
            self._hit(
                i.get("title"),
                i.get("link"),
                i.get("snippet"),
                published=i.get("date"),
                position=i.get("position"),
            )
            for i in items
        ]
        return hits, len(items), {}


class SerpApiAdapter(_SerpScraper):
    vendor = "serpapi"
    label = "SerpApi (Google SERP scraper)"
    default_url = "https://serpapi.com"
    key_envs = ("SERPAPI_API_KEY",)
    auth = Auth("query", "api_key")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("SerpApi", self.flag_env(), "SERPAPI_API_KEY")
        return [
            _tool(
                "serpapi_search",
                head
                + _LEGAL_SHADOW
                + "Google organic results via GET /search.json?engine=google (q, "
                "start=result offset for paging: 0, 10, 20 ...; gl, hl; api_key query "
                "parameter, never echoed). One SERP page (~10 hits) per call: SerpApi's "
                "docs no longer list a num parameter since Google dropped it in 2025. "
                "~$25/1k assumed (Starter plan $25 / 1,000 searches; Developer $75 / "
                "5,000 = $15/1k; the free tier is 250 searches/month). " + _KEYED_TAIL,
                _serp_schema(
                    {
                        "start": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 990,
                            "default": 0,
                            "description": "result offset (0 = first page, 10 = second)",
                        }
                    }
                ),
                "/search.json",
                "GET",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        q = self._query(args)
        start = adapters._int_arg(args, "start", 0, 0, 990, self.label)
        gl, hl = self._gl_hl(args)
        query = {"engine": "google", "q": q}
        if start:
            query["start"] = str(start)
        if gl:
            query["gl"] = gl
        if hl:
            query["hl"] = hl
        return _Request("GET", tool.path, query, None, {"q": q, "start": start})

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict) or not (
            isinstance(parsed.get("organic_results"), list)
            or "search_metadata" in parsed
        ):
            raise _ShapeError("no 'organic_results' list / search_metadata envelope")
        items = _items(parsed.get("organic_results"))
        hits = [
            self._hit(
                i.get("title"),
                i.get("link"),
                i.get("snippet"),
                published=i.get("date"),
                position=i.get("position"),
            )
            for i in items
        ]
        extras: dict = {}
        meta = parsed.get("search_metadata")
        if isinstance(meta, dict):
            extras["search_metadata"] = {
                k: meta.get(k)
                for k in ("id", "status", "total_time_taken")
                if meta.get(k) is not None
            }
        if not items and isinstance(parsed.get("error"), str):
            extras["note"] = f"SerpApi said: {parsed['error']}"
        return hits, len(items), extras


class DataForSEOAdapter(_SerpScraper):
    vendor = "dataforseo"
    label = "DataForSEO (Google SERP scraper)"
    default_url = "https://api.dataforseo.com"
    key_envs = ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")
    auth = Auth("basic")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix(
            "DataForSEO", self.flag_env(), "DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD"
        )
        return [
            _tool(
                "dataforseo_serp",
                head
                + _LEGAL_SHADOW
                + "Google organic SERP via POST /v3/serp/google/organic/live/advanced "
                "(q as keyword, depth<=100, location_code default 2840=US, "
                "language_code default en; HTTP basic auth). Only items of type "
                "'organic' become hits; raw_count counts every SERP item. $2/1k list "
                "price per SERP page of 10 results: the estimate multiplies by "
                "ceil(depth/10) and by 5 for EACH search operator in q (site:, "
                "intitle:, inurl:, filetype:, ...) as the vendor's rate card does; "
                "the API's own 'cost' field is relayed. " + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        **_count_schema("depth", 1, 100, 10, "SERP depth"),
                        "location_code": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 2840,
                            "description": "DataForSEO location code (2840 = United States)",
                        },
                        "language_code": {
                            "type": "string",
                            "default": "en",
                            "description": "language code, e.g. 'en'",
                        },
                    },
                    "required": ["q"],
                },
                "/v3/serp/google/organic/live/advanced",
                "POST",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        tag = self.label
        q = self._query(args)
        depth = adapters._int_arg(args, "depth", 10, 1, 100, tag)
        location = adapters._int_arg(args, "location_code", 2840, 1, None, tag)
        language = _code_arg(args, "language_code", _LANG_RE, tag) or "en"
        body = [
            {
                "keyword": q,
                "location_code": location,
                "language_code": language,
                "depth": depth,
            }
        ]
        echo = {
            "q": q,
            "depth": depth,
            "location_code": location,
            "language_code": language,
        }
        return _Request("POST", tool.path, {}, body, echo)

    def _price_per_1k(self, tool: AdapterTool, args: dict) -> float | None:
        """Rate card (read 2026-09-02): the base price is per SERP page of 10
        results, ``depth`` rounds up to whole pages, and every search operator in
        the keyword multiplies the task by 5. Rounded up, never down."""
        base = PRICE_PER_1K.get(tool.name)
        if base is None:
            return None
        args = args or {}
        try:
            depth = adapters._int_arg(args, "depth", 10, 1, 100, self.label)
        except ValueError:
            depth = 10
        pages = -(-depth // 10)
        operators = len(_DATAFORSEO_OPERATOR_RE.findall(str(args.get("q") or "")))
        return round(base * pages * (5**operators), 6)

    def _body_credits(self, parsed) -> dict:
        if isinstance(parsed, dict) and parsed.get("cost") is not None:
            return {"cost": parsed.get("cost")}
        return {}

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict) or "status_code" not in parsed:
            raise _ShapeError("no DataForSEO status_code envelope")
        if parsed.get("status_code") != 20000:
            raise _ShapeError(
                f"API status {parsed.get('status_code')}: {parsed.get('status_message')}"
            )
        tasks = _items(parsed.get("tasks"))
        if not tasks:
            raise _ShapeError("no tasks in the answer")
        task = tasks[0]
        if task.get("status_code") != 20000:
            raise _ShapeError(
                f"task status {task.get('status_code')}: {task.get('status_message')}"
            )
        results = _items(task.get("result"))
        items = _items(results[0].get("items")) if results else []
        hits = [
            self._hit(
                i.get("title"),
                i.get("url"),
                i.get("description"),
                published=i.get("timestamp"),
                position=i.get("rank_absolute"),
            )
            for i in items
            if i.get("type") == "organic"
        ]
        extras: dict = {}
        if results:
            extras["items_count"] = results[0].get("items_count")
            extras["se_results_count"] = results[0].get("se_results_count")
        return hits, len(items), extras


class ZenSerpAdapter(_SerpScraper):
    vendor = "zenserp"
    label = "ZenSerp (Google SERP scraper)"
    default_url = "https://app.zenserp.com"
    key_envs = ("ZENSERP_API_KEY",)
    auth = Auth("header", "apikey")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("ZenSerp", self.flag_env(), "ZENSERP_API_KEY")
        return [
            _tool(
                "zenserp_search",
                head
                + _LEGAL_SHADOW
                + "Google organic results via GET /api/v2/search (q, num<=100, "
                "location, gl, hl; apikey header). Only organic entries with a URL "
                "become hits (question/video blocks are counted in raw_count). "
                "~$2/1k list price (Small plan). " + _KEYED_TAIL,
                _serp_schema(
                    _count_schema("num", 1, 100, 10, "results to return"),
                    {
                        "location": {
                            "type": "string",
                            "default": "",
                            "description": "Google canonical location, e.g. 'Paris,France'",
                        }
                    },
                ),
                "/api/v2/search",
                "GET",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        q = self._query(args)
        num = adapters._int_arg(args, "num", 10, 1, 100, self.label)
        gl, hl = self._gl_hl(args)
        query = {"q": q, "num": str(num)}
        location = str(args.get("location") or "").strip()
        if location:
            if _CONTROL_RE.search(location) or len(location) > 200:
                raise ValueError(
                    f"{self.label}: 'location' is not a valid location string"
                )
            query["location"] = location
        if gl:
            query["gl"] = gl
        if hl:
            query["hl"] = hl
        return _Request("GET", tool.path, query, None, {"q": q, "num": num})

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict) or not (
            isinstance(parsed.get("organic"), list) or "query" in parsed
        ):
            raise _ShapeError("no 'organic' list / query envelope")
        items = _items(parsed.get("organic"))
        hits = [
            self._hit(
                i.get("title"),
                i.get("url") or i.get("destination"),
                i.get("description"),
                published=i.get("date"),
                position=i.get("position"),
            )
            for i in items
            if i.get("url") or i.get("destination")
        ]
        return hits, len(items), {}


_SCRAPINGBEE_RANGES = ("past_hour", "past_day", "past_week", "past_month", "past_year")


class ScrapingBeeAdapter(_SerpScraper):
    vendor = "scrapingbee"
    label = "ScrapingBee Google API (SERP scraper)"
    default_url = "https://app.scrapingbee.com"
    key_envs = ("SCRAPINGBEE_API_KEY",)
    # The docs (read 2026-09-02) mark the ``?api_key=`` query form DEPRECATED and
    # require the Bearer header; the plan sketch's ``/api/v1/store/google`` path
    # is the old one -- the documented endpoint is ``/api/v1/google``.
    auth = Auth("header", "Authorization", "Bearer ")

    def _build_tools(self) -> list[AdapterTool]:
        head = _keyed_prefix("ScrapingBee", self.flag_env(), "SCRAPINGBEE_API_KEY")
        return [
            _tool(
                "scrapingbee_google",
                head
                + _LEGAL_SHADOW
                + "Google organic results via GET /api/v1/google (q as search, "
                "page 1-10, country_code, date_range=past_hour|past_day|past_week|"
                "past_month|past_year, light_request default true; Authorization: "
                "Bearer -- the ?api_key= form is deprecated upstream). A light request "
                "is 10 credits (~$2.54/1k assumed at the Hobby plan, $19 / 75,000 "
                "credits); light_request=false is 15 credits (~$3.80/1k) and may return "
                "more; the spb-cost header is relayed. " + _KEYED_TAIL,
                {
                    "type": "object",
                    "properties": {
                        **_Q,
                        "page": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 1,
                            "description": "Google result page to fetch (1-10)",
                        },
                        "country_code": {
                            "type": "string",
                            "default": "",
                            "description": "2-letter country code, e.g. 'us' (optional)",
                        },
                        "date_range": {
                            "type": "string",
                            "default": "",
                            "description": "past_hour|past_day|past_week|past_month|past_year",
                        },
                        "light_request": {
                            "type": "boolean",
                            "default": True,
                            "description": "10 credits (default); false = 15 credits",
                        },
                    },
                    "required": ["q"],
                },
                "/api/v1/google",
                "GET",
            )
        ]

    def _prepare_call(self, tool: AdapterTool, args: dict) -> _Request:
        tag = self.label
        q = self._query(args)
        page = adapters._int_arg(args, "page", 1, 1, 10, tag)
        country = _code_arg(args, "country_code", _COUNTRY_RE, tag)
        date_range = _choice_arg(
            args, "date_range", ("",) + _SCRAPINGBEE_RANGES, "", tag
        )
        light = _bool_arg(args, "light_request", True, tag)
        query = {"search": q, "light_request": "true" if light else "false"}
        if page != 1:
            query["page"] = str(page)
        if country and country != "ALL":
            query["country_code"] = country.lower()
        if date_range:
            query["date_range"] = date_range
        echo = {"q": q, "page": page, "light_request": light}
        return _Request("GET", tool.path, query, None, echo)

    def _price_per_1k(self, tool: AdapterTool, args: dict) -> float | None:
        try:
            light = _bool_arg(args or {}, "light_request", True, self.label)
        except ValueError:
            light = True
        # 15 credits instead of 10 at the same Hobby-plan credit price, rounded up.
        return PRICE_PER_1K.get(tool.name) if light else 3.80

    def _normalize(self, tool, args, parsed, headers):
        if not isinstance(parsed, dict) or not (
            isinstance(parsed.get("organic_results"), list) or "meta_data" in parsed
        ):
            raise _ShapeError("no 'organic_results' list / meta_data envelope")
        items = _items(parsed.get("organic_results"))
        hits = [
            self._hit(
                i.get("title"),
                i.get("url"),
                i.get("description"),
                published=i.get("date"),
                position=i.get("position"),
            )
            for i in items
        ]
        extras: dict = {}
        meta = parsed.get("meta_data")
        if isinstance(meta, dict):
            extras["meta_data"] = {
                k: meta.get(k)
                for k in (
                    "number_of_results",
                    "number_of_organic_results",
                    "number_of_page",
                )
                if meta.get(k) is not None
            }
        return hits, len(items), extras


#: Every vendor this lane knows, in wiring order (one adapter each when enabled).
VENDORS: tuple[type[KeyedSearchAdapter], ...] = (
    BraveAdapter,
    KagiAdapter,
    LinkupAdapter,
    MojeekAdapter,
    YouComAdapter,
    PerplexityAdapter,
    MarginaliaAdapter,
    SerperAdapter,
    SerpApiAdapter,
    DataForSEOAdapter,
    ZenSerpAdapter,
    ScrapingBeeAdapter,
)
VENDOR_BY_NAME = {cls.vendor: cls for cls in VENDORS}


def _int_env(environ, name: str, default: int) -> int:
    raw = environ.get(name)
    if not isinstance(raw, str) or not raw.strip():
        return default
    text = raw.strip()
    if not text.isdigit():
        raise ValueError(f"{name} must be a non-negative integer (got {text!r})")
    return int(text)


def _float_env(environ, name: str, default: float) -> float:
    raw = environ.get(name)
    if not isinstance(raw, str) or not raw.strip():
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        raise ValueError(
            f"{name} must be a number in USD (got {raw.strip()!r})"
        ) from None
    if value < 0 or value != value:  # negative or NaN
        raise ValueError(f"{name} must be >= 0 USD (got {raw.strip()!r})")
    return value


def ledger_path(environ) -> str:
    value = environ.get(LEDGER_PATH_ENV)
    return (
        value.strip()
        if isinstance(value, str) and value.strip()
        else DEFAULT_LEDGER_PATH
    )


def build(environ) -> list[SelfHostedAdapter]:
    """One adapter per vendor whose flag AND key are set; ``[]`` when none.

    Reads only env NAMES from ``environ``; makes no request. An invalid cap value
    raises ValueError so ``lanes.extra_adapters`` reports the lane degraded
    instead of running a safety cap it could not parse.
    """
    max_calls = _int_env(environ, MAX_CALLS_ENV, DEFAULT_MAX_CALLS_PER_DAY)
    cap_usd = _float_env(environ, SPEND_CAP_ENV, DEFAULT_SPEND_CAP_USD)
    ledger = Ledger(ledger_path(environ))
    built: list[SelfHostedAdapter] = []
    for cls in VENDORS:
        if not adapters._flag_enabled(environ, cls.flag_env()):
            continue
        secret = cls.secret_from(environ)
        if not secret:
            continue
        base = (environ.get(cls.url_env()) or "").strip() or cls.default_url
        built.append(
            cls(
                base,
                secret,
                ledger,
                max_calls_per_day=max_calls,
                spend_cap_usd=cap_usd,
            )
        )
    return built
