# CSRF-Token Cluster Analysis — cookies.tsv (HS project)

**Date:** 03.09.2026 (analysis date; data window 2017-11 -> 2026-08)
**Analyst:** offline vault analysis, `D:\bolt`
**Inputs:** `deep-mine\cookies.tsv` (v1, 264 data rows — AUTHORITATIVE for this cluster; `deep-mine2\cookies.tsv` is EMPTY, 0 rows, a v2 data-quality gap), `jira\comments\b*.json` (190 chunk files), `jira\issues\i*.json`, `jira\descr_full\` (0 hits)
**Rule compliance:** no network; `scripts\dbx_*.ps1` never opened; token values in this report are masked to first-8-chars + length.

---

## 1. Executive summary

The 2026 csrftoken cluster is a **systematic, ongoing, multi-user leak of live per-session Box anti-CSRF tokens** into the HS (Hiring Support) Jira project, caused by an HR document workflow habit: specialists draft employment documents in **Box's Google Docs editor integration** and paste the resulting editor URL — which embeds a session-bound `csrfToken` — into Jira comments as "smart-links" for cross-check/review. **84 distinct token values** (81 in the 2026 window) from **9 distinct human authors** across **80+ HR tickets**, spanning **2025-01-17 -> 2026-08-26** (still active at export). These are NOT one person's template: nearly every paste carries a fresh token minted for that editor session. Severity: **MEDIUM** (not a standalone bearer credential, but live CSRF-defense tokens + direct file IDs for employment contracts/NDAs, persisted in Jira and proven to survive into data exports like this vault).

## 2. Cluster statistics (from cookies.tsv)

| Metric | Value |
|---|---|
| Total rows (data) | 264 |
| `csrfToken=` rows | 218 (all in `csrfToken` camelCase form, URL query param) |
| Rows in 2026 | 214 — **all 214 are csrfToken** |
| Rows in 2025 | 4 (HS-17404 x2 same token; LSS-47696, LSS-57506 one each) |
| Other cookie names | `_ga` 28, `sessionId` 15, `jsessionid`/`JSESSIONID` 3 — all pre-2025, benign analytics/session URLs in legal/marketing contexts |
| 2026 distinct issue keys | **80** (all `HS-*`) |
| Max rows per key | 6 (HS-36559 = one comment containing 3 different editor links) |
| Distinct token values | **84 total / 81 in 2026** |
| Token shape | all 64 lowercase hex chars, no shared prefix structure |

Year distribution: 2019:5, 2020:12, 2021:2, 2022:7, 2023:17, 2024:3, 2025:4, **2026:214**.

Row multiplicity: each editor URL contains the token twice (query string + `#?_gfid=docs_editor_frame&csrfToken=...` fragment), so one paste yields ~2 mined rows; tokens seen 4x = two matched captures of the same paste (comment + export duplication).

## 3. The responsible workflow and team

**Project HS = "Hiring Support"** — the People Ops / HR service desk. Issues are Workday-synced HR transactions: `Process New Hire - <name> - <country>`, `Maintain Job Details - <name> - <country>`, `Process Global Promotion`, `NDA for a quest (work shadow)`. Type column shows "Auto generated" (Workday-initiated, wd3.myworkday.com/bolt links in bodies) or "Service Request". Issue status mostly `Closed Complete`.

**The leaking habit:** when an HR document specialist finishes drafting a contract/NDA/JD/relocation agreement, they paste the Box Google-editor URL of the document into the ticket so a colleague can cross-check it. Verbatim examples (tokens masked):

- `Doc is prepped - [link|https://bolt.app.box.com/integrations/googledss/openGoogleEditor?fileId=2170270921657&trackingId=3&csrfToken=7e7132b9…[MASKED-len64]…|smart-link]` (HS-32305, Kristi Liina Vahl, 2026-03-19 — earliest 2026 case)
- `Box document for cross check: [https://bolt.app.box.com/integrations/googledss/openGoogleEditor?fileId=2295512691732&csrfToken=b53f2cf4…]` (HS-39675)
- `Please review the [document |https://bolt.app.box.com/integrations/googledss/openGoogleEditor?fileId=2427594899626&trackingId=3&csrfToken=dced16c9…[MASKED-len64]#]and WD. Thank you!` (HS-41939, 2026-08-26 — latest case)
- `DE contract: [https://bolt.app.box.com/integrations/googledss/openGoogleEditor?fileId=2191314824644&csrfToken=7bcaf10e…] DE Relo agreement: […fileId=2191346641424&csrfToken=eca13c7b…]` (HS-36559 — three links, three tokens, one comment)

