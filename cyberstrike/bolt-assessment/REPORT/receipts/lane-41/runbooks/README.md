# Lane-41 GO-Gated Runbook Index (SOTA Track A3) — STAGING ONLY

**Authored 2026-10-02 · Bolt Technology OÜ authorized red-team engagement · zero network activity in this staging pass**

Four execution runbooks authored from on-disk intel only. No network call was made; no credential was used, echoed, or rotated; every factual claim is traceable to an on-disk source (`[source: …]`) or explicitly marked `[NEEDS-VERIFY]`. Destructive primitives are GO-GATED; RB-3 additionally prohibits policy writes even under GO (read-only inference only).

| Runbook | Lane | Budget cap (network actions) | GO status | Destructive scope |
|---|---|---|---|---|
| [RB-1-ranger.md](RB-1-ranger.md) — Ranger authed-RCE ladder | Track A3 / lane-41 | **≤10** (P0≤1/P1≤2/P2≤2/P3≤3/P4≤2) | **AWAITING** | RCE-probe class T3 GO-GATED |
| [RB-2-kubecost.md](RB-2-kubecost.md) — kubecost re-test | Track A3 / lane-41 | **≤8** (P0≤1/P1≤3/P2≤2/P3≤1/P4≤1) | **AWAITING** | none (read-only ladder) |
| [RB-3-lifecycle-dos.md](RB-3-lifecycle-dos.md) — lifecycle-DoS verification | Track A3 / lane-41 | **≤4** (P0≤1/P1≤2/P2≤1 cond./P3=0) | **AWAITING** | policy writes PROHIBITED even under GO |
| [RB-4-n8n-10.130.md](RB-4-n8n-10.130.md) — n8n-from-10.130 | Track A3 / lane-41 | **≤8** (P0≤1/P1≤2/P2≤2/P3≤2/P4≤1) | **AWAITING** | execution primitives out of scope entirely |

**All four carry the identical hard constraints**: NEVER-ROTATE credentials; single-attempt per (key,endpoint); ≥1.25 s pacing (≤1 rps); victim/third-party credentials report-only; zero PII values (counts/sha8 only); leak-gate compliance (no raw `eyJ…`/`Bearer` shapes); sha8-only fingerprints in chat and artifacts; two-strikes-per-primitive abort; budget-abort fail-closed.

**Sentinel**: every runbook terminates with the exact line `AWAITING OWNER GO — DO NOT FIRE`.

**Lineage**: these full-template runbooks supersede the four compact drafts (`RUNBOOK-ranger-rce-ladder.md`, `RUNBOOK-kubecost-retest.md`, `RUNBOOK-lifecycle-dos-verification.md`, `RUNBOOK-n8n-from-10.130.md`) already under `receipts/lane-41/`; the drafts are retained for provenance. Lane-40 selection items (CH-1/CH-4, CH-2 conditional) are unaffected — those execute under the lane-41 SELECTION-MEMO, not under this runbook set.

**Open [NEEDS-VERIFY] markers** (to resolve only during a future authorized firing pass): RB-1 T1 console/JS version-banner surface; RB-1 T2 exact policy-endpoint set for the deployed build; RB-1 T3 CVE-2025-59059 applicability to this console build (atlas-flagged, unconfirmed); RB-2 T1 exact API surface of the deployed kubecost (no kubecost CVE asserted anywhere — none on-disk); RB-3 T1 exact lifecycle/retention property surface; RB-4 T1 editor ingress path (no n8n CVE asserted — none on-disk).

**Seal**: `SHA256SUMS` in this directory covers README.md + all four runbooks; verify with `sha256sum -c SHA256SUMS`.

AWAITING OWNER GO — DO NOT FIRE
