# RULERESEARCH — BUILD round 3: the corpus the sweep never looked at

Round 2 (`7770f6e8`) was cleared by an independent audit and then **refuted by an adversarial
lane** (`RULE-AUDIT-ADV-R2.md`), which proved one defect executable and, separately, that the audit
which cleared it had located the same gap, written the settling experiment, and not run it.

This round fixes that defect, fixes the sentences built on it, and — because the defect was a
*silent divergence between an instrument and a claim* rather than either one being wrong on its
own — adds the gate that makes the class unrepeatable.

Every number below came from a command run in this session. Nothing was carried over unexecuted,
including the adversary's own findings: I re-derived the defect with different instruments before
accepting it.

COVERAGE: D1-D5 MEASURED (table below), plus one axis neither the adversary nor any prior round
raised — whether the DECLARED corpus is itself complete (§5b: measured, three trees is right, with
the discriminator named). UNMEASURED and disclosed inline: the token estimator is
still `cl100k_base`, not Anthropic's tokenizer (±10-20%; `/context` is the only first-party receipt
and a subagent cannot invoke it); the non-path contradiction axes (command invocations, cited line
numbers, counted claims) remain unswept on all three trees; and `agent-self/bootstrap.ps1` was
still not executed, so §3.4's promote-delta is still a simulation.

## Inbound findings and what happened to each

| # | inbound (adversarial round 2) | my verdict after re-measuring | outcome |
|---|---|---|---|
| D1 | `r2_pathrefs.py:36` `TREES` omits `agent-self/config/rules` — 78 files, 30.7% of the corpus | **CONFIRMED** — reproduced, and the exclusion is undisclosed exactly as charged | FIXED in code |
| D2 | tenth path-axis contradiction at `agent-self/config/rules/README.md:74` | **CONFIRMED** by three signals I chose myself, none of them the adversary's probe | Listed as `RULE-AUDIT.md` §3.10; fix PROPOSED (out of write scope) |
| D3 | `agent-self:README.md:138` is the same benign case already waived for `live:README.md:104` | **CONFIRMED** — read both, identical sentence | WAIVED with its reason |
| D4 | "MEASURED: no [tenth contradiction]" is wider than its evidence | **CONFIRMED overclaim** | Sentence fixed at 9 sites; the refuted wording is preserved, not deleted |
| D5 | `_r2_blobcheck.py`'s receipt is single-use — rc=1 for every reader after the commit | **CONFIRMED** — reproduced rc=1 | FIXED: `--rev <rev>` reads committed blobs |

## 1. D1/D2 — re-measured before accepted

The floor says a subagent's finding is a single signal. So before touching anything I asked the
question the adversary's sweep answers, using instruments it does not use:

```
$ ls agent-self/config/rules/common/
agents.md  code-review.md  coding-style.md  development-workflow.md  git-workflow.md
hooks.md   patterns.md     performance.md   security.md              testing.md
$ find agent-self -name 'windows-shell*' -print
                                          (no output, exit 0)
$ git ls-files agent-self/config/rules/common | wc -l
10                                        (same 10 — so it is not ignored or untracked either)
```

and read the citing line at source. `agent-self/config/rules/README.md:74`:

> a rule that calls itself cross-tool (for example [`common/windows-shell.md`](common/windows-shell.md)) is NOT in Codex's instruction chain until you add a pointer yourself

Both the backticked path and the link target resolve relative to that README's own directory, so
both name `agent-self/config/rules/common/windows-shell.md`. It is not there. Positive control:
the same basename **is** present in the other two trees (`rules/common/windows-shell.md`,
`~/.claude/rules/common/windows-shell.md`) — which is why the sweep verdict is BASENAME-ONLY (a
wrong pointer) rather than MISSING (a nonexistent file), and which proves the classifier is
discriminating rather than blanket-failing the tree.

D1 reproduces on the code: `TREES` held two entries, `rule_audit.TREES` holds three, and the
artifact's DoD-1 corpus is 254 files. Nothing connected them.

## 2. The fix in code — three buckets, and an exit code that cannot green-wash

