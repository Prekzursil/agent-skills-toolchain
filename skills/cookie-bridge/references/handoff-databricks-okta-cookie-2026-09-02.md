# Handoff: Databricks cookie-bridge vs Okta wall

**Date:** 2026-09-02  
**Status:** disk-verified investigation (read-only; no inject, no extract, no browser CDP probe)  
**Question:** Can bolt-datascience / bolt-common / bolt-geo skip the Okta wall the same way as 2026-07-23 (cookie-bridge DBAUTH + `bolt.okta.com` `idx` already injected into Chrome and Edge), or must DBAUTH (said expired 2026-07-28) and Okta `idx` (said exp ~2026-09-01) be re-extracted before another safe Edge inject?

**Verdict:** Re-extract before another safe Edge inject. The 2026-07-23 skip is not a live 2026-09-02 path.

No cookie values, PATs, or vault plaintext are in this file.

---

## Direct answer

| Path | Usable 2026-09-02? |
|---|---|
| Reuse 2026-07-23 DBAUTH to skip Okta | **No** — recorded expiry 2026-07-28 22:51; that is what the 2026-07-23 probe used |
| Reuse store JSON for another Edge inject | **No** — `databricks_cookies.json` missing; injector hard-exits |
| Rely on leftover Edge `idx` for silent SSO | **Unproven** — no live probe; addendum called `idx` a session cookie with no expiry |
| Phone re-extract, then `safe_main_cookie_inject.py` | **Required** before claiming another safe inject |

The “~2026-09-01” `idx` expiry is **not** in inspected sources.

---

## 1. Extract (2026-07-23)

Two independent 2026-07-24 documents read the same store.

From `C:\Users\Prekzursil\Cowork\output\claim-verification-handoff_2026-07-24.md` (claim-2):

- `extracted_at=2026-07-23T20:05:38.060844+00:00`
- `cookie_count=30`
- `bolt-common.cloud.databricks.com:DBAUTH`
- `bolt-datascience.cloud.databricks.com:DBAUTH`
- `bolt-geo.cloud.databricks.com:DBAUTH`
- `bolt.okta.com:JSESSIONID`
- `bolt.okta.com:idx`

Same `extracted_at` / count / three DBAUTH + Okta `idx` in `C:\Users\Prekzursil\Cowork\output\session-health-chatgpt-dbx-aws_2026-07-24.md` §3.

Workspace hosts from `RUNBOOK-cookie-bridge-databricks-2026-07-24.md` §3:

| Profile | Host |
|---|---|
| bolt-datascience | `https://bolt-datascience.cloud.databricks.com` |
| bolt-common | `https://bolt-common.cloud.databricks.com` |
| bolt-geo | `https://bolt-geo.cloud.databricks.com` |

SSO: `bolt.okta.com`. Runbook artifact table: `databricks_cookies.json` = phone CDP extract 2026-07-23, 30 cookies, DBAUTH × 3 + Okta `idx`.

---

## 2. Inject (2026-07-23) — what “skip Okta wall” meant

Runbook §4.D:

- Databricks-only payload into **main Chrome and Edge** (ChatGPT skipped).
- Chrome: 30/30 set, probe `looksApp=true` on **datascience**, integrity OK.
- Edge: same.
- Named reports: `safe_main_inject_report_20260723T203206Z.json` (Chrome), `…T203225Z.json` (Edge). Those JSON files are **not on disk now**.

Addendum §4 (receipts re-read with real schema):

- both browsers `set_ok:30 set_fail:0`
- `looksLogin:False looksApp:True`
- `integrity_ok:True`

Claim-verification table also lists later Chrome apply `safe_main_inject_report_20260724T002700Z.json`: `WEB_LIKELY_OK`, `probe_dbx_ok=true`, `set_ok=30`.

Injector probe (`safe_main_cookie_inject.py`): navigates **only** `https://bolt-datascience.cloud.databricks.com/` and sets `looksLogin` from `/sign in|log in|okta|authenticate/`. bolt-common and bolt-geo were **not** separately probed.

So 2026-07-23 “no Okta wall” = **DBAUTH still in lifetime, datascience only**.

---

## 3. Expiry — DBAUTH vs idx

Addendum §5 (only source for the clock; original JSON gone → **medium** on the timestamp):

> Cookie store: 30 cookies, extracted 2026-07-23T20:05:38Z.  
> `DBAUTH` ×3 expire **2026-07-28 22:51** → **~4.9 days** of runway.  
> `bolt.okta.com:idx` (session cookie, **no expiry**).

Today is **2026-09-02**. Recorded DBAUTH lifetime ended **2026-07-28**.

