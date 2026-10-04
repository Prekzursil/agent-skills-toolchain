# FINAL LEAK-GATE — receipts/lane-52 objects 00–08 — 2026-10-03

**Receipt:** `receipts/lane-52/09-leakgate-final-2026-10-03.md` · mode 0600
**Scanner:** `/tmp/lane52_leakgate_final.py` (strictly offline; reads local receipt files only)
**Policy:** sha8 fingerprints only — NEVER-ROTATE, NO-RE-BURN, zero credentials, zero PII.
**Command:** `python3 /tmp/lane52_leakgate_final.py`

## Battery — 24 classes (18 credential shapes + 6 PII shapes)

| Class | Description | Pattern |
|-------|-------------|---------|
| C01 | AWS access key id (AKIA + 16) | `AKIA[0-9A-Z]{16}` |
| C02 | AWS temporary key id (ASIA + 16) | `ASIA[0-9A-Z]{16}` |
| C03 | GitHub PAT ghp_ (36) | `ghp_[A-Za-z0-9]{36}` |
| C04 | GitHub OAuth token gho_ (36) | `gho_[A-Za-z0-9]{36}` |
| C05 | GitHub user-to-server ghu_ (36) | `ghu_[A-Za-z0-9]{36}` |
| C06 | GitHub app token ghs_ (36) | `ghs_[A-Za-z0-9]{36}` |
| C07 | GitHub refresh token ghr_ (36) | `ghr_[A-Za-z0-9]{36}` |
| C08 | GitHub fine-grained PAT github_pat_ | `github_pat_[A-Za-z0-9_]{22,}` |
| C09 | Anthropic key sk-ant- | `sk-ant-[A-Za-z0-9_\-]{16,}` |
| C10 | Generic sk- secret run (16+) | `\bsk-[A-Za-z0-9]{16,}` |
| C11 | Slack token xox[baprs]- | `xox[baprs]-[A-Za-z0-9\-]{10,}` |
| C12 | OpenAI key dapi- | `dapi-[A-Za-z0-9_\-]{20,}` |
| C13 | Other provider key dyy+ | `dyy\+[A-Za-z0-9_\-]{20,}` |
| C14 | Private key PEM header | `-----BEGIN [A-Z ]*PRIVATE KEY-----` |
| C15 | Bearer token literal | `Bearer\s+[A-Za-z0-9._+/\-]{16,}` |
| C16 | JWT two-segment eyJ..eyJ | `eyJ[A-Za-z0-9_\-]{6,}\.eyJ` |
| C17 | Google API key AIza (35) | `AIza[0-9A-Za-z_\-]{35}` |
| C18 | Secret assignment literal | `(?i)(password|passwd|secret|api_?key|token)\s*[:=]\s*[\"'][A-Za-z0-9+/=_\-]{16,}[\"']` |
| P01 | Email @bolt.eu | `[A-Za-z0-9._%+\-]+@bolt\.eu` |
| P02 | Email @taxify.eu | `[A-Za-z0-9._%+\-]+@taxify\.eu` |
| P03 | Email @boltint.net | `[A-Za-z0-9._%+\-]+@boltint\.net` |
| P04 | Phone +37x (EE/LV/LT, 8 digits) | `\+37[0-9](?:[\s\-]?\d){7}` |
| P05 | Phone +45 (DK, 8 digits) | `\+45(?:[\s\-]?\d){8}` |
| P06 | GPS decimal coordinate pair | `[\-]?\d{1,2}\.\d{4,}\s*,\s*[\-]?\d{1,3}\.\d{4,}` |

## Per-object results

| Object | sha256 | Bytes | Lines | Non-zero classes | Hits |
|--------|--------|-------|-------|------------------|------|
| `00-pre-verify-2026-10-03.md` | `5ff72d946a7892c92ed199dc4cfb529bbcf32287aa265dbbf98d7b1bc54eb901` | 12709 | 166 | none | 0 |
| `01-register-pre-append-copy.md` | `a3a12a55e17c00d31255c3349bd178265fced34c4f348f54a85edc0250ef9866` | 24332 | 235 | none | 0 |
| `02-register-append-2026-10-03.txt` | `b4df80d973e3ab921c5272f496bd2c244d5f774c7e86aef08a48a9765c1f8c02` | 6581 | 50 | none | 0 |
| `03-leakgate-append-block.md` | `93c1c061e252350751c1b6b700921a151be290204ee919558e76a500475d34b1` | 3322 | 55 | none | 0 |
| `04-tally-2026-10-03.md` | `33ff46918bda77fb9ce9c1a2d36c20d2915e3b62ade2c7f00ae4c52e868ae786` | 6438 | 82 | none | 0 |
| `05-phase2-proof.md` | `2582b7be35493a02cce53a5f9c62fe831a8c347cb2b30eb92c9257700ac95320` | 8318 | 80 | none | 0 |
| `06-leakgate-phase2.md` | `70281c6af48db4221ae22ec66e25181af2f756c55f09eafa900622b3359b0f4a` | 1941 | 36 | none | 0 |
| `07-exit-attestation-2026-10-03.md` | `b7b148dcc87ab3d07460addd520f49329b761073dcfe5d0b6a78f22827d87059` | 8119 | 66 | none | 0 |
| `08-budget-and-network-ledger-2026-10-03.md` | `a29c990a3a926f4ef394f972d7bd37d78033f3c354133a599237fbfddc4c9636` | 2574 | 36 | none | 0 |

## Totals and verdict

- Objects scanned: 9 of 9
- Classes evaluated per object: 24
- **TOTAL HITS: 0**
- **VERDICT: CLEAN** — zero credential shapes, zero PII shapes; sha8-only policy upheld across all lane-52 receipts.
