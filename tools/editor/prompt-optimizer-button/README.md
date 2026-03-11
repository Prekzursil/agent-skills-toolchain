# Prompt Optimizer Button v2

A fast, local-first VS Code extension that optimizes selected prompt text without opening an external browser.

## Runtime model
- Runs inside the VS Code extension host.
- Keeps the same extension ID as the earlier browser-launching build.
- Uses deterministic local prompt shaping plus `vscode.diff` for review.

## What changed
- no `openExternal`
- deterministic local prompt optimization
- inline diff via `vscode.diff`
- actions to **Replace**, **Insert Below**, or **Copy**
- compatibility aliases for the old commands

## Presets
- General
- Codex task
- Bug report
- Research request

## Main command
- `Prompt Optimizer: Optimize Prompt`

## Local validation
```powershell
node --check .\extension.js
node .\scripts\smoke-test.js
npx --yes @vscode/vsce package
```
