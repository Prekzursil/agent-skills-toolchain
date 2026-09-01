# Shared control-plane pointer

This file is not a second contract. The behavior contract is
`C:\Users\Prekzursil\AGENTS.md`. Skills SSOT is `C:\Users\Prekzursil\.agents\skills`.
MCP inventory SSOT is `C:\Users\Prekzursil\.agents\agents.json`.
After skill or rule edits, run `C:\Users\Prekzursil\.agents\scripts\sync_shared_state.ps1`.

## Universal harness share (HARD)
Every agent runtime (Claude, Codex, Cursor, Grok, Goose, Agy, Fabric, and any other) MUST load skills from C:\Users\Prekzursil\.agents\skills and rules/behavior from C:\Users\Prekzursil\AGENTS.md (or a 10-line pointer file that only includes that). Never maintain a second diverged copy. sync_shared_state.ps1 is mandatory after skill/rule edits. skills.daily must be the vault, not a subset.
