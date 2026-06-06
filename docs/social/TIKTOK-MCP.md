# TikTok MCP — Research & Build Decision

**Status:** ✅ **BUILT, TESTED & REGISTERED** (2026-06-06) — see the "BUILT" section below.
The original research/decision record is retained underneath for rationale.
**Date:** 2026-06-06.
**Context:** evaluated as a peer to the existing personal social-media MCP toolchain
(`insta-mcp`, `fb-messenger-mcp`, `whatsapp-mcp` in `~/source/repos/`). Same
spirit, same self-hosted/private-account intent, same ToS/ban-risk posture.

Paths use `~` = `C:\Users\Prekzursil` on this Windows host; POSIX equivalent
`~/source/repos/`. Commands are shown Windows-first.

---

## BUILT (2026-06-06) — what actually shipped

The research below recommended **Lane C (BUILD a thin read-only wrapper)** — that is exactly
what was built, tested live, registered, and backed up.

- **Repo:** `~/source/repos/tiktok-mcp` — git-backed, **local-only (no remote)**; `.env` and
  `data/` gitignored. Python 3.12 `.venv`, `TikTokApi==7.3.3` + `mcp[cli]`, Playwright
  **chromium and webkit** installed.
- **Server:** `server.py` — FastMCP, **9 read-only tools**: `tiktok_trending`,
  `tiktok_user_info`, `tiktok_user_posts`, `tiktok_user_liked`, `tiktok_hashtag`,
  `tiktok_video_details`, `tiktok_comments`, `tiktok_related_videos`, `tiktok_search_users`.
  `count` clamped to [1, 50]; errors returned as `{error, detail, hint}`, never a crash.
- **API reality vs the plan:** TikTok-Api 7.x exposes **user search only** — there is *no*
  generic video search. Video discovery is via `tiktok_hashtag` / `tiktok_trending`. Bonus
  tool gained that wasn't in the plan: `tiktok_related_videos`.
- **E2E result (verified live, keyless):** `tiktok_trending` **works with zero setup**
  (returned real videos and validated the field trimmers against real payloads).
  `user_info` / `hashtag` (and by extension video/comments/related/search) return
  `EmptyResponseException` — TikTok bot-walls *unauthenticated* scraping of those endpoints.
  `TIKTOK_BROWSER=webkit` did **not** fix it; an `ms_token` is the real lever.
- **To enable the non-trending tools:** set **`TIKTOK_MS_TOKEN`** (the `msToken` cookie from a
  logged-in tiktok.com session — a nonce, *not* a login; store gitignored, never logged).
  Set **`TIKTOK_PROXY`** only on a datacenter/cloud egress IP (a home IP needs no proxy).
  Optional **`TIKTOK_BROWSER`** = chromium (default) | webkit | firefox.
- **Registered** user-scope as `tiktok` → `claude mcp get tiktok` = ✓ Connected. Security:
  semgrep + bandit clean, gitleaks clean, secrets never logged.
- **Agent-facing reference:** the `tiktok-public-research` skill in this repo.

> Everything from here down is the original research/decision record (why BUILD, the library
> survey, the account-state notes). Kept for provenance; the section above is current truth.

---

## TL;DR (read this first)

**The insta-mcp analogy inverts for TikTok.** insta-mcp's entire value is
*authenticated own-account read* — your Saved, DMs, inbox, liked, following. For
TikTok, **that capability does not exist in any maintained library.** Concretely:

- **DMs / inbox:** readable by **no** route — official or unofficial. Same wall as
  FB 1:1 Messenger (E2EE) already documented in the toolchain. **HIGH confidence.**
- **Saved/favorites, For You feed, following list:** **no** maintained library and
  **no** official OAuth scope exposes these for your own account. **HIGH confidence.**
- The one Node library that *did* read authenticated For You / Following / own
  posts / likes (`szdc/tiktok-api`) was **archived in 2021, last commit 2019** —
  dead, and it required MITM-sourced device params + a self-implemented anti-spam
  signature. **HIGH confidence.**
- What *is* alive (`davidteather/TikTok-Api`, 6.4k★, active to v7.3.3 Apr 2026)
  reads **public data only** — trending, a creator's *public* posts/likes,
  hashtags, search, comments, video metadata. **No authenticated routes, cannot
  post.** **HIGH confidence.**

**Recommendation = conditional, driven by what the user actually wants TikTok for:**

