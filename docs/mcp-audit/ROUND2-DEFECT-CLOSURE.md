# MCPRESEARCH round 2 — defect closure ledger

Measured 2026-08-13, worktree `C:/Users/Prekzursil/source/ast-integrate`.
Companion to `MCP-CAPABILITY-AND-DISPOSITION.md` §11. One row per defect an independent
verifier CONFIRMED in round 1: reproduced first, then fixed, then red-proofed.

COVERAGE: all three confirmed defects reproduced BEFORE the fix, fixed, and each fix
proven to fire in its known-broken state. The round-1 measurements were independently
re-swept and agree 16/16. **NOT measured:** whether a fourth defect remains (the artifact
was not re-derived from scratch); the R1 wiring into `tools/mcpctl` and `tools/monitorcore`
(outside this lane's file scope); the `searxng` disable (a config mutation, recommended
only).

If it still reads this way, the unit died before measuring anything and no verdict here
may be cited. — *it does not; every line below carries executed output.*

---

## The three confirmed defects

| # | defect | class | status |
|---|---|---|---|
| D1 | `call_verified` contradicted its own legend inside `disposition.json` | self-contradiction in a machine-readable artifact | **CLOSED**, invariant + 4-mutation red-proof |
| D2 | "emits exactly the four fields mcpctl leaves null" — `rss_bytes` was not emitted | overclaim (value right, name missing) | **CLOSED**, claim now executed |
| D3 | repo-wide ruff count disclosed as 60; verifier measured 51 | disclosure accuracy (both correct, unstable metric) | **CLOSED**, replaced by a scoped timestamped census |

None of the three was a wrong measurement. All three were sentences wider than their
evidence — the estate's documented dominant failure mode, and the reason the fix for two of
them is *a machine check*, not better wording.

---

## D1 — the S4 self-contradiction

### Reproduced, permanently, in both directions (`_r2_reproduce.py`) — exit 0

The reproduction reads the round-1 **committed blob** (`git show b9dce830:…`), not the
working tree, so it keeps reproducing the defect after the fix lands instead of quietly
turning into a note that everything is fine.

```
== D1 call_verified self-contradiction ==
  BEFORE b9dce830: legend='real initialize+tools/list, or a real in-session too'...
  BEFORE contradictory rows (5): ['agent-mail','basic-memory','figma','github','huggingface']
  BEFORE call_verified=16 of 23, while the prose claimed 21
  AFTER  contradictory rows (0): []
  AFTER  call_verified=21 of 23
```

It fails closed in **both** directions: if BEFORE ever stops showing the defect, the
detector is broken and the run goes red rather than reporting success.

Both round-1 numbers were individually correct. The defect was that a legend and a field
had drifted apart, so the artifact asserted two incompatible things at once and a
downstream reader would get whichever one they happened to parse.

### Fixed

`rank_disposition.py` now emits S4 as three fields that cannot disagree:

* `call_verified` — the **union**, exactly what the legend advertises
* `handshake_verified` / `s4_executed` — the two halves, still separately visible
* `call_method` — `stdio-handshake` | `in-session-tool-call` | `null`

The legend is a module constant (`S4_LEGEND`), so the text that SHIPS and the text the
check READS are one object — two copies drifting apart is what caused the defect.
`decide()` branches on `handshake_verified`, not the union, so a row's evidence sentence
still names the probe that actually answered.

### Made unrepresentable, not merely corrected

`assert_signal_consistency()` aborts the run on three shapes: a `call_verified` that is not
the union; a `call_method` naming a method that produced no evidence; and a legend that
stops advertising both methods. This is the same discipline `assert_reversible()` already
applies to `REMOVE`.

### Red-proof (`_r2_redproof_invariants.py` part A) — exit 0

```
== PART A: assert_signal_consistency ==
  baseline (shipped semantics) -> silent  OK
  mutation round1-handshake-only      -> invariant fired  OK
  mutation verified-with-no-evidence  -> invariant fired  OK
  mutation wrong-call-method          -> invariant fired  OK
  mutation legend-narrowed            -> invariant fired  OK
```

`round1-handshake-only` is the literal round-1 computation. The invariant fires on it.

### After

```
rows 23 · call_verified 21 · contradictory [] · methods {stdio-handshake,
in-session-tool-call, None}
```

Dispositions unchanged: `DISABLE 1 / INVESTIGATE 2 / KEEP 20`. This was a disclosure fix,
and it must not have moved a verdict — it did not.

---

## D2 — "exactly the four fields"

### Reproduced, both directions

