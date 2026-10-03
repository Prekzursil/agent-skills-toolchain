# RB-3 — lifecycle-DoS verification (S3 lifecycle-policy plane, strictly non-destructive)

**Lane-41 / SOTA Track A3 staged runbook · authored 2026-10-02 · GO-GATED — STAGING ONLY**

| Axis | Value |
|---|---|
| Lane reference | ASSESSMENT-PLAN-SOTA.md §Track A3 ("lifecycle-DoS verification"); §4 GO-gated set [source: /work/bolt-intel/ASSESSMENT-PLAN-SOTA.md] |
| Provenance | /work/bolt-intel/ASSESSMENT-PLAN-SOTA.md (A3 template mandate; destructive-lifecycle verification lane text); /work/bolt/REPORT/receipts/lane-33 (proven SQL write reach: INSERT→DELETE→COUNT=0 at a tested managed prefix; Files API 403-revoked); /work/bolt/REPORT/receipts/lane-32 (AWS holdings: only 5 mountable key pairs at that time — 2 expired / 3 dead; 181 secret-bearing pairs remain host-side unstaged); /work/bolt-intel/SSOT_2026-09-06.md (managed bucket set incl. bolt-delta-lake-sensitive; wave-15 goldwave bucket listings); /work/bolt/REPORT/receipts/lane-41/RUNBOOK-lifecycle-dos-verification.md (compact prior draft, superseded by this file, kept for lineage); /work/bolt/REPORT/LANE-REGISTER.md (lane-40 block: NO-RE-BURN of the proven write primitive) |
| GO status | **AWAITING OWNER GO** |

## 1. Target(s) (as on-disk)

- **S3 lifecycle-policy write reachability on managed buckets** (`bolt-delta-lake-sensitive` and the wave-15 managed bucket set) via the **proven SQL write path** (lane-33: INSERT→DELETE→COUNT=0 at a tested prefix; the lifecycle-policy surface itself was never probed) [source: /work/bolt/REPORT/receipts/lane-41/RUNBOOK-lifecycle-dos-verification.md, Target row; lane-33 write-reach proof].
- The DoS hypothesis under verification: whether a lifecycle-policy transition (ExpireObject / NoncurrentVersionExpiry) could be attached by the SQL-write principal — **NON-destructively inferable only**; every policy-write remains PROHIBITED (see §6).

## 2. Preconditions (all required BEFORE any firing)

1. **Owner GO** — explicit, dated, in writing. NOTE: even under GO, this runbook remains **strictly read-only** (see §3/§6); the destructive leg named by the original lane text stays parked behind a *separate, future* GO issuance that this runbook does not authorize.
2. **LIVE Databricks PAT** sha8 `4c5f245f` (or `2e1ce409` subset) — present in the vault; used per NEVER-ROTATE, single-attempt per (key,endpoint).
3. **LIVE AWS key pair for the bucket-control plane** — **NONE currently mountable** (lane-32 verdict: 2 expired / 3 dead; 181 pairs host-side). boto3 lifecycle read executes ONLY if the operator stages a verified-live pair [source: /work/bolt/REPORT/receipts/lane-32 CRED-MATRIX.md].
4. NEVER-ROTATE ledger re-read; NO-RE-BURN: the lane-33 write proof (INSERT→DELETE→COUNT=0) must NOT be re-executed — cite the existing evidence [source: /work/bolt/REPORT/LANE-REGISTER.md, lane-40 block]; leak-gate acknowledged.

## 3. Technique table (all read-only)

| Step | Technique (name / source) | Expected observable | Call cost | Risk class |
|---|---|---|---|---|
| T0 | Gateway/host health sentinel before first contact [source: /work/bolt/REPORT/CONVENTIONS.md] | 404-root/406 `/mcp` signature | ≤1 | RECON-READ |
| T1 | SQL metadata read over the proven statement-API path: `DESCRIBE TABLE`/`SHOW TBLPROPERTIES`-class + `information_schema` volume/table-properties enumeration for lifecycle-bearing properties (read-only) [NEEDS-VERIFY — exact property surface on this build] | property rows that reference lifecycle/retention classes (sha8-only values) | ≤2 | RECON-READ |
| T2 | **Conditional** boto3 `get_bucket_lifecycle_configuration` (READ-ONLY) — ONLY if a verified-live AWS pair is operator-staged [source: lane-32 preconditions; prior draft Tools row] | lifecycle rule listing (rule counts + sha8 fingerprints) OR AccessDenied → policy-plane separation evidence | ≤1 | RECON-READ |
| T3 | Inference close-out: policy-metadata visibility vs write-reachability mapping | documented inference chain, sha8 evidence, STOP | ≤0 (analysis-only) | ANALYSIS |

