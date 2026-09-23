# Onions lane — legal / safety envelope (index-only)

**Status (owner decision 2026-09-02): the onion lane works BY DEFAULT but ASKS
before every search.** `ENABLE_ONIONS=0` is a hard kill switch. **Owner decision
G-7 (2026-09-02)** added **VormWeb** as a second clearnet onion-INDEX source,
**DEFAULT-ON**, behind the same gate; `ENABLE_VORMWEB=0` kills that engine alone.
The repo-discovery (OSSInsight) lane remains **default OFF** (`ENABLE_OSSINSIGHT=0`).
This document is the binding scope for all of them; read it before enabling any.

The unchanged hard rules — **no Tor, no `.onion` fetch, index-only, Ahmia's
blacklist inherited** — are NOT relaxed by making the lane default-on, and they
apply to **VormWeb results identically**. The ask-before-search confirmation gate +
a one-time owner sign-off replace the old default-off env flag as the safety
mechanism.

## Scope statement — onion lane (Ahmia + VormWeb indexes)

The onion lane is **querying clearnet onion indexes only** — the **Ahmia** index
and, since G-7, the **VormWeb** index — through the SearXNG provider the hub
already fronts. It is **not** a new tool and **not** a new service: it is an
`engines=ahmia` / `engines=vormweb` (or `categories="onion index"`, which means
*every enabled index*) parameter on the existing `searxng_web_search` tool, gated
at the hub. A result is **a title + the indexed snippet/metadata + the `.onion`
URL as a string** — nothing more, from either index.

### Ask-before-search + modes + result tagging (the default-on UX)

- **Ask before searching.** An onion-intent `searxng_web_search` (`engines=ahmia`,
  `engines=vormweb`, or a category containing `onion`) is **not forwarded** until
  the caller re-invokes with `onion_confirm=true`. The first call returns a
  **confirmation request** (not an error) that the agent must surface to the human
  — it never auto-confirms. The request lists the **`engines`** it will query.
- **Which index.** No explicit engine (category-only intent) = **every enabled
  index** (`ahmia,vormweb` by default). `engines=ahmia` or `engines=vormweb` =
  that one index only. Non-onion engines mixed into an onion request are dropped —
  the lane never blends clearnet general engines under the dark-web banner.
- **Search modes (index breadth only).** The confirmation lists `onion_mode`:
  `low` (~5 index hits) · `medium` (~10) · `high` (~20) · `deepest` (max ~20, all
  index-only). Modes set how many **index** hits come back — they do **not** crawl,
  fetch, or render any `.onion` page.
- **Clearly differentiated results.** A confirmed onion response is prepended with a
  `TOR / DARK-WEB INDEX RESULTS` banner naming the index(es) and carries a
  structured `_onion` marker (`lane: ahmia-index | vormweb-index |
  ahmia+vormweb-index`, `engines:[…]`, `tor:true, onion_fetched:false,
  verified:false, mode:…`), so onion hits are unambiguously distinct from normal
  web results. `verified:false` is ours and is **never** flipped by VormWeb's own
  "Verified" badge.

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

