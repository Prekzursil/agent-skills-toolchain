# DISCLOSURE & REMEDIATION — OWNER-FACING PACKAGE (ROUND-2 CLOSE-OUT)

Doc: DISCLOSURE-AND-REMEDIATION-2026-10-05.md
Date (UTC): 2026-10-05
Prepared for: Bolt Technology OÜ — security and asset owners
Provenance: materialized STRICTLY from the already-sealed engagement record
(rounds 1–2). No new research, no new probing, zero network actions.
Handling constraints honored by construction: sha8-only fingerprints (first 8 hex of
the recorded sha256), ZERO PII values, ZERO credential material, generic descriptions
only. Leak-gate verified — see receipts/lane-65/.
Priority ordering: credential revocations FIRST (D1, D2), then data-exposure
containment (D3), then takeover/imposture windows (D4–D7), then hygiene (D8, D9).

---

## D1 — Databricks personal access tokens (2 recorded) — REVOCATION ORDER 1 AND 2
Fingerprints: sha8 4c5f245f (revoke FIRST) · sha8 2e1ce409 (revoke second)
Exposure (recorded): two workspace personal access tokens surfaced during the
assessment; both were recorded LIVE at last validation. These underpin the highest-
severity recorded chains (external-links to presigned-object exfiltration, and broad
schema-level grants).
Detection (BEFORE revoking — preserve the audit anchor): pull workspace audit logs /
token usage history for both token identities — creation time, creator, scopes, last
uses, source addresses — so the misuse window is bounded while the token identity is
still resolvable. Capture this FIRST, then revoke.
Remediation: revoke sha8 4c5f245f immediately after the audit capture; revoke
sha8 2e1ce409 second. Migrate dependent automation to secrets-manager-backed service
principals with least-privilege scopes; enforce token TTLs and token-usage policies.
Verification: post-revocation calls must fail auth; alert on any use attempt after the
revocation timestamp (expected: none).

## D2 — Exposed AWS access key IDs (39 recorded; 6 PRIORITY) — REVOCATION ORDER 3
PRIORITY fingerprints: sha8 09aeaf62 · 2887bb37 · 5f53b991 · 9d4385dc · c4772679 · d302f085
Exposure (recorded): 39 AWS access key IDs were recorded as existing (key-ID existence
confirmed) with secret material never located by the assessment; exposure class is
public breach-corpus reference (IDs only).
Detection: for each key ID — starting with the PRIORITY six — query CloudTrail
event history by access-key ID across all regions for ANY historical use since first
exposure; treat every one of the 39 as compromised until rotated.
Remediation: disable + rotate the six PRIORITY keys first; then sweep the remaining 33
by the identical pattern (CloudTrail history check → disable → rotate → delete old key
material). Prefer immediate disablement where rotation scheduling would delay.
Verification: zero CloudTrail events attributable to rotated key IDs after rotation;
alert rules on the retired key IDs for late use attempts.

## D3 — ng_pii / mixpanel_riders / sel_geo datasets and grants — CONTAINMENT
Fingerprints (recorded schema-level exposures): ng_pii (~43.7M-row rider-PII class),
mixpanel_riders (135/135 tables granted; largest measured at ~433M rows), sel_geo
(144/144 EXTERNAL tables; ≥3.94e12 sampled-floor rows).
Exposure (recorded): schema-level SELECT(+MODIFY) grants far broader than any
operational need; full-precision GPS coordinates and route polylines resident in
analytical tables.
Remediation: restructure grants to least-privilege role-based access per consuming
team; move PII-class tables behind a governed catalog with row/column policies and
purpose-based access; mask or truncate GPS coordinates and simplify route polylines for
all non-operational consumers; provide aggregate-only views for analytics.
Detection: access audit over the three datasets (who read what, when); alerting on
bulk reads of PII-class tables and on any new grant at schema scope.

