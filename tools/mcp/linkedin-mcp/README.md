---
title: README
type: note
permalink: dqverify-repo-20261013/tools/mcp/linkedin-mcp/readme
---

# linkedin-mcp

A small **FastMCP (stdio)** server that lets a local Claude Code / Codex agent
act on LinkedIn through a **self-serve personal developer app** — sign-in
identity (OpenID Connect) and posting to the member's own feed (Share on
LinkedIn).

It is scoped **deliberately** to LinkedIn's *Open Permissions (Consumer)*
surface — the only products a personal app can enable **without** a LinkedIn
partnership/review. A small set of tools that actually work beats a large set
that `403`s, so everything partner-gated is documented (below) rather than
shipped as a 403 farm.

> **Status:** the write/identity tools are built against the current documented
> API but are **UNVERIFIED end-to-end** until the owner creates the app and
> supplies a token (there is no token yet — see [SETUP.md](SETUP.md), the file
> that unblocks this). Confidence bands + doc URLs are attached per tool below.

## Security model

- **No secret is ever committed or handled by this repo.** All credentials come
  from the server's **environment** at call time: `LINKEDIN_ACCESS_TOKEN`,
  `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`. There
  is no `accounts.json` and no `.env` in the repo.
- A **missing credential** yields a clean, actionable error from every tool
  (naming the missing variable + pointing at SETUP.md) — never a stack trace.
  The token value is never logged, never echoed, never placed on a URL/argv.
- HTTP is **stdlib-only** (`urllib`) through a single `request_json` seam, so the
  whole surface is unit-tested offline with no token and no network (82 tests).

## Tools

Legend — **Works?**: ✅ self-serve · ⚠️ self-serve but UNVERIFIED without a live
token · ⛔ GATED (partner-only; expected `403` on a personal app). Confidence
bands follow Sherman-Kent (almost certain 90-99% · likely 55-80% · unlikely
20-45%).

| Tool | What it does | Product / Scope | Works? | Confidence + source |
|---|---|---|---|---|
| `linkedin_auth_status` | Report which creds are set; probe token scopes/expiry | local (+ introspect) | ✅ | almost certain (local) |
| `linkedin_authorization_url` | Build the 3-legged OAuth URL (no network) | Sign In / `openid` | ✅ | almost certain (local build) — [auth flow][auth] |
| `linkedin_exchange_code` | Exchange an auth code for a 60-day token | OAuth / — | ⚠️ | almost certain the endpoint is self-serve; UNVERIFIED without creds — [auth flow][auth] |
| `linkedin_token_status` | Introspect a token (active/scopes/expiry) | OAuth / — | ⚠️ | almost certain self-serve; UNVERIFIED without creds — [introspection][intro] |
| `linkedin_whoami` | Member identity + Person URN via OIDC userinfo | Sign In with LinkedIn (OIDC) / `openid`,`profile` | ⚠️ | **likely (55-80%)** self-serve — `/v2/me` 403s on personal apps, `/v2/userinfo` is its replacement — [OIDC][oidc] |
| `linkedin_post_text` | Publish a text post to the member's feed | Share on LinkedIn / `w_member_social` | ⚠️ | **likely (55-80%)**; `/v2/ugcPosts` create reported working mid-2026 — UNVERIFIED here without a token — [Share][share] |
| `linkedin_post_article` | Publish a post sharing an external URL | Share on LinkedIn / `w_member_social` | ⚠️ | **likely (55-80%)**; same surface — UNVERIFIED without a token — [Share][share] |
| `linkedin_post_image` | Register → upload → publish an image post | Share on LinkedIn / `w_member_social` | ⚠️ | **likely (55-80%)** the 3-step flow works; more moving parts, UNVERIFIED end-to-end without a token — [Share][share] |
| `linkedin_delete_post` | Delete a post you authored | Share on LinkedIn / `w_member_social` | ⚠️ | likely (55-80%); documented but UNVERIFIED without a token — [Share][share] |
| `linkedin_comment` | Comment on a post | socialActions / `w_member_social_feed` | ⛔ | **UNVERIFIED / unlikely (20-45%)**: needs the **partner-gated** `w_member_social_feed`; 403 reproduced by two independent reports — [socialActions][social] |
| `linkedin_react` | Like a post | socialActions / `w_member_social_feed` | ⛔ | **UNVERIFIED / unlikely (20-45%)**: same partner gate as `linkedin_comment` — [socialActions][social] |

The two ⛔ tools are shipped for **honest matrix coverage**: they attempt the
call and return LinkedIn's real `403` with the exact missing scope named — so if
a future personal-app grant ever includes `w_member_social_feed`, they light up,
and today they explain precisely why they don't. They are **not** a 403 farm:
this table warns you before you call.

