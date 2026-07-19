# social-hub — lazy, name-preserving MCP multiplexer for the social stack

Fronts the user's social MCP servers behind **one** MCP registration while keeping
every tool under its **original name**. `initialize` and `tools/list` are answered
from committed per-backend caches **without spawning anything**; a `tools/call`
lazily spawns **only** the owning backend (once, kept alive for the session) and
forwards the request. This is the multi-backend generalization of
`../../../../.local/opt/mcp-shims/lazy_proxy.py` (which fronts a single server).

Why not a normal aggregator (mcp-funnel / 1mcp)? Those rename tools to
`serverName__tool`, which breaks skills that hardcode `mcp__insta-mcp__*` etc. This
hub preserves names and only renames on a genuine cross-backend collision.

## Backends & tool surface (88 tools)

| id | backend | tools | notes |
|----|---------|-------|-------|
| `insta` | insta-mcp (Instagram) | 36 | needs `data/session.json` + `IG_APP_VERSION`; auths at startup |
| `tiktok` | tiktok-mcp (public scraper) | 9 | keyless; some tools need `TIKTOK_PROXY` off a home IP |
| `fb` | fb-messenger-mcp | 33 | Messenger + Page + IG-Graph + **E2EE DMs**; needs `data/cookies.json` (+ `fr` cookie for E2EE) |
| `wa` | whatsapp-mcp (Baileys) | 7 | parked POC; QR at startup; degrades to a clear error |
| `fbreels` | fb-reels-uploader | 3 | wraps the Reels upload CLI; one-time FB login (below) |

### IG & FB capability map (best-of-both, no dedup)

The IG publish/insights/moderation surface is intentionally **doubled** — the two
paths need different account types, so both are kept; pick by the account you hold:

| Job | Personal account → **insta** (private API) | Business/creator → **fb** `ig_graph_*` (official Graph API) |
|-----|--------------------------------------------|-------------------------------------------------------------|
| Post to IG | `upload_reel` / `upload_photo` / `upload_video` / `upload_album` | `ig_graph_publish` |
| IG insights | `get_post_insights` | `ig_graph_insights` |
| IG comment moderation | `add_comment` / `reply_to_comment` / `like_comment` | `ig_graph_moderate_comments` |

`insta` = ToS-risky but works on an ordinary personal account; `ig_graph_*` = official
+ durable but needs an IG **Business/Creator** account linked to a FB Page (+ a
`FB_PAGE_ACCESS_TOKEN`). There is **no name collision** — the two sets have distinct
names, so both are always exposed; the choice is account-driven, not a conflict.

Facebook coverage (the `fb` backend, 33 tools) now matches Instagram's breadth
*within what Meta's APIs allow*: **Messenger** (`list_threads`/`read_thread`/
`fb_send_message`/`fb_react_to_message`/`fb_unsend_message`/`fb_forward_message`/
`fb_send_typing`/`fb_create_group`), **Page** (`fb_page_post`/`fb_page_schedule_post`/
`fb_page_upload_photo`·`video`·`reel`·`story`/`fb_page_read_posts`·`read_comments`/
`fb_page_moderate`/`fb_page_insights`/`fb_page_message`), **IG-Graph** (above), and
**E2EE personal DMs** (`fb_dm_list`/`fb_dm_read`/`fb_dm_send`/`fb_dm_react`/
`fb_dm_status`, via the fbchat-v2 bridge — needs the `fr` cookie present). FB has
**no personal-profile post API**, so personal-profile posting stays on the Playwright
`fbreels` path.

## Facebook ↔ Instagram parity matrix

