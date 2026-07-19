# linkedin-mcp — owner setup (the unblocker)

This is the one thing only you can do: create a LinkedIn developer app, request
the two self-serve products, and generate an access token. ~10 minutes. After
step 6 the MCP works. Screen/tab/button labels below are the **actual** ones on
the LinkedIn Developer Portal as of 2026 — if LinkedIn renames one, the shape of
the flow is unchanged.

> You never paste a token into this repo. You put it in your **environment**
> (step 7). Nothing here is committed.

---

## 0. Prerequisite: a LinkedIn Page (mandatory, no bypass)

Creating an app **requires** associating it with a LinkedIn **Page** (company
page). You don't need a real company — a solo developer creates their own free
Page and becomes its **super admin**, which lets you self-approve your own app
verification in step 4.

- If you already administer a Page, skip to step 1.
- Otherwise create one: go to <https://www.linkedin.com/company/setup/new/>,
  pick **Company**, fill in a name (anything you control, e.g. "Darias Dev"),
  tick the verification box, and click **Create page**. You are now its super
  admin.

## 1. Create the app

1. Go to <https://www.linkedin.com/developers/apps> and click **Create app** (top
   right).
2. On the **Create an app** page fill in:
   - **App name** — anything, e.g. `agent-linkedin-mcp`.
   - **LinkedIn Page** — type your Page's name or URL and select it (this is the
     mandatory association from step 0).
   - **App logo** — upload any square image (required to submit).
   - Tick the **legal agreement** box.
3. Click **Create app**.

## 2. Note your Client ID and Client Secret

1. Open your new app and click the **Auth** tab.
2. Under **Application credentials** you'll see **Client ID** and
   **Primary Client Secret** (click the eye/copy icon to reveal the secret).
3. Keep these for step 7. Treat the secret like a password — never commit it.

## 3. Add a redirect URL (only needed if you drive OAuth yourself)

Still on the **Auth** tab, under **OAuth 2.0 settings → Authorized redirect URLs
for your app**, click **Add redirect URL** and add one:

- If you'll use the **token generator** (recommended, step 5) you can still add
  a placeholder like `https://localhost/callback`.
- If you'll run the 3-legged flow yourself, add the exact callback your code
  listens on (e.g. `https://localhost:8000/auth/linkedin/callback`). It must
  match **exactly** — no `#`, query params are ignored.

## 4. Verify the app for your Page

1. Click the **Settings** tab.
2. Click **Verify** (next to your Page).
3. In the **Verify company** dialog click **Generate URL**.
4. Copy the URL. As the Page **super admin** (step 0), open it yourself and click
   **Verify** — done. (If someone else admins the Page, send them the URL; they
   have 30 days.)

## 5. Request the two self-serve products

1. Click the **Products** tab.
2. Find **Sign In with LinkedIn using OpenID Connect** → click **Request access**.
   It is granted **instantly** (no review). This gives the `openid`, `profile`,
   `email` scopes → powers `linkedin_whoami`.
3. Find **Share on LinkedIn** → click **Request access**. Also granted
   **instantly**. This gives the `w_member_social` scope → powers the posting
   tools.
4. Wait ~1 minute, then reload — both should show under **Added products**.

> Do **not** request Advertising API, Community Management, Marketing Developer
> Platform, etc. — those are review/partner-gated and the MCP doesn't use them
> (see the README "Deliberately NOT built" section). Requesting them won't help
> and may stall on review.

## 6. Generate an access token (the fast path — no code)

1. Go to the **token generator**:
   <https://www.linkedin.com/developers/tools/oauth/token-generator>
   (also reachable from the app's **Docs and tools** menu → **Token Generator**).
2. **Select the app** you created.
3. Tick the **scopes** you want the token to carry — at minimum:
   `openid`, `profile`, `email`, `w_member_social`.
4. Click **Request access token**. LinkedIn shows its **authorization** screen —
   click **Allow**.
5. On the **Token Details** screen click **Copy token**. This is your
   `LINKEDIN_ACCESS_TOKEN`. It is valid for **60 days** (5,184,000 s); after that,
   repeat step 6 to mint a new one.

> Alternative (only if you prefer running OAuth yourself): call the MCP's
> `linkedin_authorization_url` tool to build the consent URL, open it, approve,
> copy the `code` off your redirect, and pass it to `linkedin_exchange_code`
> within 30 minutes. The token generator above is simpler and needs no redirect
> server.

## 7. Put the credentials in your environment

Export these in the environment the MCP server launches from (PowerShell shown;
adapt for your shell). **Do not** paste them into any file in this repo.

```powershell
# PowerShell — current session
$env:LINKEDIN_ACCESS_TOKEN = "<paste the token from step 6>"
# Optional (only if you use linkedin_exchange_code / linkedin_token_status):
$env:LINKEDIN_CLIENT_ID     = "<Client ID from step 2>"
$env:LINKEDIN_CLIENT_SECRET = "<Client Secret from step 2>"
$env:LINKEDIN_REDIRECT_URI  = "<the redirect URL you added in step 3>"
```

To persist across sessions, set them as **User environment variables** (Windows
Settings → *Edit environment variables for your account*) or via
`setx LINKEDIN_ACCESS_TOKEN "<token>"` (note: `setx` truncates at 1024 chars — a
LinkedIn token fits, but if a future token is longer, use the Settings UI).

## 8. Enable and verify the MCP

1. The server is registered in `tools/mcp/canonical-mcp-servers.json` (the roster
   — exposed/visible). To keep the standing "exposed but disabled" default when
   you **promote** the canonical set to user scope (`hooks/mcp-userscope-sync/
   promote-mcp-userscope.ps1`, run with Claude closed), add `"linkedin"` to
   `~/.claude/.mcp-disabled-defaults.json` so the enforce-mcp-defaults hook keeps
   it off in every project (same treatment as the research MCPs). Then **enable
   it only where you want it** by removing `"linkedin"` from that project's
   `disabledMcpServers` array in `~/.claude.json` and restarting Claude Code
   (repo `docs/SETUP-GUIDE.md` §6 has the exact steps).
2. Build the venv once: `cd tools/mcp/linkedin-mcp && uv sync`.
3. In a session, call `linkedin_auth_status` — it should now report
   `"can_post": true` and your token's expiry. Then try `linkedin_whoami`.
4. First real post: `linkedin_post_text(text="Hello from my MCP", visibility="CONNECTIONS")`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| every tool: `LINKEDIN_ACCESS_TOKEN is not set` | env var not exported in the server's environment | step 7, then restart the session |
| `401` / "expired access token" | token older than 60 days or revoked | regenerate (step 6) |
| `403` on `linkedin_whoami` | token lacks `openid`/`profile` | regenerate the token with those scopes ticked (step 6.3) |
| `403` on posting | `w_member_social` not on the token, or Share product not added | add **Share on LinkedIn** (step 5.3), regenerate the token |
| `403` on comment/react | `w_member_social_feed` is **partner-gated** — a personal app cannot get it | expected; not fixable self-serve (see README) |
| `invalid scope` on the authorization URL | a scope your app doesn't have | request the matching product (step 5), or drop the scope |

Scopes are fixed **at token-issue time** — after adding a product you must
**regenerate the token** for the new scope to take effect.
