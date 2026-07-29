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
# Security Guidelines

> AGENTS.md §9 is the always-on security floor (no secrets, no `--no-verify`, no
> force-push to main, validate inputs). The detailed checklist below is code-turn-scoped.

## Mandatory Security Checks

Before ANY commit:
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (sanitized HTML)
- [ ] CSRF protection enabled
- [ ] Authentication/authorization verified
- [ ] Rate limiting on all endpoints
- [ ] Error messages don't leak sensitive data

## Secret Management

- NEVER hardcode secrets in source code
- ALWAYS use environment variables or a secret manager
- Validate that required secrets are present at startup
- Rotate any secrets that may have been exposed

## Security Response Protocol

If security issue found:
1. STOP immediately
2. Use **security-reviewer** agent
3. Fix CRITICAL issues before continuing
4. Rotate any exposed secrets
5. Review entire codebase for similar issues