> **Owner amendment 2026-09-02, decision G-7 (kept beside the original).** The
> lane's scope line "querying the Ahmia index only" is widened to **"querying the
> Ahmia index and the VormWeb index only"** — both clearnet, both index-only. The
> FORBIDDEN list itself is **unchanged** and applies to VormWeb results
> **identically**: no Tor/SOCKS, never fetch or render a `.onion` URL (a VormWeb
> hit's URL is the same string an Ahmia hit carries and is refused the same way),
> never crawl onion services, never scrape result pages beyond the one index page
> SearXNG parses, never store onion content. The owner's exact scope: "wire only
> vormweb and default on, nothing else" — no third engine, no Ahmia MD5 blacklist
> guard.

### VormWeb — second index source (G-7, DEFAULT-ON)

- **What it is.** `https://vormweb.de` is a clearnet directory/index of `.onion`
  hidden services with a search form (`GET /en/search?q=…`, minimum 3 characters).
  It has **no API, no ToS**, and its `robots.txt` is a 404 (probed 2026-09-02 from
  the cloud VM: HTTP 200 in ~0.6 s, 41 index hits for "privacy"). Upstream SearXNG
  ships no `vormweb` engine, so the definition is **ours**: a generic SearXNG
  `xpath` engine in `deploy/searxng-min/settings.yml` under category `onion index`
  (never the Tor-gated `onions`), shortcut `vw`, `disabled: false`.
- **Same envelope, same gate.** `engines=vormweb` is onion intent exactly like
  `engines=ahmia`: ask-before-search, modes, kill switch (`ENABLE_ONIONS=0`), and
  the `TOR / DARK-WEB INDEX` banner + `_onion` marker (`lane: vormweb-index`). A
  result is a title + snippet + the `.onion` URL **as a string**, never fetched.
- **Per-engine kill switch.** `ENABLE_VORMWEB=0` (or `false|no|off`) drops VormWeb
  from the default engine list; an **explicit** `engines=vormweb` request is then
  **refused with a truthful message** (which flag, which engines still work) rather
  than silently narrowed. Unset/truthy = ON. Ahmia has no per-engine switch — it is
  the lane's anchor; `ENABLE_ONIONS=0` is how it goes off.
- **Caveats the owner explicitly accepted (G-7) — carried, not hidden:**
  1. **Operator consent is unresolved.** VormWeb publishes no ToS and no robots
     policy, and the cloud agent **cannot e-mail the operator**. The engine ships
     **documented, not silent** (this section, the YAML comment, the confirmation
     text) with a **low request rate**: one GET per confirmed search, no paging, no
     retries beyond SearXNG's own, and the search still requires the human's
     per-use confirmation. If the operator ever objects, set `ENABLE_VORMWEB=0` and
     remove the stanza — nothing else depends on it.
  2. **Filtering is VormWeb's self-declared policy only — unverifiable.** VormWeb
     labels entries "Verified" / "Warning" / "Risky" and states it curates its
     index; we **cannot audit** that. Unlike Ahmia there is no published blacklist
     to inherit, and the owner **explicitly declined** a hub-side Ahmia-MD5
     blacklist guard (G-7: "skip Ahmia MD5 blacklist"), so **no independent hub-side
     screen exists**. Every hit is tagged `verified: false` regardless of VormWeb's
     badge, and the banner says so. Users of the lane accept that a VormWeb index
     hit is exactly as unvetted as its operator's self-description.
- **Not verified from the cloud VM:** that a live SearXNG instance loads the xpath
  stanza and returns results (no Docker here). The xpaths were checked against the
  live markup with lxml (41/41 results, none missing title/href); the estate
  instance still needs a restart + one `engines=vormweb` query (sign-off checklist).

### How the code enforces this

- `onions.py` `onion_decision()` classifies each SearXNG-provider call into
  `pass` / `forbid` / `killed` / `ask` / `run`: onion intent (any category
  containing `onion`, incl. `onions` / `onion index`, or a lane engine — `ahmia`
  or `vormweb`) returns `ask` (a confirmation request, not an error) until the
  caller supplies `onion_confirm=true`; `web_url_read` of a `.onion` host is
  `forbid` **always**; `ENABLE_ONIONS=0` returns `killed`, and so does an explicit
  request for a kill-switched engine (`ENABLE_VORMWEB=0` + `engines=vormweb`). A
  confirmed `run` forwards mode-applied args pinned to the resolved index engine(s)
  (`engines=ahmia,vormweb` by default, one engine if one was named) and the
  response is tagged with the matching `lane`. Decisions happen **at the hub**: on
  `ask`/`forbid`/`killed` no SearXNG child is spawned and no query is forwarded.
  Pinned by `tests/test_onions.py` +
  `tests/test_hub.py::test_onion_search_asks_before_searching_by_default`.
- The SearXNG config (`deploy/searxng-min/settings.yml`) registers a **clearnet
  `ahmia.fi`** Ahmia engine and a **clearnet `vormweb.de`** xpath engine, both
  under category **`onion index`** (not the Tor-gated `onions`) with **no
  `outgoing.proxies`**, and **removes** the onion-only default `ahmia` and `torch`
  engines (they point at `.onion` and need Tor). With no Tor proxy the lane
  **fails closed** (empty result / a truthful error) rather than silently reaching
  for Tor. `tests/test_deploy_settings.py` pins the category, the absence of any
  `.onion` host in the VormWeb stanza, and the absence of any proxy.

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
| `ENABLE_ONIONS` | **unset = ON (ask-first)** | the onion INDEX lane (Ahmia + VormWeb) works by default: an onion-intent `searxng_web_search` returns a confirmation request; the caller re-invokes with `onion_confirm=true` + `onion_mode`. Set `ENABLE_ONIONS=0` to **hard-disable the whole lane** (kill switch). `.onion` fetch stays forbidden regardless |
| `ENABLE_VORMWEB` | **unset = ON** (G-7) | VormWeb is in the default engine set. Set `ENABLE_VORMWEB=0` to drop it: category-only searches then query Ahmia alone and an explicit `engines=vormweb` is **refused with a truthful message**. Does nothing when `ENABLE_ONIONS=0` (the lane is already off) |
| `ENABLE_OSSINSIGHT` | `0` (OFF) | the hub wires the OSSInsight repo-discovery adapter (`ossinsight_*` tools) |

Set them in the hub's environment (e.g. the `search-hub` entry's `env` in
`~/.mcp.json`). The onion lane is reachable by default (ask-gated); OSSInsight is
not reachable until `ENABLE_OSSINSIGHT=1`. Requesting one index: `engines=ahmia`
or `engines=vormweb`; omitting `engines` (or `categories="onion index"`) queries
every enabled index.

