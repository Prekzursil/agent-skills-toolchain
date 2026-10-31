---
title: RULERESEARCH-GROUNDING-R2
type: note
permalink: dqverify-repo-20261013/docs/rule-audit/ruleresearch-grounding-r2
---

# RULERESEARCH lane — grounding round 2 (delta since R1)

STATUS: MEASURED. Lane = RULERESEARCH (grounding). No production code written; no rule edited.
HEAD at measurement = `27da3215`. Claude Code `2.1.228`.

If it still reads this way, the unit died before measuring anything and no verdict here may be cited.
(Skeleton sentinel retained verbatim per the write-as-you-go mandate. Sections below ARE measured;
see COVERAGE for what is not.)

COVERAGE
- MEASURED: fresh frontmatter classification across 3 trees; always-on token totals; CI
  reachability of all 8 rule-audit gates (with a both-directions detector control); repo↔live
  drift; status of 2 flagship contradictions in both trees; the credential inversion; whether
  `InstructionsLoaded` is wired anywhere.
- UNMEASURED: Anthropic-tokenizer counts (cl100k_base estimates, ±10-20%); compaction behaviour
  of lazy rules (§6, new axis, never probed by any round); the other 7 contradictions from R1 were
  not individually re-measured this round — only 4.2 and 4.3 were.
- Probe: `docs/rule-audit/_r5_grounding_probe.py` → `_r5_out.json`. Read-only.

**This round's single most important output is negative: the DoD was already met by a prior lane.
Do not rebuild it.** See §1.

---

## 1. Prior art — the DoD is DONE. Do not re-measure it.

`docs/rule-audit/` already holds **4 completed audit rounds + 3 adversarial rounds + 2 verify
rounds**, 8 gate scripts, and a 123 KB machine-readable inventory. Commit `23ee1622` is literally
titled *"classify all 254 rules by measured frontmatter, total the always-on cost, correct 9
rule-vs-reality contradictions"* — that is this lane's Definition of Done, already shipped.

| artifact | what it already establishes |
|---|---|
| `RULE-AUDIT.md` (39 KB) + `rule-audit.json` (123 KB) | full classification + contradiction census |
| `RULE-AUDIT-R2/R3/R4.md` | 3 successive correction rounds |
| `RULE-AUDIT-ADV-R2/R3/R4.md` | adversarial re-execution; R4 verdict "build is SOUND" |
| `RULE-AUDIT-VERIFY{,-R3}.md` | independent DoD re-execution |
| `rule_audit.py`, `lazy_predict.py`, +6 gates | executable checks |
| `RULERESEARCH-GROUNDING.md` | this lane's R1 output |

**`RULE-AUDIT-INTEGRATE.md` is a dead skeleton** — every section still reads
`UNKNOWN - not yet measured`. The INTEGRATE lane died before measuring anything, and by its own
sentinel no verdict in it may be cited. Its §2 asks *"is any rule-audit gate actually wired into
CI?"* — §3 below answers it.

## 2. Classification + token cost (DoD-1/2) — reproduced, with a 4th live replication

| tree | files | always-on | lazy | always-on tok | all tok |
|---|---|---|---|---|---|
| repo `rules/` | 88 | **8** | 80 | **17,107** | 63,294 |
| live `~/.claude/rules/` | 88 | **8** | 80 | **15,141** | 54,426 |
| `agent-self/config/rules/` | 78 | 4 | 74 | 1,201 | 38,008 |

The always-on 8 (identical in repo and live, all `common/`): `agents.md`,
`bash-hud-and-terminal-emit.md`, `cross-vendor-dispatch.md`, `fan-out-contract.md`,
`harness-vcs-hygiene.md`, `single-signal-verification.md`, `stale-megapr-reconcile.md`,
`windows-shell.md`.

**Fourth independent live replication, this session, both halves:**
- turn 0: my own system prompt carried **exactly those 8** rule files and no others — 8/8, zero
  false positives across 88 candidates.
- turn 1: after I read a `.py` file, the harness injected **16** path-scoped rules (11 `common/`
  + all 5 `python/`). Negative control fired: `common/hooks.md` (globs `**/hooks/**`,
  `**/settings*.json`, `**/.claude/**` — none matching) did **not** arrive.

This matches `lazy_predict.py`'s `OBSERVED_INJECTED` set exactly. Confidence the model is correct:
**almost certain (90-99%)**.

Drift note, disclosed: repo always-on is **17,107** tok here vs **17,069** at R1 (+38). Small and
unattributed — I did not bisect which file moved. Not load-bearing for any verdict below.

## 3. HEADLINE — 0 of 8 rule-audit gates are wired into CI (MEASURED)