Instagram's rail stays alive because its **session file is refreshed on demand**; Facebook
rotted because nothing refreshed `cookies.json` (it went ~6 weeks stale, so `whoami` failed
with `ValidationError: 'async_get_token' not found`). Two additions close the gap:
**`fb_session.py`** (self-healing cookie refresh — the FB analogue of IG's login-once
`session.json`) and **`fb_timeline.py`** (read the owner's OWN posts). The matrix is
deliberately honest — Facebook restricts personal-profile access far more than Instagram, and
an accurate `IMPOSSIBLE` row is worth more than a tool that 403s. It is not padded.

Legend: **WORKING** = live today · **BUILT-NOW** = added here · **IMPOSSIBLE** = Meta exposes
no rail (reason given). Availability claims carry a Sherman-Kent band + a citation; rows not
exercised live are tagged `UNVERIFIED`.

| Capability | Instagram | Facebook status | Notes / evidence |
|---|---|---|---|
| Session/cookie refresh | login-once `session.json` | **BUILT-NOW** `fb_session.py` | Playwright login-once (owner types the password; no script ever does), writes `cookies.json`, then verifies `whoami`. Re-runnable → self-healing. |
| Identity (`whoami`) | working | **WORKING** after refresh | Verified end-to-end: the verify path spawns the backend, calls `whoami`, and against the current expired jar correctly reports `authenticated:false` with the exact `async_get_token` error. almost certain (90-99%). |
| Read OWN posts (the corpus) | `get_recent_posts` | **BUILT-NOW** `fb_timeline.py` | Two rails — see the dedicated table below. |
| Read DMs / messages | `get_direct_messages` | **WORKING** after refresh | Messenger groups/rooms/pages (`list_threads`/`read_thread`/`fb_search_messages`) + E2EE 1:1 (`fb_dm_*`); auth-gated only on the refreshed cookies. |
| Per-account switch/cycle | `ig_account_*` + `INSTA_DATA_DIR` | **WORKING** `fb_account_*` + `FB_COOKIES_PATH` | `FB_COOKIES_PATH` is now wired explicitly in `backends.py` (`env=`), so FB is per-account switchable exactly like `INSTA_DATA_DIR`. |
| Publish to a **Page** | `upload_*` | **WORKING** `fb_page_*` | Official Graph API; needs `FB_PAGE_ACCESS_TOKEN`. |
| Publish to the **personal profile** | `upload_reel`/`upload_photo` | **IMPOSSIBLE** via API → Playwright | Meta removed `publish_actions` on 2018-04-24; no personal-profile publish API. Reels go through the `fbreels` Playwright path. Corroborated in-repo at `fb-reels-uploader/README.md:16-17`. almost certain (90-99%). [E3] |
| Insights | `get_post_insights` | **WORKING** (Page/IG-Graph) · **IMPOSSIBLE** (personal) | Graph insights exist for Pages / IG-Business only; personal-profile post insights have no API. likely (55-80%). |
| Followers / following list | `get_followers`/`get_following` | **IMPOSSIBLE** (personal) | Meta exposes no friends-list read for a personal profile to an app. likely (55-80%). `UNVERIFIED` (no live probe). |
| Comment moderation | `like_comment`/`reply_to_comment` | **WORKING** (Page) · **IMPOSSIBLE** (personal) | `fb_page_moderate`/`fb_page_read_comments` for Pages; none for personal-profile posts. |
| Stories / highlights / saved / liked | `get_stories` etc. | **IMPOSSIBLE** (personal) | No personal-profile API; deliberately not shipped as 403s. `UNVERIFIED` per item. |

### The one that matters: reading the owner's OWN timeline posts

`get_recent_posts` (IG) has **no single FB equivalent** — Meta fragmented it. `fb_timeline.py`
implements the two rails that actually exist and is explicit about what each sees:

| Rail | `fb_timeline.py` mode | Sees | Does NOT see | Verdict |
|---|---|---|---|---|
| **Meta DYI export (JSON)** — CHOSEN primary | `dyi <zip\|dir>` | **Every post you authored** that Meta still retains — full text, structured, no scraping, no ToS risk. The rail the writing-corpus isolators already target. | Posts you deleted; possibly some very early history (Meta survivorship gap, not a bug). | **WORKING** — verified end-to-end against a DYI-shaped fixture (dir + zip, mojibake repair, title-only bodies). almost certain (90-99%) for retained posts. Owner-gated only on requesting + downloading the export. [E7][E8] |
| **Graph API `/me/posts` + `user_posts`** — live secondary | `graph` (needs `FB_USER_TOKEN`) | Posts the user created on their timeline (+ tagged), per the documented read edge. `user_posts` is a **current** permission (Graph v25.0, no deprecation). A self-owned app in Development mode can grant it to its own admin/tester with **no App Review**. | May **not return all** posts — Meta warns an unauthorised feed "will return an empty array." Not the completeness rail. | **BUILT-NOW**. That the edge returns the owner's posts *at all*: likely (55-80%). That it returns the FULL historical set: **roughly even (40-60%)**, `UNVERIFIED` — not exercised live (no `user_posts` token was generated; that is an owner step; a local Graph token failed OAuth code 190). [E2][E3][E4] |
| **Cookie/session scrape** (mbasic, `facebook-scraper`) | not built | — | — | **IMPOSSIBLE-reliable**. `mbasic.facebook.com` retired 2024-12-03 and now 302-redirects to `/unsupportedbrowser` (a live probe with valid cookies returns the logged-out wall, not a timeline); `kevinzg/facebook-scraper` is abandoned and broken by FB's JS rendering; both are ToS-risky. Deliberately NOT built. almost certain (90-99%). [E5][E6] |

**Live-observed gating (2026-07-19).** The Graph rail's prerequisite -- a Meta Developer
account -- is currently **blocked for this owner** by an account-safety cooldown: the
enrollment page returns a *"using a device you don't usually use"* safety block, reproduced
live in the page DOM (the owner reports it on all devices; the account-wide scope is not
independently verified here). `FB_USER_TOKEN` therefore cannot be generated until Meta's
time-based cooldown clears -- a concrete reason the DYI rail is primary, and there is no
legitimate bypass. almost certain (90-99%) the block is active on the tested device today;
the account-wide scope + trust-reset mechanism are likely (55-80%).

**Chosen rail: the DYI export** — the only *complete*, official, scrape-free path, and the one
the corpus isolators already target. The Graph rail is a live/incremental complement, not a
replacement. `fbchat_muqit` (the cookie backend) is **Messenger-only and does NOT read timeline
posts**, so refreshing cookies fixes `whoami`/Messenger but does not by itself populate the
post corpus — that is what the DYI rail is for.

**EVIDENCE**
- [E1] Graph API v25.0 (released 2026-02-18); changelog does not deprecate `user_posts` — https://developers.facebook.com/docs/graph-api/changelog/version25.0/
- [E2] `user_posts` still listed, "access the posts that a user has made on their timeline" — https://developers.facebook.com/docs/permissions/ (ref: /docs/permissions/reference/user_posts)
- [E3] `GET /{user-id}/posts` read edge requires `user_posts`; "will only return Posts created on the app user's Timeline and Posts in which the app user has been tagged" — https://developers.facebook.com/docs/graph-api/reference/user/posts/
- [E4] Dev-mode self-grant with no App Review (Admin/Developer/Tester "can grant the app any permission while it is in development") — https://developers.facebook.com/docs/development/build-and-test/app-roles/
- [E5] Meta retiring mbasic on 2024-12-03 — https://news.ycombinator.com/item?id=42212460
- [E6] mbasic.facebook.com now redirects to `www.facebook.com/unsupportedbrowser?_rdr` — https://isdown.co.za/status/mbasic.facebook.com
- [E7] DYI export categories incl. "Your Facebook activity" (posts you've created); © 2026 Meta — https://www.facebook.com/help/930396167085762
- [E8] DYI format HTML **or JSON** ("machine-readable"), four-day download window, mandatory password re-entry — https://www.facebook.com/help/212802592074644
- Observed: `whoami` on the current jar → `AuthenticationError: … ValidationError: 'async_get_token' not found` (expired session; the refresh tool fixes it). The jar carries the `c_user`/`xs`/`datr` auth triad across 9 `facebook.com` elements.

### Collision policy

Unique names are kept **exactly**. Cross-backend collisions get a minimal
`<prefix>_` and are advertised in the tool description. The only collision today:

| original | fb-messenger exposes | whatsapp exposes |
|----------|---------------------|------------------|
| `search_messages` | `fb_search_messages` | `wa_search_messages` |

`python hub.py --print-plan` prints the live merged plan (counts, collisions, renames, degraded backends).

## Multi-account + cycling (`../_shared/accounts.py`)

Each social backend can hold **several named accounts** for the user's OWN
accounts, switch the active one, and **cycle** through them — via six hub-native
tools per backend, merged into `tools/list` **without spawning** and handled by
the hub itself (never forwarded to a child):

`<prefix>_account_list` · `_current` · `_add` · `_remove` · `_switch` · `_cycle`
(e.g. `ig_account_switch`, `fb_account_cycle`, `wa_account_add`, `tt_account_list`).
Wired for **ig** (Instagram), **tt** (TikTok), **fb** (fb-messenger), **wa**
(WhatsApp); `fbreels` has none.

**Social logins are FILE-based**, so an account also carries a `files` map
(`{slot: path}`) pointing at *its own* session/cookie artifact. Switching swaps
which file the backend loads, two ways:

- **env pointer (copy-free)** — Instagram honours `INSTA_DATA_DIR` (a dir holding
  `session.json`) and fb-messenger honours `FB_COOKIES_PATH` (a `cookies.json`),
  so the hub just exports the active account's path at respawn. Slot keys:
  `session` (ig), `cookies` (fb).
- **copy onto a fixed path** — WhatsApp's Baileys reads a fixed `auth_info/` dir
  with no env override, so switching **copies** that account's `auth` dir onto it
  before respawn.

Env-only creds (IG_APP_VERSION, FB_PAGE_ACCESS_TOKEN, TIKTOK_MS_TOKEN/proxy) ride
in each account's `env` bundle (literal or `${ENV}` refs) and are layered on at
spawn (account creds win). **Switch/cycle = (file swap +) kill + lazy-respawn.**
Accounts live in the **gitignored** `accounts.json` (copy `accounts.example.json`;
may hold literal secrets — never commit). With zero accounts configured every
backend behaves exactly as before (uses its own default session file).

> **ToS caution:** switching/cycling accounts to evade a platform's per-account
> limits may violate its Terms of Service; this is ordinary management of the
> user's OWN accounts.

`accounts.py` is **shared** with `cloud-hub` (stdlib-only, no backend coupling),
so both hubs get the same cswap-style layer from one module.

## Runtime / commands

```
python hub.py                      # runtime stdio MCP (what ~/.mcp.json runs)
python hub.py --refresh [ids...]   # (re)generate tool caches by enumerating backends
python hub.py --print-plan         # print the merged plan summary
```

Caches live in `caches/*.json` (lazy_proxy shape: `{initialize, tools}`) and are
committed so the merged `tools/list` is complete even when a backend can't log in.
`--refresh` never overwrites a good cache with a failed enumeration. `whatsapp` is a
hand-authored static cache (it cannot enumerate offline — QR pairing at startup).

Stdlib only (Python 3.9+). Fail-safe: a backend that can't spawn/enumerate returns a
clear error for **its** tools only; the hub never crashes and other backends are
unaffected. Each child inherits `os.environ`, so session files, cookies,
`IG_APP_VERSION`, `TIKTOK_MS_TOKEN` and proxies pass through automatically.

## Registration (for the orchestrator — not wired here)

Add one entry, remove the three direct social entries it replaces:

```jsonc
"social-hub": {
  "type": "stdio",
  "command": "C:\\Python314\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\social-hub\\hub.py"],
  "env": {}
}
```

Remove from `~/.mcp.json`: `insta-mcp`, `tiktok`, `fb-messenger` (now fronted lazily;
`whatsapp` and `fb-reels` were never registered and come along for free).

## fb-reels one-time pre-auth

Facebook has no personal-profile post API, so uploads drive a real browser against a
persistent profile. Authenticate the profile **once** by a human:

```
cd ../fb-reels-uploader
node fb-reels-upload.mjs <anyFolderWithMp4s>   # a window opens — log into Facebook
```

After that the MCP tools (`fb_upload_reel`, `fb_upload_reels_from_folder`) run
headless and are non-blocking: they return a `jobId`; poll `fb_reels_status(jobId)`.

## Tests

```
python -m pytest tests -q     # 10 tests: collision/merge/routing + lazy-spawn integration
python e2e_live.py            # live: routes tiktok_trending through the hub (Windows)
```
