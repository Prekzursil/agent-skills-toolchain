# Lane-56 Receipt 03 — COUNTED Severity Tally (counted from the drafted register append-block text; never estimated)

- Date: 2026-10-05 (subtask-155). Counting source: `/work/lane56/drafts/register_append_block_DRAFT.md`, sha256 1672258af0e245d10aca48413163da3ee1c68dcd6cc5235ca5284e9d32617f02 (0600; sealed verbatim copy embedded in receipt 04).
- Method: exact text parse of the draft's finding table severity column (field extraction with whitespace stripped; tokens matched exactly), plus exact token count of `intel_l36_h*` row IDs. No estimates; counts reproduced below with the command.

## Enumerated per-item count table (12 finding rows + intel)

| # | Item | Counted as | Rationale |
|---|------|-----------|-----------|
| 1 | K-34 — 39 live-record AWS key IDs publicly exposed (identifiers without secrets) | HIGH (1) | ONE consolidated exposure finding for the 39-key-ID class + remediation row (single class, not 39 findings) |
| 2 | F1 — client JWT + username in plain SharedPreferences; allowBackup=TRUE | HIGH (1) | stage-B finding |
| 3 | F7 — zero TLS pinning (Java + 26 native libs); user-CA MITM viable | HIGH (1) | stage-B finding |
| 4 | F3 — VerificationWebView file/universal-access flags; dead-code candidate | HIGH-IF-REACHABLE (1, conditional class) | conditional on reachability; counted in its OWN conditional class and NOT summed into unconditional HIGH (conservative: reachability unproven — dead-code candidate) |
| 5 | F2 — exported CrossAppLoginService (allowlist mitigation present) | MEDIUM (1) | |
| 6 | F4 — PlainWebView without allowlist | MEDIUM (1) | |
| 7 | F6 — boltprelive:// pre-prod scheme in production | MEDIUM (1) | |
| 8 | F11 — root/tamper detection dead code | MEDIUM (1) | |
| 9 | C-36 — shared self-signed RSA-1024 release cert (a75c6372) fleet-wide | MEDIUM (1) | distinct cert-management finding; chains with F7 but counted separately |
| 10 | F15 — two Mixpanel tokens (e6c777a0, 696d9c16) catalog-only | LOW (1) | |
| 11 | F5 — stage-A wildcard-intent-filter claim | RETRACTED (0 — transparency note) | retraction recorded transparently; NO severity assigned; NOT counted |
| 12 | F12 — driver EncryptedSharedPreferences; allowBackup=FALSE | GOOD (0 — positive control) | NOT counted |
| — | intel_l36_h1–h8 census rows (12 GENUINELY-NEW hosts) | INTEL (8) | informational intel rows, counted as intel, SEPARATE from vulnerability severity |
| — | lane-55 drift rows + 15 REPORT-ONLY + 6 UNUSABLE | 0 | no new Bolt-estate vulnerability severity (drift is temporal expiry; REPORT-ONLY is victim-shaped third-party material) |

## Mechanical count output (from the draft file)

```text
      1 GOOD
      3 HIGH
      1 HIGH-IF-REACHABLE
      1 LOW
      5 MEDIUM
      1 RETRACTED
intel rows (distinct intel_l36_h tokens): 8
```

Reproduction command (exact severity-column parse; header/separator rows excluded by exact token match):

```sh
awk -F'|' '/^\|/ { sev=$(NF-1); gsub(/[ \t]/,"",sev);
  if (sev=="HIGH"||sev=="MEDIUM"||sev=="LOW"||sev=="HIGH-IF-REACHABLE"||sev=="RETRACTED"||sev=="GOOD") print sev }' \
  /work/lane56/drafts/register_append_block_DRAFT.md | sort | uniq -c
```

## Counted additions and cumulative arithmetic (explicit)

- Counted additions in this block: CRITICAL +0; HIGH +3 (K-34, F1, F7); MEDIUM +5 (F2, F4, F6, F11, C-36); LOW +1 (F15). Conditional: +1 (F3, HIGH-IF-REACHABLE — own class, not summed into HIGH). Intel: +8 (intel_l36_h1–h8). Not counted: F5 RETRACTED, F12 GOOD.
- Baseline cumulative register tally: 3 CRITICAL / 4 HIGH / 4 MEDIUM / 11 LOW.
- NEW cumulative totals:
  - CRITICAL: 3 + 0 = **3**
  - HIGH: 4 + 3 = **7**
  - MEDIUM: 4 + 5 = **9**
  - LOW: 11 + 1 = **12**
  - Conditional class (HIGH-IF-REACHABLE): **1** (tracked separately, never merged into HIGH)
  - Informational intel rows: **8**
- Register-facing tally line (verbatim): baseline 3/4/4/11 + 0/3/5/1 = **3 CRITICAL / 7 HIGH / 9 MEDIUM / 12 LOW** (+1 conditional, +8 intel).

## Treatment rules applied (as directed)

- F3 counted in its own conditional class (HIGH-IF-REACHABLE), NOT into unconditional HIGH — reachability unproven (dead-code candidate); stated explicitly here and in the register block.
- F5 retraction = transparency note, NO severity, NOT counted.
- F12 GOOD = positive control, NOT counted.
- intel_l36_h1–h8 = informational intel rows counted as intel, separate from vulnerability severity.
- lane-55 drift + REPORT-ONLY rows = no new Bolt-estate vulnerability severity.
- The 39 exposed key IDs = ONE consolidated HIGH exposure finding (K-34) + remediation row, not 39 individual findings.
