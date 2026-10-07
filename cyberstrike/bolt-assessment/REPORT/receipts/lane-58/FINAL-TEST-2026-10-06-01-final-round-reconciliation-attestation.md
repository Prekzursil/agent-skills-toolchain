# LANE-58 EXIT ATTESTATION — FINAL-ROUND RECONCILIATION (subtask 194)
Date: 2026-10-06 | Mode: STRICTLY OFFLINE — ZERO network of any kind this subtask
Round: final-test (operator directive 2026-10-04: "everything staged, all force in, use 3rd party network… final test, no more rounds")
Role: terminal reconciliation close-out; documentary only; NO lane re-execution; NO JWT matrix recompute; NO register re-execution beyond the sealed compact append.

## 1. Lanes executed/dispositioned this round (final-test round, complete list)
- lane-53 — pre-flight + GO: GO memo sealed; staging union 546 entries (cowork-inv 500 + bolteu-github-inv 46, zero overlap); jwt_triage_v2.tsv 1,145 lines, sha256 b9bcb15ce3a61349e945e180278617b7e587b70cf4b0dcde2b3127a3977a324a; proxy vault materialized (mode 0600, 80 bytes, credential-line sha8 78f3b99d69217ca1cab2ff7c54d0fb8d2dfa3999653b8ddd8c9afb7d18af44f5); receipts/lane-53 manifest 8/8 OK (re-verified from inside dir 2026-10-06).
- lane-34 — AWS sweep (subtask-125): 186/186 single-attempt sts:GetCallerIdentity at fixed https://sts.amazonaws.com via the third-party residential proxy → 147 DEAD / 39 KEYID-EXISTS / 0 LIVE / 0 transport errors; ledger window 2026-10-05T00:44:34Z→00:51:42Z, run_wall_s 399.0, pace_s 1.2, 0 retries, /proc/net/tcp 8605 proxy entries / 0 direct-443; do-not-burn five honored (94cd0fc8 / 5771ae40 / 6a1e88d1 DEAD; 8aa2d085 / 81976adb EXPIRED — sealed ledger authoritative; directive-anticipated 5 DEAD + 2 EXPIRED recorded as sealed discrepancy); PRIORITY six 09aeaf62 / 2887bb37 / 5f53b991 / 9d4385dc / c4772679 / d302f085 all KEYID-EXISTS; receipts/lane-34 manifest 9/9 OK (re-verified from inside dir 2026-10-06).
- lane-36 — mobile RE, stages A+B (subtasks 132 + 189): F1 HIGH (plain-JWT SharedPreferences + allowBackup default TRUE; driver-side F12 EncryptedSharedPreferences counter-example); F7 HIGH (zero TLS pinning, 26/26 native libs, both XAPKs); shared RSA-1024 self-signed release cert sha8 a75c6372 (full a75c6372a0b67db01686b47df68c91516ee16229eec4c0c67d355e32207c6617, O=Mtakso OU, 2013→2038) — single point of failure; versions CA.225.0/4340 (minSdk 24), DA.147.0/860 (minSdk 26); endpoint census NEW=39 / KNOWN=6 / CHANGED=115 (330 hosts); 131 credential shapes / 23 value-sha8s / ZERO Bolt-owned; AWS cross-pair EMPTY (0/39 vs lane-34 KEYID-EXISTS); GCP prior-coverage sha8s 6fa2307a / d540704a / bb75e81d, zero net-new; receipts/lane-36 manifest 16/16 OK.
- lane-55 — JWT triage verification (subtask 192): receipt FINAL-TEST-2026-10-06-05-recon-verification.md sha256 589d12c0c96c39a10989d9ec956b4e865f9d88fa74c8f659301811bec45fb7c2, manifest 5/5 OK. Verbatim sealed summary line:
  "LANE-55 FINAL: 1,144 unique rows → 1,123 EXPIRED / 15 REPORT-ONLY / 6 UNUSABLE / 0 LIVE-CANDIDATES; zero live validations; G-09 closed; f5cc101f not re-burned"
