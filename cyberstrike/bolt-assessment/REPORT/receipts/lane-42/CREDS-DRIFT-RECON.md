# LANE-42 STEP 0b — CREDS-SSOT DRIFT RECONCILIATION (582 vs 632 vs 782)

- **Lane:** 42 (final consolidation, STEP 0b)
- **Date executed:** 2026-10-02
- **Mode:** ZERO network, ZERO new credential probes, ZERO credential-value reads beyond structural census (sha8 fields only). NEVER-ROTATE untouched. Third-party victim credentials remain REPORT-ONLY.
- **Artifacts examined:** `/work/intel-core/credentials/CREDS-SSOT_2026-09-06.json` (master, sha256 `bf9acbd29378…`), lineage `…_v1/_v2/_v4/_v5.json`, `…_pre-ssot-v5.bak.json`, `…_2026-09-06.md`, `_build_ssot.py`, 61 dated append files; phase-0 `/work/bolt/REPORT/phase0/CREDENTIAL-LEDGER.md` row 24; lane-32 `CRED-MATRIX.md` (64-row final); lane-37 `/work/lane37/build_graph.py` + GRAPH-RECEIPT + graph_stats (782 Credential nodes).

---

## 1. Anchor figures and their exact provenance

| Figure | Where it comes from | Verification |
|---|---|---|
| **582** | **v1-era census** of `CREDS-SSOT_2026-09-06_v1.json` stats block; transcribed into phase-0 CREDENTIAL-LEDGER row 24 as the engagement baseline | v1 stats = `total_unique 582, live_usable_creds 17, dead 64, expired 239, unverified 19, unknown_never_tested 229` — **verbatim match** to ledger row 24 histogram "17 LIVE / 64 DEAD / 239 EXPIRED / 19 UNVERIFIED / 229 NEVER-TESTED" |
| **632** | `ssot-v5` census (waves 8–14 catch-up, 2026-09-06) = current master `stats.total_unique` = the figure quoted in lane-37 GRAPH-RECEIPT line 119 | Master stats sum check: 40 live + 1 free_live + 7 soft_revoked + 70 dead + 255 expired + 8 placeholder + 6 unverified + 3 suspended + 64 not-a-cred + 154 not-testable + 24 untestable-shape = **632 exactly** |
| **782** | Current master `credentials[]` row count = kuzu graph Credential node count (row-level PK = sha8) | Independent recount: 782 rows, 782 distinct sha8 values; lane-37 provenance src000 = same file, sha256 `bf9acbd29378…` |

## 2. Lineage census chain (all files present in credentials dir)

| Lineage file | rows | stats.total_unique | live | dead | expired |
|---|---|---|---|---|---|
| `…_v1.json` (2026-09-06 gen) | 582 | **582** | 23 (usable 17) | **64** | **239** |
| `…_v2.json` (creds-verify2) | 582 | 582 | 35 | 70 | 240 |
| `…_v4.json` (pre-drain2 era) | 589 | 589 | 36 | 70 | 241 |
| `…_pre-ssot-v5.bak.json` | 607 | 607 | 43 | 71 | 251 |
| `…_v5.json` (ssot-v5) | 632 | 632 | 40 | 70 | 255 |
| **`CREDS-SSOT_2026-09-06.json` (current master)** | **782** | **632** | 40 | 70 | 255 |

## 3. Delta classification

