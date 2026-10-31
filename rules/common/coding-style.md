---
paths:
- '**/*.py'
- '**/*.ts'
- '**/*.tsx'
- '**/*.js'
- '**/*.jsx'
- '**/*.go'
- '**/*.rs'
- '**/*.java'
- '**/*.rb'
- '**/*.php'
- '**/*.c'
- '**/*.cpp'
- '**/*.h'
- '**/*.cs'
- '**/*.swift'
- '**/*.kt'
- '**/*.sh'
- '**/*.cc'
- '**/*.cgi'
- '**/*.csproj'
- '**/*.css'
- '**/*.csx'
- '**/*.cxx'
- '**/*.dart'
- '**/*.hh'
- '**/*.hpp'
- '**/*.html'
- '**/*.kts'
- '**/*.pl'
- '**/*.pm'
- '**/*.psgi'
- '**/*.pyi'
- '**/*.scss'
- '**/*.sln'
- '**/*.svelte'
- '**/*.t'
- '**/*.vue'
permalink: dqverify-repo-20261013/rules/common/coding-style
---

# Coding Style

## Immutability (CRITICAL)

> **Language note**: This rule may be overridden by language-specific rules for languages where
> this pattern is not idiomatic. Where `rules/<language>/coding-style.md` states an override, the
> language-specific rule **wins** — specific beats general. Current overrides:
> [golang/coding-style.md](../golang/coding-style.md) (pointer receivers, functional options)
> and [rust/coding-style.md](../rust/coding-style.md) (`let mut`, consuming `mut self` builders).
> The marker lives here, not only in `rules/README.md`, because that README is scoped to
> `**/*.__never_load__` and never enters context — this rule does.

ALWAYS create new objects, NEVER mutate existing ones:

```
// Pseudocode
WRONG:  modify(original, field, value) → changes original in-place
CORRECT: update(original, field, value) → returns new copy with change
```

Rationale: Immutable data prevents hidden side effects, makes debugging easier, and enables safe concurrency.

## File Organization

MANY SMALL FILES > FEW LARGE FILES:
- High cohesion, low coupling
- 200-400 lines typical, 800 max
- Extract utilities from large modules
- Organize by feature/domain, not by type

## Error Handling

ALWAYS handle errors comprehensively:
- Handle errors explicitly at every level
- Provide user-friendly error messages in UI-facing code
- Log detailed error context on the server side
- Never silently swallow errors

## Input Validation

ALWAYS validate at system boundaries:
- Validate all user input before processing
- Use schema-based validation where available
- Fail fast with clear error messages
- Never trust external data (API responses, user input, file content)

## Code Quality Checklist

Before marking work complete:
- [ ] Code is readable and well-named
- [ ] Functions are small (<50 lines)
- [ ] Files are focused (<800 lines)
- [ ] No deep nesting (>4 levels)
- [ ] Proper error handling
- [ ] No hardcoded values (use constants or config)
- [ ] No mutation (immutable patterns used), unless a language override above applies