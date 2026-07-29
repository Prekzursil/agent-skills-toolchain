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
---
# Testing Requirements

## Minimum Test Coverage: per `.coverage-thresholds.json` (100% on metaswarm; 80%+ where none is defined)

**The SSOT outranks any agent's or skill's own default.** `agents/tdd-guide.md` advertises a flat
"80%+"; that number is its **fallback** for a project with no `.coverage-thresholds.json`, never a
pass mark and never a ceiling. When the file exists, its numbers are the only pass/fail line —
`tools/editor/metaswarm/.coverage-thresholds.json` requires 100 on lines, branches, functions and
statements, so 80% there is a FAIL even if tdd-guide reports compliant. Read the file before
reporting coverage compliance; do not report a threshold you did not read.

Test Types (ALL required):
1. **Unit Tests** - Individual functions, utilities, components
2. **Integration Tests** - API endpoints, database operations
3. **E2E Tests** - Critical user flows (framework chosen per language)

## Test-Driven Development

MANDATORY workflow:
1. Write test first (RED)
2. Run test - it should FAIL
3. Write minimal implementation (GREEN)
4. Run test - it should PASS
5. Refactor (IMPROVE)
6. Verify coverage meets `.coverage-thresholds.json` (SSOT; 80%+ if none)

## Troubleshooting Test Failures

1. Use **tdd-guide** agent
2. Check test isolation
3. Verify mocks are correct
4. Fix implementation, not tests (unless tests are wrong)

## Agent Support

- **tdd-guide** - Use PROACTIVELY for new features, enforces write-tests-first. Its "80%+" is
  the no-SSOT **fallback** only; where `.coverage-thresholds.json` exists, that file wins and the
  agent's verdict does not clear the gate.
