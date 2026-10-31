---
name: browser-rail
description: Use as the DEFAULT for any multi-step browser work on a site the owner
  is signed into - reading, filling, clicking, uploading, or posting across several
  turns on grok.com, chatgpt.com, a dashboard, a webmail, an admin panel, or any logged-in
  app. Drives a dedicated CDP Chrome/Edge profile with Playwright over role locators
  (the a11y tree), not pixels. Covers the Chrome-136 break where --remote-debugging-port
  is silently IGNORED on the default user-data-dir, the dedicated-profile fix, how
  the owner signs in ONCE so no credential ever passes through an agent, passing content
  as an evaluate ARG instead of inlining it into JS, and when to fall back to claude-in-chrome
  instead. Triggers include drive the browser, log into a site and do X, automate
  this web app, upload a file to a web page, attach to my Chrome, CDP, remote debugging
  port, connect_over_cdp, browser automation, or scrape a page I am logged into. NOT
  for a one-off look at a tab the owner already has open (use claude-in-chrome) and
  NOT for fetching a public page (use WebFetch or firecrawl).
permalink: dqverify-repo-20261013/skills/browser-rail/skill
---

# Browser Rail

A fast, durable rail for driving a **logged-in** browser from an agent. Attach to
a dedicated CDP profile with Playwright, resolve elements by ROLE, and never touch
a credential.

## The break this exists to route around

**Chrome 136+ ignores `--remote-debugging-port` when it points at the DEFAULT
user-data-dir.** It does not warn; the port simply never listens. Every "just
attach to the browser you already have open" recipe written before that change is
now silently dead, and the failure looks like a Playwright bug rather than a
browser policy.

The fix is a **dedicated automation profile**. A separate `--user-data-dir` is
still allowed to open the debugging port.

Measured on this box (2026-07-24): Chrome `150.0.7871.129` on port 9222 with
`--user-data-dir=C:\Users\Prekzursil\.chrome-automation` answers
`GET /json/version` with HTTP 200 and a live `webSocketDebuggerUrl`.

## Start the rail

```powershell
pwsh -File scripts/Start-BrowserRail.ps1
pwsh -File scripts/Start-BrowserRail.ps1 -Browser edge -Port 9333
pwsh -File scripts/Start-BrowserRail.ps1 -Status
```

Idempotent: if the port already answers **and** the running browser's
`--user-data-dir` is the rail profile, nothing launches and it reports
`SUCCESS:browser-rail already live ...; reused`. If the port is held by a
**different** profile it reports `FAILED` instead of attaching to whatever is
listening. `-Stop` refuses to kill a browser whose profile is not the rail
profile, so it can never close the owner's real Chrome.

It ends on a terminal line (AGENTS.md §4): `SUCCESS:browser-rail <detail>` or
`FAILED:browser-rail <reason>`.

## Credentials: the owner signs in once, you never do

**Never type, paste, request, or read a password, OTP, or recovery code.** The rail
does not need one.

1. The launcher opens the dedicated profile as a NORMAL visible browser window.
2. **The owner** signs into the sites they want automated, by hand, once.
3. Chrome persists those cookies in the profile directory. Every later attach is
   already authenticated.

The launcher creates the profile directory only when it is absent and never writes
into it — the owner's session data lives there.

Seeding the profile by copying the live one does **not** carry logins: Chrome holds
`Default/Network/Cookies` under an exclusive lock while it runs, so the copy skips
exactly the file that matters. Do not try to work around that lock. Ask the owner
to sign in.

If a probe says the session is not authenticated, the correct action is to **tell
the owner to sign in** — not to attempt a login flow.

## Drive by role, not by pixels

`page.accessibility` does **not** exist in the installed Playwright (1.61.0,
measured). Use **role locators**, which read the same accessibility tree:

```python
page.get_by_role("button", name="Send")
page.get_by_role("textbox", name="Message")
page.get_by_role("link", name="Settings")
```

Role locators beat both CSS selectors and screenshots: they survive restyling and
class-name churn, they say what the control *is*, and they cost no vision tokens.
Reach for a screenshot only to show the owner something visual, or when a canvas
element genuinely has no accessible name.

## The Python helper

`scripts/browser_rail.py`. The pure half imports without
Playwright installed; the browser half imports it lazily.

```python
from browser_rail import AuthSignals, PostRequest, find_or_open_page, is_authed, rail

SIGNALS = AuthSignals(
    logged_out_url_substrings=("/login", "/sign-in"),
    logged_out_names=("Sign in", "Create account"),
    logged_in_names=("Sign out", "New chat"),
)

with rail() as browser:                       # connect_over_cdp on 127.0.0.1:9222
    page, opened = find_or_open_page(browser, "https://grok.com/")
    verdict = is_authed(page, SIGNALS)
    if verdict.authed is not True:
        raise SystemExit(f"ask the owner to sign in ({verdict.reason})")
```

`find_or_open_page` REUSES a tab already on that domain — usually the
authenticated one — instead of opening a duplicate that loses page state. Its
match is host-based, so `notgrok.com` and `https://evil.com/grok.com` do not
count as `grok.com`.

