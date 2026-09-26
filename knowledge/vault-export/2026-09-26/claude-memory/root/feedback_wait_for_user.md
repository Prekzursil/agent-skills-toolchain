---
name: Wait for user before checking game state
description: Do not poll or auto-check game state - wait for user to confirm actions
  like unpausing
type: feedback
permalink: main/claude-memory/root/feedback-wait-for-user
---

When working with live game processes (Cheat Engine, memory scanning, breakpoints), do NOT auto-poll or run timed checks. Wait for the user to explicitly confirm they have performed an action (unpause, take damage, etc.) before checking results.

**Why:** Polling without user confirmation produces stale/invalid data. The game may be paused, the user may not have performed the action yet, or the state may have changed between the action and the check.

**How to apply:** Always wait for explicit user confirmation before reading breakpoint hits, HP values, or any game state that depends on gameplay having occurred.