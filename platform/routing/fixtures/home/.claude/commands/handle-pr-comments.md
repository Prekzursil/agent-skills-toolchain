# /handle-pr-comments

Handle review comments on pull requests with appropriate responses and resolutions.

## Usage

```text
/handle-pr-comments <pr-number>
```

## Overview

This command helps systematically address PR review comments from automated tools (like CodeRabbit) and human reviewers. It ensures consistent, professional responses that acknowledge the AI assistance.

---

## CRITICAL: Complete PR Lifecycle Protocol

**A PR is NOT complete until ALL of the following are true:**

1. All CI checks pass
2. **EVERY** code review comment has been addressed (including trivial/nitpicks)
3. **EVERY** comment thread has received an individual response
4. All threads are marked as resolved (after reviewer approval)
5. Any work > 1 day has a GitHub issue created
6. No pending reviewer comments awaiting response
7. ALL tests pass, there are no pre-existing issues or flaky tests - these are excuses. Fix the underlying issues, don't disable tests.
