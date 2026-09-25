---
paths:
  - "**/*.py"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.go"
  - "**/*.rs"
  - "**/*.java"
  - "**/*.rb"
  - "**/*.php"
  - "**/*.c"
  - "**/*.cpp"
  - "**/*.h"
  - "**/*.cs"
  - "**/*.swift"
  - "**/*.kt"
  - "**/*.sh"
  - "**/*.cc"
  - "**/*.cgi"
  - "**/*.csproj"
  - "**/*.css"
  - "**/*.csx"
  - "**/*.cxx"
  - "**/*.dart"
  - "**/*.hh"
  - "**/*.hpp"
  - "**/*.html"
  - "**/*.kts"
  - "**/*.pl"
  - "**/*.pm"
  - "**/*.psgi"
  - "**/*.pyi"
  - "**/*.scss"
  - "**/*.sln"
  - "**/*.svelte"
  - "**/*.t"
  - "**/*.vue"
---
# Code Review Standards

## Purpose

Code review ensures quality, security, and maintainability before code is merged. This rule defines when and how to conduct code reviews.

## When to Review

**MANDATORY review triggers:**

- After writing or modifying code
- Before any commit to shared branches
- When security-sensitive code is changed (auth, payments, user data)
- When architectural changes are made
- Before merging pull requests

**Pre-Review Requirements:**

Before requesting review, ensure:

- All automated checks (CI/CD) are passing
- Merge conflicts are resolved
- Branch is up to date with target branch

## Review Checklist

Before marking code complete:

- [ ] Code is readable and well-named
- [ ] Functions are focused (<50 lines)
- [ ] Files are cohesive (<800 lines)
- [ ] No deep nesting (>4 levels)
- [ ] Errors are handled explicitly
- [ ] No hardcoded secrets or credentials
- [ ] No console.log or debug statements
- [ ] Tests exist for new functionality
- [ ] Test coverage meets `.coverage-thresholds.json` (single source of truth; 80%+ if none defined)

## Security Review Triggers

**STOP and use security-reviewer agent when:**

- Authentication or authorization code
- User input handling
- Database queries
- File system operations
- External API calls
- Cryptographic operations
- Payment or financial code

## Review Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| CRITICAL | Security vulnerability or data loss risk | **BLOCK** - Must fix before merge |
| HIGH | Bug or significant quality issue | **WARN** - Should fix before merge |
| MEDIUM | Maintainability concern | **INFO** - Consider fixing |
| LOW | Style or minor suggestion | **NOTE** - Optional |

> **Language note — the HIGH row is the GENERAL default and it is overridable.** This table
> is the single source of truth for the *general* review outcome: a review holding HIGH but
> no CRITICAL is a WARN, not a block. Language-specific review surfaces MAY be deliberately
> stricter and block on HIGH; where they do, they say so in their own text. The surfaces that
> currently override this row are the **Python** review path
> ([`agents/python-reviewer.md`](../../agents/python-reviewer.md),
> [`commands/python-review.md`](../../commands/python-review.md),
> `skills/source-command-python-review`) and the **TypeScript/JavaScript** review path
> ([`agents/typescript-reviewer.md`](../../agents/typescript-reviewer.md)). Anything not on
> that list follows the WARN row. This marker lives here, next to the text it qualifies,
> because `rules/README.md` is scoped `**/*.__never_load__` and its "Rule Priority" section
> never enters a model's context — an override recorded only there is unresolvable at the
> point of use.

## Agent Usage

Use these agents for code review:

| Agent | Purpose |
|-------|---------|
| **code-reviewer** | General code quality, patterns, best practices |
| **security-reviewer** | Security vulnerabilities, OWASP Top 10 |
| **typescript-reviewer** | TypeScript/JavaScript specific issues |
| **python-reviewer** | Python specific issues |

## Review Workflow

```
1. Run git diff to understand changes
2. Check security checklist first
3. Review code quality checklist
4. Run relevant tests
5. Verify coverage meets `.coverage-thresholds.json` (SSOT; 80%+ if none)
6. Use appropriate agent for detailed review
```

## Common Issues to Catch

### Security

- Hardcoded credentials (API keys, passwords, tokens)
- SQL injection (string concatenation in queries)
- XSS vulnerabilities (unescaped user input)
- Path traversal (unsanitized file paths)
- CSRF protection missing
- Authentication bypasses

### Code Quality

- Large functions (>50 lines) - split into smaller
- Large files (>800 lines) - extract modules
- Deep nesting (>4 levels) - use early returns
- Missing error handling - handle explicitly
- Mutation patterns - prefer immutable operations
- Missing tests - add test coverage

### Performance

- N+1 queries - use JOINs or batching
- Missing pagination - add LIMIT to queries
- Unbounded queries - add constraints
- Missing caching - cache expensive operations

## Approval Criteria

- **Approve**: No CRITICAL or HIGH issues
- **Warning**: Only HIGH issues (merge with caution)
- **Block**: CRITICAL issues found
- **Scope**: these are the GENERAL criteria. A language-specific surface that declares itself
  stricter (see the Language note under [Review Severity Levels](#review-severity-levels))
  blocks on HIGH for its own language; that is an override of this list, not a contradiction
  of it.

## Integration with Other Rules

This rule works with:

- [testing.md](testing.md) - Test coverage requirements
- [security.md](security.md) - Security checklist
- [git-workflow.md](git-workflow.md) - Commit standards
- [agents.md](agents.md) - Agent delegation
