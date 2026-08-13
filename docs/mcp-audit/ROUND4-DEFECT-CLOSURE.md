# MCPRESEARCH round 4 — defect closure ledger

Measured 2026-08-13, worktree `C:/Users/Prekzursil/source/ast-integrate`.
Companion to `ROUND3-DEFECT-CLOSURE.md` and `ROUND2-DEFECT-CLOSURE.md`. One row per
defect, each **reproduced against a pinned commit first**, then fixed, then red-proofed in
both states.

COVERAGE: three verifier findings closed — one false statement of fact, one overclaim, one
latent gate gap — plus their blast radius in round 2, which the verifier did not name but
which is the same claim's origin. 13 gates re-executed with captured exit codes. Four
detector failures in my own round-4 instruments, all caught by controls and all recorded.
**NOT measured:** the other ~23 CI steps; the exact mechanism of one Git-Bash grep
misreading (disclosed inline, settling experiment named); anything outside
`docs/mcp-audit/**` and `command-center/mcp-audit/**`.

If it still reads this way, the unit died before measuring anything and no verdict here
may be cited. — *it does not; every line below carries executed output.*

## Provenance — this round DID have the verifier's report

Round 3 had to re-derive its defect list because the round-2 verifier's report never
reached it. That gap is closed: round 3's report was salvaged into the repo by a sibling
lane at `command-center/ssot/salvaged-from-scratch/VERIFY-MCPRESEARCH-r3.md`, and this
round works from it directly. Its verdict was **PARTIAL** — all four DoD items PASS on
execution, with one REAL DEFECT, one OVERCLAIM and one LATENT gap. All three are below.

| # | defect | class | status |
|---|---|---|---|
| F1 | `ROUND3-DEFECT-CLOSURE.md` asserted the `.md`/`.json` blobs "carry CRLF (278 / 840)". Both blobs are **0 CRLF**; both numbers are exact LINE counts | false statement of fact, shipped | **CLOSED**, corrected + both-states red-proof |
| F2 | "AGENTS.md reads 112, exactly round 2's number, so the detector fires and agrees" — an inert control that talked round 3 out of a CORRECT first reading; plus a false `7aa86f16` attribution | overclaim / control-that-cannot-distinguish | **CLOSED**, refuted wording preserved, correction executed |
| F3 | `dod1()` never checked row-set MEMBERSHIP and `main()` failed closed only below 20 rows, so dropping up to 3 mounted servers still printed "DoD1 PASS" | latent gate gap | **CLOSED**, pinned-set floor + a control that fires |
| F1b | The same false claim's **origin**: round 2's five-row "CRLF lines" table | blast radius (not named by the verifier) | **CLOSED**, table refuted in place and replaced with measured values |

The family is unchanged across all four rounds — *a claim and the thing it describes
drifting apart* — but round 4's instance is the worst of the series, because it is the only
one where the drift produced a **statement about the repository that is simply untrue**,
and because a control was run, passed, and made it worse.

---

## F1 — "the blobs carry CRLF": measured 0, on every blob, at every revision

### Reproduced against the commit that shipped it

`_r4_redproof.py` reads `git show 673cd180:…`, not HEAD — reading HEAD would erase the
defect the moment the fix lands.

```
  BEFORE 673cd180 ROUND3-DEFECT-CLOSURE.md   asserted=1 quoted=0 detector fires: True
         e.g. gate, both commits), while the `.md`/`.json` blobs carry CRLF (`ROUND3-…
  BEFORE 2caafe53 ROUND2-DEFECT-CLOSURE.md   asserted=2 quoted=0 detector fires: True
         e.g. ## Observed while gating, NOT this lane's to fix: `.md` / `.json` blobs store CRLF
```

### The control round 3 never ran

A reading of "0 CRLF" is worthless on its own: it is equally consistent with *"the blob is
LF"* and with *"`git show` normalises and this instrument is blind."* That ambiguity is
what produced the false sentence, so `_r4_eol_probe.py` PART A refuses to print a single
number until it has disproved the second possibility **end to end, through the identical
code path** — build a repo, commit a genuinely-CRLF blob, read it back with `git show`:

```
  A1 synthetic CRLF buffer       -> (3, 3)  want (3, 3)  ok=True
  A2 synthetic LF buffer         -> (0, 3)  want (0, 3)  ok=True
  A3 REAL CRLF blob via git show -> (3, 3)  want (3, 3)  ok=True
  A4 REAL LF   blob via git show -> (0, 3)  want (0, 3)  ok=True
  => git show PRESERVES CRLF when the blob has it, so a reading of 0 on a real
     blob means the blob is LF -- not that the instrument is blind.
