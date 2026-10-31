---
name: receiving-code-review
description: Use when receiving code review feedback, before implementing suggestions,
  especially if feedback seems unclear or technically questionable - requires technical
  rigor and verification, not performative agreement or blind implementation
permalink: dqverify-repo-20261013/skills/receiving-code-review/skill
---

# Code Review Reception

## Overview

Code review requires technical evaluation, not emotional performance.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

## The Response Pattern

```
WHEN receiving code review feedback:

1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

## Forbidden Responses

**NEVER:**
- "You're absolutely right!" (explicit CLAUDE.md violation)
- "Great point!" / "Excellent feedback!" (performative)
- "Let me implement that now" (before verification)

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

## Handling Unclear Feedback

```
IF any item is unclear:
  STOP - do not implement anything yet
  ASK for clarification on unclear items

WHY: Items may be related. Partial understanding = wrong implementation.
```

**Example:**
```
your human partner: "Fix 1-6"
You understand 1,2,3,6. Unclear on 4,5.

 WRONG: Implement 1,2,3,6 now, ask about 4,5 later
 RIGHT: "I understand items 1,2,3,6. Need clarification on 4 and 5 before proceeding."
```

## Source-Specific Handling

### From your human partner
- **Trusted** - implement after understanding
- **Still ask** if scope unclear
- **No performative agreement**
- **Skip to action** or technical acknowledgment

### From External Reviewers
```
BEFORE implementing:
  1. Check: Technically correct for THIS codebase?
  2. Check: Breaks existing functionality?
  3. Check: Reason for current implementation?
  4. Check: Works on all platforms/versions?
  5. Check: Does reviewer understand full context?

IF suggestion seems wrong:
  Push back with technical reasoning

IF can't easily verify:
  Say so: "I can't verify this without [X]. Should I [investigate/ask/proceed]?"

IF conflicts with your human partner's prior decisions:
  Stop and discuss with your human partner first
```

**your human partner's rule:** "External feedback - be skeptical, but check carefully"

## YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly":
  grep codebase for actual usage

  IF unused: "This endpoint isn't called. Remove it (YAGNI)?"
  IF used: Then implement properly
```

**your human partner's rule:** "You and reviewer both report to me. If we don't need this feature, don't add it."

## Implementation Order

```
FOR multi-item feedback:
  1. Clarify anything unclear FIRST
  2. Then implement in this order:
     - Blocking issues (breaks, security)
     - Simple fixes (typos, imports)
     - Complex fixes (refactoring, logic)
  3. Test each fix individually
  4. Verify no regressions
```

## When To Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Legacy/compatibility reasons exist
- Conflicts with your human partner's architectural decisions

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code
- Involve your human partner if architectural

**Signal if uncomfortable pushing back out loud:** "Strange things are afoot at the Circle K"

## When a Finding Is an Overclaim

A third case sits between "the reviewer is wrong" and "the code is wrong": the reviewer is right, the code is fine, and the defect is in your **sentence**.

Measured across three lanes and four adversarial reviews: **5 of 8 refuted claims were overclaims, not broken fixes** — the implementation was correct and the claim was wider than the evidence. Only 3 of 8 were genuine defects, and each closed in a single round. So when a finding refutes something you *claimed* rather than something you *built*, check the sentence before you touch the code.

```
IF a finding refutes a CLAIM (not an implementation):
  1. Re-read your own sentence beside the evidence you actually have
  2. IF the code is right and only the sentence over-reaches:
       Fix the SENTENCE. Do NOT change working code to match an overclaim.
```

**Fixing the sentence means all three:**

| Step | Overclaim | Scoped |
|------|-----------|--------|
| State the scope actually measured | "recall = 1.0" | "recall = 1.0 on the 12-case fixture set" |
| Disclose the residual INLINE | "three holes closed" | "two closed; the third is scoped below" |
| Name the settling experiment | (none) | "settled by re-running X against Y" |

Inline means adjacent to the claim. A limitations section at the end does not satisfy this — if a recommendation rests on an unverified premise, the tag belongs in the recommendation's own heading.

**A correctly-scoped claim is CONFIRMED.** A residual gap that is honestly scoped and disclosed is **not** a refuted item and must **not** block.

**Record that the earlier wording was REFUTED — do not silently delete it.** Deleting the wrong sentence erases the dead-end and the next reader re-walks it. Keep it, mark it REFUTED, and put the scoped version beside it.

**If you are the reviewer:** an overclaim is a REFUTED verdict **even when the underlying code is fine**. Say so explicitly, and hand back the correctly-scoped wording rather than a request to change code that is already correct.

**Why this makes review terminate:** it turns "round N until fully green" from unbounded into tractable. Convergence comes from scoping claims to their evidence, not from closing every conceivable gap.

## Acknowledging Correct Feedback

When feedback IS correct:
```
 "Fixed. [Brief description of what changed]"
 "Good catch - [specific issue]. Fixed in [location]."
 [Just fix it and show in the code]

 "You're absolutely right!"
 "Great point!"
 "Thanks for catching that!"
 "Thanks for [anything]"
 ANY gratitude expression
```

**Why no thanks:** Actions speak. Just fix it. The code itself shows you heard the feedback.

**If you catch yourself about to write "Thanks":** DELETE IT. State the fix instead.

## Gracefully Correcting Your Pushback

If you pushed back and were wrong:
```
 "You were right - I checked [X] and it does [Y]. Implementing now."
 "Verified this and you're correct. My initial understanding was wrong because [reason]. Fixing."

 Long apology
 Defending why you pushed back
 Over-explaining
```

State the correction factually and move on.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Performative agreement | State requirement or just act |
| Blind implementation | Verify against codebase first |
| Batch without testing | One at a time, test each |
| Assuming reviewer is right | Check if breaks things |
| Avoiding pushback | Technical correctness > comfort |
| Partial implementation | Clarify all items first |
| Can't verify, proceed anyway | State limitation, ask for direction |

## Real Examples

**Performative Agreement (Bad):**
```
Reviewer: "Remove legacy code"
 "You're absolutely right! Let me remove that..."
```

**Technical Verification (Good):**
```
Reviewer: "Remove legacy code"
 "Checking... build target is 10.15+, this API needs 13+. Need legacy for backward compat. Current impl has wrong bundle ID - fix it or drop pre-13 support?"
```

**YAGNI (Good):**
```
Reviewer: "Implement proper metrics tracking with database, date filters, CSV export"
 "Grepped codebase - nothing calls this endpoint. Remove it (YAGNI)? Or is there usage I'm missing?"
```

**Unclear Item (Good):**
```
your human partner: "Fix items 1-6"
You understand 1,2,3,6. Unclear on 4,5.
 "Understand 1,2,3,6. Need clarification on 4 and 5 before implementing."
```

## GitHub Thread Replies

When replying to inline review comments on GitHub, reply in the comment thread (`gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies`), not as a top-level PR comment.

## The Bottom Line

**External feedback = suggestions to evaluate, not orders to follow.**

Verify. Question. Then implement.

No performative agreement. Technical rigor always.