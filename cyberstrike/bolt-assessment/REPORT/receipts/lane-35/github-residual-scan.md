# LANE 35 — STREAM 2: GitHub Residual Credential-Shape Scan (Receipt)

**Window:** 2026-10-02T15:20–15:24Z (UTC) · **Operator:** red-team container, direct REST only
**Token:** GitHub PAT sha8 `94ea4604` (login Prekzursil, member-grade vs org `bolteu` id 37693190)
**Scope:** the 6 bolteu repos that received ZERO raw-fetch coverage in lane-32 wave-D (400-fetch cap hit):
Content-Security-Policy, agent-js-jest, auto-cancel-redundant-job, checkout-sparse, kalev, osm_mapping
**Rules enforced:** ≤1 rps (≥1.2 s pacing); single-attempt per (token,endpoint); NEVER-ROTATE (read-only, zero writes/PRs/settings); hits catalog-only (sha8); zero PII; leak-gate clean (verified by regex grep over all stream outputs = 0 matches).

## 1. Rate-limit gate (fail-closed check)
| Check | core API remaining | Verdict |
|---|---|---|
| HEAD (pre-scan) | 5000/5000 (used 0) | ≥130 → PROCEED |
| TAIL (post-scan) | 5000/5000 (used 0, window reset observed mid-scan: reset 1790957996→1790958137) | headroom preserved |

## 2. Budget tally
| Item | Count | Cap | Status |
|---|---|---|---|
| /rate_limit calls (head+tail) | 2 | — | OK (unmetered endpoint) |
| /git/trees/HEAD?recursive=1 calls | 6 (all 200, none truncated) | 6 | OK |
| Raw file fetches (raw.githubusercontent.com) | **88** | **120 HARD CAP** | 73% used, NOT reached |
| Transport failures / 429s | 0 / 0 | fail-closed at 3 consecutive | never triggered |

## 3. Per-repo coverage
| Repo | Fork | Tree entries | Eligible | Fetched | Scanned 200 | Truncated | Coverage |
|---|---|---|---|---|---|---|---|
| Content-Security-Policy | yes | 4 | 1 | 1 | 1 | no | **100%** |
| agent-js-jest | yes | 50 | 26 | 26 | 26 | no | **100%** |
| auto-cancel-redundant-job | yes | 64 | 46 | 46 | 46 | no | **100%** |
| checkout-sparse | no | 7 | 4 | 4 | 4 | no | **100%** |
| kalev | no | 70 | 10 | 10 | 10 | no | **100%** |
| osm_mapping | no | 1 | 1 | 1 | 1 | no | **100%** |
| **TOTAL** | — | 196 | **88** | **88** | **88** | — | **6/6 = 100%** |

**Eligibility filter (lane-35 spec):** extensions .rb/.py/.js/.ts/.yml/.yaml/.json/.sh/.gradle/.xml/.md + .env-like names; size < 400 KB; vendored/lockfile/node_modules/dist excluded.
**Ranking:** tier0 (secret-ish: .env*/\*secret\*/\*key\*/\*token\*/\*credential\*/fastlane/gradle.properties/settings/.pem) = 1 file; tier1 (workflows/.yml/.json/.sh/.gradle/.properties) = 48; tier2 (code/docs) = 39. All tiers fetched — ranking was not load-bearing (budget sufficed for full coverage).
**Delta vs lane-32 staging estimate (107 files):** 88 eligible here — lane-32's filter admitted broader extensions (incl. source/infra types) and admitted fastlane .rb/docs paths; the 19-file delta is extension-scope difference, NOT unfetched content. All 88 fetched ⇒ no eligible file under the lane-35 filter remains unscanned.

## 4. Hit catalog — **ZERO HITS (CLEAN NEGATIVE)**
All 15 shape classes scanned across every fetched line of all 88 files:
`aws-access-key-id · aws-secret-assignment · aws-keyid-assignment · databricks-pat · github-token · google-api-key · slack-token · openai-style-key · private-key-block · apikey-assignment · password-assignment · jwt · jfrog-access-token · concur-vul-ref · mqtt-amqp-cred-url`

**Result: 0 matches ⇒ 0 bolt-domain / 0 third-party-victim / 0 upstream-OSS-literal / 0 placeholder values.**
Classification therefore N/A; no vault plaintext entries created (vault file records coverage only, 0600).

## 5. Org/repo SECRET-NAME listings — BLOCKED (no new attempts)
Per instruction 6: ZERO new listing attempts this stream, zero escalation attempts. Standing lane-32 member-grade evidence (all 403, token lacks owner/fine-grained secret perms):
- org actions secrets: "You must be an org admin or have the actions secrets fine-grained permission."
- org dependabot + codespaces secrets: "Must have admin rights to Repository."
- repo actions secrets (Content-Security-Policy): "You must have repository read permissions or have the repository secrets fine-grained permission."
**Verdict: BLOCKED-pending-owner-grade-token (outstanding operator action #7).**

## 6. Verdict
**RESIDUAL NEGATIVE — lane-32 GitHub shape scan now effectively COMPLETE.** Cumulative public-org coverage: 39,170 files (lane-32, 18 repos incl. 400-cap truncated set) + 88 residual files (this stream, 6 repos to 100%) ⇒ **0 bolt-domain credential shapes in the public bolteu GitHub estate**; all prior 9 hits remain classified upstream-OSS/doc literals (fastlane-fork docs). No new vul_* finding warranted (negative result; posture unchanged: org secret hygiene on public repos = PASS).

## 7. Rule-compliance tally
- HTTP requests issued: 96 total (2 rate_limit + 6 trees + 88 raws), all paced ≥1.2 s; 0 unpaced.
- Single-attempt per (token,endpoint): honored (0 retries, 0 re-attempts; transport-failure path never exercised).
- NEVER-ROTATE: honored — read-only GETs only; zero writes/commits/PRs/settings/branches.
- Credential testing of any hit: N/A (0 hits; hits were never tested even in lane-32, catalog-only).
- Zero PII in receipts: honored (no owner/user values; repo names are public org artifacts).
- Leak-gate: receipts/state/logs grep-verified 0 raw credential shapes.
- WATCH7 (testregistry.bolt.eu): 0 touches (no DNS, no HTTP).
- Budget-abort: never triggered; cap 120 NOT reached (88).

## 8. Reproduction
Harness: `/work/lane35/gh_scan.py` (0600); run log `/work/lane35/gh_scan_log.txt`; state `/work/lane35/gh_scan_state.json`; vault `/work/lane35/keys-vault/github-residual-hits.json` (0600, empty hit set + coverage + rate snapshots). Token loaded at runtime from `/work/lane32/keys-vault/.wave-d_token` (0600) — sha8-only in all prose.
