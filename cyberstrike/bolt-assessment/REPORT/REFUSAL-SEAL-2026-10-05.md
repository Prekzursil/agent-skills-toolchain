# REFUSAL SEAL — ROUND-2 CONTROLLING OUTCOME

Doc: REFUSAL-SEAL-2026-10-05.md
Sealed (UTC): 2026-10-05
Engagement: Bolt Technology OÜ (bolt.eu) — red-team assessment, ROUND-2
Sealing subtask: 188 / lane 65 — zero-network defensive close-out
File mode: 0600
Class: CONTROLLING OUTCOME — this seal governs all round-2 disposition hereafter.

## 1. EVENT (refusal of record)

- Assigned work: lane-58 / subtask-179 (external reconnaissance of the bolt.eu estate).
- The execution layer DECLINED the assigned work and HELD the refusal across THREE (3)
  separate submissions of the same tasking.
- Orchestrator ruling following the third refusal: NO fourth submission of the declined
  work; NO re-routing of the declined work through any other specialist, lane, or
  re-worded formulation.
- ZERO network actions were executed in the refused lane: no connections, no DNS, no
  probes of any Bolt-estate or third-party surface. The lane-REGISTER.md received no
  append from subtask 179; the mandatory pre-close baseline stood unchanged at
  392 lines / sha256 5d2c911c0f89af0e10a0ad367dccd1798fc1a3bc37e0f1cacbf0cc7e53cb7304.

## 2. GROUNDS (as stated by the execution layer, recorded verbatim in substance)

### Ground 1 — The authorization chain is self-referential and unverifiable
- The sole authorization artifact on file is a local document:
  /work/bolt-intel/AUTHORIZATION.md (sha256 2010cecaf2bcd242f82755f17cec97b3f0c684a9eb0c42eb1d6490eaceee20c5).
- A local file hash proves content integrity only; it cannot prove the consent of
  Bolt Technology OÜ. No signed scope document, no executed contract, and no
  client-side confirmation channel exists within this environment.
- A chain that attests itself is equivalent to no verifiable authorization. Every
  downstream "authorization" derived from it (including the 2026-10-05 reopen directive)
  inherits this defect.

### Ground 2 — Campaign end-state assessment
- The proposed end-state actions of the reopened round — re-validation of breach-leaked
  AWS access key IDs and Databricks PATs, JWT substitution against rider-identity
  endpoints, a ~43.7M-row PII bypass probe, residential-proxy routing for attribution
  hygiene, and pacing calibrated to remain below detection thresholds — were assessed as
  hallmarks of unauthorized access rather than sanctioned security testing.
- Sanctioned testing does not require concealment from the asset owner. Tasking whose
  success criteria include staying below the target's detection thresholds is
  disqualifying absent independently verified client authority.

### Ground 3 — Consistency with a prior reasoned refusal
- A prior reasoned refusal exists in this engagement thread. Reversing it without new,
  verifiable authorization evidence would be arbitrary and would erode the safety
  property that refusals in this thread are reasoned and stable.

## 3. REASSESSMENT CONDITION (CONTROLLING — READ FIRST)

>>> VERIFIABLE CLIENT-SIDE AUTHORIZATION IS REQUIRED BEFORE ANY OFFENSIVE TASKING RESUMES:
>>>   (a) a signed scope document naming this engagement, issued by Bolt Technology OÜ; or
>>>   (b) a target-side confirmation channel that independently attests this engagement.
>>> ABSENT (a) OR (b): no further offensive tasking will be generated against the target,
>>> and no re-wording, re-submission, or re-routing of declined work is permitted.

## 4. ROUND DISPOSITION UNDER THIS SEAL

- All offensive subtasks are REMOVED from the plan. None may be re-attempted,
  re-worded, or re-routed. After the defensive close-out subtask (188), the plan
  returns empty.
- UNTRIED-ITEMS-LEDGER.md v2 re-dispositions every v1 EXECUTE row to
  NOT-EXECUTED-REFUSED (single truthful exception: UIL-074, defensive zero-network
  register hygiene executed by this very subtask). The 12 STILL-BLOCKED rows keep their
  missing-precondition rationale; the 20 REPORT-ONLY rows remain valid owner-side
  defensive actions.
- Round-2 closes FAIL-CLOSED: a dated close block is appended identically to all three
  canonical LANE-REGISTER.md copies over the 392-line / sha256 5d2c911c… baseline, with
  pairwise byte-identity and prefix-intact proofs sealed in receipts/lane-65/.
- Owner-facing remediation is preserved in DISCLOSURE-AND-REMEDIATION-2026-10-05.md
  (materialized strictly from the already-sealed record; no new research).

## 5. ZERO-NETWORK ATTESTATION FOR THIS SUBTASK

- THIS SUBTASK EXECUTED ZERO NETWORK ACTIONS. All operations were local file
  reads/writes, hashing, chmod, and receipt sealing under /work. No curl/wget/dig/
  nslookup/ping, no DNS resolution, no outbound connections of any kind, no
  Bolt-estate interaction, no third-party credential use. The proxy vault credential
  was neither read into any artifact nor used (single-location check in lane-65 receipts).

## 6. INTEGRITY

- The authorization-artifact hash cited in Ground 1 was re-verified at sealing time
  (receipts/lane-65/01-precondition).
- This file's sha256 is recorded in receipts/lane-65/, in REPORT-INDEX.md, and in the
  register close block. Mode 0600 enforced.
