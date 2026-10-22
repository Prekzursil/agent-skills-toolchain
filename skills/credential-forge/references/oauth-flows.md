# oauth-flows — the capture ladder, per-IdP verdicts, and the hard walls

`capture.py` is a thin driver over this ladder. Every rung is owner-in-the-loop;
the ladder order is law, not preference.

## The ladder (strict preference order)

### (a) DEVICE-CODE — first, wherever the IdP offers it

- **Entra (Microsoft)**: devicecode endpoint verified LIVE 2026-10-22 (HTTP 200,
  `expires_in` 900 s, poll interval 5 s). The OWNER types the code at
  `login.microsoft.com/devicelogin` themselves; `capture.py --provider
  entra-device` prints the code + steps, and polls only when `--owner-present`
  is passed (no unattended polling on a code the owner hasn't seen).
- **gcloud**: `gcloud auth login --no-launch-browser` — prints a URL + code,
  zero browser automation.
- **GitHub**: `gh auth login` web flow — device-style handoff, zero browser
  automation.
- **az**: `az login --use-device-code` — same shape.

Why first: the code is visible to the owner; the automation never sees
credentials. This is the only rung that needs no browser at all.

### (b) SSO-COOKIE via env-held credentials — POST form

For portals with a plain login POST and no bot-wall: credentials held in env
(design: `INSTITUTIONAL_*` password-shaped vars, never logged) are POSTed to
the portal's session endpoint; the resulting cookie goes to the consuming lane
in memory. This is the institutional-literature-access recipe —
owner-sanctioned for that portal, no headless bot-wall involved. Password-shaped
env vars used here are NEVER rotated or migrated by the forge (documented
exception path — see SKILL.md capability 3).

### (c) BROWSER-ATTACH consent-click — LAST resort only

Only when ALL of: the IdP offers no device flow; the IdP has no bot-wall; the
owner explicitly initiated the capture and is watching. Driven by shelling out
to `python playwright` scripts that attach to the owner's visible browser
(attach MCP tools are NOT mounted in workflow subagents — shell-out is the
estate-verified path). Downloads-throwing flows route to browser-rail instead.

## Hard walls (refuse-paths, encoded in capture.py — not judgment calls)

| Wall | Verdict |
|---|---|
| accounts.google.com automation | **NEVER.** 6 owner accounts, lockout risk, zero verified wins. `capture.py --provider google-oauth` refuses with this citation. |
| Headless capture vs Cloudflare/Akamai-fronted IdPs (JSTOR-style) | **DEAD** — proven; do not retry headless. |
| Firefox lane | **IMPOSSIBLE** on this estate (research verdict) — no Firefox automation lane exists. |
| httpOnly cookie extraction via attach | **NEVER via attach** — the cookie-bridge phone-side lane owns httpOnly cookie capture. |
| cdp-endpoint fallback | **STAYS OFF.** |
| Profile-file session seeding (copying a Chrome profile / Cookies file) | **NEVER** — Chrome holds the Cookies file under exclusive lock; profile seeding is both broken and a contamination risk. |

## The anti-phishing-equivalence rule (verbatim doctrine)

Silent consent-click automation in a logged-in real profile is functionally an
OAuth-phishing kit. The ONLY acceptable consent-click capture is:
owner's-own-accounts, owner-initiated, owner-visible. If any of the three is
missing, refuse — the refusal is the feature.

## Owner-consent gates (enumerated)

1. Device codes: entered by the owner at the IdP's page, never by automation.
2. Consent-click capture: owner-initiated AND owner-visible AND own-accounts.
3. First per-client extension connect (tab-drag): an owner act.
4. First rail sign-in: an owner act.
5. `--owner-present` flag gates any polling/automation rung — without it,
   capture.py prints instructions and exits.

## Refresh (NOT capture — but adjacent)

Capture mints; refresh is provider-native (the owning CLI rewrites its own
store). Never hand-roll a refresh POST against an inferred endpoint — grok and
zcode refresh endpoints are research-marked INFERENCE, not observation. When a
grant expires, re-run the ladder; do not invent a refresh.
