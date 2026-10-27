---
name: "source-command-save-session"
description: "Save current session state to a dated file in ~/.Codex/sessions/ so work can be resumed in a future session with full context."
---

# source-command-save-session

Use this skill when the user asks to run the migrated source command `save-session`.

## Command Template

# Save Session Command

Capture everything that happened in this session — what was built, what worked, what failed, what's left — and write it to a dated file so the next session can pick up exactly where this one left off.

## When to Use

- End of a work session before closing Codex
- Before hitting context limits (run this first, then start a fresh session)
- After solving a complex problem you want to remember
- Any time you need to hand off context to a future session

## Process

### Step 1: Gather context

Before writing the file, collect:

- Read all files modified during this session (use git diff or recall from conversation)
- Review what was discussed, attempted, and decided
- Note any errors encountered and how they were resolved (or not)
- Check current test/build status if relevant

### Step 2: Create the sessions folder if it doesn't exist

Create the canonical sessions folder in the user's Codex home directory:

```bash
mkdir -p ~/.Codex/sessions
```

### Step 3: Write the session file

Create `~/.Codex/sessions/YYYY-MM-DD-<short-id>-session.tmp`, using today's actual date and a short-id that satisfies the rules enforced by `SESSION_FILENAME_REGEX` in `session-manager.js`:

- Allowed characters: lowercase `a-z`, digits `0-9`, hyphens `-`
- Minimum length: 8 characters
- No uppercase letters, no underscores, no spaces

Valid examples: `abc123de`, `a1b2c3d4`, `frontend-worktree-1`

### Step 4: Populate the file with all sections below
### Step 5: Show the file to the user
### Session File Format
### Session: YYYY-MM-DD
### What We Are Building
### What WORKED (with evidence)
