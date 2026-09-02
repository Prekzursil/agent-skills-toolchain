# Onions lane — legal / safety envelope (index-only)

**Status (owner decision 2026-09-02): the Ahmia onion lane works BY DEFAULT but
ASKS before every search.** `ENABLE_ONIONS=0` is a hard kill switch. The
repo-discovery (OSSInsight) lane remains **default OFF** (`ENABLE_OSSINSIGHT=0`).
This document is the binding scope for both; read it before enabling either.

The unchanged hard rules — **no Tor, no `.onion` fetch, index-only, Ahmia's
blacklist inherited** — are NOT relaxed by making the lane default-on. The
ask-before-search confirmation gate + a one-time owner sign-off replace the old
default-off env flag as the safety mechanism.

## Scope statement — Ahmia lane

The onion lane is **querying the Ahmia index only**, through the SearXNG provider
the hub already fronts. It is **not** a new tool and **not** a new service: it is an
`engines=ahmia` (or `categories="onion index"`) parameter on the existing
`searxng_web_search` tool, gated at the hub. A result is **a title + the indexed
snippet/metadata + the `.onion` URL as a string** — nothing more.

### Ask-before-search + modes + result tagging (the default-on UX)

- **Ask before searching.** An onion-intent `searxng_web_search` (`engines=ahmia`
  or a category containing `onion`) is **not forwarded** until the caller re-invokes
  with `onion_confirm=true`. The first call returns a **confirmation request** (not
  an error) that the agent must surface to the human — it never auto-confirms.
- **Search modes (index breadth only).** The confirmation lists `onion_mode`:
  `low` (~5 index hits) · `medium` (~10) · `high` (~20) · `deepest` (max ~20, all
  index-only). Modes set how many **index** hits come back — they do **not** crawl,
  fetch, or render any `.onion` page.
- **Clearly differentiated results.** A confirmed onion response is prepended with a
  `TOR / DARK-WEB INDEX RESULTS` banner and carries a structured `_onion` marker
  (`tor:true, onion_fetched:false, verified:false, mode:…`), so onion hits are
  unambiguously distinct from normal web results.

> **Why not the literal `onions` category?** Stock SearXNG **hard-gates** the
> `onions` category on a working Tor proxy: `searx/engines/__init__.py`
> `is_engine_active()` drops any engine whose `categories` contains the string
> `onions` unless `using_tor_proxy` is set, and `searx/network` probes
> `check.torproject.org` at startup and refuses to run otherwise. Since this lane
> is **no-Tor**, the clearnet Ahmia engine is registered under `onion index` (a
> name that loads without Tor) and selected by `engines=ahmia`. The hub guard
> detects onion intent by the substring `onion` in any category **plus** the
> `ahmia` engine, so the intuitive `categories=onions` is still gated (it just
> returns nothing from a clearnet instance).

### FORBIDDEN (verbatim — violations = stop and report, do not "fix" around them)

- Onion-lane scope = querying the Ahmia index only. FORBIDDEN: Tor/SOCKS
  proxies, fetching or rendering any .onion URL, crawling onion services,
  scraping result pages, storing onion content. Results are titles + indexed
  metadata + the .onion URL as a string, nothing more.
- Both lanes default OFF. Activation only via env flag
  (ENABLE_ONIONS=0, ENABLE_OSSINSIGHT=0) documented in the envelope doc.
- Ahmia's abuse blacklist is a feature, not an obstacle. Never filter
  around it; surface their removal policy in the envelope doc.

> **Owner amendment 2026-09-02 (kept beside the original, not silently edited).**
> The owner reversed the "onion default OFF" activation rule for the **Ahmia lane
> only**: it now works by default but **asks before every search** (per-use
> confirmation) with `ENABLE_ONIONS=0` as a hard kill switch. Every OTHER line
> above — no Tor, no `.onion` fetch, no crawling/scraping/storing onion content,
> Ahmia's blacklist inherited — stands **verbatim and unchanged**. OSSINSIGHT stays
> default OFF.

### How the code enforces this

- `onions.py` `onion_decision()` classifies each SearXNG-provider call into
  `pass` / `forbid` / `killed` / `ask` / `run`: onion intent (any category
  containing `onion`, incl. `onions` / `onion index`, or the `ahmia` engine)
  returns `ask` (a confirmation request, not an error) until the caller supplies
  `onion_confirm=true`; `web_url_read` of a `.onion` host is `forbid` **always**;
  `ENABLE_ONIONS=0` returns `killed`. A confirmed `run` forwards mode-applied,
  index-pinned args and the response is tagged. Decisions happen **at the hub**: on
  `ask`/`forbid`/`killed` no SearXNG child is spawned and no query is forwarded.
  Pinned by `tests/test_onions.py` +
  `tests/test_hub.py::test_onion_search_asks_before_searching_by_default`.
