---
description: Review the profile-capture queue — approve or discard queued self-disclosure
  statements
permalink: dqverify-repo-20261013/commands/profile-review
---

# Profile review

Review the owner's profile-capture queue at
`C:\Users\Prekzursil\.claude\hooks\profile-capture\capture-queue.jsonl`.

The queue is JSONL; each line is `{"captured": ..., "session": ..., "text": ..., "status": "pending|approved|discarded"}`.
The Stop hook (`capture.py`) nags whenever >= 5 lines still carry `"status": "pending"`.
Nothing is ever written to any profile store by this command — "approved" only means the
statement may be cited as context; "discarded" means never cite it.

## Behavior

**With no arguments** (`$ARGUMENTS` empty): Read the queue file. List every line with
`"status": "pending"` numbered by its line number in the file, showing its `captured` date and
full `text`. Then ask the owner for picks in the form `<line>=approve` / `<line>=discard`
(space-separated, e.g. `1=discard 2=discard 3=approve`), plus the shorthand `all-discard` /
`all-approve`. Do NOT change anything yet.

**With arguments**: apply exactly the given picks (anything not named stays untouched):

1. Read the raw file. For each named line, replace only its `"status": "pending"` value with
   `"approved"` or `"discarded"` — never alter `captured`, `session`, or `text`.
2. Write the file back preserving every line and the original line order (keep the trailing
   newline; the file ends with one empty line by convention).
3. Re-read the file and count remaining `"status": "pending"` lines (exact substring match,
   same as capture.py uses). Report: picks applied, pending count before -> after, and whether
   the count is now below the hook's threshold of 5 (nag stops) or not.
4. If any `text` field looks like sensitive personal data (phone numbers, birth dates,
   addresses, credentials) and the owner asked to approve it, surface one plain warning line
   ("this will be citable context") but still apply their pick — the gate is theirs.

Never delete lines from the queue (append-only spirit; discarded lines remain as record).
Never touch `seen.txt` or `capture.py`.