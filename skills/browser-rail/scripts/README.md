---
title: README
type: note
permalink: dqverify-repo-20261013/skills/browser-rail/scripts/readme
---

# browser-rail scripts

| File | What it is | Verified how |
|---|---|---|
| `Start-BrowserRail.ps1` | Idempotent CDP profile launcher (Chrome/Edge) | Live: 8 scenarios (Chrome+Edge) |
| `browser_rail.py` | Playwright helper; pure half + lazy browser half | Pure half: 45 unit tests. Browser half: 1 live probe, no automated tests |
| `test_browser_rail.py` | Unit tests for the PURE half (no browser needed) | 45 passed |
| `mutation_probe.py` | Both-states check: do the tests actually fire? | 6/6 mutations caught |
| `manual_probe_live.py` | Exercises the browser half against a running rail | Live on example.com (unauthenticated) |

> **Scope of the "Verified how" column (residual, stated inline).** The 45 unit
> tests exercise the PURE half of `browser_rail.py` only. The browser-driving
> half (`rail`, `find_or_open_page`, `visible_role_names`, `is_authed`,
> `evaluate_with_arg`, `upload_text_as_file`, `post_json`) is `# pragma: no
> cover` and has **no automated tests**; its only check is `manual_probe_live.py`,
> run once against **example.com, which is not an authenticated site**. So the
> auth-detection path (`is_authed`/`classify_auth` end-to-end on a real logged-in
> page) is UNVERIFIED against a live signed-in site, the exact workload the rail
> exists for. Settle it by running `manual_probe_live.py` against a site the owner
> is actually signed into. The "8 scenarios" above is the count of launcher runs
> shown in PR #163, not proof that every branch of the script was exercised.

## Run

```powershell
pwsh -File Start-BrowserRail.ps1 -Status      # is the rail up?
python -m pytest test_browser_rail.py -q      # pure logic, no browser
python mutation_probe.py                      # are the tests load-bearing?
python manual_probe_live.py                   # browser half (needs a live rail)
```

## Measured, 2026-07-24 (Windows 11, Chrome 150.0.7871.129, Playwright 1.61.0)

- `GET http://127.0.0.1:9222/json/version` → **HTTP 200**, live
  `webSocketDebuggerUrl`. Probed over raw HTTP, independently of Playwright.
- Launcher cold path on Edge `151.0.4129.35`, port 9333, fresh profile:
  `profile_created=true` → `launched=true` → **SUCCESS**; re-run →
  `launched=false` (idempotent); `-Stop` → port dead.
- Safety guards fire: a mismatched `-ProfileDir` on a live port reports FAILED
  instead of attaching, and `-Stop` refuses a foreign profile (the browser was
  still serving HTTP 200 afterwards).
- `driver_start_plus_connect=5.23s` — this spans Playwright DRIVER startup plus
  `connect_over_cdp`, **not** the CDP handshake alone. The sub-second figure often
  quoted for `connect_over_cdp` excludes bringing the driver up. Subsequent
  navigation was `2.38s`.
- `page.accessibility` is **absent** in Playwright 1.61.0
  (`hasattr(Page, "accessibility") == False`) — role locators are the a11y path.

## Known limits

- `assert_payload_not_inlined` skips payload strings under 12 characters, by
  design. It is a lint, not a proof.
- The playwright-touching functions have no automated tests; mocking Playwright
  would only assert that the mock works. `manual_probe_live.py` is their check;
  and it has only run against example.com (unauthenticated), so the logged-in
  path is UNVERIFIED end-to-end against a real signed-in site.
- The `--extension` bridge in `../references/playwright-mcp-extension.md` was read
  from `--help` but never installed or exercised.