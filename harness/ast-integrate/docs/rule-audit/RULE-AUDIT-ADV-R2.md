# RULERESEARCH — ADVERSARIAL VERIFICATION of BUILD round 2 (`7770f6e8`) and of the AUDIT that cleared it

Everything below was EXECUTED at `C:/Users/Prekzursil/source/ast-integrate`. Probe:
`docs/rule-audit/_adv2_probe.py`.

VERDICT: **build_is_sound = false** (one defect, executable-proven) · **audit_holds = false**
(the auditor named the gap, wrote the settling experiment, did not run it, and returned CLEAN).

COVERAGE: §1-§7 measured. Not measured: the non-path contradiction axes (command invocations,
cited line numbers, counted claims) — same residual the BUILD discloses; and absolute token truth
(`cl100k_base` estimate, `/context` not invocable from a subagent).

---

## 1. Everything the BUILD and AUDIT quoted reproduces

| probe | result | rc |
|---|---|---|
| `rule_audit.py --self-test` | `CONTROL-GROUPS: classifier=6 drift=4 crlf=2 encoder=3 failclosed=4 TOTAL=19` → `SUCCESS ... (19)` | 0 |
| `r2_control_count_gate.py` | `4 live prose claim(s) == tool 19 == AST 19 == group sum 19` | 0 |
| `r2_failclosed_mutation.py` | MUTANT rc=1 naming `FAIL STATE A ... rc=0`; PRISTINE rc=0 | 0 |
| `r2_pathrefs.py` / `--self-test` | `scanned=176 unwaived=0 waived=2 mentions=48`; 3 gate states pass | 0 / 0 |
| `_r2_blobcheck.py` (post-commit) | `FAILED:r2_blobcheck no staged .py files -- fail closed` | **1** |
| `rule_audit.py --json <p> --md <p>` | `SUCCESS:rule_audit`; regenerated JSON **and** MD byte-identical (`cmp`) | 0 |
| `lazy_predict.py` | `16/16 injected reproduced, 1/1 withheld` | 0 |
| `_adv_indep_classify.py` / `_adv_readme_block.py` | `compared=254 mismatches=0` / block matches tree | 0 |
| `pytest ci/tests/test_rules_*.py` | 167 passed | 0 |
| `ruff check` / `ruff format --check` on `docs/rule-audit/` | clean / 19 files formatted | 0 |

**REFUTED in round 4 — corrected in place, recorded rather than deleted.** The `rule_audit.py` row
above previously read `rule_audit.py --json --md`, with no values. <!--argv-invalid--> It exits **2** with
`error: argument --json: expected one argument` and writes nothing, so this table certified `0` for
a command that cannot run, and the `cmp` beside it was vacuous — the artifacts were unchanged
because nothing was written. The underlying claim holds when the command is run as it was actually
run (real paths: `SUCCESS:rule_audit`, rc=0, both artifacts sha256-identical). This is an overclaim
in an ADVERSARIAL artifact: the round-2 adversary re-executed eleven receipts and transcribed the
twelfth. `r4_receipt_argv_gate.py` now parses every documented invocation here with the tool's own
parser, and this line was one of the ten it failed on before the fix.

Commit `7770f6e8`: 9 files, all under `docs/rule-audit/`. Foreign paths NONE. Detector control:
the same filter on sibling `de77c002` emits `command-center/hook-audit/orchestrator-findings.md`,
so the empty result is a measurement. Zero paths under `rules/`, `AGENTS.md`, `agent-self/`.

**A SEVENTH independent reproduction of the classification model, which I did not arrange.** My own
turn-0 system prompt in this fresh session carried exactly 8 live rules — `agents`,
`bash-hud-and-terminal-emit`, `cross-vendor-dispatch`, `fan-out-contract`, `harness-vcs-hygiene`,
`single-signal-verification`, `stale-megapr-reconcile`, `windows-shell` — the 8 no-frontmatter
files and no others. After I read `.py` files the harness injected exactly 16 path-scoped rules
(11 `common/` + 5 `python/`) and withheld `common/hooks.md`. That is the harness itself agreeing
with `lazy_predict.py`, not a predictor agreeing with itself.

