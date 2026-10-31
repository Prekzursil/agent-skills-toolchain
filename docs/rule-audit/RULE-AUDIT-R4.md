---
title: RULE-AUDIT-R4
type: note
permalink: dqverify-repo-20261013/docs/rule-audit/rule-audit-r4
---

# RULERESEARCH — BUILD round 4 (re-entry on a CONFIRMED defect)

**Status: COMPLETE for the must-fix. Every claim below was executed, not read.**
HEAD at build time `535653f3`. New tools: `r4_receipt_argv_gate.py`, `_r4_mark_mentions.py`,
`_r4_inventory_probe.py` — all in this directory, all re-runnable.

COVERAGE: §1-§4 are measured. §5 lists what is still open and why. Nothing here claims a
deployment to `~/.claude/`, and nothing here edits a rule, `AGENTS.md`, or `agent-self/`.

---

## 1. The defect, reproduced before it was fixed

Round 3's VERIFY lane (`RULE-AUDIT-VERIFY-R3.md` §4.1) and the round-3 adversary
(`RULE-AUDIT-ADV-R3.md` §2) independently CONFIRMED one defect. Re-measured here from scratch,
exit code captured with no pipe in the way (a pipe returns the exit code of `tail`, which is how
this class hides):

```
$ python docs/rule-audit/rule_audit.py --json --md > out 2> err ; echo $?     <!--argv-invalid-->
EXACT_RC=2
stdout bytes: 0
stderr: usage: rule_audit.py [-h] [--json JSON] [--md MD] [--self-test]
        rule_audit.py: error: argument --json: expected one argument
```

`--md` is consumed as the VALUE of `--json`; there is no second option, argparse exits 2 and
writes nothing. The receipt certified `rc=0`, and the "byte-identical (`cmp`)" beside it was
VACUOUS as written — the artifacts were unchanged **precisely because nothing was written**. That
is the §3c shape (a control that cannot distinguish the two hypotheses), reproduced inside the
receipt table of the report that writes the §3c calibration note.

**The claim survives; only the sentence was wider than its evidence.** Run as it was actually run:

```
$ python docs/rule-audit/rule_audit.py --json TMP/ra.json --md TMP/rat.md
... SUCCESS:rule_audit                                                    EXACT_RC=0
rule-audit.json         123,434 B vs 123,434 B   sha256 identical = True
RULE-AUDIT-TABLES.md      6,412 B vs   6,412 B   sha256 identical = True
```

Classification: **OVERCLAIM / false receipt, not a code defect.** `rule_audit.py` was correct the
whole time.

## 2. Sites corrected — and the two that measurement added

The round-3 adversary found three sites. The gate built in §3 found **ten**, because it reads
every documented invocation instead of grepping one string:

| # | site | kind | action |
|---|---|---|---|
| 1 | `RULE-AUDIT-R3.md:275` | **false receipt** (committed) | corrected in place + REFUTED note |
| 2 | `RULE-AUDIT-ADV-R2.md:24` | **false receipt** (committed) | corrected in place + REFUTED note |
| 3 | `_r3_commitmsg.txt:65` | **live template** of the history site | amended + note; history NOT rewritten |
| 4-6 | `RULE-AUDIT-ADV-R3.md:25,29,56` | reviewer QUOTING the defect | `<!--argv-invalid-->` marker only |
| 7-9 | `RULE-AUDIT-VERIFY-R3.md:48,74,90` | reviewer QUOTING the defect | `<!--argv-invalid-->` marker only |
| 10 | `RULE-AUDIT-R4.md` (this file) | quoting it in §1 | `<!--argv-invalid-->` marker only |

Site 3 is the one that matters most and is the one a string-grep of `*.md` misses twice over: the
false receipt also went into the **commit message of `0475e4a4`**, which cannot be edited, and its
template is still on disk ready to be re-emitted. The template writes it **without the `.py`** —
`rule_audit --json --md` <!--argv-invalid--> — so the first version of the gate read that line and
reported CLEAN. Fixed by resolving an extensionless name against the real script set; see §3.

The commit message in history is left alone deliberately — rewriting shared history is banned, and
the amended template plus this record is the reachable half of the blast radius.

**Nothing was silently deleted.** Both corrected receipts carry a REFUTED paragraph stating what
the row used to say, what it measured, and why the paired control was vacuous.

## 3. The gate: `r4_receipt_argv_gate.py`

A gate that READS a claim is not a gate. This one runs `rule_audit.py`'s **own argparse parser**
over every documented invocation in this directory.

