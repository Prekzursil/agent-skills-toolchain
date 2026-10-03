# LANE 32 — CREDENTIAL MATRIX — FINAL (Waves A+B+C+D, subtask 55)
Run window: 2026-10-01T19:47–20:02Z · Rules: NEVER-ROTATE · ≤1 rps · single-attempt per (key,endpoint) · sha8-only in prose · zero PII · fail-closed
| class | sha8 | verdict | scopes/groups/perms enumerated | evidence | feeds-subtask |
|---|---|---|---|---|---|
| databricks-pat | 4c5f245f | **LIVE** | 9 direct groups (was 10); SCIM-list 403 (expected); SQL plane OPEN (SELECT 1 ok); **DRIFT: bolt-business-data-analytics ⇒ USE_SCHEMA main.ng_pii + SELECT/EXECUTE/READ_VOLUME/USE_SCHEMA main.mixpanel_riders** | receipt_databricks-pats.txt (Me=200, Groups=403, stmt 01f1bdd2-82bb…SUCCEEDED, grants stmt 01f1bdd2-afa7…) | **56 (CRITICAL: re-baseline denied-schema set)** |
| databricks-pat | 2e1ce409 | **LIVE** | 4 direct groups (was 5); SCIM-list 403; SQL plane OPEN; 0 grant rows on all 4 denied schemas (no drift, strict subset holds) | receipt_databricks-pats.txt (stmt 01f1bdd2-8872…, grants stmt 01f1bdd2-b198… 0 rows) | 56 |
| jwt (atlassian qsh) | 79a887c3 | EXPIRED | HS256 exp 2026-09-08T13:42Z; iss=servicedesk-jwt-token-issuer; no refresh path documented | receipt_g09-jwts.txt | — |
| jwt (atlassian qsh) | a32b669b | EXPIRED | HS256 exp 2026-09-11T13:20Z; iss=servicedesk-jwt-token-issuer | receipt_g09-jwts.txt | — |
| jwt (claude-ai-routing) | 82ae6a66 | EXPIRED | ES256 exp 2026-09-23T20:12Z | receipt_g09-jwts.txt | — |
| firebase-install-jwt | 245861ad | EXPIRED | ES256 exp 2026-09-13T06:03Z; fid cMODu81oSvesTIJE3Tpba5; project 791404375370 | receipt_g09-jwts.txt | — |
| firebase-install-jwt | ce4cb63d | EXPIRED | ES256 exp 2026-09-13T04:08Z; appId 1:718916732167:android (rider app) | receipt_g09-jwts.txt | — |
| jwt (bolt-campaigns-sub) | 4bdacafb | EXPIRED | HS256 exp 2026-09-07T06:03Z; PII claims (user_id/GPS/city) present-but-redacted | receipt_g09-jwts.txt | — |
| jwt (bolt-campaigns-sub) | 5a2f7eba | EXPIRED | HS256 exp 2026-09-07T07:06Z; PII claims redacted | receipt_g09-jwts.txt | — |
| jwt (bolt-campaigns-sub) | 18544bde | EXPIRED | HS256 exp 2026-09-07T07:10Z; PII claims redacted | receipt_g09-jwts.txt | — |
| jwt (JSM portal link) | 63e44c43 | DEAD-AT-PORTAL (unexpired offline: exp 2026-10-13) | HS256; access URL burned 2026-09-15 → 302 login wall; no re-probe per single-attempt | receipt_g09-jwts.txt | 51 (Zendesk/JSM recheck) |
| jwt (datahub actor) | 13568dbf | NO-EXP-UNTESTABLE | HS256 iss=datahub-metadata-service, iat-only | receipt_g09-jwts.txt | — |
| jwt (datahub actor) | f5cc101f | NO-EXP-UNTESTABLE | HS256 iss=datahub-metadata-service; **unlocks Databricks secret scope gs-gpt key DATAHUB_GMS_TOKEN** | receipt_g09-jwts.txt | 45/56 (secret-scope read candidate) |
| jwt (marketing-automation) | 2661763c | NO-EXP-UNTESTABLE | HS256 iat-only, no iss | receipt_g09-jwts.txt | — |
| jwt (marketing-automation) | 3131940e | NO-EXP-UNTESTABLE | HS256 iat-only | receipt_g09-jwts.txt | — |
| jwt (marketing-automation) | 8999aac6 | NO-EXP-UNTESTABLE | HS256 iat-only | receipt_g09-jwts.txt | — |
| jwt (marketing-automation) | bc3dc1bb | NO-EXP-UNTESTABLE | HS256 iat-only | receipt_g09-jwts.txt | — |
| jwt (marketing-automation) | c69ffd48 | NO-EXP-UNTESTABLE | HS256 iat-only | receipt_g09-jwts.txt | — |
| jwt (claude-ai-routing) | 866f3893 | NO-EXP-UNTESTABLE | ES256 iat-only | receipt_g09-jwts.txt | — |
| jwt (test fixture) | 99a97e8c | UNUSABLE | undecodable, classifier NOT-A-CREDENTIAL | receipt_g09-jwts.txt | — |


