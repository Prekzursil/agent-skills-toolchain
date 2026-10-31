---
title: README
type: note
permalink: dqverify-repo-20261013/tools/mcp/fb-messenger-mcp/readme
---

# fb-messenger-mcp

An MCP server for Facebook / Messenger, expanded toward Instagram-parity. Four
tiers behind one server (`fb-messenger`):

| Tier | Module | Auth | ToS |
|------|--------|------|-----|
| Read (original) | `fbmcp/read_tools.py` | facebook.com cookies | unofficial |
| **T1** Graph API (Page + pro-IG) | `fbmcp/graph.py` | Page access token | **ToS-clean** |
| **T3** non-E2EE send/react | `fbmcp/messenger_send.py` | facebook.com cookies | unofficial |
| **T4** 1:1 E2EE DM bridge | `fbmcp/dm_e2ee.py` + `fbmcp/backends/` | cookies + Go bridge | unofficial, **AGPL-3.0** |

Personal 1:1 Messenger DMs are end-to-end encrypted, so the cookie tools
(fbchat-muqit) only reach **groups / rooms / pages**. The `fb_dm_*` tools handle
E2EE 1:1 DMs via a separate bridge. See `NOTICE` / `LICENSE-AGPL-3.0`.

## Tools

* **Read:** `whoami`, `list_threads`, `read_thread`, `search_messages`, `thread_info`
* **T3 send (non-E2EE):** `fb_send_message`, `fb_send_file`, `fb_react_to_message`,
  `fb_unsend_message`, `fb_forward_message`, `fb_mark_read`, `fb_send_typing`,
  `fb_create_group`
* **T1 Graph — Page:** `fb_graph_token_info`, `fb_page_post`, `fb_page_schedule_post`,
  `fb_page_upload_photo`, `fb_page_upload_video`, `fb_page_upload_reel`,
  `fb_page_upload_story`, `fb_page_read_posts`, `fb_page_read_comments`,
  `fb_page_moderate`, `fb_page_insights`, `fb_page_message`
* **T1 Graph — Instagram:** `ig_graph_publish`, `ig_graph_insights`,
  `ig_graph_moderate_comments`
* **T4 E2EE DM:** `fb_dm_status`, `fb_dm_list`, `fb_dm_read`, `fb_dm_send`, `fb_dm_react`

(Personal-profile posting is handled by the separate `fb-reels` MCP — not
duplicated here.)

## Install

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt        # core (GPL-3.0)
.venv/Scripts/python -m pip install -r requirements-e2ee.txt   # T4 only (AGPL-3.0)
```

## Registration (`~/.mcp.json`)

The entrypoint is unchanged (`server.py`), so an existing registration already
runs the full server after a restart. To activate T1/T4, add their env vars:

```json
"fb-messenger": {
  "type": "stdio",
  "command": "C:\\Users\\Prekzursil\\source\\repos\\fb-messenger-mcp\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\repos\\fb-messenger-mcp\\server.py"],
  "env": {
    "FB_PAGE_ACCESS_TOKEN": "EAAB...long-lived-page-token",
    "FB_PAGE_ID": "1234567890",
    "FB_IG_USER_ID": "17841400000000000",
    "FB_APP_ID": "optional-for-token-info",
    "FB_APP_SECRET": "optional-appsecret-proof",
    "FB_GRAPH_VERSION": "v23.0",

    "FB_E2EE_ENABLED": "1",
    "FB_DM_PROXY": "http://user:pass@residential-proxy:port"
  }
}
```

Everything in `env` is optional per tier: the read + T3 tools need only
`data/cookies.json`; T1 needs the token vars; T4 needs `FB_E2EE_ENABLED` + the
E2EE deps + cookies with `datr`/`fr`.

## Auth — what YOU must provide

**Cookies (read + T3 + T4)** — export facebook.com cookies with the C3C browser
extension to `data/cookies.json` (or set `FB_COOKIES_PATH`). Format = the
`cookies.json.example` list. T4 additionally requires `datr` and `fr`.

**T1 Graph API** — a Meta developer app + a Facebook Page + a long-lived Page
access token. No app review is needed to manage your OWN Page/IG assets. Steps:

1. Create an app at developers.facebook.com (type: Business).
2. Add products: Facebook Login / Pages API (+ Instagram Graph API for the
   `ig_*` tools). Link your professional IG account to the Page.
3. Grant scopes: `pages_manage_posts`, `pages_read_engagement`,
   `pages_manage_engagement`, `pages_messaging`, `read_insights`, and for IG:
   `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`,
   `instagram_manage_insights`.
4. Get a User token (Graph API Explorer), exchange it for a long-lived token,
   then get the **Page** token from `GET /me/accounts`. Put it in
   `FB_PAGE_ACCESS_TOKEN`, the Page id in `FB_PAGE_ID`, and the IG account id in
   `FB_IG_USER_ID`. Verify with the `fb_graph_token_info` tool.

**T4 E2EE bridge** — `pip install -r requirements-e2ee.txt`, then provide the Go
bridge binary `fbchat-bridge-e2ee` (fbchat-v2 auto-downloads it, or build it
with Go ≥ 1.24 and set `FBCHAT_E2EE_BIN`). Set `FB_E2EE_ENABLED=1`. Run
`fb_dm_status` to confirm readiness.

## Account-ban risk (cookie tiers)

Read, T3, and T4 automate a personal account (unofficial APIs) — against Meta
ToS. Use a **warmed** secondary account, one **static residential/ISP proxy**
(`FB_DM_PROXY`) matching its geography, **human cadence**, and **low volume**.
T1 (official tokens) carries no such risk.

## Tests

```sh
.venv/Scripts/python -m pytest -q
```

Tests mock the network / bridge, so no credentials are needed. Anything needing
live FB creds (real posts/sends) is param-verified but runtime-untested here.