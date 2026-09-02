"""Planted file-route construction sites. The scanner must stay silent."""

GOOD_COMMIT = "git commit -F {path}"
GOOD_PR_BODY = "gh pr create --title t --body-file {path}"
GOOD_PROMPT = "codex --ignore-user-config --prompt-file {path}"
