# userscripts/

Browser **userscripts** (Tampermonkey / Violentmonkey) — small, self-contained
`*.user.js` automations that run on specific sites. Unlike `tools/web/` (web-mediated
*tool contracts* an agent drives), these are personal browser-side conveniences you
install once and click.

## Install (any userscript here)

1. Install [Tampermonkey](https://www.tampermonkey.net/) (or Violentmonkey) in your browser.
2. Open the `.user.js` file (raw) — the manager offers to install it.
3. Updates: bump `@version` and re-open, or paste the file over the existing script.

## Scripts

### `github-pat-quick-fill.user.js` — GitHub fine-grained PAT: max all permissions

One-click fills **every** permission on the GitHub fine-grained PAT creation page
(`github.com/settings/personal-access-tokens/new`) and sets each to its **maximum**
access level.

- **DOM-driven, nothing hardcoded** — permission names are read from GitHub's live
  "Add permissions" picker, so the script **survives GitHub adding/removing permissions**.
- **Handles every permission category** (Repository, Account, and any future one):
  scrolls to mount lazily-rendered sections, finds each category's "Add permissions"
  trigger by text *or* `aria-label`, and re-scans across passes.
- Access levels are ranked by text (`Admin > Read and write > Read-only`), so new
  levels rank sanely; read-only-max permissions are left as-is.
- Two floating buttons on the PAT page: **🔑 PAT Quick Fill** (prefill name/owner/
  expiration via URL params) and **⚡ Max ALL Permissions** (the DOM sweep). The sweep
  is **idempotent** — click again to catch any stragglers on a sluggish render.

Usage: open the PAT page → click **⚡ Max ALL Permissions** → wait (~30–60 s for the
full sweep) → review → **Generate token**.

> Note: GitHub replaced the old "every permission is a checkbox" form with an
> "Add permissions" picker model. This script targets that current UI (v8.x); the
> older-UI checkbox path is kept as a safety net.
