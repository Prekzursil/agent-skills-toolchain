# Onions lane — legal / safety envelope (index-only, default OFF)

**Status: default OFF. Both follow-up lanes ship disabled.** This document is the
binding scope for the dark-web (Ahmia) lane and the repo-discovery (OSSInsight)
lane added to `tools/mcp/search-hub`. Read it before setting either flag.

## Scope statement — Ahmia lane

The onion lane is **querying the Ahmia index only**, through the SearXNG provider
the hub already fronts. It is **not** a new tool and **not** a new service: it is an
`engines=ahmia` (or `categories="onion index"`) parameter on the existing
`searxng_web_search` tool, gated at the hub. A result is **a title + the indexed
snippet/metadata + the `.onion` URL as a string** — nothing more.

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

### How the code enforces this

- `onions.py` `guard()` refuses `searxng_web_search` that selects an onion category
  (any category containing `onion`, incl. `onions` / `onion index`) or the `ahmia`
  engine unless `ENABLE_ONIONS` is truthy, and refuses **any** `web_url_read` of a
  `.onion` host **regardless of the flag** (that would be fetching an onion service
  — forbidden). Refusals happen **at the hub**: no SearXNG child is spawned and no
  query is forwarded. Pinned by `tests/test_onions.py` +
  `tests/test_hub.py::test_onions_category_blocked_when_flag_off`.
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

## Activation flags (both default 0 / OFF)

| flag | default | effect when set truthy (`1`/`true`) |
|---|---|---|
| `ENABLE_ONIONS` | `0` (OFF) | the hub forwards `searxng_web_search` calls that select `engines=ahmia` / `categories="onion index"` (or the intuitive `onions`); `.onion` fetch stays forbidden |
| `ENABLE_OSSINSIGHT` | `0` (OFF) | the hub wires the OSSInsight repo-discovery adapter (`ossinsight_*` tools) |

Set them in the hub's environment (e.g. the `search-hub` entry's `env` in
`~/.mcp.json`). With both unset, neither lane is reachable.

## Owner sign-off (fill in before enabling the onion lane)

By enabling `ENABLE_ONIONS=1` I confirm this is **authorized research** use, that I
have read the FORBIDDEN list above and Ahmia's blacklist/removal policy, and that
the lane is index-only (no Tor, no `.onion` fetch, no scraping/storage of onion
content):

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