## D4 — Zendesk dangling CNAME — TAKEOVER WINDOW
Fingerprint: sha8 e1de03e8 (current-state record; original baseline sha8 1420af19)
Exposure (recorded): a support-domain CNAME points at a decommissioned third-party
support instance; claim-ability was demonstration-proven (first-signup-wins) and the
record remains dangling/unremediated.
Remediation: EITHER remove the stale DNS record OR re-claim the referenced target to
close the window; confirm the disposition with the SaaS provider; sweep DNS for other
dangling aliases of the same class.
Detection: monitor DNS changes and certificate-transparency logs for the affected
label until the record is removed or re-claimed.

## D5 — Mobile finding F1 (HIGH) — TOKEN STORAGE
Exposure (recorded): session JWT and username stored in plain SharedPreferences with
android:allowBackup="true" — recoverable from device backups and physical access.
Remediation: migrate token/identity storage to encrypted storage (e.g.
EncryptedSharedPreferences or an equivalent keystore-backed mechanism); set
allowBackup="false" for the sensitive preferences (or exclude them via backup rules);
invalidate and re-issue sessions after the storage migration ships.
Verification: confirm no plaintext token material in backups or preference files in
the next release build.

## D6 — Mobile finding F7 (HIGH) — NO TLS PINNING
Exposure (recorded): zero TLS certificate pinning across the Java layer and all 26
recorded native libraries — MITM/imposture exposure for API traffic on hostile
networks.
Remediation: introduce certificate pinning (SPKI-style) for primary API hosts, with a
remote-update/kill-switch strategy to avoid bricking; add certificate-transparency
monitoring for issued certificates covering the app's domains.
Verification: pinning coverage report across Java + native stacks in CI; CT monitor
alerts configured.

## D7 — Release-signing RSA-1024 certificate — CRYPTO ROTATION
Fingerprint: sha8 a75c6372 (fleet-shared, self-signed, release-signing)
Exposure (recorded): a 1024-bit RSA key shared across the app fleet — below current
minimums and shared blast radius.
Remediation: rotate to ≥2048-bit RSA (prefer 3072+) or ECDSA with per-app keys BEFORE
the next release cycle; plan signing-key migration so already-shipped releases verify
during transition.
Verification: new releases signed only with ≥2048-bit keys; old key retired from
signing infrastructure.

## D8 — braze_neveruse token corpus — DEAD-TOKEN RETIREMENT
Exposure (recorded): 72 third-party push/analytics tokens recorded under a
never-use-class label; 66 assessed live, 4 dead, 2 not-applicable.
Remediation: revoke/retire the 66 live tokens at the third-party provider (these are
victim-shaped/third-party credentials — retirement, not use); confirm the 4 dead and
2 N/A rows are removed from any active configuration.
Verification: provider console shows the corpus retired; no further live entries.

## D9 — Driver-licence PII corpus — INCIDENT-RESPONSE HANDLING
Exposure (recorded): 114,419 driver-licence records constitute a PII corpus requiring
IR treatment (recorded as LIST-only during the assessment; zero row values read into
any artifact).
Remediation (IR sequence): access audit over the corpus (who/when/what); retention
review against stated purpose; minimization or deletion of records beyond need;
encryption-at-rest confirmation; notify per applicable data-protection obligations if
the audit finds unauthorized access.
Verification: audit report closed; retention decision documented; corpus access now
least-privilege and logged.

---

## Cross-cutting guidance
- Sequencing rule: D1 audit-capture → D1 revocations → D2 PRIORITY six → D2 sweep →
  D3 grant restructuring → D4 DNS fix → D5–D7 mobile/crypto → D8/D9 hygiene.
- All fingerprints above are truncated (sha8) by engagement hygiene rule; full hashes
  reside in the sealed engagement register and lane receipts, available to the owner
  through the engagement's disclosure channel.
- This package contains no exploit details, no PII values, and no credential material.