Widening `TREES` is one line. The part worth reviewing is what happens to the finding it surfaces,
because the tempting move is to waive it and go green — which would be this program's signature
failure with extra steps.

`agent-self/**` is **outside this lane's write scope** (propose-only), so the broken pointer cannot
be fixed here. The sweep therefore separates three things it previously collapsed into two:

| bucket | meaning | effect on the gate |
|---|---|---|
| unwaived | an unadjudicated broken pointer | `rc=1` — the thing the sweep exists to catch |
| `WAIVERS` | read at source, **not** a defect (use-vs-mention, or a quoted example whose relative path is correct from where it is quoted) | silent, but printed with its reason |
| `KNOWN_DEFECTS` | read at source, **a real defect**, source out of write scope | `rc=2`, printed loudly, `FAILED:` marker |

`rc=2` is still a FAILED terminal state. It exists only to distinguish "a tracked defect is still
live" from "something NEW appeared", so the sweep keeps working as a regression gate while the
tracked item waits on someone with write access to that tree. **A tracked entry that stops matching
also fails the sweep** (`rc=1`, `STALE ENTRY`) — so when the source is fixed, the entry cannot be
left behind as a lie.

Gate-level states, all driven through the real `main()`:

```
gate-level controls (main() must go red for a real defect):
  PASS  clean tree -> exit 0
  PASS  broken positional claim -> exit 1
  PASS  stale waiver -> exit 1
  PASS  tracked defect, nothing new -> exit 2
  PASS  tracked defect + a NEW broken claim -> exit 1
  PASS  stale tracked defect -> exit 1
SUCCESS:r2_pathrefs-self-test all 6 gate-level states passed
```

The fourth and fifth exist as a pair on purpose. Alone, "tracked defect → 2" would prove only that
the bucket exists; the fifth proves a tracked entry **does not silence a new finding sharing the
tree** — which is the exact way a known-defect list turns into a blanket exemption.

The real three-tree run:

```
rule files scanned: 254 across 3 trees
non-EXACT references: 61
  bare-filename MENTIONS (no location asserted, not findings): 56
  POSITIONAL path claims that do not resolve: 5
  WAIVED  live:README.md:104  ->  ../common/coding-style.md
  WAIVED  repo:common/cross-vendor-dispatch.md:36  ->  lib/job-control.mjs
  TRACKED DEFECT  BASENAME-ONLY  agent-self:README.md:74  ->  common/windows-shell.md
  TRACKED DEFECT  BASENAME-ONLY  agent-self:README.md:74  ->  common/windows-shell.md
  WAIVED  agent-self:README.md:138  ->  ../common/coding-style.md
FAILED:r2_pathrefs scanned=254 unwaived_path_claims=0 waived=3 known_defects=1 still live
and tracked (no NEW finding; rc=2 distinguishes this from rc=1)
```

Both pre-existing waivers still fire, so widening invalidated nothing — the whole delta is the
added tree. The tracked defect fires twice on one line because the backticked path and the link
target are two independent pointer claims that happen to agree.

## 3. §3.10 — the tenth contradiction, at its real size

Written up in `RULE-AUDIT.md` §3.10 with the measurement, the controls, and the proposed
correction. Two things I want to state here rather than let a reader infer:

**Severity is low, and I am not inflating it to make the round look better.** This is a
documentation pointer in a README, not an instruction that changes agent behaviour. It is nowhere
near §3.1 (a security non-negotiable inverted in a deploy source). It is also not nothing:
`agent-self/bootstrap.ps1:45` force-copies that tree over `~/.claude`, so a **fresh** bootstrap
ships a README pointing at a rule it never installed. On this box the link happens to resolve
against a `windows-shell.md` that arrived by another route — which is precisely why nobody noticed.

**The correction is proposed, not applied.** Preferred fix: ship
`rules/common/windows-shell.md` into `agent-self/config/rules/common/`, which also narrows §3.4's
parity gap. Alternative if that tree is deliberately a subset: cite one of the 10 rules it does
ship. I did not edit `agent-self/**`; `git status --short -- agent-self/` is empty.

## 4. D4 — the sentence, and the self-check that could not fail