```
== D2 'exactly the four fields' overclaim ==
  mcpctl Liveness fields : ['last_error', 'pid', 'rss_bytes', 'tool_count']
  BEFORE missing by name : ['rss_bytes']      (round-1 blob b9dce830)
  AFTER  missing by name : []                 (capability-matrix-r2.json)
```

Three of four. The consequence was real, not cosmetic: an injection built from those keys
would have carried `rss_bytes=None` into every row — the exact "unmeasured renders as
nothing" hole `mcpctl.matrix.Liveness` documents itself as guarding against.

### Fixed

`process_memory()` emits `rss_bytes` alongside `working_set_bytes`. **The value was already
correct** — Windows exposes no RSS counter and `WorkingSetSize` is its documented analogue
(the mapping psutil uses for `Process.memory_info().rss` on nt). Only the NAME was missing,
so both are emitted and the provenance survives the alias. The re-sweep re-measured it for
real rather than back-filling the old artifact. `disposition.json` rows now also carry
`pid` + `rss_bytes`, so a row of the shipped table *is* an injectable snapshot.

### The claim is now executed, not asserted

`_r2_redproof_invariants.py` part B constructs `mcpctl.matrix.Liveness(**{f: row[f] ...})`
from the producer's own row keys and requires every field non-null on every verified row.

**Both states, measured:**

| state | result |
|---|---|
| round-1 matrix (`capability-matrix.json`) | **RED** — 16 rows report `['rss_bytes']` missing, exit 1 |
| round-2 matrix (`capability-matrix-r2.json`) | **GREEN** — 16/16 complete, exit 0 |
| mutation: delete `rss_bytes` from the green rows | **RED** — control fired |

The control shape matters. "Does `build_rows()` succeed" would pass under BOTH hypotheses,
because `Liveness` defaults every field to `None` and an empty snapshot builds happily —
that is the control-that-cannot-distinguish failure this estate keeps re-committing. The
discriminating assertion is that each of the four fields is **non-null**.

---

## D3 — the ruff disclosure

Round 1 disclosed 60 repo-wide offenders; the verifier measured 51 for the same claim.
**Neither was wrong.** Four readings of the same number:

| reading | count |
|---|---|
| round-1 build | 60 |
| round-1 verifier | 51 |
| round-2 open | 46 |
| round-2, 03:33:57Z | 27 |
| round-2, 03:41:06Z | 31 |
| round-2, 03:52:41Z | 37 |

Six readings, **60 → 51 → 46 → 27 → 31 → 37**, three of them inside a nineteen-minute
window of this one round. A dozen sibling lanes commit into this shared worktree while the
audit runs, so the repo-wide count has a half-life of minutes, and quoting it without a
timestamp manufactures a disagreement between two honest observers — which is exactly what
happened between the round-1 build and the round-1 verifier.

`ruff-census.json` is a **timestamped snapshot**, not a live figure: whatever is committed
records the moment it was taken, and re-running the script overwrites it with the current
reading. The stable, actionable number is `in_scope`, which has been **0** at every one of
those readings.

`_r2_ruff_census.py` replaces the number with a measurement: in-scope vs out-of-scope **by
owner**, UTC-stamped, written to `ruff-census.json`, with the exit code driven by the
in-scope count **alone**.

```
== ruff format --check census @ 2026-08-13T03:33:57+00:00 ==
  repo-wide would-reformat : 27   (MOVING TARGET)
  IN-SCOPE (this lane)     : 0  []
  out-of-scope by owner    : {'command-center/hook-audit': 8, 'command-center/grounding': 7,
                              'platform/lib': 5, 'docs/*probe*.py': 6, 'platform/routing': 1}
SUCCESS:ruff-census in_scope=0 repo_wide=27
```

Failing this lane's gate on a sibling's file would repeat the original error in the
opposite direction: a number whose scope does not match the claim.

---

## Two defects in my OWN round-2 instruments, caught and fixed

Consistent with round 1, where two of the three detector failures were self-inflicted.
Recorded because a fix pass that reports zero of its own mistakes is not credible.

| # | my instrument said | the contradiction | root cause |
|---|---|---|---|
| 1 | `_r2_redproof_invariants.py` with no arguments went RED after the fix landed | the same check passed when handed the r2 matrix explicitly | its default concatenated **both** matrices, so the frozen round-1 rows (which correctly lack `rss_bytes`) polluted the current-producer check. Default is now the current producer's output; the round-1 matrix is passed explicitly to see it go red on purpose. |
| 2 | `_r2_reproduce.py` reported `D1_contradictory_rows=0` and still printed `SUCCESS` | it was supposed to be *reproducing* a defect | v1 read the WORKING TREE, so regenerating `disposition.json` erased the very thing it existed to demonstrate, and its terminal marker was an `or` across two defects so one surviving detection masked the other. Rewritten to read the round-1 committed blob and to fail closed in both directions. |

