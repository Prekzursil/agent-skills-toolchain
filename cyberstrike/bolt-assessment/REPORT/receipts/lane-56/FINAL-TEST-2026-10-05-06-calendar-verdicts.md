# Lane-56 Receipt 06 — Calendar Verdicts (Zendesk recheck / Cursor spend review / ACM renewal)

- Date: 2026-10-05 (subtask-155, evaluation checkpoint — STRICTLY OFFLINE from this subtask: zero wire calls; the Zendesk DNS recheck was executed separately by the pentester and is cited by sealed evidence below).

## 1. Zendesk dangling-CNAME recheck — STILL-DANGLING, UNREMEDIATED (verdict FINAL)

- Verdict class RETAINED: dangling-CNAME takeover risk class remains open; no remediation observed as of 2026-10-05 07:38 UTC.
- Observed records (exactly as resolved):
  - `testsupport.bolt.eu. 300 IN CNAME d3v-taxify.zendesk.com.`
  - `d3v-taxify.zendesk.com. 1800 IN A 216.198.53.2, 216.198.54.2` (Zendesk edge 216.198.0.0/16).
- Interpretation: the bolt.eu zone still publishes the byte-identical CNAME to the deleted legacy Taxify dev Zendesk target. Baseline SSOT wave-9 / lane-39 receipt sha8 1420af19 established the target as claimable, quarantine-blocked, with a PoC-proven first-signup-wins path.
- Discriminator limitation: DNS alone cannot distinguish unclaimed-claimable vs third-party-claimed-active-tenant — the baseline discriminator was an HTTP-layer provider 404, which is out of scope under the round's zero-HTTP mandate. BOTH states remain exposure.
- Timeline: quarantine expired ~2026-09-20 → ≥15-day claim-exposed gap as of run date 2026-10-05.
- Method attestation (2-query/zero-HTTP): exactly 2 DNS queries (hard limit), 11 s pacing between them, ZERO HTTP/TLS/port probes; resolved via the direct system resolver per lane-39 baseline lineage (documented exception to proxy routing — the proxy governs HTTP-level attempts only).
- Sealed evidence: lane-56 receipt 02 — `FINAL-TEST-2026-10-05-02-zendesk-dns-recheck-2026-10-05.md`, sha256 e1de03e8631a0f580ce02823ce75668cbdac7156b6d920449306c6a25f3da32c (pre-existing manifest entry — untouched).
- Register-facing remediation wording (verbatim-ready): **remove or re-point the CNAME and confirm address disposition with the SaaS provider.**

## 2. Cursor spend-limit review — due 2026-10-05 (= run date) — report-only owner note

- Standing item sha8 efb9f2bc; review due date falls exactly on this checkpoint's run date.
- Disposition: REPORT-ONLY — no red-team action is available or required (operator/owner-side review of spend limits); no network interaction, no credential touch.
- Register wording: owner to confirm spend limits unchanged and record confirmation; no severity, no exposure change.

## 3. ACM *.bolt.eu renewal — action window before 2027-01-08

- Standing lane-31 lineage item (sha8 8bced7de). Carried as an operator action with deadline 2027-01-08.
- No new certificate surface was introduced by the FINAL-TEST round (lane-36 observed only the pre-existing shared self-signed RSA-1024 release cert a75c6372 in mobile builds — separate finding C-36, already in the remediation list).
- Disposition: note retained pre-2027-01-08; no action from the red team.

## Status roll-up

| Item | Due | Verdict | Evidence |
|------|-----|---------|----------|
| Zendesk dangling-CNAME recheck | 2026-10-05 | STILL-DANGLING, UNREMEDIATED; risk class RETAINED; ≥15-day claim-exposed gap | receipt 02 (e1de03e8) + this receipt |
| Cursor spend-limit review | 2026-10-05 | REPORT-ONLY owner note (efb9f2bc) | this receipt |
| ACM *.bolt.eu renewal | before 2027-01-08 | operator action retained; no new surface | this receipt (lane-31 lineage 8bced7de) |
