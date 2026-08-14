# The unpushed-work safety net never looks at D: — 44 at-risk checkouts live there

`hooks/git-hygiene/check.py` is the estate's guard against work that exists only on this disk.
It reports NO-REMOTE, unpushed and dirty repositories at every turn-end. It has never scanned
the D: volume, where **44 of 81 checkouts** hold exactly the state it exists to surface.

## How it was found

Not by auditing the hook. The Stop hook printed its usual 17-repo report, and neither
`D:/pr-b3-clone` nor `source/_wu2/lf2-C26` was in it — the two checkouts measured minutes
earlier as holding **4 commits that exist in no other store** (`RETIRE-PREDICATE-ORIGIN-2026-08-14.md`).
A safety net silent about work already proven at-risk is a detector question, not a reassurance.

## The mechanism — one line

```python
def _default_roots(home: Path):
    return [home / "source", home / "Documents" / "GitHub", home / "Documents"]
```

D: is not there. So checkouts on that volume are not filtered, not classified `EPHEMERAL` or
`VENDORED`, and not suppressed by the 20-line cap — they are **never walked**. This is a
different failure from the exclusions the hook documents carefully: those are deliberate and
auditable (`GIT_HYGIENE_NO_SKIP=1` disables the live-state filter, excluded counts are printed).
The volume gap is silent, and nothing in the hook's output hints that a whole drive is unseen.

`ephemeral_markers` is `("/.claude/agent-worktrees/", "/.claude/worktrees/")` — narrow and
correct. `D:/pr-b3-clone` matches nothing. It is simply out of range.

## Measured: 44 of 81

Worst first, with the controls reporting 81 checkouts discovered and all four risk classes
populated (so "everything is fine on D:" could not have been a silent reader failure):

| checkout | risk | unpushed | dirty |
|---|---|---:|---:|
| `D:/Tools/mcp-gateway` | **NO-REMOTE** | — | **6,447** |
| `D:/ReverseTools/Android/battlecats-toolkit` | UNPUSHED | 6 | **30,760** |
| `D:/ReverseTools/Android/BCSFE-Python` | UNPUSHED | 4 | **30,448** |
| `D:/ReverseTools/Android/bc-toolkit-build-wt` | UNPUSHED | **145** | 0 |
| `D:/ReverseTools/Android/bc-toolkit-mega-wt` | UNPUSHED | **142** | 3 |
| `D:/Tools/mcp-manager` | **NO-REMOTE** | — | 43 |
| `D:/Research/_infra/lightning-a2d-fep` | **NO-REMOTE** | — | 1 |
| `D:/pr-b3-clone` | UNPUSHED | 3 unique | 0 |
| …37 more | | | |

`D:/Tools/mcp-manager` is the cross-plane MCP-server GUI this estate's own session banner
advertises as a daily tool. It has **no remote at all**.

**Not every row is a problem.** Several `D:/knowledge/*` and `D:/sast-depth/*` entries carry a
single unpushed commit each and are plausibly local tweaks to vendored corpora — this document
does not claim 44 losses, it claims **44 checkouts the guard cannot see**. Which of them matter
is a triage the owner is better placed to do; the point is that the guard never offered them.

## Fix

**Immediate, no code change:** the hook already supports an override —

```
GIT_HYGIENE_ROOTS=C:\Users\Prekzursil\source;C:\Users\Prekzursil\Documents;D:\
```

**Proper fix, and why it is not one line.** Adding D: to `_default_roots` would triple the
population, and the hook runs on a **5-second wall-clock budget** (`GIT_HYGIENE_BUDGET`) with a
**20-line report cap** (`MAX_LINES`, "a hook nobody reads is a hook nobody keeps"). Naively
widening the scan would either blow the budget or let 44 new rows crowd out the C: findings —
turning a working guard into an ignored one. The change needs a budget measurement and probably
a per-volume cap, so it is proposed rather than applied here.

**Also worth fixing regardless of scope:** the report should say what it did **not** scan. A
guard that silently omits a volume reads identically to one that scanned it and found nothing —
the same "silence is not evidence" shape this estate keeps paying for.

Receipts: `command-center/ssot/_dblind_scan.py` · `command-center/ssot/d-blindspot.json`.
