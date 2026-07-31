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
# Git Workflow

## Commit Message Format
```
<type>: <description>

<optional body>
```

Types: feat, fix, refactor, docs, test, chore, perf, ci

Note: Attribution disabled globally via ~/.claude/settings.json.

## Pull Requests

When creating a PR:

1. Analyze the full commit history, not just the latest commit —
   `git diff <base-branch>...HEAD` (three dots: the merge-base surface).
2. Draft a comprehensive PR summary from that diff.
3. Include a test plan with TODOs.
4. Push with `-u` if the branch is new, then open the PR.

`/pr-shepherd` is for AFTER the PR exists — it monitors CI, reviews and threads through
to merge. It resolves a PR number (explicit argument, else `gh pr view` for the branch)
and **exits 1 when there is none**, so it cannot do any of steps 1-4 on a branch that has
commits but no PR yet.

Full pre-git process (plan → TDD → review):
[development-workflow.md](./development-workflow.md).
