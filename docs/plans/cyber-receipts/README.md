# Cyber-suite wave receipts

Each builder writes `docs/plans/cyber-receipts/<wave-id>.md` **immediately** as a skeleton, then rewrites it at every milestone.

Required header:

```
# <wave-id> receipt
If it still reads this way, the unit died before measuring anything and no verdict here may be cited.
COVERAGE: <sections still UNKNOWN>
```

Parent merge blocks (exact `agents.json` JSON, parked companion, test-count deltas) belong in a `PARENT MERGE` section. Do not edit the registry yourself.

## Roster (2026-09-02)

| Wave | Receipt | Status |
|------|---------|--------|
| W-rails | `W-rails.md` | DONE — 69 hook tests |
| W-routing | `W-routing.md` | DONE — ioc/attack + VT/cve routes; Wave N executor tokens added by parent |
| W-corpus | `W-corpus.md` | DONE |
| W-blue | `W-blue.md` | DONE |
| W-dfir | `W-dfir.md` | DONE |
| W-purple | `W-purple.md` | DONE |
| W-0day | `W-0day.md` | DONE |
| W-cti | `W-cti.md` | DONE |
| W-cloud | `W-cloud.md` | DONE — prowler-mcp parent-merged DEFAULT-OFF |
| W-upgrades | `W-upgrades.md` | DONE |
| W-offensive | `W-offensive.md` | DONE — `metasploit-run` + `sliver-mcp` ENABLED (owner override) |

