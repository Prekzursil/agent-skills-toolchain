---
title: code-review
type: note
permalink: dqverify-repo-20261013/commands/code-review
---

# Code Review

Comprehensive security and quality review of uncommitted changes:

1. Get changed files: git diff --name-only HEAD

2. For each changed file, check for:

**Security Issues (CRITICAL):**
- Hardcoded credentials, API keys, tokens
- SQL injection vulnerabilities
- XSS vulnerabilities  
- Missing input validation
- Insecure dependencies
- Path traversal risks

**Code Quality (HIGH):**
- Functions > 50 lines
- Files > 800 lines
- Nesting depth > 4 levels
- Missing error handling
- console.log statements
- TODO/FIXME comments
- Missing JSDoc for public APIs

**Best Practices (MEDIUM):**
- Mutation patterns (use immutable instead)
- Emoji usage in code/comments
- Missing tests for new code
- Accessibility issues (a11y)

3. Generate report with:
   - Severity: CRITICAL, HIGH, MEDIUM, LOW
   - File location and line numbers
   - Issue description
   - Suggested fix

4. Apply the severity gate defined in [rules/common/code-review.md](../rules/common/code-review.md#review-severity-levels) — that table is the single source of truth for the outcome, and this command must not restate it differently:
   - **CRITICAL** → **BLOCK** the commit. Must be fixed before merge.
   - **HIGH** → **WARN**. Report it and advise fixing before merge; merge with caution. Do *not* block.
   - **MEDIUM** → INFO (consider fixing). **LOW** → NOTE (optional).

Never approve code with security vulnerabilities!