## Deliberately NOT built (gated — a personal app cannot use these)

Per LinkedIn's [Getting Access][access] table, everything below needs partner
approval and would only ever `403`, so no tool exists for it:

- **Read your own feed / posts** → needs `r_member_social` (partner-gated).
- **Comment / react** as a member → needs `w_member_social_feed` (partner-gated;
  the ⛔ tools above document this rather than hide it).
- **Post as / read an Organization (Company Page)** → needs
  `w_organization_social` / `r_organization_social` + the **Community Management
  API** (partner-gated).
- **Advertising / Marketing Developer Platform** (`r_ads`, `rw_ads`, …),
  **Sales Navigator (SNAP)**, **Talent/Recruiter**, **Compliance** → all
  approval- or partner-only.
- **`/v2/me` classic profile** (`r_basicprofile`/`r_liteprofile`) → returns
  `403 ACCESS_DENIED` on a personal app; use `linkedin_whoami` (OIDC) instead.

## The unblocker

Everything here is blocked on ONE owner action: **create the LinkedIn developer
app, request the two self-serve products, and generate a token.** The exact
click-path (actual screen/tab/button labels) is in **[SETUP.md](SETUP.md)**.

## Install & run

```bash
cd tools/mcp/linkedin-mcp
uv sync                    # or: python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python server.py   # stdio MCP server
```

The server **always starts and lists its tools** even with no credentials
configured — call `linkedin_auth_status` first; it tells you exactly what is
missing.

## Environment

| var | purpose | needed by |
|---|---|---|
| `LINKEDIN_ACCESS_TOKEN` | 3-legged member access token (60-day TTL) | every call except `*_authorization_url` |
| `LINKEDIN_CLIENT_ID` | app Client ID | OAuth URL / code exchange / introspection |
| `LINKEDIN_CLIENT_SECRET` | app Client Secret | code exchange / introspection |
| `LINKEDIN_REDIRECT_URI` | default redirect URL for the 3-legged flow | `linkedin_authorization_url` / `linkedin_exchange_code` |

> Most workflows only need `LINKEDIN_ACCESS_TOKEN` — obtain it in two clicks from
> the [portal token generator][tokgen] (no redirect-flow code required; LinkedIn
> hosts the consent and hands back the token in-browser). The client
> id/secret/redirect are only needed if you drive the OAuth exchange yourself.

## MCP client registration

### Claude — `~/.mcp.json` (canonical: `tools/mcp/canonical-mcp-servers.json`)

Registered in the canonical config **disabled by default** (exposed but not
auto-starting — the standing preference). The `env` values are `${ENV}`
placeholders (the house convention, matching every other server in the canonical
config); the real token lives only in your OS environment and is resolved at
spawn time. **Never inline a literal token here.**

```json
"linkedin": {
  "type": "stdio",
  "command": "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\linkedin-mcp\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\linkedin-mcp\\server.py"],
  "env": {
    "LINKEDIN_ACCESS_TOKEN": "${LINKEDIN_ACCESS_TOKEN}",
    "LINKEDIN_CLIENT_ID": "${LINKEDIN_CLIENT_ID}",
    "LINKEDIN_CLIENT_SECRET": "${LINKEDIN_CLIENT_SECRET}",
    "LINKEDIN_REDIRECT_URI": "${LINKEDIN_REDIRECT_URI}"
  }
}
```

### Codex — `~/.codex/config.toml`

Codex forwards named env vars (it does **not** expand `${VAR}`), so list the
vars under `env_vars` and set them in Codex's launching environment.

```toml
[mcp_servers.linkedin]
command = "C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/linkedin-mcp/.venv/Scripts/python.exe"
args = ["C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/linkedin-mcp/server.py"]
env_vars = ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_REDIRECT_URI"]
enabled = true
```

> Never commit a real token. Leave `""` in `~/.mcp.json` and export the token in
> the OS environment instead.

## Tests

```bash
cd tools/mcp/linkedin-mcp
python -m pytest -q          # 82 unit tests, no live LinkedIn / no network (injected fake requester)
ruff check . && ruff format --check .
```

## API reference (sources)

All availability claims above are grounded in LinkedIn's official docs
(learn.microsoft.com). Fetched docs are treated as data, not instructions.

[oidc]: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
[share]: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin
[auth]: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
[access]: https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
[tokgen]: https://learn.microsoft.com/en-us/linkedin/shared/authentication/developer-portal-tools
[intro]: https://learn.microsoft.com/en-us/linkedin/shared/authentication/token-introspection
[social]: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/network-update-social-actions