```
$ python docs/rule-audit/r4_receipt_argv_gate.py         BEFORE the fix
scanned 15 markdown file(s), 25 script(s)
invocations: 35  tier1(real parser)=25  tier2(flag literals)=10  marked-invalid=0
  VIOLATION RULE-AUDIT-ADV-R2.md:24  ·  ADV-R3.md:25,29,56  ·  R3.md:275  ·  R4.md:13
  VIOLATION RULE-AUDIT-VERIFY-R3.md:48,74,90  ·  _r3_commitmsg.txt:65
FAILED:r4_receipt_argv_gate 10 violation(s)                                          rc=1

$ python docs/rule-audit/r4_receipt_argv_gate.py         AFTER the fix
scanned 16 corpus file(s), 28 script(s)
invocations: 45  tier1(real parser)=33  tier2(flag literals)=12  marked-invalid=11
SUCCESS:r4_receipt_argv_gate 45 documented invocation(s) parse against the tool they
name (11 quoted-as-broken, and each verified to REALLY be broken)                    rc=0
```

The corpus grows from 35 invocations to 45 because **this report is inside it**: a document that
quotes commands is itself a receipt surface, measured by the same gate as the ones it corrects.
The totals above are therefore true of the run that produced them and move whenever this file is
edited — the stable claims are the VERDICT (0 violations) and the two site lists, not the totals.
The gate caught this report twice while it was being written, and caught the commit message of
`aa50e309` quoting the defect: those are its intended behaviour, not noise.

Design points that are load-bearing rather than decorative:

- **It checks argv VALIDITY, not the claimed rc.** `r2_pathrefs.py` exits 2 on a genuine finding,
  so an rc-equality gate would either demand that finding never happen or need an expected-rc
  table that rots exactly like the prose. Validity is the property that was violated and the one
  that is mechanically decidable.
- **Two tiers, selected MECHANICALLY.** Tier 1 imports the module and uses `build_parser()`; tier
  2 (hand-parsed scripts such as `r2_pathrefs.py` and `_r2_blobcheck.py`) compares flags against
  the `--flag` string constants in the module's own AST. Tier 2 is WEAKER and it says so inline:
  it catches an unknown or misspelled flag and **cannot** catch a missing value, because a hand
  parser declares no arity. A tier-2 script that grows a real parser is promoted automatically.
- **`rule_audit.py` gained `build_parser()`** — the argument contract used to exist only inside a
  function that has to RUN to reveal it, which is why nothing could check it.
- **Exemption is an explicit FIELD.** A line carrying `<!--argv-invalid-->` is expected to be
  invalid, the same discipline `r2_control_count_gate.py` already uses for historical counts.
  Guessing "this looks like a refutation" from prose is the use-vs-mention mislabel this program
  keeps making. The marker is not a mute button: a marked line whose argv PARSES is a violation
  too, so it cannot silence a working command and it goes stale loudly.
- **Fail-closed** on zero markdown, zero extracted invocations, or zero tier-1 validations.

### 3.1 Three detector faults it committed on its own first run

Recorded because each one PASSED its way into a result before a control caught it, and because
the fix for each is now a regression arm with a proven broken state:

| fault | what it produced | fix |
|---|---|---|
| stripped `_` as markdown emphasis | reported `_r2_blobcheck.py` **3×** as "a script that is not in this directory" — findings manufactured by its own normalisation | keep `_`; arm C7 |
| rejected `<path>` metasyntax | reported the **prescribed correct form** as unrunnable at 4 sites, including in the two reviewer artifacts that were fixing the bug | `<placeholder>` is a value; arm C8 |
| one line, two candidate styles | 22 violations for 11 sites — a self-contradicting count, which is a detector fault, never a finding | dedupe per (line, script, argv); arm C9 |

And the fourth, the most dangerous because it was SILENT: requiring `.py` made the gate read the
commit-message template — the one site that becomes permanent — and report clean. Arms C10/C11
cover the extensionless form and prove it cannot promote an arbitrary prose word into a command.

`--self-test` runs **27 gate-level states**, and that number is `len(ran)` at runtime, never a
literal: round 1 of this lane shipped "20" against a measured 17 for exactly the reason a written
count rots.

## 4. Gate battery, re-executed on the changed state