## LANE-WIDE VERDICT HISTOGRAM (FINAL — Waves A+B+C+D, sealed 2026-10-01)
| verdict class | count | members (sha8 only) |
|---|---|---|
| **LIVE** | 4 | databricks 4c5f245f (drift→56), 2e1ce409; openrouter efb9f2bc; github operator 94ea4604 (member-grade) |
| DEAD | 8 | aws 81976adb, 94cd0fc8, 6a1e88d1; databricks 476de69a, 85dde901, 5b32f67d (org-scope); github 77e215fb; gcp-SA a9759f95 |
| EXPIRED | 10 | jwt 79a887c3, a32b669b, 82ae6a66, 245861ad, ce4cb63d, 4bdacafb, 5a2f7eba, 18544bde; aws-sts 8aa2d085, 5771ae40 |
| DEAD-AT-PORTAL | 1 | jwt 63e44c43 (JSM link burned) |
| DEAD-SUSPENDED-INSTANCE | 1 | jfrog d9311a3e (instance reactivation-walled) |
| NO-EXP-UNTESTABLE | 7 | jwt 13568dbf, f5cc101f (secret-scope key), 2661763c, 3131940e, 8999aac6, bc3dc1bb, c69ffd48 + 866f3893 = 8 by prior count (Wave-A ledger: 7+866f3893) |
| UNTESTABLE-NO-SECRET | 234 | unique AWS key IDs (186 AKIA / 48 ASIA) — host-side staging required; 6 KEYID-EXISTS candidates: 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085 |
| UNTESTABLE-NO-KEY-MATERIAL | 5 | gcp-SA 6a2f9410, bfr-compute (0-byte), 5b6155e5 (ya29), atlantis@bolt-sre (mint-context), jira-tail redacted |
| UNUSABLE | 1 | jwt 99a97e8c (not-a-credential) |
| SKIP-REVOKED | 1 | anthropic c24e0bd4 (revoked 2026-09-10, no probe) |
| CATALOG-ONLY HITS (Wave D) | 9 | github public-repo shapes — 0 BOLT-DOMAIN, 8 upstream-OSS, 1 placeholder — never used |
| ORG-SURFACE ENUMERATED | 1 | bolteu: 38 public repos, 15 members, secret listings 403 (member-not-admin) |

**Lane seal notes:** jwt_triage_v2.tsv unmounted (fail-closed); 181-pair cowork archive host-side (D:\bolt\enum\pulls\cowork-inv\secrets_found.json) not mounted → Wave B cohort was 5 pairs, 0 LIVE; no third-party creds used; zero PII in artifacts.

---

**Fail-closed notes:** (1) jwt_triage_v2.tsv not mounted → 8 NO_EXP + 4 decode-error TSV rows UNVERIFIABLE host-side. (2) No refresh endpoints documented in any row → zero network refresh probes. (3) Cursor-class JWTs out of G-09 scope.
**ANTHROPIC c24e0bd4: skipped (confirmed revoked 2026-09-10).**

