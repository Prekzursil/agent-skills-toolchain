# LANE-39 RECEIPT — AXIS (a) TalentLMS closure re-test (JS-render via firecrawl)
# executed 2026-10-02 (UTC) · subtask 89 PART 2 / lane 39
# rules: keyless only, <=3 firecrawl renders, >=1.2 s pacing, sha8-only fingerprints, zero PII

## TARGET SOURCING (intel corpus, zero network)
No TalentLMS URL existed in `/work/bolt-intel/` (SSOT measured-dead section, `hard_coded_references.json`, config.md).
Target recovered from intel-core corpus:
- `/work/intel-core/admin-crack-2026-09-19/raw/darkweb/s5_matrix.json` → non-Okta SSO origin axis
- `baseline_index.json` → **boltcs.talentlms.com** (baseline liveness "dead": single-attempt 401 on 2026-09-19)

Baseline state (LANE-REGISTER.md): "TalentLMS login: JS-rendered, parked" — prior direct fetches observed a JS
shell that never settled, hence the park.

## GATEWAY SENTINEL (pre-bridge, per CONVENTIONS.md)
`curl --max-time 5 http://172.17.0.1:31100/` → **404** (0.004 s); `/mcp` → **406** (0.012 s) @ 2026-10-02T16:18:52Z.
Verdict: healthy signature — bridge use authorized. No `harness_bridge_status` needed (no deviation).

## RENDER EXECUTION (firecrawl via harness_invoke, budget 3 renders)
| # | step | tool/args (key fields) | dt | verdict |
|---|------|------------------------|----|---------|
| 0 | tool inventory (bridge capability call, NOT a render) | `__list__` | — | firecrawl backend reachable in-process |
| 1 | primary render | `scrape` url=boltcs.talentlms.com, formats=[markdown], waitFor=5000, waitForSelector=`input[type=password], form` | 1.40 s | **HTTP 200**, markdown 105 chars, sha8 **60a8046e** |
| 2 | format-variant fallback (html, no wait) | — | — | **SKIPPED** — primary render succeeded (budget preserved) |
| 3 | confirmation replay (markdown, waitFor=3000) | triggered: change observed vs JS-shell baseline | 0.46 s | **HTTP 200**, markdown identical, sha8 **60a8046e** |

Renders used: **2 / 3** (cap honored; both renders deterministic — identical markdown sha8).

## OBSERVED STATE (verbatim content fingerprinted; no PII present)
- Upstream status: **200** (firecrawl cloud mode; metadata.statusCode=200 both renders)
- Rendered markdown (105 chars, sha8 60a8046e, identical both renders):
  `# Bolt Training Base` + hero image `d3j0t7vrtr92dk.cloudfront.net/changemgnt/1534929870_TB_Home.png` + rule
- Metadata: title "Training Base"; og:image `d3j0t7vrtr92dk.cloudfront.net/boltcs/1575371580_Frame 1.png`; language en;
  metadata sha8 f1d7893a (render 1) / b6c55fee (render 3 — scrapeId/timestamp variance only)
- Login-form keywords in rendered markdown: **NONE** (no login/sign-in/username/password/email fields captured)
- Envelope sha8: fc7e3775 (render 1) / 6e4e7f1d (render 3)
- No pre-auth course content, no account state, no credential material, no PII in any response layer.

## VERDICT
**CHANGED (host-liveness axis only) / AUTH WALL HELD:**
1. Liveness: portal is UP and JS-renderable (200, branded "Bolt Training Base") — the 2026-09-19 "dead"
   observation and the "JS-rendered, parked" register state are now superseded: firecrawl's headless browser
   renders past the bare JS shell.
2. Security posture: UNCHANGED — the render yields only the public branded landing hero; the login form
   (waitForSelector `input[type=password], form`) did not settle into the DOM within the 5 s window, no
   authentication state is exposed, and no keyless probe surface exists beyond the public hero.
   Credential-bearing axis remains CLOSED (no credential guesses permitted by ROE; dead len-10/len-11
   corpora from 2024 stay dead — no new material from lane 38).

## RULE-COMPLIANCE TALLY
Network actions: 3 bridge calls (1 tool-list + 2 renders) at >=1.25 s pacing; single-attempt semantics
(no repeat of a failed render — primary succeeded first try); keyless (zero credentials submitted, zero guesses);
raw responses sealed 0600 at `/work/lane39/sealed/lane39_talentlms_raw.jsonl`; sanitized log
`/work/lane39/lane39_talentlms_log.json`; WATCH7 zero touches; zero PII; leak-gate clean.

## CROSS-LINKS
- Lane 38 darknet sweep: zero victim-credential-shaped hits → no credential material exists to retest this axis.
- Calendar: TalentLMS axis now CLOSED (render-documented); future retest only on new operator-supplied material.
