# RULERESEARCH — BUILD lane, round 2

STATUS: complete and measured. Every number below was produced by a command in this round,
except the two committed receipts named in §2, which predate it and are what the correction
rests on.

COVERAGE: measured — the refuted claim and its provenance, the two-world re-measurement, the
mechanism, the change and its two levels of equivalence proof, the controls, and DoD. Declared
NOT measured, inline where it matters: the other contradictions of DoD-3, the runner execution
of the workflow, and the exact speed multiplier (a band is given instead).

## 1. What round 1 got wrong

A verifier re-executed BUILD-R1's gate table and REFUTED one cell:

> `r2_pathrefs.py --self-test` — **rc=0, 2.8 s**, inside a six-row table summing to 9.4 s.

Measured by the verifier on this box against the real `~/.claude`: **235.4 s, 124.8 s,
116.1 s**. The cell is off by 40-80x and the six-row sum by 15-25x.

**The verifier is right about the number, and the shipped code was not defective.** Every exit
code in that table was correct then and is correct now. The defect is in the SENTENCE — more
precisely in a column header — which is the dominant defect shape in this program.

## 2. Provenance: a two-world column with no world label

Both numbers are real and both were already in committed receipts. They come from DIFFERENT
environments and were merged into one unlabelled `wall` column:

