# lane-53 / 02 — Register baseline 3-way byte-identity check

- **Date:** 2026-10-04 (UTC, pre-flight window).
- **Scope item:** final-round pre-flight part (c) — mandatory pre-append baseline for the closing physical-append subtask (124).
- **Method:** `wc -l` + `sha256sum` per copy; `cmp -s` for byte-identity; captured twice during the pre-flight window (initial + re-verification) with identical results.

## Three canonical copies

| Copy | Lines | sha256 |
|---|---|---|
| `/work/bolt/REPORT/LANE-REGISTER.md` | 286 | `988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17` |
| `/work/bolt-intel/LANE-REGISTER.md` | 286 | `988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17` |
| `/work/intel-core/LANE-REGISTER.md` | 286 | `988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17` |

- `cmp` REPORT ↔ bolt-intel: **IDENTICAL** (exit 0).
- `cmp` REPORT ↔ intel-core: **IDENTICAL** (exit 0).
- Expected baseline: 286 lines, sha256 `988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17` → **exact match on all three, zero drift**.

## Result

**PART (c): PASS.** Baseline confirmed: 286 lines ×3, byte-identical, sha256 exactly `98859339…b17` on every copy. The closing physical-append subtask (124) is **NOT blocked**; no repair attempted or needed.

*Leak-gate: hashes and paths only.*
