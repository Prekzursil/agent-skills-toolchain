# Onions lane — legal / safety envelope (index-only, default OFF)

**Status: default OFF. Both follow-up lanes ship disabled.** This document is the
binding scope for the dark-web (Ahmia) lane and the repo-discovery (OSSInsight)
lane added to `tools/mcp/search-hub`. Read it before setting either flag.

## Scope statement — Ahmia lane

The onion lane is **querying the Ahmia index only**, through the SearXNG provider
the hub already fronts. It is **not** a new tool and **not** a new service: it is a
`categories=onions` (or `engines=ahmia`) parameter on the existing
`searxng_web_search` tool, gated at the hub. A result is **a title + the indexed
snippet/metadata + the `.onion` URL as a string** — nothing more.

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

- `onions.py` `guard()` refuses `searxng_web_search` with `categories=onions` /
  `engines=ahmia` unless `ENABLE_ONIONS` is truthy, and refuses **any**
  `web_url_read` of a `.onion` host **regardless of the flag** (that would be
  fetching an onion service — forbidden). Refusals happen **at the hub**: no
  SearXNG child is spawned and no query is forwarded. Pinned by
  `tests/test_onions.py` + `tests/test_hub.py::test_onions_category_blocked_when_flag_off`.
- The SearXNG engine (`deploy/searxng-min/settings.yml`) is pinned to **clearnet
  `ahmia.fi`** with **no `outgoing.proxies`**. SearXNG's upstream default points
  the Ahmia engine at the Ahmia **`.onion`** (which needs Tor) — we do **not** use
  that. With no Tor proxy configured the lane **fails closed** (empty result / a
  truthful error) rather than silently reaching for Tor.
- Not Evil / Torch are **not** enabled (dead engines, and out of scope anyway).

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

- `https://ahmia.fi/search/?q=...` **302-redirects datacenter / bot queries to the
  homepage** (measured: `302 Location: /`, plus an `Onion-Location:` header). So a
  cloud/CI probe of the clearnet index returns **no results** — this is expected,
  not a bug. Live result verification must be done on the **owner's estate SearXNG
  instance from a residential IP** (`category=onions` for a benign query such as
  `ahmia`). Until that is done, treat result quality as unverified.
- Consequently the lane may return empty even when enabled, from an IP Ahmia
  rate-limits. It never falls back to Tor or the `.onion` to compensate.

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
| `ENABLE_ONIONS` | `0` (OFF) | the hub forwards `searxng_web_search` calls that select `categories=onions` / `engines=ahmia`; `.onion` fetch stays forbidden |
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
- Estate-instance `category=onions` verification done (residential IP): `☐`

> Automated access to dark-web indexes may be illegal in your jurisdiction
> regardless of intent. Tor is operational security, not legal protection. This
> lane deliberately does neither Tor nor onion fetching.

## Re-evaluation trigger

Anything **beyond index search** — fetching/rendering a `.onion`, adding a Tor/SOCKS
proxy, crawling or scraping onion result pages, storing onion content, or enabling
a second onion engine (Not Evil / Torch / etc.) — is **out of this envelope** and
requires a **new decision record + a fresh owner sign-off** before any code is
written. Do not extend the lane in place.
