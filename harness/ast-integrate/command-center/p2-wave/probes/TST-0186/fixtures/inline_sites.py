"""Planted inline prose construction sites. The scanner must fire on these.

Not imported by the runner. Strings are command templates an agent would
emit if it inlined commit/PR/prompt prose onto a shell command line.
"""

BAD_COMMIT = "git commit -m '{message}'"
BAD_COMMIT_DOUBLE = 'git commit -m "{message}"'
BAD_PR_BODY = "gh pr create --title t --body '{body}'"
BAD_PROMPT = "codex --prompt '{prompt}'"
BAD_BASH = "bash -c 'codex --prompt {prompt}'"
