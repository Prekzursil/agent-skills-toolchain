---
title: aws_phone_cookie_inventory_2026-07-24
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/aws-phone-cookie-inventory-2026-07-24
---

# AWS phone cookie inventory + vault (2026-07-24)

**No secrets in this file.** Cookie values stay on-disk outside git under ACL-locked paths and DPAPI vault containers.

## What was done

Same path as ChatGPT / Databricks phone bridges:

1. Phone Chrome CDP via ADB USB (`R5CX11Z7RXR` / SM-S928B)
2. Extract cookies for AWS access portal + Bolt Okta SSO
3. Save store + metadata status
4. DPAPI vault + INDEX append + vault manifest update

## Tooling

| Item | Path / command |
|------|----------------|
| Bridge script | `~/.crcp/cookie-bridge/aws_cookie_bridge.py` |
| Secret store | `~/.crcp/cookie-bridge/aws_cookies.json` |
| Status (no values) | `~/.crcp/cookie-bridge/aws_cookies_status.json` |
| DPAPI vault | `~/.crcp/secret-vault/aws-cookies.dpapi` |
| Vault INDEX | `~/.crcp/secret-vault/INDEX.md` (AWS section) |

```powershell
# Re-extract from phone (Chrome open on AWS portal)
python "$env:USERPROFILE\.crcp\cookie-bridge\aws_cookie_bridge.py" extract

# Metadata-only status
python "$env:USERPROFILE\.crcp\cookie-bridge\aws_cookie_bridge.py" status

# DPAPI vault + INDEX refresh
python "$env:USERPROFILE\.crcp\cookie-bridge\aws_cookie_bridge.py" vault

# One-shot
python "$env:USERPROFILE\.crcp\cookie-bridge\aws_cookie_bridge.py" sync
```

## Access portal (names only)

| Field | Value |
|-------|--------|
| Instance / host | `d-996771582c.awsapps.com` |
| URL | `https://d-996771582c.awsapps.com/start/` |
| Kind | AWS IAM Identity Center access portal |
| SSO IdP | `bolt.okta.com` (authenticated tab open on phone) |

## Extract result (2026-07-24)

| Metric | Result |
|--------|--------|
| Device | ADB `device` (SM-S928B) |
| Phone Chrome | Chrome/150 CDP `chrome_devtools_remote` |
| Tabs used | AWS access portal + Okta UserHome |
| Cookies saved | **12** (deduped) |
| Portal cookies | **4** (`d-996771582c.awsapps.com`) |
| Okta cookies | **8** (`bolt.okta.com`) |
| Console cookies | **0** (no `console.aws.amazon.com` tab open at extract) |
| Health | **GOOD_PORTAL** |
| Vault | `aws-cookies.dpapi` — plaintext ~13.4 KB → cipher ~13.6 KB |
| Round-trip | **DECRYPT-OK** |

### Session-ish cookie names (no values)

- `d-996771582c.awsapps.com` → `x-amz-sso_authn`, `awsccc`, `awscccp`, `idc-access-portal-tab-preference`
- `bolt.okta.com` → `JSESSIONID`, `idx`, (+ other Okta session cookies)

Full name/domain/length table lives in `~/.crcp/secret-vault/INDEX.md` under **AWS cookies (phone extract)**.

## Auth plane (estate inventory addition)

### AWS web session (phone-origin)

| Item | Location |
|------|----------|
| Cookie store (SECRET) | `~/.crcp/cookie-bridge/aws_cookies.json` |
| Status (safe) | `~/.crcp/cookie-bridge/aws_cookies_status.json` |
| Extract source | Phone Chrome via ADB → CDP port 9223 |
| Key surfaces | IAM Identity Center portal (`*.awsapps.com`), Bolt Okta |
| Vault container | `~/.crcp/secret-vault/aws-cookies.dpapi` |
| Protection | DPAPI CurrentUser + ACL user-only |

**Do not commit** `aws_cookies.json`. Treat portal/SSO cookies as password-equivalent.

### Related planes (already documented)

| Plane | Store |
|-------|--------|
| ChatGPT web | `chatgpt_cookies.json` / `chatgpt-cookies.dpapi` |
| Databricks web | `databricks_cookies.json` |
| Databricks CLI PATs | `~/.databrickscfg` / `databricks-cfg.dpapi` |

## Limits / honest gaps

1. **No AWS Console account session cookies** were present — only the **access portal** + Okta. To get account console cookies, open an account from the portal on the phone, then re-run `extract`.
2. Some duplicate Okta/portal websockets timed out (phone CDP load); first successful portal + Okta tabs still yielded 12 cookies.
3. Bridge does **not** auto-inject into daily Chrome/Edge main profiles (same safety default as Databricks durable path). Inject can be added later if needed.
4. Values exist only in the JSON store + DPAPI container — never in this report, status JSON, or INDEX value columns.

## Re-extract when

- Portal login expires / “session expired” on `awsapps.com`
- Okta re-auth required
- After phone Chrome data clear
- Before any automation that needs a fresh SSO session

## Mirror of prior discipline

| Rule | Applied |
|------|---------|
| Don’t echo values | Status prints names/lengths/domains only |
| Save on disk + vault | `aws_cookies.json` + `aws-cookies.dpapi` |
| Document metadata | This report + vault INDEX section |
| Restrict ACLs | Store dir + cookie file + vault container |
| No git tracking of secrets | Report under `tools/crcp/reports/` is value-free only |