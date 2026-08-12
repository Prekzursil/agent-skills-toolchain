# Single-Signal Verification (two independent signals before a load-bearing claim)

**A single tool's silence or single reading is NOT evidence.** Before asserting that something
is *absent*, *broken*, *stuck*, or *done* — especially when the next action is disruptive (a
restart, a kill, a "re-fix", a rollback) — corroborate with a SECOND, mechanically-independent
probe. If the two disagree, the first was likely a measurement artifact, not ground truth.

This is the most expensive recurring failure mode. SIX live instances in ONE session
(2026-07-18), every one a wrong conclusion from a single unverified signal:

| Wrong claim | Single signal (the artifact) | Independent signal that corrected it |
|---|---|---|
| "ctx 100% — restart the run" | cumulative `total_token_usage` as the ctx numerator | **last-turn** `last_token_usage / window` (the real occupancy) |
| "agents are stuck / 0 KB" | a stale cached file-size snapshot | CPU-delta over 20 s **AND** byte-growth of the err logs (86-142 KB, climbing) |
| "`mon` is not on PATH" | `which mon` in **Git-Bash** (ignores `.cmd` shims) | `Get-Command mon` in **PowerShell** → resolves `mon.cmd` |
| "the board always dies" | a `-match` regex with `\c` (a .NET control-char escape → never matched) | fix the regex → four surviving boards were there all along |
| "codex agents are fire-and-forget" | turn-count alone (3 turns ⇒ didn't wait) | **wall-clock delta** (a 3-turn peer blocked 20m35s) **AND** the literal `--background` token in the command string — both one grep away |
| "the Remove-Item guard was a true positive" | the blocked command's **payload** (a doc body quoting `Remove-Item`) | the `tool_use` **input verb** — both fires were `Set-Content` writing markdown, 2/2 false positives |
| "the FB/WhatsApp MCP has no auth" (2026-07-19) | `fb_account_list` / `wa_account_list` → `accounts: []` (the *alternate-profile store*) | `whoami` → live `{uid, name}` **AND** `wa_search_messages` → real messages with `is_from_me` — the session WAS authenticated; `[]` meant "no alternate profiles", a different field |
| "the PR is BLOCKED = its checks are missing" (2026-07-19) | `mergeStateStatus: BLOCKED` read as "not yet run" | the `quality` run's `conclusion=failure` — the checks had **run and failed**; BLOCKED ≠ pending. Fixing one gate then revealed the next (jobs stop at the FIRST failing step) |
| "the MCP disable took effect" (2026-07-19) | `disabledMcpServers` present at **root** of `~/.claude.json` | the **process table** (320 live MCP procs, disabled servers spawning 10 min post-restore) **AND** the pre-restore backup (key lived per-*project*, not root) — root-scope was inert |
| "the hooks.json fix is verified" (2026-07-19b) | `codex exec` stderr showed no parse error | the **desktop Hooks panel** — the probe printed nothing in the **broken state too**, so its silence was meaningless (see the both-states rule below) |
| "`bash` will run this hook" (2026-07-19b) | `command -v bash` in Git Bash → `/usr/bin/bash` | `Get-Command bash` in PowerShell → `C:\WINDOWS\system32\bash.exe` = **WSL**, which mangles Windows paths and rejects CRLF. The MSYS view is not what a Windows process spawns. |
| "hyperframes is unused / nothing is enabled" (2026-07-19b) | `enabledPlugins` empty at root of `~/.claude.json` | `~/.claude/settings.json` holds the **real** map — `hyperframes=false`, `metaswarm=true`. Right key, wrong file. |
| "the vendored constant drifted to 0" (2026-07-19b) | regex `[<>=]{1,2}` "comparison" match | it also matches a bare `=`, so the `size = 0` **initialiser** read as a threshold. Use `(?:<=\|>=\|<\|>\|==\|!=)`. |
| "CI has no checks / can't tell" (2026-07-19b) | `gh pr checks` errored on PAT scope | `gh run list --branch` → `quality` + `no-runtime-junk` both **success**. A tool's auth failure is a DETECTOR failure, never a verdict. |
| "the test suite protects this constant" (2026-07-19b) | 15/15 green | **mutation test**: reverting `DEFAULT_MIN_BYTES` 1024→512 still passed, because every case passed `min_bytes` explicitly and the default was never exercised |
| "a rule with no `paths:` frontmatter is never loaded" (2026-08-07) | an assumption, never probed — then acted on by "arming" files | the **inverse** is true: the 8 files with NO frontmatter are exactly the 8 injected at turn 0; the other 12 in `common/` (80 tree-wide) carry `paths:` and load lazily on a matching touch — re-measured 2026-08-12 with a negative control, `docs/rule-audit/lazy_predict.py`. Adding `paths: ["**/*"]` DEMOTES an always-on rule. `check_no_regression.py` INV-6 had been printing `frontmatter={owner-ops-authorization.md: True, ci-hygiene.md: True}` all session — a list that never contained the two files believed to be armed |

**Read your own instrument — the dominant failure is RECALL, not detection.** Measured 2026-08-07/08:
**seven** load-bearing claims in ONE session were confidently wrong, and not one was a detector
failure. In every case the correct answer was already available and simply unread: the gate's own
output printed on every run; a three-week-old basic-memory DECISION note carrying the complete fix
design; `ci-hygiene.md` §4 (squash-merge makes a MERGED branch report as `ahead` — the fix was
merged and pushing it would have **reverted 74 lines** of hardening); a 24 KB
`hooks/_shared/use_vs_mention.py` declared "unbuilt"; two benchmarks that measured EMPTY inputs and
returned a clean, meaningless green; and an inference about which files a tool loads, taken over a
direct measurement (`grok inspect --json`) that was available the whole time.

So: before asserting a thing is absent, broken, novel, or unbuilt, **search for it**. Run recall
(`basic-memory`), read the gate output you just produced instead of skimming it, and `grep` the tree
for the thing you are about to declare missing. A green gate you did not read is a signal you did
not take, and a documented defect class does not protect you if recall is never run. When a claim
and an instrument you are already running disagree, **the instrument wins**.

## The rule

1. **Absence/failure needs corroboration; success needs corroboration.** "Nothing there",
   "it crashed", "it's done" — each is a claim, not an observation, until a second independent
   probe agrees.
2. **The two signals must be mechanically independent** — a different shell, a different data
   field, a different measurement (process CPU vs file mtime vs byte-count), not the same query
   re-run. Re-running the same probe is not a second signal.
3. **Verify the detector before trusting the absence.** A "0 results / not found / 0 alive"
   reading is often a broken matcher, wrong shell, wrong path, or stale cache — check that the
   detector *can* find a known-present item before concluding nothing is present.
3b. **The both-states test (the sharpest form of rule 3).** Before a probe's silence counts as
   "fixed", run it against the **known-BROKEN** state and confirm it FIRES there. A probe that is
   silent in both states measures nothing. Measured 2026-07-19b: a `codex exec` probe printed no
   parse error either before or after the fix, and was one step from being reported as
   verification. The same discipline applied to a TEST SUITE is **mutation testing** — revert each
   real bug in turn and require the suite to go red; a suite that stays green is not protecting
   that behaviour. One of six C1 mutations survived and exposed a genuine hole in the tests.
3c. **A control that cannot distinguish the two hypotheses is not a control — it only proves the
   instrument ran.** This is the failure mode 3b does *not* catch, and it is more seductive because
   the control PASSES and you record it as diligence. Measured 2026-08-12 on
   `hooks/_dispatch/manifest.json`: `manifest["events"][<event>]` is a **dict**
   (`{settings_matcher, settings_timeout, checks}`), not a list of hooks, so iterating it yields the
   three KEY NAMES and `len()` reports "3 modules" for every event on both sides. Live and repo
   therefore compared **equal** — while a lens had correctly measured `PreToolUse live=5 repo=7`,
   including the missing producer that makes `/rollback` a promise the harness cannot keep. A
   detector control was run and it passed: it confirmed the first entry parsed as
   `settings_matcher`. That is the *wrong collection*, one level above the hooks, so the control
   proved only that the file was readable. Four successive probes agreed with each other and all
   four were wrong.
   - **The test:** state the two hypotheses first (`H1: surfaces are identical` vs `H2: repo has
     hooks live lacks`), then ask what the control's PASS would look like under each. If it looks
     the same under both, the control is inert — it is measuring readability, not the claim.
   - **Cheapest fix:** make the control a COUNT of the thing you are actually comparing, and fail
     closed when it is implausible. The corrected reader prints `found 25 live checks across 4
     events` and exits non-zero at zero, so a shape change is loud instead of reporting parity.
   - **Tell:** a suspiciously round, suspiciously equal number on both sides (here, "3 and 3" four
     times) is more often a collection-level mistake than genuine parity.
   - **When your probe and someone else's disagree, this is the first thing to suspect in YOUR
     probe** — rule 4 of the fan-out contract says the specific probe wins over the agent count, and
     that cuts against your own instrument too.
4. **Terminal-state discipline (AGENTS.md §4):** `DONE` only on receipt **AND** postcondition;
   `FAILED`/`STALLED` only on an AND-gate of ≥2 signals — never single-signal, never CPU-alone,
   never mtime-alone.
5. **A subagent's finding is a single signal too.** N subagents asserting the same thing is
   still one lens if they read the same stale input — verify load-bearing subagent claims
   against the real config/code before acting (this rule caught a "ground truth" that three
   design agents carried forward from a stale premise).
6. **Declare the SOURCE probe, not just the verifier — an undeclared source is zero signals,
   not one.** Independence is a property of a *pair*; with only the verifier recorded there is
   no pair to compare and nothing to certify. State both: what measurement PRODUCED the claim,
   and what mechanically different measurement CHECKED it.
   - **Mechanizing this rule inherits the obligation.** A gate that compares probe fingerprints
     must treat a missing/empty source as a VIOLATION, never as "differs from the verifier, so
     independent". Measured on `.agents/skills/claim-verify-gate/scripts/claim_gate.py`:
     `_validate()` (`:132-156`) requires an id, text, and recognized verdict but **not**
     `source_probe`; at `:173-185` an absent source normalizes to four empty strings, which any
     non-empty verifier trivially differs from, so the `same-probe-rerun` check cannot fire. A
     `CONFIRMED` claim with no `source_probe`, one verifier, and a syntactically valid evidence
     anchor returns `"violations": []`, `"ok": true`, exit 0 — the gate certifies corroboration
     for a claim that declares no producing measurement at all. That contradicts the caller's
     own prose at `.agents/skills/claim-verify-gate/SKILL.md:66-68`. Require a non-empty
     `source_probe` for any `CONFIRMED`/`REFUTED` verdict *before* comparing fingerprints.
   - **A green suite is not coverage of this path.** The shipped regression reported all 30
     test functions passing while the hole was live: its missing-probe case omits the
     *verifier*, not the *source*. Test the absent-source direction explicitly (rule 3b).

## When it bites hardest
Long autonomous loops, fan-out monitoring, RE offset work, "is it done yet" polling, and any
moment the *fix* is disruptive (restart / kill / force-push / rollback). The cost of a second
probe is seconds; the cost of acting on a false signal is a wasted restart, a killed sibling,
or a wrong "done". Pairs with `fresh-context-verify` (re-derive a load-bearing value in a clean
context) and the two-strikes pivot (AGENTS.md §4b).

**Auditors are not exempt.** In this same session an audit agent reproduced the exact failure it
was documenting — reading a blocked command's *content* instead of its *verb* — and shipped the
opposite of a sibling audit's correct verdict. Two same-level reports that disagree are a
resolve-from-raw-source trigger, never a pick-one trigger.


## Four more detector shapes, measured PROMPT-1.5 (2026-07-21)

Twelve self-inflicted detector failures occurred in one program. The rule above already covers the
principle; these are the SHAPES, because each looked like a finding until a second probe disagreed.

| shape | wrong reading | why |
|---|---|---|
| `grep -c pat \|\| echo 0` | reported **all 7 PRs hit** AND an **empty intersection**, in one run | `grep -c` prints `0` **and** exits 1, so `\|\| echo 0` also fires -> `"0\n0"`, which `!= "0"` |
| a process probe whose pattern is in its OWN command line | a dead session reported **ACTIVE**, twice | `Win32_Process` matched the probe itself. Tell: the reported `CreationDate` equals the probe's own run time |
| comparing two DIFFERENT files | `record.py` vs `stubscan.py` -> "DRIFTED" | of course they differ; compare like with like |
| `pytest <dir>` on a standalone script | `INTERNALERROR> SystemExit: 0` read as a failing suite | the file calls `sys.exit()` at module level; run it through its own entry point -> 174 passed |

**A self-contradicting output is a detector failure, not a finding.** If one run reports two things
that cannot both be true, stop and fix the instrument before reading either number.

**Corollary — equality to a pinned SHA is a self-falsifying safety check.** Asserting "peer tree @
`<sha>`, N modified" as an invariant raised **three** false alarms while a human committed to that
tree legitimately. Use invariants that survive concurrent work instead:
  (a) the baseline commit remains an ANCESTOR of HEAD (no history rewrite), AND
  (b) every intervening commit is OWNER-authored, not agent-authored, AND
  (c) no changed/untracked path carries a unit name from your program, AND
  (d) no agent performed a write against that tree.
Detector weakness to disclose when using it: author identity is forgeable -- corroborate with the
changed-path surface.