Nine sites in `RULE-AUDIT-R2.md` carried the two-tree scope. All nine are corrected, and the
refuted wording is preserved verbatim (strikethrough plus a correction banner at the top of the
document) rather than deleted, so the record stays checkable.

The corrected claim: *no tenth contradiction on the path axis in `live` or `repo` (176 files); one
in `agent-self` (78 files), found the moment the sweep was pointed at it.*

The more useful finding is **why nobody caught it**, and it indicts a paragraph I would otherwise
have pointed at as evidence of rigour. `RULE-AUDIT-R2.md`'s own overclaim check reads:

> "No tenth contradiction" is scoped to the path axis in every place it appears.

That is TRUE. It was also **incapable of failing** — the claim genuinely was axis-scoped
everywhere, so the check passed and got recorded as diligence while the unexamined dimension
(corpus) sat one `ls` away: `176` printed next to a DoD that says `254`. This is
`rules/common/single-signal-verification.md` §3c — *a control that cannot distinguish the two
hypotheses is not a control* — reproduced by the lane that wrote §3c into the rules tree three days
earlier. Recorded in `RULE-AUDIT-R2.md` §8 with the generalisation: enumerate the dimensions of a
scope claim (axis · corpus · time · tree · tool version) and state the measured value of each,
rather than confirming the one already known to be right.

## 5. NEW — `r3_corpus_parity_gate.py`, so this cannot recur silently

Round 2 met an overclaim by binding the prose to the tool's own output. Same medicine, corpus
dimension: bind the SWEEP to the AUDIT.

Two mechanically independent bindings, because each has a blind spot the other covers:

* **paths** — `rule_audit.TREES` (the declared corpus, from which every DoD-1 number derives) must
  equal `r2_pathrefs.TREES` as resolved paths. Catches a tree added to one module and not the
  other: the round-2 defect exactly.
* **count** — the `*.md` count the sweep REPORTS visiting at runtime must equal the count
  `rule_audit`'s own scanner enumerates. Catches what a path comparison cannot: identical tree sets
  where one walk silently visits fewer files (changed glob, early `continue`, skipped subdir).

It does not merely assert. It **re-creates the round-2 defect against the real sweep** and requires
both bindings to fire:

```
declared corpus (rule_audit.TREES) : ['agent-self', 'live', 'repo']  files=254
swept corpus (r2_pathrefs.TREES)   : ['agent-self', 'live', 'repo']  files=254

both-states control (re-creating the round-2 two-tree sweep):
  MUTANT sees: tree 'agent-self' is in the declared corpus but NOT swept (...) -- this is the round-2 defect
  MUTANT sees: file counts disagree: the audit enumerates 254, the sweep visited 176
  mutant swept 176 files (real sweep: 254)
  path binding fires on the mutant : PASS
  count binding fires on the mutant: PASS

SUCCESS:r3_corpus_parity 3 trees / 254 files declared == swept, and the two-tree mutation fires on both bindings
```

The mutant reproduces round 2's `176` exactly. That is the strongest single line in this round: the
gate is not asserted to catch the defect, it is **observed** catching it, in the same invocation
that reports the green.

### 5b. But is the DECLARED corpus itself right? — consistency vs completeness

The obvious attack on §5: the gate binds the sweep to `rule_audit.TREES`, so if *that* were missing
a tree both sides would agree at two and the gate would report parity on an incomplete corpus. The
three-tree corpus had been inherited unquestioned since round 1. Measured now:

```
$ find . -type d -name rules -not -path "*/.git/*" -not -path "*/node_modules/*" -not -path "*/vendor/*"
./rules                                   <- corpus
./agent-self/config/rules                 <- corpus
./skills/code-security/rules              ./skills/llm-security/rules
./.agents/skills/code-security/rules      ./.agents/skills/llm-security/rules
$ find "$HOME/.claude" -maxdepth 4 -type d -name rules      -> 101 hits
```

**Verdict: three is right, and here is the discriminator rather than an assertion.** The four
skill-bundled directories hold 82 markdown files that are *not* injectable rules:

* **different frontmatter schema.** 78 of 82 carry frontmatter, but the vocabulary is
  `title / impact / impactDescription / tags` — a security-catalogue schema. The rule corpus's
  vocabulary is `paths:`, the key that gates lazy injection. Presence of frontmatter is not the
  discriminator; its *schema* is. Had I checked only "does it have frontmatter", 78 files would
  have looked like rules.
* **not deployed to the rule tree.** `find ~/.claude/rules -name code-injection.md` returns nothing;
  `~/.claude/rules/` holds `README.md` plus 14 language directories and nothing else. They deploy
  to `~/.claude/skills/` and load through skill progressive disclosure, not turn-0 injection.
* **first-party negative evidence.** My own turn-0 context carried the 8 no-frontmatter live rules
  and no skill rule; the 16 path-scoped rules injected after I read `.py` files were all from
  `~/.claude/rules/`. The harness itself never treats these as rules.

Of the 101 `~/.claude` hits, exactly one — `~/.claude/rules` — is the live tree. The other 100 are
`agent-worktrees/`, `agent-worktrees-salvage/`, `scratch/`, `toolchain-audit/` and dated backups:
disposable clones, which is the same conclusion this repo's own `CLAUDE.md` SSOT block reaches
about the 25 checkouts on this box. They are excluded deliberately, and now on the record.

This is a **one-time measurement, not a gate** — a fifth tree added tomorrow would not fire
anything. Automating it (walk for `rules/` dirs, discriminate by frontmatter schema, fail on an
unknown one) is the natural next gate and is listed as residual.

## 6. D5 — a receipt nobody could re-run

`_r2_blobcheck.py` read the **staged index**. Round 2 ran it, printed `SUCCESS:r2_blobcheck`, and
committed — after which the index is empty and the same command returns
`FAILED ... fail closed` for every later reader. The adversary confirmed rc=1 and had to re-derive
the evidence by hand. Fail-closed was right and stays; the missing piece was a second mode.

`--rev <rev>` reads a commit's blobs (`git cat-file -p <rev>:<path>`). Round 2's evidence line is
now reproducible by anyone, forever, from the artifact alone:

```
$ python docs/rule-audit/_r2_blobcheck.py --rev 7770f6e8
blob source: commit 7770f6e8
.py blobs extracted: 6   CRLF pairs in blobs: 0
  ruff check: rc=0            ruff format --check: rc=0  ['6 files already formatted']
  CONTROL (mangled docs/rule-audit/_r2_blobcheck.py): rc=1 (must be non-zero)
SUCCESS:r2_blobcheck 6 blob(s) from commit 7770f6e8 clean at LF, control fires        rc=0
```

Both fail-closed states still fire, and I checked the one that matters — a rev with no `.py` files
is not silently reported as clean:

```
$ python docs/rule-audit/_r2_blobcheck.py --rev e3493fc8      (the md-only round-1 commit)
FAILED:r2_blobcheck no .py files in commit e3493fc8 -- nothing measured, fail closed   rc=1
$ python docs/rule-audit/_r2_blobcheck.py                     (empty index)
FAILED:r2_blobcheck no .py files in staged index -- nothing measured, fail closed      rc=1
```

## 7. Gates, on the changed state

```
r2_pathrefs.py --self-test          SUCCESS all 6 gate-level states passed          rc=0
r2_pathrefs.py                      FAILED  scanned=254 unwaived=0 waived=3 known=1 rc=2 (by design)
r3_corpus_parity_gate.py            SUCCESS 3 trees / 254 files, mutation fires     rc=0
rule_audit.py --self-test           CONTROL-GROUPS: classifier=6 drift=4 crlf=2
                                    encoder=3 failclosed=4 TOTAL=19 -> SUCCESS (19)  rc=0
r2_control_count_gate.py            SUCCESS 4 live prose claim(s) == tool 19
                                    == AST 19 == group sum 19                        rc=0
r2_failclosed_mutation.py           SUCCESS mutant rc=1, pristine rc=0               rc=0
lazy_predict.py                     SUCCESS 16/16 injected, 1/1 withheld             rc=0
rule_audit.py --json <p> --md <p>   regenerated: JSON and TABLES byte-identical      rc=0
pytest ci/tests/test_rules_*.py     167 passed in 0.84s                              rc=0
uvx ruff@0.15.17 check              All checks passed!
uvx ruff@0.15.17 format --check     20 files already formatted
```