| receipt | world | rows it produced |
|---|---|---|
| `_b3_portability.win-bare-nohome.json` | HOME redirected to an **empty temp dir**; `~/.claude` absent (the runner's world) | `rule_audit --self-test` 1.2 · **`r2_pathrefs --self-test` 2.8** · `r2_control_count_gate` 1.6 · `r2_failclosed_mutation` 3.1 · `r4_receipt_argv_gate` 0.5 · `r4_credential_rule_gate` 0.2 · `rule_audit` bare 1.3 · `lazy_predict` 0.7 · `r2_pathrefs` bare 3.3 |
| `_b2_slowgate_probe.json` | **real HOME**, this box | `r2_pathrefs` bare 110.5 · `r3_corpus_parity_gate` 89.0 |

Eight rows from the first file, two from the second, one column, no label — and
`RULE-AUDIT-INTEGRATE.md` headed it **"rc (this box)"**, attributing the redirected-HOME rows to
a machine that never produced them. The R1 report then used that column to argue "the timeouts
were slow, not hung", where the two slow rows came from the other world.

The refuted wording is preserved in both documents with the correction beside it, per the
lane's own rule that an overclaim is recorded rather than deleted.

## 3. Two-world re-measurement, one clock (`_b10_gate_timing.py --tag before`)

An independent third instrument, on this box, same session:

| invocation | real `~/.claude` | `~/.claude` absent |
|---|---|---|
| `r2_pathrefs.py --self-test` | **142.9 s · 97.9 s · 210.1 s** (rc=0) | **2.6 s · 3.5 s** (rc=0) |

So the corrected sentence predicts BOTH numbers and both were reproduced: the published 2.8 s
is right for the world `_b3` measured and wrong for the world it was published under. Six
real-HOME measurements now exist across two instruments (mine 97.9-210.1, the verifier's
116.1-235.4) and they agree.

**A wall time on this box is a range, not a point.** The same gate measured 97.9 s and 210.1 s
within one session — a 2.1x spread from file-cache warmth and sibling load. Any future citation
of these numbers must carry the range and the world.

## 4. Mechanism, measured rather than argued

`r2_pathrefs.classify()` falls back to `in_claude_home(name)`, which walked the seven
`HOME_SEARCH_DIRS` subtrees **per distinct unresolved basename**, sharing nothing between names:

| measurement (real HOME) | value |
|---|---|
| one absent-name lookup, all 7 dirs | **31.06 s** (`plugins` alone 29.8 s; `skills` 1.05; the other five ≤0.21) |
| `in_claude_home` on an absent name | 37.39 s |
| `in_claude_home` on a present-but-late name | 33.59 s |
| `basename_index()` (the whole repo) | 2.36 s / 14,193 distinct names / 21,346 files |

`--self-test` resolves three distinct absent names, so ~3 × 31 s ≈ 93 s of walking — which is
the 98-210 s observed, and the entire 60x gap between the two worlds (with HOME redirected
those roots do not exist, every walk short-circuits, and the same run is 2.6 s).

The property worth naming: cost was **O(unresolved names × tree)**, so the sweep was slowest
exactly when it had the most to report.

## 5. Change: one shared index instead of a walk per name

`r2_pathrefs.in_claude_home()` now consults a `home_index()` built by ONE `os.walk` of the same
seven subtrees, instead of walking them again for every name. A name carrying a glob
metacharacter keeps the original per-name `rglob`, because there `rglob` is a PATTERN match and
set membership is not.

| measurement, real `~/.claude` | before | after |
|---|---|---|
| `r2_pathrefs.py --self-test` | 97.9 · 142.9 · 210.1 s | 23.6 · 20.1 · 24.8 s — **but 134.2 s** in the final `ci_gate` run |
| `r2_pathrefs.py` bare (the real 254-file sweep) | 110.5 s (`_b2_slowgate_probe.json`) | 23.1 s |
| `ci_gate.py`, all six gates | 98.3 s | 38.1 s |
| **control** — same gate, `~/.claude` ABSENT | 2.6 · 3.5 s | 2.8 · 3.5 s |

**NO WALL-CLOCK SPEEDUP IS CLAIMED, and I am recording why I nearly claimed one.** This section
first read "at least 4x", from the least favourable pairing of the two columns above. Then the
final verification run measured the *indexed* self-test at **134.2 s** — worse than the *before*
column's best (97.9 s). Wall time on this box is dominated by page-cache state and sibling load
and swings ~6x on the same command, so any before/after pairing measured minutes apart, in
either direction, is noise dressed as a result. A claim my own next command refutes is an
overclaim; it is corrected here rather than deleted, because that is the failure this round
exists to fix.

What IS established, and it is not a timing claim:

- **Traversal count**, measured per lookup by `_b11` in a single interleaved session: the first
  lookup builds the index, and every lookup after it costs **0.0 s**, against 23.4-55.1 s each
  for the legacy walk. N full traversals became 1.
- **The one case that gets worse**: a name found EARLY used to short-circuit at 0.0 s and now
  pays the whole index build. If a run makes exactly one lookup and it hits in `plugins`, the
  change is a straight loss. It is a win from ~2-3 lookups upward; the self-test and the real
  sweep each make 3.
- Within `_b11`'s own session — the closest thing here to an interleaved A/B — three lookups
  cost 115.5 s legacy against 81.0 s indexed, i.e. **~1.4x**, with the index paying the coldest
  slot. That is the most defensible number in this document, and it is far short of 4x.

**Settling experiment**, not run: alternate the pre-change and post-change gate A/B/A/B in one
session from a `git show HEAD~:docs/rule-audit/r2_pathrefs.py` twin. It needs the twin to sit in
this directory to keep `REPO = parents[2]` valid, which would put a duplicate gate in the CI
inventory — so it is named, not shipped.

**Equivalence — the part that decides whether the change was allowed at all**, at two levels:

- *function*: `_b11_home_index_equivalence.py` holds the verbatim pre-change body and requires it
  to agree with the current one — 5/5 names agree (present-early, present-late, absent ×2,
  glob-metacharacter), `mismatches: []`, and the comparator control proves it can report a
  mismatch.
- *gate*: the bare sweep's terminal marker is byte-identical to the committed pre-change receipt
  — `FAILED:r2_pathrefs scanned=254 unwaived_path_claims=0 waived=3 known_defects=1 still live
  and tracked (no NEW finding; rc=2 distinguishes this from rc=1)`, rc=2 — and `--self-test`
  still passes its 6 gate-level states.

A function-level proof alone would not have been enough: it shows five names agree, not that the
254-file sweep still reports the same findings.

## 6. Both-states controls

| control | broken state | good state |
|---|---|---|
| `ci_gate --self-test`, all 12 pure predicates | each FIRES | each SILENT — rc=0 |
| `_b11` legacy-vs-current on 5 names (early / late / absent ×2 / glob-metachar) | comparator control: an inverted implementation IS reported as a mismatch | 5/5 agree, `mismatches: []` |
| `_b10` parts-vs-whole coherence | a world mismatch lands at ratio ~0.04 or ~60 | in-world runs land inside the 0.25-4.0 band |

**A control I had to widen, disclosed rather than quietly retuned.** `_b10`'s first coherence
band was 0.75-1.6 and the `before` run measured ratio 0.45, flagging incoherent. The cause was
ordinary variance (97.9 vs 210.1 s on the dominant gate), not a world mismatch — so as written
it could not distinguish its two hypotheses, which is the defect class this lane documents. The
band is now 0.25-4.0: it tolerates 4x noise and still fires an order of magnitude before a 60x
world mismatch. The `before` receipt was produced under the old band and its `coherent: false`
should be read as "noisy", not as a finding.

**An optimisation that lost, kept in the record.** The first index built with
`Path.rglob("*")` took 110.5 s — MORE than the 31 s single lookup it replaced, because pathlib
allocates a Path per visited entry. Measured by `_b11`, not guessed; rebuilt on `os.walk`, which
`_b11` then measured at 81.0 s cold. On that microbenchmark alone the change was worth roughly
nothing (break-even at ~2.7 unresolved names, and the self-test has 3) and I was about to revert
it. The END-TO-END measurement is what settled it — 20-25 s against 98-210 s — because the
microbenchmark timed a cold build against warm walks. **The microbenchmark and the end-to-end
run disagreed, and the end-to-end run wins**; a component timing is not a claim about the
program.

## 7. Also shipped: the gate now states its own world and times

`ci_gate.py` prints `world: live ~/.claude rules tree PRESENT/ABSENT` and a per-gate wall time
plus a total. The next evidence table is therefore COPIED from an instrument in one environment
instead of assembled by hand from two receipts. It prints no path — a CI log is a published
artifact and the home directory is an identity disclosure. Exit codes and invariants unchanged.

## 8. DoD status

- **DoD-1 — every rule classified always-on vs lazy by measured frontmatter: PASS**, unchanged
  and still enforced. `ci_gate` re-ran green this round: `always-on=8, divergence=3`.
- **DoD-2 — always-on token cost totalled: PASS**, unchanged (17,107 tok repo / 15,141 live over
  the 8; cl100k_base estimates, stated as such). Not re-derived this round.
- **DoD-3 — every contradiction measured and listed with the correction: PASS (inherited).**
  `r4_credential_rule_gate` re-ran this round: rc=1, 4 violations, exactly as pinned. **Not
  individually re-measured this round: the other contradictions.**
- **DoD-4 — no rule rewritten without evidence: PASS.** No rule was rewritten. `rules/`,
  `AGENTS.md` and `agent-self/**` are untouched by this round's commits.

## 9. Residual

- The workflow still has **never run on a runner**; the tiktoken-on-Linux repair remains
  UNVERIFIED with the same settling experiment (the first run of the new workflow).
- **Repo↔live drift (29/88 files, 7/8 always-on) is still neither gated nor fixed.** Unchanged
  from R1 and still an owner-visible deploy, not a silent build-lane side effect.
- The credential inversion is still **pinned, not fixed** — owner action.
- `_b10` and `_b11` walk the live tree and take minutes; both are `EXCLUDED` from the CI plan
  with that reason, so neither is a per-PR gate.
- Wall time is **not asserted** anywhere: `_b10` exits non-zero only if an exit code changes.
  Timing is evidence, not a contract, and a timing gate on a shared box would be flaky by
  construction.
