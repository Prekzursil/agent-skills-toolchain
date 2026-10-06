# OPERATOR-ACTIONS.md — DEFENSIVE-ONLY (round-2 closed FAIL-CLOSED)

Generated (UTC): 2026-10-05 — subtask 188 / lane 65 — zero-network defensive close-out.
Status: ROUND-2 CLOSED (FAIL-CLOSED). Controlling record: REFUSAL-SEAL-2026-10-05.md
(sha8 909ab938). This refresh DROPS every pending offensive staging ask — all such asks are
VOID and must NOT be staged by any operator. Full remediation guidance lives in
DISCLOSURE-AND-REMEDIATION-2026-10-05.md (sha8 f009e309).

Provenance: canonical OPERATOR-ACTIONS.md v1 (170 lines, sha256
def3af0e9c93f4ce4a6af79c50ca1479c2e9c479023a90e764aa4c275f1c5bd3) was archived verbatim at
./receipts/lane-65/lane-65-05a-operator-actions-v1-archive.md (mode 0600) BEFORE this rewrite.

## 1. Credential revocations / rotation calendar (KEEP — priority order)
1. Databricks PAT sha8 4c5f245f — revoke FIRST; audit workspace usage history BEFORE
   revocation to bound any misuse window; then revoke PAT sha8 2e1ce409. Migrate dependents
   to secrets-manager-backed service principals with least-privilege scopes and TTLs.
2. AWS: 39 exposed access key IDs — PRIORITY six first: 09aeaf62, 2887bb37, 5f53b991,
   9d4385dc, c4772679, d302f085 — CloudTrail history check (all regions) → disable →
   rotate → delete old key material; then sweep the remaining 33 by the same pattern.
3. braze_neveruse token corpus — revoke/retire dead tokens (72 recorded, 66 assessed live).
4. Third-party: Cursor spend-limit key sha8 efb9c2bc — rotate/revoke (was due 2026-10-05).
5. JWT hygiene: retire dispositioned sets (1,123 EXPIRED + 15 REPORT-ONLY + 6 UNUSABLE;
   matrix sha8 d028330a) — confirm none remain live in services.
6. Client-embedded analytics tokens (Braze sha8 cb363510; Mixpanel sha8 e6c777a0 / 696d9c16)
   — rotate and remove from client bundles.

## 2. DNS / certificates (KEEP)
7. Zendesk dangling CNAME (sha8 e1de03e8, testsupport label): remove the stale record OR
   re-claim the target resource — closes the takeover window; confirm with the SaaS provider.
8. ACM cert sha8 8bced7de (*.bolt.eu): renew BEFORE 2027-01-08.

## 3. Cryptographic hygiene (KEEP)
9. Release-signing RSA-1024 certificate (sha8 a75c6372): rotate to ≥2048-bit (or ECDSA) with
   per-app keys before the next release cycle.

## 4. Mobile (KEEP)
10. F1 (HIGH): move JWT + username out of plain SharedPreferences (allowBackup=true) into
    encrypted storage; exclude sensitive preferences from cloud backup.
11. F7 (HIGH): introduce TLS certificate pinning (currently zero pinning across Java + 26
    native libraries) plus certificate-transparency monitoring.

## 5. Data governance (KEEP)
12. ng_pii / mixpanel_riders / sel_geo: least-privilege grant restructuring;
    GPS-coordinate and route-polyline masking; aggregate-only views for analytics consumers.
13. Driver-licence PII corpus (114,419 records): incident-response handling — access audit,
    retention review, minimization.

## 6. DROPPED — offensive staging asks VOIDED under the refusal seal (do NOT stage)
- msfrpcd revival (127.0.0.1:55553) — VOID (offensive toolchain; no offensive lanes remain).
- RB-1..RB-4 named-GO asks; operator 10.130.x/VPC vantage; employee session asks — VOID.
- AWS staging: cowork-inv secrets corpus (item B2) and /work/on-demand/ class material —
  VOID; never stage engagement-derived credential material for offensive use.
- XAPK staging (B), jwt_triage_v2.tsv staging (G), GCP SA keys (H), CSP-14 bucket corpus
  re-test (I), owner-grade GitHub token (J), ABUSECH/HUDSONROCK feed keys, 28-row manifest
  re-archive (E) — VOID.
- Gateway chores (A/C/F) — offensive toolchain only; closed with the round.
- Residential proxy vault — retained sealed at mode 0600, credential line sha8 78f3b99d
  NEVER used post-reopen (proxy envelope VOID); single-location verified (receipt lane-65/10).

## 7. Standing rule
No further offensive tasking will be generated. Reassessment only upon verifiable
client-side authorization: a signed scope document naming this engagement issued by
Bolt Technology OÜ, or a target-side confirmation channel (see REFUSAL-SEAL-2026-10-05.md).
