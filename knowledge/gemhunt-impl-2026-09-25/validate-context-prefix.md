# Lane: validate-context-prefix — ADVERSARIAL validation of lane `context-prefix`

Validator run 2026-09-25, host OFFLOAD-W2025. Posture: REFUTE by default. Every verdict
below used an instrument MECHANICALLY DIFFERENT from the one the implementer used;
re-running their command was never counted as confirmation.

**Status: COMPLETE.** 4 items examined, 11 hard rules checked, regressions probed.
Headline: **0 hard-rule violations. 1 premise REFUTED with a measurable code defect.
2 OVERCLAIMS. 1 undisclosed self-inflicted cost. 1 finding STRONGER than they claimed.**

---

## Instruments I used (vs theirs)

| Their instrument | My DIFFERENT instrument |
|---|---|
| PowerShell `Select-String` / `Get-FileHash` | Git Bash `grep -n` / `wc -l` / `diff`; `git show HEAD:` blob; **this session's own injected prefix** |
| `probe_dupes.py` over 3 largest transcripts | `val_probe_cache.py` + `val_probe_cache2.py`, re-derived from scratch over **all 1,897** transcripts |
| `--selftest` (their own) | **My own 6 mutants** of their code — break it myself, confirm exit 1 |
| `bytes/4` token arithmetic | **Live injected skill listing** — count skills whose description was actually dropped |
| lint enumerates CLAUDE.md @-import chain | enumerate what the LIVE session actually injects, then scan it with their own patterns |

---

## (a) `# Compact instructions` block — CONFIRMED (with one off-by-one OVERCLAIM)

**CONFIRMED.**
- Premise: I read `~/.claude/rules/common/context-reduction.md` rule 2 directly in my own
  injected context — it does mandate *"keep a `# Compact instructions` block in CLAUDE.md so
  auto/manual compaction deterministically preserves decisions, diffs, and OPEN-LOOPS."* Exact.
- Pre-state ABSENT, corroborated by an instrument they could not have used: **this validator's
  own system context carries the PRE-EDIT `~/.claude/CLAUDE.md`** (no `# Compact instructions`
  block), proving the file lacked it when this workflow's prefix was built.
- Post-state: `grep -n -i '^#\+[[:space:]]*Compact instructions'` → `7:` in BOTH files.
  `wc -l` → 146 / 146. `diff .claude/CLAUDE.md .agents/CLAUDE.md` → **no output**;
  sha256 equal (`043DE8428E703A07…`), 10,404 B each. Mirrors genuinely in sync.
- Under the ceiling: context-reduction rule 8 wants CLAUDE.md < 200 lines; 146 ✓.

**OVERCLAIM (minor, immaterial).** They wrote *"total lines 146 (was 129, +17 ≤ 25 cap)"*.
`git diff --numstat` → **`18  0  CLAUDE.md`**. `git show HEAD:CLAUDE.md` = **128** lines,
live = 146, delta = **18**. The block is 18 lines and the pre-state was 128 — off by one on
both. Verdict unchanged (18 ≤ 25).