```

A5 adds a stronger control still: a **real, committed, third-party-authored** CRLF blob in
this repo (`_crlf_control_repo/known_crlf.md`, from a sibling lane) reads `(3, 3)`.

### The measurement

```
  rev       path                                     said  CRLF  lines  wt CRLF  hypothesis
  673c/0d3c ROUND3-DEFECT-CLOSURE.md                  278     0    278        0  H2 LINE-count
  673cd180  disposition.json                          840     0    840        0  H2 LINE-count
  2caafe53  ROUND2-DEFECT-CLOSURE.md                  248     0    276        0  neither
  2caafe53  ruff-census.json                           28     0     28        0  H2 LINE-count
  2caafe53  MCP-FLEET-AUDIT.md                        355     0    355        0  H2 LINE-count
  2caafe53  README.md                                 328     0    328      328  H2 LINE-count
  2caafe53  AGENTS.md                                 112     0    112      112  H2 LINE-count
  H1 'the numbers are CRLF counts' matches 0/7
  H2 'the numbers are LINE counts'  matches 6/7
```

The one "neither" is the round-2 doc's own row: `248` is its line count at `959f783f`, one
commit before the table shipped — the number was taken and the document kept growing. So
**7 of 7 are line counts**, six of them still exact at the shipping revision.

Second instrument, mechanically independent of byte counting — `git ls-files --eol`:
**0 of this lane's 40 indexed paths** are `i/crlf`, with its own control (127 of 135
`*.ps1` read `w/crlf`, proving the parser can see `crlf` where it exists).

### Why the mistake was so durable

`README.md` and `AGENTS.md` are genuinely CRLF **in the working tree** — and for a
fully-CRLF file *the CRLF count and the line count are the same number*. Two of the five
round-2 rows were therefore consistent with both hypotheses, and those two are exactly the
ones round 3 reached for as controls.

### Scoped replacement sentence, now shipped in both docs

> `README.md` and `AGENTS.md` are CRLF in the WORKING TREE (`w/crlf`) but LF in the
> committed blob (`i/lf`). Every blob this lane committed — `.py`, `.md` and `.json` alike
> — is 0 CRLF, which is what CI reads. `.gitattributes` pins only `*.sh` and `*.ps1`, so
> the worktree is unnormalised, but no committed byte is affected.

Consequences that follow and are recorded rather than left dangling: there is **no
`.md`/`.json` CRLF condition** to hand the orchestrator; round 2's "UNVERIFIED: is CI
sensitive to `.md`/`.json` line endings" is **moot, not open**; and round 3's residual list
has that item struck with a pointer to the correction.

---

## F2 — the inert control, and a false attribution

Round 3 wrote: *"`AGENTS.md` reads **112**, exactly round 2's number, so the detector fires
and agrees."* `AGENTS.md`'s blob is **0 CRLF and 112 LF lines**. A line count agreed with a
line count; nothing about a CRLF detector was tested. Round 3's **first** reading —
"round 2's CRLF table is wrong" — was correct, and the inert second control talked it out
of it. This is the third instance of that shape in this lane and the only one that shipped
a falsehood.

The attribution is wrong too, and separately checkable: `7aa86f16` is *"docs: repair a
decapitated README section, drop a stale currency banner, gate both"* (+7/-3 on
`README.md`), not an EOL rewrite, and `README.md` is `i/lf` on both sides of it.

**Both refuted paragraphs are preserved verbatim in blockquotes** in
`ROUND3-DEFECT-CLOSURE.md`, marked REFUTED, with the correction beneath them. Deleting them
would remove the only evidence of how the lane fails.

### The fix had to survive its own preservation rule

Requiring the refuted wording to stay on disk means a naive "is the false claim still in
this file?" check stays red forever — and the tempting way to make it green is to delete
the evidence. So `_r4_redproof.py` counts the **field, not the document**: a match on a
non-blockquote line is an *assertion*; the same match inside a blockquote is a *mention*.
Two clauses in opposite directions, plus two mutations:

```
  AFTER  ROUND3-DEFECT-CLOSURE.md  asserted=0 (want 0, ok=True)  quoted=1 (want >0, ok=True)
  AFTER  ROUND2-DEFECT-CLOSURE.md  asserted=0 (want 0, ok=True)  quoted=1 (want >0, ok=True)
  mutation unquote-the-refuted-line -> A1 fires: True
  mutation delete-the-refuted-line  -> A2 fires: True