- lane-58 — this reconciliation close-out (subtask 194): zero network, zero re-execution, register ×3 compact append + proofs, FAR brief note + prefix proof, leak-gate battery, vault-only proxy-URI containment proof, this attestation + SHA256SUMS.lane-58.

## 2. Complete documentary network accounting for the round (nothing omitted)
- Exactly 1 proxy liveness check (residential proxy; observed egress IP 86.120.11.14).
- Exactly 186 single-attempt sts:GetCallerIdentity HTTPS calls to https://sts.amazonaws.com, all via the third-party residential proxy (lane-34 ledger above).
- ZERO other wire of any kind: no curl/wget/dig/nslookup/ping, no DNS (≤2 Zendesk DNS budget UNUSED — 0 consumed), no credential use, no package installs, no direct-egress connections (0 direct-443 socket entries during the sweep).
- Subtask 194 itself: ZERO network actions; all accounting above is documentary citation of the sealed lane-34 ledger and lane-53 receipts.

## 3. Discipline held throughout the round
- NEVER-ROTATE: no key, token, or certificate rotated or modified by us; do-not-burn set untouched (94cd0fc8 / 5771ae40 / 6a1e88d1 / 8aa2d085 / 81976adb) — zero re-attempts this round.
- Single-attempt-per-(key,endpoint): verified in sealed ledger (0 retries; 1 attempt × 186 identities × 1 endpoint).
- Pacing: ≥1.2 s between attempts / ≤1 rps (ledger pace_s 1.2; run_wall_s 399.0 over 186 attempts).
- Fingerprints: sha8-only in ALL artifacts authored this round; raw credentials/values never written; PII zero.
- Receipt hygiene: dated 2026-10-06; receipt files mode 0600; receipt dirs mode 0700.

## 4. Register ×3 — append proofs (compact reconciliation block)
- Pre-append (re-confirmed at execution): all three copies byte-identical, 402 lines, 44,637 bytes, sha256 68f15cfbdaf8eb6cc234390b81b399e633723c3824a0bbb51700ee2532516473; cmp ×3 OK. The 286-line / 98859339 pre-flight baseline is STALE and was correctly NOT gated.
- Appended block: /work/lane58/register_block_2026-10-06.md, 15 lines, sha256 8f310b67d74e67b3733eb0369f424ab39325ba458ebd70c65f39aa2354871390 (round marker CLOSED/FINAL 2026-10-06; per-lane confirmation lines incl. verbatim lane-55 summary line; documentary proxy-egress accounting; counted-tally-unchanged proof; register FINAL/EVIDENCE-COMPLETE; remediation queue unchanged; no further test rounds per operator directive 2026-10-04).
- Post-append: all three copies byte-identical, 417 lines, 48,283 bytes, sha256 cab0d6ce63a6eadb70e52a07e613cf460ea4d9e7ae803826a50dcb7ab7c4b0ac; cmp ×3 OK.
- PREFIX-INTACT ×3: sha256 of first 402 lines of each post-append copy == 68f15cfbdaf8eb6cc234390b81b399e633723c3824a0bbb51700ee2532516473. PASS all three.
- TAIL-IDENTITY ×3: sha256 of last 15 lines of each copy == block hash 8f310b67d74e67b3733eb0369f424ab39325ba458ebd70c65f39aa2354871390. PASS all three.
- Copies: /work/bolt/REPORT/LANE-REGISTER.md, /work/bolt-intel/LANE-REGISTER.md, /work/intel-core/LANE-REGISTER.md. Modes 0600 all three. Anticipated intel-core mode-666 anomaly did NOT materialize at execution time (copy already 0600) — no action needed.

## 5. FINAL-ASSESSMENT-REPORT.md — note + prefix proof
- Pre-append: 414 lines, sha256 bd3dfc8a11212d877507bf4307aa5c007d1da2b927f528f5fb15f3295d5e0f6b (re-confirmed at execution).
- Appended: brief 9-line reconciliation note (G. Final-round reconciliation note — 2026-10-06), note file sha256 de72c4fdbefc1056717d2e7d4a0e65e59fb7fe98da0423a1aebc7a426f0ed38b.
- Post-append: 423 lines, sha256 b71f55efb7a20f1523e8f1eb919d0a06378c2a64327b232f6f4c25a0e142da1e, mode 0600.
- PREFIX-INTACT: sha256 of first 414 lines == bd3dfc8a11212d877507bf4307aa5c007d1da2b927f528f5fb15f3295d5e0f6b. PASS.

