---
title: RULE-AUDIT-VERIFY-R3
type: note
permalink: dqverify-repo-20261013/docs/rule-audit/rule-audit-verify-r3
---

# RULERESEARCH — INDEPENDENT VERIFY of the round-3 BUILD claim

Auditor: independent VERIFY lane. Mandate: re-measure the builder's round-3 work by EXECUTION.
A digest is a claim, not a receipt.

COVERAGE: every gate in the builder's battery was re-run; every claimed file Test-Path'd; both
commits re-derived for scope with a controlled filter; §3.10, §3.1, §5b and the two undeployed
round-1 corrections independently re-measured with instruments the builder did not use.
NOT measured: the historical `ruff format` before/after `cmp` (round-2 state, unreachable now);
the `_r2_blobcheck` empty-index invocation (sibling lanes have staged files — see §4.2).

## 0. Environment

- repo: `C:/Users/Prekzursil/source/ast-integrate`
- HEAD at verify start: `f3a1410c` (siblings committed 5 times after the builder's last commit)
- builder's commits `0475e4a4` and `580e9160`: **both present in history**

## 1. Commits — CONFIRMED

| commit | claimed | measured |
|---|---|---|
| `0475e4a4` | 8 files, +1268 / −57 | 8 files, +1268 / −57 — exact |
| `580e9160` | 1 file, +52 / −1 | 1 file, +52 / −1 — exact |

Scope filter `git show --name-only --format="" <sha> \| grep -v "^docs/rule-audit/"` returns
**nothing** for both. **Detector controlled**: the identical filter on sibling `673cd180` emits
`docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md` (rc=0), so the empty result is a measurement, not a
broken matcher. No foreign path swept.

All 10 claimed files exist and are `git ls-files`-tracked.

## 2. Gate battery — re-executed, 11 of 12 exact

| command | claimed | my result |
|---|---|---|
| `r2_pathrefs.py` | 254 / 3 trees, 0 unwaived, 3 waived, 1 tracked, rc=2 | **exact**, rc=2 |
| `r2_pathrefs.py --self-test` | all 6 gate-level states, rc=0 | **exact**, rc=0 |
| `r3_corpus_parity_gate.py` | 254==254, mutant 176, both bindings, rc=0 | **exact**, rc=0 |
| `rule_audit.py --self-test` | 6/4/2/3/4 TOTAL=19, rc=0 | **exact**, rc=0 |
| `r2_control_count_gate.py` | 4 live == tool 19 == AST 19, rc=0 | **exact**, rc=0 |
| `r2_failclosed_mutation.py` | mutant rc=1, pristine rc=0 | **exact**, rc=0 |
| `lazy_predict.py` | 16/16 + 1/1, rc=0 | **exact**, rc=0 |
| `_r2_blobcheck.py --rev 7770f6e8` | 6 blobs, 0 CRLF, control fires | **exact**, rc=0 |
| `_r2_blobcheck.py --rev 0475e4a4` | 4 blobs, 0 CRLF, control fires | **exact**, rc=0 |
| `_r2_blobcheck.py --rev e3493fc8` | fail-closed rc=1 | **exact**, rc=1 |
| `pytest ci/tests/test_rules_*.py` | 167 passed | **167 passed** in 0.95s |
| `ruff@0.15.17 check` / `format --check` | passed / 20 formatted | **exact** |
| `rule_audit.py --json --md` | byte-identical, **rc=0** | **rc=2 — DEFECT, see §4.1** |  <!--argv-invalid-->

## 3. DoD — all four PASS on re-execution

**DoD-1 (classify always-on vs lazy by measured frontmatter) — PASS.** 254 files / 3 trees;
always-on 8 repo / 4 agent-self / 8 live. Regenerating to a temp path with the *correct*
invocation (`--json <path> --md <path>`, rc=0) and comparing to the committed artifacts:
`cmp` reports **both byte-identical**. Reproducible.

**DoD-2 (always-on token cost totalled) — PASS.** live always-on `15,141` tok; floor `23,050`
with memory files. Estimator caveat (`cl100k_base`, not Anthropic's tokenizer) is stated inline.

**DoD-3 (every contradiction measured + correction) — PASS on the honest scope.** §3 carries ten
sections, each with a correction; §3.10 is new. The artifact's own §3 header (`RULE-AUDIT.md:133-139`)
labels exhaustiveness **UNVERIFIED** and cites round 3 as direct evidence the earlier "every" was
false. That is the correct call — I did not attempt to certify "every".

**DoD-4 (no rule rewritten without evidence) — PASS.** Zero `rules/`, `AGENTS.md` or `agent-self/`
paths in either commit; `git status --short` for those paths is empty. **Detector controlled**: the
same grep on round-1 commit `23ee1622` fires, emitting `rules/README.md` and
`rules/common/single-signal-verification.md`.

## 4. Findings

### 4.1 REAL DEFECT (committed, durable) — a receipt that cannot run, certified as rc=0

`rule_audit.py --json --md` is an **argparse usage error**. Measured cleanly, no pipe masking:  <!--argv-invalid-->

```
EXACT rc of 'rule_audit.py --json --md' = 2
rule_audit.py: error: argument --json: expected one argument
--- stdout bytes: 0 ---
--- did the artifacts change? ---  rule-audit.json: OK   RULE-AUDIT-TABLES.md: OK
```

It regenerates **nothing**. The accompanying `cmp` "byte-identical" is therefore **vacuous when run
as written** — the artifacts are unchanged precisely because nothing was written. This is the
§3c shape (a control that cannot distinguish the two hypotheses), reproduced inside the receipt
table of the very report that writes the §3c calibration note.

Committed in TWO places, both added by `0475e4a4`:

- `docs/rule-audit/RULE-AUDIT-R3.md:275` — `rule_audit.py --json --md … rc=0`  <!--argv-invalid-->
- `docs/rule-audit/RULE-AUDIT-ADV-R2.md:24` — same command, `| 0 |`

The correct signature is documented by this same lane at `RULE-AUDIT.md:27`
(`--json out.json --md out.md`), so the author knew it; this is transcription, not fabrication.

**Classification: OVERCLAIM / false receipt, NOT a code defect.** The claim it supports is TRUE —
I proved reproducibility with the correct invocation. Fix the SENTENCE, not the code.

Scoped correction for both sites:
`python docs/rule-audit/rule_audit.py --json <path> --md <path>` → `SUCCESS:rule_audit` rc=0;
regenerated JSON and TABLES `cmp`-identical to the committed artifacts.

### 4.2 NOT a defect — one receipt unreproducible because the world moved

`_r2_blobcheck.py` bare mode (empty index → fail-closed rc=1) could not be reproduced: sibling
lanes have since staged `.py` files, so bare mode now measures 6 staged blobs and returns rc=0.
The fail-closed branch is a **single shared code path** (`_r2_blobcheck.py:54`) which I DID
exercise via `--rev e3493fc8` → rc=1. Mechanism proven; the specific invocation is state-dependent.

### 4.3 Independently re-derived — the builder's findings are REAL

- **§3.10** — `agent-self/config/rules/common/` ships **10** files, `windows-shell.md` not among
  them. Three instruments agree (`ls`, `find`, `git ls-files` all → 10 / no match). **Positive
  control**: the same basename resolves in `rules/common/` (18,586 B) and
  `~/.claude/rules/common/` (16,617 B), so BASENAME-ONLY is discriminating, not tree-wide failure.
  `agent-self/config/rules/README.md:74` does link it. `bootstrap.ps1:45` is exactly
  `Copy-Item (Join-Path $Self 'config\*') $ClaudeHome -Recurse -Force`.
- **§3.1 (highest severity, still unfixed)** — `agent-self/config/AGENTS.md` contains **0**
  occurrences of the live §9 bullet "NEVER remove, rotate, revoke…" (grep rc=1); live has **1**
  (rc=0). **Detector controlled** with a string that IS present → 3 hits, rc=0. Its §9b line 131
  says *"rotate, don't just delete"* where live `AGENTS.md:142-144` says *"per §9 you do not rotate
  it yourself … leave the rotation to the owner"*. A §9 non-negotiable inverted in a deploy source
  that is force-copied over `~/.claude`. **Owner decision, not another audit round.**
- **Residual #3** — `diff` confirms the repo corrections to `harness-vcs-hygiene.md` (13 lines
  incl. the `-Report json` WRITES warning) and `cross-vendor-dispatch.md` are **absent from the
  live tree**. Undeployed, as disclosed.
- **§5b** — 6 `rules/` dirs in-repo (2 corpus + 4 skill-bundled). Skill-bundled: **82** .md files,
  **78** with a frontmatter block, **0** with a `paths:` key. A presence check misclassifies 78; the
  schema check misclassifies 0. Claim exact.
- **The mutant's 176** — round 2's committed artifact really does read
  `rule files scanned: 176 across 2 trees` and `R2-7 … MEASURED: no`. Control: `grep -c 999999` → 0.
- **Parity gate is not hardcoded** — `importlib.import_module` on both modules (`:45-46`), reads
  `.TREES` live (`:106-107`), mutates a copy for the control (`:130-133`).
- **Honest residual verified** — the gate's third binding (`:109` empty tree map, `:114` zero-file
  corpus) exists and is genuinely unexercised, exactly as residual #6 declares.

## 5. Verdict

**PARTIAL.** All four DoD items pass when I execute them, and 11 of 12 gate receipts reproduce
exactly. PARTIAL is driven solely by §4.1: one committed receipt asserts rc=0 for a command that
returns rc=2 and writes nothing, and its paired `cmp` control is vacuous as written. The underlying
claim is true; the sentence is wider than its evidence.

Confidence: **ALMOST CERTAIN (90-99%)** on everything re-executed above — each is a direct
measurement with a controlled detector. The one claim I cannot certify is DoD-3's "every", which the
builder also declines to certify.