```

That checker immediately earned its keep: it flagged **my own first draft** of the round-2
correction, which restated the refuted sentence in the document's own voice while
explaining that it was refuted.

---

## F3 — a gate that could not notice a server disappearing

`dod1()` validated fields *per row* and never checked *which rows exist*; `main()` failed
closed only below 20 of 23. Three mounted servers could vanish and DoD1 — whose promise is
"**every** mounted server inventoried" — would still print PASS, because every surviving
row was well-formed and the missing ones were never asked about.

**Fixed** with a pinned `EXPECTED_MOUNTED` set of 23 names, sourced from two independent
places that agree exactly: the `mcp__<name>__*` namespaces the harness exposed to this
session, and the 23 rows of the committed `capability-matrix.json`. The floor is now
`len(EXPECTED_MOUNTED)` rather than a hand-picked 20.

**Limitation, stated because a gate that hides one is worse than no gate:** a committed
blob cannot know what is mounted *today*, so this is a FLOOR. A newly mounted server does
not red the gate; a disappearing one does. Retiring one legitimately requires editing the
constant in the same commit — a deliberate, reviewable line in a diff instead of a silent
shrink.

### The discriminating comparison — the old gate is executed, not recalled

`_r4_redproof.py` PART B extracts `_r2_dod_check.py` **from commit `673cd180`** and runs
its `dod1` against a table with one server removed:

```
  mutation: drop the row for 'cloud-hub' (23 -> 22 rows)
  round-3 dod1 on the shrunken table -> 0 problems (PASS = blind: True)
  round-4 dod1 on the shrunken table -> 1 problems (fires: True)
  round-4 dod1 on the CURRENT table  -> silent: True
  round-3 main() floor was 20 of 23 rows -> up to 3 could vanish silently: True