### Three auth states, not two

`is_authed` returns an `AuthVerdict` whose `authed` is `True`, `False`, or
**`None` = UNKNOWN**. `None` means no configured signal fired; it is NOT a
synonym for "logged out". A detector's silence is not evidence.

Configure BOTH directions and check `signals.both_states_ready` — a signal set
with only logged-out markers can never return `True`.

This is not theoretical. During live verification the probe was configured with
example.com's OLD link text ("More information"); the page now renders "Learn
more". The verdict came back `None / no-signal-fired` rather than a confident
wrong answer. A one-directional detector would have reported "logged out".

Ambiguity resolves to **not authed** on purpose: a false "not authed" costs one
manual check, a false "authed" sends the agent into a confusing downstream
failure.

### Pass content as an ARG — never inline it into JS

Concatenating content into a JS source string re-parses it as code. Quotes,
backslashes, and `</script>` in the payload then change what executes.

```python
evaluate_with_arg(page, "(arg) => arg.text.length", {"text": body})   # correct
page.evaluate(f"() => '{body}'")                                       # WRONG
```

`evaluate_with_arg`, `upload_text_as_file`, and `post_json` all route through
`assert_payload_not_inlined`, which raises `PayloadInlinedError` when caller
content appears verbatim in the source. **Stated limit:** it only scans payload
strings of 12+ characters, because shorter strings occur naturally in ordinary JS.
It is a lint against the common mistake, not a proof.

`post_json` fetches from the page's own origin with `credentials: 'include'`, so
the request inherits the logged-in session — no cookie is ever extracted.

### Canonical `browser_*` verb names (Browser Use borrow)

The rail also exposes a Browser-Use-style `browser_*` vocabulary: a thin, stable
ALIAS layer so a caller can name an action the same way even if an underlying
helper is later renamed. `VERB_TABLE` maps each of the 13 borrowed verbs to the
function that implements it, and addressing stays role+name (which survives a
restyle), so this standardises only the NAMES.

- Navigate / interact: `browser_navigate` (= `find_or_open_page`, keeps tab
  reuse), `browser_click`, `browser_type`, `browser_get_state`, `browser_scroll`,
  `browser_go_back`, `browser_extract_content`.
- Tabs / sessions: `browser_list_tabs`, `browser_switch_tab`, `browser_close_tab`,
  `browser_list_sessions`, `browser_close_session` (a CDP DISCONNECT, not a quit),
  `browser_close_all`.
- The four rail-only verbs keep `browser_*` aliases too: `browser_is_authed`,
  `browser_evaluate`, `browser_upload_text`, `browser_post_json`.

Browser Use's `retry_with_browser_use_agent` is deliberately NOT adopted: the
rail is a primitive layer, not an agent runtime.

## Work over 60s runs under longrun

Crawls, multi-page sweeps, and long form flows exceed 60s. Per AGENTS.md §4a, run
them through `scripts/longrun.ps1` with `run_in_background` + `Monitor` — never a
blocking foreground call:

```powershell
pwsh -File scripts/longrun.ps1 -Id browser-sweep -HeartbeatSec 15 -HangTimeoutSec 300 `
  -Cmd python my_sweep.py
```

A browser rail is exactly the workload that stalls invisibly (a modal, an expired
session, a captcha). The heartbeat is what turns a silent hang into a `FAILED:` line.

## When to use claude-in-chrome instead

`claude-in-chrome` drives the owner's **real, already-open** browser and shows what
they see. It is the right tool when:

- the task is ONE quick look at a tab the owner already has open;
- the site is signed in on the DEFAULT profile only, and asking the owner to sign
  into the rail profile is not worth it;
- the owner wants to watch and take over mid-flow;
- an extension the automation profile lacks is required.

Use the rail instead when the work is multi-step, repeated, or scripted, when you
need deterministic role locators and real return values rather than a pixel relay,
or when opening tabs in the owner's main window would disturb their session.

Rough cost note: attaching over CDP and reading roles returns structured data,
whereas a pixel relay spends vision tokens per look. Treat that as a directional
claim, not a benchmark — no head-to-head timing was run.

## Playwright MCP `--extension` bridge

There is a third option that drives the owner's REAL profile through a browser
extension, with no dedicated profile at all. It needs a `~/.claude.json` change.
**Do not edit that file live** — it is clobbered within ~30s. The exact config
text, and both the `--extension` and `--cdp-endpoint` variants, are in
[references/playwright-mcp-extension.md](references/playwright-mcp-extension.md)
for the claude-closed lane to apply.

## Verify before you trust

```powershell
pwsh -File scripts/Start-BrowserRail.ps1 -Status   # rail alive?
python scripts/mutation_probe.py                   # tests still fire?
python scripts/manual_probe_live.py                # browser half works?
```

`mutation_probe.py` reverts six real behaviours and requires the suite to go RED on
each. A green suite that has never been mutation-checked is not evidence that it
protects anything.