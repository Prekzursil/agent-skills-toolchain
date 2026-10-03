# RB-2 — kubecost re-test (cost/allocation plane exposure re-measure)

**Lane-41 / SOTA Track A3 staged runbook · authored 2026-10-02 · GO-GATED — STAGING ONLY**

| Axis | Value |
|---|---|
| Lane reference | ASSESSMENT-PLAN-SOTA.md §Track A3 ("kubecost re-test"); §4 GO-gated set [source: /work/bolt-intel/ASSESSMENT-PLAN-SOTA.md] |
| Provenance | /work/bolt-intel/ASSESSMENT-PLAN-SOTA.md (A3 template mandate); /work/bolt-intel/SSOT_2026-09-06.md (w20 breach-series names `kubecost-depth` + `prometheus-depth`; vpc-census: internal planes resolve via split-DNS but no route from the engagement container); /work/bolt/REPORT/receipts/lane-41/RUNBOOK-kubecost-retest.md (compact prior draft, superseded by this file, kept for lineage); /work/bolt/REPORT/LANE-REGISTER.md (lane-40 evaluation block) |
| GO status | **AWAITING OWNER GO** |

## 1. Target(s) (as on-disk)

- kubecost **cost/allocation plane from a VPC vantage** (internal ingress; the external Spectrum edges mirror the admin estate only, mTLS-enforced) [source: /work/bolt/REPORT/receipts/lane-41/RUNBOOK-kubecost-retest.md, Target row; lane-31 ATTACK-SURFACE-INVENTORY.md for the edge-mirror statement].
- Prior lane: w20 `kubecost-depth` — **depth assessed, multi-cluster cost-data reach unresolved at seal** [source: /work/bolt-intel/SSOT_2026-09-06.md, w20 breach-series list + prior draft Prior-evidence row].
- Endpoint set from the prior draft (read-only GETs): `/api/allocation`, `/api/costDataRange`, `/model/alldata` [source: /work/bolt/REPORT/receipts/lane-41/RUNBOOK-kubecost-retest.md, Tools row].

## 2. Preconditions (all required BEFORE any firing)

1. **Owner GO** — explicit, dated, in writing.
2. **Confirmed VPC vantage reachability from the authorized container** — no new network position may be created by the red team (split-DNS resolves but no route from home per vpc-census) [source: SSOT vpc-census entry; prior draft Gating row].
3. No kubecost credential is held — the re-test is **anon-first**, authed second (separation below). If an operator supplies an authenticated vantage context, it is declared in the receipt before use.
4. NEVER-ROTATE ledger re-read; leak-gate (sha8-only) acknowledged.

## 3. Technique table

| Step | Technique (name / source) | Expected observable | Call cost | Risk class |
|---|---|---|---|---|
| T0 | Gateway/host health sentinel before first contact [source: /work/bolt/REPORT/CONVENTIONS.md] | 404-root/406 `/mcp` signature | ≤1 | RECON-READ |
| T1 | **Anonymous** enumeration ladder: GET `/api/allocation`, `/api/costDataRange`, `/model/alldata` (one attempt each; standard kubecost cost-model API surface) [source: prior draft Tools row] | 200-with-allocation-JSON (exposure) vs 401/403/302 (gated) | ≤3 | RECON-READ |
| T2 | **Auth-vs-anon separation**: repeat the strongest 200-endpoint under the operator-supplied authed context only if declared (NEVER-ROTATE; single-attempt) | delta between anon and authed visibility | ≤2 | AUTH-CONTEXT-READ |
| T3 | Cluster/namespace enumeration triage — sha8 fingerprints of workload names only, no full inventories | enumerated namespace/workload counts + sha8 list | ≤1 | RECON-READ |
| T4 | Re-verify + close-out diff | before/after state identical | ≤1 | CLEANUP |

## 4. Execution ladder (ordered phases)

- **P0** Sentinel + vantage confirmation — fail-closed BEFORE technique steps.
- **P1** Anonymous read ladder (T1) — resolve the w20 "unresolved multi-cluster cost-data reach" question directly.
- **P2** Auth-vs-anon separation (T2) — only if P1 returned any 200 AND operator-supplied authed context exists.
- **P3** Triage to sha8-only workload fingerprints (T3).
- **P4** Cleanup + dated verdict receipt (T4).

## 5. Network-call budget (FUTURE — declared, not spent)

| Phase | Cap |
|---|---|
| P0 | ≤1 |
| P1 | ≤3 |
| P2 | ≤2 |
| P3 | ≤1 |
| P4 | ≤1 |
| **Total** | **≤8 network actions** |

Pacing: ≥1.25 s between calls (enforces ≤1 rps); single-attempt per (key,endpoint).

## 6. Abort criteria (fail-closed)

- **Two-strikes** per primitive class (two consecutive failed GET classes → abort that class, record).
- Any **429** → immediate abort; ≥3 consecutive transport failures → lane abort.
- Any response implying a state-changing side effect (unexpected 2xx on write-shaped call) → treat as unintended state change: stop, re-verify, abort lane, register note.
- **Budget-abort fail-closed**: budget exhausted → stop regardless of state.
- If all P1 endpoints gate cleanly → write the dated HELD receipt and terminate early (no P2).

## 7. Success oracles (exact, verifiable)

- **O1**: ≥1 HTTP 200 on an **unauthenticated** allocation endpoint → re-open finding as data-exposure with sha8 evidence.
- **O2**: all endpoints gated (401/403/302) → dated HELD receipt, zero re-open, w20 question closed as measured-gated.
- **O3**: any cluster-namespace enumeration naming workloads → sha8-only workload fingerprints, no full inventories, no cost values pasted (aggregate counts only).

## 8. Evidence / receipt requirements

- Execution receipt: `/work/bolt/REPORT/receipts/lane-41/rb-2-execution.md` + append to `SHA256SUMS.lane-41` (`sha256sum -c` verified).
- sha256 per artifact; sha8-only fingerprints; **zero PII values**; response bodies hashed/summarized, never pasted whole.
- Leak-gate: NO raw `eyJ…`/`Bearer` shapes.
- Every claim `[source: …]` or `[NEEDS-VERIFY]`. (No kubecost-specific CVE is named in the on-disk corpus → no CVE identifiers are asserted here.)

## 9. Cleanup plan

No state changes expected (read-only GET ladder). Verify no sessions/cookies persist in the container workspace; purge curl artifacts; before/after diff identical; record early-termination state when applicable.

## 10. Binding constraints (acknowledged)

NEVER-ROTATE all credentials · single-attempt per (key,endpoint) · ≤1 rps · destructive actions GO-GATED only (none planned — read-only) · victim/third-party credentials report-only · zero PII values anywhere · every factual claim traceable to on-disk source or marked `[NEEDS-VERIFY]`.

AWAITING OWNER GO — DO NOT FIRE
