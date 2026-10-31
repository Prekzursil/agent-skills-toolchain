---
paths:
- '**/*.go'
- '**/go.mod'
- '**/go.sum'
permalink: dqverify-repo-20261013/rules/golang/coding-style
---

# Go Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md) with Go specific content.

## Formatting

- **gofmt** and **goimports** are mandatory — no style debates

## Mutability

> **Language note**: this section overrides the "Immutability (CRITICAL)" rule in
> [common/coding-style.md](../common/coding-style.md) for Go.

The common rule says "ALWAYS create new objects, NEVER mutate existing ones". That absolute
does **not** apply to Go, and applying it produces wrong code:

- **Pointer receivers that mutate the receiver are idiomatic** — `func (s *Server) SetPort(...)`.
  A value receiver mutates a *copy*, so the write is silently lost.
- **The functional-options constructor in [patterns.md](patterns.md) requires mutation.**
  `Option` is `func(*Server)`, so `WithPort(9090)` must assign `s.port`. An option cannot
  return a replacement value without changing that signature, so obeying the common ban while
  keeping the prescribed contract leaves `NewServer(WithPort(9090))` on its 8080 default.
- `append`, `sort.Slice`, `copy`, and mutex-guarded shared state all mutate in place by design.

Still avoid, because these are the real hazards the common rule is aiming at:

- mutating a caller-owned argument the caller did not opt into (document it if you must)
- mutating shared state without a lock or channel
- retaining a pointer to a loop variable or to a caller's slice backing array

## Design Principles

- Accept interfaces, return structs
- Keep interfaces small (1-3 methods)

## Error Handling

Always wrap errors with context:

```go
if err != nil {
    return fmt.Errorf("failed to create user: %w", err)
}
```

## Reference

See skill: `golang-patterns` for comprehensive Go idioms and patterns.