| Bucket | Count | Explanation (evidence) | sha8-only examples |
|---|---|---|---|
| **(a) Staging arrival during authorized engagement** | **0** | EXCLUDED by four independent proofs: (1) mtime audit — 0 files newer than 2026-10-01T17:09:39Z (see STAGING-RECHECK.md); (2) verdict_date census — range 2026-09-06→2026-09-19 across all 748 dated rows, **0 rows ≥ 2026-09-30**; (3) discovered_in lane vocabulary — all tags are pre-engagement operator campaign lanes (cowork-inv 500, cred-gauntlet 86, bolteu-github-inv 46, harvest-inv 41, creds-cursor 39, ssot-v5 25, food-forensics 22, ai-endpoints 20, git-creds 15, lane4-c-emulator 6, yasin-pats 3, cursor-workos-chain 3, PAT-backup 2, dbx-bucket 2, cursor-restore 2); (4) master sha256 `bf9acbd29378…` byte-stable — identical to lane-37's 2026-10-02 provenance hash. | — |
| **(b) Ledger drift — pre-engagement operator lineage growth 582→632** | **+50** | Operator-side SSOT regeneration chain dated 2026-09-06: v1→v2 verdict-only (582, live_usable 17→35); v2→v4 **+7** rows (582→589); v4→pre-v5 **+18** rows (589→607); pre-v5→v5 **+25** rows (607→632) — the +25 enumerated in the md stats table and `regenerated_by.append`. Zero of these rows post-date 2026-09-19. | ssot-v5 +25: a63be4ce (cursor-session-jwt LIVE), d7efcfa8 (cursor-api-key LIVE), 34d80612 (bolt-eater-authtoken LIVE), 59e80250 (bolt-rider-jwt EXPIRED), fea1f60e / c44b1da8 / 453020af (EXPIRED), 4bdacafb / 5a2f7eba / 18544bde (UNVERIFIED), 245861ad / 87a9e6b1, 05fa1844 + 13 NOT-A-CREDENTIAL rows (c37c0914 … 16efcf59), f1c0a4c7 |
| **(c) Ingest / counting artifact — 632 census vs 782 rows** | **+150 rows** (not new credentials) | Exactly 150 current-master rows are absent from v5 (independently isolated). They are the operator's **post-v5 append waves dated 2026-09-14→2026-09-19** (backup files enumerate the waves: pre-pmm-apikey, pre-sre-battery, pre-openai-spark-lake, pre-jfrog-enum, pre-gcp-compute-foothold, pre-google-oauth-trio, pre-outsource-cred-hunt, pre-dbx-query-params, pre-braze-write-probe, pre-braze-15-verify, fenti-mqtt, braze-scope-matrix, pre-cursor-workos-chain-20260919, pre-webform-open-window, pre-support-text-via-bypass, pre-sec1-followup, pre-fenti-editor-strip-note). These appends grew the row array WITHOUT regenerating the stats block — **core census fields remain frozen at v5 values** (total_unique 632 / live 40 / dead 70 / expired 255; only auxiliary fields differ). Lane-37 then ingested ALL 782 rows as row-level Credential nodes (782 nodes) while its receipt quoted the frozen 632 census → 632-vs-782 is a **counting-basis divergence**, not credential growth. | Post-v5 +150 provider mix: braze 70 (lowercase-'live' catalog-only class = the 66-key Braze catalog baseline +4), provider-UNSET 34, supportwebform.bolt.eu 19, AWS-class 12, Hertz-Estonia-Zendesk 6, google 3, cursor 3, gcp 1, taxify.atlassian.net JSM 1; verdict mix: live 66, UNSET 29, DEAD/ERR 12, untested 11, HONORED-AT-AUTH-LAYER 10, key-id-only 5, expired 4, dead 4, LIVE 2, EXPIRED 2 |

## 4. Residual unmerged corpus (noted, not counted)

45 dated standalone append files (`CREDS-SSOT_2026-09-14…2026-09-29_*_append.json`, 55,039 total rows, dominated by warehouse-dimuser 34.4 MB + osintly-snusbase/jira-tail/leakcheck stealer corpora) were **never merged** into the master (master's post-v5 rows end 2026-09-19; appends continue to 2026-09-29). These are operator-side, pre-engagement, largely report-only victim/PII-harvest material per ROE. No values were read during this reconciliation; counts only. The manifest's "52 MB" figure corresponds to the whole credentials directory (53,359,799 B), not the 786 KB master json — the operator manifest conflated the two and carried the stale v1-era "582 creds" figure.

## 5. Engagement-time credential verdicts (for completeness)

No verdicts were written into the master SSOT during the authorized engagement (proofs in bucket (a)). Engagement verdicts live exclusively in lane receipts/matrices: lane-32 CRED-MATRIX 64-row final (LIVE=4: Databricks 4c5f245f + 2e1ce409, OpenRouter efb9f2bc report-only, GitHub 94ea4604 member-grade); lane-37 applied 5 LIVE overlays to the GRAPH COPY ONLY (find-or-create, not to the SSOT file).

## 6. Disposition (verbatim-usable in final assessment report)

**DISPOSITION:** The 632-vs-582 delta is entirely pre-engagement, operator-side SSOT lineage growth — the v1 census of 582 (phase-0 baseline anchor, verified verbatim against v1 stats: live_usable 17 / dead 64 / expired 239 / unverified 19 / never-tested 229) grew to 632 at ssot-v5 (2026-09-06, +25 enumerated rows) — while the current master additionally carries 150 post-v5 appended rows (2026-09-14→09-19 operator waves) against a stats block whose core census fields remain frozen at v5 values, which lane-37 ingested row-level (782 kuzu Credential nodes) while quoting the frozen 632 census; zero credentials arrived, changed, or were added during the authorized engagement (0 files newer than 2026-10-01T17:09:39Z; max verdict_date 2026-09-19; master sha256 bf9acbd29378… byte-stable since mount), no new credential probes were executed for this reconciliation, NEVER-ROTATE is untouched, and all third-party victim material (stealer/dimuser corpora among the unmerged appends) remains report-only.

## 7. Compliance

Zero network calls; zero credential probes; zero credential values read (sha8 fields, counts, filenames, dates only); no token/auth-header shapes in this receipt; no PII values.
