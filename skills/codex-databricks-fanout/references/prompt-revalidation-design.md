---
title: prompt-revalidation-design
type: note
permalink: dqverify-repo-20261013/skills/codex-databricks-fanout/references/prompt-revalidation-design
---

# Prompt Revalidation Pipeline — Design Spec

**Status:** owner-approved flow (brainstormed + grilled 2026-07-24). Awaiting spec review → implementation plan.

**Goal:** Revalidate the 4 large generated adoption prompts (workflow · CyberStrike · HackTricks ·
parallel-worktree orchestrator) before they are trusted or executed — first VERIFY + FIX them (Phase A,
no local mutation), then EXECUTE them for real in isolated worktrees to gated PRs (Phase B), with a human
go/no-go between.

## Approved pipeline

```
mechanical accuracy verifier (script)
  → judgment critics (sol + Opus, disagreement = defect)
  → fix-synthesis with anti-regression
  → meta-miss pass + dry-run smoke
  → human go/no-go
  → Phase B: 3 worktrees, install-lock, gated PRs
  → MCP promote as explicit post-merge manual DoD
  → all artifacts under generated-prompts/reviewed/ + verifier receipts
```

## Phase A — Verify + Fix (Databricks + Claude, no local mutation)

### A1. Mechanical accuracy verifier (deterministic script — closes the same-model independence gap)
- For EACH of the 4 prompts, extract every *checkable* claim: npm/pip packages + versions, file paths,
  git commits/tags, shell commands, MCP server entries, URLs.
- Verify each DETERMINISTICALLY against ground truth — `npm view <pkg>@<ver>`, path-exists in a fresh
  clone, `git cat-file -e <commit>`, URL reachability. A script, **not** an LLM opinion
  (fan-out-contract C4: if an algorithm can answer it, write the algorithm).
- Emit **verifier receipts**: per-prompt JSON `{claim, kind, verdict: pass|fail|unknown, evidence}`.
  A `fail` is an accuracy defect — model-independent and definitive (this is the layer that catches a
  hallucinated package/path the generator's own model would rubber-stamp).
- Component: `verify_claims.py` (a new review lane). Runs where it has git + npm + network.

### A2. Judgment critics (cross-model — sol + Opus)
- Per prompt, TWO critics on the JUDGMENT dimensions (security/§9, completeness-vs-spec, executability):
  **gpt-5.6-sol** (Databricks node) **and Claude Opus** (Claude subagent).
- **Disagreement between sol and Opus on any point = a flagged defect** to resolve — this is what surfaces
  a model-specific blind spot. Agreement on "clean" is a stronger pass than either alone.
- Output: per-prompt judgment defect-list carrying both verdicts + the disagreements.

### A3. Fix-synthesis (anti-regression)
- Per prompt, apply A1 accuracy defects + A2 resolved judgment defects → a CORRECTED prompt.
- **Anti-regression:** each fix is scoped; the synthesis diff-checks the corrected prompt against the
  original and MUST preserve all good content (fix the sentence, don't rewrite the doc), with a final
  "did any fix delete/regress good content?" check. (The overclaim discipline: most defects are
  overclaims, not broken content.)

### A4. Meta-miss pass + dry-run smoke
- **Meta-miss:** one agent per prompt asks "what did A1–A3 miss?" — an unchecked claim type, an un-run
  verification, a security angle not covered (completeness-critic pattern).
- **Dry-run smoke:** a light executability smoke — render each adoption prompt's concrete outputs (the
  `SKILL.md`, the MCP fleet JSON, the workflow-script skeleton) WITHOUT installing/wiring — confirming the
  steps are followable and the produced artifacts are well-formed.

### Human go/no-go
- Deliverable to the owner: the 4 corrected prompts + a consolidated defect report + the verifier
  receipts. Owner reviews and gives go/no-go **before any real adoption** (Phase B).

## Phase B — Execute for real (local ultracode → gated PRs)

### B1. Orchestration
- Run the CORRECTED orchestrator prompt (the 4th) over the 3 CORRECTED adoption prompts, each in its own
  git worktree (`isolation:'worktree'`) → own branch.
- **Concurrency:** all 3 worktrees run concurrently (git isolation is cheap), but a **global install-lock**
  serializes the heavy install steps (Bun/npm/MCP-server spawns) so only one installs at a time; run under
  **memguard** to avoid the known commit-freeze on this box.

### B2. Per-adoption gate
- Each adoption: execute → QZP 6-gate + platform matrix → commit → push branch → open PR. **Never
  auto-merge.** Owner curates.
- CyberStrike's offensive install happens only inside its isolated, gated worktree/branch; the PR to
  `agent-skills-toolchain` contains ONLY the skill + MCP config + docs — the AGPL/offensive tool never
  enters the repo (its install is a documented local step behind the merge).

### B3. MCP promotion = explicit post-merge manual DoD
- The CyberStrike + HackTricks adoptions wire the MCP fleet via `~/.mcp.json → promote → .claude.json`,
  which per the estate rule only works with **Claude Code CLOSED**. So each PR's Definition-of-Done carries
  an explicit MANUAL, post-merge, Claude-closed step ("close Claude, run the promoter, verify the server is
  exposed-but-disabled"). The worktree run stages the config; the live promotion is the owner's action.

## Artifacts
- All Phase-A outputs under `tools/databricks-fanout-harness/generated-prompts/reviewed/`: the 4 corrected
  prompts, the consolidated defect report, and the verifier receipts (JSON). Durable on the toolchain branch.

## Components to build
- `verify_claims.py` — claim extraction + deterministic checks + receipts (the A1 verifier).
- Phase-A driver — Databricks fan-out (verifier + sol judgment critics + fix-synth + meta-miss/smoke) plus
  Claude-side Opus judgment critics; a merge step feeds sol↔Opus disagreements into the fix-synth.
- Phase-B invocation — the corrected orchestrator prompt wrapped with the global install-lock + memguard.

## Known limits (stated, not hidden)
- Cross-model judgment still shares *some* blind spots (both are frontier LLMs); the mechanical verifier +
  the human gate are the real backstop, not model-count.
- The pipeline spans two rails: the Databricks node runs gpt-5.6-sol; Opus critics run as Claude subagents.
- Phase B mutates real repos on branches; nothing merges without owner curation; MCP promotion is a
  deferred manual step.