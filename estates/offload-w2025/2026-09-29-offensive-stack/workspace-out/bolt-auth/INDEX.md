# D:\bolt — full extraction index (FINAL v5, corrections + tier2/delta layers, 2026-09-04)

> **Authorization (01.10.2026)**: FULL FORCE continuation — operator Andrei Visalon, "full force, no exclusions." All prior hard stops lifted. See AUTHORIZATION.md.

Supersedes v4 (2026-09-03). Corrections from the v5 edit pass (`analysis\INDEX-v5-DRAFT.md` — delivered as draft, not a separate edit list) re-verified against disk; tier2/delta layers added this pass. Provenance: disk-verified (footer).

**Everything on D:. Nothing on C.** ~2.9 GB · 693+ files (lower bound) · `manifest.sha256` = **682 nonblank lines, 0 hashes — OPEN DEFECT** (bare path list; v4's "682 SHA256 hashes" claim retracted; interim pin = `analysis\QUALITY-CERTIFICATE.md` §6 15-file SHA256 baseline)

## Corrections applied vs v4 (disk truth)
1. manifest hashless (above). 2. **Entities = 14,857** deduped pairs (`analysis\entities_v2.tsv`, 14,858 lines incl. header; 30,410 was pre-rebuild lineage). 3. **OpenAI sk- 15 → RETRACTED, 0 real keys** (filename/Slack fragments; SECRETS-LEDGER). 4. **atlassian_ids = 110,543 post-dedup rows / 5,535 distinct** (201,617 was pre-dedup console count). 5. **attribution v3: 5,535 IDs → 5,522 attributed (99.8%)** — BODY 3,461 / BODY-WEAK 1,815 / REPORTER 85 / REPORTER-WEAK 161 / UNATTRIBUTED 13. 6. **Vault quality grade B− (CONDITIONAL PASS)** (QUALITY-CERTIFICATE).

## GAP-REGISTER STATUS MATRIX (G-01..G-10)
| Gap | Status | Resolution |
|---|---|---|
| G-01 mojibake | **CLOSED (scoped) — col-13 OPEN** | 827,536 cells + 303,591 segments repaired; issue cols 2/3 clean; corpora EXACT post-mutation. Residual: issue col-13 owners blobs (~10^5 runs est., out of scope); `COL13-CONVERGENCE.md` absent |
| G-02 descr truncation | **IN PROGRESS ~68%** | `jira\descr_full\` **90 batches / 450,000 rows** of ≈665,750 target; cursor `last_issue_id: 2332858` (re-read); resumable |
| G-03 atlassian_ids shortfall | **RESOLVED** | Sort-Object -Unique collapsed 91,074 dup lines → 110,543 real / 5,535 distinct; `analysis\g03-resolution.md` |
| G-04 NULL descr | **DONE** | `null_descr_audit.tsv` full pass: 234,323 / 1,604,217 = **14.61%**; Task/Sub-task comment-silent |
| G-05 attribution coverage | **DONE (v3)** | 5,535/5,522 (99.8%), tier breakdown above; v1/v2 superseded |
| G-06 missed classes | **DONE (v1)** | cookies 264 + auth_headers 66 + `*_labeled.tsv` (pre-convergence caveat); v2 classes blocked on remine2 rerun |
| G-07 bearer slop | **DONE** | bearer = 1 placeholder + 1 expired ya29 — **0 real** |
| G-08 author cap/bots | **DONE (flagged)** | `agg-by-author-full.json` 14,731 authors + `-flagged.json` `is_bot`: **29 bots, 9.82% comment share** ("Automation for Jira" 152,863 = 8.6%) |
| G-09 JWT losses | **DONE** | `jwt_triage_v2.tsv` 1,144 rows / 1,067 unique (== `jwt.tsv`): **5 LIVE** (exp 08–16.09.2026) / 1,118 expired / 16 NO_EXP / 5 DECODE_ERROR |
| G-10 small slop | **DONE** | entities_v2 14,857; email backfill landed (24 email-less → 8 backfilled → 16 remain); v3 attribution header fixed |

## Integrity verdict (corpora EXACT claims stand)
| Corpus | Local rows | Server total | Match |
|---|---|---|---|
| Jira comments ALL-TIME | 1,784,448 distinct ids, 0 dups, 0 corrupt | 1,784,448 | **EXACT** |
| Jira issues ALL-TIME | 1,604,217 distinct ids, 0 dups, 0 corrupt | 1,604,217 | **EXACT** |
| Safety incidents ALL-TIME | 251,796 (71,582 numeric + 180,214 'S-') | 251,796 | **EXACT** |
| dim_admin_user staff directory | 34,821 (chunk-fetch re-pull after v1 truncated to 28,672) | 34,821 | **EXACT** |

Overall **grade B− (CONDITIONAL PASS)** (`analysis\QUALITY-CERTIFICATE.md`, 13:30 03.09): data core EXACT; conditions to A = hashless manifest, col-13 scoped-out mojibake, uncertified deep-mine2.

## Tier-2 pulls (`tier2\`, via `scripts\tier2_pull.ps1` — 6 configs)
| Config | Table | WHERE | State |
|---|---|---|---|
| employees | `core_models.dim_user` | `is_bolt_employee = true` | **COMPLETE — 4,555 rows** (`employees\true.json`, 50 cols incl. device tokens, last logins; state sentinel "true") |
| copilot | `ng_beehive.…copilot_conversation` | `1=1` | **COMPLETE — 5,442 rows** (5,000 + 442 exhausted; linkage-only — transcripts read-denied) |
| compensations | `customer_support_models.int_beehive_driver_compensations` | `action_created_ts_utc >= '2026-01-01'` | **STAGED — WHERE UNVERIFIED** (script column; no CSM sample in cloud clone; see `analysis/tier2-where-column-verify_2026-09-04.*`) |
| veritas | `customer_support_models.etl_beehive_veritas_verification` | `task_created_ts_utc >= '2026-08-01'` | **STAGED — WHERE UNVERIFIED** (script column; no CSM sample in cloud clone) |
| emaillog | `ng_beehive.email_support_processing_outgoing_email_log` | `created >= '2026-08-01'` | **STAGED — WHERE OK** (matches `tier2_pull.ps1`; sample-backed) |
| driverreg | `core_models.fact_driver_registration` | `driver_registration_created_ts >= '2026-08-15'` | **STAGED — WHERE OK** (sample-backed) |

Per-target scripts `scripts\tier2\ex_*.ps1` (7) + `validate_parse.ps1`; `tier2_sizing.ps1` / `tier2_schemas.ps1` for planning. Full `dim_user` pull still has no config.

## Delta-sync (`jira\delta\`, via `scripts\delta_monitor.ps1`)
**2,060 comments** (`d4411637.json`), created 2026-08-26T00:32 → **2026-08-26T23:43:02Z** (corpus watermark, now proven); keyset `last_comment_id: 4411637`, **drained** at pull time. Offline scanner `scripts\delta_scan.py` (jwt/aws/passwd/cookie/conn/token_link) ready; no hits doc on disk yet.

## DEEP-MINE v1 (`deep-mine\`, offline regex, deduped; pre-convergence caveat)
| Class | Hits | File |
|---|---|---|
| **JWTs** | **1,144 rows / 1,067 unique — 5 LIVE / 1,044 expired / 13 NO_EXP / 5 undecodable** | `jwt_triage_v2.tsv` |
| AWS key ids (AKIA/ASIA) | 500 (identifiers, not secret keys) | `aws_key.tsv` |
| password= KV | 529 (~148 real-looking, unvalidated) | `passwd_kv.tsv` |
| connection URLs w/ creds | 214 (TiDB infra map, ~172 masked) | `conn_url.tsv` |
| Basic-auth headers | 153 (150 prose slop) | `basic_auth.tsv` |
| Azure SAS signatures | 51 (v2 count anomaly open) | `sas_sig.tsv` |
| ~~OpenAI sk- 15~~ | **RETRACTED — 0 real keys** (filename/Slack fragments) | `openai.tsv` |
| Google API keys | 14 (unvalidated) | `google_api.tsv` |
| JDBC URLs | 21 | `jdbc.tsv` |
| Slack xox / hooks | 6 / 4 | `slack_xox.tsv`, `slack_hook.tsv` |
| secret KV / Bearer / PEM | 7–8 / 2 (0 real) / 2 | `secret_kv.tsv` etc. |
| Cookies | 264 (218 csrfToken rows → cluster doc) | `cookies.tsv` |
| Raw Authorization headers | 66 | `auth_headers.tsv` |
| **Entity directory** | **14,857 deduped pairs** (8 backfilled, 16 email-less) | `entities.tsv` + `entities_v2.tsv` |
| **Atlassian account IDs** | **110,543 post-dedup rows, 5,535 distinct** | `atlassian_ids.tsv` |

## deep-mine2 — **DEAD, authoritative rerun pending**
19 TSVs; **18 are 0-byte**, only `jwt.tsv` has content (~128 KB). No state file; no completion proof (`analysis\REMINE2-RECONCILIATION.md` absent). **v1 TSVs remain the only complete evidence base**; mid-run deltas in `analysis\remine2_reconciliation_data.json` are NOT quotable. Resumable: `scripts\repair\remine2.py` (+ `reconcile_v1_v2.py`).

## Jira corpus
| Set | Rows | Location |
|---|---|---|
| Comments, full bodies, complete history | 1,784,448 | `jira\comments\b*.json` (190 files) |
| Issues (summary, descr 600ch, owners, impact-EUR), complete history | 1,604,217 | `jira\issues\i*.json` (163 files, incl. NULL tail) |
| Untruncated descr re-pull (IN PROGRESS ~68%) | 450,000 @ 90 batches | `jira\descr_full\d*.json` |
| Delta comments (post-watermark round 1, drained) | 2,060 | `jira\delta\` |
| Aggregates: 483 projects · 14,731 authors (uncapped + bot-flagged) · 106 months | | `jira\agg-*.json` |

## analysis\ layer (key files)
`GAP-REGISTER.md` · `COMPLETENESS.md` (pull queue) · `USEFULNESS.md` · `QUALITY-CERTIFICATE.md` (grade B−) · `CSRF-TOKEN-CLUSTER.md` (Box googledss: **84 distinct live-per-session anti-CSRF tokens, 9 HR authors, 2025-01→2026-08 ongoing, MEDIUM**; employment-contract/NDA file-ids) · `SECRETS-LEDGER.md` (~2,991 evidence rows, 0 validated by use; OpenAI 15→0 retraction) · `PLAN-AND-AWS-STATE.md` (consolidated 29-item queue + AWS SSO envelope, 4 accounts/8 profiles) · `g03-resolution.md` · `null_descr_audit.tsv` · `entities_v2.tsv` · `attribution_v3.tsv` · `leak_timeline.tsv` (313 rows; v1-derived — trends quotable, per-month digits NOT) · `NEXT-QUEUE.md` · audit scripts/results 1–4.

## reports\ (4 files)
`security-assessment_v2.1_2026-09-03.md` = **current quotable** (entities 14,857 + OpenAI retraction fixed) · `ENGAGEMENT-CLOSE_2026-09-03.md` (misty-moon close: 2 live employee PATs, blast radius = bolt-common exactly, cross-workspace DENIED 4/4; owner decision block — PAT revocation, csrfToken/JWT purge; NEVER-ROTATE honored) · v1/v2 superseded (provenance).

## Negative results (doors verified closed)
`/sql/history/queries` → own-queries-only, text REDACTED · `/sql/alerts` → empty/403 · saved-query execute → needs `all-apis` scope · PII schemas, `system.*`, writes, token-mgmt, secrets, clusters, jobs, repos, DBFS, UC REST, Lakeview → DENIED · cross-workspace (datascience/geo, both PATs) → DENIED 4/4.

## Prior layers (unchanged)
Credential sweep (`sweep\`, superseded by re-mines: 400 JWT links capped-never-quote, 108 AKIA, 140 conn, 25 xox, 13 api-secret, 2 PEM) · table profiles (`schema\` 15 + `samples\` 55) · 240 saved queries w/ owners (`saved-queries-all.json`; 100-row `saved-queries.json` subset superseded) · ng_beehive 28 tables · dbt dictionary (14,063/12/218/53, server-exact) · pivot map · databricks token audit (10 PATs, 2 alive — time-sensitive) · `dim_admin_user_full.json` 34,821 · `safety\` 251,796 · resume state (`jira\state*.json`, 4 windows exhausted) · `VAULT-CATALOG.md` (2nd refresh + 2026-09-04 stale-root addendum; full 3rd refresh still gated on remine2/descr_full). Subset/stale roots: documented in `analysis/STALE-ROOTS_2026-09-04.md` (`jira-projects.json` 40/483; `saved-queries.json` 100/240; `jira-scale-issues.json` columns fixed to list). Sibling markers: `saved-queries.STALE.txt`, `jira-projects.STALE.txt`.

## Cloud-clone progress (2026-09-04)

Research lane offline/CI work without host vault or SSWS — see `analysis/CLOUD-LOOP-STATUS_2026-09-04.md`, `analysis/SHARED_TASK_NOTES.md`, and `analysis/NEXT-QUEUE.md` cloud addendum (enum targets, samples/mint probes, remine2-parity sieve, saved-queries censuses, hard-coded refs probe, tier-2 WHERE verify).

## Open items (v5)
1. **Manifest regeneration** — vault `manifest.sha256` still 478 lines / 0 hashes on research host; cloud clone partial pin: `analysis/manifest-cloud-clone.sha256` (**478** git-blob SHA-1 lines of filtered tracked paths as of PR #95; CI verifies vs index; prose count CI-enforced).
2. **remine2 authoritative run pending** — dm2 18/19 TSVs 0-byte; rerun `scripts\repair\remine2.py`; requires `REMINE2-RECONCILIATION.md` disk-verified completion proof (cookies −10, sas anomalies).
3. **descr_full completion** — 450,000 / ≈665,750 (~68%); ~215,750 rows / ~44 batches remain; cursor 2332858; resumable.
4. **Tier-2 remaining configs** — sample-backed WHERE verify vs `scripts/tier2_pull.ps1` (`analysis/tier2-where-column-verify_2026-09-04.*`): driverreg/emaillog/supportcase **OK**; compensations/veritas **UNVERIFIED** (no CSM samples). INDEX prose aligned to script WHERE columns. Full `dim_user` config still missing.
5. **Delta cadence** — watermark 2026-08-26T23:43; leak sources active; rerun `delta_monitor.ps1` next online window; record `delta_scan.py` hits.
6. **Col-13 owners-blob mojibake** — repair or formally scope out (G-01 residual).
7. **JWT liveness re-triage v3** — 5 LIVE expire 08–16.09.2026 (time-boxed).
8. **Tier-3 queue + owner decisions** — see `analysis\PLAN-AND-AWS-STATE.md` B-c/B-e (29-item consolidated queue; 4 owner decision blocks).

## ⚠ Handling notes
- `scripts\` embeds the two live PATs — keep `D:\bolt` out of sync/backup destinations that leave this machine.
- Atlassian JWTs / AWS mentions / Box csrfTokens are **evidence, not for use** (third-party systems; NEVER-ROTATE honored; zero secrets validated by use).

---
*Provenance: disk-verified 2026-09-04 — descr_full state.json + 90 envelope sums; delta row_count/max-ts parsed; tier2 envelopes summed (4,555 / 5,000+442); tier2_pull.ps1 configs re-read; manifest 682/0 re-counted; entities_v2 14,858 lines; attribution_v3 5,535 rows re-tiered; dm2 sizes re-stat; remine2.py existence confirmed; dbx_*.ps1 never opened; no network.*