**UNDISCLOSED COST (not a rule violation, but it is this lane's own doctrine).**
context-reduction rule 10: *"mid-session CLAUDE.md/MCP-config edits invalidate the system
cache… Avoid these mid-task."* The edit landed at **22:47:47** with **4 live `claude.exe`
sessions + this live workflow**. So a cache-hygiene gem paid a system-cache invalidation
across ≥5 live sessions. Evidence it really invalidated: my prefix holds the pre-edit copy.
The item's net-negative section counts the ~180 added tokens but never this.

**Both-states:** correctly N/A — a doc block is not a gate (rule 7 scope). Agreed.

## (b) `cache_lens.py` — OVERCLAIM: premise REFUTED, one headline number measurably wrong

**Both-states CONFIRMED — by my own mutants, not their selftest.**
| mutant | result |
|---|---|
| `mid = None` → dedupe genuinely inert | `FAILED` **exit 1** (3 of 6 checks flip) |
| drop `and r["cr"] == 0` from the cold detector | `FAILED` **exit 1** |
| unmodified original | `SUCCESS` **exit 0** |

*Discarded honestly:* my first mutant (deleting `if mid in seen: continue`) still passed — it is
semantically INERT because `seen[mid] = …` dedupes via the dict key regardless. I did **not**
report that as a refutation.

**REFUTED premise.** Docstring + evidence claim *"distinct usage tuples per id = 1 … the
IDENTICAL usage block is copied onto every duplicate line … dedupe by message.id is safe +
lossless"* (labeled VERIFIED ~97%). Re-derived over **all 1,897** transcripts (they sampled 3):

- **6,463 of 35,453 distinct `message.id` (18.2%) carry DIFFERENT usage tuples** across their
  duplicate lines. Their premise requires 0.
- **6,444 of those have an all-zero `(0,0,0)` FIRST line** with the real usage on a later line,
  e.g. `msg_2026092016055363390735edb34943: [(0,0,0), (618,105728,0)]`.
- `scan_file` keeps the **FIRST** line → it discards the real usage on exactly those.
- Their risk note is **inverted**: *"stays correct even if usage were logged only on the first
  content-block line (keeps that one)"* — reality logs the **zero** first.

**Measured consequence (keep-first vs keep-max, same corpus):**

| | keep-FIRST (shipped) | keep-MAX | error |
|---|---|---|---|
| cache_read | 8,577,089,059 | 9,341,718,304 | **−8.19% (−764.6M tok)** |
| input_tokens | 102,000,508 | 165,519,644 | **−38% (−63.5M tok)** |
| cold prefix rewrites | **348** | **333** | **+15 false cold (~4%)** |
| hit rate | 94.73% | 94.53% | robust ✓ |

The 15 extra "cold rewrites" are artifacts: a message whose first line logged `cr=0` while a
later line shows a real cache read is misread as a cold prefix re-encode. That directly hits the
reported *"cold prefix rewrites 347 / 82,617,810 tok"*.

**Secondary defect.** Dedupe is **per file** (`scan_file`) then globally concatenated.
**114 message.ids appear in ≥2 transcript files** → the global totals double-count 115 messages
(+2,143,760 cache_creation, +0.57%); cross-file-deduped cold count is **343**.

**What SURVIVES (CONFIRMED).** The 2.92x line inflation (mine: 103,686 raw → 35,568 per-file
distinct = 2.92x) and the **94.7% hit rate** are both robust and reproduce independently.

**Correctly-scoped claim:** *dedupe by `message.id` correctly removes the ~2.9x per-content-block
line inflation and the 94.7% hit rate is robust; but usage is NOT identical across duplicate
lines (18.2% differ, 6,444 with a zero-valued first line), so keep-first undercounts cache_read
~8% and input ~38% and over-reports cold prefix rewrites ~4%. Fix: keep the max/last non-zero
usage per id, and dedupe globally rather than per file.*

## (c) `skill_listing_audit.py` — CONFIRMED (stronger than claimed) + 1 OVERCLAIM

**Both-states CONFIRMED by my own mutants:** `binding()` forced to always return
`"NON-BINDING"` → `FAILED` exit 1; scan matching `"nope.md"` → `FAILED` exit 1;
original → `SUCCESS` exit 0.

**Counts CONFIRMED by an independently written parser + traversal.** My regex parser (no shared
code) reproduced **LOCAL 468 SKILL.md → 160,933 name+desc bytes BYTE-FOR-BYTE**. PLUGIN 2,167
(mine 949,873 B vs their 944,041 B — 0.6% parser delta, immaterial). Their junction claim holds:
comparing walked count vs distinct `os.path.realpath` gives **0** duplicates in LOCAL and **1**
in PLUGIN, so `os.walk` fixed a real glob undercount without double counting.

**STRONGER THAN THEY CLAIMED — truncation DIRECTLY OBSERVED, no arithmetic.**
This validator's own injected skill listing contains dozens of **bare-name** entries. I took 21
of them and read their SKILL.md frontmatter: **21/21 HAVE a description on disk (107–786 chars);
0 genuinely lack one** (`ralph-hats` 232, `re-triage-preflight` 786, `screenshot` 218, `semgrep`
399, `slides` 379, `yeet` 136, …). The live prefix is dropping descriptions **right now**. That
is direct observation of the truncation the tool predicts, with zero dependence on bytes/4.

**OVERCLAIM.** *"@1M cap 40,000 BINDS even on LOCAL alone (+233)"* rests on a **0.58% margin**
over a bytes/4 estimate. Sensitivity sweep on the identical byte count:

| chars/token | 3.5 | 3.8 | **4.0** | 4.2 | 4.5 | 5.0 |
|---|---|---|---|---|---|---|
| LOCAL tokens | 45,980 | 42,350 | **40,233** | 38,317 | 35,762 | 32,186 |
| verdict | BINDS | BINDS | **BINDS +233** | NON-BINDING | NON-BINDING | NON-BINDING |

English+markdown commonly runs ~4.2–4.5 chars/token, so the LOCAL-only verdict flips inside the
error bar. Consequently their *"REFUTED the task's 34,194-tok premise"* is only half-established:
the growth 415→468 skills / 136,778→160,933 B is **CONFIRMED**; *"local now exceeds the cap"* is
**UNRESOLVED**.

**Correctly-scoped claim:** *LOCAL+PLUGIN (276k tok vs a 40k cap, 6.9x) BINDS robustly, and
description-dropping is DIRECTLY OBSERVED in this session's live listing. Whether LOCAL ALONE
exceeds the cap is UNRESOLVED — it binds at ≤4.0 chars/token and does not at ≥4.2. Settling
experiment: count the listing payload with a real tokenizer, or count bare-name entries in a
local-skills-only session.*

**Ban honored — CONFIRMED.** `settings.json` independently parsed: `skillListingBudgetFraction`
= **0.04**, unchanged; `ENABLE_TOOL_SEARCH` = `true`.

## (d) `stable_prefix_lint.py` — OVERCLAIM: right conclusion, 27.9% of the evidence

**Both-states CONFIRMED by my own mutants:** `scan_volatile` forced to `return False, [], bare`
→ `FAILED` exit 1; `dangling.append(...)` removed → `FAILED` exit 1; original → `SUCCESS` exit 0.

**Report-only CONFIRMED.** Static scan for mutating/egress calls across all three scripts: every
`open(...,"w")` / `rmtree` / `unlink` is inside `run_selftest()` against `tempfile` paths. No
`subprocess`, `os.system`, `Popen`, `socket`, `urllib` or `requests` anywhere.

**Dangling @-import CONFIRMED by two independent signals.** `Test-Path ~/.claude/AGENTS.md` =
**False**; and this session's injected memory-file set lists `.claude/CLAUDE.md`,
`.claude/AGENTS-RUNTIME.md`, `~/AGENTS.md`, `~/CLAUDE.md` — and never `.claude/AGENTS.md`.

**OVERCLAIM.** *"the 4 always-on memory FILES (42,904 B ≈ 10,726 tok) are ALL stable … so cache
thrash is from tool-def/order/hook injection, not files."* The lint enumerates ONLY the CLAUDE.md
`@`-import chain. This session's prefix demonstrably ALSO injects `~/.claude/rules/common/*.md`
(24 of them visible in my own context) and `…/memory/MEMORY.md`:

| set | files | bytes | ~tokens |
|---|---|---|---|
| audited by the lint | 4 | 42,904 | 10,726 |
| **proven injected, NOT audited** | **25** | **110,661** | **27,665** |

**The lint covered 27.9% of the proven always-on bytes** — 2.6x more always-on bytes went
unexamined than examined. (An earlier pass of mine put this at 184 files / 917,732 B by counting
every per-note memory file; I narrowed it, because MEMORY.md is an INDEX and those notes are
on-demand, not always-on. Reporting the honest 25/110,661.)

**In the implementer's favour (checked deliberately).** Re-running the lint's own volatility
patterns across the missed set flags only 2 files — `hooks.md` and `research-coverage.md` — and
both are `gen-marker` FALSE POSITIVES on prose (*"Registration is generated"*, *"a generated
face"*). **MEMORY.md is CLEAN.** So the substantive conclusion survives; only its width fails.

**Correctly-scoped claim:** *No file in the CLAUDE.md @-import chain (4 files, 42,904 B) carries
per-turn-varying content. The rules/common tree and MEMORY.md — a further 110,661 B, 72% of the
proven always-on bytes — were never enumerated by the lint; an independent scan of them with the
same patterns finds no real volatility either, so the verdict holds, but the lint itself measured
only ~28% of it. Fix: add `~/.claude/rules/common/*.md` and the project MEMORY.md to the roots.*

---

## Hard-rule check — 0 VIOLATIONS

| # | Rule | Verdict | Evidence |
|---|---|---|---|
| 1 | authored vs deployed | **PASS** | No `rules/common` file touched by this lane. The 3 rules edited today (22:19–22:20) PREDATE the 22:47 edit and carry IDENTICAL mtimes on authored + deployed sides (sync-rules.ps1 shape). `~/.claude/CLAUDE.md` is NOT a deployed rules copy — `sync-rules.ps1` copies only `rules/common/*.md`, and the only `CLAUDE.md` hits across `~/.agents/scripts/*.ps1` are inside comments. Editing both mirrors byte-identically is correct. |
| 2 | `~/.claude.json` untouched | **PASS (instrument-limited)** | Integrity intact: parses with `-AsHashtable`, **88** root mcpServers, 45 project keys. mtime 23:08:09 is NOT attributable — 4 live sessions rewrite that file by design. No evidence of a lane edit. |
| 3 | no deletions | **PASS** | 88 MCP servers, plugins, 468 local + 2,167 plugin SKILL.md all present. Deletions were PROPOSED only (dangling AGENTS.md fix, plugin-cache curation) and applied nowhere. |
| 4 | no credential touch | **PASS** | No env-secret access, no egress in any script. The new CLAUDE.md block explicitly says *"credential or variable NAMES (never values)"*. |
| 5 | no process kills | **PASS** | No `subprocess`/`os.system`/`Popen`/kill in any of the 3 scripts. |
| 6 | no commit | **PASS** | `git status --porcelain` → ` M CLAUDE.md` unstaged + 3 scripts `??` untracked. `git diff --cached --numstat` **EMPTY**. HEAD `e04ffabc4` @22:21:20 predates the 22:47 edit. |
| 7 | both-states mandatory | **PASS** | Independently proven on all 3 scripts via 6 of my own mutants (4 material). |
| 8 | Windows shell | **PASS** | No truncation: trailing byte `0x0A`, all scripts parse and run. |
| 9 | write-as-you-go | **PASS** | Their artifact present at the declared path, 10,236 B. |
| 10 | net-negative | **PASS** | Stated per item; (a) honestly admits it retires nothing textual; (b) legitimately retires the scratchpad prototype. |
| 11 | VERIFIED/INFERRED + band | **PASS with a calibration miss** | Every claim is labeled. But the two claims I refuted/narrowed were labeled **VERIFIED ~97%** and **~95%** — over-confident, not unlabeled. |

## Regressions

1. **`lint-rules-loading.ps1` → `PASS: every authored rule is cited AND deployed`, exit 0.**
   No rules-loading regression.
2. **`settings.json` parses; `skillListingBudgetFraction` 0.04 and `ENABLE_TOOL_SEARCH=true`
   unchanged.** But it is now **27,825 B vs the task's ground-truth 27,209 B** (+616), mtime
   23:05:27 — changed by SOMETHING in this run. **Not this lane** (0.04 verified unchanged);
   orchestrator should attribute it to another lane.
3. **Prompt-cache invalidation across ≥5 live sessions** from the mid-session CLAUDE.md edit
   (context-reduction rule 10). Self-inflicted, undisclosed, ironic for a cache lane. Not a
   hard-rule violation.
4. **Pre-existing, not damage:** `~/.claude.json` throws on bare `ConvertFrom-Json` —
   duplicate-cased project keys (`C:/Users/Prekzursil` vs `C:/Users/prekzursil`). Any tool that
   parses it case-insensitively will fail. Recorded so it is not later blamed on this lane.

## Verdict

The lane shipped **4 real, runnable, side-effect-free artifacts** and broke **no hard rule**.
(a) and (c) are essentially sound — and (c) is in fact better supported than its author knew,
because truncation is directly observable in the live prefix. The two defects worth acting on:
**(b) keep-first dedupe loses data on 18.2% of messages and inflates the cold-rewrite count**,
and **(d) the stable-prefix verdict was written over all always-on files while measuring 28% of
them.** Both are fixable in a few lines.

SUCCESS:validate-context-prefix
