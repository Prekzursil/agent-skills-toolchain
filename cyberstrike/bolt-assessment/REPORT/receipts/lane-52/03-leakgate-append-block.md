# LANE-52 · 03-LEAK-GATE — APPEND-BLOCK PRE-APPEND SCAN

- Date: 2026-10-03 · Phase 2 STEP 4 (scan executed BEFORE any register append; append blocked until clean)
- Mode: STRICT OFFLINE (local filesystem only; zero network, zero Databricks data-plane)
- Scanned object: `receipts/lane-52/02-register-append-2026-10-03.txt`
  - sha256: `b4df80d973e3ab921c5272f496bd2c244d5f774c7e86aef08a48a9765c1f8c02` · wc -l: 50 · bytes: 6581
- Method: python3 embedded battery (same class set as `receipts/lane-42/LEAK-GATE-AUDIT.md` and
  the lane-52/00 conventions), applied over the full staging text; sha8-only evidence policy;
  riders NEVER-ROTATE / NO-RE-BURN in force.
- Verbatim fidelity notes: lane-48 rows are the receipt-00 section 3.2 single-line rows
  (dual-source proof vs `receipts/lane-48/07-register-proposals.txt` sha256 276c2830…); lane-51
  rows are zero-touch wrapped blocks from `receipts/lane-51/register-proposals-2026-10-03.txt`
  (sha256 c1dd0dfa…), preserving register-native '- ' bullet + 2-space continuation style.

## Credential-shape battery (18 classes) — expected 0 hits

| # | Class | Representative regex | Hits |
|---|-------|----------------------|------|
| 1 | AWS access-key class AKIA + 16-char suffix | `AKIA[0-9A-Z]{16}` | 0 |
| 2 | AWS temporary class ASIA + 16-char suffix | `ASIA[0-9A-Z]{16}` | 0 |
| 3 | AWS class ABIA + 16-char suffix | `ABIA[0-9A-Z]{16}` | 0 |
| 4 | AWS class ACCA + 16-char suffix | `ACCA[0-9A-Z]{16}` | 0 |
| 5 | GitHub class ghp_ + 36-char suffix | `ghp_[A-Za-z0-9]{36}` | 0 |
| 6 | GitHub class gho_ + 36-char suffix | `gho_[A-Za-z0-9]{36}` | 0 |
| 7 | GitHub class ghu_ + 36-char suffix | `ghu_[A-Za-z0-9]{36}` | 0 |
| 8 | GitHub class ghs_ + 36-char suffix | `ghs_[A-Za-z0-9]{36}` | 0 |
| 9 | GitHub class ghr_ + 36-char suffix | `ghr_[A-Za-z0-9]{36}` | 0 |
| 10 | GitHub fine-grained prefix + 20 chars | `github_pat_[A-Za-z0-9_]{20,}` | 0 |
| 11 | Anthropic sk-ant prefix + 8 chars | `sk-ant-[A-Za-z0-9-]{8,}` | 0 |
| 12 | generic sk- prefix + 20 chars | `sk-[A-Za-z0-9]{20,}` | 0 |
| 13 | Slack token class xox- + 10 chars | `xox[baprs]-[A-Za-z0-9-]{10,}` | 0 |
| 14 | OpenAI dapi prefix + 20 chars | `dapi-[A-Za-z0-9-]{20,}` | 0 |
| 15 | drip connector class dy{2,} | `dy{2,}` | 0 |
| 16 | PEM private-key header | `-----BEGIN[A-Z0-9 ]*PRIVATE KEY` | 0 |
| 17 | authorization bearer shape | `Bearer [A-Za-z0-9]` | 0 |
| 18 | JWT two-segment shape | `eyJ[A-Za-z0-9_-]{10,}\.eyJ` | 0 |

## PII-value battery (6 classes) — expected 0 hits

| # | Class | Representative regex | Hits |
|---|-------|----------------------|------|
| 1 | e-mail at bolt.eu | `[A-Za-z0-9._%+-]+@bolt\.eu` | 0 |
| 2 | e-mail at taxify.eu | `[A-Za-z0-9._%+-]+@taxify\.eu` | 0 |
| 3 | e-mail at boltint.net | `[A-Za-z0-9._%+-]+@boltint\.net` | 0 |
| 4 | Estonian phone shape +37x | `\+37[0-9]{8}` | 0 |
| 5 | Danish phone shape +45x | `\+45[0-9]{8}` | 0 |
| 6 | GPS decimal coordinate pair | `-?[0-9]{2}\.[0-9]{6,},\s*-?[0-9]{1,2}\.[0-9]{6,}` | 0 |

## Result

TOTAL HITS: 0. VERDICT: CLEAN — append authorized to proceed (STEP 5).

Rider compliance of the append block: no credential material (NEVER-ROTATE), no live credential
re-verification (NO-RE-BURN — PAT references are sha8 fingerprints only), zero PII values,
evidence cited as receipts/findings paths only.
