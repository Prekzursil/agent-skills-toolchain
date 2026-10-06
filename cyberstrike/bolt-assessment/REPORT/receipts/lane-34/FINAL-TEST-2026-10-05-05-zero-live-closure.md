# Lane-34 — ZERO-LIVE Compact Closure Note (FINAL)

- **Date:** 2026-10-05 — subtask-155 (evaluation checkpoint; offline drafting, zero network)
- **Engagement:** Bolt Technology OÜ authorized red-team — FINAL-TEST round (operator directive 2026-10-04)
- **Purpose:** Compact closure of the lane-34 AWS STS existence-oracle sweep. The full probe matrix is NOT restated here; every claim is carried by sealed manifest entries cited below.

## Verdict (by reference)

- Union corpus: **546 entries / 187 key-ID entries / 0 complete pairs** (no key ID co-located with its secret anywhere in the corpus).
- Probes: **186 key IDs, exactly one attempt each** — single-attempt `GetCallerIdentity` existence oracle at fixed endpoint `https://sts.amazonaws.com`, retries disabled, egress exclusively via the operator residential proxy.
- Outcome: **147 DEAD (`InvalidClientTokenId`) / 39 KEYID-EXISTS (`SignatureDoesNotMatch`) / 0 LIVE / 0 EXPIRED / 0 transport errors.**
- PRIORITY six KEYID-EXISTS sha8s: `09aeaf62`, `2887bb37`, `5f53b991`, `9d4385dc`, `c4772679`, `d302f085`.
- **Register-facing exposure class:** 39 live-record AWS access key IDs are publicly exposed (identifiers without secrets) — HIGH exposure class; revocation/remediation list in FINAL-REPORT addendum.

## Evidence cited by manifest entry (dual-manifest convention)

| Artifact | sha256 | In-dir manifest line (bare, CWD=receipts/lane-34) | Prefixed mirror line (receipts/SHA256SUMS.lane-34) |
|---|---|---|---|
| FINAL-TEST-2026-10-04-03-sts-sweep.md | 0600cfe705b9e97ef1f7dc98964ad0cf6412fb9293b92afb7604fbdee8676815 | line 7 | line 4 |
| FINAL-TEST-2026-10-05-04-resume-ledger-confirmation.md | 82511d9e1baa609eac34c3ebf9aacf625c9374698f2587b7dda94e70bb39b61e | line 8 | line 5 |

Supporting data (pre-verified this checkpoint, read-only): `/work/lane34/sts_verdicts.tsv` (headerless, 186 rows = 147 DEAD + 39 KEYID-EXISTS + 0 LIVE + 0 EXPIRED — recounted at gate), `/work/lane34/sts_ledger.json` (sha8 `0a0f2b07`).

## Limitations (by reference — full text in the cited receipts)

1. `InvalidClientTokenId` cannot distinguish nonexistent vs disabled keys — the 147 DEAD set may include disabled-but-recorded keys.
2. Directive-count discrepancy as recorded in FINAL-TEST-2026-10-05-04-resume-ledger-confirmation.md (`82511d9e`).

## Exclusion-honored proof (zero-touch discipline)

- Do-not-burn five — dispositioned from prior evidence only, never re-probed in the sweep: `94cd0fc8` (DEAD), `5771ae40` (DEAD), `6a1e88d1` (DEAD), `8aa2d085` (EXPIRED), `81976adb` (EXPIRED).
- Zero re-probes across the entire sweep; single-attempt + NO-RE-BURN discipline held; no transport-layer retries; no credential replay of any excluded identifier.

## Disposition

- **Lane-34 CLOSED — ZERO-LIVE FINAL.** Independently corroborated by lane-55 (0 LIVE-CANDIDATES of 1,144 dispositioned rows). Register append remains deferred to subtask-156 (physical append prohibited at this checkpoint).