Independent re-derivation with a hand-rolled frontmatter parser (not the builder's):
`repo 88 / agent-self 78 / live 88 = 254`, always-on `8 / 4 / 8`, third bucket
(`frontmatter_without_paths`) **empty in all three trees**, live always-on `15,141 tok`, floor
`23,050`. Exact agreement with both prior lanes.

---

## 2. THE DEFECT — the round's headline sweep silently excludes 30.7% of its own corpus, and the excluded region is NOT empty

`r2_pathrefs.py:36` — `TREES = {"live": ..., "repo": ...}`. `agent-self/config/rules` (78 files)
is not swept. Adding it and re-running `main()` unchanged:

```
rule files scanned: 254 across 3 trees
  POSITIONAL path claims that do not resolve: 5
  WAIVED  live:README.md:104  ->  ../common/coding-style.md
  WAIVED  repo:common/cross-vendor-dispatch.md:36  ->  lib/job-control.mjs
  BASENAME-ONLY agent-self:README.md:74  ->  common/windows-shell.md      <- backtick token
  BASENAME-ONLY agent-self:README.md:74  ->  common/windows-shell.md      <- link target
  BASENAME-ONLY agent-self:README.md:138 ->  ../common/coding-style.md
FAILED:r2_pathrefs unwaived_path_claims=3 stale_waivers=0                 rc=1
```

Both waivers still fire, so nothing was invalidated by widening — the delta is purely the added
tree. Adjudicated at source, exactly as the BUILD adjudicates its own two:

* **REAL, and novel — the tenth path-axis contradiction.** `agent-self/config/rules/README.md:74`
  writes ``[`common/windows-shell.md`](common/windows-shell.md)`` while describing it as the
  cross-tool rule. `ls agent-self/config/rules/common/` returns 10 files —
  `agents, code-review, coding-style, development-workflow, git-workflow, hooks, patterns,
  performance, security, testing` — and **no `windows-shell.md`**. Control: the same filename IS
  present in both other trees (`rules/common/windows-shell.md` 18,586 B;
  `~/.claude/rules/common/windows-shell.md` 16,617 B), which is why the verdict is BASENAME-ONLY
  rather than MISSING. Two mechanically independent signals: the sweep's classification and a
  direct `ls`. Blast radius is bounded but real — `agent-self/bootstrap.ps1:45`
  (`Copy-Item (Join-Path $Self 'config\*') $ClaudeHome -Recurse -Force`) deploys this tree over
  `~/.claude`, so on THIS box the link happens to resolve against a `windows-shell.md` that
  pre-dates the deploy, but a **fresh bootstrap** ships a dead pointer.
* **Benign, needs the same waiver the BUILD already wrote.** `agent-self:README.md:138 ->
  ../common/coding-style.md` is byte-for-byte the same illustrative override-note quoted from the
  `rules/golang/` perspective that the BUILD waived at `live:README.md:104`. Read both: identical
  sentence. It is a probe limitation, not a rule defect.

**Why this blocks rather than being an honestly-scoped residual.** The floor says a disclosed
residual must not block. This one is NOT disclosed. Four `agent-self` mentions in
`RULE-AUDIT-R2.md` (`:92`, `:94`, `:195`, `:227`) — bootstrap, drift counts, the AGENTS.md finding.
None says the sweep skips that tree. Worse, §4's bounding paragraph exists precisely to enumerate
what is not covered and enumerates only AXES: *"other axes (command invocations, line-number
citations, counted claims) are still unmeasured"* (`:154-158`). The tree dimension is omitted from
the very sentence whose job is to bound the claim, while the artifact's own DoD-1 defines the
corpus as 254 files across three trees. `RULE-AUDIT-R2.md:29` therefore answers
*"is there a tenth contradiction on the path axis?"* with **"MEASURED: no."** — and that answer is
false for the corpus this artifact itself defines. The self-audit at `:256` checks that the claim
is *"scoped to the path axis in every place it appears"* and never checks the tree scoping.

This is the round's headline deliverable (8 files → 176), and the residual it left is non-empty.

**Fix, entirely inside lane scope, ~1 line of code.** Add `agent-self` to `r2_pathrefs.TREES`; add
the waiver for `:138` with its read reason; list `agent-self/config/rules/README.md:74` in
`RULE-AUDIT.md` §3 as contradiction #10 with its correction; rescope `:29`/`:108`/`:154`/`:234`
from "both trees" to "all three trees" once it is green. Editing
`agent-self/config/rules/README.md` itself is OUTSIDE the declared file scope — propose-only,
exactly like §3.1.

---

## 3. Attacks that FAILED — recorded so the one finding is not mistaken for a pattern

Four independent attempts to break the sweep found nothing. Each is a real measurement, not a
shrug.