Searched 114 CI-executable files (`.github/workflows/*.yml`, `ci/**`, `scripts/**`, root
`*.toml`/`*.cfg`) for each gate's filename and module stem:

| gate | CI-wired |
|---|---|
| `rule_audit.py` | **NO** |
| `lazy_predict.py` | **NO** |
| `r2_control_count_gate.py` | **NO** |
| `r2_failclosed_mutation.py` | **NO** |
| `r2_pathrefs.py` | **NO** |
| `r3_corpus_parity_gate.py` | **NO** |
| `r4_credential_rule_gate.py` | **NO** |
| `r4_receipt_argv_gate.py` | **NO** |

**DETECTOR CONTROL, both directions, VALID:** the same search finds the known-wired
`test_rules_integrity` in `.github/workflows/quality.yml` (positive fires) and does **not** find a
bogus token (negative silent). So "NO" is a measurement, not a broken matcher.

Consequence: four rounds of gate-building — including the credential gate and the fail-closed
mutation gate — **never execute**. They are documentation that happens to be Python. This
independently corroborates ADV-R4 §4 ("Neither nonzero script is CI-wired").

**Proven pattern available:** the sibling MCP-audit lane hit the identical gap and closed it at
HEAD — `27da3215 ci(mcp-audit): wire the lane's 14 gates into CI -- none of them ran, and 5 could
not`. Copy that wiring shape; do not invent one. Note its own commit message says 5 of 14 *could
not* run once wired — expect the same discovery here, which is the point of wiring them.

## 4. HEADLINE — the corrected rules were never deployed; live is still wrong

repo↔live drift is **29 of 88 files**, and **7 of 8 always-on rules differ** (only
`stale-megapr-reconcile.md` matches). At R1 this was 28/88 and 6/8 — it is getting **worse**, not
better. No file is only-in-repo or only-in-live (name sets identical).

| contradiction | repo | live |
|---|---|---|
| 4.2 `harness-vcs-hygiene.md` — bare `-Report json` **writes** (data loss) | FIXED (`-Drift -Report json`) | **STILL WRONG** |
| 4.3 `cross-vendor-dispatch.md` — §1 contradicts AGENTS.md §4a and its own §7 | FIXED ("Reconciliation with AGENTS.md §4a") | **STILL WRONG** |

**Fifth signal, from inside this agent:** my own always-on turn-0 context carries the live
`harness-vcs-hygiene.md`, which reads *"`scripts/sync-from-live.ps1` (`-Report json` to see drift,
`-WhatIf`, then a scoped commit)"* — the data-loss form, missing `-Drift`. I am being instructed by
the defective copy while auditing it. Likewise live `cross-vendor-dispatch.md` §1 bans
`run_in_background` while its own §7 mandates `longrun`.

**Detector honesty:** my probe reported `wrong=True` for repo 4.2 as well. That is a
**use-vs-mention false positive in my own probe** — the repo file contains the string only inside
its correction (*"Bare `-Report json` WRITES"*), while the actual recommendation is
`-Drift -Report json`. The repo file is correct; my substring matcher was not. Flagged rather than
quietly dropped, because it is the exact defect class this audit catalogues.

## 5. HEADLINE — the credential inversion is STILL LIVE (owner action)

| probe | result |
|---|---|
| `agent-self/config/AGENTS.md` contains "NEVER remove, rotate, revoke…" | **False** (absent) |
| `agent-self/config/AGENTS.md` contains "rotate, don't just delete" | **True** (inverted) |
| live `~/.claude/AGENTS.md` contains the prohibition | **True** |
| `agent-self/bootstrap.ps1:45` `Copy-Item (Join-Path $Self 'config\*') $ClaudeHome -Recurse -Force` | present |

The repo's deploy source **instructs the opposite of the standing §9 security non-negotiable**, and
one `pwsh agent-self/bootstrap.ps1` force-copies it over `~/.claude`. `f27dbb93` gave it a tracker
and `r4_credential_rule_gate.py` was written for it — but that gate is in the unwired set (§3), so
nothing detects it. Correctly left unfixed by prior lanes (out of write scope; owner handles
credential policy). **Still the highest-severity open item.**

## 6. NEW axis no round has covered — lazy rules do not survive compaction

First-party docs, quoted: *"Project-root CLAUDE.md survives compaction… Nested CLAUDE.md files and
rules with `paths:` frontmatter are **not** re-injected automatically; they reload the next time
Claude reads a file matching the rule's patterns."*

On this estate that means **80 of 88 rules — including `owner-ops-authorization.md`,
`ci-hygiene.md`, `security.md`, `code-review.md` — silently leave context at every `/compact`** and
stay gone until a matching file is touched. Long autonomous sessions here compact routinely. No
audit round measured this. UNVERIFIED for this estate specifically; settling experiment: `/context`
immediately before and after a `/compact`, diffing the Memory-files list.