The question’s `idx` expiry ~2026-09-01 is **not in any inspected file**.

`cookie_to_cdp` in `safe_main_cookie_inject.py`: if `expires` is missing or `<= 0`, sets `time.time() + 30 * 24 * 3600`. A session `idx` injected on 2026-07-23 would have gotten a **synthetic ~30-day** expiry (~2026-08-22), not 2026-09-01.

Okta Identity Engine uses `idx` instead of Classic `sid`; lifetime is org Global Session Policy, not a fixed date.  
https://developer.okta.com/docs/guides/oie-upgrade-sessions-api/main/

---

## 4. New inject cannot use the old store (two probes)

`safe_main_cookie_inject.py`:

- `DATABRICKS_FILE = ~/.crcp/cookie-bridge/databricks_cookies.json`
- `load_payload`: if kind is `databricks` or `both` and file missing → `SystemExit(f"missing {DATABRICKS_FILE}")`

Probe A (2026-09-02): direct read of `C:\Users\Prekzursil\.crcp\cookie-bridge\databricks_cookies.json` → does not exist.  
Probe B (2026-09-02): listing of `C:\Users\Prekzursil\.crcp\cookie-bridge\` → only `session_options.json` and `session_options.md`.

Also missing on read: inject reports `T203206Z` / `T203225Z`, `RESTORE_FROM_JUL20_21.md`.  
Repo cookie-store `C:\Users\Prekzursil\_v_m03apply\tools\crcp\cookie-store\` has only `README.md`.

---

## 5. Doctrine when DBAUTH dies

Runbook §4.E: “DBAUTH can expire; re-extract from phone if DBX drops to Okta login.”

`C:\Users\Prekzursil\_v_m03apply\tools\crcp\cookie-store\README.md`: stored cookies last days–weeks; when they lapse, re-run the bridge against the phone.

Safe sequence (runbook §6):

```powershell
adb devices
adb forward tcp:9223 localabstract:chrome_devtools_remote
python "$env:USERPROFILE\.crcp\cookie-bridge\databricks_cookie_bridge.py" extract
# quit Edge fully
python "$env:USERPROFILE\.crcp\cookie-bridge\safe_main_cookie_inject.py" --browser edge --payload databricks
```

Do **not** use `inject_all_main_profiles.py` (gated; 2026-07-20 corruption vector).

---

## 6. Later refresh did not land (secondary)

`C:\Users\Prekzursil\Cowork\output\session-analysis-30bd50d4_2026-08-07\user_messages.md` quotes 2026-08-06 okta-relay:

- `phone_extract` failed: `Phone not connected as ADB device.`
- validator still saw `databricks_cookies.json` `{count: 32, DBAUTH: true, idx: false}`

That later store is not on disk now. Original log file was not inspected.

---

## Uncertainties

- No live 2026-09-02 CDP/HTTP probe of main Edge or Chrome Databricks/Okta.
- Question’s `idx` expiry ~2026-09-01 unsupported; addendum said session cookie, no expiry.
- Silent Okta SSO minting new DBAUTH from leftover `idx` after DBAUTH expiry was not tested.
- bolt-common / bolt-geo never separately probed.
- Original inject-report JSON and `databricks_cookies.json` are gone; 2026-07-24 copies of their fields were used.
- 2026-08-06 quoted validator is secondary only.

---

## Inspected paths

- `C:\Users\Prekzursil\.agents\skills\cookie-bridge\references\RUNBOOK-cookie-bridge-databricks-2026-07-24.md`
- `C:\Users\Prekzursil\.agents\skills\cookie-bridge\references\RUNBOOK-cookie-bridge-databricks-2026-07-24-ADDENDUM.md`
- `C:\Users\Prekzursil\.agents\skills\cookie-bridge\safe_main_cookie_inject.py`
- `C:\Users\Prekzursil\.agents\skills\cookie-bridge\databricks_cookie_bridge.py`
- `C:\Users\Prekzursil\Cowork\output\claim-verification-handoff_2026-07-24.md`
- `C:\Users\Prekzursil\Cowork\output\session-health-chatgpt-dbx-aws_2026-07-24.md`
- `C:\Users\Prekzursil\Cowork\output\session-health-chatgpt-dbx-aws_2026-07-24.json`
- `C:\Users\Prekzursil\_v_m03apply\tools\crcp\cookie-store\README.md`
- `C:\Users\Prekzursil\.crcp\cookie-bridge\` (listing + missing `databricks_cookies.json`)
- https://developer.okta.com/docs/guides/oie-upgrade-sessions-api/main/