- The SearXNG engine (`deploy/searxng-min/settings.yml`) registers a **clearnet
  `ahmia.fi`** Ahmia engine under category **`onion index`** (not the Tor-gated
  `onions`) with **no `outgoing.proxies`**, and **removes** the onion-only default
  `ahmia` and `torch` engines (they point at `.onion` and need Tor). With no Tor
  proxy the lane **fails closed** (empty result / a truthful error) rather than
  silently reaching for Tor.

### Ahmia's abuse blacklist / removal policy (a feature — never filtered around)

Ahmia maintains a blacklist of abusive hidden services (notably child-abuse
material) and removes them from its index; the ban list is published as MD5 hashes
of the banned `.onion` addresses. Because this lane queries the Ahmia index, we
inherit Ahmia's filtering by construction and **must not** attempt to bypass,
re-include, or work around it.

- Blacklist / policy: <https://ahmia.fi/blacklist/>
- Banned services (MD5 list): <https://ahmia.fi/blacklist/banned/>
- Legal / terms: <https://ahmia.fi/legal/>
- About: <https://ahmia.fi/about/>

### Verified operational findings (2026-09-02)

- **SearXNG Tor-gate (source-verified).** `is_engine_active()` marks any engine whose
  `categories` contains `onions` INACTIVE unless a Tor proxy is configured, and the
  network layer probes `check.torproject.org` at startup. So a clearnet Ahmia engine
  **must not** use the literal `onions` category — we use `onion index` and
  `engines=ahmia`, and remove the Tor-only `ahmia`/`torch` defaults.
- **Clearnet markup confirmed.** `GET https://ahmia.fi/search/?q=<token>` returns the
  exact `<li class="result">` / `redirect_url=` markup SearXNG's `ahmia` engine
  parses (177 results for a benign query in the research pass).
- **Datacenter rate-limit.** From a datacenter/CI IP, `https://ahmia.fi/search/?q=...`
  **302-redirects to the homepage** (measured: `302 Location: /`, `Onion-Location:`
  header), so a cloud probe returns **no results** — expected, not a bug. Live
  verification must run on the **estate instance from a residential IP**
  (`engines=ahmia` for a benign query such as `ahmia`). Ahmia's ToS §2 also
  discourages automated scraping — keep volume low. The lane never falls back to Tor
  or the `.onion` to compensate.

## Scope statement — OSSInsight (repo-discovery) lane

Keyless queries to the **public** OSSInsight API (`https://api.ossinsight.io`) for
open-source repository discovery and stats. In-process HTTP, no key, no crawl. It
is default OFF via `ENABLE_OSSINSIGHT` and only exposes endpoints that returned a
live HTTP 200 (see the decision record for the endpoint verification). Degraded
metrics are **passed through truthfully** (the API's own `data_quality` block is
relayed, never hidden or fabricated).

## Activation flags

| flag | default | effect |
|---|---|---|
| `ENABLE_ONIONS` | **unset = ON (ask-first)** | the Ahmia INDEX lane works by default: an onion-intent `searxng_web_search` returns a confirmation request; the caller re-invokes with `onion_confirm=true` + `onion_mode`. Set `ENABLE_ONIONS=0` to **hard-disable** (kill switch). `.onion` fetch stays forbidden regardless |
| `ENABLE_OSSINSIGHT` | `0` (OFF) | the hub wires the OSSInsight repo-discovery adapter (`ossinsight_*` tools) |

Set them in the hub's environment (e.g. the `search-hub` entry's `env` in
`~/.mcp.json`). The onion lane is reachable by default (ask-gated); OSSInsight is
not reachable until `ENABLE_OSSINSIGHT=1`.

## Owner sign-off (one-time authorization for the ask-gated onion lane)

Because the lane is now default-on-with-ask, this sign-off is the **one-time**
authorization; the per-search confirmation is the ongoing gate. I confirm this is
**authorized research** use, that I have read the FORBIDDEN list above and Ahmia's
blacklist/removal policy, and that the lane is index-only (no Tor, no `.onion`
fetch, no scraping/storage of onion content):

- Authorized by: `________________________`
- Date: `________________________`
- Jurisdiction confirmed lawful for index querying: `________________________`
- Estate-instance `engines=ahmia` verification done (residential IP): `☐`

> Automated access to dark-web indexes may be illegal in your jurisdiction
> regardless of intent. Tor is operational security, not legal protection. This
> lane deliberately does neither Tor nor onion fetching.

## Re-evaluation trigger

Anything **beyond index search** — fetching/rendering a `.onion`, adding a Tor/SOCKS
proxy, crawling or scraping onion result pages, storing onion content, or enabling
a second onion engine (Not Evil / Torch / etc.) — is **out of this envelope** and
requires a **new decision record + a fresh owner sign-off** before any code is
written. Do not extend the lane in place.