Both are the same shape: a check whose PASS did not mean what its name implied.

---

## Corroboration the round-2 sweep bought for free

The re-sweep existed to measure `rss_bytes`, but it is also an independent re-measurement a
day later on a differently-loaded box. `_r2_corroborate.py` compares round 1 vs round 2 on
tool COUNT **and** the exact tool NAME set — names matter more, since two runs can agree on
24 while advertising different tools, which would silently invalidate the set arithmetic
behind the single DISABLE.

```
== corroboration over 16 verified servers ==
  control: all 16 rows carry names; renamed one tool in 'angr' -> disagreement reported? True
  cloud-hub 424/424 · search-hub 68/68 · paper-search 57/57 · chrome-devtools 29/29 ·
  playwright|-cdp|-extension 24/24 each · angr 14/14 · frida-mcp 13/13 · repomix 8/8 ·
  scholarly-access 8/8 · qlty 5/5 · searxng 4/4 · codex 2/2 · context7 2/2 ·
  claude-code-mcp 1/1
SUCCESS:r2-corroborate 16/16 agree on count AND names
```

The control is the load-bearing line: two runs with **missing** name lists would compare
equal (empty == empty) and print a confident agreement while measuring nothing. So the
script requires the sets to be non-empty, then renames one tool and requires the
disagreement to be reported.

`overlap_report.py` re-run on the fresh sweep reproduces all four pair verdicts exactly:
three playwright rails byte-identical at 24/24/0-unique (INVESTIGATE, **not** eligible —
identical is not strict containment), and `searxng` ⊂ `search-hub` 4/4 with 0 unique (the
single DISABLE).

---

## Observed while gating, NOT this lane's to fix: `.md` / `.json` blobs store CRLF

The blob gate checks CRLF on `.py` only, so the third round-2 commit (JSON + Markdown, no
Python) made it **fail closed** — correctly, there was nothing for it to lint. Checking the
other blobs by hand turned up CRLF, so I controlled it before calling it anything:

| blob | CRLF lines | authored by |
|---|---|---|
| `docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md` | 248 | this lane |
| `command-center/mcp-audit/ruff-census.json` | 28 | this lane |
| `docs/mcp-audit/MCP-FLEET-AUDIT.md` | 355 | the grounding lane |
| `README.md` | 328 | pre-existing |
| `AGENTS.md` | 112 | pre-existing |

`README.md` and `AGENTS.md` were never touched by this lane, so **CRLF in `.md`/`.json`
blobs is a repo-wide pre-existing condition, not something round 2 introduced** — and it is
not a reader artifact either: `git show` and `git cat-file` both report 248 on the same
file. `.gitattributes` pins only `*.sh eol=lf` and `*.ps1 eol=crlf`; `.md` and `.json` are
unpinned, so a Windows checkout commits whatever the working tree holds.

**Every `.py` blob this lane committed is 0 CRLF** (verified by the blob gate on both
Python-bearing commits), which is what the ruff/CI surface actually reads. Fixing the
`.md`/`.json` case means editing `.gitattributes` — a shared file, and a normalisation pass
that would rewrite thousands of lines across every lane. Reported for the orchestrator,
deliberately not done here. **UNVERIFIED:** whether any CI step is sensitive to `.md`/
`.json` line endings; settling experiment is a CI run over a deliberately LF-normalised
copy of one such file.

## Confidence

* **Almost certain (90-99%)** — each defect was reproduced before its fix and each fix has
  a control observed to fire in the known-broken state; the 16/16 corroboration (executed
  twice, controlled); `rss_bytes` now non-null on all 16 verified rows; in-scope ruff
  offenders = 0.
* **Uncertain (20-55%)** — that no FOURTH defect remains in this artifact. Three were found
  by a verifier and closed; I did not re-derive the artifact from scratch, and a
  self-review is not the settling experiment. **The settling experiment is another
  independent verify pass.**
* **Unchanged from round 1, still open** — the `mcpctl` precedence question (mounted-but-not
  `enabled` rows), the bytes-vs-tokens reconciliation with `impact.py`, the agent-mail
  8811/8812 port split, and whether the three playwright rails differ BEHAVIOURALLY (name
  identity is measured; behaviour is not, which is why they are INVESTIGATE).
* **Explicitly NOT claimed** — that CI is green. Two gates were verified over the committed
  blobs; the other ~23 CI steps were not run.