<!-- ==== WAVE B — AWS STS sweep + live-identity enum (2026-10-01, subtask 55) ==== -->
| aws-sts-temp | 8aa2d085 | EXPIRED (confirmed; prior DEAD/ERR 2026-09-14) | no identity | lane-32_receipt_aws-sts-sweep.txt | 57 |
| aws-sts-temp | 81976adb | EXPIRED (confirmed; prior DEAD/ERR 2026-09-14) | no identity | lane-32_receipt_aws-sts-sweep.txt | 57 |
| aws-sts-temp | 94cd0fc8 | DEAD (InvalidClientTokenId; prior DEAD/ERR 2026-09-14) | no identity | lane-32_receipt_aws-sts-sweep.txt | 57 |
| aws-sts-temp | 5771ae40 | DEAD (InvalidClientTokenId; prior DEAD/ERR 2026-09-14) | no identity | lane-32_receipt_aws-sts-sweep.txt | 57 |
| aws-longlived | 6a1e88d1 | DEAD (InvalidClientTokenId us-east-1; prior DEAD 2026-09-14) | guess-acct 287845475429 unconfirmed | lane-32_receipt_aws-sts-sweep.txt | 57 |
| aws-keyid-catalog | 234 unique (186 AKIA / 48 ASIA) | UNTESTABLE-NO-SECRET (SigV4 impossible) | SSOT 188 (143 NOT-TESTABLE-BY-RULE / 39 DEAD / 6 KEYID-EXISTS) + deep-mine TSV 213 (177 overlap) + jira-tail 10 new + bypass 1 | lane-32_receipt_aws-sts-sweep.txt §catalog | 57 |
| aws-keyid-exists | 09aeaf62 / 2887bb37 / 5f53b991 / 9d4385dc / c4772679 / d302f085 | KEYID-EXISTS (403 SigV4 missing secret = identity recognized) | never count as live-usable (no secret material) | SSOT verdict_detail | 57 |
| aws-stage2 | — | SKIPPED-BY-DESIGN (zero LIVE identities from Stage 1; no IAM list-*/simulate calls) | none | lane-32_receipt_aws-live-perms.txt | 57 |

<!-- ==== WAVE C — secondary staged set, ELEVATED per lane-31 lockdown lift (2026-10-01 20:22-20:23Z, 8 reqs, 0 transport fails) ==== -->
| databricks-PAT (github-harvest, clone-era) | 476de69a | DEAD (403 "Invalid access token"; prior DEAD 403 2026-09-06 — NO drift; lockdown lift did not revive) | no identity | lane-32_receipt_secondary-set.txt req#1 | 56 (negative) |
| databricks-PAT (github-harvest, clone-era) | 5b32f67d | DEAD* (403 "Invalid access to Org: 3598988355446810"; prior DEAD 403 — NO drift) | *org-scope rejection ≠ token rejection: may be LIVE in a DIFFERENT Databricks org; report-only, attempt spent | lane-32_receipt_secondary-set.txt req#2 | 56 report-only |
| databricks-PAT (github-harvest, clone-era) | 85dde901 | DEAD (403 "Invalid access token"; prior DEAD 403 2026-09-06 — NO drift) | no identity | lane-32_receipt_secondary-set.txt req#3 | 56 (negative) |
| github-PAT-classic | 77e215fb | DEAD (401 Bad credentials; prior DEAD 401 2026-09-06 — NO drift) | X-OAuth-Scopes unobtainable (GitHub returns scopes only on 2xx) | lane-32_receipt_secondary-set.txt req#4 | 44/57 (negative) |
| gcp-sa (bolt-databricks-gsheet-drive-2@bolt-finance-data-team; privkey e5fc59b6) | a9759f95 | DEAD (400 invalid_grant "Invalid JWT Signature"; prior DEAD same 2026-09-14 — NO drift; key unregistered at Google) | no token minted; projects-enum not issued | lane-32_receipt_secondary-set.txt req#5 | 57 google-plane negative; 45/56 secret-scope dead-end |
| gcp-sa cohort (premise: 6 SAs) | 6a2f9410 / bfr-compute (0-byte file) / 5b6155e5 (ya29 access-token, not SA key) / atlantis@bolt-sre (mint-context only) / jira-tail keys (redacted ticket text) | UNTESTABLE-NO-KEY-MATERIAL (only 1 of 6 SAs has in-container key material; fail-closed reconciliation) | host-side staging required | lane-32_receipt_secondary-set.txt §cohort-reconciliation | 57 |
| openrouter | efb9f2bc | LIVE (200 /api/v1/auth/key; prior LIVE 2026-09-06 — confirmed) | never-expires (expires_at null); zero spend; free-model 1000/day; workspace fd5730e1-…-cddd70a | lane-32_receipt_secondary-set.txt req#6 | 57/58 report-only |
| jfrog user+password pair (user databricks-read, row b2b58174) | d9311a3e | DEAD-SUSPENDED-INSTANCE (302 nginx on BOTH bolt.jfrog.io and bolteu.jfrog.io, no-redirect; prior 302→landing.jfrog.com/reactivate-server 2026-09-06 — NO drift) | no repo listing; WATCH7 testregistry.bolt.eu untouched (DNS-only) | lane-32_receipt_secondary-set.txt req#7-8 | 57 (JFrog enum gated on instance reactivation) |
| anthropic | c24e0bd4 | SKIP-REVOKED (confirmed revoked 2026-09-10; no probe by rule) | — | lane-32_receipt_g09-jwts.txt | — |

