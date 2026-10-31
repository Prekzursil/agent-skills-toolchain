---
name: claude-prompt-forge
description: Prompt-forging skill for Claude Code and long autonomous Claude sessions
  — the prompt analogue of grill-me-extensive. Builds orchestration, session, unit,
  and handoff prompts with resume-don't-restart preambles, both-states evidence contracts,
  AND-gate completion, hard safety bans, and unit sentinels so work survives compaction
  and resists false greens. Use when writing or hardening a multi-phase Claude prompt,
  when a prior prompt caused restarts or false completion, or when the user says forge
  a prompt, prompt for Claude Code, make this prompt robust, orchestration prompt,
  session prompt, or handoff prompt.
permalink: dqverify-repo-20261013/skills/claude-prompt-forge/skill
---

Forge prompts that drive Claude (especially Claude Code) through multi-phase autonomous work without restarting completed gates, trusting uncontrolled zeros, or claiming success from partial evidence.

This skill is the prompt analogue of `grill-me-extensive`. Where grill-me-extensive scopes a program by walking decisions, this skill produces the **instrument** that executes a decided program. Read `references/prompt-anatomy.md` for the full anatomy, `references/failure-patterns.md` for the measured failure modes each rule prevents, and `references/discovery-surface.md` when forging prompts that discover tools, MCPs, skills, or capacity upgrades (multi-registry + maturity flags + concrete borrow lines).

## When to use

- Writing or hardening an orchestration / session / unit prompt for Claude Code
- Turning a decision log or backlog into a paste-ready Claude prompt
- Fixing a prompt that caused restart-of-completed-work, false greens, or fragment overwrites
- Producing prompts for fan-out units, harvest units, or review units

Do **not** use for ordinary one-shot questions, casual chat, or prompts that do not need durability across context loss.

## The 8-section method

Produce prompts in this order. Omit a section only when it is genuinely inapplicable — never because it is long.

### 1. ROLE AND DELIVERABLE (who + what only)

State who Claude is in this turn and the single deliverable class. Ban pretence of access Claude does not have.

```
You are the [architect | implementer | reviewer | miner] for [program].
You produce [design + executable prompts | code + receipts | ranked shortlist].
You do NOT [claim measurements you did not run | re-derive banked facts | re-open settled decisions].
```

### 2. RESUME-DON'T-RESTART PREAMBLE

Name every completed gate, measurement, and artifact that must **not** be redone. Restarting completed work is the single most expensive failure mode in long programs.

```
DO NOT redo: [294-option selection, Gate 1, Wave-1 merges, measured envelope X].
Treat these as given. If your plan requires re-deriving them, your plan is wrong unless you produce a NEW measurement that supersedes them.
```

### 3. GROUND TRUTH (measured, banked)

List facts that were measured on the estate. Tag confidence. Forbid re-derivation.

- Numbers, paths, run IDs, policy IDs, commit SHAs
- Working envelopes (concurrency, stagger, node type)
- Verified absences (with the detector that proved absence)

### 4. BINDING DECISIONS (settled, do not re-litigate)

Owner-directed or grill-converged decisions. Re-opening them without new evidence is a defect.

### 5. HARD SAFETY BOUNDARIES (prohibitions)

State as bans, not preferences:

- Paths / branches / peers never to touch
- Commands never to run (`sync-from-live`, force-push, `--no-verify`, credential rotation without owner)
- Data classes that stay local
- Fragment-overwrite ban (see failure patterns)

### 6. EVIDENCE AND COMPLETION CONTRACT

Mandate the proof standard. Every completion claim needs:

| requirement | meaning |
|---|---|
| **Both-states** | Detector fires on known-broken AND is silent on known-good. Silent in both states measures nothing. |
| **AND-gate** | Exit 0 AND artifact exists AND size ≥ floor AND schema/sentinel validates AND no forbidden path changed. Exit alone is SEVERED, not SUCCESS. |
| **Mutation** | Reintroduce a representative defect in an isolated fixture; suite goes red; revert. |
| **Freshness** | Cached green carries a timestamp; stale green is UNKNOWN. |
| **Agent self-report** | A lead, never evidence. |

Require named artifacts, atomic writes, and a `RESUME.json` (or equivalent) at every wave boundary so the program survives compaction.

### 7. PHASED WORK (numbered, ordered, gated)

Break work into phases with explicit entry/exit criteria. Put gates **before** the work they protect (e.g. monitor ships before fan-out beyond smoke). Prefer:

**ADOPT → EXTEND → WIRE → CONSOLIDATE → PROVE → BUILD**

Mechanical questions go to code; agents get judgment only.