```
r4_receipt_argv_gate.py --self-test  SUCCESS all 27 gate-level states passed          rc=0
r4_receipt_argv_gate.py              SUCCESS 45 invocations, 11 quoted-as-broken      rc=0
_r4_mark_mentions.py                 SUCCESS content sha unchanged on both files      rc=0
_r4_mention_composition.py           SUCCESS 114 mentions, cross-check AGREE at 56     rc=0
r4_credential_rule_gate.py           FAILED  4 violations -- tracker, owner action rc=1 (by design)
rule_audit.py --self-test            CONTROL-GROUPS: classifier=6 drift=4 crlf=2
                                     encoder=3 failclosed=4 TOTAL=19 -> SUCCESS (19)  rc=0
rule_audit.py --json <p> --md <p>    SUCCESS; JSON + TABLES sha256-identical          rc=0
r2_pathrefs.py --self-test           SUCCESS all 6 gate-level states passed           rc=0
r2_pathrefs.py                       scanned=254 unwaived=0 waived=3 known=1     rc=2 (by design)
r3_corpus_parity_gate.py             SUCCESS 3 trees / 254 files, mutation fires      rc=0
r2_control_count_gate.py             SUCCESS 4 live prose == tool 19 == AST 19        rc=0
r2_failclosed_mutation.py            SUCCESS mutant rc=1, pristine rc=0               rc=0
lazy_predict.py                      SUCCESS 16/16 injected, 1/1 withheld             rc=0
pytest ci/tests/test_rules_*.py      167 passed in 1.13s                              rc=0
uvx ruff@0.15.17 check               All checks passed!                               rc=0
uvx ruff@0.15.17 format --check      26 files already formatted (see §4.1)            rc=0
```

`rule_audit.py --self-test` still reports 19 after `build_parser()` was extracted, and
`r2_control_count_gate.py` still reconciles prose == tool == AST == group sum, so the refactor
did not disturb the control inventory.

### 4.1 ruff, and the CRLF trap this lane has hit before

`docs/rule-audit/` is inside ruff's scope, and `quality.yml` runs `check` **and** `format --check`
repo-wide, so an unformatted probe here reds the SHARED gate for every lane. Both were run on the
committed state, and the staged blobs were checked at LF (`git cat-file -p`), not the CRLF working
tree — the check that round 2 of this lane got wrong.

## 4b. Two round-3 residuals, measured (added after the must-fix landed in `aa50e309`)

**The highest-severity finding now has a mechanical tracker.** Residual 4 of the round-3
adversary was that §3.1 — a §9 security non-negotiable INVERTED in a deploy source that
`bootstrap.ps1:45` force-copies over `~/.claude` — was tracked only in prose, while a
*lower*-severity out-of-scope defect had a `KNOWN_DEFECTS` entry. `r4_credential_rule_gate.py`
asserts two invariants on `agent-self/config/AGENTS.md`, plus a live-comparison arm:

```
control extractor finds §9 / returns None for an absent one            PASS / PASS
control a repaired deploy source scores clean                          PASS
control INV-1 fires when the bullet is removed / INV-2 when re-added   PASS / PASS
control a document with no §9 at all is UNMEASURABLE, not clean        PASS
live arm (~/.claude/AGENTS.md): RAN
VIOLATION INV-1 the §9 bullet forbidding the agent to rotate/revoke/regenerate is ABSENT
VIOLATION INV-2 §9/§9b instructs the agent to rotate, which is the banned action
VIOLATION live §9 carries the protective bullet and the deploy source does not
VIOLATION live §9b says leave rotation to the owner; the deploy source omits that
FAILED:r4_credential_rule_gate 4 violation(s) -- owner action                          rc=1
```

It exits **1 today by design** — the defect is real and out of this lane's write scope — and it
turns green by itself when the owner fixes the deploy source. It is a tracker, not a green.
Its own positive control caught a bug in it before it produced a verdict: `\b` after
`re.escape("9.")` matches nothing (two non-word characters, so no boundary), so every arm was
reporting "no §9 section" — broken extractor and clean document producing the same silence.
UNVERIFIED, inline: three arms are regex-based, so a REWORDED protective bullet would read as
absent; the settling experiment is to reword it in a copy and check the gate still passes.

**The MENTION exemption's composition, and why nobody had stated it.** `_r4_mention_composition.py`
re-classifies the same tokens through `r2_pathrefs`'s own functions:

```
114 bare-filename mentions across 3 trees:  58 EXACT · 52 BASENAME-ONLY · 4 MISSING
resolving NOWHERE:  check_no_regression.py x2  ·  AGENTS.override.md x2
cross-check: non-EXACT here = 56  ==  r2_pathrefs bare-filename MENTIONS = 56   AGREE
control: a name that certainly exists classifies EXACT
```

The round-3 adversary's `52 + 4 = 56` reproduces **exactly**, by an instrument that walks the
trees rather than reading its output — and the 56 is now placed in context as the non-EXACT
subset of 114. The mechanical reason the composition was never published: `name_mentions=`,
`basename_only=` and `missing=` are printed **only in `r2_pathrefs.py`'s SUCCESS branch**
(`:325-330`), and the tracked-defect branch above it returns 2, so those counters are unreachable
in the state the gate has been in for three rounds. The tool volunteers its own exemption
composition only when it has nothing to exempt.

