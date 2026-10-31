---
name: "source-command-aside"
description: "Answer a quick side question without interrupting or losing context from the current task. Resume work automatically after answering."
---

# source-command-aside

Use this skill when the user asks to run the migrated source command `aside`.

## Command Template

# Aside Command

Ask a question mid-task and get an immediate, focused answer — then continue right where you left off. The current task, files, and context are never modified.

## When to Use

- You're curious about something while Codex is working and don't want to lose momentum
- You need a quick explanation of code Codex is currently editing
- You want a second opinion or clarification on a decision without derailing the task
- You need to understand an error, concept, or pattern before Codex proceeds
- You want to ask something unrelated to the current task without starting a new session

## Usage

```
/aside <your question>
/aside what does this function actually return?
/aside is this pattern thread-safe?
/aside why are we using X instead of Y here?
/aside what's the difference between foo() and bar()?
/aside should we be worried about the N+1 query we just added?
```

## Process

### Step 1: Freeze the current task state

Before answering anything, mentally note:
- What is the active task? (what file, feature, or problem was being worked on)
- What step was in progress at the moment `/aside` was invoked?
- What was about to happen next?

Do NOT touch, edit, create, or delete any files during the aside.

### Step 2: Answer the question directly

Answer the question in the most concise form that is still complete and useful.

- Lead with the answer, not the reasoning

### Step 3: Resume the main task
### Edge Cases
### Example Output
### Notes
