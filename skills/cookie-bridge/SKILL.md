---
name: cookie-bridge
description: Estate-local browser cookie/session bridge. Injects the owner's OWN web
  sessions (ChatGPT, Databricks) from a phone CDP extract into the owner's MAIN Chrome/Edge/Comet
  profiles WITHOUT the profile corruption that an earlier force-kill approach caused.
  Use for putting a logged-in web session onto a main browser profile safely, or for
  extracting/refreshing a session from a phone over ADB+CDP. NOT for third-party accounts,
  NOT for reading or exfiltrating cookie values, NOT for bypassing another site's
  auth.
metadata:
  type: reference
  risk: high
  estate_local: true
permalink: dqverify-repo-20261013/skills/cookie-bridge/skill
---

# cookie-bridge

Estate-local tooling to move the owner's **own** authenticated web sessions onto the
owner's **own** main browser profiles, safely. Every script operates on this machine's
local browser profiles; none reads or transmits a cookie value off-box.

## Why this exists (the corruption it prevents)

On 2026-07-20 an un-gated `inject_all_main_profiles.py` **force-killed** live browsers and
rebound the real User Data via CDP with **no pre-snapshot and no integrity check**. It cost
Chrome its multi-account list. The corruption vector was **force-kill + main-profile rebind
without backup/verify**, not cookie injection itself. This skill is the safe replacement.

## Hard rules (non-negotiable)

1. Prefer `safe_main_cookie_inject.py` over any kill-all inject. It snapshots
   Preferences/Cookies/Login Data first, refuses if the browser is still running, uses
   `Network.setCookie` ONLY (never a delete API), verifies integrity, and rolls back on
   failure.
2. **Never** `Network.deleteCookies` / wipe a cookie jar on a main profile.
3. **Never** rewrite `Preferences` as part of a cookie inject. Account merge is a SEPARATE
   step. (Bundling a Preferences patch into an inject is what pruned Chrome's account_info
   to 0 on 2026-07-23.)
4. Snapshot `Sessions` BEFORE closing a browser if windows must be preserved.
5. After a CDP inject (`about:blank`), restore `Sessions` from the pre-close backup before a
   normal launch.
6. Do not touch `.sso-mirror-backup-2026070*` (a separate, older concern).
7. Never print cookie values, PATs, or secret-vault plaintext.

## Gated / dangerous scripts

Two scripts force-kill browsers and are gated behind `I_ACCEPT_PROFILE_RISK=1`; they refuse
to run without it and `--help` never kills:

- `inject_all_main_profiles.py` — the legacy kill-all inject. DEPRECATED; prefer the safe tool.
- `restore_browser_sessions.py` — kill → promote largest Session/Tabs → relaunch with
  `--restore-last-session`. Kills ALL browsers, including one you may want left alone.

## Known limitation — account restore is NOT a file operation

Restoring `account_info` into `Preferences` is cosmetic: Chrome validates those entries
against OAuth refresh tokens it no longer holds and prunes them on startup. **No file-level
restore reconstitutes a signed-in Google account** — that requires manual sign-in. Do not
represent an on-disk account-list restore as a recovered login.

## Safe commands

```powershell
# status only
python safe_main_cookie_inject.py --dry-run --browser chrome,edge --payload databricks

# re-extract from phone (tabs open + USB debug)
adb forward tcp:9223 localabstract:chrome_devtools_remote
python databricks_cookie_bridge.py extract

# main inject, one browser at a time, quit that browser first
python safe_main_cookie_inject.py --browser chrome --payload databricks
```

## Script inventory

| script | role |
|---|---|
| `safe_main_cookie_inject.py` | **preferred** main inject: snapshot + integrity + graceful close |
| `safe_restore_prefs_accounts.py` | merge Chrome account_info from a backup (browsers must be quit) |
| `databricks_cookie_bridge.py` | extract/inject Databricks; default = durable isolated profile |
| `cookie_bridge.py` | phone extract/inject for ChatGPT (ADB → CDP) |
| `apply_durable.py` | apply cookies to an ISOLATED durable profile (safe, never main) |
| `restore_browser_sessions.py` | **gated** kill→restore-sessions→relaunch |
| `inject_all_main_profiles.py` | **gated, DEPRECATED** legacy kill-all inject |
| `inject_edge.py` / `inject_now.py` / `inject_selenium.py` | narrower inject variants |
| `list_session_options.py` / `print_session_summary.py` / `restore_by_ids.py` | session inspection/restore helpers |

Runtime artifacts (cookie JSON, reports, snapshots, profiles) are `.gitignore`d and never
versioned — this skill is tooling only.