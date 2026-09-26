---
name: bc-verifier-robustness-fixes
description: Verifier/Closer trustworthiness fixes for the Ralph BC-unlock loop (cumulative
  hit-set, fail-closed, proxy-preserve) + loop recovery ops
metadata:
  node_type: memory
  type: project
  originSessionId: c5980bb4-6564-4a44-a055-9721b0720cee
permalink: main/claude-memory/root/bc-verifier-robustness-fixes
---

The Ralph BC-unlock Verifier→Closer cycle was untrustworthy. Root causes (verified against code + artifacts, correcting the review):
- NOT menu_unreachable false-zeros — those were ALREADY fail-loud (`verify_visible_events.py` writes `status` + exits 3; closer Rule 1 retries). The LIVE corruptor was **OCR variance**: per-iter `hit_count` swung 148–193 with scroll depth, and the closer read the band as "no growth" → premature `BC_UNLOCK_COMPLETE` (see `closer_decision_18`, iter-18).
- `precondition.py` `kill_port_8890()` killed a RESPONSIVE proxy (`connect_ex==0 → kill`) → BC refetched real data → injected events vanished → false-low.

Fixes applied 2026-05-24 (`dat-cache-decode/verify_visible_events.py` + `.ralph/precondition.py` + `.ralph/hats/bc-unlock-master.yml`):
1. **Monotonic cumulative hit-set** keyed by run_id → `reports/cumulative_hits.json`; `gap.json`/`visible_events.json` now carry `cumulative_hit_count` + `new_hits_this_iter`. Closer judges plateau on CUMULATIVE (non-decreasing, variance-immune), never per-iter `hit_count`.
2. **Fail-closed gating**: `status ∈ {ok, menu_unreachable, ocr_fail}`; `ocr_fail` = reached list but <3 OCR lines (returns 4). Closer Rule 1 = if `status != ok` → reverify, NEVER count as zero/plateau; completion requires `status==ok` AND cumulative flat ≥5 VALID iters.
3. **Deterministic scroll**: fixed-increment sweep, stop after 2 stale scrolls (bottom). `detect_screen` gained an OCR-anchor fallback (≥4 tile lines ⇒ special_stages) to kill the cat_base↔unknown bounce.
4. **Proxy preserve**: `kill_port_8890` preserves a responsive 8890, reaps only a wedged port.

Ops: loop driven by `.ralph/supervisor/outer-supervisor.ps1` (PARENT of ralph; gates = `ralph preflight` + `ralph hats validate -c ralph.yml -H <hats>` + `.ralph/preflight.py`). Reload hats mid-run = tree-kill ralph (watchdog relaunches `--continue`). If the SUPERVISOR itself dies, manual relaunch = `Start-Process pwsh -ArgumentList '-NoProfile','-File','.ralph/supervisor/outer-supervisor.ps1' -WindowStyle Hidden` (clear stale `.ralph/loop.lock` first). The `RalphSupervisorWatchdog` scheduled task is boot/logon-scoped — it does NOT health-respawn a mid-session death. **KNOWN FOLLOW-UP**: the watchdog restarts ralph on CLEAN completion (exit 0) via `--continue` → re-completion loop (wasteful); a fresh launch (new loop-id) resets it. Relates to [[battlecats_calendar_unlock_stack]], [[ralph-headless-mcp-trust-gate]].