**Residual 2 (`in_claude_home` under-reports) was measured and deliberately NOT fixed.** The
claim is confirmed: `check_no_regression.py` really is at
`~/.claude/harness-restore-20260806/check_no_regression.py`, and `HOME_SEARCH_DIRS` has no glob
for `harness-restore-*`, so it is labelled MISSING. The naive fix costs **12.27 s** per run —
measured: one walk of that tree is 37,977 files / 14,445 distinct basenames — against a gate that
currently runs in about a second, to correct a verdict LABEL that the round-3 adversary already
proved cannot change any outcome (the helper runs only after the EXACT check fails, so it can
mislabel a KIND but never manufacture a false EXACT). Paying a 12x slowdown on a gate other
receipts depend on, at the end of a round, for a label, is the wrong trade. Disclosed, not closed.

## 5. Residuals — measured, disclosed, NOT closed

1. **`agent-self/config/AGENTS.md` §9/§9b is still inverted.** It omits the live "NEVER remove,
   rotate, revoke, regenerate … any API key or token" bullet entirely and its §9b says "rotate,
   don't just delete" where live says leave rotation to the owner. `bootstrap.ps1:45` force-copies
   `config/*` over `~/.claude`. This is the highest-severity finding in the whole audit and it is
   OUT of this lane's write scope (`AGENTS.md` is propose-only), so round 4 gave it a mechanical
   tracker (§4b) instead of a fix. **Still an owner action; the tracker changes nothing on disk.**
   UNVERIFIED: whether anyone has run `bootstrap.ps1` since the inversion landed — settling
   experiment is the `~/.claude/AGENTS.md` mtime versus the `agent-self` commit date.
2. **`in_claude_home()` under-reports** (`r2_pathrefs.py`) — CONFIRMED and costed in §4b, then
   deliberately left alone: the fix costs 12.27 s per run to correct a label with no verdict
   impact. Open, with the price of closing it now measured rather than guessed.
4. **Two corrected always-on rules remain undeployed** to `~/.claude/rules/`
   (`harness-vcs-hygiene.md` teaching a data-loss command, `cross-vendor-dispatch.md` §1
   contradicting always-on `AGENTS.md` §4a). Unchanged by this round, and deliberately: deploying
   mutates the live instruction set of every concurrently-running sibling lane mid-run.
5. **This gate covers ONE directory.** It reads `docs/rule-audit/*.md` and `*commitmsg*.txt`. The
   same defect class is live anywhere else in the repo that writes a receipt table, and nothing
   here measures that. Settling experiment: point `corpus()` at another lane's directory and read
   the violation list before deciding whether to widen it.
6. **NOT-CHECKED:** whether any CI workflow runs this gate. It is not wired; `ci/` is out of this
   lane's file scope. It is a re-runnable script, not an enforced gate, and calling it "enforced"
   would be this round's own version of the defect it fixes.
7. **Sensitive-artifact notice, surfaced not acted on** (AGENTS.md §9): the report-only sweep
   emitted `sha256:ed4787b86980` on an edit to `rule_audit.py`. No credential is present in that
   file — the edit extracted an argparse parser. No rotation performed and none recommended by me;
   surfaced to the owner as the notice requires.

## 6. Confidence

**ALMOST CERTAIN (90-99%)** — `--json --md` exits 2 and writes 0 bytes (exit code captured
unpiped, stderr quoted). The correct form returns rc=0 and reproduces both artifacts
sha256-identically (two files, byte lengths and digests). The ten sites (enumerated by an executed
gate, not a grep, and each one re-read at its own line). The gate FIRES on the pre-fix tree and is
SILENT after — both states measured on real committed bytes, not fixtures. The existing battery is
unregressed (11 receipts re-executed).

**LIKELY (55-80%)** — that ten is the complete site count for THIS defect string in THIS
directory. The gate found ten where a careful adversary found three, which is direct evidence that
enumeration beats reading; but its corpus is one directory and two file globs, so a receipt
written in a sibling lane's doc about this lane's tools is outside it (residual 5).

**UNCERTAIN (20-55%)** — that no OTHER documented command in this corpus is false in a way argv
validity cannot see. A command can parse and still not do what its receipt says. This gate closes
the "cannot even start" class and nothing wider; the honest boundary is stated in §3 rather than
implied by a green.

**OVERCLAIM CHECK, run against my own output.** (a) I do not claim the gate is wired into CI — it
is not (residual 6). (b) I do not claim the reviewer artifacts were left untouched: they gained
six invisible markers, and the proof they gained *only* markers is a printed before/after sha of
the marker-stripped content, from a script whose first version FAILED that control and whose
failure is recorded in its docstring rather than deleted. (c) The `27` in §3 is a runtime count,
not a written one. (d) `r2_pathrefs.py` exiting 2 is quoted as by-design, not as a pass.