When the program is about discovering tools, MCPs, skills, or capacity upgrades, include a **discovery-surface** phase (or required lens set) per `references/discovery-surface.md`: GitHub-native structural search + parallel registries (package, MCP dirs, HF, early-signal social, vendor changelogs), maturity flags, concrete borrow lines, and inventory dedup. Do not forge a discovery program that only does keyword GitHub search.

### 8. OUTPUT / UNIT CONTRACT

For every unit that writes an artifact:

1. Write the full analysis to an **exact path**.
2. End with a line that is exactly `UNIT-COMPLETE: {id}` (or the program's sentinel).
3. If blocked, still write a partial file + sentinel + `BLOCKER` section — never invent contents.
4. Aim under a stated tool-call budget; write the one artifact once.

Calibrated confidence on claims: almost-certain (90–99%) · very likely (80–90%) · likely (55–80%) · roughly even (45–55%) · unlikely · very unlikely. Write `UNVERIFIED` **inline** next to the claim, with the settling experiment named.

## Question policy (encode in the prompt)

- At most **one** consolidated decision packet per session segment.
- Ask only when the answer cannot be derived mechanically, changes architecture/capability/security/irreversibility, and has genuinely non-equivalent options.
- No per-turn micro-questions. No permission theater for recommend-and-proceed work.
- Foundation-first: the 1–2 framing questions that reframe downstream work come before detail questions.

## Anti-patterns to ban inside the forged prompt

| anti-pattern | rule |
|---|---|
| Fragment trap | Never copy a generated MODIFY excerpt over a live file. Require complete files, exact patches with preimage hashes, or structural edits on anchors that occur exactly once. |
| Use-vs-mention | "Does this string appear" ≠ "does this key exist in the parsed object". Ask the structure. |
| Doneness vs completeness | Writer finished ≠ work finished ≠ run reached terminal state. Require the run's own terminal state. |
| Timeout believed but null | Re-read the submitted run object; assert timeout non-null. |
| Agents for mechanical work | Classification, diff, census → code. Agents for judgment only. |
| Uncontrolled zero | Validate every detector against known-present and known-broken before trusting absence. |
| Restart completed gates | Name them in the preamble; treat re-derivation as a defect. |
| GitHub-only discovery | When the program discovers tools/MCPs/skills/capacity, require the multi-registry discovery surface (see `references/discovery-surface.md`). |
| Star / download tourism | Candidate ranking needs maintenance signal, license, tests/examples, and a concrete borrow line — popularity is weak signal only. |
| Silent WIP promotion | Pre-1.0 / RFC / changelog-only items must carry an explicit maturity flag; they cannot enter production TIER-0 without owner risk acceptance. |
| Re-propose existing skills | Cross-ref Phase 0 inventory and live skills; duplicates merge or skip, never reappear as top-gems. |

## Modes (state which you are forging)

- **orchestration** — multi-phase program prompt for a full Claude Code session
- **unit** — single fan-out / mine / review unit with strict output contract
- **handoff** — bridge prompt that reconstructs state for a new session without restart
- **hardening** — take an existing weak prompt and rewrite it to this standard
- **substrate** — design + executable prompts for infrastructure (monitors, governors, loops)

Defaults: "write the next Claude prompt" → orchestration. "prompt for each worker" → unit. "resume this program" → handoff. "this prompt failed / caused rework" → hardening.

## Process

1. **Scout** the decision log, state-of-the-world, backlog, and prior prompts. Prefer measured numbers over narrative.
2. **Bank** ground truth and binding decisions into sections 3–4.
3. **Encode** safety bans and evidence contract before phases.
4. **Order** phases with gates first; prefer adopt/extend/wire over build. If discovery is in scope, include the multi-registry discovery surface from `references/discovery-surface.md`.
5. **Write** the prompt long and specific — working program prompts run to thousands of words with numbered phases. Brevity that omits a contract is a defect.
6. **Self-check** against `references/failure-patterns.md` and, when discovery is in scope, `references/discovery-surface.md` before delivery.
7. Optionally deliver a ≤200-word note of what changed vs the previous prompt and why.

## Deliverable shape

```markdown
# PROMPT — [name]

**Target:** Claude Code | Claude | …
**Attach:** [files]
**Mode:** orchestration | unit | handoff | …

## 0. Who you are and what you produce
## 1. Resume-don't-restart
## 2. Ground truth (measured)
## 3. Binding decisions
## 4. Hard safety boundaries
## 5. Evidence and completion contract
## 6. Phased work
## 7. Output / unit contract
## 8. Question policy
```

A forged prompt is not a summary of the problem. It is the instrument that makes the next session correct by default.

Stub template: `assets/orchestration-prompt-stub.md`.