```

DoD1 now carries **two** controls, one per branch — `blank-source-file` (malformed row) and
`drop-a-mounted-row` (absent row). Both fire. Dispositions unchanged at
`DISABLE 1 / INVESTIGATE 2 / KEEP 20`: this was a gate fix and must not have moved a
verdict — it did not.

---

## Four detector failures in my OWN round-4 instruments

Consistent with every prior round, self-inflicted detector failures outnumbered the real
findings. Each was caught by a control, not by inspection.

| # | my instrument said | the contradiction | root cause |
|---|---|---|---|
| 1 | `i/crlf: 0` then, four minutes later, `i/crlf: 1` | two runs of one probe disagreeing | Not a parser bug. HEAD moved `0475e4a4` → `379351df` and a sibling committed a CRLF control fixture. The repo-wide number is a moving target, so the load-bearing figure is now the **lane-scoped** one (0 of 40), which does not move. |
| 2 | `grep -c $'\r'` = the LINE count on five revisions Python read as 0 CR | two instruments, same bytes, opposite answers | Unexplained in the false-**positive** direction and disclosed as such. The false-**negative** direction was pinned with `od`: MSYS grep opens input in TEXT mode and strips CR before matching, so it returns **0 on input `od` proves contains CR** and needs `-U`. |
| 3 | the round-3 BEFORE state showed `asserted=0` — the detector was silent where the defect provably exists | a red-proof that cannot see its own BEFORE state proves nothing | I pinned the wrong revision (`0d3c9e93`, where the verifier took its line count) instead of `673cd180`, where the sentence actually landed. Measured, not guessed: `grep -c "blobs carry CRLF"` over the three round-3 commits gives `0 / 0 / 1`. `main()` now fails closed if a BEFORE state stops exhibiting its defect. |
| 4 | the in-repo positive control "did not fire" (`grep -cU` → 0 on a blob with 3 CRs) | a control failing on a file two other instruments agree is CRLF | **Three** compounding causes, each producing a *reassuring* number rather than an error: (a) `grep -c` prints `0` for "matched nothing" and for "was handed nothing"; (b) `bash` spawned from Python on this box is **WSL bash**, not Git Bash — the child reported cwd `/mnt/c/Users/...`; (c) this checkout is a **linked worktree** whose `.git` is a file holding a *Windows* absolute path, which WSL git cannot resolve (`fatal: not a git repository: /mnt/c/.../C:/Users/.../worktrees/ast-integrate`). Every reading taken that way was void. |

Failure 4 is the most reusable and is worth lifting out of this lane: **on this estate, a
`bash -lc` child spawned from Python inside a linked worktree silently reads an empty
repository.** Any probe built that way returns clean zeros forever. The second instrument
is now `git cat-file -p` invoked directly with `check=True`, so a failure raises instead of
returning a comforting `0`, and both readers must agree on byte size as well as CR count.

Failure 2 also supplies the best available answer to the question the verifier left open —
*where did round 2's numbers come from?* A CR-pattern grep through this shell **can** return
exactly the line count of a CR-free file (measured: 276 on a 276-line CR-free blob), which
is the precise shape of round 2's table. That is a reproduced *mechanism*, not a
demonstrated history: round 2's actual command was never committed and cannot be recovered.
**LIKELY (55-80%)**, and it is labelled that way in the script and here.

---

## Every gate, re-executed, with its real exit code

`python _r3_gate_sweep.py --rev <this commit>` → `SUCCESS:gate-sweep 13/13 gates behaved,
exit codes captured`, exit 0.

| gate | rc | want | marker |
|---|---|---|---|
| `probe_capability --control` | 0 | 0 | `SUCCESS:probe-capability control-only` |
| `redproof_control` | 0 | 0 | `SUCCESS:redproof-control 4/4 mutations caught` |
| `overlap_report` | 0 | 0 | `SUCCESS:overlap-report pairs=4 surfaces=16` |
| `_r2_reproduce` | 0 | 0 | `SUCCESS:r2-reproduce both defects present in the round-1 blob, absent now` |
| `_r2_redproof_invariants` | 0 | 0 | `SUCCESS:r2-redproof 4/4 A-mutations caught, B injection complete` |
| `_r2_corroborate` | 0 | 0 | `SUCCESS:r2-corroborate 16/16 agree on count AND names` |
| `_r3_redproof_liveness` | 0 | 0 | `SUCCESS:r3-redproof A ok, B 5/5 mutations caught, C widened predicate` |
| `_r4_eol_probe` | 0 | 0 | `SUCCESS:r4-eol controls fired, claims measured` |
| `_r4_grep_control` | 0 | 0 | `SUCCESS:r4-grep suspect detector characterised, corrected form controlled` |
| `_r4_cr_settle` | 0 | 0 | `SUCCESS:r4-cr-settle 0 CR in every claimed blob, positive control fires` |
| `_r4_redproof` | 0 | 0 | `SUCCESS:r4-redproof A both-states + 2 mutations, B the widened DoD1 sees the absence` |
| `_r2_dod_check` @ this commit | 0 | 0 | `SUCCESS:dod-check 4/4 DoD items PASS, 6/6 negative controls fired` |
| `_r2_dod_check` @ `630bb8af` | 1 | **1** | `FAILED:dod-check ['DoD3']` |

The `--rev` matters: it points the DoD ledger at the **committed blob**, not the working
tree. A `WORKTREE` run prints `[WORKTREE pre-flight, NOT a shipped verdict]` in its own
marker so a pre-flight can never be quoted as this line.

## Confidence

* **Almost certain (90-99%)** — every claimed CRLF number is a line count and every blob
  named in this lane is 0 CRLF (two mechanically independent instruments, each with a
  positive control observed to fire, plus a real committed CRLF blob as a third check);
  the `7aa86f16` misattribution (its diff is +7/-3 of prose); the round-3 DoD1 blindness
  (its own code, extracted from its own commit and executed against a shrunken table); the
  13 gate exit codes (captured `returncode`s); `bash`-from-Python being WSL and failing on
  this linked worktree (the child printed its own `/mnt/c` cwd and git's own fatal error).
* **Likely (55-80%)** — that a CR-pattern grep through the Git-Bash transport is how
  round 2's table came to be line counts. The mechanism is reproduced; the history is not
  recoverable, because round 2's command was never committed.
* **Uncertain (20-55%)** — that no FIFTH defect remains. Four rounds have each found three
  or four, which is not obviously converging. A self-review is not the settling
  experiment; another independent verify pass is.
* **UNVERIFIED, named with its experiment** — the false-positive direction of the Git-Bash
  grep reading (settling experiment: replace `grep` with a wrapper that dumps its own argv
  through `od -c`, then re-run the loop form). Carried over and still open: whether the 7
  unmeasured rows would yield a tool surface over HTTP; whether `agent-mail`'s 8811-vs-8812
  port field is stale or a second instance; whether the three playwright rails differ
  BEHAVIOURALLY.
* **Unchanged from earlier rounds, still open** — the `mcpctl` precedence question, the
  bytes-vs-tokens reconciliation with `impact.py`, and the `searxng` disable (a config
  mutation, recommended only). The `.md`/`.json` CRLF item is **removed from this list**:
  it never existed.
* **Explicitly NOT claimed** — that CI is green. Two gates were verified over the committed
  blobs; the other ~23 steps were not run.
