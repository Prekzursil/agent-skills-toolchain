# CRCP cookie-store — phone-extracted browser session cookies (git-crypt encrypted)

These JSON files hold **real session cookies** extracted from the owner's phone (via ADB +
Chrome CDP) for reuse across the estate's browsers and tooling. They are stored **encrypted at
rest** with git-crypt (same mechanism as `tools/mcp/**/accounts.json`); they decrypt to plaintext
only after `git-crypt unlock <key>` on a trusted device.

## Contents
| File | Source account | Extracted |
|------|----------------|-----------|
| `chatgpt_cookies.json` | ChatGPT / Codex (<work-workspace-account> workspace) | 2026-07-20 |
| `databricks_cookies.json` | Databricks (bolt workspaces) | 2026-07-23 |
| `aws_cookies.json` | AWS IAM Identity Center portal + Okta SSO | 2026-07-24 |

## Reuse
Bridges + injectors live in `tools/crcp/scripts/`:
- `inject_now.py` — live CDP inject into a debug-port Chrome (the "bare Chrome tab" path).
- `safe_main_cookie_inject.py` + `restore_browser_sessions.py` — session-preserving inject into
  the MAIN Chrome/Edge/Comet profiles (backs up + restores tabs/windows; browser must be closed).
- `cookie_bridge.py` / `databricks_cookie_bridge.py` / `aws_cookie_bridge.py` — per-service
  extract/status bridges (re-pull from the phone over ADB).

Working copies also live at `~/.crcp/cookie-bridge/`; the DPAPI vault mirror is at
`~/.crcp/secret-vault/`. Inventory reports: `tools/crcp/reports/aws_phone_cookie_inventory_*.md`,
`workspace_e2e_scorecard_*.md`.

## IMPORTANT — these are session tokens, they EXPIRE
A stored cookie is reusable only until its session expires (ChatGPT/AWS/Databricks sessions last
days–weeks). The durable, truly-permanent asset is the **extraction + injection tooling** here;
when a session lapses, re-run the bridge against the phone to refresh the store. Never commit a
raw `*_cdp_cookies*.json` dump to `reports/` (not encrypted) — that path is gitignored.
