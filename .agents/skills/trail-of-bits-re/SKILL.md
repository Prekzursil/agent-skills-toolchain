---
name: trail-of-bits-re
description: Use when you want the Trail of Bits security/RE skill packs — differential-review (security-focused review of a code CHANGE, folding in git history to catch vulnerabilities a diff introduced), variant-analysis (find the SAME bug class across a codebase / other repos by pattern), and yara-authoring (write high-quality YARA-X detection rules with linting and atom analysis). Also the map to the rest of the trailofbits/skills marketplace (dwarf-expert, firebase-apk-scanner, constant-time-analysis, static-analysis, insecure-defaults, sharp-edges, semgrep-rule-creator, and more). These are advisory prompt/skill packs — Claude reasons with them, nothing auto-blocks. Install selectively (cherry-pick, do not bulk-install all 40 — catalogue tax). CC BY-SA 4.0.
origin: user
metadata:
  gem: E5-ida-multi-mcp
  upstream: https://github.com/trailofbits/skills
---

# trail-of-bits-re — Trail of Bits security/RE skill packs

`trailofbits/skills` is a **Claude Code plugin marketplace** of ~40 installable skill
packs distilling Trail of Bits' audit expertise. They are **prompt/skill packs** — no
runtime, no MCP server, no vector-DB — so they ride the native `/plugin` bus and add
zero always-on cost until invoked. Licensed **CC BY-SA 4.0** (attribution +
share-alike; keep the attribution if you fork a rule/skill).

This skill centers the three the `E.5` gem calls out, then maps the rest so you can
cherry-pick the RE/security-relevant ones without importing all 40 (catalogue tax —
see the `mcp-fleet-curation` discipline).

## The three core packs (the RE suite)

- **`differential-review`** — security-focused analysis of a **code change**. It folds
  in git history to spot vulnerabilities *introduced* by a modification (the class a
  plain unit-test diff sails past). Reach for it on PR review, a suspicious commit, or
  "did this refactor open a hole?" — complements the `security-review` skill (whole-
  branch) by focusing on the *delta* + its history.
- **`variant-analysis`** — once you have one confirmed bug, find its **siblings**: the
  same vulnerability *class* elsewhere in the codebase (or across repos) by pattern.
  This is the "we found CVE-X, where else does this pattern live?" workflow. Pairs with
  `semgrep-rule-creator` / `semgrep-rule-variant-creator` when you want to freeze the
  pattern into a reusable rule, and with the `qlty`/semgrep MCP to run it at scale.
- **`yara-authoring`** — author high-quality **YARA-X** detection rules (YARA-X is the
  Rust successor to legacy YARA) with linting, **atom analysis** (so your rule's
  literal atoms are actually selective, not a slow catch-all), and best-practice
  guidance. The most comprehensive pack in the collection. Reach for it whenever you
  turn a malware/sample finding into a durable signature — complements the RE stack
  (`ghidra-mcp`/`ida-pro-mcp`/`capa-triage`) by encoding what you found into detection.

## Install (selective — user/setup step)

Claude Code:
```
/plugin marketplace add trailofbits/skills
/plugin menu        # browse, then install ONLY the packs you need
```
Codex:
```
codex plugin marketplace add trailofbits/skills
codex plugin list
codex plugin add differential-review@trailofbits
codex plugin add variant-analysis@trailofbits
codex plugin add yara-authoring@trailofbits
```
Layout is `plugins/<name>/` per pack. **Do not bulk-install all 40** — pick the
RE/security-relevant handful below; every enabled pack is context budget you pay each
session it loads.

> `/plugin marketplace add` / install is an explicit `/plugin`-driven setup action —
> **outside this skill's file scope**. This skill documents the choice; it does not
> flip marketplace config for you.

## The rest of the marketplace — RE/security-relevant picks

Beyond the core three, these are the packs worth considering for this owner's RE /
Battle-Cats / security work (full set is ~40):

| Pack | Use it for |
|---|---|
| `dwarf-expert` | reading/reasoning over DWARF debug info in native binaries |
| `firebase-apk-scanner` | scan an APK for exposed Firebase/backend config (BC-adjacent) |
| `constant-time-analysis` | crypto side-channel / non-constant-time comparisons |
| `static-analysis` | drive static analyzers with expert framing |
| `insecure-defaults` | flag dangerous default configs |
| `sharp-edges` | language/API footguns that read as correct but aren't |
| `semgrep-rule-creator` / `semgrep-rule-variant-creator` | turn a finding into a reusable Semgrep rule / rule variants |
| `entry-point-analyzer` | map a program's real entry points / attack surface |
| `burpsuite-project-parser` | parse a Burp project file for web-app RE |
| `supply-chain-risk-auditor` | dependency / supply-chain risk pass |
| `zeroize-audit` | verify secrets are actually zeroized in memory |
| `second-opinion` | independent adversarial review of your own conclusion |
| `mutation-testing` / `property-based-testing` / `fp-check` | strengthen test signal / cut false positives |

(Others in the marketplace — `building-secure-contracts`, `rust-review`, `c-review`,
`modern-python`, `agentic-actions-auditor`, workflow/meta packs — are useful but
outside the RE core; install on demand.)

## How it rides the existing bus

- **Native `/plugin`** — no new runtime, no MCP, no daemon. Just skills Claude reads.
- **Complements, does not duplicate** — `differential-review` + `security-review`
  (delta vs branch); `variant-analysis` + `semgrep`/`qlty` MCP (reason vs run-at-scale);
  `yara-authoring` + the RE disassembler stack (encode a finding into detection); the
  offline `hacktricks` KB stays the first-stop reference lookup.
- **Advisory, not a gate** — these packs make Claude reason better; **none of them
  block, nag, or auto-fail** anything. That is by design and satisfies the shadow-first
  posture (there is no behavior gate here to shadow).

## Anti-overfit / posture

- Skill packs, not infrastructure — they reintroduce **no** rejected component (no
  vector-DB, no second orchestration runtime, no trained critic, no guardrail
  framework).
- **Selective install is the discipline** — bulk-enabling all 40 re-inflates the
  per-turn tool/token budget the `mcp-fleet-curation` skill exists to defend. Enable
  the RE core (3) plus a task-specific pick or two; retire what you stop using.
- **CC BY-SA 4.0** — if you copy/adapt a rule or skill body, keep the attribution and
  the share-alike terms.

## Verify

```bash
# skill is well-formed / vault-admissible (frontmatter parses, no angle brackets in description)
python - <<'PY'
import re, pathlib
p = pathlib.Path.home()/".claude/skills/trail-of-bits-re/SKILL.md"
t = p.read_text(encoding="utf-8"); fm = t.split("---",2)[1]
assert "\nname: trail-of-bits-re" in fm and "\ndescription:" in fm, "frontmatter missing"
desc = re.search(r"\ndescription:\s*(.+)", fm).group(1)
assert "<" not in desc and ">" not in desc, "angle bracket in description breaks quick_validate"
print("SUCCESS trail-of-bits-re SKILL.md well-formed")
PY

# after install, confirm the packs are present:
#   /plugin menu   (Claude Code)  or  codex plugin list  (Codex)
```
