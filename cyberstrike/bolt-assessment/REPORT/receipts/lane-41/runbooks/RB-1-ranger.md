# RB-1 — Ranger authed-RCE ladder (Apache Ranger admin plane)

**Lane-41 / SOTA Track A3 staged runbook · authored 2026-10-02 · GO-GATED — STAGING ONLY**

| Axis | Value |
|---|---|
| Lane reference | ASSESSMENT-PLAN-SOTA.md §Track A3 ("Ranger authed-RCE ladder"); §4 "GO-gated lanes are prepared, never executed" [source: /work/bolt-intel/ASSESSMENT-PLAN-SOTA.md] |
| Provenance | /work/bolt-intel/ASSESSMENT-PLAN-SOTA.md (A3 template mandate); /work/bolt-intel/SSOT_2026-09-06.md (vpc-census wave-15; megawave vault-ranger-final + airflow-ranger; session-value inventory; cve-exhaustive atlas r2 R1 corrections; w19 gate-980s + ranger-nashorn); /work/bolt/REPORT/receipts/lane-31/ATTACK-SURFACE-INVENTORY.md (Spectrum edge mirrors); /work/bolt/REPORT/receipts/lane-41/RUNBOOK-ranger-rce-ladder.md (compact prior draft, superseded by this file, kept for lineage); /work/bolt/REPORT/LANE-REGISTER.md (lane-40 evaluation block) |
| GO status | **AWAITING OWNER GO** |

## 1. Target(s) (as on-disk)

- Primary: Apache Ranger **admin console** on the **Ranger+MLflow+DataHub shared internal ingress** (vpc-census wave-15 internal cluster; 188 new internal hosts / 65 IP clusters / 8 subnets; split-DNS resolves but **no route from the engagement container**) [source: /work/bolt-intel/SSOT_2026-09-06.md, vpc-census entry].
- External mirrors (recon-only context): Spectrum edges 172.65.240.204 (prod) and 172.65.223.108 (new edge) mirror the admin estate vhost-by-vhost behind an **mTLS envoy interstitial** ("Certificate needed") [source: /work/bolt/REPORT/receipts/lane-31/ATTACK-SURFACE-INVENTORY.md].
- Version band on-disk: Ranger **IN-RANGE [2.2.0–2.4.0]** per gate-980s (vul_095f2e53f001) [source: /work/bolt-intel/SSOT_2026-09-06.md, w19 entry].

## 2. Preconditions (all required BEFORE any firing)

1. **Owner GO** — explicit, dated, in writing (per ASSESSMENT-PLAN §4: prepared, never executed until GO issuance).
2. **Network vantage**: authorized route to the internal ingress (split-DNS resolves; container has no route today). Operator must provide the vantage; NO new network position may be created by the red team itself [source: SSOT vpc-census entry; lane-41 prior draft Gating row].
3. **msfrpcd estate-side start** (operator item D) if MSF-rank modules are to be used — currently metasploit backend UNAVAILABLE (msgrpc refused) [source: /work/bolt/REPORT/receipts/lane-30 backend manifest; ASSESSMENT-PLAN §4].
4. **Credential basis**: NO Ranger admin credential is held. Both doors "positively closed on every reachable plane" per vault-ranger-final [source: SSOT megawave entry]. Any authed leg therefore depends on an employee bolt.okta.com session reaching the console (consolidated truth: every remaining escalation path funnels through one employee session) [source: SSOT session-value inventory + architectural verdict]. No session is held → authed phases fire ONLY if operator supplies one; otherwise the runbook terminates at recon.
5. NEVER-ROTATE ledger re-read; leak-gate (sha8-only) acknowledged.

## 3. Technique table