| If the goal is… | Verdict |
|---|---|
| **Own-account private read** (the insta-mcp spirit: my saved, my DMs, my feed) | **Not achievable.** No build. Reviving szdc-style auth = dead lib + MITM + high ban risk. Recommend against. |
| **Own *public* posts + profile + analytics** (official, durable) | **FIND/light-build:** official Display API via OAuth. No saved/DM/feed though. |
| **Public discovery / research** (trending, a creator's public posts, transcripts, search) | **BUILD** a thin Python/FastMCP wrapper over `davidteather/TikTok-Api` — mirrors `fb-messenger-mcp` + the drug-discovery MCPs, **not** insta-mcp. |

There is no single TikTok MCP that is "insta-mcp for TikTok." Pick the lane first.

---

## 1. Existing TikTok MCP servers (FIND candidates)

All found via GitHub/npm search 2026-06-06. None reads your private account; the
useful ones are **public-data / SaaS-backed**, which breaks the toolchain's
self-hosted trust model (your queries leave your machine through a third party —
unlike insta-mcp, where the session is yours).

| MCP | Lang | Auth / backend | What it does | Maturity | Verdict |
|---|---|---|---|---|---|
| **Seym0n/tiktok-mcp** | TS/Node ≥18 | **TikNeuron API key** (paid SaaS backend) | 3 tools: `tiktok_get_subtitle`, `tiktok_get_post_details`, `tiktok_search` — public video metadata + captions | ~163★, v2.2.0 (Feb 2026), maintenance-mode | Most polished FIND. **But routes through TikNeuron** — not self-hosted, costs money, public-only. |
| **terrylinhaochen/tiktok_mcp** | Python | scrapes direct | search + insight extraction | low | **DISQUALIFIED.** Returns **fabricated MOCK data** when TikTok blocks it (which it says is the current default). Silent fabrication = a footgun in a research tool. |
| **yap-audio/tiktok-mcp** | Python | scrapes direct (anti-detection built in) | hashtag/trending video discovery + metadata | low/early | Public discovery only; brittle scraping, no auth. |
| **fmd-labs/viral-app-mcp** | — | **viral.app SaaS** backend | profile lookup, video metrics, transcripts | low | SaaS-backed; public analytics only. |
| **AdsMCP/tiktok-ads-mcp-server**, **ysntony/tiktok-ads-mcp** | Py/Node | **TikTok Business/Ads API** (official OAuth) | campaign mgmt, ad analytics, reporting | moderate | Only relevant if you run paid **TikTok Ads**. Not a personal-account tool. |
| **Bright Data / Composio / Apify "TikTok" MCPs** | hosted | **vendor API key**, residential pool included | public scraping at scale | commercial | Paid SaaS. Robust public data, zero own-account access; your data egresses the vendor. |

**Security note on the FIND options:** every one above either (a) ships your
queries to a third-party SaaS (TikNeuron / viral.app / Bright Data / Composio /
Apify) or (b) is a low-maturity scraper that silently mocks. None is the
"my session, my machine" model of insta-mcp / fb-messenger-mcp. If a FIND is
chosen, **Seym0n/tiktok-mcp** is the cleanest, with the explicit caveat that it's
a paid public-data proxy, not personal-account access.

---

## 2. Underlying unofficial-API libraries (what a BUILD would ride)

| Library | Lang | Auth | Reads (logged-in user) | Reads (public) | Status | Ban/ToS |
|---|---|---|---|---|---|---|
| **davidteather/TikTok-Api** | Python 3.9+ | **`ms_token` cookie only** (anti-bot help, NOT login) | ❌ none — "no support for any user-authenticated routes" | trending, user public posts, user public likes, hashtag, search, comments, video metadata. **Cannot post.** | **ALIVE** — 6.4k★, v7.3.3 (Apr 2026), 129 releases | unofficial; `EmptyResponseException` = bot-detection, proxies often required |
| **szdc/tiktok-api** | Node | `loginWithEmail`/`loginWithUsername` → cookie jar | ✅ **For You + Following feed, own posts, likes, followers/following, follow/like/comment** (the one lib that did this) | yes | **DEAD** — archived 2021-09, last commit 2019, 1.3k★ | needs MITM-sourced device params + self-implemented anti-spam sig (`as`/`cp`/`mas`); unmaintainable today |
| **EmilioBarradas/tiktok-app-api**, **zzzjano/TikTok-API**, **zetreex/TikTok-Unauthorized-API**, **mangledbottles/Musically-API** | Node/various | cookies or none | ❌ | feed/user/post metrics, no-watermark, search (unauth) | mixed/older | same unofficial-API ban risk |
| **TikAPI.io**, **tiktok-api (npm)** | hosted/Node | vendor key / reverse-eng cookie | varies | public + some | commercial / fragile | paid or fragile |

**DMs across the board:** no unofficial library exposes the TikTok message inbox.
The reverse-engineering community (MITM of the iOS app via Charles + SSL-kill)
documents feed/user/post endpoints; the private chat surface is not in any
maintained wrapper. **Reading TikTok DMs is not possible** — treat it exactly like
FB 1:1 Messenger E2EE in `social-dm-search`: say so plainly, don't pretend.

### Official TikTok API (the durable, low-risk path)

OAuth 2.0, app registration + scope approval required. Confirmed scope list
(developers.tiktok.com/doc/tiktok-api-scopes, 2026-06-06):

- `user.info.basic` / `user.info.profile` / `user.info.stats` — own profile + stats
- `video.list` — own **public** videos
- `video.publish` / `video.upload` — post / draft
- research + data-portability scopes (gated programs)

**No scope exists** for saved/favorited videos, the For You feed, following list,
or DMs. **HIGH confidence.** So even the official API can't deliver the insta-mcp
experience — it gives own *public* posts + profile + the ability to publish.

---

## 3. FIND vs BUILD — recommendation

**Decide the lane with the user before any work.** The capability facts resolve
each lane deterministically:

1. **Lane A — "insta-mcp for TikTok" (own private feed / saved / DMs):**
   **Do not build.** Impossible with maintained tooling. The only lib that ever
   did authenticated own-account read is dead (2019) and would need MITM device
   params + bespoke signing + a logged-in session on a fragile private API =
   maximal ban risk for minimal, decaying payoff. **Recommend against.** Be honest
   that this is the one toolchain platform where the private-read pattern can't be
   reproduced.

2. **Lane B — own public footprint, durably (analytics/publishing):**
   **FIND/light-build the official Display API** (OAuth). Best for "show/manage my
   own public posts + profile + stats," and the only ToS-clean path. Cost = app
   registration + scope approval; payoff = stable, no ban risk. Still **no** saved
   / feed / DMs.

3. **Lane C — public discovery / research (most likely the real want):**
   **BUILD a thin wrapper over `davidteather/TikTok-Api`** (active, public-only) —
   OR just install **Seym0n/tiktok-mcp** if paying TikNeuron and SaaS egress are
   acceptable. BUILD keeps it self-hosted and free; SaaS is more robust against
   bot-detection. Trade self-hosting vs. reliability.

**Default recommendation if forced to pick:** **Lane C, BUILD**, because it
preserves the toolchain's self-hosted ethos and is free — with eyes open that
even public reads are flaky (bot-detection) and need the residential proxy on
cloud egress. If the user only cares about their *own* content and wants zero ban
risk, switch to **Lane B (official API)**.

---

## 4. BUILD scaffold (Lane C) — mirrors fb-messenger-mcp / drug MCPs

**Not** the insta-mcp pattern (there's no authenticated session lib to ride). The
honest TikTok build is a **Python venv + FastMCP** wrapper over a public scraper,
exactly like `fb-messenger-mcp`, `rdkit-mcp-server`, and `schrodinger-mcp`.

- **Repo:** `~/source/repos/tiktok-mcp/` (`C:\Users\Prekzursil\source\repos\tiktok-mcp`).
- **Language/runtime:** Python 3.11+, `.venv`. (Node is possible but the only
  alive, well-maintained lib is Python — so Python.)
- **Library:** `davidteather/TikTok-Api` (`pip install TikTokApi`) +
  `python -m playwright install` (it drives a headless browser for signing).
- **Server framework:** `mcp[cli]` / FastMCP — same as `fb-messenger-mcp/server.py`
  and `schrodinger-mcp/server.py`.
- **Auth method:** **no login.** Set an `ms_token` (copied from a logged-in
  `tiktok.com` cookie) via env to reduce bot-detection. There is *no* session.json
  / QR / password — that's the whole point: public-only. Store `ms_token` in a
  **gitignored** `.env` / `data/` (consistent with every other repo here).
- **MCP tools to expose** (all public-data, grade reliability in the docstrings):
  - `tiktok_search(query, count)` — video search.
  - `tiktok_trending(count)` — trending feed.
  - `tiktok_user_posts(username, count)` — a creator's **public** posts.
  - `tiktok_user_liked(username, count)` — a creator's **public** likes (only if
    that user made likes public).
  - `tiktok_hashtag(tag, count)` — videos for a hashtag.
  - `tiktok_video_details(url_or_id)` — metadata (desc, author, stats, music).
  - `tiktok_comments(url_or_id, count)` — top-level comments.
  - *(optional)* `tiktok_get_subtitle(url_or_id)` — captions, if reachable.
  - **Explicitly NOT exposed:** own feed, own saved/favorites, own following, DMs,
    any write/post/like — none are reachable. Document the absence so the agent
    never implies it can read them.
- **Registration** (user scope, like insta-mcp / the drug MCPs):
  ```
  claude mcp add tiktok -e TIKTOK_MS_TOKEN=<ms_token> -- ^
    C:\Users\Prekzursil\source\repos\tiktok-mcp\.venv\Scripts\python.exe server.py
  ```
  (POSIX: `claude mcp add tiktok -e TIKTOK_MS_TOKEN=... -- ~/source/repos/tiktok-mcp/.venv/bin/python server.py`.)
  Tools load on the next Claude Code restart. Per project policy, consider adding
  it to `disabledMcpServers` and enabling per-project (same as the drug MCPs).
- **Residential proxy (required on cloud/datacenter egress):** TikTok bot-detection
  is aggressive; a datacenter IP gets `EmptyResponseException` fast. On the Oracle
  VM / any datacenter host, route through the **Byteful sticky-Romania residential
  proxy** already provisioned for IG/FB
  (`source/repos/social-mcp-deploy/proxy-endpoints.secret`). `TikTokApi` accepts a
  `proxies=` arg per session — wire env `TIKTOK_PROXY` → that. **Running LOCAL on
  the home residential IP, no proxy needed** (same rule as IG/FB). Note: TikTok's
  geo + the proxy's RO exit may localize trending/results to Romania.
- **Security checklist** (match the toolchain bar): gitignore `data/`, `.env`,
  `*.token`; never log `ms_token`; run `semgrep`/`bandit` before commit; pin
  `TikTokApi`; vet transitive deps (Playwright pulls a browser — large surface).

**Effort:** ~a few hours (it's a thin read-only wrapper, no auth flow, no
challenge/2FA dance like insta-mcp). The hard part is *reliability*, not code:
bot-detection means tools fail intermittently and need proxy + `ms_token` refresh.

---

## 5. Account-state notes (what changes setup)

- **Personal vs Business/Creator account:** irrelevant for the **unofficial** public
  scraper (it reads anyone's public data regardless). Matters only for the
  **official API** — a Business account unlocks the Ads/Marketing API
  (`tiktok-ads-mcp`); a personal account is limited to Display API scopes
  (own public posts + profile).
- **No "flagged" axis like IG, but a shadowban axis exists.** Unofficial scraping
  doesn't log into your account, so it won't get *your account* banned the way IG's
  private API did — but heavy scraping from one IP gets **IP-blocked** (the
  `EmptyResponseException`). If you ever add *authenticated* actions (don't, per
  Lane A), then your account ban risk returns and a residential proxy +
  human-pacing become mandatory, exactly like the flagged-IG playbook.
- **Region:** TikTok geo-localizes results to the egress IP. The Byteful RO exit
  will bias trending/search toward Romania; for global/region-specific research,
  the proxy region is a knob. Match it to intent.
- **Local (home residential IP) vs Cloud (datacenter):** LOCAL = no proxy, lowest
  block rate. CLOUD = **must** use the Byteful residential proxy or TikTok blocks
  almost immediately — same egress rule already established for IG/FB in
  `social-mcp-deploy`.
- **`ms_token` lifecycle:** it expires; refresh by re-copying the cookie from a
  logged-in `tiktok.com` browser session. No automated re-auth (there's no login),
  so treat a sudden empty-response spike as "refresh `ms_token` and/or rotate proxy
  exit" — the TikTok analogue of "IG → `node login.mjs`".

---

## Confidence summary

- DMs unreadable by any route; no maintained lib reads authenticated own-account
  TikTok — **HIGH** (multiple sources + explicit library docs + dead szdc).
- `davidteather/TikTok-Api` alive, public-data-only, cannot post — **HIGH**
  (PyPI/GitHub, v7.3.3 Apr 2026, README explicit).
- Official Display API has no saved/feed/following/DM scope — **HIGH** (confirmed
  against developers.tiktok.com/doc/tiktok-api-scopes).
- `Seym0n/tiktok-mcp` = TikNeuron paid SaaS, public-only; `terrylinhaochen` mocks —
  **HIGH** (repo READMEs).
- Cloud egress needs residential proxy; LOCAL home IP doesn't — **HIGH** (consistent
  with the toolchain's IG/FB proxy research + TikTok bot-detection sources).

## Sources

- https://github.com/davidteather/TikTok-Api · https://pypi.org/project/TikTokApi/ · https://davidteather.github.io/TikTok-Api/
- https://github.com/szdc/tiktok-api (archived 2021)
- https://github.com/Seym0n/tiktok-mcp · https://www.pulsemcp.com/servers/seym0n-tiktok
- https://github.com/terrylinhaochen/tiktok_mcp · https://github.com/yap-audio/tiktok-mcp · https://github.com/fmd-labs/viral-app-mcp
- https://github.com/AdsMCP/tiktok-ads-mcp-server · https://github.com/ysntony/tiktok-ads-mcp
- https://developers.tiktok.com/doc/tiktok-api-scopes · https://developers.tiktok.com/doc/display-api-get-started/ · https://developers.tiktok.com/doc/scopes-overview
- https://github.com/zetreex/TikTok-Unauthorized-API · https://github.com/mangledbottles/Musically-API · https://tikapi.io/
