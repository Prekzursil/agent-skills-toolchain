---
title: Grill-100 gem-stack locks G-1 to G-6 pending G-7 (2026-08-27)
type: note
permalink: main/reference/grill/grill-100-gem-stack-locks-g-1-to-g-6-pending-g-7-2026-08-27
tags:
- grill
- mcp
- g6-6b
- sync
- evpi
---

# Grill-100 locks (valid_as_of: 2026-08-27 ~02:49)

Canonical: `C:\Users\Prekzursil\Cowork\output\grill-100-gem-stack_2026-08-26.md`

## Locked

- G-1…G-5 as before (A+B+C, 2A, G3-D, 4D, 5B)
- G-6 **6B**: sibling quarantines 31 to sidecar; live mcp.json = 6 only

## Live G-7 (pending)

`sync_shared_state` / `merge_cursor_mcp_servers` second loop re-adds missing registry keys as disabled. 6B does not survive `--write` unless patch (7A), accept G3-D restore (7B), freeze (7C), or dry-run first (7D). Recommended 7A. No implement this turn.

## Relations

- supersedes [[Grill-100 gem-stack locks G-1 to G-5 pending G-6 (2026-08-27)]] on the live-ask