**REFUTED in round 4, and corrected in place rather than deleted.** This row previously read
`rule_audit.py --json --md` — no values — and certified it `rc=0`. <!--argv-invalid--> That argv is
an argparse usage error: `--md` is consumed as the VALUE of `--json`, and the tool exits **2**
having written **0 bytes**. So the paired "byte-identical" was VACUOUS as written — the artifacts
were unchanged precisely because nothing was written, which is the §3c shape (a control that cannot
distinguish the two hypotheses) inside a receipt table. Measured round 4, exit code captured with no
pipe in the way: `EXACT_RC=2`, `rule_audit.py: error: argument --json: expected one argument`.

The CLAIM the row supports survives: run with real paths the invocation returns `SUCCESS:rule_audit`
rc=0 and both artifacts are sha256-identical to the committed ones (`rule-audit.json` 123,434 B,
`RULE-AUDIT-TABLES.md` 6,412 B). Only the sentence was wider than its evidence. Round 4 also built
`r4_receipt_argv_gate.py`, which parses every documented invocation in this directory with the
tool's own parser; it FAILED on this exact line before the fix and passes after it.

`r2_pathrefs.py` exiting 2 is the honest state, not a broken gate: a real broken pointer is live in
a tree this lane may not write to. `rc=1` (a new or drifted finding) is what would demand action.

**`ruff format` was applied to 3 files and PROVEN semantics-preserving**, not assumed: stdout of
all four affected invocations captured before and after, `cmp` reports 4/4 byte-identical. The
round-1 lane found that `ruff check` green does not imply `ruff format --check` green, and that
`quality.yml` runs both repo-wide — so an unformatted file here reds the shared gate for every
sibling lane.

167/167 is a **no-regression** signal for the rule contracts, not evidence that anything in this
round is correct — those tests do not read `docs/rule-audit/` at all.

## 8. Detector controls, and the state in which each one fires

| control | fires when | proven this round |
|---|---|---|
| corpus-parity path binding | a tree is declared but not swept | YES — mutant names `agent-self` |
| corpus-parity count binding | tree sets match but a walk visits fewer files | YES — mutant reports 254 vs 176 |
| corpus-parity fail-closed | empty tree map, 0-file corpus, or unparseable sweep | code path present, not exercised (residual) |
| sweep: clean → 0 | nothing outstanding | YES |
| sweep: unwaived → 1 | an unadjudicated broken pointer | YES |
| sweep: stale waiver → 1 | a waiver stops matching | YES |
| sweep: tracked → 2 | a tracked defect is still live | YES |
| sweep: tracked + new → 1 | a tracked entry tries to shadow a new finding | YES |
| sweep: stale tracked → 1 | someone fixed the source and left the entry | YES |
| sweep classifier | EXACT / BASENAME-ONLY / MISSING each reachable | YES — 5 classifier cases |
| blobcheck mangle control | extracted blobs stop being CI-clean | YES — rc=1 on the mangled copy |
| blobcheck fail-closed (2 modes) | no `.py` in the index, or none in the rev | YES — both measured, rc=1 |
| §3.10 positive control | the classifier blanket-fails a tree | YES — same basename EXACT in 2 trees |

## 9. What this round did NOT change

* **No rule file.** `git status --short -- rules/` is empty; this round edited zero rules. Round 1's
  three rule corrections stand unchanged.
* **No `AGENTS.md`, no `agent-self/**`, no `~/.claude/**`, no `ci/**`, no `scripts/**`, no
  `.github/workflows/**`** — the last being the shared-file hazard that red-blocked every PR.
* **No deploy.** The two live-wrong always-on rules (§3.2, §3.3) are still fixed only in `rules/`
  and still unread by any agent. Unchanged from round 2, and still an orchestrator call because
  `sync-rules.ps1` mutates the live instruction set of every concurrently-running sibling.

## 10. Confidence

