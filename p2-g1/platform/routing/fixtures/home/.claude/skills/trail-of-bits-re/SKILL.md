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

### Install (selective — user/setup step)
### The rest of the marketplace — RE/security-relevant picks
### How it rides the existing bus
### Anti-overfit / posture
### Verify
### after install, confirm the packs are present:
### /plugin menu   (Claude Code)  or  codex plugin list  (Codex)