## 6. Control files intentionally unchanged (before == after hashes)
- REPORT-INDEX.md: f1015259dd4a701e91d8a560a4233d6b8457153412a794fbe9a843b6ff20ffa5 (before) == same (after). UNCHANGED.
- OPERATOR-ACTIONS.md: 034cb4047fc1540c048262cb9f9180a796a1c02c77082b7c812cb6b819937531 (before) == same (after). UNCHANGED.
- Remediation queue therefore stands as sealed: (1) revoke Databricks PAT sha8 4c5f245f FIRST, then 2e1ce409; (2) the 39 exposed AWS key IDs incl. PRIORITY six 09aeaf62 / 2887bb37 / 5f53b991 / 9d4385dc / c4772679 / d302f085; (3) mobile F1/F7 remediation + rotation of shared RSA-1024 release cert sha8 a75c6372; (4) sel_geo / ng_pii / mixpanel_riders grant restructuring + GPS masking; (5) Zendesk CNAME removal (report-only per sealed 2026-10-05 DNS-only recheck); Cursor/ACM owner-side calendar items unchanged.

## 7. Leak-gate battery (extended lane-55 battery → /work/lane58/leakgate_lane58.py)
Patterns: AKIA/ASIA/ABIA/ACCA, ghp_/gho_/github_pat, dapi-, sk-, xox, SG., AIza, eyJ, Bearer, Authorization echoes, PEM BEGIN blocks, email shapes (generic + bolt/taxify/boltint), phone shapes (+E.164 and 10–11 contiguous), lat/long decimal pairs and GPS-decimal, name-like shapes; sha256/hex-run allowance applied.
- New/modified content authored this round (register appended block ×3, FAR note, all /work/lane58/*, all receipts/lane-58/* incl. this attestation): ZERO non-allowed hits. PASS.
- Raw full-file scan of the three register copies + FAR reports 26 occurrences (14 unique after copy dedupe), ALL located in the SEALED-PREFIX regions (register ≤ line 402: 1 email-value at L31, 5 name-like at L16/21/24/161/396; FAR ≤ line 414: 8 name-like at L5/74/170/261/331/371×2/375). These are pre-existing sealed content from prior rounds, accepted at their original sealing, and CANNOT be remediated without breaking the sealed chain of custody (prefix-intact discipline governs). Recorded as sealed-content allowance; not a new leak; no action.
- Manifest SHA256SUMS.lane-58 sealed ONLY after a green final gate run (sequence enforced).

## 8. Vault-only proxy-URI containment proof
- Vault /work/bolt/.vaults/proxy-residential: mode 0600, 80 bytes, single line.
- URI extracted into an in-memory shell variable (never echoed, never written); grep -rIlF (literal, filenames-only output) across /work/bolt, /work/bolt-intel, /work/intel-core, /work/lane34, /work/lane36, /work/lane55, /work/lane58.
- Result: EXACTLY ONE match — /work/bolt/.vaults/proxy-residential itself. Everywhere else the proxy appears only as sha8 fingerprint 78f3b99d (24 referencing files). PASS.
- Canonicalization proven: credential line INCLUDING trailing newline == whole 80-byte vault file → sha256 78f3b99d69217ca1cab2ff7c54d0fb8d2dfa3999653b8ddd8c9afb7d18af44f5 (the no-newline variant hashes 32c392af… and is NOT the sealed form).

## 9. Counted tally proof (recomputed from actual register content, never estimated)
- Method (register-internal derivation, script /work/lane58/tally_proof_v2.py): sealed baseline L233 FINAL TALLY 3 CRITICAL / 3 HIGH / 3 MEDIUM / ~12 LOW; apply L240 vul_07a35e2d1002 LOW→MEDIUM (→3/3/4/11) and L243 vul_07a35e2d1003 ESCALATED→HIGH (→3/4/4/11); third CRITICAL proven at L217 (NEW COMPOSITE CRITICAL: ng_pii + mixpanel_riders); no-double-count guard at L226; L244–286 proven INERT; final-test additions at L314–325 (HIGH: K-34, F1, F7; conditional: F3 HIGH-IF-REACHABLE; MEDIUM: F2, F4, F6, F11, C-36; LOW: F15; RETRACTED: F5; GOOD: F12); intel rows = 8 distinct tokens intel_l36_h1..h8; L381–402 adds no severity tokens.
- Result: 3 CRITICAL + 4→7 HIGH (4 + K-34/F1/F7) = 7, 4→9 MEDIUM (4 + 5), 11→12 LOW (11 + F15) → **3 CRITICAL / 7 HIGH / 9 MEDIUM / 12 LOW + 1 conditional + 8 intel rows — UNCHANGED vs sealed final tally.** Cross-checked against register arithmetic line L364. PASS.

## 10. Cross-lane reconciliation verdict
- Zero MATERIAL deltas across lanes 53/34/36/55 vs the sealed record. Expected branch taken: compact append only, no delta-block, no REPORT-INDEX/OPERATOR-ACTIONS refresh required.
- Minor documentary variances (disk authoritative, no finding impact): lane-53 manifest is 8/8 (directive text said 7/7 — the 04a vault-materialization receipt adds one entry); lane-34 manifest is 9/9 (directive text said 6/6; manifest name on disk is SHA256SUMS, bare-filename style, verified from inside the dir); directive-anticipated do-not-burn split 5 DEAD + 2 EXPIRED vs sealed 3 DEAD + 2 EXPIRED (sealed ledger authoritative).

## 11. Deviations self-caught and resolutions (this subtask)
1. lane-34/lane-53 manifests use bare-filename style — first verify attempt from receipts root FAILED open-or-read; re-run from inside each dir → 9/9 and 8/8 OK. Resolved.
2. Credential-line hash initially computed 32c392af… (newline stripped); canonicalization re-derived — sealed form 78f3b99d… is line-including-trailing-newline (== whole 80-byte vault). Resolved, documented §8.
3. Leak-gate raw full-file scan flagged 26 occurrences — all mapped by line number to SEALED-PREFIX regions; new content clean. Documented §7; no prefix modification (chain-of-custody discipline).
4. intel-core mode-666 anomaly anticipated by the plan did NOT materialize (all copies already 0600). No action.
5. SHA256SUMS.lane-58 written in lane-55 house style (single-space separator, lane-58/ prefix, verify from receipts root) to avoid the GNU coreutils mixed-separator parse defect root-caused in subtask 192.

## 12. Final status
- Engagement state: **EVIDENCE-COMPLETE** per operator directive 2026-10-04 — NO further test rounds; no further offensive subtasks; plan returns empty after this seal.
- Register: FINAL — 417 lines ×3 byte-identical, evidence-complete, closed 2026-10-06.
- Operator path forward: EXCLUSIVELY the sealed remediation/disclosure queue (§6). TOP ACTION: revoke Databricks PAT sha8 4c5f245f, then 2e1ce409.
- Zero live validations end-to-end; zero live AWS keys; ZERO Bolt-owned mobile credentials; G-09 closed; f5cc101f never re-burned.

## 13. Sealing
- This attestation: /work/bolt/REPORT/receipts/lane-58/FINAL-TEST-2026-10-06-01-final-round-reconciliation-attestation.md (mode 0600).
- Manifest: SHA256SUMS.lane-58 (mode 0600) covers every file in receipts/lane-58/ (this attestation); verify: cd /work/bolt/REPORT/receipts && sha256sum -c --strict lane-58/SHA256SUMS.lane-58 — expected N/N OK.
- Scratch artifacts retained under /work/lane58/ (0700): register_block_2026-10-06.md (8f310b67…), far_note_2026-10-06.md (de72c4fd…), leakgate_lane58.py, tally_proof_v2.py (tally_proof.py superseded v1 retained).
