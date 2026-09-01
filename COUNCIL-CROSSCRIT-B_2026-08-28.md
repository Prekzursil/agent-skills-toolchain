# COUNCIL-CROSSCRIT-B_2026-08-28 (Round 2 Cross-Critique)

**Date:** 28.08.2026
**Scope:** Structural/Memory Council Adjudication

## 1. Vector-Disable (Semantic Memory)
**Verdict: MODIFY (Retract permanent disable)**
*   **Evidence:** `BASIC-MEMORY-RELIABILITY_2026-08-27.md` proves the crash-loop was caused by an oversized entity (a 378 KB session catalog yielding 1,482 chunks) and an impatient watchdog killing slow warm-ups. With the catalog moved out and the watchdog deferred via a fresh marker, a 10-minute stability probe passed cleanly.
*   **Comparison:** Permanent disable sacrifices a core feature unnecessarily now that the root cause is fixed. A circuit-breaker degradation to FTS is ideal but requires code changes. The best immediate path is "no change + size policy" (ban files >100KB from the vault).
*   **Reversible A/B Test:** Run with semantic memory enabled for 48 hours under the new size policy. Monitor `daemon-*.err.log` and `basic-memory-supervisor.log` for "bound but HTTP unresponsive" strikes. If strikes exceed 3 per day, flip `BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED=false` for the next 48 hours and compare watchdog kills.

## 2. WSL2+systemd Offload
**Verdict: REJECT**
*   **Red-Team:** WSL2 uses `vmmem`, drawing from the exact same starved physical RAM pool (~1.8 GB free). Moving the daemon to WSL does not create more memory; it merely shifts the OOM/trim pressure to the Linux kernel, which will aggressively kill processes or swap heavily, replicating the timeouts. Furthermore, WSL introduces networking complexities (localhost forwarding), suspend/resume lifecycle quirks, and a new failure boundary.
*   **Strongest Dissent:** "It violates the anti-overfit rule by adding a virtualization layer to solve a memory problem that virtualization cannot fix."

## 3. Home-as-Workspace (Double-loading MCPs)
**Verdict: KEEP (Dedicated Root)**
*   **Red-Team:** Using NTFS junctions to map the home directory into a workspace folder risks infinite loops in recursive searches and backup tools. Relying on Cursor UI project-scope toggles is fragile against path casing bugs and doesn't guarantee the engine won't double-load.
*   **Action:** Migrate to a dedicated workspace root (e.g., `C:\Users\Prekzursil\projects`). It requires behavioral change but cleanly eliminates the RAM tax of double-loaded MCPs and 358-skill listings without technical debt.

## 4. RAM-seconds Lease (Quorum-sensing)
**Verdict: KEEP**
*   **Assessment:** High value, low complexity. Using `LockFileEx` as both an admission ticket and a mutex is brilliant. The Windows kernel guarantees lock release on process death (even hard crashes), eliminating the "dead-but-alive" JSON registry stale state. It coordinates runtimes (Cursor, Claude Code) without a second orchestrator daemon.
*   **Implementation Note:** Requires a strict policy (and perhaps a 15-line helper script) that all mutating agents must acquire the lock before spawning.

## 5. Health Visibility + Drift Warnings
**Verdict: KEEP (Minimal Surface)**
*   **Assessment:** A terminal banner appended to `sync_shared_state.ps1` with `DRIFT:WARN` sentinels is cheap, un-ignorable, and read-only.
*   **Red-Team:** A VS Code status bar item or tray notifier risks alert fatigue and requires extension maintenance. Stick to the end-of-run sync script check first.

---

## Ranked Top 5 Actions

1. **Implement RAM-seconds lease (Kernel Lock):** Enforce `LockFileEx` per-worktree for mutating agents to prevent concurrent edits and retry storms. (Addresses Issues 1 & 2 natively).
2. **Migrate to Dedicated Workspace Root:** Move active development to a dedicated folder (e.g., `~\projects`) to stop Cursor from double-loading `mcp.json` and wasting RAM.
3. **Add Bridge Drift Check to Sync Script:** Append a read-only check to `sync_shared_state.ps1` that asserts invariants (like the Claude local bridge file) and emits `DRIFT:WARN`.
4. **Enforce Vault Size Policy (Retract Vector-Disable):** Keep semantic memory enabled, but strictly ban machine-generated files >100KB from `D:\basic-memory`. Execute the 48-hour A/B test.
5. **Implement Name-Only Harness Sweeps:** Enforce that agent sweeps use Glob/filenames and never read the bodies of dual-use/RE skills to avoid cyber-safeguard blocks.