**PROHIBITED everywhere, including under GO**: `put_bucket_lifecycle_configuration`, `delete_bucket_lifecycle_configuration`, any policy PUT/DELETE, any object/tag mutation. These are named only to define the abort boundary.

## 4. Execution ladder (ordered phases)

- **P0** Sentinel + credential/vantage confirmation — fail-closed BEFORE technique steps.
- **P1** SQL metadata read (T1) on the managed objects (no data-row reads; metadata only).
- **P2** Conditional boto3 lifecycle read (T2) — skipped entirely (recorded as SKIPPED-no-key) unless a live key was staged.
- **P3** Inference close-out (T3): map "SQL-write-proven principal" × "policy-plane visibility" into the DoS-feasibility verdict WITHOUT executing any policy change; document the inference chain and stop.

## 5. Network-call budget (FUTURE — declared, not spent)

| Phase | Cap |
|---|---|
| P0 | ≤1 |
| P1 | ≤2 |
| P2 | ≤1 (conditional; 0 if no live key) |
| P3 | 0 |
| **Total** | **≤4 network actions** |

Pacing: ≥1.25 s between calls (enforces ≤1 rps); single-attempt per (key,endpoint).

## 6. Abort criteria (fail-closed)

- **Two-strikes** per primitive class (two consecutive failures of the same read primitive → abort that primitive, record, fail-closed).
- Any **429** → immediate abort; ≥3 consecutive transport failures → lane abort.
- **Dirty-state tripwire (special)**: byte-for-byte before/after comparison of any policy/table metadata; ANY drift beyond the declared read scope → immediate stop, residue re-verify, whole-lane abort, register note.
- Any accidental write-shaped request (even one rejected with 403) → recorded as a strike + explicit post-hoc verification that no state changed.
- **Budget-abort fail-closed**: budget exhausted → stop regardless of state.
- Policy-write is only INFERRED, never executed: if the inference chain cannot be completed with read-only evidence, the verdict stays INFERRED-ONLY and the lane closes with that caveat.

## 7. Success oracles (exact, verifiable)

- **O1**: lifecycle/retention-relevant property or rule metadata made visible through either read path → exposure/feasibility mapped with sha8 evidence.
- **O2**: metadata before/after **identical** (byte-for-byte) at every checkpoint.
- **O3**: if write-feasibility is only inferable, the inference chain is documented end-to-end with sha8-hashed intermediates and the lane STOPS there (no policy mutation, ever, under this runbook).
- **O4**: zero data-row reads (metadata plane only), zero PII values anywhere.

## 8. Evidence / receipt requirements

- Execution receipt: `/work/bolt/REPORT/receipts/lane-41/rb-3-execution.md` + append to `SHA256SUMS.lane-41` (`sha256sum -c` verified).
- sha256 per artifact; sha8-only fingerprints; **zero PII values** (counts/sha8 only); property/rule values hashed, never pasted.
- Leak-gate: NO raw `eyJ…`/`Bearer` shapes; AWS/Databricks credential material never echoed.
- Every claim `[source: …]` or `[NEEDS-VERIFY]`. (No lifecycle-specific CVE/technique identifier is named in the on-disk corpus → none asserted.)

## 9. Cleanup plan

No writes are permitted, so cleanup = verification only: re-read the metadata surfaces touched in P1/P2 and diff against the P0 baseline (must be byte-identical); purge all transient container artifacts; record the SKIPPED/blocked legs explicitly.

## 10. Binding constraints (acknowledged)

NEVER-ROTATE all credentials · single-attempt per (key,endpoint) · ≤1 rps · destructive actions GO-GATED only — **and in this runbook prohibited even under GO** (read-only inference only) · victim/third-party credentials report-only · zero PII values anywhere · NO-RE-BURN of the lane-33 write proof · every factual claim traceable to on-disk source or marked `[NEEDS-VERIFY]`.

AWAITING OWNER GO — DO NOT FIRE
