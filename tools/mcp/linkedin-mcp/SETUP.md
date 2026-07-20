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

Two of the four are **secrets** — `LINKEDIN_ACCESS_TOKEN` and
`LINKEDIN_CLIENT_SECRET`. Never type either as a literal at an interactive
prompt (see the warning below); set them with the non-echoing method instead.
The other two are not secrets and can be assigned directly:

```powershell
# Not secret — only needed for linkedin_exchange_code / linkedin_token_status
$env:LINKEDIN_CLIENT_ID    = "<Client ID from step 2>"
$env:LINKEDIN_REDIRECT_URI = "<the redirect URL you added in step 3>"
```

### ⚠ Do NOT use `setx` for the token

`setx LINKEDIN_ACCESS_TOKEN "<token>"` puts the secret in **two** durable places
at once: your shell's command history (`PSReadLine`'s `ConsoleHost_history.txt`,
plaintext, on disk) **and** the registry under `HKCU\Environment`, plaintext,
readable by every process running as you, inherited by every future process.
Deleting the variable later does not scrub the history file. Treat any token
that has been through `setx` as compromised — regenerate it (step 6).

The same applies to plain `$env:X = "<token>"` typed at an interactive prompt:
the literal lands in your history file.

### The safe way — non-echoing, session-scoped

Paste the token into a prompt that does not echo it and does not record it:

```powershell
$sec = Read-Host -AsSecureString 'Paste the LinkedIn access token'
$env:LINKEDIN_ACCESS_TOKEN = [System.Net.NetworkCredential]::new('', $sec).Password

# Only if you use linkedin_exchange_code / linkedin_token_status:
$sec = Read-Host -AsSecureString 'Paste the LinkedIn client secret'
$env:LINKEDIN_CLIENT_SECRET = [System.Net.NetworkCredential]::new('', $sec).Password

Remove-Variable sec
```

The value now lives only in this shell's process memory. Nothing is written to
disk, the registry, or your history file, and it disappears when the shell exits.

**Important:** an MCP server inherits the environment of the process that
launched it, so you must **start Claude Code from this same shell** (`claude`)
for the variable to reach the server. Launching Claude from the Start Menu or a
different terminal will NOT see it, and `linkedin_auth_status` will report the
token as missing.

If you genuinely need it to survive reboots, use Windows Settings →
*Edit environment variables for your account* (a GUI field — no shell history),
and accept that it is then stored in the registry in plaintext. Prefer
re-pasting it per session; the token only lasts 60 days anyway.

## 8. Enable and verify the MCP

1. **Register it on the surface Claude actually reads.** Claude Code resolves
   user-scope MCP servers from the root `mcpServers` object of
   `~/.claude.json` — **not** from `~/.mcp.json` (that file is *project* scope
   and additionally needs per-project approval via `enabledMcpjsonServers`,
   which is empty here, so servers declared only there stay dark). Because a
   running Claude session rewrites `~/.claude.json` every ~30 s, a hand-edit made
   while Claude is open is silently clobbered.

   Use the bundled script, which enforces that for you:

   ```powershell
   # Read-only preflight -- safe to run any time, even with Claude open:
   C:\Python314\python.exe .\tools\mcp\linkedin-mcp\apply_linkedin_userscope.py --check

   # For real -- CLOSE EVERY CLAUDE WINDOW FIRST:
   C:\Python314\python.exe .\tools\mcp\linkedin-mcp\apply_linkedin_userscope.py --apply
   ```

   It refuses to write while any Claude process is alive, backs up
   `~/.claude.json` first (and verifies the backup is non-empty), drives the
   supported `claude mcp add --scope user` CLI rather than hand-patching JSON,
   and re-reads the file afterwards to prove the entry landed.

   Add `--enable` to leave it switched on; the default registers it and adds
   `"linkedin"` to the root `disabledMcpServers` array.

   > **Caveat, measured 2026-07-20:** root `disabledMcpServers` is not a reliable
   > off-switch on this box — `apify` and `biomni-hub` are both listed in it yet
   > their tools are live in a session. The only *guaranteed* off state is not
   > being registered at all:
   > `apply_linkedin_userscope.py --apply --remove`.
   > There is no active `enforce-mcp-defaults` hook here — `~/.claude/settings.json`
   > registers 18 hook events and none of them reference it, and
   > `enforce-mcp-defaults.py` exists only inside scratch agent-worktrees. Do not
   > rely on `~/.claude/.mcp-disabled-defaults.json` to keep this server off.

2. No venv needed: the roster launches the server with the system
   interpreter `C:\Python314\python.exe`, which already has `mcp` and
   `fastmcp` importable (verified by a live stdio handshake against
   `server.py`). This matches its sibling hubs (social-hub, search-hub,
   cloud-hub). `uv sync` remains optional if you want an isolated venv —
   point the roster `command` at `.venv/Scripts/python.exe` if you do.
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
