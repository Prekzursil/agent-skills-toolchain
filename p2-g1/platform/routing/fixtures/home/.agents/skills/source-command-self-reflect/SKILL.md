---
name: "source-command-self-reflect"
description: "Extract learnings from recent PR reviews, conversations, and session patterns to update the knowledge base"
---

# source-command-self-reflect

Use this skill when the user asks to run the migrated source command `self-reflect`.

## Command Template

# BEADS Self-Reflect

You are performing a self-reflection for the BEADS agent swarm. Your job is to analyze PR review comments, conversation history, and session patterns to extract high-quality, reusable learnings.

**Philosophy**: Be judicious. Quality over quantity. Each learning should make future development measurably better.

## Phase A: PR Comment Analysis

### Step 1: Fetch PR Comments

```bash
GITHUB_TOKEN=$(gh auth token) npx tsx scripts/beads-fetch-pr-comments.ts --days 7
```

This outputs PR comments to `.beads/temp/pr-comments.json`.

### Step 2: Extract CodeRabbit's Structured Learnings

```bash
cat .beads/temp/pr-comments.json | jq -r '.comments[].body' | grep -A5 "^Learnt from:" | grep "^Learning:" | sed 's/^Learning: //' | sort -u
```

### Evaluate Each CodeRabbit Learning

**NOT all CodeRabbit learnings are equal.** Evaluate each one:

#### ACCEPT (High Value)

- **Applies to patterns**: `Applies to **/*.test.ts: ...` - Actionable file-scoped rules
- **NEVER/ALWAYS rules**: Clear, enforceable constraints
- **Security/Performance**: Critical quality gates
- **Gotchas with context**: Explains WHY something is problematic

#### REJECT or DEFER (Low Value)

- **PR-specific context**: "In PR #X, someone did Y" - Too specific unless the pattern generalizes
- **Personality observations**: "Developer provides detailed updates" - Not actionable

### Quality Filter Questions
### Phase B: Conversation & Session Mining (Optional)
### Phase C: Config Reflection (Optional)
### Step 3: Analyze Comment Patterns
### Pattern Detection Checklist
### Step 4: Present Candidates for Approval
### Candidate Learnings