## 7. NEW instrument — `InstructionsLoaded` hook is unused

Docs: *"Use the `InstructionsLoaded` hook to log exactly which instruction files are loaded, when
they load, and why. This is useful for debugging path-specific rules or lazy-loaded files."*

Measured: the token appears **nowhere** in live `settings.json`, `hooks/_dispatch/manifest.json`,
`hooks/**`, or `ci/**`. Control: the same search finds `PreToolUse` in that manifest, whose four
wired events are `SessionStart, Stop, PostToolUse, PreToolUse`.

This is a first-party instrument that would convert the entire always-on/lazy classification from a
**frontmatter parse** into a **harness receipt**, and would settle §6 mechanically. Every round so
far has inferred load behaviour; this measures it.

## 8. External SOTA

- **Official memory docs — settles the load model verbatim:** *"Rules without `paths` frontmatter
  are loaded at launch with the same priority as `.claude/CLAUDE.md`"*; *"Rules without a `paths`
  field are loaded unconditionally… Path-scoped rules trigger when Claude reads files matching the
  pattern, not on every tool use."* This is first-party confirmation of the inverse-intuition
  corollary in this lane's charter: adding `paths: ["**/*"]` **demotes** a launch-loaded rule.
  Also documents `/context` → **Memory files**, `claudeMdExcludes`, and the `InstructionsLoaded`
  hook. https://code.claude.com/docs/en/memory
- **Inverse defect report** — [#16299](https://github.com/anthropics/claude-code/issues/16299)
  claims path-scoped rules load *globally regardless of* `paths:`. Does **not** reproduce on
  2.1.228: my negative control (`common/hooks.md` withheld) refutes it directly. Recorded so the
  next reader does not re-alarm — the same trap R1 hit with the #16853 cluster.
- Community corroboration of the cost model (unscoped rule == second CLAUDE.md; path-scoped == zero
  cost until triggered): [zenn.dev loading-mechanism writeup](https://zenn.dev/yottayoshida/articles/claude-code-context-cost-structure?locale=en),
  [claudefa.st rules-directory guide](https://claudefa.st/blog/guide/mechanics/rules-directory).

## 9. Ranked plan

1. **Wire the 8 rule-audit gates into CI** (§3). Highest leverage: it makes four rounds of existing
   work executable instead of decorative. Copy the shape from `27da3215`. Expect some gates to fail
   once wired — that is the finding, not a setback. Give the wiring a both-states control (a
   synthetic violation must turn CI red).
2. **Deploy the corrected `rules/common` to live** (§4): `pwsh scripts/sync-rules.ps1 -WhatIf`,
   read the list, then the real run. This lands the data-loss fix and the dispatch reconciliation
   where agents actually read them. Costs ≈ +1,966 tok/turn. Do **NOT** use `sync-from-live.ps1`
   (that is the tool §4.2 is about, and its live doc is the wrong one).
3. **Escalate the credential inversion to the owner** (§5) — do not fix in-lane. Once (1) lands,
   `r4_credential_rule_gate.py` will hold the line automatically.
4. **Add a repo↔live parity gate** (§4). Drift went 28 → 29 while 167 tests stayed green, because
   every test reads `rules/` and `agent-self/`, never `~/.claude/rules/`. Confirmed use-vs-mention:
   the only two CI references to `.claude/rules` are a **docstring** and a **comment**, not reads.
   `pytest.skip` when `~/.claude` is absent (CI has none).
5. **Wire `InstructionsLoaded`** (§7) and re-derive the classification from its log. Converts the
   DoD from parse to receipt and settles §6 in the same stroke.
6. **Measure the compaction hole** (§6). New axis, cheap, and it may be the largest real-world
   correctness gap in the fleet: the security and CI-hygiene rules are all lazy.
7. **Run `/context` once** and paste the Memory-files block in — converts every token number here
   from cl100k estimate to first-party receipt. Still not done after two rounds.
8. **Add a load-semantics gate**: no rule may change frontmatter-presence relative to its sibling
   trees without an allowlist entry — catches `bootstrap.ps1` silently promoting 3 lazy rules to
   always-on.
9. **Fill or delete `RULE-AUDIT-INTEGRATE.md`** (§1). A skeleton in a directory of finished audits
   invites a future reader to cite `UNKNOWN` as a finding.

Explicitly NOT recommended: (a) re-running the classification/contradiction census — it exists and
reproduces (§1, §2); (b) re-scoping any rule's frontmatter on the strength of #16299 — it does not
reproduce here; (c) consolidating the three rule trees before (4) exists, since without a parity
gate the merge cannot be shown not to have lost content; (d) treating the 167 green tests as
coverage of the deployed tree.