## Owner sign-off (one-time authorization for the ask-gated onion lane)

Because the lane is now default-on-with-ask, this sign-off is the **one-time**
authorization; the per-search confirmation is the ongoing gate. I confirm this is
**authorized research** use, that I have read the FORBIDDEN list above, Ahmia's
blacklist/removal policy and the **VormWeb caveats** (operator consent unresolved;
filtering self-declared and unverifiable), and that the lane is index-only (no
Tor, no `.onion` fetch, no scraping/storage of onion content):

- Authorized by: `________________________`
- Date: `________________________`
- Jurisdiction confirmed lawful for index querying: `________________________`
- Estate-instance `engines=ahmia` verification done (residential IP): `☐`
- Estate-instance `engines=vormweb` verification done after a SearXNG restart
  (the xpath stanza only loads on restart): `☐`

> Automated access to dark-web indexes may be illegal in your jurisdiction
> regardless of intent. Tor is operational security, not legal protection. This
> lane deliberately does neither Tor nor onion fetching.

## Re-evaluation trigger

Anything **beyond index search** — fetching/rendering a `.onion`, adding a Tor/SOCKS
proxy, crawling or scraping onion result pages, storing onion content, or enabling
a second onion engine (Not Evil / Torch / etc.) — is **out of this envelope** and
requires a **new decision record + a fresh owner sign-off** before any code is
written. Do not extend the lane in place.

> **Trigger fired once, 2026-09-02 (kept beside the original).** The "second onion
> engine" clause above fired for **VormWeb** and was resolved the way it demands: a
> decision record (G-7 in `docs/plans/2026-09-02-search-research-tools-gemhunt.md`)
> plus the owner's explicit words ("wire only vormweb and default on, nothing
> else"), with the two caveats recorded above. Nothing else moved: still index
> search only, still no Tor, still no `.onion` fetch. A **third** engine — or any
> hub-side blacklist/screening logic, which the owner declined — fires this trigger
> again and needs its own record + sign-off.