No support tooling, beehive, dashboard, or curl is involved — this is purely **humans copy-pasting the browser address bar** of the Box Google Docs editor into Jira comments. `jira\descr_full\` has zero hits: 100% of pastes are comments.

**Pasting authors (by paste occurrences in the comments corpus, 139 total):**

| Occurrences | Author |
|---|---|
| 83 (~60%) | aikemaris.muursepp@bolt.eu (Aike-Maris Müürsepp) |
| 20 | marilin.allak@bolt.eu (Marilin Allak) |
| 14 | kristi.vahl@bolt.eu (Kristi Liina Vahl) |
| 8 | kristin.runnel@bolt.eu (Kristin Runnel) |
| 7 | alice.gorobets@bolt.eu (Alice Gorobets) |
| 2 each | kerilin.mand, kadri.kivimaa, ingrid.valgejarv |
| 1 each | cetlyn.ojamaa, joao.santana (the very first paste, HS-17404, 2025-01-17) |

9 distinct human authors — this is a **team-wide convention, not a single individual's mistake**. (The two 2025 LSS outliers, LSS-47696 / LSS-57506, fall outside the sampled comment chunks; treat them as isolated precursors of the same copy-paste habit in Legal Support.)

## 4. Same token or different tokens?

**Different — conclusively.** Evidence:

1. **84 distinct values** across 218 rows; 81 distinct in the 2026 window alone. If this were one person's reusable template, distinct-count would be ~1-5.
2. **Token -> issue cardinality is 1:1 everywhere except one case:** token `959045c6|64` appears in HS-32411 (2026-03-20T10:57) and HS-32956 (2026-03-20T13:53) — the same Kristi Vahl Box session re-pasting the same URL for the same fileId after the first Workday task was cancelled and recreated ("Task was cancelled and a new one made"). Same-day, ~3h apart, same fileId 2171173580779.
3. **HS-36559 carries 3 distinct tokens in a single comment** (7bcaf10e, eca13c7b, c4684a03 — one per document link, same timestamp), proving tokens are minted **per editor-open / per file session**, not per user account lifetime.
4. No two authors ever share a token value; no prefix/similarity structure across values (all random 64-hex).

**Interpretation:** each paste leaks a token freshly generated for that user's Box editor session for that file. Sample masked fingerprints (first 8 + length): `fc350d43|64`, `f800b942|64`, `e95e69ee|64`, `e13d3cff|64`, `b722e002|64`, `27e39569|64`, `7e7132b9|64`, `959045c6|64` (the shared one), `dced16c9|64`.

## 5. Blast radius / origin

- **Origin host:** `bolt.app.box.com` — Bolt's enterprise Box tenant (path `/integrations/googledss/openGoogleEditor`). 
- **Secondary hosts in the URLs:** `api.box.com/fsip/files/<fileId>` (direct file-service pointers, `isInboundFsipRequest=true`) and Google API-loader params (`jsh=…gapi.lb.en…rs=AHpOoo…`) from the embedded Google Docs editor frame.
- **What the token is:** an anti-CSRF token bound to the pasting user's authenticated Box session for the Google-editor integration endpoints. It is **not** a session cookie and not standalone bearer auth — abusing it classically requires riding the victim's session (CSRF). It cannot be confirmed offline whether these tokens expire (each observed only at its single paste timestamp); the per-open minting pattern (4.3) suggests short-lived rotation, which limits but does not eliminate the window.
- **What it unlocks if live:** state-changing actions in the Box Google Docs editor integration as the leaking user, against the referenced `fileId` — HR documents whose content is highly sensitive: employment contracts, NDAs, relocation agreements, JDs, with surrounding comments discussing salaries, equity, seniority, citizenship/naturalisation documents, SSNs (GDPR-special-category-adjacent PII).
- **Audience exposure:** every reader of the ticket (broad internal), plus — proven by this vault — **any downstream data export**: the tokens survived a Jira dump into offline analysis files verbatim. 80+ tickets over 18 months, still occurring in the final week of the export window (2026-08-26).

## 6. Severity assessment (as evidence, not exploitation)

**MEDIUM** — systematically repeated exposure of live session-bound CSRF-defense tokens + direct Box file IDs for HR/legal documents into a widely-readable issue tracker, by an entire team as standard practice, persisting indefinitely and propagating into exports. Aggravators: volume (84 tokens), duration (18 months, ongoing), sensitivity of target documents (employee PII), 9 affected accounts. Mitigators: not standalone credentials; per-open rotation likely shortens validity; exposure audience is internal Jira readers. A combined finding (CSRF token + fileId + known target user) is what an insider or export-recipient would need for a targeted request-forgery attempt against the Box editor integration during the token's validity window — unverified offline, flagged for the report.

## 7. Remediation pointers

1. **Stop pasting editor-session URLs into Jira.** Share Box documents via canonical shared links or Box's own share flow, not the `googledss/openGoogleEditor` address-bar URL. The HS cross-check convention ("Doc prepped - [link|...]") is the root cause — update the team's workflow template/guide.
2. Ask Box admins whether `googledss` csrfTokens can be kept out of persistent URLs (fragment vs query), and confirm rotation/expiry policy; if tokens are long-lived, treat the 84 leaked values as candidate invalidations.
3. Scrub/redact the affected tickets (80 HS keys + HS-17404 + LSS-47696/57506) in any future Jira export; add `csrfToken=` to export redaction patterns (alongside existing cookie/secret regexes).
4. Awareness item for the 9 authors, prioritizing the top contributor (~60% of pastes) — behavior fix, not credential rotation.

## 8. Provenance

- All numbers recomputed live from `deep-mine\cookies.tsv` (264 rows verified), `jira\comments\*.json` (139 paste occurrences, 82 distinct issues, 9 authors), `jira\issues\*.json` (6 keys resolved), `jira\descr_full\` (0 hits verified).
- `deep-mine2\cookies.tsv` verified EMPTY (0 data rows) — v1 is the authoritative source for this cluster; v2 gap should be noted in the re-mine log.
- Full token values were never written to this report; masked fingerprints only (first 8 chars + length).

**disk-verified** — artifact re-read after write; all cited counts regenerable from the inputs above.