| Step | Technique (name / source) | Expected observable | Call cost | Risk class |
|---|---|---|---|---|
| T0 | Gateway/host health sentinel before first contact [source: /work/bolt/REPORT/CONVENTIONS.md] | 404-root/406 `/mcp` signature | ≤1 | RECON-READ |
| T1 | Authed recon of admin console: GET `/login`, JS bundle version banner — HackTricks-corpus style "admin console version fingerprint" [source: ASSESSMENT-PLAN-SOTA.md A3; NEEDS-VERIFY at runtime] | Ranger build string; confirm/deny [2.2.0–2.4.0] band | ≤2 | RECON-READ |
| T2 | Authenticated policy read: `GET /service/plugins/policies` (read-only enumeration; standard Ranger REST surface) [NEEDS-VERIFY — exact endpoint set for this build] | ≥1 policy row JSON (sha8-fingerprinted only) | ≤2 | RECON-READ |
| T3 | Authed-RCE class per ranger-nashorn authed-class vul_0960df9dc001 (band firm [2.2.0–2.4.0], unsandboxed) [source: SSOT w19 ranger-nashorn]; Ranger CVE-2025-59059 flagged in-range by cve-exhaustive atlas r2 R1 [source: SSOT w18 cve-exhaustive entry] — applicability to this console build [NEEDS-VERIFY] | Command-execution oracle: `id`-echo only, zero persistence | ≤3 | RCE-PROBE (GO-GATED) |
| T4 | Post-primitive verification + logout; policy JSON diff before/after | diff = identical; session terminated | ≤2 | CLEANUP |

## 4. Execution ladder (ordered phases)

- **P0** Sentinel + vantage confirmation — fail-closed BEFORE technique steps.
- **P1** Version fingerprint (T1) → confirms/denies in-range band. Out-of-band → dated HELD receipt, stop.
- **P2** Policy read-reach (T2) — read-only proof of authorization plane access.
- **P3** RCE class (T3) — ONLY if P2 succeeded AND owner GO covers the RCE class explicitly. id-echo oracle, single attempt per (key,endpoint).
- **P4** Cleanup (T4) — diff, logout, seal.

## 5. Network-call budget (FUTURE — declared, not spent)

| Phase | Cap |
|---|---|
| P0 | ≤1 |
| P1 | ≤2 |
| P2 | ≤2 |
| P3 | ≤3 |
| P4 | ≤2 |
| **Total** | **≤10 network actions** |

Pacing: ≥1.25 s between calls (enforces the binding ≤1 rps hard rule); single-attempt per (key,endpoint).

## 6. Abort criteria (fail-closed)

- **Two-strikes** per primitive class (2 consecutive failures of the same primitive → that primitive aborted, recorded, fail-closed).
- Any **429** or rate-limit signature → immediate abort.
- ≥3 consecutive transport failures → lane abort.
- Any unintended state change beyond a declared id-echo → immediate rollback attempt, residue re-verify, whole-lane abort, register note.
- **Budget-abort fail-closed**: budget exhausted → stop regardless of state.
- No authed session available at P2 gate → terminate with dated HELD receipt (this is the expected outcome on current holdings).

## 7. Success oracles (exact, verifiable)

- **O1**: authenticated session established on Ranger console (≥1 2xx on login POST or API).
- **O2**: policy-list read returns ≥1 policy row (read-reach proof), sha8-only fingerprints.
- **O3**: any RCE primitive yields command-execution oracle WITHOUT persistence — `id`-echo only.
- **O4**: zero policy modifications — policy JSON diff before/after identical.
- **O5**: full session logout; no artifacts left on target.

## 8. Evidence / receipt requirements

- Execution receipt: `/work/bolt/REPORT/receipts/lane-41/rb-1-execution.md` + append to `SHA256SUMS.lane-41` (`sha256sum -c` verified).
- sha256 for every artifact; **sha8-only fingerprints in chat/artifacts**; **zero PII values** (counts/sha8 only).
- Leak-gate: NO raw `eyJ…`/`Bearer` shapes anywhere; version strings and response bodies hashed, not pasted.
- Every claim carries `[source: …]` or `[NEEDS-VERIFY]`.

## 9. Cleanup plan

Logout all sessions created; delete any transient request artifacts from the container workspace; before/after state diff (P4) must be **identical**; record diff result in the receipt even when terminating early.

## 10. Binding constraints (acknowledged)

NEVER-ROTATE all credentials · single-attempt per (key,endpoint) · ≤1 rps · destructive actions GO-GATED only (RCE-probe class additionally gated) · victim/third-party credentials report-only · zero PII values anywhere · every factual claim traceable to on-disk source or marked `[NEEDS-VERIFY]`.

AWAITING OWNER GO — DO NOT FIRE