**ALMOST CERTAIN (90-99%)** — `agent-self/config/rules/common/windows-shell.md` does not exist
(three independent instruments, plus a positive control proving the probe finds that basename where
it does exist). `TREES` omitted that tree (read at the line; and the mutation reproduces the exact
176 the round-2 artifact printed). The corpus is 254 files across three trees (two independent
enumerators agree). All six sweep states and both parity bindings fire as reported (executed, in
the same invocation as the green). 167/167. `ruff format` semantics-preserving (4/4 `cmp`).
Round-2's blob receipt now reproduces at `--rev 7770f6e8` (executed).

**ALMOST CERTAIN (90-99%)** — that three trees is the complete rule corpus **as of this commit**
(§5b: an exhaustive `find` on both roots, plus a named discriminator — frontmatter schema — and
first-party evidence that the harness never injects the 82 skill-bundled files). Not gated, so the
band applies to today, not to tomorrow.

**LIKELY (55-80%)** — that the three-tree path sweep now finds everything on this axis. It found
exactly 5 positional claims and I adjudicated all 5, but a tree newly under an instrument deserves
more than one clean run before "closed", and `GENERIC` still drops five common basenames by design.

**UNCERTAIN (20-55%), disclosed inline** — that no eleventh contradiction exists. Round 3 is direct
evidence against optimism here: the tenth was invisible for two rounds and three reviewers, and it
took an instrument rather than a reader to surface it. The census stays a floor.

**Estimator caveat, unchanged** — every token figure is `cl100k_base`, ±10-20%.

**OVERCLAIM CHECK on this document.** (a) The sweep is RED and I lead with that rather than
reporting "gates green"; `rc=2` is presented as a FAILED state. (b) §3.10's severity is stated as
*below* §3.1-§3.3 — the round's headline find is also its least dangerous one, and inflating it
would be the easy win. (c) The corpus-parity gate is claimed to catch the round-2 defect on the
strength of a mutation that was executed, not on the strength of its design. (d) "167 passed" is
scoped as no-regression, since those tests never read this directory. (e) One control in §8 is
marked as present-but-unexercised rather than folded into the green. (f) I did not re-litigate
anything the round-2 audit cleared; I re-ran it, and it reproduced.

## 11. Residual

1. **§3.10 is LIVE.** A fresh `agent-self/bootstrap.ps1` still ships a README pointing at a rule it
   does not install. Out of this lane's write scope; the sweep exits 2 until it is fixed.
2. **§3.1 remains the highest-severity item in the whole lane and is still unfixed** — the
   `agent-self/config/AGENTS.md` §9 credential-rotation inversion, propose-only across three
   rounds now. Exact patch in `RULE-AUDIT.md` §5.1. Nothing gates `AGENTS.md` parity.
3. **The corrections in `rules/` are still not deployed** (§3.2, §3.3) and `~/.claude/rules/` is
   still read by no gate — the root cause of all 29 drifted files.
4. **Two CI gates specified, not built** (`ci/` out of scope), now three: the deployed-surface
   parity test, the load-semantics allowlist, and wiring `r3_corpus_parity_gate.py` itself. Each
   already emits a terminal marker and has a proven failing state, so each is a one-line addition.
5. **Only the path axis is swept.** Command invocations, cited line numbers and counted claims are
   unmeasured on all three trees. Settling experiment unchanged: extract every checkable assertion
   in `rules/**` that names a file, line, command or count and assert each mechanically.
6. **The parity gate's own fail-closed paths are unexercised.** They are one `TREES = {}` away from
   a control; I ran out of falsifiable value before contriving it, and say so rather than listing
   them as proven.
6b. **Corpus completeness is measured once, not gated.** §5b establishes that three trees is the
   right corpus and names the discriminator (frontmatter *schema*, not presence), but nothing
   fires if a fourth appears. Next gate: walk for `rules/` directories, classify each by
   frontmatter schema, fail on an unrecognised one. Until then §5b is a snapshot dated to this
   commit.
7. **`/context` still not run** (a subagent cannot), so every token figure remains an estimate.
8. **`ci/tests` cannot go fully green on Windows** — one pre-existing `os.fsdecode(b"\xff")`
   failure, proven pre-existing in a fresh clone by the VERIFY lane. Not this lane's.
