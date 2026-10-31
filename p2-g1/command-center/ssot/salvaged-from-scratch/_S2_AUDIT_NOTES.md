# SKILLS2 round-3 independent audit — MEASURED

COVERAGE: all four DoD items executed. Two minor sentence-scope overclaims found; zero blocking defects.

| claim | result |
|---|---|
| commit f1ce459e exists, 16 files, 0 foreign, 0 skill-tree files, reachable | CONFIRMED |
| all 16 artifacts Test-Path true; blob crlf=0; blob==disk; ruff 0.15.17 green | CONFIRMED |
| all 16 committed outputs reproduce BYTE-IDENTICAL on my re-run | CONFIRMED |
| DoD1 render bug diagnosed, budget-vs-parse separated | CONFIRMED + 5th independent sample (my own listing) |
| DoD2 vault dry-run: exit 0, nothing written, copied=0 needs_merge=403 | CONFIRMED |
| DoD3 union-merge proposal, 125 lines, both sides, NOT applied | CONFIRMED |
| DoD4 7/7 negative cases naming a sibling in 3 writable trees | CONFIRMED (my 1st matcher was too narrow — MY detector failure) |
| vault + skills.daily untouched by round 3 | CONFIRMED via mtime + guard census |
| no round-2 SKILLS2 verifier report on disk | CONFIRMED via repo-wide + scratch mtime sweep |

Overclaims: (1) ±440 correction scoped to "items 1 and 4" but the item-3 proposal also carries a
stale 115,478; (2) verifier-trace provenance mixes round-1 re-runs into the round-2 window.