* **Fence over-skip.** `references()` skips fenced blocks; an unbalanced ` ``` ` would silently
  swallow the rest of a file. Measured across all 254 files: **0 unbalanced-fence files**, 414
  pointer tokens outside fences vs **6** inside. The skip hides nothing material.
* **Five-base resolver permissiveness.** `classify()` returns EXACT if a token resolves under ANY
  of `REPO`, `~/.claude`, `~`, tree root, containing dir — so a live-tree pointer could be
  rescued by a repo file. Measured on the live tree: first-match tally
  `{containing_dir: 81, REPO: 15, tree_root: 2}`, and only **2** positional tokens resolve solely
  via the repo/home bases: `harness-vcs-hygiene.md:19 -> scripts/sync-from-live.ps1` (a rule about
  a repo script — correct) and `single-signal-verification.md:100 ->
  .agents/skills/claim-verify-gate/scripts/claim_gate.py` (resolves under `~`, correct). No false
  clean manufactured.
* **The mention/claim FIELD split.** `"/" in normalise_token(token)` drops bare filenames. The one
  arguable case is a leading `./`: 10 tokens become bare and are dropped. Read all 10 — 9 are
  `./git-workflow.md` / `./development-workflow.md` sibling links that resolve anyway, and the
  10th is `repo:README.md:91`, the line that *states* `./install.sh` does not exist. Correct
  use-vs-mention handling, not a hole.
* **Count-gate vacuity.** Runtime `len(ran)`, AST call-site count, and per-group sum are three
  genuinely different derivations; a `check()` moved into a loop or behind an early return would
  split them. The fail-closed path is reachable and I confirmed a marker cannot silence the whole
  gate. The gate also correctly picked up my new file in its glob (6 files scanned, not 5).

---

## 4. The AUDIT does not hold

The auditor's independent work was substantial and mostly excellent — a hand-rolled parser, its own
blob check, its own fail-closed harness, and four of its own detector failures disclosed rather
than buried. But the CLEAN verdict does not survive.

The auditor located this exact gap and described it precisely:

> `TREES = {"live", "repo"}` … `agent-self/config/rules` (78 files, 30.7% of the 254-file corpus)
> is NOT swept — and that is both the tree holding the highest-severity finding (§3.1) and a deploy
> source that `bootstrap.ps1:45` force-copies over `~/.claude`.

…then filed it as a non-blocking "SCOPING NOTE", concluded *"nothing stated is false"* and
*"None survived verification"*, and wrote the settling experiment itself — *"add it to `TREES` and
re-run"* — **without running it.** One command, already written out, returns `rc=1` on a real
broken pointer. That is the failure this program keeps repeating and the one my spawn prompt names:
reasoning about coverage where the instrument was one invocation away.

Two further problems with the audit as delivered:
* Its second scoping note is **truncated mid-sentence** (`"_r2_blobcheck.py EVIDENCE IS NOT"`), so
  part of its own reasoning is unreadable and cannot be checked.
* It reports `_r2_blobcheck.py` post-commit as *"correctly refuses"*. Confirmed rc=1 — but the
  consequence is that the BUILD's `SUCCESS:r2_blobcheck` evidence line is **not reproducible by
  anyone after the commit**. I verified it equivalently (committed blobs, 0 CRLF, `ruff` clean,
  mangled-copy control fires), so the claim is true; it is the *receipt* that is single-use.

---

## 5. What I did NOT change

No rule file, no `AGENTS.md`, no `agent-self/**`, nothing under `rules/`.
`git status --short -- rules/ AGENTS.md agent-self/` is empty. I added two files to
`docs/rule-audit/` (`_adv2_probe.py`, this artifact) and ran `ruff format` on my own probe so the
lane's `ruff format --check docs/rule-audit/` stays green; re-verified `r2_control_count_gate.py`
rc=0 with both new files present.

---

## 6. Confidence

**ALMOST CERTAIN (90-99%)** that the tenth contradiction is real: the missing file is confirmed by
two independent means, with a positive control (same filename present in the other two trees) and a
negative control (the sweep is silent on the two trees where it exists).

**ALMOST CERTAIN (90-99%)** that the exclusion is undisclosed: I enumerated every `agent-self`
occurrence in the artifact and read §4's bounding paragraph in full.

**LIKELY (55-80%)** that the three-tree sweep, once wired, finds nothing further — it found exactly
these 5 positional claims and I adjudicated all 5, but a third tree newly under the instrument
deserves one clean green before anyone says "closed".

**UNCERTAIN (20-55%)**, unchanged and inherited: every token figure is `cl100k_base` ±10-20%. My
independent count used the same encoder, so my agreement corroborates the arithmetic, not the
absolute truth. `/context` remains the only first-party receipt.

Calibration note: this program's base rate is ~7 overclaims per 5 real defects, and I went looking
for the widened sentence. On the *count* axis the BUILD scoped narrower than its evidence
(commendably). On the *tree* axis it scoped wider — "MEASURED: no" for a corpus it had measured only
two-thirds of. One defect, not a pattern.