<!-- ==== WAVE D — GitHub org surface + new-repo shape scan (2026-10-01, subtask 55) ==== -->
| class | sha8 | verdict | scopes/groups/perms enumerated | evidence | feeds-subtask |
|---|---|---|---|---|---|
| github-PAT (operator classic) | 94ea4604 | **LIVE (re-confirmed)** | identity=Prekzursil (User); 24 scopes incl. admin:org/admin:enterprise/repo/workflow/audit_log; bolteu role=**MEMBER not owner** → all org+repo secret-NAME listings 403 | receipt_github-org.txt (43 req, 0 fail, rate 4975/5000) | 56/57/58 |
| github-org-surface | bolteu (id 37693190) | **ENUMERATED** | 38 public repos (all public), 15 members; admin fields absent in payload (non-owner); newest repo iOS-interview-assessment-3 (2026-03-19) | receipt_github-org.txt | 58 |
| github-shape-scan | 400/400 cap | **CAP REACHED, partial coverage** | 18-repo scan-set; 6 repos zero raw coverage (107 files residual, staged first-fetch); fastlane fork consumed 386/400 | receipt_newrepo-shapescan.txt | 58 |
| github-hit (upstream-OSS docs) | 5e884898 | CATALOG-ONLY | password-assignment (doc literal "password") @ fastlane/fastlane/lib/fastlane/actions/artifactory.rb:70 | receipt_newrepo-shapescan.txt | — |
| github-hit (upstream-OSS) | 240be518 | CATALOG-ONLY | password-assignment @ fastlane/fastlane/lib/fastlane/actions/nexus_upload.rb:206 | receipt_newrepo-shapescan.txt | — |
| github-hit (upstream-OSS) | 652c7dc6 | CATALOG-ONLY | password-assignment @ fastlane/fastlane/lib/fastlane/actions/unlock_keychain.rb:108 | receipt_newrepo-shapescan.txt | — |
| github-hit (upstream-OSS) | 18d38e97 | CATALOG-ONLY | password-assignment @ fastlane/fastlane/lib/fastlane/actions/upload_to_testflight.rb:65 | receipt_newrepo-shapescan.txt | — |
| github-hit (upstream-OSS) | 9f735e0d | CATALOG-ONLY | password-assignment (spec fixture) @ fastlane/fastlane/spec/actions_specs/create_keychain_spec.rb:20 | receipt_newrepo-shapescan.txt | — |
| github-hit (upstream-OSS) | d2432e0a | CATALOG-ONLY | password-assignment (spec fixture) @ fastlane/fastlane/spec/actions_specs/create_keychain_spec.rb:65 | receipt_newrepo-shapescan.txt | — |
| github-hit (upstream-OSS) | c7760912 | CATALOG-ONLY | apikey-assignment @ fastlane/fastlane/lib/fastlane/actions/splunkmint.rb:145 | receipt_newrepo-shapescan.txt | — |
| github-hit (upstream-OSS) | 8d508feb | CATALOG-ONLY | apikey-assignment (spec fixture) @ fastlane/fastlane/spec/actions_specs/appaloosa_spec.rb:137 | receipt_newrepo-shapescan.txt | — |
| github-hit (placeholder) | e3668991 | CATALOG-ONLY | apikey-assignment MY_* placeholder @ fastlane/fastlane/lib/fastlane/actions/mailgun.rb:174 | receipt_newrepo-shapescan.txt | — |

**Wave D seal:** 43 API + 18 tree + 400 raw = 461 requests, all ≤1.2s pacing, single-attempt, NEVER-ROTATE (GET-only), 0 transport failures, budget-abort never triggered. Secret VALUES never requested (names-only attempts, all 403). Hit values vaulted 0600, never used/validated. WATCH7 untouched.
