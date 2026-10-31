---
name: "source-command-resume-session"
description: "Load the most recent session file from ~/.Codex/sessions/ and resume work with full context from where the last session ended."
---

# source-command-resume-session

Use this skill when the user asks to run the migrated source command `resume-session`.

## Command Template

# Resume Session Command

Load the last saved session state and orient fully before doing any work.
This command is the counterpart to `/save-session`.

## When to Use

- Starting a new session to continue work from a previous day
- After starting a fresh session due to context limits
- When handing off a session file from another source (just provide the file path)
- Any time you have a session file and want Codex to fully absorb it before proceeding

## Usage

```
/resume-session                                                      # loads most recent file in ~/.Codex/sessions/
/resume-session 2024-01-15                                           # loads most recent session for that date
/resume-session ~/.Codex/sessions/2024-01-15-session.tmp           # loads a specific legacy-format file
/resume-session ~/.Codex/sessions/2024-01-15-abc123de-session.tmp  # loads a current short-id session file
```

## Process

### Step 1: Find the session file

If no argument provided:

1. Check `~/.Codex/sessions/`
2. Pick the most recently modified `*-session.tmp` file
3. If the folder does not exist or has no matching files, tell the user:
   ```
   No session files found in ~/.Codex/sessions/
   Run /save-session at the end of a session to create one.
   ```
   Then stop.

If an argument is provided:

- If it looks like a date (`YYYY-MM-DD`), search `~/.Codex/sessions/` for files matching

### Step 2: Read the entire session file
### Step 3: Confirm understanding
### Step 4: Wait for the user
### Edge Cases
### Example Output
### Notes
