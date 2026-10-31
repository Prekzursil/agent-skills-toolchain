---
paths:
- '**/*.go'
- '**/go.mod'
- '**/go.sum'
permalink: dqverify-repo-20261013/agent-self/config/rules/golang/hooks
---

# Go Hooks

> This file extends [common/hooks.md](../common/hooks.md) with Go specific content.

## PostToolUse Hooks

Configure in `~/.claude/settings.json`:

- **gofmt/goimports**: Auto-format `.go` files after edit
- **go vet**: Run static analysis after editing `.go` files
- **staticcheck**: Run extended static checks on modified packages