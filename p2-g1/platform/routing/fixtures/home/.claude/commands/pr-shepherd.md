---
description: Monitor a PR through to merge - handles CI failures, reviews, and thread resolution
---

# PR Shepherd

Monitor a PR from creation through merge, handling CI failures, review comments, and thread resolution automatically.

## Usage

```text
/pr-shepherd [pr-number]
```

If no PR number is provided, uses the PR associated with the current branch.

## What This Does

1. **Monitors CI/CD** - Polls every 60 seconds for status changes
2. **Monitors Reviews** - Watches for new comments and unresolved threads
3. **Auto-fixes simple issues** - Lint, prettier, type errors
4. **Asks before complex fixes** - Presents options with pros/cons for approval
5. **Handles review comments** - Delegates to `handling-pr-comments` skill
6. **Checkpoints at 4 hours** - Asks if you want to continue or handoff

## Steps

1. **Get PR information**:

   ```bash
   PR_NUMBER=${1:-$(gh pr view --json number -q .number 2>/dev/null)}
   if [ -z "$PR_NUMBER" ]; then
     echo "No PR found. Provide PR number: /pr-shepherd 123"
